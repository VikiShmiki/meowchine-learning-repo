"""Bus journeys, failures and check-ins through the real bilingual application."""

import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_web_browser import browser as browser_fixture
from test_web_browser import page as page_fixture
from test_web_browser import web_url as web_url_fixture

browser = browser_fixture
page = page_fixture
web_url = web_url_fixture
pytestmark = [
    pytest.mark.skipif(os.getenv("SRA_BROWSER_TESTS") != "1", reason="Opt-in browser tests"),
    pytest.mark.parametrize("web_url", ["transit_server:app"], indirect=True),
]


def prepare(page, web_url):
    config = page.request.post(web_url + "/__test/transit").json()
    page.request.post(web_url + "/__test/reset-community")
    page.goto(web_url)
    page.get_by_role("button", name="Electronics", exact=True).click()
    page.locator("#confirm-picks").click()
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill(str(config["latitude"]))
    page.get_by_label("Longitude", exact=True).fill(str(config["longitude"]))
    page.get_by_role("button", name="Set coordinates", exact=True).click()
    page.locator('#trip-mode input[value="transit"]').check()
    return config


@pytest.mark.parametrize("width", [320, 390, 1280])
@pytest.mark.parametrize("language", ["en", "mk"])
def test_bus_itinerary_map_completion_and_full_exclusion(page, web_url, width, language):
    page.set_viewport_size({"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    config = prepare(page, web_url)
    page.locator(".language-switch").select_option(language)
    with page.expect_response("**/api/v1/trips") as response:
        page.locator("#plan-trip").click()
    assert response.value.ok, response.value.text()
    body = response.value.json()
    assert [leg["mode"] for leg in body["legs"]] == ["walking", "bus", "walking"]
    expect(page.locator(".transit-legs li[data-mode=bus]")).to_contain_text("5")
    expect(page.locator(".bus-route-line")).to_have_count(1)
    expect(page.locator(".trip-route-line:not(.bus-route-line)")).to_have_count(2)
    expect(page.locator("#trip-result")).to_contain_text("Europe/Skopje")
    expect(page.locator("#trip-result")).to_contain_text(
        "Board:" if language == "en" else "Качување:"
    )
    expect(page.locator(".transit-legs")).to_contain_text(
        "Starting point" if language == "en" else "Почетна точка"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if os.getenv("SRA_TRANSIT_SCREENSHOTS"):
        page.locator("#trip-result").screenshot(
            path=str(Path(os.environ["SRA_TRANSIT_SCREENSHOTS"]) / f"jsp-{language}-{width}.png")
        )
    page.get_by_role(
        "button", name="Dropped off" if language == "en" else "Ги предадов", exact=True
    ).click()
    expect(page.locator("#trip-result")).to_be_hidden()
    expect(page.locator("#trip-checkin")).to_be_visible()
    row = page.locator("#stop-report-dialog .stop-report-container")
    with page.expect_response("**/api/v1/container-reports"):
        row.locator("button[data-condition=full]").click()
    # A fresh visitor cannot get a bus itinerary to the only compatible full facility.
    result = page.request.post(
        web_url + "/api/v1/trips",
        data={
            "origin": {key: config[key] for key in ("latitude", "longitude")},
            "mode": "transit",
            "items": [{"material": "electronics", "condition_confirmed": True}],
            "share_coordinates": True,
        },
    )
    assert result.status == 422
    assert result.json()["detail"]["code"] == "no_compatible_site"
    assert not errors


def test_unavailable_timetable_retry_and_mode_date_invalidation(page, web_url):
    prepare(page, web_url)
    page.request.post(web_url + "/__test/transit?fail=true")
    page.locator("#plan-trip").click()
    expect(page.locator("#trip-status")).to_contain_text("JSP timetable is unavailable")
    expect(page.locator("#plan-trip")).to_be_enabled()
    expect(page.locator("#trip-result")).to_be_hidden()
    page.request.post(web_url + "/__test/transit")
    page.locator("#plan-trip").click()
    expect(page.locator("#trip-result")).to_be_visible()
    page.locator("#transit-departure").fill("2026-10-17T22:00")
    expect(page.locator("#trip-result")).to_be_hidden()
    page.locator("#plan-trip").click()
    expect(page.locator("#trip-status")).to_contain_text("No scheduled JSP service")
    page.locator('#trip-mode input[value="walking"]').check()
    expect(page.locator("#transit-options")).to_be_hidden()
    page.locator("#plan-trip").click()
    expect(page.locator("#trip-result h3")).to_have_text("Walking trip")
