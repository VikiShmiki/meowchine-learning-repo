"""Compact stop cards and optional per-container observations on the real page."""

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
def test_dropoff_popup_full_changes_other_routes(page, web_url, width, mode):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(web_url)
    with page.expect_response("**/api/v1/trips") as planned:
        route(page, web_url, mode=mode)
    stop = planned.value.json()["stops"][0]
    card = page.locator("#trip-stop-1")
    expect(card.locator(".stop-card-number")).to_have_text("1")
    expect(card.locator(".stop-actions button")).to_have_count(2)
    expect(card).not_to_contain_text("Unknown")
    assert card.evaluate(
        "el => el.style.getPropertyValue('--stop-fill') === "
        "SiteData.stopAppearance(['glass']).background"
    )
    card.get_by_role("button", name="Dropped off", exact=True).click()
    popup = page.locator("#stop-report-dialog")
    expect(popup).to_be_visible()
    expect(popup.locator("h2")).to_have_text("Still space here?")
    expect(popup.locator(".stop-report-choices button")).to_have_count(2)
    expect(popup.get_by_role("button", name="Still space", exact=True)).to_be_focused()
    expect(page.locator("#trip-result")).to_be_hidden()
    expect(page.locator("#trip-items li")).to_have_count(0)
    assert reports(page, web_url) == []
    row = popup.locator(".stop-report-container")
    reported = row.get_attribute("data-asset-id")
    assert reported in stop["asset_ids"]
    with page.expect_response("**/api/v1/container-reports"):
        popup.get_by_role("button", name="Full", exact=True).click()
    if len(stop["asset_ids"]) > 1:
        expect(row).not_to_have_attribute("data-asset-id", reported)
        popup.get_by_role("button", name="Skip", exact=True).click()
    expect(popup).to_have_count(0)
    assert len(reports(page, web_url)) == 1
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
    expect(page.locator("#checkin-heading")).to_be_focused()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(page.locator("#trip-checkin select")).to_have_count(0)


@pytest.mark.parametrize("dismiss", ["Skip", "Escape"])
def test_dismiss_popup_never_reports_and_end_early_keeps_items(page, web_url, dismiss):
    page.goto(web_url)
    route(page, web_url)
    button = page.get_by_role("button", name="Report a problem", exact=True)
    button.click()
    popup = page.locator("#stop-report-dialog")
    expect(popup).to_be_visible()
    if dismiss == "Escape":
        page.keyboard.press("Escape")
    else:
        popup.get_by_role("button", name="Skip", exact=True).click()
    expect(popup).to_have_count(0)
    expect(button).to_be_focused()
    page.get_by_role("button", name="Finish trip", exact=True).click()
    expect(page.locator("#trip-checkin")).to_contain_text("Trip finished")
    expect(page.locator("#trip-items li")).to_have_count(1)
    expect(page.locator("#trip-checkin select")).to_have_count(0)
    assert not reports(page, web_url)


def test_problem_retry_preserves_container_and_basket(page, web_url):
    page.goto(web_url)
    route(page, web_url)
    page.get_by_role("button", name="Report a problem", exact=True).click()
    popup = page.locator("#stop-report-dialog")
    row = popup.locator(".stop-report-container")
    expect(popup.get_by_role("button", name="Blocked", exact=True)).to_be_visible()
    asset = row.get_attribute("data-asset-id")
    page.route("**/api/v1/container-reports", lambda interception: interception.abort())
    popup.get_by_role("button", name="Full", exact=True).click()
    expect(popup.get_by_role("status")).to_have_text("Could not send. Try again.")
    expect(row).to_have_attribute("data-asset-id", asset)
    expect(popup.get_by_role("button", name="Full", exact=True)).to_be_enabled()
    expect(page.locator("#trip-items li")).to_have_count(1)
    assert not reports(page, web_url)
    page.unroute("**/api/v1/container-reports")
    with page.expect_response("**/api/v1/container-reports"):
        popup.get_by_role("button", name="Full", exact=True).click()
    expect(page.locator("#route-condition-notice")).to_be_visible()
    assert len(reports(page, web_url)) == 1


def test_catalog_retry_and_macedonian_positive_report(page, web_url):
    page.goto(web_url)
    route(page, web_url)
    page.route("**/api/v1/sites?scope=citizen", lambda interception: interception.abort())
    page.get_by_role("button", name="Dropped off", exact=True).click()
    popup = page.locator("#stop-report-dialog")
    expect(popup).to_contain_text("Could not load containers.")
    page.unroute("**/api/v1/sites?scope=citizen")
    popup.get_by_role("button", name="Retry", exact=True).click()
    expect(popup.get_by_role("button", name="Still space", exact=True)).to_be_visible()
    page.evaluate("() => NajdiFrliI18n.setLanguage('mk')")
    expect(popup.locator("h2")).to_have_text("Има уште место?")
    with page.expect_response("**/api/v1/container-reports") as response:
        popup.get_by_role("button", name="Има место", exact=True).click()
    assert response.value.request.post_data_json["condition"] == "available"
    assert len(reports(page, web_url)) == 1
    # A positive observation remains unreviewed; no automatic public clearance.
    assert not page.request.get(web_url + "/api/v1/container-statuses").json()["statuses"]


def test_multi_stop_cards_keep_numbers_colors_and_no_second_questionnaire(page, web_url):
    page.goto(web_url)
    route(page, web_url)
    page.get_by_role("button", name="Clothes for donation", exact=True).click()
    page.locator("#confirm-picks").click()
    with page.expect_response("**/api/v1/trips") as planned:
        page.get_by_role("button", name="Find my route", exact=True).click()
    trip = planned.value.json()
    assert len(trip["stops"]) == 2
    for number, stop in enumerate(trip["stops"], 1):
        card = page.locator(f"#trip-stop-{number}")
        expect(card.locator(".stop-card-number")).to_have_text(str(number))
        assert card.evaluate(
            "(el, kinds) => el.style.getPropertyValue('--stop-fill') === "
            "SiteData.stopAppearance(kinds).background",
            stop["item_kinds"],
        )
    first = page.locator("#trip-stop-1")
    first.get_by_role("button", name="Dropped off", exact=True).click()
    expect(first).to_have_attribute("data-completed", "true")
    expect(page.locator("#trip-result")).to_be_visible()
    expect(page.locator("#trip-items li")).to_have_count(1)
    popup = page.locator("#stop-report-dialog")
    expect(popup.locator(".stop-card-number")).to_have_text("1")
    popup.get_by_role("button", name="Skip", exact=True).click()
    page.get_by_role("button", name="Finish trip", exact=True).click()
    expect(page.locator("#trip-checkin")).to_contain_text("Trip finished")
    expect(page.locator("#trip-checkin .condition-row")).to_have_count(0)
    assert not reports(page, web_url)


def test_older_status_read_and_failed_refresh_keep_successful_full_report(page, web_url):
    page.goto(web_url)
    route(page, web_url)
    page.get_by_role("button", name="Report a problem", exact=True).click()
    popup = page.locator("#stop-report-dialog")
    expect(popup.get_by_role("button", name="Full", exact=True)).to_be_visible()
    held = []

    def old_read(interception):
        if not held:
            held.append(interception)
        else:
            interception.abort()

    page.route("**/api/v1/container-statuses", old_read)
    with page.expect_request("**/api/v1/container-statuses"):
        page.evaluate("() => { CommunityUI.refresh().catch(() => {}); }")
    with page.expect_response("**/api/v1/container-reports"):
        popup.get_by_role("button", name="Full", exact=True).click()
    held[0].fulfill(json={"statuses": {}, "version": "older-read"})
    expect(page.locator("#route-condition-notice")).to_be_visible()
    assert len(reports(page, web_url)) == 1


def test_multiple_containers_report_only_explicit_choices_once(page, web_url):
    page.goto(web_url)
    page.route(
        "**/api/v1/sites?scope=citizen",
        lambda interception: interception.fulfill(
            json={
                "sites": [
                    {
                        "assets": [
                            {
                                "id": "first",
                                "name": "Paper container",
                                "address": "First location",
                                "source_materials": ["paper"],
                            },
                            {
                                "id": "second",
                                "name": "Glass container",
                                "address": "Second location",
                                "source_materials": ["glass"],
                            },
                        ]
                    }
                ]
            }
        ),
    )
    requests = []
    page.route("**/api/v1/container-reports", lambda interception: requests.append(interception))
    page.evaluate("""() => CommunityUI.reportStop(['first', 'second', 'first'], {
        number: 2, appearance: SiteData.stopAppearance(['paper_tetrapak', 'glass'])
    })""")
    popup = page.locator("#stop-report-dialog")
    expect(popup).to_contain_text("Paper container")
    expect(popup.locator(".stop-report-progress")).to_have_text("1 / 2")
    with page.expect_request("**/api/v1/container-reports"):
        popup.get_by_role("button", name="Full", exact=True).click()
    expect(popup.get_by_role("button", name="Full", exact=True)).to_be_disabled()
    expect(popup.get_by_role("button", name="Still space", exact=True)).to_be_disabled()
    assert requests[0].request.post_data_json == {"asset_id": "first", "condition": "full"}
    requests[0].fulfill(json={"created": 1_800_000_000, "expires": 1_800_043_200})
    expect(popup).to_contain_text("Glass container")
    expect(popup.locator(".stop-report-progress")).to_have_text("2 / 2")
    expect(popup.get_by_role("button", name="Still space", exact=True)).to_be_focused()
    popup.get_by_role("button", name="Skip", exact=True).click()
    expect(popup).to_have_count(0)
    assert len(requests) == 1


def test_expired_report_details_remain_available_in_map_control(page, web_url):
    page.goto(web_url)
    with page.expect_response("**/api/v1/trips") as response:
        route(page, web_url)
    asset_id = response.value.json()["stops"][0]["asset_ids"][0]
    page.route(
        "**/api/v1/container-statuses",
        lambda interception: interception.fulfill(
            json={
                "statuses": {},
                "rechecks": {
                    asset_id: {
                        "condition": "full",
                        "reported_at": 1_700_000_000,
                        "expires": 1_700_043_200,
                        "source": "community_report",
                    }
                },
                "version": "expired",
            }
        ),
    )
    page.evaluate("() => CommunityUI.refresh()")
    page.evaluate(
        "id => { const control = CommunityUI.containerControl([id]); "
        "document.body.append(control); control.open = true; }",
        asset_id,
    )
    row = page.locator(f'.condition-row[data-asset-id="{asset_id}"]')
    expect(row.locator(".condition-badge")).to_have_text("Needs a fresh check")
    expect(row.locator(".condition-history")).to_be_hidden()
    row.locator(".condition-report-details > summary").click()
    expect(row.locator(".condition-history")).to_contain_text("Last observation: Full")
    assert reports(page, web_url) == []
    page.evaluate("() => NajdiFrliI18n.setLanguage('mk')")
    expect(row.locator(".condition-badge")).to_have_text("Потребна е нова проверка")
