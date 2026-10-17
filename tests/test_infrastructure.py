"""Synthetic ingestion failures and real snapshot contract checks require no network."""

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_recycling import api
from smart_recycling.infrastructure import LAYERS, load_infrastructure, prepare_snapshot
from smart_recycling.infrastructure_models import SiteSnapshot

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data/policy/skopje_v1.json"


def feature(asset_id, site_id, materials, *, scope="city", vending=False, latitude=42.0):
    """Create a synthetic source row with explicit provenance fields."""
    raw = {
        "asset_id": asset_id,
        "site_id": site_id,
        "materials": materials,
        "release_scope": scope,
        "asset_type": "reverse_vending_machine" if vending else "recycling_container",
        "collection_mode": "reverse_vending" if vending else "drop_off_container",
        "source_name": "Pakomak vending-machine list" if vending else "Pakomak container map",
        "source_url": "https://example.test/source",
        "source_record_id": asset_id,
        "source_authority": "test_fixture",
        "operator": "fixture",
        "dataset_version": "test-v1",
        "as_of_date": "2026-09-19",
        "scraped_at": "2026-09-19T00:00:00Z",
        "source_updated_at": None,
        "source_address": None,
        "source_municipality": None,
        "verification_method": "test_fixture",
        "last_field_verified_at": None,
        "location_confidence": "unknown",
        "material_confidence": "unknown",
        "coordinate_method": "synthetic",
        "coordinate_accuracy_m": 10.0,
        "freshness_tier": "unknown",
        "reuse_status": "test_fixture",
        "publication_eligible": False,
        "license_evidence": None,
        "derived_municipality_code": "test",
        "derived_municipality_en": "Test area",
        "operational_status": "unknown",
        "qa_flags": "operational_status_unknown",
    }
    return {
        "type": "Feature",
        "properties": raw,
        "geometry": {"type": "Point", "coordinates": [21.4, latitude]},
    }


def write_layers(directory: Path, layers: list[list[dict]]) -> None:
    """Write matching checksums so semantic validation is tested independently."""
    summary = {"outputs": {}}
    for (filename, _, count_key), rows in zip(LAYERS, layers, strict=True):
        body = json.dumps({"type": "FeatureCollection", "features": rows}).encode()
        (directory / filename).write_bytes(body)
        summary["outputs"][filename] = hashlib.sha256(body).hexdigest()
        summary[count_key] = len(rows)
    (directory / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


@pytest.fixture
def layers():
    general = feature("general", "general-site", "mixed_municipal_waste", latitude=42.1)
    general["properties"].update(asset_type="waste_container", source_name="City of Skopje GIS")
    return [
        [
            feature("glass", "shared", "glass"),
            feature("machine", "shared", "metal_cans;plastic_bottles", vending=True),
            feature("paper", "paper-site", "paper", latitude=42.2),
        ],
        [general],
        [
            feature(
                "metro",
                "metro-site",
                "metal_cans;plastic_bottles",
                vending=True,
                scope="metro_extension",
                latitude=42.3,
            )
        ],
    ]


def test_grouping_preserves_per_asset_acceptance_and_provenance(tmp_path, layers):
    write_layers(tmp_path, layers)
    snapshots = load_infrastructure(tmp_path, POLICY)
    city = json.loads(snapshots["city"].body)
    assert (city["site_count"], city["asset_count"]) == (3, 4)
    shared = next(site for site in city["sites"] if site["id"] == "shared")
    glass, machine = shared["assets"]
    assert glass["acceptance"]["accepted_item_kinds"] == ["empty_glass_packaging"]
    assert "empty_glass_packaging" not in machine["acceptance"]["accepted_item_kinds"]
    assert machine["provenance"]["publication_eligible"] is False
    assert machine["operational_status"] == "unknown"
    assert machine["qa_flags"] == ["operational_status_unknown"]
    general = next(site for site in city["sites"] if site["id"] == "general-site")
    assert general["assets"][0]["acceptance"] is None
    metro = json.loads(snapshots["metro_extension"].body)
    assert metro["asset_count"] == 1
    assert all(asset["id"] != "metro" for site in city["sites"] for asset in site["assets"])


def test_digest_is_stable_and_covers_policy_changes(tmp_path, layers):
    write_layers(tmp_path, layers)
    original = load_infrastructure(tmp_path, POLICY)["city"]
    parsed = SiteSnapshot.model_validate_json(original.body)
    assets = tuple(asset for site in parsed.sites for asset in site.assets)
    reordered = prepare_snapshot(
        tuple(reversed(assets)),
        parsed.scope,
        parsed.policy_version,
        parsed.policy_sha256,
        parsed.evidence_sources,
        parsed.source_checksums,
    )
    assert reordered.body == original.body
    assert original.etag == f'"{hashlib.sha256(original.body).hexdigest()}"'
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["profiles"][0]["limits"] = "Changed guidance"
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    assert load_infrastructure(tmp_path, path)["city"].etag != original.etag


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("nan", "finite"),
        ("range", "less than or equal"),
        ("bool", "valid number"),
        ("duplicate", "duplicate asset"),
        ("scope", "release_scope"),
        ("material", "unknown material"),
        ("site_coordinate", "conflicting coordinates"),
        ("site_identity", "conflicting source site IDs"),
        ("id", "valid string"),
        ("mode", "collection mode"),
    ],
)
def test_invalid_source_records_fail_without_partial_publication(tmp_path, layers, mutation, match):
    row = layers[0][0]
    if mutation in {"nan", "range", "bool"}:
        row["geometry"]["coordinates"][1] = {"nan": float("nan"), "range": 91, "bool": True}[
            mutation
        ]
    elif mutation == "duplicate":
        layers[1][0]["properties"]["asset_id"] = "glass"
    elif mutation == "scope":
        row["properties"]["release_scope"] = "metro_extension"
    elif mutation == "material":
        row["properties"]["materials"] = "unknown_plastic"
    elif mutation == "site_coordinate":
        row["geometry"]["coordinates"][1] = 42.5
    elif mutation == "site_identity":
        row["properties"]["site_id"] = "different-id-same-coordinate"
    elif mutation == "id":
        row["properties"]["asset_id"] = None
    else:
        row["properties"]["collection_mode"] = "reverse_vending"
    write_layers(tmp_path, layers)
    with pytest.raises(ValueError, match=match):
        load_infrastructure(tmp_path, POLICY)


def test_corrupt_or_missing_export_fails_with_actionable_context(tmp_path, layers):
    write_layers(tmp_path, layers)
    path = tmp_path / LAYERS[0][0]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_infrastructure(tmp_path, POLICY)
    path.unlink()
    with pytest.raises(ValueError, match="SRA_INFRASTRUCTURE_PATH"):
        load_infrastructure(tmp_path, POLICY)


def test_declared_projected_crs_is_not_treated_as_latitude_longitude(tmp_path, layers):
    write_layers(tmp_path, layers)
    name = LAYERS[0][0]
    path = tmp_path / name
    data = json.loads(path.read_text(encoding="utf-8"))
    data["crs"] = {"type": "name", "properties": {"name": "EPSG:3857"}}
    body = json.dumps(data).encode()
    path.write_bytes(body)
    summary_path = tmp_path / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["outputs"][name] = hashlib.sha256(body).hexdigest()
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="WGS84"):
        load_infrastructure(tmp_path, POLICY)


def test_snapshot_http_cache_and_scope(tmp_path, layers, monkeypatch):
    write_layers(tmp_path, layers)
    monkeypatch.setattr(api, "snapshots", load_infrastructure(tmp_path, POLICY))
    client = TestClient(api.app)
    response = client.get("/api/v1/sites")
    assert response.status_code == 200
    assert response.json()["scope"] == "city"
    assert response.json()["categories_are_discovery_only"] is True
    etag = response.headers["etag"]
    for validator in [etag, f"W/{etag}", f'"old", {etag}', "*"]:
        cached = client.get("/api/v1/sites", headers={"If-None-Match": validator})
        assert cached.status_code == 304
        assert cached.content == b""
        assert cached.headers["etag"] == etag
        assert "private" in cached.headers["cache-control"]
    assert client.get("/api/v1/sites", headers={"If-None-Match": '"old"'}).status_code == 200
    metro = client.get("/api/v1/sites?scope=metro_extension", headers={"If-None-Match": etag})
    assert metro.status_code == 200
    assert metro.json()["asset_count"] == 1
    assert client.get("/api/v1/sites?scope=all").status_code == 422


def test_checked_in_snapshot_counts_and_no_specialist_facilities():
    snapshots = load_infrastructure(ROOT / "data/infrastructure/skopje-2026-09-19", POLICY)
    city = json.loads(snapshots["city"].body)
    assets = [asset for site in city["sites"] for asset in site["assets"]]
    assert (city["site_count"], city["asset_count"]) == (1583, 1596)
    assert len({asset["id"] for asset in assets}) == 1596
    assert sum(asset["asset_type"] == "reverse_vending_machine" for asset in assets) == 38
    assert sum("paper" in asset["source_materials"] for asset in assets) == 7
    assert all("special_unsupported" not in asset["categories"] for asset in assets)
    assert all(asset["operational_status"] == "unknown" for asset in assets)
