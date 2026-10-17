"""Behavioral gates for the evaluated classifier and manual recovery contract."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_recycling.api import app
from smart_recycling.domain import WasteCategory
from smart_recycling.guidance import GuidanceClassifier, load_classifier
from smart_recycling.minilm import CategorySuggestion, MiniLMError

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data/policy/skopje_v2.json"
ARTIFACT = ROOT / "data/classifier/rules-v3.json"
client = TestClient(app)


@pytest.mark.parametrize(
    "text",
    [
        "battery in a glass bottle",
        "plastic bottle of pesticide",
        "paint in a metal can",
        "leaking rechargeable battery",
        "paper packaging containing a syringe",
    ],
)
def test_manual_recycling_cannot_override_specialist_signal(text: str) -> None:
    body = client.post(
        "/api/v1/classify",
        json={
            "text": text,
            "manual_kind": "empty_glass_packaging",
            "condition_confirmed": True,
        },
    ).json()
    assert body["status"] == "specialist"
    assert body["category"] == "special_unsupported"
    assert body["facility_ids"] == []
    assert body["routing_available"] is False


@pytest.mark.parametrize(
    "text", ["used diaper", "greasy cardboard", "paper cup", "not empty bottle"]
)
def test_held_conditions_cannot_be_confirmed_into_recycling(text: str) -> None:
    body = client.post(
        "/api/v1/classify",
        json={
            "text": text,
            "manual_kind": "clean_paper",
            "condition_confirmed": True,
        },
    ).json()
    assert body["category"] is None
    assert body["status"] == "held"


def test_abstention_has_working_manual_recovery() -> None:
    body = client.post("/api/v1/classify", json={"text": "a jar"}).json()
    assert body["status"] == "clarify"
    assert body["abstained"] is True
    assert "empty_glass_packaging" in {option["id"] for option in body["choices"]}
    selected = {"text": "a jar", "manual_kind": "empty_glass_packaging"}
    assert client.post("/api/v1/classify", json=selected).json()["status"] == "confirm_condition"
    body = client.post("/api/v1/classify", json={**selected, "condition_confirmed": True}).json()
    assert body["status"] == "ready_for_site_matching"
    assert body["confidence_kind"] == "manual_selection"
    assert body["evidence_ids"]
    assert not body["routing_available"]


def test_confirmation_does_not_implicitly_select_or_coerce() -> None:
    for payload in [
        {"text": "bottle", "condition_confirmed": True},
        {"text": "bottle", "manual_kind": "general"},
        {"text": "bottle", "manual_kind": "clean_paper", "condition_confirmed": "yes"},
        {"text": " "},
    ]:
        assert client.post("/api/v1/classify", json=payload).status_code == 422


def test_specialist_contact_is_not_a_facility() -> None:
    body = client.post("/api/v1/classify", json={"text": "old charger"}).json()
    assert body["contact_url"] == "https://nulaotpad.com.mk/prijavi-e-otpad"
    assert body["facility_ids"] == ["ewaste-karpos-yard", "ewaste-east-gate-mall"]
    assert body["status"] == "confirm_condition"
    unknown = client.post("/api/v1/classify", json={"text": "old pesticide"}).json()
    assert unknown["contact_url"] is None
    assert unknown["facility_ids"] == []
    mixed = client.post("/api/v1/classify", json={"text": "paint and a battery"}).json()
    assert mixed["contact_url"] is None


def test_manual_specialist_selection_is_not_model_confidence() -> None:
    body = client.post(
        "/api/v1/classify", json={"text": "unknown device", "manual_kind": "electronics"}
    ).json()
    assert body["status"] == "confirm_condition"
    assert body["confidence_kind"] == "manual_selection"
    assert body["confidence"] == 0


def test_generic_materials_and_mixed_items_need_clarification() -> None:
    for text in ("glass", "plastic", "a jar", "glass bottle and plastic bottle"):
        body = client.post("/api/v1/classify", json={"text": text}).json()
        assert body["status"] == "clarify"
        assert body["category"] is None


def test_learned_category_is_only_a_broad_suggestion() -> None:
    class FakeSuggester:
        model_version = "test-minilm"

        def suggest(self, text: str) -> CategorySuggestion:
            assert text == "breakfast box"
            return CategorySuggestion(
                category=WasteCategory.PAPER_TETRAPAK,
                score=0.87,
                model_version=self.model_version,
            )

    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    classifier = GuidanceClassifier(policy, 0.85, category_suggester=FakeSuggester())

    answer = classifier.decide("breakfast box")

    assert answer.status == "clarify"
    assert answer.abstained is True
    assert answer.category is None
    assert answer.suggested_category is WasteCategory.PAPER_TETRAPAK
    assert answer.suggestion_score == 0.87
    assert answer.suggestion_model_version == "test-minilm"
    assert answer.choices[0].id in {"clean_cardboard", "clean_paper", "empty_tetrapak"}


def test_hazard_and_condition_rules_run_before_learned_suggestion() -> None:
    class FailingSuggester:
        model_version = "must-not-run"

        def suggest(self, text: str):
            raise AssertionError("learned suggestion bypassed a policy rule")

    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    classifier = GuidanceClassifier(policy, 0.85, category_suggester=FailingSuggester())

    assert classifier.decide("old battery").status == "specialist"
    assert classifier.decide("greasy breakfast box").status == "held"


def test_learned_inference_failure_preserves_manual_clarification() -> None:
    class BrokenSuggester:
        model_version = "broken-minilm"

        def suggest(self, text: str):
            raise MiniLMError("offline")

    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    classifier = GuidanceClassifier(policy, 0.85, category_suggester=BrokenSuggester())

    answer = classifier.decide("breakfast box")

    assert answer.status == "clarify"
    assert answer.suggested_category is None
    assert answer.choices


def test_artifact_must_match_current_rules_and_policy(tmp_path) -> None:
    assert isinstance(load_classifier(ARTIFACT, POLICY), GuidanceClassifier)
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    artifact["code_sha256"] = "0" * 64
    path = tmp_path / "stale.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        load_classifier(path, POLICY)


def test_missing_class_is_not_reported_as_measured_success() -> None:
    report = json.loads((ARTIFACT.parent / "evaluation-v3.json").read_text(encoding="utf-8"))
    assert report["manual_test"]["per_class"]["general"]["support"] == 0
    assert report["manual_test"]["per_class"]["general"]["f1"] is None
    assert report["manual_test_scope"]["held_queries"] == 41
    selected = report["validation"]
    assert selected["answered_accuracy"] >= 0.95
    assert selected["held_false_answers"] == 0
    assert selected["coverage"] >= 0.5


def test_evaluation_reproduces_committed_artifact_and_quality(tmp_path) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/evaluate_guidance.py"), "--out", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert json.loads((tmp_path / ARTIFACT.name).read_text()) == json.loads(ARTIFACT.read_text())

    def deterministic(value):
        if isinstance(value, dict):
            return {
                key: deterministic(item)
                for key, item in value.items()
                if key not in {"p95_predict_ms", "latency_environment"}
            }
        if isinstance(value, list):
            return [deterministic(item) for item in value]
        return value

    name = "evaluation-v3.json"
    actual = json.loads((tmp_path / name).read_text())
    expected = json.loads((ARTIFACT.parent / name).read_text())
    assert deterministic(actual) == deterministic(expected)
