"""Reviewed clothing-donation venues, isolated from the frozen City analysis."""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from smart_recycling.domain import WasteCategory
from smart_recycling.electronics import prepare_citizen_snapshot
from smart_recycling.infrastructure import PreparedSnapshot
from smart_recycling.infrastructure_models import (
    Acceptance,
    FrozenModel,
    InfrastructureAsset,
    InfrastructureSite,
    NonEmpty,
    Provenance,
    SiteSnapshot,
)


class ClothingSite(FrozenModel):
    id: NonEmpty
    name: NonEmpty
    address: NonEmpty
    latitude: Annotated[float, Field(ge=41.85, le=42.15, allow_inf_nan=False)]
    longitude: Annotated[float, Field(ge=21.2, le=21.65, allow_inf_nan=False)]
    municipality_code: NonEmpty
    municipality_name: NonEmpty
    collection_mode: Literal["drop_off_container", "staffed_drop_off"]
    reported_containers: Annotated[int, Field(ge=1, le=20)] | None
    coordinate_source: Annotated[
        str, Field(pattern=r"^https://www\.openstreetmap\.org/(node|way)/[0-9]+$")
    ]
    coordinate_method: NonEmpty
    coordinate_updated_at: NonEmpty
    arrival_note: NonEmpty


class ClothingCatalog(FrozenModel):
    version: Literal["skopje-clothes-v1"]
    reviewed_on: Literal["2026-09-22"]
    sites: tuple[ClothingSite, ...]


def add_clothing_sites(base: SiteSnapshot, directory: Path, policy_path: Path) -> PreparedSnapshot:
    raw = (directory / "sites.json").read_text(encoding="utf-8")
    digest = hashlib.sha256(raw.encode()).hexdigest()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if digest != manifest["sites_sha256"]:
        raise ValueError("Clothing catalog checksum mismatch")
    catalog = ClothingCatalog.model_validate_json(raw)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    profile = next(row for row in policy["profiles"] if row["id"] == "red_cross_clothes")
    guidance = policy["specialist_guidance"]["wearable_clothes"]
    if (
        base.scope != "citizen"
        or set(profile["accepted_item_kinds"]) != {"wearable_clothes"}
        or profile["asset_type"] != "collection_centre"
        or profile["required_materials"] != ["wearable_clothes"]
        or profile["source_names"] != ["Red Cross of the City of Skopje"]
        or set(guidance["facility_ids"]) != {row.id for row in catalog.sites}
        or len(catalog.sites) != manifest["mapped_venues"]
        or "red_cross_clothes_2026" not in profile["evidence_ids"]
        or any(key not in base.evidence_sources for key in profile["evidence_ids"])
    ):
        raise ValueError("Clothing catalog and acceptance evidence disagree")
    source = base.evidence_sources["red_cross_clothes_2026"]
    if source.url != manifest["source"]:
        raise ValueError("Clothing source mismatch")
    sites = list(base.sites)
    seen = {site.id for site in sites}
    for row in catalog.sites:
        if row.id in seen:
            raise ValueError("Duplicate clothing site ID")
        seen.add(row.id)
        if policy["arrival_notes"].get(row.id) != [row.arrival_note]:
            raise ValueError("Clothing arrival note missing or stale")
        asset = InfrastructureAsset(
            id=f"{row.id}-collection",
            source_site_id=row.id,
            name=row.name,
            address=row.address,
            latitude=row.latitude,
            longitude=row.longitude,
            asset_type="collection_centre",
            collection_mode=row.collection_mode,
            source_materials=("wearable_clothes",),
            categories=(WasteCategory.SPECIAL_UNSUPPORTED,),
            municipality_code=row.municipality_code,
            municipality_name=row.municipality_name,
            operational_status="unknown",
            qa_flags=("venue_pin_not_container", "not_field_verified"),
            provenance=Provenance(
                source_name=source.publisher,
                source_url=source.url,
                source_record_id=row.id,
                source_authority="collection_operator",
                operator=source.publisher,
                dataset_version=catalog.version,
                as_of_date=catalog.reviewed_on,
                scraped_at=catalog.reviewed_on,
                source_updated_at="2026-04-20",
                source_address=row.address,
                source_municipality=row.municipality_name,
                verification_method="Published donation venue matched to OSM; agent review",
                last_field_verified_at=None,
                location_confidence="mapped_venue_not_field_verified",
                material_confidence="operator_published",
                coordinate_method=row.coordinate_method,
                coordinate_accuracy_m=None,
                freshness_tier="published_not_live",
                reuse_status="curated_facts_and_ODbL_coordinates",
                publication_eligible=True,
                license_evidence="https://www.openstreetmap.org/copyright",
            ),
            acceptance=Acceptance(
                profile_id=profile["id"],
                accepted_item_kinds=tuple(profile["accepted_item_kinds"]),
                evidence_ids=tuple(profile["evidence_ids"]),
                limits=profile["limits"],
            ),
            observation=None,
        )
        sites.append(
            InfrastructureSite(
                id=row.id,
                latitude=row.latitude,
                longitude=row.longitude,
                materials=("clothes",),
                assets=(asset,),
            )
        )
    return prepare_citizen_snapshot(
        base.model_copy(
            update={
                "dataset_version": f"{base.dataset_version}+{catalog.version}",
                "sites": tuple(sites),
                "site_count": len(sites),
                "asset_count": base.asset_count + len(catalog.sites),
                "source_checksums": {**base.source_checksums, "clothes/sites.json": digest},
            }
        )
    )
