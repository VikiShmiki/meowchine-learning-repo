"""Versioned specialist destinations, separate from the frozen City coverage inputs."""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from smart_recycling.domain import WasteCategory
from smart_recycling.infrastructure import PreparedSnapshot
from smart_recycling.infrastructure_models import (
    Acceptance,
    EvidenceSource,
    FrozenModel,
    InfrastructureAsset,
    InfrastructureSite,
    NonEmpty,
    Provenance,
    SiteSnapshot,
)


class CollectionSite(FrozenModel):
    """Curated factual records; no geocoding or availability inference at runtime."""

    id: NonEmpty
    name: NonEmpty
    address: NonEmpty
    latitude: Annotated[float, Field(ge=41.85, le=42.15, allow_inf_nan=False)]
    longitude: Annotated[float, Field(ge=21.2, le=21.65, allow_inf_nan=False)]
    municipality_code: NonEmpty
    municipality_name: NonEmpty
    operator: Literal["JP Komunalna Higiena Skopje", "Elkolekt / Elektro Eko Grizha"]
    profile_id: Literal["karpos_electronics", "east_gate_small_electronics"]
    acceptance_source: NonEmpty
    coordinate_source: NonEmpty
    coordinate_parent: NonEmpty
    coordinate_method: NonEmpty
    coordinate_updated_at: NonEmpty
    license: Literal["https://www.openstreetmap.org/copyright"]


class CollectionCatalog(FrozenModel):
    version: Literal["skopje-electronics-v2"]
    reviewed_on: Literal["2026-09-22"]
    sites: tuple[CollectionSite, ...]


def citizen_snapshot(base: SiteSnapshot, directory: Path, policy_path: Path) -> PreparedSnapshot:
    """Add validated e-waste sites for discovery/routes, never for coverage/upgrades."""
    raw = (directory / "sites.json").read_text(encoding="utf-8")
    digest = hashlib.sha256(raw.encode()).hexdigest()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if digest != manifest["sites_sha256"]:
        raise ValueError("Electronics catalog checksum mismatch")
    catalog = CollectionCatalog.model_validate_json(raw)
    policy_text = policy_path.read_text(encoding="utf-8")
    policy = json.loads(policy_text)
    profiles = {row["id"]: row for row in policy["profiles"]}
    sources = {key: EvidenceSource(**value) for key, value in policy["sources"].items()}
    sites = list(base.sites)
    seen = {site.id for site in sites}
    for row in catalog.sites:
        if row.id in seen:
            raise ValueError("Duplicate electronics site ID")
        seen.add(row.id)
        profile = profiles[row.profile_id]
        if (
            set(profile["accepted_item_kinds"])
            != (
                {"small_electronics"}
                if row.profile_id == "east_gate_small_electronics"
                else {"electronics", "small_electronics"}
            )
            or profile["asset_type"] != "collection_centre"
            or row.operator not in profile["source_names"]
            or row.acceptance_source not in {sources[e].url for e in profile["evidence_ids"]}
            or not row.coordinate_source.startswith("https://www.openstreetmap.org/node/")
            or not row.coordinate_parent.startswith("https://www.openstreetmap.org/way/")
        ):
            raise ValueError(
                "Electronics destination lacks matching acceptance/coordinate evidence"
            )
        asset = InfrastructureAsset(
            id=f"{row.id}-electronics",
            source_site_id=row.id,
            name=row.name,
            address=row.address,
            latitude=row.latitude,
            longitude=row.longitude,
            asset_type="collection_centre",
            collection_mode="drop_off_container"
            if row.profile_id == "east_gate_small_electronics"
            else "staffed_drop_off",
            source_materials=("electrical_electronic_equipment",),
            categories=(WasteCategory.SPECIAL_UNSUPPORTED,),
            municipality_code=row.municipality_code,
            municipality_name=row.municipality_name,
            operational_status="unknown",
            qa_flags=("not_field_verified", "check_opening_hours"),
            provenance=Provenance(
                source_name=row.operator,
                source_url=row.acceptance_source,
                source_record_id=row.id,
                source_authority="collection_operator"
                if row.profile_id == "east_gate_small_electronics"
                else "municipal_operator",
                operator=row.operator,
                dataset_version=catalog.version,
                as_of_date=catalog.reviewed_on,
                scraped_at=catalog.reviewed_on,
                source_updated_at=None,
                source_address=row.address,
                source_municipality=row.municipality_name,
                verification_method="operator acceptance matched to OSM entrance; agent review",
                last_field_verified_at=None,
                location_confidence="mapped_entrance_not_field_verified",
                material_confidence="operator_published",
                coordinate_method=row.coordinate_method,
                coordinate_accuracy_m=None,
                freshness_tier="published_not_live",
                reuse_status="curated_facts_and_ODbL_coordinates",
                publication_eligible=True,
                license_evidence=row.license,
            ),
            acceptance=Acceptance(
                profile_id=row.profile_id,
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
                materials=(WasteCategory.SPECIAL_UNSUPPORTED,),
                assets=(asset,),
            )
        )
    snapshot = base.model_copy(
        update={
            "scope": "citizen",
            "dataset_version": f"{base.dataset_version}+{catalog.version}",
            "policy_version": policy["version"],
            "policy_sha256": hashlib.sha256(policy_text.encode()).hexdigest(),
            "sites": tuple(sites),
            "site_count": len(sites),
            "asset_count": base.asset_count + len(catalog.sites),
            "evidence_sources": sources,
            "source_checksums": {**base.source_checksums, "electronics/sites.json": digest},
        }
    )
    return prepare_citizen_snapshot(snapshot)


def prepare_citizen_snapshot(snapshot: SiteSnapshot) -> PreparedSnapshot:
    """Serialize an immutable citizen snapshot with a content-derived cache key."""
    body = json.dumps(
        snapshot.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return PreparedSnapshot(
        body, f'"{hashlib.sha256(body).hexdigest()}"', snapshot.site_count, snapshot.asset_count
    )
