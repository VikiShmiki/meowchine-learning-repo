"""Optional accounts end-to-end, with fake routing and an isolated database."""

import json
import os
import time
import uuid

import pytest
from playwright.sync_api import expect
from test_web_browser import ROOT
from test_web_browser import browser as browser_fixture
from test_web_browser import page as page_fixture
from test_web_browser import web_url as web_url_fixture

from smart_recycling import api

browser = browser_fixture
page = page_fixture
web_url = web_url_fixture
pytestmark = [
    pytest.mark.skipif(os.getenv("SRA_BROWSER_TESTS") != "1", reason="Opt-in browser tests"),
    pytest.mark.parametrize("web_url", ["system_server:app"], indirect=True),
]
PASSWORD = "only-for-browser-testing-42"


def register(page, web_url):
    page.request.post(web_url + "/__test/reset-account-budget")
    page.get_by_role("button", name="Sign in", exact=True).click()
    page.locator("#account-register-tab").click()
    username = "test_" + uuid.uuid4().hex[:10]
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.locator("#account-submit").click()
    expect(page.locator("#account-message")).to_have_text("Account created.")
    expect(page.locator("#account-heading")).to_have_text(username)
    page.get_by_role("button", name="Close account").click()
    return username


def route(page, web_url, material="Glass bottles and jars", mode="Walking"):
    page.request.post(web_url + "/__test/reset-routing-budget")
    page.get_by_role("button", name=material, exact=True).click()
    page.locator("#confirm-picks").click()
    page.get_by_text("Enter coordinates manually", exact=True).click()
    page.get_by_label("Latitude", exact=True).fill("41.9965")
    page.get_by_label("Longitude", exact=True).fill("21.4314")
    page.get_by_role("button", name="Set coordinates", exact=True).click()
    page.get_by_label(mode, exact=True).check()
    page.get_by_role("button", name="Find my route", exact=True).click()
    expect(page.locator("#trip-result")).to_be_visible()


@pytest.mark.parametrize("width", [360, 1280])
@pytest.mark.parametrize("mode", ["Walking", "Driving"])
def test_account_route_dropoff_history_navigation_and_logout(page, web_url, width, mode):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(web_url)
    username = register(page, web_url)
    route(page, web_url, mode=mode)
    page.get_by_role("button", name="Dropped these off", exact=True).click()
    expect(page.locator("#trip-status")).to_contain_text("Saved to My activity.")
    expect(page.locator("#trip-items li")).to_have_count(0)
    page.get_by_role("button", name="My activity", exact=True).click()
    expect(page.locator(".account-total")).to_have_text("1")
    expect(page.locator('.account-badge[data-earned="true"]')).to_have_count(1)
    expect(
        page.get_by_role("progressbar", name="Progress to 10 recycling drop-offs")
    ).to_have_attribute("aria-valuenow", "1")
    page.get_by_role("tab", name="History", exact=True).click()
    expect(page.locator(".account-history-row")).to_have_count(1)
    expect(page.locator(".account-materials")).to_have_text("Glass")
    box = page.locator("#account-dialog").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= width
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    if os.getenv("SRA_LAYOUT_SCREENSHOTS"):
        page.locator("#account-dialog").screenshot(
            path=str(ROOT / "artifacts" / f"account-{width}-{mode}.png")
        )
    page.get_by_role("button", name="Close account").click()
    expect(page.locator("#account-entry")).to_be_focused()
    page.get_by_role("navigation", name="Application").get_by_role(
        "link", name="City coverage"
    ).click()
    page.get_by_role("button", name="My activity", exact=True).click()
    expect(page.locator("#account-heading")).to_have_text(username)
    expect(page.locator(".account-total")).to_have_text("1")
    page.get_by_role("button", name="Sign out", exact=True).click()
    expect(page.locator("#account-guest")).to_be_visible()
    expect(page.locator("#account-member")).to_be_hidden()
    page.locator("#account-login-tab").click()
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.locator("#account-submit").click()
    expect(page.locator(".account-total")).to_have_text("1")


@pytest.mark.parametrize("material", ["General waste", "Clothes for donation"])
def test_general_and_clothes_completion_rules(page, web_url, material):
    page.goto(web_url)
    register(page, web_url)
    route(page, web_url, material=material)
    page.get_by_role("button", name="Dropped these off", exact=True).click()
    expect(page.locator("#trip-items li")).to_have_count(0)
    page.get_by_role("button", name="My activity", exact=True).click()
    expect(page.locator(".account-total")).to_have_text("0" if material == "General waste" else "1")


def test_failed_dropoff_preserves_basket_and_retry_counts_once(page, web_url):
    page.goto(web_url)
    register(page, web_url)
    route(page, web_url)
    page.route("**/api/v1/account/dropoffs", lambda interception: interception.abort())
    page.get_by_role("button", name="Dropped these off", exact=True).click()
    expect(page.get_by_role("button", name="Mark without saving")).to_be_visible()
    expect(page.locator("#trip-items li")).to_have_count(1)
    expect(page.get_by_role("button", name="Dropped these off", exact=True)).to_be_enabled()
    page.unroute("**/api/v1/account/dropoffs")
    page.get_by_role("button", name="Dropped these off", exact=True).click()
    expect(page.locator("#trip-items li")).to_have_count(0)
    page.get_by_role("button", name="My activity", exact=True).click()
    expect(page.locator(".account-total")).to_have_text("1")


def test_session_expiry_allows_explicit_unsaved_completion(page, web_url):
    page.goto(web_url)
    register(page, web_url)
    route(page, web_url)
    page.request.post(web_url + "/api/v1/account/logout", headers={"X-Najdi-Frli-Action": "1"})
    page.get_by_role("button", name="Dropped these off", exact=True).click()
    expect(page.locator("#trip-items li")).to_have_count(1)
    page.get_by_role("button", name="Mark without saving").click()
    expect(page.locator("#trip-items li")).to_have_count(0)


def test_account_validation_failure_recovery_and_deletion(page, web_url):
    page.goto(web_url + "/city")
    username = register(page, web_url)
    page.get_by_role("button", name="My activity", exact=True).click()
    page.get_by_text("Delete account", exact=True).click()
    page.get_by_label("Confirm password").fill("wrong-password-for-test")
    page.get_by_role("button", name="Delete account and history").click()
    expect(page.locator("#account-message")).to_have_text("Password incorrect.")
    page.get_by_label("Confirm password").fill(PASSWORD)
    page.get_by_role("button", name="Delete account and history").click()
    expect(page.locator("#account-message")).to_have_text("Account and history deleted.")
    page.locator("#account-login-tab").click()
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.locator("#account-submit").click()
    expect(page.locator("#account-message")).to_have_text("Username or password incorrect.")
    expect(page.locator("#account-submit")).to_be_enabled()


def test_guest_route_and_dialog_keyboard_dismissal(page, web_url):
    page.goto(web_url)
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.locator("#account-dialog")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#account-dialog")).not_to_be_visible()
    route(page, web_url)
    page.get_by_role("button", name="Dropped these off", exact=True).click()
    expect(page.locator("#trip-status")).to_have_text("All items marked dropped off.")


@pytest.mark.parametrize("width", [360, 1280])
@pytest.mark.parametrize("count", [0, 1, 10, 25])
def test_activity_visual_states_and_keyboard_navigation(page, web_url, width, count):
    now = time.time()
    user = {"id": "visual-test", "username": "recycling_test"}
    streams = ["glass", "plastic_metal", "paper_tetrapak", "clothes", "electronics"]
    with api.community_store.connection() as db:
        db.execute(
            "INSERT INTO accounts VALUES (?,?,?,?)", (user["id"], user["username"], "unused", now)
        )
        for i in range(count):
            db.execute(
                "INSERT INTO dropoffs VALUES (?,?,?,?,?)",
                (
                    f"visual-{i}",
                    user["id"],
                    json.dumps([streams[i % 5]]),
                    now - i * 86400,
                    1,
                ),
            )
    summary = api.accounts.summary(user)
    page.route("**/api/v1/account/me", lambda r: r.fulfill(json=summary))
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(web_url)
    page.get_by_role("button", name="My activity", exact=True).click()
    expect(page.locator(".account-total")).to_have_text(str(count))
    expect(page.locator(".activity-days span")).to_have_count(28)
    assert (
        sum(
            int(v)
            for v in page.locator(".activity-days span").evaluate_all(
                "els => els.map(e => e.dataset.level)"
            )
        )
        == count
    )
    if os.getenv("SRA_LAYOUT_SCREENSHOTS"):
        page.locator("#account-dialog").screenshot(
            path=str(ROOT / "artifacts" / f"activity-overview-{width}-{count}.png")
        )
    page.get_by_role("tab", name="Overview", exact=True).focus()
    page.keyboard.press("ArrowRight")
    expect(page.get_by_role("tab", name="Badges", exact=True)).to_be_focused()
    expect(page.locator(".account-badge")).to_have_count(6)
    # Keep a visible gap between every central symbol and its inner border.
    assert page.locator(".badge-art > svg").evaluate_all("""svgs => svgs.every(svg => {
        const rim = svg.querySelector('.badge-rim');
        const shapes = [...svg.querySelectorAll('.badge-symbol > *')];
        return shapes.length > 0 && shapes.every(shape => {
            const points = [];
            if (shape.getTotalLength) {
                const length = shape.getTotalLength();
                for (let i = 0; i <= 100; i++)
                    points.push(shape.getPointAtLength(length * i / 100));
            } else {
                const b = shape.getBBox();
                for (const x of [b.x, b.x + b.width])
                    for (const y of [b.y, b.y + b.height]) points.push({x, y});
            }
            return points.every(p => [[-3,0],[3,0],[0,-3],[0,3]].every(([dx,dy]) =>
                rim.isPointInFill(new DOMPoint(p.x + dx, p.y + dy))));
        });
    })""")
    expected = sum(a["earned_at"] is not None for a in summary["achievements"])
    expect(page.locator('.account-badge[data-earned="true"]')).to_have_count(expected)
    if os.getenv("SRA_LAYOUT_SCREENSHOTS"):
        page.locator("#account-dialog").screenshot(
            path=str(ROOT / "artifacts" / f"activity-badges-{width}-{count}.png")
        )
    assert page.locator("#account-dialog").evaluate("e => e.scrollWidth <= e.clientWidth")
    page.keyboard.press("End")
    expect(page.get_by_role("tab", name="History", exact=True)).to_be_focused()
    expect(page.locator(".account-history-row")).to_have_count(count)
    page.get_by_label("Filter by material").select_option("electronics")
    expect(page.locator(".account-history-row")).to_have_count(count // 5)
    page.get_by_label("Filter by material").select_option("general")
    expect(page.locator(".account-empty")).to_be_visible()
    page.get_by_role("tab", name="History", exact=True).focus()
    page.keyboard.press("Home")
    expect(page.get_by_role("tab", name="Overview", exact=True)).to_be_focused()
