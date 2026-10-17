"""Real-page regressions; opt in after installing a Playwright browser.

CI runs these as a required gate. Tile traffic is stubbed: tests must not crawl OSM.
"""

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from PIL import Image
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.skipif(
    os.getenv("SRA_BROWSER_TESTS") != "1", reason="Set SRA_BROWSER_TESTS=1 for browser tests"
)
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def web_url(request, tmp_path_factory):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            getattr(request, "param", "smart_recycling.api:app"),
            "--app-dir",
            str(ROOT / "tests"),
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "SRA_MINILM_SUGGESTIONS": "false",
            "SRA_ORS_API_KEY": "",
            "OPENAI_API_KEY": "",
            "SRA_COMMUNITY_DB": str(tmp_path_factory.mktemp("browser-db") / "community.sqlite3"),
            "SRA_REVIEW_TOKEN": "browser-test-reviewer-" + "x" * 32,
            "SRA_VISION_DAILY_LIMIT": "10000",
            "SRA_VISION_CLIENT_DAILY_LIMIT": "10000",
            "SRA_VISION_CLIENT_HOURLY_LIMIT": "10000",
            "SRA_ROUTING_DAILY_LIMIT": "10000",
            "SRA_ROUTING_CLIENT_DAILY_LIMIT": "10000",
            "SRA_ROUTING_CLIENT_HOURLY_LIMIT": "10000",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(url + "/health", timeout=1).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            if process.poll() is not None:
                pytest.fail("Browser-test server failed startup")
            time.sleep(0.1)
        else:
            pytest.fail("Browser-test server did not become healthy")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(
            headless=True, channel=os.getenv("SRA_BROWSER_CHANNEL") or None
        )
        yield instance
        instance.close()


@pytest.fixture
def page(browser, web_url):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.set_default_timeout(15000)
    # Neutral fixture tile: avoid all automated requests to the public tile service.
    context.route(
        "https://tile.openstreetmap.org/**",
        lambda route: route.fulfill(
            content_type="image/svg+xml",
            body='<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">'
            '<rect width="256" height="256" fill="#e5eadf"/></svg>',
        ),
    )
    yield page
    context.close()


def test_clothing_discovery_is_separate_from_electronics(page, web_url):
    page.goto(web_url)
    open_discovery(page)
    page.get_by_label("Recorded material").select_option("clothes")
    expect(page.locator("#site-count")).to_contain_text("5 recorded sites")
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill("Kopche")
    expect(page.locator("#site-list li")).to_have_count(1)
    page.locator("#site-list button").click()
    expect(page.locator("#site-details")).to_contain_text("donation")
    expect(page.locator("#site-details")).to_contain_text("wearable")
    page.get_by_label("Recorded material").select_option("special_unsupported")
    expect(page.locator("#site-count")).to_contain_text("No recorded sites match")


def test_real_snapshot_filter_details_and_mobile_layout(page, web_url):
    errors = []
    page.on("pageerror", lambda error: errors.append(error))
    page.goto(web_url)
    expect(page.locator("#data-status")).to_contain_text("1,590 sites / 1,603 assets")
    expect(page.locator("#site-map canvas")).to_have_count(1)
    expect(page.get_by_role("link", name="OpenStreetMap", exact=True)).to_be_visible()
    expect(page.locator("#site-list")).to_be_hidden()
    expect(page.locator("#site-list li")).to_have_count(0)
    expect(page.get_by_role("button", name="Next sites")).to_have_count(0)
    open_discovery(page)
    page.get_by_label("Recorded material").select_option("glass")
    snapshot = httpx.get(web_url + "/api/v1/sites").json()
    count = sum("glass" in site["materials"] for site in snapshot["sites"])
    expect(page.locator("#site-count")).to_contain_text(f"{count} recorded sites")
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill("Centar")
    expect(page.locator("#site-list li")).to_have_count(5)
    expect(page.locator("#search-status")).to_contain_text("Keep typing")
    page.locator("#site-list button").first.click()
    expect(page.locator("#site-details")).to_contain_text("Operating status: unknown")
    expect(page.locator("#site-details")).to_contain_text("Acceptance limits:")
    page.get_by_label("Recorded material").select_option("special_unsupported")
    expect(page.locator("#site-count")).to_contain_text("No recorded sites match")
    expect(page.locator("#site-details")).to_be_hidden()
    expect(page.locator("#site-list li")).to_have_count(0)
    page.get_by_label("Recorded material").select_option("all")
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill("not-a-real-site")
    expect(page.locator("#site-count")).to_contain_text("No recorded sites match")
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill("Centar")
    expect(page.locator("#site-list li").first).to_contain_text("Centar")
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill(" ")
    expect(page.locator("#site-list li")).to_have_count(0)
    expect(page.locator("#site-list")).to_be_hidden()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_visual_polish_navigation_icons_and_helper(page, web_url, width):
    page.set_viewport_size({"width": width, "height": 960})
    page.goto(web_url)
    expect(page.locator("#site-map")).to_have_attribute("data-zoom", "16")
    for route, active in [("/", "Recycle"), ("/city", "City coverage")]:
        if route != "/":
            page.get_by_role("link", name="City coverage", exact=True).click()
        expect(page.locator(".flow-nav a")).to_have_text(["Recycle", "City coverage"])
        expect(page.locator(".flow-nav [aria-current=page]")).to_have_text(active)
        for link in page.locator(".flow-nav a").all():
            assert link.bounding_box()["height"] >= 44
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("link", name="Recycle", exact=True).click()
    expect(page.locator(".waste-icon")).to_have_count(6)
    assert page.locator(".waste-icon").evaluate_all("""icons => icons.every(icon => {
      const box = icon.getBoundingClientRect();
      return box.width === box.height && box.width >= 64;
    })""")
    screenshots = os.getenv("SRA_LAYOUT_SCREENSHOTS")
    if screenshots:
        page.screenshot(path=str(Path(screenshots) / f"polish-recycle-{width}.png"))
        page.locator(".choose-column").screenshot(
            path=str(Path(screenshots) / f"polish-icons-{width}.png")
        )
    page.locator("#ai-help summary").click()
    expect(page.locator("#classify-form")).to_be_visible()
    page.get_by_text("Enter coordinates manually", exact=True).click()
    for selector in ["#item", "#latitude", "#longitude"]:
        assert page.locator(selector).evaluate(
            "el => parseFloat(getComputedStyle(el).fontSize)"
        ) >= (16 if width <= 760 else 14)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    if screenshots:
        page.locator("#ai-help").screenshot(
            path=str(Path(screenshots) / f"polish-helper-{width}.png")
        )
    screenshot = os.getenv("SRA_BROWSER_SCREENSHOT")
    if screenshot:
        page.locator("#collection-points").screenshot(path=screenshot)


def test_manual_origin_map_origin_and_clear(page, web_url):
    page.goto(web_url)
    expect(page.locator("#data-status")).to_contain_text("1,590")
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill("Centar")
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("41.9981")
    page.get_by_label("Longitude", exact=True).fill("21.4254")
    page.get_by_role("button", name="Set coordinates").click()
    expect(page.locator("#origin-coordinates")).to_contain_text("Manual starting point")
    expect(page.locator("#site-list li").first).to_contain_text("km straight-line")
    page.get_by_role("button", name="Change", exact=True).click()
    page.get_by_role("button", name="Choose on map").click()
    page.get_by_role("button", name="Use map center").click()
    expect(page.locator("#origin-coordinates")).to_contain_text("Map center starting point")
    page.get_by_role("button", name="Change", exact=True).click()
    page.get_by_role("button", name="Choose on map").click()
    page.locator("#site-map").click(position={"x": 120, "y": 90})
    expect(page.locator("#origin-coordinates")).to_contain_text("Selected starting point")
    page.get_by_role("button", name="Change", exact=True).click()
    page.get_by_role("button", name="Clear starting point").click()
    expect(page.locator("#latitude")).to_have_value("")
    expect(page.locator("#site-list li").first).not_to_contain_text("km straight-line")


def test_location_denied_and_late_position_cannot_replace_manual_origin(page, web_url):
    page.add_init_script("""navigator.geolocation.getCurrentPosition = (ok, fail) => {
      if (!window.lateLocation) fail({code: 1}); else window.pendingPosition = ok;
    };""")
    page.goto(web_url)
    page.get_by_role("button", name="Use my location").click()
    expect(page.locator("#origin-status")).to_contain_text("permission denied")
    expect(page.get_by_role("button", name="Use my location")).to_be_enabled()
    page.evaluate("window.lateLocation = true")
    page.get_by_role("button", name="Use my location").click()
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("42")
    page.get_by_label("Longitude", exact=True).fill("21.4")
    page.get_by_role("button", name="Set coordinates").click()
    page.evaluate("window.pendingPosition({coords:{latitude:0,longitude:0,accuracy:10}})")
    expect(page.locator("#origin-coordinates")).to_contain_text("42.00000, 21.40000")


def test_device_location_and_reload_privacy(page, web_url):
    page.context.grant_permissions(["geolocation"])
    page.context.set_geolocation({"latitude": 42, "longitude": 21.4, "accuracy": 20})
    requests = []
    page.on("request", lambda request: requests.append((request.url, request.post_data)))
    page.goto(web_url)
    page.get_by_role("button", name="Use my location").click()
    expect(page.locator("#origin-coordinates")).to_contain_text("Device location")
    expect(page.locator("#origin-coordinates")).to_contain_text("±20 m")
    page.reload()
    expect(page.locator("#origin-status")).to_have_text("")
    assert not any("latitude" in url or body for url, body in requests)


@pytest.mark.parametrize("width", [320, 390, 1280])
def test_location_summary_edit_cancel_and_selection_count(page, web_url, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.route("**/api/v1/routing", lambda route: route.fulfill(json={"configured": True}))
    page.goto(web_url)
    expect(page.locator("#origin-summary")).to_be_hidden()
    # Location methods are neutral actions, not an implied selected GPS value.
    assert page.locator("#locate").evaluate("el => getComputedStyle(el).backgroundColor") == (
        page.locator("#pick-origin").evaluate("el => getComputedStyle(el).backgroundColor")
    )
    for label in (
        "Glass bottles and jars",
        "Plastic bottles and cans",
        "Paper and cartons",
        "General waste",
    ):
        page.get_by_role("button", name=label, exact=True).click()
    page.locator("#confirm-picks").click()
    expect(page.locator("#basket-count")).to_have_text("4 selected")
    expect(page.locator("#locate")).to_be_focused()
    page.get_by_role("button", name="Choose on map", exact=True).click()
    expect(page.locator("#pick-origin")).to_have_attribute("aria-pressed", "true")
    page.get_by_role("button", name="Use map center", exact=True).click()
    expect(page.locator("#origin-summary")).to_be_visible()
    expect(page.locator("#origin-editor")).to_be_hidden()
    expect(page.locator("#clear-origin")).to_be_hidden()
    expect(page.locator("#origin-label")).to_be_focused()
    expect(page.locator("#origin-label")).to_have_text("Point on map")
    expect(page.locator("#map-pick-hint")).to_be_hidden()
    expect(page.locator("#pick-controls")).to_be_hidden()
    expect(page.locator("#pick-origin")).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#origin-details")).not_to_have_attribute("open", "")
    expect(page.locator("#plan-trip")).to_be_enabled()
    saved = page.locator("#origin-coordinates").text_content()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    screenshots = os.getenv("SRA_LAYOUT_SCREENSHOTS")
    if screenshots:
        page.locator("#trip-panel").screenshot(
            path=str(Path(screenshots) / f"trip-ready-{width}.png")
        )
    page.get_by_role("button", name="Change", exact=True).click()
    expect(page.locator("#origin-summary")).to_be_hidden()
    expect(page.locator("#origin-editor")).to_be_visible()
    expect(page.locator("#plan-trip")).to_be_disabled()
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("0")
    page.get_by_role("button", name="Keep current point", exact=True).click()
    expect(page.locator("#origin-coordinates")).to_have_text(saved)
    expect(page.locator("#plan-trip")).to_be_enabled()
    expect(page.locator("#change-origin")).to_be_focused()
    page.get_by_role("button", name="General waste", exact=True).click()
    page.get_by_role("button", name="General waste", exact=True).click()
    page.locator("#confirm-picks").click()
    expect(page.locator("#plan-trip")).to_be_focused()
    page.get_by_role("button", name="Change", exact=True).click()
    page.get_by_role("button", name="Clear starting point", exact=True).click()
    expect(page.locator("#origin-summary")).to_be_hidden()
    expect(page.locator("#origin-edit-actions")).to_be_hidden()
    expect(page.locator("#latitude")).to_have_value("")
    expect(page.locator("#plan-trip")).to_be_disabled()
    expect(page.locator("#locate")).to_be_focused()


def test_location_method_switches_ignore_late_gps_and_reset_busy_state(page, web_url):
    page.add_init_script(
        "navigator.geolocation.getCurrentPosition = ok => { window.pendingPosition = ok; };"
    )
    page.goto(web_url)
    page.get_by_role("button", name="Use my location", exact=True).click()
    expect(page.locator("#locate")).to_have_text("Locating…")
    expect(page.locator("#locate")).to_have_attribute("aria-busy", "true")
    page.get_by_role("button", name="Choose on map", exact=True).click()
    expect(page.locator("#locate")).to_have_text("Use my location")
    expect(page.locator("#locate")).to_have_attribute("aria-busy", "false")
    page.evaluate("window.pendingPosition({coords:{latitude:0,longitude:0,accuracy:10}})")
    expect(page.locator("#origin-summary")).to_be_hidden()
    expect(page.locator("#map-pick-hint")).to_be_visible()
    page.get_by_role("button", name="Use my location", exact=True).click()
    expect(page.locator("#map-pick-hint")).to_be_hidden()
    expect(page.locator("#pick-origin")).to_have_attribute("aria-pressed", "false")
    page.evaluate("window.pendingPosition({coords:{latitude:42,longitude:21.4,accuracy:20}})")
    expect(page.locator("#origin-label")).to_have_text("Current location")
    expect(page.locator("#origin-editor")).to_be_hidden()
    expect(page.locator("#origin-coordinates")).to_contain_text("±20 m")
    page.get_by_role("button", name="Change", exact=True).click()
    page.get_by_role("button", name="Use my location", exact=True).click()
    page.get_by_role("button", name="Keep current point", exact=True).click()
    page.evaluate("window.pendingPosition({coords:{latitude:0,longitude:0,accuracy:10}})")
    expect(page.locator("#origin-coordinates")).to_contain_text("42.00000, 21.40000")
    expect(page.locator("#origin-editor")).to_be_hidden()


def test_cached_refresh_failure_and_no_cache_failure(page, web_url):
    page.route("**/api/v1/sites?scope=citizen", lambda route: route.abort())
    page.goto(web_url)
    expect(page.locator("#data-status")).to_contain_text("no saved snapshot")
    expect(page.locator("#data-details")).to_have_attribute("open", "")
    expect(page.get_by_role("button", name="Refresh site data")).to_be_enabled()
    page.unroute("**/api/v1/sites?scope=citizen")
    page.get_by_role("button", name="Refresh site data").click()
    expect(page.locator("#data-status")).to_contain_text("1,590")
    page.route("**/api/v1/sites?scope=citizen", lambda route: route.abort())
    page.get_by_role("button", name="Refresh site data").click()
    expect(page.locator("#data-status")).to_contain_text("Showing saved snapshot as of")
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill("Centar")
    expect(page.locator("#site-list li")).to_have_count(5)


def test_tile_failure_keeps_list_and_library_failure_keeps_coordinates(page, web_url):
    page.route("https://tile.openstreetmap.org/**", lambda route: route.abort())
    page.goto(web_url)
    expect(page.locator("#map-status")).to_contain_text("tiles are unavailable")
    expect(page.locator("#site-list")).to_be_hidden()
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill("Centar")
    expect(page.locator("#site-list")).to_be_visible()
    expect(page.locator("#site-list li")).to_have_count(5)
    page.route("**/vendor/leaflet/leaflet.js", lambda route: route.abort())
    page.reload()
    expect(page.locator("#map-status")).to_contain_text("Map unavailable")
    expect(page.locator("#site-list")).to_be_hidden()
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill("Centar")
    expect(page.locator("#site-list")).to_be_visible()
    expect(page.locator("#site-list li")).to_have_count(5)
    expect(page.get_by_label("Latitude", exact=True)).to_be_enabled()


def test_guidance_manual_recovery_and_specialist_safety(page, web_url):
    page.goto(web_url)
    open_ai(page)
    page.get_by_label("Item", exact=True).fill("a jar")
    page.get_by_role("button", name="Check", exact=True).click()
    expect(page.locator("#question")).to_contain_text("What is the item made of")
    page.get_by_label("Choose the item type").select_option("empty_glass_packaging")
    page.get_by_role("button", name="Confirm & add to trip").click()
    expect(page.locator("#message")).to_contain_text("Added to your trip")
    open_ai(page)
    page.get_by_label("Item", exact=True).fill("old battery")
    page.get_by_role("button", name="Check", exact=True).click()
    expect(page.locator("#category")).to_have_text("Specialist disposal")
    expect(page.locator("#contact")).to_be_visible()
    expect(page.locator("#manual-form")).to_be_hidden()
    expect(page.get_by_role("button", name="Confirm & add to trip")).to_be_hidden()


def test_photo_suggestion_requires_review_before_trip_add(page, web_url, tmp_path):
    photo = tmp_path / "recycling-items.png"
    Image.new("RGB", (80, 60), "green").save(photo)
    page.route(
        "**/api/v1/photo-suggestions",
        lambda route: route.fulfill(
            json={
                "items": [
                    {
                        "description": "clear glass jar",
                        "item_kind": "empty_glass_packaging",
                        "category": "glass",
                        "visible_condition": "appears_empty_clean",
                        "status": "candidate",
                        "reason": "It appears to be empty glass packaging.",
                    }
                ],
                "model_version": "openai:fixture-model",
                "policy_version": "skopje-policy-v1",
                "requires_user_confirmation": True,
                "message": "Review every suggestion before adding it to your trip.",
            }
        ),
    )
    page.goto(web_url)
    open_ai(page)
    page.get_by_label("Photo", exact=True).set_input_files(photo)
    expect(page.locator("#photo-file-name")).to_have_text("recycling-items.png")
    page.get_by_role("button", name="Suggest from photo", exact=True).click()
    expect(page.locator("#photo-result")).to_contain_text("clear glass jar")
    expect(page.locator("#trip-items li")).to_have_count(0)
    page.get_by_role("button", name="Review suggestion", exact=True).click()
    expect(page.get_by_label("Choose the item type")).to_have_value("empty_glass_packaging")
    page.get_by_role("button", name="Confirm & add to trip", exact=True).click()
    expect(page.locator("#basket-count")).to_have_text("1 selected")


def open_ai(page):
    if page.locator("#ai-help").get_attribute("open") is None:
        page.locator("#ai-help > summary").click()


def open_discovery(page):
    if page.locator("#discovery-controls").get_attribute("open") is None:
        page.locator("#discovery-controls > summary").click()


def add_trip_item(page, description="a jar", kind="empty_glass_packaging"):
    open_ai(page)
    page.get_by_label("Item", exact=True).fill(description)
    page.get_by_role("button", name="Check", exact=True).click()
    page.get_by_label("Choose the item type").select_option(kind)
    page.get_by_role("button", name="Confirm & add to trip").click()
    expect(page.locator("#message")).to_contain_text("Added to your trip")


def prepare_trip(page, web_url):
    page.route("**/api/v1/routing", lambda route: route.fulfill(json={"configured": True}))
    page.goto(web_url)
    add_trip_item(page)
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("41.9965")
    page.get_by_label("Longitude", exact=True).fill("21.4314")
    page.get_by_role("button", name="Set coordinates").click()


def trip_fixture(mode):
    return {
        "mode": mode,
        "distance_m": 1200,
        "duration_s": 900,
        "geometry": {"type": "LineString", "coordinates": [[21.4314, 41.9965], [21.432, 41.997]]},
        "stops": [
            {
                "name": "Fixture glass collection",
                "latitude": 41.997,
                "longitude": 21.432,
                "item_kinds": ["empty_glass_packaging"],
                "network_access_gap_m": 4,
                "acceptance_limits": ["Empty glass packaging only"],
            }
        ],
        "source_as_of": "2026-09-19",
        "optimizer": "Fixture shortlist",
        "warnings": ["Fixture response; not a live route"],
        "attribution": "ORS / OSM",
    }


def test_trip_basket_modes_consent_and_edit_invalidation(page, web_url):
    requests = []

    def respond(route):
        payload = json.loads(route.request.post_data)
        requests.append(payload)
        route.fulfill(json=trip_fixture(payload["mode"]))

    page.route("**/api/v1/trips", respond)
    prepare_trip(page, web_url)
    add_trip_item(page, "clean paper", "clean_paper")
    expect(page.locator("#basket-count")).to_have_text("2 selected")
    assert requests == []
    page.get_by_role("button", name="Find my route", exact=True).click()
    expect(page.locator("#trip-result")).to_contain_text("Walking trip")
    expect(page.locator("#trip-result")).to_contain_text("Ends at the last stop")
    expect(page.locator(".trip-route-line")).to_have_attribute("stroke-dasharray", "8 10")
    expect(page.locator("#route-mode-label")).to_have_text("Walking")
    assert (
        page.locator(".route-line-key path").evaluate("el => getComputedStyle(el).strokeDasharray")
        != "none"
    )
    assert len(requests[0]["items"]) == 2
    assert requests[0]["share_coordinates"] is True
    page.get_by_label("Driving", exact=True).check()
    expect(page.locator("#trip-result")).to_be_hidden()
    page.get_by_role("button", name="Find my route", exact=True).click()
    expect(page.locator("#trip-result")).to_contain_text("Driving trip")
    expect(page.locator(".trip-route-line")).not_to_have_attribute("stroke-dasharray", "8 10")
    assert (
        page.locator(".trip-route-line").evaluate("el => getComputedStyle(el).strokeDasharray")
        == "none"
    )
    expect(page.locator("#route-mode-label")).to_have_text("Driving")
    assert (
        page.locator(".route-line-key path").evaluate("el => getComputedStyle(el).strokeDasharray")
        == "none"
    )
    page.get_by_role("button", name="Remove item 1", exact=True).click()
    expect(page.locator("#trip-result")).to_be_hidden()
    expect(page.locator("#basket-count")).to_have_text("1 selected")


@pytest.mark.parametrize("width", [320, 1280])
@pytest.mark.parametrize("mode", ["walking", "driving"])
def test_stop_colors_match_assigned_dropoffs_and_legend(page, web_url, width, mode):
    page.set_viewport_size({"width": width, "height": 900})
    fixture = trip_fixture(mode)
    assignments = [
        (["empty_glass_packaging"], "glass", "rgb(154, 115, 23)"),
        (["empty_plastic_bottle", "empty_metal_can"], "plastic_metal", "rgb(54, 115, 78)"),
        (["paper_tetrapak"], "paper_tetrapak", "rgb(82, 101, 166)"),
        (["general"], "general", "rgb(102, 115, 108)"),
    ]
    fixture["stops"] = [
        {
            **fixture["stops"][0],
            "name": f"Fixture {material}",
            "item_kinds": kinds,
            "latitude": 41.997 + index * 0.0003,
            "longitude": 21.432 + index * 0.0003,
        }
        for index, (kinds, material, _) in enumerate(assignments)
    ]
    fixture["geometry"]["coordinates"] = [[21.4314, 41.9965]] + [
        [stop["longitude"], stop["latitude"]] for stop in fixture["stops"]
    ]
    page.route("**/api/v1/trips", lambda route: route.fulfill(json=fixture))
    prepare_trip(page, web_url)
    page.get_by_label(mode.title(), exact=True).check()
    page.get_by_role("button", name="Find my route", exact=True).click()
    expect(page.locator(".route-stop-number")).to_have_count(4)
    for index, (_, material, color) in enumerate(assignments):
        badge = page.locator(f'.route-stop-number[data-materials="{material}"]')
        expect(badge).to_have_text(str(index + 1))
        assert badge.evaluate("el => getComputedStyle(el).backgroundColor") == color
        row = page.locator(f"#trip-stop-{index + 1}")
        expect(row).to_have_attribute("data-materials", material)
        assert row.evaluate("el => getComputedStyle(el, '::before').backgroundColor") == color
    expect(page.locator("#map-legend")).to_be_visible()
    expect(page.locator("#map-legend > span")).to_have_count(6)
    expect(page.locator("#map-legend")).not_to_contain_text("Mixed")
    legend = page.locator("#map-legend").bounding_box()
    key = page.locator("#route-map-key").bounding_box()
    assert key["y"] + key["height"] < legend["y"]
    for marker in page.locator(".route-stop-number, .origin-pin").all():
        box = marker.bounding_box()
        assert box["y"] + box["height"] < key["y"]
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    screenshots = os.getenv("SRA_LAYOUT_SCREENSHOTS")
    if screenshots:
        page.locator("#map-shell").screenshot(
            path=str(Path(screenshots) / f"stop-colors-{mode}-{width}.png")
        )


def test_trip_failure_and_stale_response(page, web_url):
    pending = []
    page.route("**/api/v1/trips", lambda route: pending.append(route))
    prepare_trip(page, web_url)
    with page.expect_request("**/api/v1/trips"):
        page.get_by_role("button", name="Find my route", exact=True).click()
    page.get_by_label("Driving", exact=True).check()
    pending[0].fulfill(json=trip_fixture("walking"))
    expect(page.locator("#trip-result")).to_be_hidden()
    expect(page.get_by_role("button", name="Find my route", exact=True)).to_be_enabled()
    page.unroute("**/api/v1/trips")
    page.route(
        "**/api/v1/trips",
        lambda route: route.fulfill(
            status=503,
            json={
                "detail": {
                    "code": "provider_timeout",
                    "message": "Routing timed out. Please retry.",
                }
            },
        ),
    )
    page.get_by_role("button", name="Find my route", exact=True).click()
    expect(page.locator("#trip-status")).to_contain_text("Routing timed out")
    expect(page.locator("#trip-result")).to_be_hidden()


def test_missing_routing_key_preserves_basket_but_does_not_claim_a_route(page, web_url):
    page.route("**/api/v1/routing", lambda route: route.fulfill(json={"configured": False}))
    page.goto(web_url)
    add_trip_item(page)
    expect(page.locator("#routing-availability")).to_contain_text("not configured")
    expect(page.get_by_role("button", name="Find my route", exact=True)).to_be_disabled()
    expect(page.locator("#basket-count")).to_have_text("1 selected")


def test_route_focus_hides_discovery_and_restores_after_edit(page, web_url):
    page.route("**/api/v1/trips", lambda route: route.fulfill(json=trip_fixture("walking")))
    prepare_trip(page, web_url)
    expect(page.locator(".leaflet-discovery-pane canvas")).to_be_visible()
    page.get_by_role("button", name="Find my route", exact=True).click()
    expect(page.locator("#route-summary")).to_contain_text("1.20 km")
    expect(page.locator("#route-map-key")).to_be_visible()
    expect(page.locator("#map-legend")).to_be_visible()
    expect(page.locator(".origin-pin")).to_have_count(1)
    expect(page.locator(".leaflet-discovery-pane canvas")).to_be_hidden()
    expect(page.locator(".route-stop-number")).to_have_text("1")
    expect(page.locator("#site-count")).to_contain_text("route and stops only")
    expect(page.locator("#discovery-controls")).not_to_have_attribute("open", "")
    page.get_by_role("button", name="Show other collection points", exact=True).click()
    expect(page.locator(".leaflet-discovery-pane canvas")).to_be_visible()
    page.get_by_label("Recorded material").select_option("glass")
    expect(page.locator(".route-stop-number")).to_have_count(1)
    page.get_by_role("button", name="Hide other collection points", exact=True).click()
    expect(page.locator(".leaflet-discovery-pane canvas")).to_be_hidden()
    page.get_by_role("button", name="Fit route", exact=True).click()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("button", name="Change", exact=True).click()
    page.get_by_role("button", name="Clear starting point", exact=True).click()
    expect(page.locator("#route-controls")).to_be_hidden()
    expect(page.locator(".route-stop-number")).to_have_count(0)
    expect(page.locator(".leaflet-discovery-pane canvas")).to_be_visible()
    expect(page.locator("#trip-result")).to_be_hidden()


def test_single_confirmation_adds_item_and_duplicate_is_not_added(page, web_url):
    requests = []
    page.on(
        "request",
        lambda request: requests.append(request) if request.url.endswith("/trips") else None,
    )
    page.goto(web_url)
    expect(page.locator("#plan-trip")).to_be_disabled()
    open_ai(page)
    page.get_by_label("Item", exact=True).fill("glass bottle")
    page.get_by_role("button", name="Check", exact=True).click()
    expect(page.get_by_label("Choose the item type")).to_have_value("empty_glass_packaging")
    expect(page.locator("#condition-label")).to_contain_text("no hazardous contents")
    expect(page.locator('#manual-form input[type="checkbox"]')).to_have_count(0)
    expect(page.locator("#electronics-size")).to_be_hidden()
    page.get_by_role("button", name="Confirm & add to trip").click()
    expect(page.locator("#basket-count")).to_have_text("1 selected")
    expect(page.locator("#manual-form")).to_be_hidden()
    expect(page.locator("#plan-trip")).to_be_disabled()
    page.get_by_role("button", name="Check", exact=True).click()
    page.get_by_role("button", name="Confirm & add to trip").click()
    expect(page.locator("#message")).to_contain_text("already in your trip")
    expect(page.locator("#basket-count")).to_have_text("1 selected")
    page.get_by_role("button", name="Add another item", exact=True).click()
    expect(page.locator("#item")).to_have_value("")
    expect(page.locator("#item")).to_be_focused()
    expect(page.locator("#result")).to_be_hidden()
    expect(page.locator("#continue-trip")).to_be_hidden()
    assert not requests


def test_confirmation_failure_retries_without_reentering_choice(page, web_url):
    page.goto(web_url)
    open_ai(page)
    page.get_by_label("Item", exact=True).fill("a jar")
    page.get_by_role("button", name="Check", exact=True).click()
    page.get_by_label("Choose the item type").select_option("empty_glass_packaging")
    page.route("**/api/v1/classify", lambda route: route.abort())
    page.get_by_role("button", name="Confirm & add to trip").click()
    expect(page.locator("#category")).to_have_text("Could not check this item")
    expect(page.get_by_label("Choose the item type")).to_have_value("empty_glass_packaging")
    expect(page.locator("#manual-form")).to_be_visible()
    page.unroute("**/api/v1/classify")
    page.get_by_role("button", name="Confirm & add to trip").click()
    expect(page.locator("#basket-count")).to_have_text("1 selected")


def test_pending_confirmation_cannot_add_after_item_edit(page, web_url):
    page.goto(web_url)
    open_ai(page)
    page.get_by_label("Item", exact=True).fill("a jar")
    page.get_by_role("button", name="Check", exact=True).click()
    page.get_by_label("Choose the item type").select_option("empty_glass_packaging")
    pending = []
    page.route("**/api/v1/classify", lambda route: pending.append(route))
    with page.expect_request("**/api/v1/classify"):
        page.get_by_role("button", name="Confirm & add to trip").click()
    expect(page.locator("#confirm-item")).to_be_disabled()
    open_ai(page)
    page.get_by_label("Item", exact=True).fill("old battery")
    pending[0].fulfill(
        json={
            "status": "ready_for_site_matching",
            "category": "glass",
            "item_kind": "empty_glass_packaging",
            "choices": [],
            "message": "Confirmed",
        }
    )
    expect(page.locator("#basket-count")).to_have_text("")
    expect(page.locator("#result")).to_be_hidden()
    page.unroute("**/api/v1/classify")
    page.get_by_role("button", name="Check", exact=True).click()
    expect(page.locator("#category")).to_have_text("Specialist disposal")
    expect(page.locator("#basket-count")).to_have_text("")


def test_routing_connection_retry_preserves_basket(page, web_url):
    page.route("**/api/v1/routing", lambda route: route.abort())
    page.goto(web_url)
    add_trip_item(page)
    expect(page.locator("#retry-routing")).to_be_visible()
    page.unroute("**/api/v1/routing")
    page.route("**/api/v1/routing", lambda route: route.fulfill(json={"configured": True}))
    page.get_by_role("button", name="Retry routing connection").click()
    expect(page.locator("#routing-availability")).to_have_text("")
    expect(page.locator("#retry-routing")).to_be_hidden()
    expect(page.locator("#basket-count")).to_have_text("1 selected")
    expect(page.locator("#plan-trip")).to_be_disabled()  # Origin still required.


def test_delayed_map_keeps_ready_route_and_stop_marker_opens_details(page, web_url):
    pending = []
    page.route("**/static/map-config.json*", lambda route: pending.append(route))
    page.route("**/api/v1/trips", lambda route: route.fulfill(json=trip_fixture("walking")))
    prepare_trip(page, web_url)
    page.get_by_role("button", name="Find my route", exact=True).click()
    expect(page.locator("#trip-result")).to_be_visible()
    config = json.loads((ROOT / "web/map-config.json").read_text())
    pending[0].fulfill(json=config)
    expect(page.locator(".route-stop-number")).to_have_text("1")
    expect(page.locator("#trip-result")).to_be_visible()
    expect(page.locator("#route-summary")).to_contain_text("1.20 km")
    page.locator(".route-stop-number").click()
    expect(page.locator("#trip-stop-1")).to_be_focused()
    page.locator(".route-stop").press("Space")
    expect(page.locator("#trip-stop-1")).to_be_focused()
    page.get_by_role("button", name="Change", exact=True).click()
    page.get_by_role("button", name="Choose on map").click()
    expect(page.locator("#pick-controls")).to_be_visible()
    page.get_by_role("button", name="Cancel selection").click()
    expect(page.locator("#pick-controls")).to_be_hidden()
    expect(page.locator("#trip-result")).to_be_visible()


def test_basket_limit_is_actionable_and_recovers_after_removal(page, web_url):
    page.goto(web_url)
    for index in range(6):
        add_trip_item(page, f"glass jar {index}")
    open_ai(page)
    page.get_by_label("Item", exact=True).fill("glass jar seven")
    page.get_by_role("button", name="Check", exact=True).click()
    page.get_by_label("Choose the item type").select_option("empty_glass_packaging")
    page.get_by_role("button", name="Confirm & add to trip").click()
    expect(page.locator("#message")).to_contain_text("six items")
    expect(page.locator("#basket-count")).to_have_text("6 selected")
    page.get_by_role("button", name="Remove item 1", exact=True).click()
    page.get_by_role("button", name="Confirm & add to trip").click()
    expect(page.locator("#message")).to_contain_text("Added to your trip")
    expect(page.locator("#basket-count")).to_have_text("6 selected")


def test_city_coverage_materials_municipalities_and_mobile_layout(page, web_url):
    errors = []
    page.on("pageerror", lambda error: errors.append(error))
    page.goto(web_url + "/city")
    expect(page.locator("#city-results")).to_be_visible()
    expect(page.locator(".estimate-note")).to_have_count(0)
    expect(page.locator("#equity-note")).to_have_text("Population within a 10-minute walk")
    expect(page.locator("#coverage-summary")).to_contain_text("Residents covered")
    expect(page.locator("#coverage-summary")).not_to_contain_text("(modeled)")
    expect(page.locator("#coverage-summary")).to_contain_text("58.1%")
    expect(page.locator("#municipality-chart .chart-row")).to_have_count(10)
    expect(page.locator("#municipality-chart .chart-bar")).to_have_count(10)
    page.get_by_label("Material stream").select_option("paper_tetrapak")
    expect(page.locator("#coverage-summary")).to_contain_text("5.0%")
    expect(page.locator("#municipality-chart .chart-row.below").first).to_be_visible()
    page.get_by_label("Material stream").select_option("general")
    expect(page.locator("#coverage-availability")).to_contain_text("unavailable, not zero")
    expect(page.locator("#municipality-chart .chart-bar")).to_have_count(0)
    expect(page.locator("#coverage-summary")).not_to_contain_text("0.0%")
    page.get_by_text("Method, sources and limitations", exact=True).click()
    expect(page.locator(".city-method")).to_contain_text("street network are unverified")
    expect(page.locator("#coverage-sources")).to_contain_text("WorldPop")
    expect(page.locator("#coverage-sources")).to_contain_text("unknown, not zero")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("link", name="Recycle", exact=True).click()
    expect(page.locator("#waste-picker")).to_be_visible()
    assert not errors


@pytest.mark.parametrize("width", [320, 360, 390, 768, 1280])
def test_city_shared_layout_and_expanded_results(page, web_url, width):
    page.set_viewport_size({"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(web_url + "/city")
    expect(page.get_by_role("heading", level=1)).to_have_text("City coverage")
    expect(page.locator(".brand")).to_have_text("Najdi Frli")
    expect(page.locator("#coverage-summary")).to_contain_text("58.1%")
    expect(page.locator("#city-status")).to_be_empty()
    expect(page.locator("#municipality-chart .chart-row")).to_have_count(10)
    expect(page.locator("#municipality-chart .chart-floor-label")).to_have_text("50% floor")
    expect(page.locator("#coverage-table-details, #coverage-municipalities")).to_have_count(0)
    expect(page.locator("#underserved-summary, #coverage-disconnected")).to_have_count(0)
    expect(page.get_by_text("Exact figures", exact=True)).to_have_count(0)
    expect(page.get_by_text("Access gaps", exact=True)).to_have_count(0)
    assert page.locator("#municipality-chart").evaluate("""chart => {
      const values = [...chart.querySelectorAll('.chart-bar')]
        .map(el => parseFloat(el.style.width));
      return values.every((v, i) => v >= 0 && v <= 100 && (i === 0 || v <= values[i - 1]));
    }""")
    expect(page.locator("#upgrade-status")).to_be_empty()
    expect(page.locator(".estimate-note")).to_have_count(0)
    expect(page.locator(".city-method")).not_to_have_attribute("open", "")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    if width > 1000:
        left = page.locator(".municipality-panel").bounding_box()
        right = page.locator(".upgrade-panel").bounding_box()
        assert abs(left["y"] - right["y"]) < 1
        assert right["x"] >= left["x"] + left["width"]
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-position")).to_have_text("1 of 5")
    expect(page.locator("#upgrade-map .upgrade-star")).to_have_count(1)
    page.get_by_text("By municipality", exact=True).click()
    expect(page.locator("#upgrade-municipalities .municipal-comparison")).to_have_count(10)
    page.get_by_text("Method, sources and limitations", exact=True).click()
    expect(page.locator("#upgrade-solver")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    screenshots = os.getenv("SRA_LAYOUT_SCREENSHOTS")
    if screenshots:
        page.locator(".municipality-panel").screenshot(
            path=str(Path(screenshots) / f"municipality-chart-{width}.png")
        )
        page.screenshot(path=str(Path(screenshots) / f"city-{width}.png"), full_page=True)
    page.get_by_label("Material stream").select_option("general")
    expect(page.locator("#coverage-availability")).to_be_visible()
    expect(page.locator("#coverage-summary")).to_contain_text("Unavailable")
    expect(page.locator("#municipality-chart .chart-bar")).to_have_count(0)
    expect(page.locator("#recommend-upgrades")).to_be_disabled()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors


def test_city_chart_preserves_zero_unknown_values_and_percentages(page, web_url):
    report = httpx.get(web_url + "/api/v1/coverage").json()
    selected = next(row for row in report["materials"] if row["material"] == "glass")
    selected["municipalities"][0].update(population=0, coverage_percent=None)
    selected["municipalities"][1]["coverage_percent"] = None
    page.route("**/api/v1/coverage", lambda route: route.fulfill(json=report))
    page.goto(web_url + "/city")
    expect(page.locator("#municipality-chart .chart-row")).to_have_count(10)
    expect(page.locator("#municipality-chart .chart-bar")).to_have_count(8)
    expect(page.locator("#municipality-chart")).to_contain_text("No modeled population")
    expect(page.locator("#municipality-chart")).to_contain_text("Unavailable")
    rows = page.locator("#municipality-chart .chart-row").evaluate_all("""rows => rows.map(row => ({
      name: row.querySelector('.chart-row-label span').textContent,
      value: row.querySelector('.chart-row-label strong').textContent,
      width: row.querySelector('.chart-bar')?.style.width ?? null
    }))""")
    expected = {m["name"]: m for m in selected["municipalities"]}
    for row in rows:
        value = expected[row["name"]]["coverage_percent"]
        if value is None:
            assert row["width"] is None
        else:
            # Browser CSS serialization rounds percentage precision.
            assert float(row["width"].removesuffix("%")) == pytest.approx(value, abs=0.0001)
            assert row["value"] == f"{value:.1f}%"
    zero = next(row for row in rows if row["name"] == "Shuto Orizari")
    assert zero["width"] == "0%" and zero["value"] == "0.0%"
    page.get_by_label("Material stream").select_option("paper_tetrapak")
    expect(page.locator("#coverage-summary")).to_contain_text("5.0%")
    expect(page.locator("#municipality-chart .chart-row")).to_have_count(10)


def test_city_coverage_unavailable_retry_and_no_substitute_metric(page, web_url):
    page.route(
        "**/api/v1/coverage", lambda route: route.fulfill(status=503, json={"detail": "Missing"})
    )
    page.goto(web_url + "/city")
    expect(page.locator("#city-status")).to_contain_text("No substitute metric")
    expect(page.locator("#city-results")).to_be_hidden()
    page.unroute("**/api/v1/coverage")
    page.get_by_role("button", name="Retry coverage", exact=True).click()
    expect(page.locator("#city-results")).to_be_visible()
    page.route("**/api/v1/coverage", lambda route: route.fulfill(json={"schema_version": 999}))
    page.reload()
    expect(page.locator("#city-status")).to_contain_text("No substitute metric")
    expect(page.locator("#city-results")).to_be_hidden()


def test_city_upgrades_budget_material_and_recovery(page, web_url):
    page.goto(web_url + "/city")
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-results")).to_be_visible()
    expect(page.locator("#upgrade-position")).to_have_text("1 of 5")
    expect(page.locator("#upgrade-summary [role=img]")).to_have_attribute(
        "aria-label", "Citywide: before 58.1%, with all proposed upgrades 59.3% walking access"
    )
    expect(page.locator("#upgrade-solver")).to_contain_text("Approximate search")
    expect(page.locator("#upgrade-municipalities .municipal-comparison")).to_have_count(10)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_label("Maximum sites to upgrade").fill("0")
    expect(page.locator("#upgrade-results")).to_be_hidden()
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-carousel")).to_be_hidden()
    expect(page.locator("#upgrade-status")).to_have_text("No upgrades selected for this budget.")
    expect(page.locator("#upgrade-solver")).to_contain_text("Exact search")
    page.get_by_label("Material stream").select_option("general")
    expect(page.locator("#upgrade-results")).to_be_hidden()
    expect(page.locator("#recommend-upgrades")).to_be_disabled()
    page.get_by_label("Material stream").select_option("paper_tetrapak")
    page.route("**/api/v1/upgrades?*", lambda route: route.fulfill(status=503, json={}))
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-status")).to_contain_text("retry")
    page.unroute("**/api/v1/upgrades?*")
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-results")).to_be_visible()
    expect(page.locator("#upgrade-summary [role=img]")).to_have_attribute(
        "aria-label", re.compile(r"Citywide: before 5\.0%")
    )


@pytest.mark.parametrize("width", [320, 390, 1280])
def test_city_upgrade_carousel_coordinates_reasons_and_navigation(page, web_url, width):
    plan = httpx.get(web_url + "/api/v1/upgrades?material=glass&n=5").json()["plan"]
    page.set_viewport_size({"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(web_url + "/city")
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-prev")).to_be_disabled()
    for index, site in enumerate(plan["sites"]):
        if index:
            page.get_by_role("button", name="Next suggested upgrade", exact=True).click()
        expect(page.locator("#upgrade-position")).to_have_text(f"{index + 1} of 5")
        expect(page.locator("#upgrade-carousel")).to_have_attribute("data-site-id", site["id"])
        expect(page.locator("#upgrade-site-title")).to_have_text(site["municipality"])
        expect(page.locator("#upgrade-location")).to_have_attribute(
            "href",
            f"https://www.openstreetmap.org/?mlat={site['lat']}&mlon={site['lon']}#map=18/{site['lat']}/{site['lon']}",
        )
        expect(page.locator("#upgrade-map .upgrade-star")).to_have_count(1)
        expect(page.locator("#upgrade-map .leaflet-container")).to_have_count(0)
        expect(page.locator("#upgrade-action-title")).to_have_text("Add glass collection")
        expect(page.locator("#upgrade-change")).to_contain_text("Add glass")
        expect(page.locator("#upgrade-reason")).not_to_contain_text(re.compile(r"\d"))
        municipality = next(m for m in plan["municipalities"] if m["name"] == site["municipality"])
        if municipality["before"] < plan["equity_floor_percent"]:
            expect(page.locator("#upgrade-reason")).to_contain_text("limited walking access")
        marker = page.locator(".upgrade-star").bounding_box()
        viewport = page.locator("#upgrade-map").bounding_box()
        assert abs(marker["x"] + marker["width"] / 2 - viewport["x"] - viewport["width"] / 2) < 2
        assert abs(marker["y"] + marker["height"] / 2 - viewport["y"] - viewport["height"] / 2) < 2
    expect(page.locator("#upgrade-next")).to_be_disabled()
    for index in range(4, 0, -1):
        page.get_by_role("button", name="Previous suggested upgrade", exact=True).click()
        expect(page.locator("#upgrade-position")).to_have_text(f"{index} of 5")
    expect(page.locator("#upgrade-prev")).to_be_disabled()
    page.locator("#upgrade-map-shell").focus()
    page.locator("#upgrade-map-shell").press("ArrowRight")
    expect(page.locator("#upgrade-position")).to_have_text("2 of 5")
    page.locator("#upgrade-map-shell").press("ArrowLeft")
    expect(page.locator("#upgrade-position")).to_have_text("1 of 5")
    for selector in ("#upgrade-prev", "#upgrade-next"):
        button = page.locator(selector).bounding_box()
        assert button["width"] >= 44 and button["height"] >= 44
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    screenshots = os.getenv("SRA_LAYOUT_SCREENSHOTS")
    if screenshots:
        page.locator("#upgrade-carousel").screenshot(
            path=str(Path(screenshots) / f"upgrade-carousel-{width}.png")
        )
    page.get_by_label("Maximum sites to upgrade").fill("1")
    expect(page.locator("#upgrade-carousel")).to_be_hidden()
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-position")).to_have_text("1 of 1")
    expect(page.locator("#upgrade-prev")).to_be_disabled()
    expect(page.locator("#upgrade-next")).to_be_disabled()
    assert not errors


@pytest.mark.parametrize(
    ("material", "action", "color"),
    [
        ("glass", "Add glass collection", "#9a7317"),
        ("plastic_metal", "Add plastic bottles and cans collection", "#36734e"),
        ("paper_tetrapak", "Add paper and cartons collection", "#5265a6"),
    ],
)
def test_city_upgrade_visual_action_and_truthful_comparisons(
    page, web_url, material, action, color
):
    plan = httpx.get(web_url + f"/api/v1/upgrades?material={material}&n=5").json()["plan"]
    page.goto(web_url + "/city")
    page.get_by_label("Material stream").select_option(material)
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-action-title")).to_have_text(action)
    expect(page.locator("#upgrade-results")).to_have_attribute("data-material", material)
    expect(page.locator("#upgrade-change .existing-bin")).to_have_count(2)
    expect(page.locator("#upgrade-change .new-bin .bin-symbol")).to_have_count(1)
    expect(page.locator("#upgrade-impact-title")).to_contain_text("whole plan")
    for selector in ("#upgrade-site-info", "#upgrade-summary", "#upgrade-municipalities"):
        expect(page.locator(selector)).not_to_contain_text(re.compile(r"\d"))
    assert (
        page.locator("#upgrade-results").evaluate(
            "el => getComputedStyle(el).getPropertyValue('--material').trim()"
        )
        == color
    )
    values = page.locator("#upgrade-summary .access-fill").evaluate_all(
        "bars => bars.map(el => parseFloat(el.style.width))"
    )
    assert values == pytest.approx([plan["before_percent"], plan["after_percent"]], abs=0.0001)
    page.get_by_text("By municipality", exact=True).click()
    rows = page.locator("#upgrade-municipalities .municipal-comparison").evaluate_all("""rows =>
      rows.map(row => ({
      name: row.querySelector('h4').textContent,
      values: [...row.querySelectorAll('.access-fill')].map(el => parseFloat(el.style.width))
    }))""")
    for row, municipality in zip(rows, plan["municipalities"], strict=True):
        assert row["name"] == municipality["name"]
        assert row["values"] == pytest.approx(
            [municipality["before"], municipality["after"]], abs=0.0001
        )
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_city_upgrade_unknown_access_is_not_shown_as_zero(page, web_url):
    body = httpx.get(web_url + "/api/v1/upgrades?material=glass&n=5").json()
    body["plan"]["municipalities"][0].update(before=None, after=None)
    page.route("**/api/v1/upgrades?*", lambda route: route.fulfill(json=body))
    page.goto(web_url + "/city")
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    page.get_by_text("By municipality", exact=True).click()
    first = page.locator("#upgrade-municipalities .municipal-comparison").first
    expect(first.locator(".access-fill")).to_have_count(0)
    expect(first.locator(".access-unknown")).to_have_count(2)
    expect(first).to_contain_text("Unavailable")


def test_city_carousel_delayed_map_uses_latest_slide_and_clears_on_material_change(page, web_url):
    pending = []
    page.route("**/static/map-config.json", lambda route: pending.append(route))
    page.goto(web_url + "/city")
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-position")).to_have_text("1 of 5")
    page.locator("#upgrade-next").click()
    expect(page.locator("#upgrade-position")).to_have_text("2 of 5")
    pending[0].fulfill(json=json.loads((ROOT / "web/map-config.json").read_text()))
    expect(page.locator(".upgrade-star")).to_have_attribute(
        "title", "Suggested upgrade 2: 32.2., Gjorche Petrov"
    )
    page.get_by_label("Material stream").select_option("general")
    expect(page.locator("#upgrade-carousel")).to_be_hidden()
    expect(page.locator(".upgrade-star")).to_have_count(0)
    page.get_by_label("Material stream").select_option("paper_tetrapak")
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-position")).to_have_text("1 of 5")
    expect(page.locator("#upgrade-action-title")).to_contain_text("Add paper and cartons")
    expect(page.locator(".upgrade-star")).to_have_count(1)


@pytest.mark.parametrize("failure", ["tiles", "config", "library"])
def test_city_carousel_map_failure_keeps_locations_and_can_recover(page, web_url, failure):
    url = {
        "tiles": "https://tile.openstreetmap.org/**",
        "config": "**/static/map-config.json",
        "library": "**/vendor/leaflet/leaflet.js",
    }[failure]
    page.route(url, lambda route: route.abort())
    page.goto(web_url + "/city")
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-map-status")).to_contain_text("unavailable")
    expect(page.locator("#upgrade-location")).to_be_visible()
    page.locator("#upgrade-next").click()
    expect(page.locator("#upgrade-position")).to_have_text("2 of 5")
    expect(page.locator("#upgrade-location")).to_have_attribute(
        "href", "https://www.openstreetmap.org/?mlat=42.0042&mlon=21.3445#map=18/42.0042/21.3445"
    )
    page.unroute(url)
    if failure == "library":
        page.reload()
        page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    else:
        page.locator("#retry-upgrade-map").click()
    expect(page.locator(".upgrade-star")).to_have_count(1)
    expect(page.locator("#upgrade-map-status")).to_be_empty()


def test_city_upgrades_stale_response_cannot_replace_new_selection(page, web_url):
    pending = []
    page.route("**/api/v1/upgrades?*", lambda route: pending.append(route))
    page.goto(web_url + "/city")
    page.get_by_role("button", name="Recommend upgrades", exact=True).click()
    expect(page.locator("#upgrade-status")).to_contain_text("Loading")
    page.get_by_label("Material stream").select_option("paper_tetrapak")
    assert len(pending) == 1
    pending[0].fulfill(
        json={"schema_version": 1, "plan": {"material": "glass", "requested_upgrades": 5}}
    )
    expect(page.locator("#upgrade-results")).to_be_hidden()
    expect(page.locator("#recommend-upgrades")).to_be_enabled()


@pytest.mark.parametrize("width", [320, 390, 1280])
@pytest.mark.parametrize("path", ["/", "/city"])
@pytest.mark.parametrize("language", ["en", "mk"])
def test_brand_visible_lettering_is_centered(page, web_url, tmp_path, width, path, language):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(web_url + path)
    page.locator(".language-switch").select_option(language)
    expect(page.locator("html")).to_have_attribute("lang", language)
    brand = page.get_by_role(
        "link", name="Najdi Frli home" if language == "en" else "Почетна страница на Najdi Frli"
    )
    expect(brand).to_have_text("Najdi Frli")
    expect(brand).to_have_attribute("href", "/")
    assert "Najdi Frli" in page.title()
    circle = brand.locator(".brand-mark").bounding_box()
    icon = brand.locator("img")
    expect(icon).to_be_visible()
    assert icon.evaluate("img => img.complete && img.naturalWidth > 0")
    arrow = icon.bounding_box()
    for axis, size in (("x", "width"), ("y", "height")):
        assert abs(circle[axis] + circle[size] / 2 - arrow[axis] - arrow[size] / 2) < 0.6

    # Compare rendered ink, not line boxes: font baseline space caused the misalignment.
    box = brand.bounding_box()
    wordmark = brand.locator(".brand-wordmark").bounding_box()
    screenshot = tmp_path / "brand.png"
    brand.screenshot(path=str(screenshot))
    with Image.open(screenshot).convert("RGB") as rendered:
        first_letter = round(wordmark["x"] - box["x"])
        ink_rows = [
            y
            for y in range(rendered.height)
            for x in range(first_letter, rendered.width)
            if all(channel < 170 for channel in rendered.getpixel((x, y)))
        ]
        assert ink_rows
        ink_center = box["y"] + (min(ink_rows) + max(ink_rows) + 1) / 2
        assert abs(ink_center - circle["y"] - circle["height"] / 2) <= 1.5
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    screenshot_dir = os.getenv("SRA_LAYOUT_SCREENSHOTS")
    if screenshot_dir:
        name = "city" if path == "/city" else "recycle"
        page.screenshot(path=str(Path(screenshot_dir) / f"brand-{name}-{language}-{width}.png"))


@pytest.mark.parametrize("width", [360, 390, 1280])
def test_route_first_layout_keyboard_and_general_guidance(page, web_url, width):
    page.set_viewport_size({"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(web_url)
    expect(page.locator("#ai-help")).not_to_have_attribute("open", "")
    expect(page.locator("#classify-form")).to_be_hidden()
    expect(page.locator("#discovery-controls")).not_to_have_attribute("open", "")
    expect(page.locator(".waste-card")).to_have_count(6)
    expect(page.get_by_role("heading", level=1)).to_have_text("Recycling routes")
    expect(page.locator("#basket-count")).to_be_empty()
    expect(page.locator("#origin-status")).to_be_empty()
    expect(page.locator("#trip-status")).to_be_empty()
    expect(page.locator("#map-status")).to_be_empty()
    expect(page.locator("#site-count")).to_be_hidden()
    expect(page.locator(".waste-card > span:not(.selection-mark)")).to_have_count(0)
    expect(
        page.locator("#ai-help small, #map-legend small, .section-heading .small-note")
    ).to_have_count(0)
    expect(page.locator("#sharing-note")).to_be_visible()
    if width > 760:
        left = page.locator(".choose-column").bounding_box()
        right = page.locator("#trip-panel").bounding_box()
        assert abs(left["y"] - right["y"]) < 1
        assert abs(left["height"] - right["height"]) < 1
        left_heading = page.locator("#picker-heading").bounding_box()
        right_heading = page.locator("#trip-heading").bounding_box()
        assert abs(left_heading["y"] - right_heading["y"]) < 1
    assert page.evaluate("""() => {
      return [...document.querySelectorAll('.selection-mark, .brand-mark')].every(el => {
        const circle = el.getBoundingClientRect();
        const icon = el.querySelector('svg').getBoundingClientRect();
        return Math.abs(circle.x + circle.width / 2 - icon.x - icon.width / 2) < 0.6
          && Math.abs(circle.y + circle.height / 2 - icon.y - icon.height / 2) < 0.6;
      });
    }""")
    # Every ID is unique: disclosures must not duplicate live controls/statuses.
    assert page.evaluate("""() => {
      const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
      return ids.length === new Set(ids).size;
    }""")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    screenshot_dir = os.getenv("SRA_LAYOUT_SCREENSHOTS")
    if screenshot_dir:
        page.screenshot(path=str(Path(screenshot_dir) / f"route-first-{width}.png"), full_page=True)
    glass = page.get_by_role("button", name="Glass bottles and jars")
    glass.focus()
    glass.press("Space")
    expect(glass).to_have_attribute("aria-pressed", "true")
    expect(glass.locator(".mark-check")).to_be_visible()
    expect(glass.locator(".mark-plus")).to_be_hidden()
    expect(page.locator("#picker-condition")).to_contain_text("No hazardous contents")
    expect(page.locator("#trip-items li")).to_have_count(0)
    glass.press("Space")
    expect(page.locator("#confirm-picks")).to_be_hidden()
    page.locator("#general-help").click()
    expect(page.locator("#general-note")).to_have_count(0)
    expect(page.locator("#general-help")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#general-help .mark-check")).to_be_visible()
    expect(page.locator("#trip-items li")).to_have_count(0)
    page.locator("#ai-help summary").click()
    page.get_by_label("Item", exact=True).fill("old battery")
    page.get_by_role("button", name="Check", exact=True).click()
    expect(page.locator("#contact")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors


def test_stream_cards_select_directly_and_sync_with_basket(page, web_url):
    requests = []
    page.on("request", lambda req: requests.append(req) if req.method == "POST" else None)
    page.goto(web_url)
    glass = page.get_by_role("button", name="Glass bottles and jars")
    plastic = page.get_by_role("button", name="Plastic bottles and cans")
    paper = page.get_by_role("button", name="Paper and cartons")
    for card in (glass, plastic, paper):
        card.click()
        expect(card).to_have_attribute("aria-pressed", "true")
        expect(card.locator(".mark-check")).to_be_visible()
    expect(page.locator("#plastic-options, #paper-options")).to_have_count(0)
    page.locator("#confirm-picks").click()
    expect(page.locator("#trip-items li")).to_have_count(3)
    assert requests == []  # Known streams need no classification/AI request.
    expect(page.locator("#trip-items")).to_contain_text("Plastic bottles & cans")
    expect(page.locator("#trip-items")).to_contain_text("Paper, cardboard & cartons")
    page.get_by_role("button", name="Remove item 1", exact=True).click()
    expect(glass).to_have_attribute("aria-pressed", "false")
    plastic.click()
    paper.click()
    expect(page.locator("#trip-items li")).to_have_count(0)
    add_trip_item(page)
    expect(glass).to_have_attribute("aria-pressed", "true")
    page.get_by_role("link", name="Edit waste types", exact=True).click()
    expect(page.locator("#waste-picker")).to_be_focused()


def test_stream_selection_preserves_pending_choices_when_basket_full(page, web_url):
    page.goto(web_url)
    for index in range(6):
        add_trip_item(page, f"jar {index}")
    paper = page.get_by_role("button", name="Paper and cartons")
    paper.click()
    page.locator("#confirm-picks").click()
    expect(page.locator("#picker-status")).to_contain_text("six items")
    expect(page.locator("#trip-items li")).to_have_count(6)
    expect(paper).to_have_attribute("aria-pressed", "true")
    page.get_by_role("button", name="Remove item 1", exact=True).click()
    page.locator("#confirm-picks").click()
    expect(page.locator("#picker-status")).to_be_empty()
    expect(page.locator("#trip-items li")).to_have_count(6)
    expect(page.locator("#trip-items li").last).to_contain_text("Paper, cardboard & cartons")


def test_pending_quick_picks_cannot_be_silently_left_out_of_route(page, web_url):
    prepare_trip(page, web_url)
    expect(page.locator("#plan-trip")).to_be_enabled()
    page.get_by_role("button", name="Plastic bottles and cans").click()
    expect(page.locator("#plan-trip")).to_be_disabled()
    expect(page.locator("#trip-status")).to_contain_text("selected items")
    page.locator("#confirm-picks").click()
    expect(page.locator("#trip-items li")).to_have_count(2)
    expect(page.locator("#plan-trip")).to_be_enabled()


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
def test_expanded_panels_share_layout_without_overflow(page, web_url, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.route("**/api/v1/trips", lambda route: route.fulfill(json=trip_fixture("walking")))
    prepare_trip(page, web_url)
    page.get_by_role("button", name="Find my route", exact=True).click()
    expect(page.locator("#trip-result")).to_be_visible()
    expect(page.locator("#map-heading")).to_have_text("Route & stops")
    route_key = page.locator("#route-map-key").bounding_box()
    zoom = page.locator(".leaflet-control-zoom").bounding_box()
    assert route_key["x"] + route_key["width"] < zoom["x"]
    page.get_by_role("button", name="Show other collection points", exact=True).click()
    page.get_by_label("Search name, address or municipality").fill("Centar")
    page.locator("#site-list button").first.click()
    expect(page.locator("#site-details")).to_be_visible()
    expect(page.locator("#site-details")).to_contain_text("Operating status: unknown")
    expect(page.locator("#site-details details").first).not_to_have_attribute("open", "")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    if width > 1000:
        trip = page.locator("#trip-result").bounding_box()
        site = page.locator("#site-details").bounding_box()
        assert abs(trip["y"] - site["y"]) < 1
    screenshots = os.getenv("SRA_LAYOUT_SCREENSHOTS")
    if screenshots:
        page.locator("#collection-points").screenshot(
            path=str(Path(screenshots) / f"expanded-map-{width}.png")
        )


@pytest.mark.parametrize("width", [320, 360, 390, 768, 1280])
@pytest.mark.parametrize("font", ["system", "Verdana"])
def test_map_close_start_overlay_controls_and_individual_sites(page, web_url, width, font):
    if font != "system":
        page.add_init_script(
            "document.addEventListener('DOMContentLoaded', "
            "() => document.body.style.fontFamily = 'Verdana, sans-serif')"
        )
    page.set_viewport_size({"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(web_url)
    expect(page.locator("#site-map")).to_have_attribute("data-zoom", "16")
    expect(page.locator("#map-view-count")).to_contain_text("in view")
    expect(page.locator("#map-shell #map-legend")).to_be_visible()
    page.locator("#map-shell").scroll_into_view_if_needed()
    shell = page.locator("#map-shell").bounding_box()
    for selector in ["#map-legend", ".map-context", ".map-view-tools", ".leaflet-control-zoom"]:
        box = page.locator(selector).bounding_box()
        assert box["x"] >= shell["x"]
        assert box["y"] >= shell["y"]
        assert box["x"] + box["width"] <= shell["x"] + shell["width"]
        assert box["y"] + box["height"] <= shell["y"] + shell["height"]
    legend = page.locator("#map-legend").bounding_box()
    zoom = page.locator(".leaflet-control-zoom").bounding_box()
    assert legend["x"] + legend["width"] < zoom["x"]
    context = page.locator(".map-context").bounding_box()
    buttons = page.locator(".map-view-tools").bounding_box()
    assert context["x"] + context["width"] < buttons["x"]
    screenshots = os.getenv("SRA_LAYOUT_SCREENSHOTS")
    if screenshots:
        page.locator("#map-shell").screenshot(path=str(Path(screenshots) / f"map-{width}.png"))
    page.get_by_role("button", name="Show all matching sites", exact=True).click()
    overview_zoom = int(page.locator("#site-map").get_attribute("data-zoom"))
    assert overview_zoom < 16
    expect(page.locator(".site-cluster")).to_have_count(0)
    expect(page.locator("#map-legend")).not_to_contain_text("Grouped")
    expect(page.locator("#map-legend small")).to_have_count(0)
    expect(page.locator("#site-map canvas")).to_have_count(1)
    page.get_by_role("button", name="Recenter map", exact=True).click()
    expect(page.locator("#site-map")).to_have_attribute("data-zoom", "16")
    page.get_by_role("button", name="Choose on map", exact=True).click()
    expect(page.locator("#map-legend")).to_be_hidden()
    expect(page.locator("#map-pick-hint")).to_be_visible()
    # Map overlays must not accidentally set a location when clicked.
    page.get_by_role("button", name="Recenter map", exact=True).click()
    expect(page.locator("#latitude")).to_have_value("")
    expect(page.locator("#map-pick-hint")).to_be_visible()
    page.get_by_role("button", name="Cancel selection", exact=True).click()
    expect(page.locator("#map-legend")).to_be_visible()
    expect(page.get_by_role("button", name="Show all matching sites", exact=True)).to_be_enabled()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors


@pytest.mark.parametrize(
    "description,reason",
    [("glass jar", "The jar is dirty."), ("стаклено шише", "валкано")],
)
def test_photo_conflict_clears_previous_confirmation(page, web_url, tmp_path, description, reason):
    from smart_recycling.vision import ModelPhotoItem, VisionService

    suggestion = VisionService._suggestion(
        ModelPhotoItem(
            description=description,
            reason=reason,
            item_kind="empty_glass_packaging",
            visible_condition="appears_empty_clean",
        )
    )
    assert suggestion.status == "needs_review"
    photo = tmp_path / "item.png"
    Image.new("RGB", (80, 60), "green").save(photo)
    page.route(
        "**/api/v1/photo-suggestions",
        lambda route: route.fulfill(
            json={
                "items": [suggestion.model_dump(mode="json")],
                "message": "Review every suggestion before adding it to your trip.",
            }
        ),
    )
    requests = []
    page.on(
        "request",
        lambda request: requests.append(request.url) if "/api/v1/classify" in request.url else None,
    )
    page.goto(web_url)
    open_ai(page)
    page.locator("#item").fill("phone")
    page.locator('#classify-form button[type="submit"]').click()
    expect(page.locator("#manual-form")).to_be_visible()
    expect(page.locator("#contact")).to_be_visible()
    assert len(requests) == 1
    page.get_by_label("Photo", exact=True).set_input_files(photo)
    page.get_by_role("button", name="Suggest from photo", exact=True).click()
    page.get_by_role("button", name="Describe manually", exact=True).click()
    expect(page.locator("#item")).to_have_value(description)
    expect(page.locator("#item")).to_be_focused()
    expect(page.locator("#manual-form")).to_be_hidden()
    expect(page.locator("#item-kind option")).to_have_count(0)
    expect(page.locator("#contact")).to_be_hidden()
    expect(page.locator("#phone")).to_be_hidden()
    expect(page.locator("#trip-items li")).to_have_count(0)
    assert len(requests) == 1
