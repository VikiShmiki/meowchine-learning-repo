"""Clothing source, acceptance and full routing boundaries; all providers stay offline."""

import hashlib
import importlib.util
import json

import pytest
from test_routing import provider

from smart_recycling import api
from smart_recycling.clothes import add_clothing_sites
from smart_recycling.infrastructure_models import SiteSnapshot
from smart_recycling.route_planner import accepts
from smart_recycling.routing import RoutingService
from smart_recycling.routing_models import RoutingError, TripRequest
from smart_recycling.vision import ModelPhotoItem, VisionService, _output_schema

ROOT = api.PROJECT_ROOT
DIRECTORY = ROOT / "data/infrastructure/clothes-2026-09-22"


@pytest.mark.parametrize("text", ["old shirt", "clean clothes", "washed jeans", "a winter jacket"])
def test_clothing_requires_its_own_confirmation(text):
    initial = api.classifier.decide(text)
    assert initial.item_kind == "wearable_clothes"
    assert initial.category.value == "special_unsupported"
    assert initial.status == "confirm_condition"
    assert "reuse" in initial.message
    assert api.classifier.decide(text, "wearable_clothes", False).status == "confirm_condition"
    ready = api.classifier.decide(text, "wearable_clothes", True)
    assert ready.status == "ready_for_site_matching"
    assert len(ready.facility_ids) == 5
    assert api.classifier.decide(text, "ordinary_residual", True).status != ready.status


@pytest.mark.parametrize(
    "text",
    [
        "torn shirt",
        "wet clothes",
        "stained jeans",
        "mouldy jacket",
        "unwashed clothes",
        "clothes not wearable",
        "shirt and a glass bottle",
        "old phone and clothes",
        "shirt with battery",
        "shirt and used tissues",
        "clothes soaked in solvent",
        "rags",
        "unknown material",
    ],
)
def test_damaged_hazardous_unknown_or_mixed_items_do_not_reach_donation(text):
    answer = api.classifier.decide(text, "wearable_clothes", True)
    assert answer.status != "ready_for_site_matching"


def test_catalog_counts_and_stream_separation():
    city = SiteSnapshot.model_validate_json(api.snapshots["city"].body)
    snapshot = api.route_service.snapshot
    clothes = [site for site in snapshot.sites if "clothes" in site.materials]
    assert len(clothes) == 5
    assert snapshot.site_count == 1590 and snapshot.asset_count == 1603
    assert snapshot.sites[: len(city.sites)] == city.sites
    assert not any("clothes" in site.materials for site in city.sites)
    for site in snapshot.sites:
        for asset in site.assets:
            assert accepts(asset, "wearable_clothes") == (site in clothes)
            if site in clothes:
                assert not any(
                    accepts(asset, kind)
                    for kind in (
                        "general",
                        "ordinary_residual",
                        "electronics",
                        "small_electronics",
                        "batteries",
                    )
                )
                assert asset.provenance.last_field_verified_at is None
    research = json.loads((DIRECTORY / "research.json").read_text(encoding="utf-8"))
    assert research["documented_venues"] == 8
    assert research["reported_containers"] == 8
    held = {row["id"] for row in research["venues"] if row["routing_status"] == "held"}
    assert len(held) == 3
    assert held.isdisjoint(site.id for site in snapshot.sites)


@pytest.mark.parametrize("mode", ["walking", "driving"])
@pytest.mark.parametrize("stream", [True, False])
def test_clothes_and_glass_route_together(mode, stream):
    adapter, calls = provider()
    planner = RoutingService(api.route_service.snapshot, api.classifier, adapter)
    clothing = (
        {"material": "clothes", "condition_confirmed": True}
        if stream
        else {
            "text": "clean shirt",
            "manual_kind": "wearable_clothes",
            "condition_confirmed": True,
        }
    )
    request = TripRequest(
        origin={"latitude": 41.99, "longitude": 21.435},
        mode=mode,
        share_coordinates=True,
        items=[clothing, {"material": "glass", "condition_confirmed": True}],
    )
    trip = planner.plan(request)
    assert set().union(*(set(stop.item_kinds) for stop in trip.stops)) == {
        "glass",
        "wearable_clothes",
    }
    stop = next(stop for stop in trip.stops if "wearable_clothes" in stop.item_kinds)
    assert stop.site_id.startswith("clothes-") and stop.arrival_notes
    assert not stop.unverified_materials
    assert calls
    clothing["condition_confirmed"] = False
    with pytest.raises(RoutingError, match="Confirm|confirmation"):
        planner.plan(
            request.model_copy(
                update={
                    "items": TripRequest(
                        origin=request.origin,
                        mode=mode,
                        share_coordinates=True,
                        items=[clothing],
                    ).items
                }
            )
        )


def test_missing_clothing_destinations_never_falls_back():
    adapter, calls = provider()
    base = SiteSnapshot.model_validate_json(api.snapshots["city"].body)
    planner = RoutingService(base, api.classifier, adapter)
    with pytest.raises(RoutingError, match="No explicitly accepting"):
        planner.plan(
            TripRequest(
                origin={"latitude": 41.99, "longitude": 21.435},
                mode="walking",
                share_coordinates=True,
                items=[{"material": "clothes", "condition_confirmed": True}],
            )
        )
    assert not calls


@pytest.mark.parametrize(
    "description,condition,expected",
    [
        ("blue shirt", "uncertain", "candidate"),
        ("clean jeans", "appears_empty_clean", "candidate"),
        ("torn shirt", "appears_empty_clean", "needs_review"),
        ("shirt", "not_empty_or_contaminated", "needs_review"),
        ("unknown object", "appears_empty_clean", "needs_review"),
        ("shirt and phone", "appears_empty_clean", "needs_review"),
        ("shirt with leaking battery", "uncertain", "specialist"),
    ],
)
def test_photo_clothing_guardrails(description, condition, expected):
    result = VisionService._suggestion(
        ModelPhotoItem(
            description=description,
            item_kind="wearable_clothes",
            visible_condition=condition,
            reason="Visible object.",
        )
    )
    assert result.status == expected
    assert (
        "wearable_clothes"
        in _output_schema()["properties"]["items"]["items"]["properties"]["item_kind"]["enum"]
    )


@pytest.mark.parametrize("change", ["checksum", "duplicate", "coordinates", "source"])
def test_clothing_catalog_fails_closed(tmp_path, change):
    data = json.loads((DIRECTORY / "sites.json").read_text(encoding="utf-8"))
    manifest = json.loads((DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
    if change == "duplicate":
        data["sites"][1] = data["sites"][0]
    if change == "coordinates":
        data["sites"][0]["latitude"] = 0
    if change == "source":
        data["sites"][0]["coordinate_source"] = "https://example.com/guessed"
    raw = json.dumps(data)
    manifest["sites_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    if change == "checksum":
        manifest["sites_sha256"] = "invalid"
    (tmp_path / "sites.json").write_text(raw, encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        add_clothing_sites(api.route_service.snapshot, tmp_path, api.settings.guidance_policy_path)


def test_scraper_extracts_counts_and_detects_source_changes():
    spec = importlib.util.spec_from_file_location(
        "clothing_scraper", ROOT / "scripts/scrape_clothing_locations.py"
    )
    scraper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scraper)
    rows = [
        f"<li>{count} контејнери {token}</li>"
        if count
        else f"<li>{token}, секој работен ден од 08:00</li>"
        for token, (_, _, count, _) in scraper.VENUES.items()
    ]
    html = "<ul>" + "".join(rows) + "</ul>"
    result = scraper.extract(html)
    assert len(result) == 8
    assert sum(row["reported_containers"] or 0 for row in result) == 8
    with pytest.raises(ValueError, match="changed"):
        scraper.extract(html.replace("2 контејнери", "3 контејнери", 1))
