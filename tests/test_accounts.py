"""Account security, private history, route tickets and honest milestone accounting."""

import base64
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from test_routing import GLASS, PAPER, request, service, site

from smart_recycling import api
from smart_recycling.accounts import Accounts, password_hash, password_matches, session_digest

PASSWORD = "testing-recycling-only-42"
HEADERS = {"X-Najdi-Frli-Action": "1"}


@pytest.fixture(scope="module")
def encoded():
    return password_hash(PASSWORD)


@pytest.fixture
def account(encoded):
    with api.community_store.connection() as db:
        db.execute(
            "INSERT INTO accounts VALUES (?,?,?,?)", ("alice-id", "alice", encoded, time.time())
        )
        db.execute("INSERT INTO accounts VALUES (?,?,?,?)", ("bob-id", "bob", encoded, time.time()))
    return api.accounts


def client_for(account, user_id="alice-id"):
    client = TestClient(api.app)
    client.cookies.set("sra_session", account.start_session(user_id, ""))
    return client


def test_password_hash_is_salted_and_verifies(encoded):
    assert encoded != password_hash(PASSWORD)
    assert PASSWORD not in encoded
    assert password_matches(PASSWORD, encoded)
    assert not password_matches("wrong-password-for-test", encoded)


def test_registration_normalizes_username_and_rotates_cookie():
    client = TestClient(api.app)
    response = client.post(
        "/api/v1/account/register",
        headers=HEADERS,
        json={"username": " New_User ", "password": PASSWORD},
    )
    assert response.status_code == 201
    assert response.json()["user"]["username"] == "new_user"
    assert response.json()["recycling_count"] == 0
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert response.headers["cache-control"] == "no-store"
    first = client.cookies.get("sra_session")
    with api.community_store.connection() as db:
        row = db.execute("SELECT * FROM sessions").fetchone()
        assert row["digest"] == session_digest(first) and row["digest"] != first
    assert (
        client.post(
            "/api/v1/account/register",
            headers=HEADERS,
            json={"username": "NEW_USER", "password": PASSWORD},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/account/login",
            headers=HEADERS,
            json={"username": "new_user", "password": PASSWORD},
        ).status_code
        == 200
    )
    assert client.cookies.get("sra_session") != first
    assert api.accounts.user(first) is None


def test_login_errors_and_logout_invalidate_session(account):
    client = client_for(account)
    for username in ["alice", "missing"]:
        response = client.post(
            "/api/v1/account/login",
            headers=HEADERS,
            json={"username": username, "password": "wrong-password-for-test"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Username or password incorrect."
    token = client.cookies.get("sra_session")
    assert client.post("/api/v1/account/logout", headers=HEADERS).status_code == 204
    assert account.user(token) is None
    assert client.get("/api/v1/account/me").json() == {"user": None}


def test_previous_account_action_header_remains_compatible(account):
    client = client_for(account)
    token = client.cookies.get("sra_session")
    assert (
        client.post("/api/v1/account/logout", headers={"X-Goodsort-Action": "1"}).status_code == 204
    )
    assert account.user(token) is None


def test_secure_cookie_on_https_and_expired_sessions(account):
    client = TestClient(api.app, base_url="https://testserver")
    response = client.post(
        "/api/v1/account/login", headers=HEADERS, json={"username": "alice", "password": PASSWORD}
    )
    assert "Secure" in response.headers["set-cookie"]
    with api.community_store.connection() as db:
        db.execute("UPDATE sessions SET expires=?", (time.time() - 1,))
    assert client.get("/api/v1/account/me").json() == {"user": None}


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/login"),
        ("post", "/register"),
        ("post", "/logout"),
        ("post", "/dropoffs"),
        ("delete", ""),
    ],
)
def test_account_mutations_require_custom_header_and_same_origin(method, path):
    client = TestClient(api.app)
    send = getattr(client, method)
    assert send("/api/v1/account" + path).status_code == 403
    assert (
        send(
            "/api/v1/account" + path, headers={**HEADERS, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("password", ["secret-too-short", "tiny", "x" * 129])
def test_passwords_never_echo_in_validation_errors(password):
    client = TestClient(api.app)
    response = client.post(
        "/api/v1/account/register",
        headers=HEADERS,
        json={"username": "bad username", "password": password},
    )
    assert response.status_code == 422
    assert password not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_auth_limit_cannot_be_reset_with_cookies(monkeypatch):
    calls = []
    monkeypatch.setattr(api.accounts, "authenticate", lambda *args: calls.append(args) and None)
    for _ in range(20):
        assert (
            TestClient(api.app)
            .post(
                "/api/v1/account/login",
                headers=HEADERS,
                json={"username": "missing", "password": PASSWORD},
            )
            .status_code
            == 401
        )
    response = TestClient(api.app).post(
        "/api/v1/account/login", headers=HEADERS, json={"username": "missing", "password": PASSWORD}
    )
    assert response.status_code == 429 and len(calls) == 20


def test_dropoff_is_private_idempotent_and_location_free(account):
    owner, stranger = client_for(account), client_for(account, "bob-id")
    ticket = account.ticket("alice-id", ["empty_glass_packaging", "ordinary_residual"])
    payload = json.loads(base64.urlsafe_b64decode(ticket.split(".")[0]))
    assert set(payload) == {"id", "user", "materials", "expires"}
    assert (
        stranger.post(
            "/api/v1/account/dropoffs", headers=HEADERS, json={"ticket": ticket}
        ).status_code
        == 422
    )
    first = owner.post("/api/v1/account/dropoffs", headers=HEADERS, json={"ticket": ticket})
    assert first.status_code == 200 and first.json()["recorded"]
    assert first.json()["badges"] == {"first_dropoff": True, "ten_dropoffs": False}
    second = owner.post("/api/v1/account/dropoffs", headers=HEADERS, json={"ticket": ticket})
    assert not second.json()["recorded"] and second.json()["recycling_count"] == 1
    assert set(second.json()["history"][0]) == {"materials", "created", "recycling"}
    assert not stranger.get("/api/v1/account/me").json()["history"]
    assert owner.get("/api/v1/review/reports").status_code == 401


def test_tampered_expired_and_unsigned_tickets_rejected(account, monkeypatch):
    valid = account.ticket("alice-id", ["glass"])
    for ticket in [valid + "x", "forged", valid.replace(".", "x.", 1)]:
        with pytest.raises(ValueError):
            account.complete("alice-id", ticket)
    future = time.time() + 86401
    monkeypatch.setattr("smart_recycling.accounts.time.time", lambda: future)
    with pytest.raises(ValueError):
        account.complete("alice-id", valid)


def test_concurrent_replay_counts_once_and_survives_restart(account):
    ticket = account.ticket("alice-id", ["glass"])
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(lambda _: account.complete("alice-id", ticket), range(8))) == 1
    reopened = Accounts(api.community_store)
    assert reopened.summary({"id": "alice-id", "username": "alice"})["recycling_count"] == 1


def test_general_not_counted_and_tenth_badge_persistent(account):
    account.complete("alice-id", account.ticket("alice-id", ["ordinary_residual"]))
    assert account.summary({"id": "alice-id"})["recycling_count"] == 0
    for number in range(1, 11):
        account.complete("alice-id", account.ticket("alice-id", ["wearable_clothes"]))
        summary = account.summary({"id": "alice-id"})
        assert summary["recycling_count"] == number
        assert summary["badges"]["ten_dropoffs"] == (number == 10)
    assert len(summary["history"]) == 11


def test_delete_requires_password_and_removes_all_owned_history_and_sessions(account):
    client = client_for(account)
    token = client.cookies.get("sra_session")
    other_session = account.start_session("alice-id", "")
    account.complete("alice-id", account.ticket("alice-id", ["glass"]))
    wrong = client.request(
        "DELETE", "/api/v1/account", headers=HEADERS, json={"password": "wrong-password-for-test"}
    )
    assert wrong.status_code == 401
    assert (
        client.request(
            "DELETE", "/api/v1/account", headers=HEADERS, json={"password": PASSWORD}
        ).status_code
        == 204
    )
    assert account.user(token) is None and account.user(other_session) is None
    with api.community_store.connection() as db:
        assert not db.execute("SELECT * FROM dropoffs WHERE user_id='alice-id'").fetchall()
        assert db.execute("SELECT * FROM accounts WHERE id='bob-id'").fetchone()


@pytest.mark.parametrize("mode", ["walking", "driving"])
def test_real_route_issues_tickets_only_for_signed_in_users(account, monkeypatch, mode):
    planner, _ = service([site("both", (GLASS, PAPER))])
    monkeypatch.setattr(api, "route_service", planner)
    payload = request(mode).model_dump()
    guest = TestClient(api.app).post("/api/v1/trips", json=payload)
    assert guest.status_code == 200 and guest.json()["stops"][0]["completion_ticket"] is None
    client = client_for(account)
    route = client.post("/api/v1/trips", json=payload)
    assert route.status_code == 200
    ticket = route.json()["stops"][0]["completion_ticket"]
    assert ticket
    completed = client.post("/api/v1/account/dropoffs", headers=HEADERS, json={"ticket": ticket})
    assert completed.json()["recycling_count"] == 1


def test_anonymous_dropoff_and_oversized_password_body_rejected():
    client = TestClient(api.app)
    assert (
        client.post(
            "/api/v1/account/dropoffs", headers=HEADERS, json={"ticket": "forged"}
        ).status_code
        == 401
    )
    response = client.post(
        "/api/v1/account/register",
        headers=HEADERS,
        json={"username": "test", "password": "x" * 20000},
    )
    assert response.status_code == 413


def test_achievements_use_entire_history_not_latest_fifty(account):
    now = time.time()
    materials = ["glass", "plastic_metal", "paper_tetrapak", "clothes", "electronics"]
    with api.community_store.connection() as db:
        for i in range(60):
            db.execute(
                "INSERT INTO dropoffs VALUES (?,?,?,?,?)",
                (
                    f"history-{i}",
                    "alice-id",
                    json.dumps([materials[i] if i < 5 else "glass"]),
                    now - (60 - i) * 86400,
                    1,
                ),
            )
    summary = account.summary({"id": "alice-id"})
    assert len(summary["history"]) == 50 and summary["history_count"] == 60
    assert summary["activity"]["material_counts"]["electronics"] == 1
    awards = {a["id"]: a for a in summary["achievements"]}
    assert len(awards) == 6 and all(a["earned_at"] is not None for a in awards.values())
    assert awards["twentyfive_dropoffs"]["earned_at"] == now - 36 * 86400
    assert awards["full_circle"]["earned_at"] == now - 56 * 86400
    assert awards["twentyfive_dropoffs"]["progress"] == 25
    assert len(summary["activity"]["days"]) == 28
    assert sum(day["count"] for day in summary["activity"]["days"]) == 27


def test_empty_general_and_replayed_dropoffs_do_not_inflate_new_achievements(account):
    assert all(a["earned_at"] is None for a in account.summary({"id": "alice-id"})["achievements"])
    account.complete("alice-id", account.ticket("alice-id", ["ordinary_residual"]))
    empty = account.summary({"id": "alice-id"})
    assert not empty["activity"]["material_counts"]
    assert not sum(d["count"] for d in empty["activity"]["days"])
    assert all(a["progress"] == 0 for a in empty["achievements"])
    ticket = account.ticket(
        "alice-id", ["wearable_clothes", "small_electronics", "ordinary_residual"]
    )
    account.complete("alice-id", ticket)
    account.complete("alice-id", ticket)
    summary = account.summary({"id": "alice-id"})
    earned = {a["id"] for a in summary["achievements"] if a["earned_at"] is not None}
    assert earned == {"first_dropoff", "second_life", "tech_return"}
    assert summary["activity"]["material_counts"] == {"clothes": 1, "electronics": 1}
    assert sum(d["count"] for d in summary["activity"]["days"]) == 1
