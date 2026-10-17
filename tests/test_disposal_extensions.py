"""Real policy/data integration with simulated providers; no paid or live API calls."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from test_routing import provider

from smart_recycling import api
from smart_recycling.electronics import citizen_snapshot
from smart_recycling.infrastructure_models import SiteSnapshot
from smart_recycling.route_planner import accepts
from smart_recycling.routing import RoutingService
from smart_recycling.routing_models import RoutingError, TripRequest
from smart_recycling.vision import ModelPhotoItem, VisionService, _output_schema

client = TestClient(api.app)


@pytest.mark.parametrize(
    "text",
    [
        "used tissue",
        "a used diaper",
        "soiled nappies",
        "dirty tissue",
        "I have a used tissue",
        "where should I throw away a used nappy?",
    ],
)
def test_residual_guidance_needs_explicit_confirmation(text):
    result = client.post("/api/v1/classify", json={"text": text}).json()
    assert result["category"] == "general"
    assert result["message"] == "This item is not recyclable. Use general waste."
    assert result["status"] == "confirm_condition"
    confirmed = client.post(
        "/api/v1/classify",
        json={
            "text": text,
            "manual_kind": result["item_kind"],
            "condition_confirmed": True,
        },
    ).json()
    assert confirmed["status"] == "ready_for_site_matching"
    assert confirmed["evidence_ids"] == ["karpos_household"]


@pytest.mark.parametrize(
    "text",
    [
        "unknown material",
        "not recyclable",
        "used wet wipes",
        "dirty paper",
        "used tissue box",
        "used tissue and glass bottle",
        "food waste",
        "ceramic mug",
        "plastic tray",
    ],
)
def test_unknowns_and_mixed_items_do_not_default_to_general(text):
    answer = api.classifier.decide(text)
    assert answer.category is None
    override = api.classifier.decide(text, "ordinary_residual", True)
    assert override.status != "ready_for_site_matching"


@pytest.mark.parametrize(
    "text",
    [
        "medical tissue",
        "used tissue soaked in solvent",
        "swollen phone",
        "leaking laptop",
        "old battery",
        "paint",
        "clinical nappy",
        "phone and a glass bottle",
    ],
)
@pytest.mark.parametrize("kind", ["ordinary_residual", "electronics"])
def test_unsafe_or_mixed_description_never_becomes_a_confirmed_trip_item(text, kind):
    assert api.classifier.decide(text, kind, True).status != "ready_for_site_matching"


def test_electronics_catalog_preserves_base_coverage_and_accepts_only_devices():
    city = SiteSnapshot.model_validate_json(api.snapshots["city"].body)
    citizen = SiteSnapshot.model_validate_json(api.snapshots["citizen"].body)
    assert city.site_count == 1583
    assert citizen.site_count == city.site_count + 7
    assert citizen.sites[: city.site_count] == city.sites
    site = next(site for site in citizen.sites if site.id == "ewaste-karpos-yard")
    assert site.id == "ewaste-karpos-yard"
    assert site.latitude == 42.0085277 and site.longitude == 21.4002845
    assert accepts(site.assets[0], "electronics")
    assert accepts(site.assets[0], "small_electronics")
    mall = next(site for site in citizen.sites if site.id == "ewaste-east-gate-mall")
    assert mall.id == "ewaste-east-gate-mall"
    assert mall.latitude == 41.9977993 and mall.longitude == 21.4509501
    assert accepts(mall.assets[0], "small_electronics")
    assert not accepts(mall.assets[0], "electronics")
    assert mall.assets[0].provenance.source_authority == "collection_operator"
    for kind in ("batteries", "general", "ordinary_residual", "empty_metal_can", "other"):
        assert not accepts(site.assets[0], kind)
    assert client.get("/api/v1/coverage").status_code == 200
    assert client.get("/api/v1/upgrades?material=glass&n=5").status_code == 200
    response = client.get("/api/v1/sites?scope=citizen")
    assert response.status_code == 200
    assert (
        client.get(
            "/api/v1/sites?scope=citizen", headers={"If-None-Match": response.headers["etag"]}
        ).status_code
        == 304
    )


@pytest.mark.parametrize("mode", ["walking", "driving"])
@pytest.mark.parametrize("entry", ["items", "streams"])
def test_general_electronics_and_glass_all_reach_compatible_stops(mode, entry):
    adapter, calls = provider()
    planner = RoutingService(api.route_service.snapshot, api.classifier, adapter)
    items = (
        [
            {
                "text": "used tissue",
                "manual_kind": "ordinary_residual",
                "condition_confirmed": True,
            },
            {"text": "old charger", "manual_kind": "electronics", "condition_confirmed": True},
            {
                "text": "glass bottle",
                "manual_kind": "empty_glass_packaging",
                "condition_confirmed": True,
            },
        ]
        if entry == "items"
        else [
            {"material": kind, "condition_confirmed": True, "accept_unverified": kind == "general"}
            for kind in ("glass", "general", "electronics")
        ]
    )
    result = planner.plan(
        TripRequest(
            origin={"latitude": 41.9965, "longitude": 21.4314},
            mode=mode,
            items=items,
            share_coordinates=True,
        )
    )
    assert len(calls) == 2
    required = {item.get("manual_kind", item.get("material")) for item in items}
    assert set().union(*(set(stop.item_kinds) for stop in result.stops)) == required
    site_index = {site.id: site for site in planner.snapshot.sites}
    for stop in result.stops:
        for kind in stop.item_kinds:
            assert any(accepts(asset, kind) for asset in site_index[stop.site_id].assets)
        if "electronics" in stop.item_kinds:
            assert stop.site_id == "ewaste-karpos-yard"
            assert any("07:00" in note for note in stop.acceptance_limits)
    assert result.policy_version == "skopje-policy-v2"


def test_missing_electronics_destination_cannot_fall_back_to_a_general_bin():
    adapter, calls = provider()
    base = SiteSnapshot.model_validate_json(api.snapshots["city"].body)
    planner = RoutingService(base, api.classifier, adapter)
    with pytest.raises(RoutingError, match="No explicitly accepting"):
        planner.plan(
            TripRequest(
                origin={"latitude": 42, "longitude": 21.4},
                mode="walking",
                items=[{"material": "electronics", "condition_confirmed": True}],
                share_coordinates=True,
            )
        )
    assert calls == []


@pytest.mark.parametrize("change", ["checksum", "duplicates", "coordinates", "acceptance"])
def test_catalog_corruption_fails_closed(tmp_path, change):
    source = api.PROJECT_ROOT / "data/infrastructure/electronics-2026-09-22"
    data = json.loads((source / "sites.json").read_text(encoding="utf-8"))
    if change == "duplicates":
        data["sites"].append(data["sites"][0])
    if change == "coordinates":
        data["sites"][0]["latitude"] = 0
    if change == "acceptance":
        data["sites"][0]["acceptance_source"] = "https://example.org/unverified"
    raw = json.dumps(data)
    (tmp_path / "sites.json").write_text(raw, encoding="utf-8")
    checksum = hashlib.sha256(raw.encode()).hexdigest() if change != "checksum" else "invalid"
    (tmp_path / "manifest.json").write_text(
        json.dumps({"sites_sha256": checksum}), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        citizen_snapshot(
            SiteSnapshot.model_validate_json(api.snapshots["city"].body),
            tmp_path,
            api.settings.guidance_policy_path,
        )


@pytest.mark.parametrize(
    "kind,description,condition,expected",
    [
        ("ordinary_residual", "used tissue", "not_empty_or_contaminated", "candidate"),
        ("ordinary_residual", "unknown plastic", "appears_empty_clean", "needs_review"),
        ("ordinary_residual", "old charger", "appears_empty_clean", "needs_review"),
        ("electronics", "old laptop", "uncertain", "candidate"),
        ("small_electronics", "old charger", "uncertain", "candidate"),
        ("small_electronics", "old fridge", "uncertain", "needs_review"),
        ("small_electronics", "swollen phone", "uncertain", "specialist"),
        ("electronics", "swollen phone", "appears_empty_clean", "specialist"),
        ("ordinary_residual", "used tissue soaked in chemicals", "uncertain", "specialist"),
    ],
)
def test_photo_candidates_use_the_same_item_and_hazard_boundaries(
    kind, description, condition, expected
):
    suggestion = VisionService._suggestion(
        ModelPhotoItem(
            description=description,
            item_kind=kind,
            visible_condition=condition,
            reason="Visible household item.",
        )
    )
    assert suggestion.status == expected
    if expected == "candidate":
        answer = api.classifier.decide(suggestion.description, suggestion.item_kind)
        assert answer.status == "confirm_condition"
    else:
        answer = api.classifier.decide(suggestion.description, suggestion.item_kind, True)
        assert answer.status != "ready_for_site_matching"


def test_photo_hazard_mentioned_only_in_reason_survives_review():
    suggestion = VisionService._suggestion(
        ModelPhotoItem(
            description="used tissue",
            item_kind="ordinary_residual",
            visible_condition="appears_empty_clean",
            reason="May contain chemical residue.",
        )
    )
    assert suggestion.item_kind == "other"
    assert (
        api.classifier.decide(suggestion.description, suggestion.item_kind, True).status == "held"
    )
    kinds = _output_schema()["properties"]["items"]["items"]["properties"]["item_kind"]["enum"]
    assert {"ordinary_residual", "electronics", "batteries", "other"} <= set(kinds)


@pytest.mark.parametrize("mode", ["walking", "driving"])
@pytest.mark.parametrize("entry", ["items", "streams"])
def test_east_gate_routes_small_devices_but_not_large_appliances(mode, entry):
    adapter, calls = provider()
    snapshot = api.route_service.snapshot
    mall = next(s for s in snapshot.sites if s.id == "ewaste-east-gate-mall")
    # Isolate this destination to prove its acceptance contract, not fake nearest ranking.
    planner = RoutingService(
        snapshot.model_copy(update={"sites": (mall,)}), api.classifier, adapter
    )
    small = {"text": "old phone", "manual_kind": "small_electronics", "condition_confirmed": True}
    stream = {"material": "electronics", "small_only": True, "condition_confirmed": True}
    payload = dict(
        origin={"latitude": 41.998, "longitude": 21.451},
        mode=mode,
        items=[small if entry == "items" else stream],
        share_coordinates=True,
    )
    trip = planner.plan(TripRequest(**payload))
    assert trip.stops[0].site_id == mall.id
    assert trip.stops[0].item_kinds == ["small_electronics"]
    assert "information desk" in trip.stops[0].arrival_notes[0]
    assert len(calls) == 2
    payload["items"] = [{"material": "electronics", "condition_confirmed": True}]
    with pytest.raises(RoutingError, match="No explicitly accepting"):
        planner.plan(TripRequest(**payload))
    assert len(calls) == 2


@pytest.mark.parametrize(
    "text", ["old fridge", "phone and refrigerator", "washing machine", "unknown device"]
)
def test_small_device_override_cannot_expand_mall_acceptance(text):
    assert (
        api.classifier.decide(text, "small_electronics", True).status != "ready_for_site_matching"
    )


def test_phone_automatically_suggests_small_device_destinations():
    answer = api.classifier.decide("old phone")
    assert answer.item_kind == "small_electronics"
    assert answer.status == "confirm_condition"
    assert set(answer.facility_ids) == {"ewaste-karpos-yard", "ewaste-east-gate-mall"}
    assert api.classifier.decide("old fridge").facility_ids == ["ewaste-karpos-yard"]


def test_size_option_is_typed_and_scoped():
    from pydantic import ValidationError

    from smart_recycling.routing_models import TripStream

    with pytest.raises(ValidationError):
        TripStream(material="glass", condition_confirmed=True, small_only=True)
    with pytest.raises(ValidationError):
        TripStream(material="electronics", condition_confirmed=True, small_only="true")
