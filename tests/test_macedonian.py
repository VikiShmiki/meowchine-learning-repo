"""Bilingual parity, hazard precedence, API locale and isolated vision contracts."""

import asyncio
import csv
import hashlib
import json
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from smart_recycling import api
from smart_recycling.guidance import CHOICES
from smart_recycling.language import latin, policy_text
from smart_recycling.localization import language_from_header, request_language
from smart_recycling.minilm import MiniLMError
from smart_recycling.multilingual import MultilingualSuggester
from smart_recycling.vision import ModelPhotoItem, OpenAIVisionProvider, VisionService

CASES = json.loads((Path(__file__).parent / "fixtures/macedonian.json").read_text("utf-8"))


@pytest.mark.parametrize("row", CASES, ids=lambda row: row["en"])
@pytest.mark.parametrize("script", ["cyrillic", "latin"])
def test_macedonian_matches_english_policy_and_confirmation(row, script):
    text = row["mk"] if script == "cyrillic" else latin(row["mk"].casefold())
    answer = api.classifier.decide(text)
    english = api.classifier.decide(row["en"])
    assert answer.status == english.status == row["status"]
    assert answer.item_kind == english.item_kind == row["kind"]
    assert answer.category == english.category
    assert answer.evidence_ids == english.evidence_ids
    if answer.status == "confirm_condition":
        confirmed = api.classifier.decide(text, row["kind"], True)
        assert confirmed.status == "ready_for_site_matching"
        assert confirmed.confidence_kind == "manual_selection"
    elif answer.status in {"specialist", "held"}:
        override = api.classifier.decide(text, "empty_plastic_bottle", True)
        assert override.status != "ready_for_site_matching"


@pytest.mark.parametrize(
    "text", ["пластично шише со батерија", "plastic bottle со хемикалии", "надуена battery"]
)
def test_mixed_language_hazards_override_manual_selection(text):
    assert api.classifier.decide(text, "empty_plastic_bottle", True).status == "specialist"


def test_normalization_keeps_unknown_words_and_boundaries():
    assert policy_text("непознато Х123") == "непознато х123"
    assert policy_text("батеријата") == "battery"
    assert policy_text("батеријатах") == "батеријатах"


@pytest.mark.parametrize(
    "header,expected",
    [
        ("mk-MK,mk;q=0.9,en;q=0.5", "mk"),
        ("mk;q=0,en", "en"),
        ("en;q=0.1,mk;q=0.8", "mk"),
        ("fr", "en"),
        ("mk;q=wrong,en", "en"),
    ],
)
def test_locale_negotiation(header, expected):
    assert language_from_header(header) == expected


def test_api_localizes_copy_but_preserves_machine_contract():
    with TestClient(api.app) as client:
        mk = client.post(
            "/api/v1/classify",
            json={"text": "празно стаклено шише"},
            headers={"Accept-Language": "mk-MK"},
        )
        en = client.post("/api/v1/classify", json={"text": "празно стаклено шише"})
        assert mk.status_code == en.status_code == 200
        assert mk.json()["choices"][0]["label"] == "Празно стаклено шише или тегла"
        assert en.json()["choices"][0]["label"] == CHOICES["empty_glass_packaging"][0]
        assert mk.json()["item_kind"] == en.json()["item_kind"]
        assert "Accept-Language" in mk.headers["vary"]
        explicit = client.post(
            "/api/v1/classify",
            json={"text": "glass bottle", "language": "en"},
            headers={"Accept-Language": "mk"},
        )
        assert explicit.json() == en.json()
        assert (
            client.post("/api/v1/classify", json={"text": "glass", "language": "xx"}).status_code
            == 422
        )


def test_macedonian_photo_hazard_in_reason_cannot_be_overridden():
    item = ModelPhotoItem(
        description="пластично шише",
        item_kind="empty_plastic_bottle",
        visible_condition="appears_empty_clean",
        reason="содржи хемикалии",
    )
    suggestion = VisionService._suggestion(item)
    assert suggestion.status == "specialist"
    assert suggestion.item_kind == "other"


@pytest.mark.parametrize(
    "kind,description",
    [
        ("ordinary_residual", "употребено марамче"),
        ("small_electronics", "полнач"),
        ("wearable_clothes", "чиста маица"),
        ("electronics", "фрижидер"),
        ("empty_glass_packaging", "стаклено шише"),
    ],
)
def test_macedonian_photo_uses_same_policy_guards(kind, description):
    item = ModelPhotoItem(
        description=description,
        item_kind=kind,
        visible_condition="appears_empty_clean",
        reason="видлив предмет",
    )
    assert VisionService._suggestion(item).status == "candidate"


def test_vision_requests_macedonian_without_changing_json_enums():
    async def run():
        def handle(request):
            body = json.loads(request.content)
            assert "Macedonian using Cyrillic" in body["instructions"]
            assert body["store"] is False
            assert (
                "empty_glass_packaging"
                in body["text"]["format"]["schema"]["properties"]["items"]["items"]["properties"][
                    "item_kind"
                ]["enum"]
            )
            return httpx.Response(
                200,
                json={
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": '{"items": []}'}],
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            provider = OpenAIVisionProvider("fake", "test-model", client=client)
            token = request_language.set("mk")
            try:
                result = await provider.analyze("data:image/jpeg;base64,test")
                assert result.items == []
            finally:
                request_language.reset(token)

    asyncio.run(run())


def test_multilingual_model_rejects_invalid_embeddings():
    class InvalidEncoder:
        def encode(self, sentences, **kwargs):
            return np.zeros((len(sentences), 384))

    with pytest.raises(MiniLMError):
        MultilingualSuggester(InvalidEncoder())


def test_macedonian_manual_test_is_hash_linked_to_all_100_english_rows():
    root = Path(__file__).resolve().parents[1] / "data/evaluation"
    english = list(csv.DictReader((root / "manual_test.csv").open(encoding="utf-8")))
    macedonian = list(csv.DictReader((root / "manual_test_mk.csv").open(encoding="utf-8")))
    expected = {
        hashlib.sha256(row["text"].encode()).hexdigest(): row["target_label"] for row in english
    }
    assert len(macedonian) == len({row["text"] for row in macedonian}) == 100
    assert {row["english_text_sha256"]: row["target_label"] for row in macedonian} == expected
    assert all(row["translation_review_status"] == "needs_native_review" for row in macedonian)


@pytest.mark.parametrize("hazard", ["хемиско средство", "хемиска течност", "хемикалиите"])
def test_chemical_inflections_block_packaging_confirmation(hazard):
    answer = api.classifier.decide("пластично шише со " + hazard, "empty_plastic_bottle", True)
    assert answer.status == "specialist"


def test_macedonian_account_validation_is_translated_and_never_echoes_password():
    with TestClient(api.app) as client:
        response = client.post(
            "/api/v1/account/register",
            json={"username": "x", "password": "secret"},
            headers={"Accept-Language": "mk", "X-Goodsort-Action": "1"},
        )
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Проверете го внесот")
    assert "secret" not in response.text
