"""Validate pinned GeoJSON exports and prepare deterministic site snapshots."""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from smart_recycling.domain import WasteCategory
from smart_recycling.infrastructure_models import (
    Acceptance,
    EvidenceSource,
    InfrastructureAsset,
    InfrastructureSite,
    NonEmpty,
    Observation,
    Provenance,
    Scope,
    SiteSnapshot,
)

MATERIAL_CATEGORIES = {
    "glass": WasteCategory.GLASS,
    "plastic_bottles": WasteCategory.PLASTIC_METAL,
    "metal_cans": WasteCategory.PLASTIC_METAL,
    "paper": WasteCategory.PAPER_TETRAPAK,
    "mixed_municipal_waste": WasteCategory.GENERAL,
}
LAYERS: tuple[tuple[str, Scope, str], ...] = (
    ("pakomak_recycling.geojson", "city", "recycling_assets"),
    ("city_mixed_waste.geojson", "city", "optional_city_mixed_waste"),
    (
        "pakomak_metro_extension.geojson",
        "metro_extension",
        "metro_extension_pakomak_vending_machines",
    ),
)


class PolicyProfile(BaseModel):
    """Only explicitly matched operator/asset/material profiles confer acceptance."""

    model_config = ConfigDict(extra="forbid")
    id: NonEmpty
    source_names: list[NonEmpty]
    asset_type: Literal["recycling_container", "reverse_vending_machine"]
    required_materials: list[NonEmpty]
    accepted_item_kinds: list[NonEmpty]
    evidence_ids: list[NonEmpty]
    limits: NonEmpty


@dataclass(frozen=True)
class PreparedSnapshot:
    """Pre-serialized bytes ensure ETag and response content cannot diverge."""

    body: bytes
    etag: str
    site_count: int
    asset_count: int


def _split_codes(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a semicolon-delimited string")
    codes = value.split(";") if value else []
    if any(not code or code != code.strip() for code in codes) or len(codes) != len(set(codes)):
        raise ValueError(f"{field} contains empty, duplicate or padded codes")
    return tuple(sorted(codes))


def _parse_asset(
    feature: dict,
    scope: Scope,
    profiles: tuple[PolicyProfile, ...],
) -> InfrastructureAsset:
    if not isinstance(feature, dict):
        raise ValueError("every asset must be a GeoJSON object")
    if feature.get("type") != "Feature" or feature["geometry"]["type"] != "Point":
        raise ValueError("every asset must be a GeoJSON Point feature")
    coordinates = feature["geometry"]["coordinates"]
    if not isinstance(coordinates, list) or len(coordinates) != 2:
        raise ValueError("coordinates must be [longitude, latitude]")
    longitude, latitude = coordinates
    raw = feature["properties"]
    if raw["release_scope"] != scope:
        raise ValueError("asset release_scope disagrees with its input layer")
    materials = _split_codes(raw["materials"], "materials")
    if not materials or set(materials) - MATERIAL_CATEGORIES.keys():
        raise ValueError("asset has empty or unknown material capabilities")
    expected_mode = (
        "reverse_vending"
        if raw["asset_type"] == "reverse_vending_machine"
        else "drop_off_container"
    )
    if raw["collection_mode"] != expected_mode:
        raise ValueError("collection mode disagrees with asset type")
    matched = [
        profile
        for profile in profiles
        if raw["source_name"] in profile.source_names
        and raw["asset_type"] == profile.asset_type
        and set(profile.required_materials).issubset(materials)
    ]
    if len(matched) > 1:
        raise ValueError("asset matches multiple policy profiles; resolve the ambiguity")
    acceptance = None
    if matched:
        profile = matched[0]
        acceptance = Acceptance(
            profile_id=profile.id,
            accepted_item_kinds=tuple(sorted(profile.accepted_item_kinds)),
            evidence_ids=tuple(sorted(profile.evidence_ids)),
            limits=profile.limits,
        )
    provenance = Provenance.model_validate({name: raw[name] for name in Provenance.model_fields})
    date.fromisoformat(provenance.as_of_date)
    observed = any(raw.get(name) is not None for name in Observation.model_fields)
    return InfrastructureAsset(
        id=raw["asset_id"],
        source_site_id=raw["site_id"],
        name=raw.get("display_name") or f"{raw['derived_municipality_en']} {raw['asset_id']}",
        address=raw.get("display_address"),
        latitude=latitude,
        longitude=longitude,
        asset_type=raw["asset_type"],
        collection_mode=raw["collection_mode"],
        source_materials=materials,
        categories=tuple(sorted({MATERIAL_CATEGORIES[material] for material in materials})),
        municipality_code=raw["derived_municipality_code"],
        municipality_name=raw["derived_municipality_en"],
        operational_status=raw["operational_status"],
        qa_flags=_split_codes(raw["qa_flags"], "qa_flags"),
        provenance=provenance,
        acceptance=acceptance,
        observation=Observation.model_validate(
            {name: raw.get(name) for name in Observation.model_fields}
        )
        if observed
        else None,
    )


def prepare_snapshot(
    assets: tuple[InfrastructureAsset, ...],
    scope: Scope,
    policy_version: str,
    policy_sha256: str,
    sources: dict[str, EvidenceSource],
    checksums: dict[str, str],
) -> PreparedSnapshot:
    """Group identical source site IDs without merging distinct physical assets."""
    groups: dict[str, list[InfrastructureAsset]] = defaultdict(list)
    coordinate_sites: dict[tuple[float, float], str] = {}
    for asset in assets:
        point = (round(asset.latitude, 6), round(asset.longitude, 6))
        previous = coordinate_sites.setdefault(point, asset.source_site_id)
        if previous != asset.source_site_id:
            raise ValueError("identical coordinate groups have conflicting source site IDs")
        groups[asset.source_site_id].append(asset)
    sites = []
    for site_id, group in sorted(groups.items()):
        points = {(round(asset.latitude, 6), round(asset.longitude, 6)) for asset in group}
        if len(points) != 1:
            raise ValueError(f"source site {site_id} contains conflicting coordinates")
        latitude, longitude = next(iter(points))
        sites.append(
            InfrastructureSite(
                id=site_id,
                latitude=latitude,
                longitude=longitude,
                materials=tuple(
                    sorted({category for asset in group for category in asset.categories})
                ),
                assets=tuple(sorted(group, key=lambda asset: asset.id)),
            )
        )
    versions = {asset.provenance.dataset_version for asset in assets}
    dates = {asset.provenance.as_of_date for asset in assets}
    if len(versions) != 1 or len(dates) != 1:
        raise ValueError(f"{scope}: empty or inconsistent dataset version/as-of date")
    snapshot = SiteSnapshot(
        scope=scope,
        dataset_version=next(iter(versions)),
        as_of_date=next(iter(dates)),
        policy_version=policy_version,
        policy_sha256=policy_sha256,
        source_checksums=checksums,
        site_count=len(sites),
        asset_count=len(assets),
        evidence_sources=sources,
        sites=tuple(sites),
    )
    body = json.dumps(
        snapshot.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return PreparedSnapshot(body, f'"{hashlib.sha256(body).hexdigest()}"', len(sites), len(assets))


def load_infrastructure(directory: Path, policy_path: Path) -> dict[Scope, PreparedSnapshot]:
    """Check every source hash before parsing; fail startup rather than use partial data."""
    try:
        summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        policy_bytes = policy_path.read_bytes()
        policy = json.loads(policy_bytes)
        sources = {
            key: EvidenceSource.model_validate(value) for key, value in policy["sources"].items()
        }
        profiles = tuple(PolicyProfile.model_validate(row) for row in policy["profiles"])
        if len({profile.id for profile in profiles}) != len(profiles):
            raise ValueError("duplicate acceptance profile IDs")
        for profile in profiles:
            if (
                not profile.source_names
                or not profile.required_materials
                or not profile.accepted_item_kinds
            ):
                raise ValueError("acceptance profiles need sources, materials and item kinds")
            if set(profile.required_materials) - MATERIAL_CATEGORIES.keys():
                raise ValueError("acceptance profile requires unknown materials")
            if not profile.evidence_ids or set(profile.evidence_ids) - sources.keys():
                raise ValueError("acceptance profile has missing or unknown evidence")
        by_scope: dict[Scope, list[InfrastructureAsset]] = {"city": [], "metro_extension": []}
        checksums: dict[str, str] = {}
        seen: set[str] = set()
        site_scopes: dict[str, Scope] = {}
        for filename, scope, count_key in LAYERS:
            raw_bytes = (directory / filename).read_bytes()
            digest = hashlib.sha256(raw_bytes).hexdigest()
            if digest != summary["outputs"][filename]:
                raise ValueError(f"checksum mismatch in {filename}; restore the pinned export")
            checksums[filename] = digest
            payload = json.loads(raw_bytes)
            if "crs" in payload:
                declared_crs = payload["crs"]
                if (
                    not isinstance(declared_crs, dict)
                    or declared_crs.get("type") != "name"
                    or not isinstance(declared_crs.get("properties"), dict)
                    or declared_crs["properties"].get("name")
                    not in {"urn:ogc:def:crs:OGC:1.3:CRS84", "urn:ogc:def:crs:EPSG::4326"}
                ):
                    raise ValueError(f"{filename}: expected WGS84 longitude/latitude coordinates")
            if payload["type"] != "FeatureCollection" or not isinstance(payload["features"], list):
                raise ValueError(f"{filename}: expected FeatureCollection")
            if (
                type(summary[count_key]) is not int
                or len(payload["features"]) != summary[count_key]
            ):
                raise ValueError(f"{filename}: count differs from source summary")
            for index, feature in enumerate(payload["features"]):
                try:
                    asset = _parse_asset(feature, scope, profiles)
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError(f"{filename} feature {index}: {error}") from error
                if asset.id in seen:
                    raise ValueError(f"duplicate asset ID across layers: {asset.id}")
                if site_scopes.setdefault(asset.source_site_id, scope) != scope:
                    raise ValueError(
                        f"source site appears in multiple scopes: {asset.source_site_id}"
                    )
                seen.add(asset.id)
                by_scope[scope].append(asset)
        return {
            scope: prepare_snapshot(
                tuple(assets),
                scope,
                policy["version"],
                hashlib.sha256(policy_bytes).hexdigest(),
                sources,
                checksums,
            )
            for scope, assets in by_scope.items()
        }
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Cannot load infrastructure from {directory} with policy {policy_path}: {error}. "
            "Restore the versioned inputs or correct SRA_INFRASTRUCTURE_PATH/SRA_POLICY_PATH."
        ) from error
