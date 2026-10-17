"""Immutable contracts for infrastructure ingestion and cacheable map snapshots."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from smart_recycling.domain import WasteCategory

Scope = Literal["city", "metro_extension", "citizen"]
Material = Literal[
    "glass",
    "plastic_bottles",
    "metal_cans",
    "paper",
    "mixed_municipal_waste",
    "electrical_electronic_equipment",
    "wearable_clothes",
]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


class FrozenModel(BaseModel):
    """Reject coercion of malformed inputs and mutation of loaded records."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")


class Provenance(FrozenModel):
    """Source identity and uncertainty retained on every physical asset record."""

    source_name: NonEmpty
    source_url: NonEmpty
    source_record_id: NonEmpty
    source_authority: NonEmpty
    operator: str | None
    dataset_version: NonEmpty
    as_of_date: NonEmpty
    scraped_at: NonEmpty
    source_updated_at: str | None
    source_address: str | None
    source_municipality: str | None
    verification_method: NonEmpty
    last_field_verified_at: str | None
    location_confidence: NonEmpty
    material_confidence: NonEmpty
    coordinate_method: NonEmpty
    coordinate_accuracy_m: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    freshness_tier: NonEmpty
    reuse_status: NonEmpty
    publication_eligible: bool
    license_evidence: str | None


class Acceptance(FrozenModel):
    """An asset-scoped policy match, not a guarantee of live availability."""

    profile_id: NonEmpty
    accepted_item_kinds: tuple[NonEmpty, ...]
    evidence_ids: tuple[NonEmpty, ...]
    limits: NonEmpty


class Observation(FrozenModel):
    """Dated telemetry, never interpreted as current operating status."""

    observed_at: str | None
    fullness_kg: Annotated[float, Field(allow_inf_nan=False)] | None
    volume_fullness_percent: Annotated[float, Field(allow_inf_nan=False)] | None


class InfrastructureAsset(FrozenModel):
    """A source asset with its own capabilities even when co-located."""

    id: NonEmpty
    source_site_id: NonEmpty
    name: NonEmpty
    address: str | None
    latitude: Latitude
    longitude: Longitude
    asset_type: Literal[
        "recycling_container", "waste_container", "reverse_vending_machine", "collection_centre"
    ]
    collection_mode: Literal["drop_off_container", "reverse_vending", "staffed_drop_off"]
    source_materials: tuple[Material, ...]
    categories: tuple[WasteCategory, ...]
    municipality_code: NonEmpty
    municipality_name: NonEmpty
    operational_status: NonEmpty
    qa_flags: tuple[NonEmpty, ...]
    provenance: Provenance
    acceptance: Acceptance | None
    observation: Observation | None


class InfrastructureSite(FrozenModel):
    """Coordinate-defined grouping; assets are retained separately."""

    id: NonEmpty
    latitude: Latitude
    longitude: Longitude
    # Discovery can distinguish specialist destinations without inventing a trained class.
    materials: tuple[WasteCategory | Literal["clothes"], ...]
    assets: tuple[InfrastructureAsset, ...]


class EvidenceSource(FrozenModel):
    """Published evidence behind a profile, including review limitations."""

    url: NonEmpty
    publisher: NonEmpty
    scope: NonEmpty
    retrieved_on: NonEmpty
    reviewer: NonEmpty
    review_method: NonEmpty
    human_signoff: bool


class SiteSnapshot(FrozenModel):
    """Complete map download with input hashes and an explicit geographic scope."""

    schema_version: Literal[1] = 1
    scope: Scope
    synthetic: Literal[False] = False
    dataset_version: NonEmpty
    as_of_date: NonEmpty
    policy_version: NonEmpty
    source_checksums: dict[str, str]
    policy_sha256: NonEmpty
    site_count: int
    asset_count: int
    categories_are_discovery_only: Literal[True] = True
    evidence_sources: dict[str, EvidenceSource]
    sites: tuple[InfrastructureSite, ...]
