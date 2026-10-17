"""Trip completion and optional container observations on the real bilingual page."""

import os

import pytest
from playwright.sync_api import expect
from test_accounts_browser import route
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


@pytest.fixture(autouse=True)
def isolated_reports(page, web_url):
    page.request.post(web_url + "/__test/reset-community")


def reports(page, web_url):
    return page.request.get(
        web_url + "/api/v1/review/reports",
        headers={"Authorization": "Bearer browser-test-reviewer-" + "x" * 32},
    ).json()["reports"]


@pytest.mark.parametrize("width", [320, 360, 1280])
@pytest.mark.parametrize("mode", ["Walking", "Driving"])
def test_final_dropoff_ends_trip_and_optional_checkin_full_changes_other_routes(
    page, web_url, width, mode
):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(web_url)
    with page.expect_response("**/api/v1/trips") as planned:
        route(page, web_url, mode=mode)
    original = planned.value.json()
    asset_ids = original["stops"][0]["asset_ids"]
    page.get_by_role("button", name="Dropped these off", exact=True).click()
    panel = page.locator("#trip-checkin")
    expect(panel).to_be_visible()
    expect(page.locator("#trip-result")).to_be_hidden()
    expect(page.locator("#route-controls")).to_be_hidden()
    expect(page.locator("#trip-completion")).to_be_hidden()
    expect(page.locator("#trip-items li")).to_have_count(0)
    expect(panel.locator(".condition-row")).to_have_count(len(asset_ids))
    row = panel.locator(".condition-row").first
    expect(row.locator("select")).to_have_value("")
    expect(row.get_by_role("button", name="Send report")).to_be_disabled()
    assert reports(page, web_url) == []
    row.locator("select").select_option("full")
    row.get_by_role("button", name="Send report").click()
    expect(row.get_by_role("status")).to_contain_text("excluded from everyone's routes")
    expect(row.get_by_role("button", name="Report sent")).to_be_disabled()
    assert len(reports(page, web_url)) == 1
    reported = row.get_attribute("data-asset-id")
    # A second browser visitor is affected without approval or an account.
    stranger = page.context.browser.new_context()
    try:
        statuses = stranger.request.get(web_url + "/api/v1/container-statuses").json()
        assert statuses["statuses"][reported]["source"] == "community_report"
        alternative = stranger.request.post(
            web_url + "/api/v1/trips",
            data={
                "origin": {"latitude": 41.9965, "longitude": 21.4314},
                "mode": mode.lower(),
                "items": [{"material": "glass", "condition_confirmed": True}],
                "share_coordinates": True,
            },
        )
        assert alternative.ok, alternative.text()
        assert reported not in {
            asset for stop in alternative.json()["stops"] for asset in stop["asset_ids"]
        }
    finally:
        stranger.close()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if os.getenv("SRA_CHECKIN_SCREENSHOTS"):
        panel.screenshot(
            path=os.path.join(os.environ["SRA_CHECKIN_SCREENSHOTS"], f"checkin-{width}-{mode}.png")
        )
    panel.get_by_role("button", name="Done / skip remaining").click()
    expect(panel).to_be_hidden()
    assert len(reports(page, web_url)) == 1


def test_end_without_visits_keeps_items_and_does_not_send_reports(page, web_url):
    page.goto(web_url)
    route(page, web_url)
    page.get_by_role("button", name="Finish trip", exact=True).click()
    expect(page.locator("#trip-checkin")).to_contain_text("No stops were marked visited")
    expect(page.locator("#trip-items li")).to_have_count(1)
    expect(page.locator("#route-controls")).to_be_hidden()
    assert not reports(page, web_url)


def test_visited_without_dropoff_checkin_retry_preserves_choice_and_remaining_items(page, web_url):
    page.goto(web_url)
    route(page, web_url)
    page.get_by_label("I visited this stop").check()
    page.get_by_role("button", name="Finish trip", exact=True).click()
    expect(page.locator("#trip-items li")).to_have_count(1)
    panel = page.locator("#trip-checkin")
    row = panel.locator(".condition-row").first
    row.locator("select").select_option("full")
    page.route("**/api/v1/container-reports", lambda interception: interception.abort())
    row.get_by_role("button", name="Send report").click()
    expect(row.get_by_role("status")).to_contain_text("Your choice is kept")
    expect(row.locator("select")).to_have_value("full")
    expect(row.get_by_role("button", name="Send report")).to_be_enabled()
    assert not reports(page, web_url)
    page.unroute("**/api/v1/container-reports")
    row.get_by_role("button", name="Send report").click()
    expect(row.get_by_role("status")).to_contain_text("Reported full")
    assert len(reports(page, web_url)) == 1


def test_checkin_skip_and_catalog_retry_do_not_invent_observations(page, web_url):
    page.goto(web_url)
    route(page, web_url)
    page.route("**/api/v1/sites?scope=citizen", lambda interception: interception.abort())
    page.get_by_role("button", name="Dropped these off", exact=True).click()
    panel = page.locator("#trip-checkin")
    expect(panel).to_contain_text("Could not load containers")
    page.unroute("**/api/v1/sites?scope=citizen")
    panel.get_by_role("button", name="Retry", exact=True).click()
    expect(panel.locator(".condition-row")).not_to_have_count(0)
    panel.get_by_role("button", name="Done / skip remaining").click()
    assert not reports(page, web_url)


def test_macedonian_checkin_preserves_choice_when_switching_languages(page, web_url):
    page.goto(web_url)
    route(page, web_url)
    page.get_by_role("button", name="Dropped these off", exact=True).click()
    panel = page.locator("#trip-checkin")
    row = panel.locator(".condition-row").first
    row.locator("select").select_option("full")
    page.locator(".language-switch").select_option("mk")
    expect(panel.locator("h2")).to_have_text("Патувањето заврши")
    expect(row.locator("select")).to_have_value("full")
    row.get_by_role("button", name="Испрати пријава", exact=True).click()
    expect(row.get_by_role("status")).to_contain_text("исклучен од рутите")
    page.locator(".language-switch").select_option("en")
    expect(row.get_by_role("status")).to_contain_text("Reported full")
    assert len(reports(page, web_url)) == 1


def test_multi_stop_completion_keeps_route_and_checkin_contains_only_visited_assets(page, web_url):
    page.goto(web_url)
    route(page, web_url)
    # Add a second material whose collection site differs from the glass stop.
    page.get_by_role("button", name="Clothes for donation", exact=True).click()
    page.locator("#confirm-picks").click()
    with page.expect_response("**/api/v1/trips") as planned:
        page.get_by_role("button", name="Find my route", exact=True).click()
    trip = planned.value.json()
    assert len(trip["stops"]) == 2
    first = page.locator("#trip-stop-1")
    first.get_by_role("button", name="Dropped these off", exact=True).click()
    expect(first).to_have_attribute("data-completed", "true")
    expect(page.locator("#trip-result")).to_be_visible()
    expect(page.locator("#trip-items li")).to_have_count(1)
    expect(page.locator("#trip-checkin")).to_be_hidden()
    page.get_by_role("button", name="Finish trip", exact=True).click()
    rows = page.locator("#trip-checkin .condition-row")
    expect(rows).to_have_count(len(trip["stops"][0]["asset_ids"]))
    assert set(rows.evaluate_all("rows => rows.map(row => row.dataset.assetId)")) == set(
        trip["stops"][0]["asset_ids"]
    )
    assert not reports(page, web_url)


def test_visited_containers_survive_replanning_are_deduplicated_and_reset_after_finish(
    page, web_url
):
    page.goto(web_url)
    route(page, web_url)
    page.get_by_label("I visited this stop").check()
    page.get_by_role("button", name="Update route", exact=True).click()
    page.get_by_role("button", name="Use existing start", exact=True).click()
    expect(page.get_by_label("I visited this stop")).to_be_checked()
    page.get_by_role("button", name="Finish trip", exact=True).click()
    rows = page.locator("#trip-checkin .condition-row")
    expect(rows).not_to_have_count(0)
    ids = rows.evaluate_all("rows => rows.map(row => row.dataset.assetId)")
    assert len(ids) == len(set(ids))
    page.get_by_role("button", name="Done / skip remaining", exact=True).click()
    page.get_by_role("button", name="Find my route", exact=True).click()
    expect(page.get_by_label("I visited this stop")).not_to_be_checked()
    page.get_by_role("button", name="Finish trip", exact=True).click()
    expect(page.locator("#trip-checkin")).to_contain_text("No stops were marked visited")
    assert not reports(page, web_url)


def test_older_status_read_and_failed_refresh_do_not_undo_a_successful_full_report(page, web_url):
    page.goto(web_url)
    route(page, web_url)
    page.get_by_role("button", name="Report a problem", exact=True).click()
    row = page.locator("#trip-stop-1 .condition-row").first
    expect(row.locator("select")).to_be_visible()
    held = []

    def old_read(interception):
        if not held:
            held.append(interception)
        else:
            interception.abort()

    page.route("**/api/v1/container-statuses", old_read)
    with page.expect_request("**/api/v1/container-statuses"):
        page.evaluate("() => { CommunityUI.refresh().catch(() => {}); }")
    row.locator("select").select_option("full")
    row.get_by_role("button", name="Report condition").click()
    expect(row.get_by_role("status")).to_contain_text("Reported full")
    held[0].fulfill(json={"statuses": {}, "version": "older-read"})
    expect(row.locator("form")).to_have_attribute("aria-busy", "false")
    expect(row.locator(".condition-badge")).to_have_text("Full")
    expect(row.get_by_role("button", name="Report sent")).to_be_disabled()
    expect(page.locator("#route-condition-notice")).to_be_visible()
    assert len(reports(page, web_url)) == 1
