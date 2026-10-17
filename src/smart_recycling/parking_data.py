"""Small, licensed parking snapshot; mapped access never implies a vacant space."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from smart_recycling.routing_models import Coordinates, RoutingError

PUBLIC_ACCESS = {"yes", "permissive"}


def public_parking(tags: dict[str, str]) -> bool:
    """Require explicit public access; exclude private/conditional/vehicle restrictions."""
    return (
        tags.get("amenity") == "parking"
        and tags.get("access") in PUBLIC_ACCESS
        and all(
            tags.get(key, "yes") in PUBLIC_ACCESS
            for key in ("vehicle", "motor_vehicle", "motorcar", "foot")
        )
        and not any("conditional" in key for key in tags)
        and tags.get("parking") not in {"underground", "multi-storey", "rooftop", "lane"}
        and tags.get("disused") != "yes"
        and tags.get("abandoned") != "yes"
        and tags.get("opening_hours") != "off"
    )


class ParkingPlace(Coordinates):
    id: str = Field(pattern=r"^osm-(node|way|relation)-[1-9][0-9]*$")
    name: str = Field(min_length=1, max_length=300)
    access: Literal["yes", "permissive"]
    point_kind: Literal["mapped_point", "driveway_crossing"]
    fee: str = Field(default="unknown", max_length=300)
    opening_hours: str = Field(default="unknown", max_length=500)
    operator: str = Field(default="", max_length=300)
    driveway_osm_id: int | None = None

    @property
    def source_url(self):
        _, kind, number = self.id.split("-")
        return f"https://www.openstreetmap.org/{kind}/{number}"


class ParkingSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    dataset_version: str
    source_timestamp: str
    source_url: str
    source_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    records_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    license: Literal["ODbL-1.0"] = "ODbL-1.0"
    attribution: str = "© OpenStreetMap contributors; extract by Geofabrik"
    places: list[ParkingPlace] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_records(self):
        if len({p.id for p in self.places}) != len(self.places):
            raise ValueError("Duplicate parking identifier")
        if any(
            not (41.9 <= p.latitude <= 42.1 and 21.2 <= p.longitude <= 21.6) for p in self.places
        ):
            raise ValueError("Parking outside snapshot bounds")
        if self.records_sha256 != records_hash(self.places):
            raise ValueError("Parking records checksum mismatch")
        timestamp = datetime.fromisoformat(self.source_timestamp.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Parking timestamp must have a timezone")
        return self


def records_hash(places):
    content = json.dumps(
        [p.model_dump() if isinstance(p, ParkingPlace) else p for p in places],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class ParkingCatalog:
    def __init__(self, path: Path, clock=lambda: datetime.now(UTC)):
        self.path, self.clock = path, clock
        self._snapshot = None

    def get(self) -> ParkingSnapshot:
        try:
            if self._snapshot is None:
                if self.path.stat().st_size > 2_000_000:
                    raise ValueError("Parking snapshot too large")
                self._snapshot = ParkingSnapshot.model_validate_json(self.path.read_bytes())
            snapshot = self._snapshot
            age = self.clock() - datetime.fromisoformat(
                snapshot.source_timestamp.replace("Z", "+00:00")
            )
            if not -1 <= age.total_seconds() / 86400 <= 90:
                raise ValueError("Parking snapshot needs refresh")
            return snapshot
        except (OSError, ValueError) as error:
            raise RoutingError(
                "parking_unavailable",
                "Parking data is unavailable or needs refreshing. Try another travel option.",
                503,
            ) from error
