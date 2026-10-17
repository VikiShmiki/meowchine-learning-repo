"""Typed trip contracts; descriptions are validated but never sent to the routing provider."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, model_validator

from smart_recycling.guidance import ItemKind

Mode = Literal["walking", "driving", "transit"]
Finite = Annotated[float, Field(ge=0, allow_inf_nan=False)]

# A quick-pick stream requires every listed capability, not a guessed item subtype.
STREAM_KINDS = {
    "glass": frozenset({"empty_glass_packaging"}),
    "plastic_metal": frozenset({"empty_plastic_bottle", "empty_metal_can"}),
    "paper_tetrapak": frozenset({"clean_paper", "clean_cardboard", "empty_tetrapak"}),
}


class Coordinates(BaseModel):
    """WGS84 origin or source site location."""

    model_config = ConfigDict(extra="forbid")
    latitude: Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
    longitude: Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]

    def lonlat(self) -> list[float]:
        """Convert explicitly to the provider's longitude-first order."""
        return [self.longitude, self.latitude]


class TripItem(BaseModel):
    """A specific item and condition supplied for server-side revalidation."""

    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, Field(min_length=1, max_length=200)]
    manual_kind: ItemKind
    condition_confirmed: StrictBool


class TripStream(BaseModel):
    """Known waste: documented recycling acceptance or acknowledged general-bin navigation."""

    model_config = ConfigDict(extra="forbid")
    material: Literal[
        "glass", "plastic_metal", "paper_tetrapak", "general", "electronics", "clothes"
    ]
    condition_confirmed: StrictBool
    accept_unverified: StrictBool = False
    small_only: StrictBool = False

    @model_validator(mode="after")
    def validate_size(self):
        if self.small_only and self.material != "electronics":
            raise ValueError("small_only applies only to electronics")
        return self

    @property
    def routing_kind(self) -> str:
        if self.material == "clothes":
            return "wearable_clothes"
        return "small_electronics" if self.small_only else self.material


class TripRequest(BaseModel):
    """A bounded basket and explicit permission to send coordinates for routing."""

    model_config = ConfigDict(extra="forbid")
    origin: Coordinates
    mode: Mode
    items: Annotated[list[TripItem | TripStream], Field(min_length=1, max_length=6)]
    share_coordinates: StrictBool
    departure_at: AwareDatetime | None = None
    include_parking: StrictBool = False

    @model_validator(mode="after")
    def parking_mode(self):
        if self.include_parking and self.mode != "driving":
            raise ValueError("Parking applies only to driving trips")
        return self


class Stop(Coordinates):
    """Matched assets for each item at one deduplicated source site."""

    site_id: str
    completion_ticket: str | None = None
    name: str
    item_kinds: list[str]
    asset_ids: list[str]
    acceptance_limits: list[str]
    arrival_notes: list[str] = Field(default_factory=list)
    unverified_materials: list[str] = Field(default_factory=list)
    network_access_gap_m: Finite


class LineString(BaseModel):
    """Network geometry, never a line joining collection points."""

    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]]


class TripResponse(BaseModel):
    """Provider-backed itinerary with explicit approximation and source metadata."""

    mode: Mode
    status_version: str = ""
    provider: Literal["openrouteservice", "jsp_gtfs_openrouteservice"] = "openrouteservice"
    profile: str
    distance_m: Finite
    duration_s: Finite
    geometry: LineString | None
    stops: list[Stop]
    dataset_version: str
    policy_version: str
    source_as_of: str
    candidate_count: int
    optimizer: str = "Minimum matrix travel time within a nearby candidate shortlist"
    ends_at_last_stop: Literal[True] = True
    warnings: list[str]
    attribution: str = "© openrouteservice by HeiGIT | © OpenStreetMap contributors"
    legs: list["TransitLeg"] = Field(default_factory=list)
    departure_at: AwareDatetime | None = None
    arrival_at: AwareDatetime | None = None
    transit_feed_version: str | None = None
    transit_fetched_at: AwareDatetime | None = None
    transit_service_end: str | None = None
    transit_source: str | None = None
    parking: list["ParkingVisit"] = Field(default_factory=list)
    parking_dataset_version: str | None = None
    parking_source_as_of: str | None = None
    driving_duration_s: Finite | None = None
    walking_duration_s: Finite | None = None


class ParkingWalk(BaseModel):
    distance_m: Finite
    duration_s: Finite
    geometry: LineString | None
    start_gap_m: Finite
    end_gap_m: Finite


class ParkingVisit(Coordinates):
    site_id: str
    parking_id: str
    name: str
    access: Literal["yes", "permissive"]
    fee: str
    opening_hours: str
    point_kind: Literal["mapped_point", "driveway_crossing"]
    source_url: str
    availability: Literal["unknown"] = "unknown"
    drive_access_gap_m: Finite
    walk_to: ParkingWalk
    walk_back: ParkingWalk | None


class TransitLeg(BaseModel):
    """Separate walk/bus geometry: never join gaps with invented paths."""

    mode: Literal["walking", "bus"]
    from_name: str
    to_name: str
    from_point: list[float]
    to_point: list[float]
    departure_at: AwareDatetime
    arrival_at: AwareDatetime
    duration_s: Finite
    distance_m: Finite
    geometry: LineString | None
    site_id: str
    line: str = ""
    headsign: str = ""
    stop_count: int = 0


class RoutingError(Exception):
    """Safe public failure; no provider response body, credential or coordinates."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
