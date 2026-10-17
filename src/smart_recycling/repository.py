"""Read and validate collection sites at the system boundary."""

import json
from pathlib import Path

from smart_recycling.domain import Site, WasteCategory


def load_sites(path: Path) -> tuple[Site, ...]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)

    if payload.get("version") != 1 or not isinstance(payload.get("sites"), list):
        raise ValueError("site data must use schema version 1 and contain a sites list")

    seen_ids: set[str] = set()
    sites: list[Site] = []
    for raw in payload["sites"]:
        site_id = str(raw["id"]).strip()
        if not site_id or site_id in seen_ids:
            raise ValueError(f"site id must be non-empty and unique: {site_id!r}")

        latitude = float(raw["latitude"])
        longitude = float(raw["longitude"])
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError(f"invalid coordinates for site {site_id}")

        materials = frozenset(WasteCategory(value) for value in raw["materials"])
        if not materials or WasteCategory.SPECIAL_UNSUPPORTED in materials:
            raise ValueError(f"invalid materials for site {site_id}")

        sites.append(
            Site(
                site_id=site_id,
                name=str(raw["name"]).strip(),
                latitude=latitude,
                longitude=longitude,
                materials=materials,
            )
        )
        seen_ids.add(site_id)

    return tuple(sites)
