"""Parking routes through the real page/API, with deterministic external roads."""

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
    pytest.mark.parametrize("web_url", ["parking_server:app"], indirect=True),
]


def prepare(page, web_url):
    page.request.post(web_url + "/__test/parking")
    page.request.post(web_url + "/__test/reset-community")
    page.goto(web_url)
    page.get_by_role("button", name="Glass bottles and jars", exact=True).click()
    page.locator("#confirm-picks").click()
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.locator("#latitude").fill("41.9965")
    page.locator("#longitude").fill("21.4314")
    page.get_by_role("button", name="Set coordinates", exact=True).click()
    page.locator('#trip-mode input[value="driving"]').check()
    expect(page.locator("#parking-options")).to_be_visible()
    page.locator("#include-parking").check()


@pytest.mark.parametrize("width", [320, 390, 1280])
@pytest.mark.parametrize("language", ["en", "mk"])
def test_parking_map_walk_completion_and_full_exclusion(page, web_url, width, language):
    page.set_viewport_size({"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    prepare(page, web_url)
    page.locator(".language-switch").select_option(language)
    with page.expect_response("**/api/v1/trips") as response:
        page.locator("#plan-trip").click()
    assert response.value.ok, response.value.text()
    body = response.value.json()
    assert body["profile"] == "driving-car+foot-walking"
    assert body["parking"][0]["availability"] == "unknown"
    expect(page.locator(".parking-visit")).to_contain_text(
        "unknown" if language == "en" else "непознат"
    )
    expect(page.locator(".parking-map-marker")).to_have_count(len(body["parking"]))
    assert page.locator(".trip-route-line").count() >= 2
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if os.getenv("SRA_PARKING_SCREENSHOTS"):
        page.locator("#trip-result").screenshot(
            path=str(
                Path(os.environ["SRA_PARKING_SCREENSHOTS"]) / f"parking-{language}-{width}.png"
            )
        )
        page.locator(".map-shell").screenshot(
            path=str(
                Path(os.environ["SRA_PARKING_SCREENSHOTS"]) / f"parking-map-{language}-{width}.png"
            )
        )
    page.get_by_role(
        "button", name="Dropped these off" if language == "en" else "Ги предадов", exact=True
    ).click()
    expect(page.locator("#trip-checkin")).to_be_visible()
    row = page.locator("#trip-checkin .condition-row").first
    asset = row.get_attribute("data-asset-id")
    row.locator("select").select_option("full")
    row.locator("button").click()
    expect(row.locator("button")).to_be_disabled()
    result = page.request.post(
        web_url + "/api/v1/trips",
        data={
            "origin": {"latitude": 41.9965, "longitude": 21.4314},
            "mode": "driving",
            "include_parking": True,
            "items": [{"material": "glass", "condition_confirmed": True}],
            "share_coordinates": True,
        },
    )
    assert result.ok, result.text()
    assert asset not in {a for s in result.json()["stops"] for a in s["asset_ids"]}
    assert not errors


def test_unavailable_retry_toggle_and_switching_modes(page, web_url):
    prepare(page, web_url)
    page.request.post(web_url + "/__test/parking?fail=true")
    page.locator("#plan-trip").click()
    expect(page.locator("#trip-status")).to_contain_text("Parking data is unavailable")
    expect(page.locator("#trip-result")).to_be_hidden()
    expect(page.locator("#plan-trip")).to_be_enabled()
    page.request.post(web_url + "/__test/parking")
    page.locator("#plan-trip").click()
    expect(page.locator(".parking-visit")).to_be_visible()
    page.locator("#include-parking").uncheck()
    expect(page.locator("#trip-result")).to_be_hidden()
    with page.expect_response("**/api/v1/trips") as response:
        page.locator("#plan-trip").click()
    assert response.value.json()["profile"] == "driving-car"
    expect(page.locator(".parking-visit")).to_have_count(0)
    page.locator('#trip-mode input[value="walking"]').check()
    expect(page.locator("#parking-options")).to_be_hidden()
    expect(page.locator("#trip-result")).to_be_hidden()
