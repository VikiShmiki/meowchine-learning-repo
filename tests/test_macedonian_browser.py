"""Macedonian journeys exercise the real backend with isolated, simulated providers."""

import os
import re
import uuid

import pytest
from playwright.sync_api import expect
from test_web_browser import ROOT
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


def switch(page, language):
    page.locator(".language-switch").select_option(language)
    expect(page.locator("html")).to_have_attribute("lang", language)


@pytest.mark.parametrize("width", [320, 390, 1280])
@pytest.mark.parametrize("mode", ["walking", "driving"])
@pytest.mark.parametrize("font", ["system", "Verdana"])
def test_macedonian_text_route_and_bidirectional_switch_preserve_state(
    page, web_url, width, mode, font
):
    if font != "system":
        page.add_init_script(
            "document.addEventListener('DOMContentLoaded', "
            "() => document.body.style.fontFamily = 'Verdana, sans-serif')"
        )
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(web_url)
    switch(page, "mk")
    expect(page.get_by_role("heading", name="Рути за рециклирање")).to_be_visible()
    if os.getenv("SRA_LAYOUT_SCREENSHOTS") and mode == "walking":
        page.screenshot(path=str(ROOT / "artifacts" / f"macedonian-home-{width}.png"))
    page.locator("#ai-help summary").click()
    page.locator("#item").fill("празно стаклено шише")
    page.locator("#classify-form button[type=submit]").click()
    expect(page.locator("#item-kind")).to_have_value("empty_glass_packaging")
    expect(page.locator("#condition-label")).to_contain_text("потврдувате")
    switch(page, "en")
    expect(page.locator("#item")).to_have_value("празно стаклено шише")
    expect(page.locator("#condition-label")).to_contain_text("By adding")
    switch(page, "mk")
    page.locator("#confirm-item").click()
    expect(page.locator("#trip-items li")).to_have_count(1)
    expect(page.locator("#trip-items")).to_contain_text("Стаклено")
    page.get_by_text("Внеси координати рачно", exact=True).click()
    page.locator("#latitude").fill("41.9965")
    page.locator("#longitude").fill("21.4314")
    page.get_by_role("button", name="Постави координати", exact=True).click()
    page.locator(f'#trip-mode input[value="{mode}"]').check()
    page.get_by_role("button", name="Најди рута", exact=True).click()
    expect(page.locator("#trip-result")).to_be_visible()
    before = page.locator("#trip-result").inner_text()
    assert "Предајте" in before
    switch(page, "en")
    expect(page.locator("#trip-result")).to_contain_text("Drop off:")
    expect(page.locator("#trip-items li")).to_have_count(1)
    switch(page, "mk")
    expect(page.locator("#trip-result")).to_contain_text("Предајте")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [320, 1280])
def test_macedonian_navigation_city_and_account(page, web_url, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(web_url)
    switch(page, "mk")
    page.get_by_role("link", name="Градска покриеност", exact=True).click()
    expect(page.locator("html")).to_have_attribute("lang", "mk")
    expect(page.locator("#coverage-summary")).to_contain_text("Покриеност на населението")
    page.locator("#coverage-material").select_option("paper_tetrapak")
    page.get_by_role("button", name="Препорачај подобрувања", exact=True).click()
    expect(page.locator("#upgrade-results")).to_be_visible()
    expect(page.locator("#upgrade-results")).to_contain_text("Додај собирање: хартија и картони")
    expect(page.locator("#upgrade-results")).not_to_contain_text("paper and cartons collection")
    if os.getenv("SRA_LAYOUT_SCREENSHOTS"):
        page.screenshot(path=str(ROOT / "artifacts" / f"macedonian-city-{width}.png"))
    page.get_by_role("button", name="Најави се", exact=True).click()
    page.locator("#account-register-tab").click()
    username = "mk_" + uuid.uuid4().hex[:10]
    page.locator("#account-username").fill(username)
    page.locator("#account-password").fill("macedonian-browser-password-42")
    page.locator("#account-submit").click()
    expect(page.locator("#account-message")).to_have_text("Сметката е создадена.")
    expect(page.locator("#account-heading")).to_have_text(username)
    page.get_by_role("tab", name="Значки", exact=True).click()
    expect(page.locator(".account-badge")).to_have_count(6)
    expect(page.locator("#account-dialog")).to_contain_text("Прво предавање")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if os.getenv("SRA_LAYOUT_SCREENSHOTS"):
        page.screenshot(path=str(ROOT / "artifacts" / f"macedonian-account-{width}.png"))
    page.get_by_role("button", name="Затвори сметка", exact=True).click()
    switch(page, "en")
    expect(page.get_by_role("button", name="My activity", exact=True)).to_be_visible()
    page.reload()
    expect(page.locator("html")).to_have_attribute("lang", "en")


@pytest.mark.parametrize(
    "material", ["glass", "plastic_metal", "paper_tetrapak", "general", "electronics", "clothes"]
)
def test_macedonian_quick_picks_and_photo_review(page, web_url, material):
    page.goto(web_url)
    switch(page, "mk")
    page.locator(f'.waste-card[data-material="{material}"]').click()
    page.locator("#confirm-picks").click()
    expect(page.locator("#trip-items li")).to_have_count(1)
    page.locator("#ai-help summary").click()
    image = {"plastic_metal": "plastic", "paper_tetrapak": "paper"}.get(material, material)
    page.locator("#item-photo").set_input_files(
        str(ROOT / f"tests/fixtures/pipeline/images/{image}.png")
    )
    page.locator("#analyze-photo").click()
    expect(page.locator("#photo-items li")).not_to_have_count(0)
    expect(page.locator("#photo-result")).to_contain_text("Прегледај")


def test_language_switch_updates_dynamic_errors_and_keeps_form_input(page, web_url):
    page.goto(web_url)
    switch(page, "mk")
    page.locator("#ai-help summary").click()
    page.locator("#item").fill("валкано пластично шише")
    page.locator("#classify-form button[type=submit]").click()
    expect(page.locator("#message")).to_contain_text("не е потврдено")
    switch(page, "en")
    expect(page.locator("#message")).to_contain_text("not confirmed")
    expect(page.locator("#item")).to_have_value("валкано пластично шише")
    page.locator("#item").fill("надуена батерија")
    page.locator("#classify-form button[type=submit]").click()
    expect(page.locator("#category")).to_have_text("Specialist disposal")
    switch(page, "mk")
    expect(page.locator("#category")).to_have_text("Специјализирано одлагање")
    expect(page.locator("#manual-form")).to_be_hidden()


def test_static_localization_has_no_untranslated_app_copy(page, web_url):
    allowed = re.compile(
        r"^(goodsort|English|Македонски|Leaflet|OpenStreetMap|©|Nula Otpad|"
        r"WorldPop|Tetra Pak|\W*\d)"
    )
    for path in ["/", "/city", "/review"]:
        page.goto(web_url + path)
        switch(page, "mk")
        texts = page.evaluate("""() => {
          const out = [];
          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
          while (walker.nextNode()) {
            const node = walker.currentNode, parent = node.parentElement;
            if (parent && !parent.closest('script, style, [translate="no"]')
              && parent.getClientRects().length && /[A-Za-z]{3}/.test(node.textContent))
              out.push(node.textContent.trim());
          } return out.filter(Boolean);
        }""")
        missing = [
            text
            for text in texts
            if not re.search(r"[А-Яа-яЃѓЌќЏџШш]", text) and not allowed.match(text)
        ]
        assert not missing, missing


def test_catalog_failure_keeps_english_controls_and_explains_retry(page, web_url):
    page.route("**/static/locales/mk.json", lambda route: route.fulfill(status=503))
    page.goto(web_url)
    expect(page.get_by_role("alert")).to_contain_text("Reload to retry")
    page.locator(".language-switch").select_option("mk")
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.get_by_role("button", name="Sign in", exact=True)).to_be_visible()


def test_cyrillic_location_search_and_language_switch_keep_query(page, web_url):
    page.goto(web_url)
    switch(page, "mk")
    page.locator("#discovery-controls summary").click()
    search = page.locator("#site-search")
    search.fill("Карпош")
    expect(page.locator("#site-list li")).not_to_have_count(0)
    switch(page, "en")
    expect(search).to_have_value("Карпош")


def test_multiple_conditions_and_report_placeholder_translate_without_editing_input(page, web_url):
    page.goto(web_url)
    switch(page, "mk")
    for material in ["glass", "general", "clothes"]:
        page.locator(f'.waste-card[data-material="{material}"]').click()
    condition = page.locator("#picker-condition")
    expect(condition).to_contain_text("Предметите за рециклирање се празни/чисти.")
    expect(condition).to_contain_text("Мешан отпад: само обичен домашен отпад.")
    expect(condition).to_contain_text("Облека: чиста, испрана и нослива")
    switch(page, "en")
    expect(condition).to_contain_text("Recyclables empty / clean.")
    expect(condition).to_contain_text("Clothes: clean, washed and wearable")
    page.goto(web_url + "/city")
    switch(page, "mk")
    expect(page.locator("#dumping-map")).to_be_visible()
    expect(page.locator("#community-reports-heading")).to_have_text("Пријави од заедницата")
    description = page.get_by_placeholder("Што е одложено тука?", exact=True)
    description.fill("Glass")
    switch(page, "en")
    expect(page.locator('textarea[name="description"]')).to_have_value("Glass")
    expect(page.locator('textarea[name="description"]')).to_have_attribute(
        "placeholder", "What is dumped here?"
    )
