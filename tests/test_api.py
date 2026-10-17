import io

from fastapi.testclient import TestClient
from PIL import Image

from smart_recycling import api
from smart_recycling.vision import (
    PhotoSuggestion,
    PhotoSuggestionsResponse,
    SuggestionStatus,
    VisibleCondition,
)

app = api.app

client = TestClient(app)


def test_health_reports_loaded_components() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model_version": "policy-rules-v3",
        "text_suggestion_model": "unavailable",
        "macedonian_suggestion_model": "unavailable",
        "supported_languages": "en,mk",
        "site_count": 1583,
        "asset_count": 1596,
        "legacy_seed_site_count": 4,
        "nearest_data_source": "synthetic",
    }


def test_classify_contract() -> None:
    response = client.post("/api/v1/classify", json={"text": "wine bottle"})

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "glass"
    assert body["confidence_kind"] == "heuristic_score"
    assert body["abstained"] is False
    assert body["model_version"] == "policy-rules-v3"
    assert body["status"] == "confirm_condition"
    assert body["routing_available"] is False


def test_nearest_contract() -> None:
    response = client.post(
        "/api/v1/nearest",
        json={"material": "paper_tetrapak", "latitude": 41.9948, "longitude": 21.4420},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["site"]["id"] == "demo-003"
    assert body["distance_m"] < 20
    assert body["synthetic"] is True


def test_special_waste_cannot_be_used_as_a_collection_material() -> None:
    response = client.post(
        "/api/v1/nearest",
        json={"material": "special_unsupported", "latitude": 41.99, "longitude": 21.43},
    )

    assert response.status_code == 422


def _photo_fixture() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (20, 20), "green").save(output, format="PNG")
    return output.getvalue()


def test_photo_suggestions_contract_and_no_store(monkeypatch) -> None:
    class FakeVisionService:
        configured = True

        async def suggest(self, raw: bytes, content_type: str | None) -> PhotoSuggestionsResponse:
            assert raw.startswith(b"\x89PNG")
            assert content_type == "image/png"
            return PhotoSuggestionsResponse(
                items=[
                    PhotoSuggestion(
                        description="clear glass jar",
                        item_kind="empty_glass_packaging",
                        category="glass",
                        visible_condition=VisibleCondition.APPEARS_EMPTY_CLEAN,
                        status=SuggestionStatus.CANDIDATE,
                        reason="It appears to be glass packaging.",
                    )
                ],
                model_version="openai:fixture-model",
                policy_version="skopje-policy-v1",
                message="Review the suggestion.",
            )

    monkeypatch.setattr(api, "vision_service", FakeVisionService())
    response = client.post(
        "/api/v1/photo-suggestions",
        content=_photo_fixture(),
        headers={"Content-Type": "image/png"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["items"][0]["item_kind"] == "empty_glass_packaging"
    assert response.json()["requires_user_confirmation"] is True


def test_photo_suggestions_require_server_key(monkeypatch) -> None:
    class UnconfiguredVisionService:
        configured = False

    monkeypatch.setattr(api, "vision_service", UnconfiguredVisionService())
    response = client.post(
        "/api/v1/photo-suggestions",
        content=_photo_fixture(),
        headers={"Content-Type": "image/png"},
    )

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["detail"]["code"] == "vision_not_configured"
