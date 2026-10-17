"""Complete browser journeys through real APIs; only external providers are simulated."""

import os
import subprocess
import sys

import httpx
import pytest
from PIL import Image
from playwright.sync_api import expect
from test_web_browser import ROOT, add_trip_item, open_ai
from test_web_browser import browser as browser_fixture
from test_web_browser import page as page_fixture
from test_web_browser import web_url as web_url_fixture

from smart_recycling.routing_models import STREAM_KINDS

browser = browser_fixture
page = page_fixture
web_url = web_url_fixture

pytestmark = [
    pytest.mark.skipif(os.getenv("SRA_BROWSER_TESTS") != "1", reason="Opt-in browser tests"),
    pytest.mark.parametrize("web_url", ["system_server:app"], indirect=True),
]


@pytest.fixture(autouse=True)
def isolate_trip_budget(web_url):
    """Each journey gets an independent quota; rate limiting has separate unit tests."""
    response = httpx.post(web_url + "/__test/reset-routing-budget")
    assert response.status_code == 200


@pytest.mark.parametrize("entry", ["text", "photo", "picker"])
@pytest.mark.parametrize("mode,profile", [("Walking", "foot-walking"), ("Driving", "driving-car")])
def test_complete_item_to_accepted_stops(page, web_url, tmp_path, entry, mode, profile):
    page.goto(web_url)
    if entry == "photo":
        open_ai(page)
        photo = tmp_path / "fixture.png"
        Image.new("RGB", (80, 60), "white").save(photo)
        page.get_by_label("Photo", exact=True).set_input_files(photo)
        page.get_by_role("button", name="Suggest from photo", exact=True).click()
        expect(page.locator("#photo-result")).to_contain_text("empty glass jar")
        expect(page.locator("#trip-items li")).to_have_count(0)
        page.get_by_role("button", name="Review suggestion", exact=True).click()
        page.get_by_role("button", name="Confirm & add to trip", exact=True).click()
        # Editing the input intentionally cancels an in-flight confirmation.
        expect(page.locator("#basket-count")).to_have_text("1 selected")
    elif entry == "picker":
        page.get_by_role("button", name="Glass bottles and jars").click()
        page.get_by_role("button", name="Paper and cartons").click()
        page.locator("#confirm-picks").click()
    else:
        add_trip_item(page)
    if entry != "picker":
        add_trip_item(page, "clean paper", "clean_paper")
    expect(page.locator("#basket-count")).to_have_text("2 selected")
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("41.9965")
    page.get_by_label("Longitude", exact=True).fill("21.4314")
    page.get_by_role("button", name="Set coordinates").click()
    page.get_by_label(mode, exact=True).check()
    with page.expect_response("**/api/v1/trips") as pending:
        page.get_by_role("button", name="Find my route", exact=True).click()
    response = pending.value
    assert response.status == 200
    assert response.headers["cache-control"] == "no-store"
    trip = response.json()
    assert trip["profile"] == profile
    assert trip["ends_at_last_stop"] is True
    sites = {s["id"]: s for s in httpx.get(web_url + "/api/v1/sites").json()["sites"]}
    covered = set()
    for stop in trip["stops"]:
        assets = [a for a in sites[stop["site_id"]]["assets"] if a["id"] in stop["asset_ids"]]
        accepted = {k for a in assets for k in a["acceptance"]["accepted_item_kinds"]}
        required = set().union(*(STREAM_KINDS.get(k, {k}) for k in stop["item_kinds"]))
        assert required <= accepted
        covered.update(stop["item_kinds"])
    assert covered == (
        {"glass", "paper_tetrapak"}
        if entry == "picker"
        else {"empty_glass_packaging", "clean_paper"}
    )
    expect(page.locator("#trip-result")).to_contain_text(mode + " trip")
    expect(page.locator(".route-stop-number")).to_have_count(len(trip["stops"]))
    page.get_by_role("link", name="City coverage", exact=True).click()
    expect(page.locator("#city-results")).to_be_visible()
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-results")).to_be_visible()
    expect(page.locator("#upgrade-position")).to_have_text("1 of 5")
    expect(page.locator("#upgrade-map .upgrade-star")).to_have_count(1)


@pytest.mark.parametrize("width", [360, 1280])
@pytest.mark.parametrize("entry", ["picker", "text", "photo"])
@pytest.mark.parametrize("mode", ["Walking", "Driving"])
def test_clothing_donation_journey(page, web_url, tmp_path, width, entry, mode):
    page.set_viewport_size({"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(web_url)
    expect(page.locator(".waste-card")).to_have_count(6)
    if entry == "picker":
        # All six cards remain equal-sized; electronics no longer spans both columns.
        sizes = page.locator(".waste-card").evaluate_all(
            "els => els.map(el => [el.offsetWidth, el.offsetHeight])"
        )
        assert all(size == sizes[0] for size in sizes)
        page.screenshot(
            path=str(ROOT / "artifacts" / f"clothes-layout-{width}.png"), full_page=True
        )
        page.get_by_role("button", name="Clothes for donation", exact=True).click()
        expect(page.locator("#picker-condition")).to_contain_text("washed and wearable")
        expect(page.locator("#picker-condition")).not_to_contain_text("Electronics")
        page.locator("#confirm-picks").click()
    elif entry == "text":
        add_trip_item(page, "clean shirt", "wearable_clothes")
    else:
        open_ai(page)
        photo = tmp_path / "clothes.png"
        Image.new("RGB", (80, 60), "red").save(photo)
        page.get_by_label("Photo", exact=True).set_input_files(photo)
        page.get_by_role("button", name="Suggest from photo", exact=True).click()
        expect(page.locator("#trip-items li")).to_have_count(0)
        expect(page.locator("#photo-items")).to_contain_text("Clothes · donation")
        page.get_by_role("button", name="Review suggestion", exact=True).click()
        expect(page.locator("#category")).to_have_text("Clothes · donation")
        expect(page.locator("#condition-label")).to_contain_text("washed and wearable")
        page.get_by_role("button", name="Confirm & add to trip", exact=True).click()
    expect(page.locator("#trip-items")).to_contain_text("Clothes · donation")
    expect(page.get_by_role("button", name="Clothes for donation", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("41.99")
    page.get_by_label("Longitude", exact=True).fill("21.435")
    page.get_by_role("button", name="Set coordinates").click()
    page.get_by_label(mode, exact=True).check()
    with page.expect_response("**/api/v1/trips") as pending:
        page.get_by_role("button", name="Find my route", exact=True).click()
    assert pending.value.status == 200
    trip = pending.value.json()
    assert trip["candidate_count"] == 3
    assert len(trip["stops"]) == 1
    assert trip["stops"][0]["site_id"].startswith("clothes-")
    assert trip["stops"][0]["item_kinds"] == ["wearable_clothes"]
    expect(page.locator("#trip-stop-1")).to_have_attribute("data-materials", "clothes")
    expect(page.locator("#trip-result")).to_contain_text("Clothes · donation")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors


def test_deployment_smoke_against_running_app(web_url):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/smoke_deployment.py"), "--url", web_url],
        capture_output=True,
        text=True,
        timeout=45,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("width", [360, 1280])
@pytest.mark.parametrize("entry", ["text", "photo", "picker"])
@pytest.mark.parametrize("mode", ["Walking", "Driving"])
def test_east_gate_small_device_journey(page, web_url, tmp_path, width, entry, mode):
    page.set_viewport_size({"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(web_url)
    if entry == "picker":
        expect(page.locator("#electronics-size")).to_be_hidden()
        page.get_by_role("button", name="Electronics", exact=True).click()
        page.get_by_label("Only phones, chargers, cables or earbuds", exact=True).check()
        page.locator("#confirm-picks").click()
        expect(page.locator("#electronics-size")).to_be_hidden()
    elif entry == "text":
        add_trip_item(page, "old phone", "small_electronics")
    else:
        open_ai(page)
        photo = tmp_path / "small-device.png"
        Image.new("RGB", (80, 60), "lime").save(photo)
        page.get_by_label("Photo", exact=True).set_input_files(photo)
        page.get_by_role("button", name="Suggest from photo", exact=True).click()
        page.get_by_role("button", name="Review suggestion", exact=True).click()
        page.get_by_role("button", name="Confirm & add to trip", exact=True).click()
    expect(page.locator("#trip-items")).to_contain_text("Small electronics")
    expect(page.get_by_role("button", name="Electronics", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("41.998")
    page.get_by_label("Longitude", exact=True).fill("21.451")
    page.get_by_role("button", name="Set coordinates").click()
    page.get_by_label(mode, exact=True).check()
    with page.expect_response("**/api/v1/trips") as pending:
        page.get_by_role("button", name="Find my route", exact=True).click()
    assert pending.value.status == 200
    trip = pending.value.json()
    assert trip["candidate_count"] == 2
    assert trip["stops"][0]["site_id"] == "ewaste-east-gate-mall"
    assert trip["stops"][0]["item_kinds"] == ["small_electronics"]
    expect(page.locator("#trip-result")).to_contain_text("ask the information desk")
    expect(page.locator("#trip-stop-1")).to_have_attribute("data-materials", "special_unsupported")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors
    if entry == "picker":
        page.screenshot(
            path=str(ROOT / "artifacts" / f"east-gate-{width}-{mode}.png"), full_page=True
        )


@pytest.mark.parametrize("width", [360, 1280])
@pytest.mark.parametrize("entry", ["text", "photo", "picker"])
@pytest.mark.parametrize("mode", ["Walking", "Driving"])
def test_general_and_electronics_complete_journey(page, web_url, tmp_path, width, entry, mode):
    page.set_viewport_size({"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(web_url)
    if entry == "picker":
        page.get_by_role("button", name="General waste", exact=True).click()
        page.get_by_role("button", name="Electronics", exact=True).click()
        page.locator("#confirm-picks").click()
    elif entry == "text":
        add_trip_item(page, "used tissue", "ordinary_residual")
        add_trip_item(page, "old charger", "electronics")
    else:
        open_ai(page)
        photo = tmp_path / "new-streams.png"
        Image.new("RGB", (80, 60), "blue").save(photo)
        page.get_by_label("Photo", exact=True).set_input_files(photo)
        page.get_by_role("button", name="Suggest from photo", exact=True).click()
        expect(page.locator("#photo-items li")).to_have_count(2)
        expect(page.locator("#trip-items li")).to_have_count(0)
        for index in range(2):
            page.locator("#photo-items li").nth(index).get_by_role(
                "button",
                name="Review suggestion",
                exact=True,
            ).click()
            expect(page.locator("#manual-form")).to_be_visible()
            page.get_by_role("button", name="Confirm & add to trip", exact=True).click()
            expect(page.locator("#trip-items li")).to_have_count(index + 1)
    expect(page.locator("#trip-items li")).to_have_count(2)
    for material in ("general", "electronics"):
        expect(page.locator(f'[data-material="{material}"]')).to_have_attribute(
            "aria-pressed", "true"
        )
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("41.9965")
    page.get_by_label("Longitude", exact=True).fill("21.4314")
    page.get_by_role("button", name="Set coordinates").click()
    page.get_by_label(mode, exact=True).check()
    with page.expect_response("**/api/v1/trips") as pending:
        page.get_by_role("button", name="Find my route", exact=True).click()
    assert pending.value.status == 200
    trip = pending.value.json()
    required = {"electronics", "general" if entry == "picker" else "ordinary_residual"}
    assert set().union(*(set(stop["item_kinds"]) for stop in trip["stops"])) == required
    electronics = next(stop for stop in trip["stops"] if "electronics" in stop["item_kinds"])
    assert electronics["site_id"] == "ewaste-karpos-yard"
    expect(page.locator("#trip-result")).to_contain_text("Karpos recycling yard")
    expect(page.locator("#trip-result")).to_contain_text("Drop off: Electronics")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors


@pytest.mark.parametrize("mode", ["Walking", "Driving"])
def test_glass_and_general_streams_route_together_with_visible_warning(page, web_url, mode):
    page.goto(web_url)
    for label in ("Glass bottles and jars", "General waste"):
        card = page.get_by_role("button", name=label, exact=True)
        card.click()
        expect(card).to_have_attribute("aria-pressed", "true")
        expect(card.locator(".mark-check")).to_be_visible()
    expect(page.locator("#general-note")).to_have_count(0)
    page.locator("#confirm-picks").click()
    expect(page.locator("#trip-items li")).to_have_count(2)
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("41.9965")
    page.get_by_label("Longitude", exact=True).fill("21.4314")
    page.get_by_role("button", name="Set coordinates").click()
    page.get_by_label(mode, exact=True).check()
    with page.expect_response("**/api/v1/trips") as pending:
        page.get_by_role("button", name="Find my route", exact=True).click()
    response = pending.value
    assert response.status == 200
    trip = response.json()
    assert set().union(*(set(s["item_kinds"]) for s in trip["stops"])) == {"glass", "general"}
    expect(page.locator(".acceptance-warning")).to_be_visible()
    expect(page.locator(".acceptance-warning")).to_contain_text("acceptance unverified")
    sites = {s["id"]: s for s in httpx.get(web_url + "/api/v1/sites").json()["sites"]}
    for stop in trip["stops"]:
        if "general" in stop["item_kinds"]:
            assert stop["unverified_materials"] == ["general"]
            assets = [a for a in sites[stop["site_id"]]["assets"] if a["id"] in stop["asset_ids"]]
            assert any("mixed_municipal_waste" in a["source_materials"] for a in assets)
