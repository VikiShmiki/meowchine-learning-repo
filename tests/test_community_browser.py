"""Real-page community journeys with local data and simulated routing providers."""

import os

import pytest
from playwright.sync_api import expect
from test_web_browser import ROOT, open_discovery
from test_web_browser import browser as browser_fixture
from test_web_browser import page as page_fixture
from test_web_browser import web_url as web_url_fixture

browser = browser_fixture
page = page_fixture
web_url = web_url_fixture
pytestmark = [
    pytest.mark.skipif(os.getenv("SRA_BROWSER_TESTS") != "1", reason="Opt-in browser tests"),
    pytest.mark.parametrize("web_url", ["system_server:app"], indirect=True),
]
REVIEW_KEY = "browser-test-reviewer-" + "x" * 32


@pytest.mark.parametrize("width", [360, 1280])
@pytest.mark.parametrize("mode", ["Walking", "Driving"])
def test_report_container_recalculates_without_losing_items(page, web_url, width, mode):
    page.request.post(web_url + "/__test/reset-routing-budget")
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(web_url)
    page.get_by_role("button", name="Glass bottles and jars", exact=True).click()
    page.locator("#confirm-picks").click()
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("41.9965")
    page.get_by_label("Longitude", exact=True).fill("21.4314")
    page.get_by_role("button", name="Set coordinates", exact=True).click()
    page.get_by_label(mode, exact=True).check()
    with page.expect_response("**/api/v1/trips") as first_response:
        page.get_by_role("button", name="Find my route", exact=True).click()
    first = first_response.value.json()
    expect(page.locator("#trip-result")).to_be_visible()
    page.locator("#trip-stop-1 .container-condition summary").click()
    row = page.locator("#trip-stop-1 .condition-row").first
    expect(row.locator("select")).to_be_visible()
    assert row.locator("select").bounding_box()["width"] >= 140
    row.locator("select").select_option("full")
    row.get_by_role("button", name="Report condition", exact=True).click()
    expect(row.get_by_role("status")).to_have_text(
        "Reported full · excluded from everyone's routes for up to 12 hours."
    )
    expect(page.locator("#route-condition-notice")).to_be_visible()
    expect(page.locator("#request-route-update")).to_be_hidden()
    expect(page.locator("#trip-items li")).to_have_count(1)
    if os.getenv("SRA_LAYOUT_SCREENSHOTS"):
        page.locator("#trip-result").screenshot(
            path=str(ROOT / "artifacts" / f"demo-container-report-{width}-{mode}.png")
        )
    with page.expect_response("**/api/v1/trips") as second_response:
        page.get_by_role("button", name="Use existing start", exact=True).click()
    second = second_response.value.json()
    assert first["stops"][0]["asset_ids"][0] not in {
        asset for stop in second["stops"] for asset in stop["asset_ids"]
    }
    assert first["mode"] == second["mode"] == mode.lower()
    expect(page.locator("#trip-items li")).to_have_count(1)
    expect(page.locator("#route-condition-notice")).to_be_hidden()
    page.get_by_role("button", name="Update route", exact=True).click()
    page.get_by_role("button", name="Choose current position", exact=True).click()
    expect(page.locator("#origin-editor")).to_be_visible()
    expect(page.locator("#plan-trip")).to_be_disabled()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if os.getenv("SRA_LAYOUT_SCREENSHOTS"):
        page.screenshot(
            path=str(ROOT / "artifacts" / f"community-route-{width}-{mode}.png"), full_page=True
        )


@pytest.mark.parametrize("width", [360, 1280])
def test_dumping_submit_private_then_review_and_publish(page, web_url, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(web_url + "/city")
    expect(page.locator("#dumping-map")).to_be_visible()
    expect(page.locator("#dumping-panel summary")).to_have_count(0)
    assert page.locator("#dumping-panel").evaluate(
        "panel => Boolean(panel.compareDocumentPosition(document.querySelector('.city-method'))"
        " & Node.DOCUMENT_POSITION_FOLLOWING)"
    )
    toggle = page.get_by_label("Show reviewed reports").bounding_box()
    assert toggle["width"] <= 20 and toggle["height"] <= 20
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if width == 360:
        page.locator("#dumping-map").click(position={"x": 140, "y": 150})
        expect(page.locator("#dumping-map .leaflet-marker-icon")).to_have_count(1)
        assert 41.8 <= float(page.get_by_label("Dumping latitude").input_value()) <= 42.2
        assert 21.2 <= float(page.get_by_label("Dumping longitude").input_value()) <= 21.7
    else:
        page.get_by_label("Dumping latitude", exact=True).fill("41.998")
        page.get_by_label("Dumping longitude", exact=True).fill("21.43")
    description = f"Test dumping report at {width}px"
    page.get_by_label("Description", exact=True).fill(description)
    page.get_by_label("Photo (optional)", exact=True).set_input_files(
        ROOT / "tests/fixtures/pipeline/images" / "glass.png"
    )
    if os.getenv("SRA_LAYOUT_SCREENSHOTS"):
        page.locator("#dumping-panel").screenshot(
            path=str(ROOT / "artifacts" / f"demo-dumping-{width}.png")
        )
    with page.expect_response("**/api/v1/dumping-reports") as submitted:
        page.get_by_role("button", name="Submit report", exact=True).click()
    report = submitted.value.json()
    expect(page.locator(".dumping-form [role=status]")).to_have_text(
        "Report saved · awaiting review"
    )
    public = page.request.get(web_url + "/api/v1/dumping-reports").json()["reports"]
    assert report["id"] not in {row["id"] for row in public}
    page.goto(web_url + "/review")
    page.get_by_label("Reviewer key").fill(REVIEW_KEY)
    page.get_by_role("button", name="Unlock", exact=True).click()
    card = page.locator(".review-card").filter(has=page.get_by_text(description, exact=True))
    expect(card).to_be_visible()
    card.get_by_role("button", name="View private photo", exact=True).click()
    expect(card.locator("img")).to_be_visible()
    card.get_by_role("button", name="Approve", exact=True).click()
    expect(card.get_by_role("button", name="Approve", exact=True)).to_be_disabled()
    page.get_by_role("button", name="Lock", exact=True).click()
    expect(page.locator("#review-reports")).to_be_empty()
    page.goto(web_url + "/city")
    expect(page.locator("#dumping-map")).to_be_visible()
    expect(page.locator("#dumping-map .leaflet-interactive")).not_to_have_count(0)
    assert report["id"] in {
        row["id"] for row in page.request.get(web_url + "/api/v1/dumping-reports").json()["reports"]
    }


def test_map_details_exposes_per_container_reporting(page, web_url):
    page.goto(web_url)
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill("Kopche")
    page.locator("#site-list button").click()
    page.locator("#site-details .container-condition summary").click()
    expect(page.locator("#site-details .condition-row .condition-badge")).to_have_text("Unknown")
    expect(page.locator("#site-details .condition-form button")).to_be_visible()


def test_dumping_network_failure_preserves_form(page, web_url):
    page.route("**/api/v1/dumping-reports", lambda route: route.abort())
    page.goto(web_url + "/city")
    expect(page.locator("#dumping-map")).to_be_visible()
    page.get_by_label("Dumping latitude").fill("41.998")
    page.get_by_label("Dumping longitude").fill("21.43")
    page.get_by_label("Description", exact=True).fill("Bags by the road")
    page.get_by_role("button", name="Submit report", exact=True).click()
    expect(page.get_by_role("button", name="Submit report", exact=True)).to_be_enabled()
    expect(page.get_by_label("Description", exact=True)).to_have_value("Bags by the road")
    expect(page.locator(".dumping-form [role=status]")).not_to_be_empty()


def test_dumping_is_only_on_city_and_container_reporting_stays_on_recycle(page, web_url):
    page.goto(web_url)
    expect(page.locator("#waste-picker")).to_be_visible()
    expect(page.locator("#dumping-panel")).to_have_count(0)
    expect(page.locator('script[src*="dumping.js"]')).to_have_count(0)
    open_discovery(page)
    page.get_by_label("Search name, address or municipality").fill("Kopche")
    page.locator("#site-list button").click()
    expect(page.locator("#site-details .container-condition")).to_be_visible()
    page.get_by_role("navigation", name="Application").get_by_role(
        "link", name="City coverage"
    ).click()
    expect(page.locator("#dumping-panel")).to_have_count(1)
    page.get_by_role("navigation", name="Application").get_by_role(
        "link", name="Recycle", exact=True
    ).click()
    expect(page.locator("#dumping-panel")).to_have_count(0)


def test_completed_stop_clears_finished_basket(page, web_url):
    page.request.post(web_url + "/__test/reset-routing-budget")
    page.goto(web_url)
    page.get_by_role("button", name="Glass bottles and jars", exact=True).click()
    page.locator("#confirm-picks").click()
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("41.9965")
    page.get_by_label("Longitude", exact=True).fill("21.4314")
    page.get_by_role("button", name="Set coordinates", exact=True).click()
    page.get_by_role("button", name="Find my route", exact=True).click()
    page.get_by_role("button", name="Dropped these off", exact=True).click()
    expect(page.locator("#trip-items li")).to_have_count(0)
    expect(page.locator("#trip-result")).to_be_hidden()
    expect(page.locator("#plan-trip")).to_be_disabled()
    expect(page.locator("#trip-status")).to_have_text("All items marked dropped off.")
