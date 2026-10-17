"""Community persistence, routing, moderation and paid-provider boundaries."""

import io
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from test_routing import GLASS, PAPER, request, service, site

from smart_recycling import api
from smart_recycling.community import AllowanceExceeded, CommunityStore
from smart_recycling.routing_models import RoutingError


@pytest.fixture
def store(tmp_path):
    return CommunityStore(tmp_path / "store.sqlite3")


def test_allowance_survives_restart_and_does_not_partially_reserve(store):
    store.reserve("vision", "one", 2, 1, 1)
    reopened = CommunityStore(store.path)
    with pytest.raises(AllowanceExceeded):
        reopened.reserve("vision", "one", 2, 1, 1)
    reopened.reserve("vision", "two", 2, 1, 1)
    with pytest.raises(AllowanceExceeded):
        reopened.reserve("vision", "three", 2, 1, 1)


def test_allowance_atomic_under_concurrent_requests(store):
    def reserve(index):
        try:
            store.reserve("vision", str(index), 3, 1, 1)
            return True
        except AllowanceExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(12))) == 3


def test_pending_private_review_shared_expiry_and_retention(store):
    report = store.submit("container", "alice", asset_id="glass", condition="full")
    assert store.statuses("alice")[0]["glass"]["condition"] == "full"
    assert not store.statuses("bob")[0]
    assert store.moderate(report["id"], "approved")
    assert store.statuses("bob")[0]["glass"]["source"] == "reviewed_community"
    with store.connection() as db:
        db.execute("UPDATE reports SET expires=?", (time.time() - 1,))
    assert not store.statuses("alice")[0]
    with store.connection() as db:
        db.execute("UPDATE reports SET created=?", (time.time() - 31 * 86400,))
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0


def test_personal_available_cannot_override_reviewed_problem(store):
    report = store.submit("container", "one", asset_id="glass", condition="damaged")
    store.moderate(report["id"], "approved")
    store.submit("container", "two", asset_id="glass", condition="available")
    assert store.statuses("two")[0]["glass"]["condition"] == "damaged"


def test_new_reviewed_available_supersedes_old_personal_problem(store):
    store.submit("container", "one", asset_id="glass", condition="full")
    report = store.submit("container", "two", asset_id="glass", condition="available")
    store.moderate(report["id"], "approved")
    assert store.statuses("one")[0]["glass"]["condition"] == "available"


def test_duplicate_report_and_signed_visitors(store):
    first = store.submit("container", "one", asset_id="glass", condition="full")
    assert store.submit("container", "one", asset_id="glass", condition="full")["id"] == first["id"]
    visitor, cookie = store.visitor("")
    assert store.visitor(cookie) == (visitor, cookie)
    assert store.visitor(cookie + "forged")[0] != visitor
    assert store.visitor("")[0] != visitor


@pytest.mark.parametrize("mode", ["walking", "driving"])
@pytest.mark.parametrize("condition", ["full", "damaged", "inaccessible"])
def test_problem_removes_only_affected_asset_and_preserves_source(mode, condition):
    glass, paper = site("glass", (GLASS,)), site("paper", (PAPER,))
    combined = glass.model_copy(update={"assets": glass.assets + paper.assets})
    alternative = site("alternative", (GLASS,), longitude=21.405)
    planner, calls = service([combined, alternative])
    response = planner.plan(
        request(mode), statuses={"glass-asset": {"condition": condition}}, status_version="v2"
    )
    assets = {asset for stop in response.stops for asset in stop.asset_ids}
    assert assets == {"paper-asset", "alternative-asset"}
    assert planner.snapshot.sites[0].assets[0].operational_status == "unknown"
    assert response.status_version == "v2"
    assert len(calls) == 2


def test_no_alternative_never_omits_waste_or_calls_provider():
    planner, calls = service([site("only", (GLASS, PAPER))])
    with pytest.raises(RoutingError, match="No explicitly accepting"):
        planner.plan(request(), statuses={"only-asset": {"condition": "full"}})
    assert not calls


def test_available_report_does_not_reopen_source_closed_asset():
    planner, calls = service([site("closed", (GLASS, PAPER), status="closed")])
    with pytest.raises(RoutingError):
        planner.plan(request(), statuses={"closed-asset": {"condition": "available"}})
    assert not calls


def test_report_api_visitors_are_separate_and_moderation_is_protected(monkeypatch):
    owner, stranger = TestClient(api.app), TestClient(api.app)
    asset_id = next(iter(api.community_assets))
    result = owner.post(
        "/api/v1/container-reports", json={"asset_id": asset_id, "condition": "full"}
    )
    assert result.status_code == 201
    assert result.headers["cache-control"] == "no-store"
    assert asset_id in owner.get("/api/v1/container-statuses").json()["statuses"]
    assert asset_id not in stranger.get("/api/v1/container-statuses").json()["statuses"]
    identifier = result.json()["id"]
    endpoint = f"/api/v1/review/reports/{identifier}"
    assert stranger.patch(endpoint, json={"state": "approved"}).status_code == 401
    monkeypatch.setenv("SRA_REVIEW_TOKEN", "test-" + "r" * 40)
    headers = {"Authorization": "Bearer test-" + "r" * 40}
    assert stranger.patch(endpoint, json={"state": "approved"}, headers=headers).status_code == 200
    assert asset_id in stranger.get("/api/v1/container-statuses").json()["statuses"]
    assert (
        owner.post(
            "/api/v1/container-reports", json={"asset_id": "missing", "condition": "full"}
        ).status_code
        == 404
    )


def test_dumping_approval_private_photo_and_upload_validation(monkeypatch):
    client, stranger = TestClient(api.app), TestClient(api.app)
    report = client.post(
        "/api/v1/dumping-reports",
        json={"latitude": 42, "longitude": 21.43, "description": "Discarded bags"},
    )
    assert report.status_code == 201
    identifier = report.json()["id"]
    assert not stranger.get("/api/v1/dumping-reports").json()["reports"]
    output = io.BytesIO()
    picture = Image.new("RGB", (200, 100), "blue")
    exif = Image.Exif()
    exif[270] = "private metadata"
    picture.save(output, format="JPEG", exif=exif)
    upload = f"/api/v1/dumping-reports/{identifier}/photo"
    assert stranger.post(upload, content=output.getvalue()).status_code == 404
    assert client.post(upload, content=b"not an image").status_code == 422
    assert client.post(upload, content=output.getvalue()).status_code == 204
    monkeypatch.setenv("SRA_REVIEW_TOKEN", "test-" + "r" * 40)
    headers = {"Authorization": "Bearer test-" + "r" * 40}
    private = f"/api/v1/review/reports/{identifier}/photo"
    assert stranger.get(private).status_code == 401
    response = client.get(private, headers=headers)
    assert response.headers["cache-control"] == "no-store"
    with Image.open(io.BytesIO(response.content)) as image:
        assert not image.getexif()
    endpoint = f"/api/v1/review/reports/{identifier}"
    client.patch(endpoint, json={"state": "approved"}, headers=headers)
    public = stranger.get("/api/v1/dumping-reports").json()["reports"][0]
    assert "client" not in public and "photo" not in public
    client.patch(endpoint, json={"state": "cleared"}, headers=headers)
    assert stranger.get("/api/v1/dumping-reports").json()["reports"][0]["state"] == "cleared"


def test_request_bounds_cross_origin_and_skoped_coordinates():
    client = TestClient(api.app)
    assert client.post("/api/v1/dumping-reports", content=b"x" * 20000).status_code == 413
    assert (
        client.post(
            "/api/v1/dumping-reports", json={}, headers={"Origin": "https://other.example"}
        ).status_code
        == 403
    )
    for payload in [
        {"latitude": 0, "longitude": 0, "description": "Elsewhere"},
        {"latitude": 42, "longitude": 21.43, "description": "   "},
    ]:
        assert client.post("/api/v1/dumping-reports", json=payload).status_code == 422


def test_vision_limit_rejects_before_calling_provider_and_preserves_manual(monkeypatch):
    monkeypatch.setenv("SRA_VISION_DAILY_LIMIT", "0")

    class FakeVision:
        configured = True

        async def suggest(self, *args):
            pytest.fail("Paid provider must not be called")

    monkeypatch.setattr(api, "vision_service", FakeVision())
    client = TestClient(api.app)
    response = client.post("/api/v1/photo-suggestions", content=b"photo")
    assert response.status_code == 429 and response.headers["retry-after"]
    assert client.post("/api/v1/classify", json={"text": "glass jar"}).status_code == 200


def test_reports_cannot_bypass_network_quota_by_changing_cookie():
    asset_id = next(iter(api.community_assets))
    for _ in range(10):
        assert (
            TestClient(api.app)
            .post("/api/v1/container-reports", json={"asset_id": asset_id, "condition": "full"})
            .status_code
            == 201
        )
    assert (
        TestClient(api.app)
        .post("/api/v1/container-reports", json={"asset_id": asset_id, "condition": "full"})
        .status_code
        == 429
    )
