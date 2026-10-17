"""Six streams × three inputs × three origins × two modes, with fake providers."""

import json
import os

import httpx
import pytest
from playwright.sync_api import expect
from test_web_browser import ROOT, open_ai
from test_web_browser import browser as browser_fixture
from test_web_browser import page as page_fixture
from test_web_browser import web_url as web_url_fixture

from smart_recycling.routing_models import STREAM_KINDS

browser = browser_fixture
page = page_fixture
web_url = web_url_fixture
FIXTURES = ROOT / "tests/fixtures/pipeline"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
pytestmark = [
    pytest.mark.skipif(os.getenv("SRA_BROWSER_TESTS") != "1", reason="Opt-in browser tests"),
    pytest.mark.parametrize("web_url", ["system_server:app"], indirect=True),
]


COPY = json.loads((ROOT / "web/locales/mk.json").read_text(encoding="utf-8"))


def ui_text(text, language):
    return COPY.get(text, text) if language == "mk" else text


def choose_item(page, row, entry, language="en"):
    def t(text):
        return ui_text(text, language)

    if entry == "picker":
        page.get_by_role("button", name=t(row["card"]), exact=True).click()
        if row["id"] == "electronics":
            page.get_by_label(t("Only phones, chargers, cables or earbuds"), exact=True).check()
        page.locator("#confirm-picks").click()
    else:
        if not page.locator("#ai-help").evaluate("el => el.open"):
            page.locator("#ai-help summary").click()
        if entry == "text":
            page.get_by_label(t("Item"), exact=True).fill(row["text"])
            page.get_by_role("button", name=t("Check"), exact=True).click()
        else:
            page.get_by_label(t("Photo"), exact=True).set_input_files(
                FIXTURES / "images" / row["photo"]
            )
            page.get_by_role("button", name=t("Suggest from photo"), exact=True).click()
            expect(page.locator("#photo-result")).to_contain_text(row["text"])
            expect(page.locator("#trip-items li")).to_have_count(0)
            page.get_by_role("button", name=t("Review suggestion"), exact=True).click()
        # Do not correct the model/rule output to manufacture a passing journey.
        expect(page.locator("#item-kind")).to_have_value(row["kind"])
        page.get_by_role("button", name=t("Confirm & add to trip"), exact=True).click()
    expect(page.locator("#basket-count")).to_have_text(
        "Избрани: 1" if language == "mk" else "1 selected"
    )
    expect(page.get_by_role("button", name=t(row["card"]), exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )


def choose_origin(page, origin, language="en"):
    def t(text):
        return ui_text(text, language)

    if origin == "gps":
        page.context.grant_permissions(["geolocation"])
        page.context.set_geolocation({"latitude": 41.9965, "longitude": 21.4314})
        page.get_by_role("button", name=t("Use my location"), exact=True).click()
    elif origin == "map":
        page.get_by_role("button", name=t("Choose on map"), exact=True).click()
        page.get_by_role("button", name=t("Use map center"), exact=True).click()
    else:
        page.get_by_text(t("Enter coordinates manually"), exact=True).click()
        page.get_by_label(t("Latitude"), exact=True).fill("41.9965")
        page.get_by_label(t("Longitude"), exact=True).fill("21.4314")
        page.get_by_role("button", name=t("Set coordinates"), exact=True).click()
    expect(page.locator("#origin-editor")).to_be_hidden()
    expect(page.locator("#plan-trip")).to_be_enabled()


@pytest.mark.parametrize("row", CASES, ids=lambda row: row["id"])
@pytest.mark.parametrize("entry", ["picker", "text", "photo"])
@pytest.mark.parametrize("origin", ["gps", "map", "manual"])
@pytest.mark.parametrize("mode", ["Walking", "Driving"])
@pytest.mark.parametrize("language", ["en", "mk"])
def test_six_stream_pipeline(page, web_url, row, entry, origin, mode, language):
    if language == "mk":
        row = {**row, "text": row["mk_text"]}
    assert httpx.post(web_url + "/__test/pipeline-case/" + row["id"]).status_code == 200
    page.set_viewport_size({"width": 360 if mode == "Walking" else 1280, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(web_url)
    if language == "mk":
        page.locator(".language-switch").select_option("mk")
        expect(page.locator("html")).to_have_attribute("lang", "mk")
    expect(page.locator("#plan-trip")).to_be_disabled()
    choose_item(page, row, entry, language)
    expect(page.locator("#plan-trip")).to_be_disabled()
    choose_origin(page, origin, language)
    page.get_by_label(ui_text(mode, language), exact=True).check()
    calls = httpx.get(web_url + "/__test/pipeline-calls").json()["calls"]
    assert calls == ([{"service": "vision"}] if entry == "photo" else [])
    with page.expect_response("**/api/v1/trips") as pending:
        page.get_by_role("button", name=ui_text("Find my route", language), exact=True).click()
    response = pending.value
    assert response.status == 200, response.text()
    trip = response.json()
    request = response.request.post_data_json
    assert request["share_coordinates"] is True
    assert len(request["items"]) == 1
    assert request["origin"]["latitude"] == pytest.approx(
        float(page.locator("#latitude").input_value()), abs=1e-6
    )
    assert request["origin"]["longitude"] == pytest.approx(
        float(page.locator("#longitude").input_value()), abs=1e-6
    )
    expected_kind = row["kind"]
    if entry == "picker" and row["id"] not in {"electronics", "clothes"}:
        expected_kind = row["material"]
    assert {kind for stop in trip["stops"] for kind in stop["item_kinds"]} == {expected_kind}
    sites = {
        site["id"]: site
        for site in httpx.get(web_url + "/api/v1/sites?scope=citizen").json()["sites"]
    }
    for stop in trip["stops"]:
        assets = [a for a in sites[stop["site_id"]]["assets"] if a["id"] in stop["asset_ids"]]
        assert assets
        if row["id"] == "general":
            assert "general" in stop["unverified_materials"]
            assert all(
                a["asset_type"] == "waste_container"
                and "mixed_municipal_waste" in a["source_materials"]
                for a in assets
            )
        else:
            accepted = {kind for a in assets for kind in a["acceptance"]["accepted_item_kinds"]}
            assert STREAM_KINDS.get(expected_kind, {expected_kind}) <= accepted
    profile = "foot-walking" if mode == "Walking" else "driving-car"
    assert trip["profile"] == profile
    assert trip["ends_at_last_stop"] is True
    calls = httpx.get(web_url + "/__test/pipeline-calls").json()["calls"]
    route_calls = [call for call in calls if call["service"] != "vision"]
    assert [call["service"] for call in route_calls] == ["matrix", "directions"]
    assert all(call["profile"] == profile for call in route_calls)
    assert route_calls[0]["points"][0] == [
        request["origin"]["longitude"],
        request["origin"]["latitude"],
    ]
    expect(page.locator("#trip-result")).to_contain_text(
        "Патување: " + ui_text(mode, language) if language == "mk" else mode + " trip"
    )
    expect(page.locator("#trip-stop-1")).to_have_attribute("data-materials", row["map_material"])
    expect(page.locator(".route-stop-number")).to_have_count(len(trip["stops"]))
    if mode == "Walking":
        expect(page.locator(".trip-route-line")).to_have_attribute("stroke-dasharray", "8 10")
    else:
        expect(page.locator(".trip-route-line")).not_to_have_attribute("stroke-dasharray", "8 10")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors
    if row["id"] == "clothes" and entry == "photo" and origin == "map":
        page.locator("#trip-result").screenshot(
            path=str(ROOT / "artifacts" / f"pipeline-{language}-{mode.lower()}-result.png")
        )
        page.screenshot(
            path=str(ROOT / "artifacts" / f"pipeline-{language}-{mode.lower()}.png"), full_page=True
        )


@pytest.mark.parametrize("text", ["battery", "swollen phone", "dirty shirt", "mystery material"])
def test_unsafe_or_unknown_items_never_enter_basket(page, web_url, text):
    httpx.post(web_url + "/__test/pipeline-case/glass").raise_for_status()
    page.goto(web_url)
    open_ai(page)
    page.get_by_label("Item", exact=True).fill(text)
    with page.expect_response("**/api/v1/classify") as pending:
        page.get_by_role("button", name="Check", exact=True).click()
    assert pending.value.json()["status"] in {"held", "specialist", "clarify"}
    expect(page.locator("#trip-items li")).to_have_count(0)
    expect(page.locator("#plan-trip")).to_be_disabled()
    assert httpx.get(web_url + "/__test/pipeline-calls").json()["calls"] == []


@pytest.mark.parametrize("fault", ["vision", "routing"])
def test_external_failure_and_retry(page, web_url, fault):
    httpx.post(web_url + "/__test/pipeline-case/glass", params={"fault": fault}).raise_for_status()
    page.goto(web_url)
    if fault == "vision":
        open_ai(page)
        page.get_by_label("Photo", exact=True).set_input_files(FIXTURES / "images/glass.png")
        button = page.get_by_role("button", name="Suggest from photo", exact=True)
        with page.expect_response("**/api/v1/photo-suggestions") as pending:
            button.click()
        assert pending.value.status == 503
        expect(page.locator("#photo-status")).to_contain_text("unavailable")
        expect(page.locator("#trip-items li")).to_have_count(0)
        expect(button).to_be_enabled()
        choose_item(page, CASES[0], "photo")
    else:
        choose_item(page, CASES[0], "picker")
    choose_origin(page, "manual")
    button = page.get_by_role("button", name="Find my route", exact=True)
    if fault == "routing":
        with page.expect_response("**/api/v1/trips") as pending:
            button.click()
        assert pending.value.status == 503
        expect(page.locator("#trip-result")).to_be_hidden()
        expect(page.locator("#basket-count")).to_have_text("1 selected")
        expect(button).to_be_enabled()
    with page.expect_response("**/api/v1/trips") as pending:
        button.click()
    assert pending.value.status == 200
    expect(page.locator("#trip-result")).to_be_visible()


@pytest.mark.parametrize("mode", ["Walking", "Driving"])
def test_all_six_selected_together(page, web_url, mode):
    httpx.post(web_url + "/__test/pipeline-case/glass").raise_for_status()
    page.goto(web_url)
    for row in CASES:
        page.get_by_role("button", name=row["card"], exact=True).click()
    page.get_by_label("Only phones, chargers, cables or earbuds", exact=True).check()
    page.locator("#confirm-picks").click()
    expect(page.locator("#basket-count")).to_have_text("6 selected")
    choose_origin(page, "map")
    page.get_by_label(mode, exact=True).check()
    with page.expect_response("**/api/v1/trips") as pending:
        page.locator("#plan-trip").click()
    assert pending.value.status == 200
    trip = pending.value.json()
    assert {kind for stop in trip["stops"] for kind in stop["item_kinds"]} == {
        "glass",
        "plastic_metal",
        "paper_tetrapak",
        "general",
        "small_electronics",
        "wearable_clothes",
    }
    assert len({stop["site_id"] for stop in trip["stops"]}) == len(trip["stops"])
