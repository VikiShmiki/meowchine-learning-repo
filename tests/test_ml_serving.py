"""Measure only suggestions reached through the actual policy decision flow."""

import json
from pathlib import Path

import numpy as np

from smart_recycling.data.ml_evaluation import select_gate
from smart_recycling.data.ml_serving import evaluate_serving, policy_fallback_mask
from smart_recycling.domain import WasteCategory
from smart_recycling.minilm import CategorySuggestion
from smart_recycling.object_models import LABELS

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "data/policy/skopje_v2.json").read_text())


class GlassSuggester:
    model_version = "test"

    def __init__(self):
        self.calls = []

    def suggest(self, text):
        self.calls.append(text)
        return CategorySuggestion(WasteCategory.GLASS, 0.99, self.model_version)


def examples():
    return [
        dict(text="glass bottle", label="glass", group="known", variant="0"),
        dict(text="glass pesto jar", label="glass", group="fallback", variant="0"),
        dict(text="mystery object", label="", group="unknown", variant="1"),
        dict(text="glass bottle and plastic bottle", label="", group="mixed", variant="0"),
    ]


def test_real_policy_subset_and_incremental_suggestion_value():
    rows = examples()
    assert policy_fallback_mask(rows, POLICY, 0.85).tolist() == [False, True, True, False]
    model = GlassSuggester()
    report = evaluate_serving(rows, model, POLICY, 0.85)
    assert model.calls == ["glass pesto jar", "mystery object"]
    summary = report["overall"]
    assert summary["fallback_supported_rows"] == 1
    assert summary["fallback_held_rows"] == 1
    assert summary["accepted_suggestions"] == 2
    assert summary["correct_suggestions"] == 1
    assert summary["held_false_suggestions"] == 1
    assert summary["accepted_accuracy"] == 0.5
    assert summary["rules_supported_correct"] == 1
    assert summary["rules_plus_suggestions_supported_correct"] == 2
    assert report["by_variant"]["0"]["accepted_accuracy"] == 1
    assert report["by_variant"]["1"]["held_false_suggestions"] == 1


def test_calibration_excludes_cases_blocked_before_ml():
    rows = [examples()[1], examples()[3]]
    classes = sorted(LABELS)
    scores = np.tile(np.eye(6)[classes.index("glass")], (2, 1))
    # A model's confident answer on an already-held mixed request is never served.
    assert select_gate(rows, scores, np.ones(2), classes) == (1.01, 1.01)
    mask = policy_fallback_mask(rows, POLICY, 0.85)
    eligible = [row for row, called in zip(rows, mask, strict=True) if called]
    assert select_gate(eligible, scores[mask], np.ones(2)[mask], classes) == (0.99, 0.9)


def test_no_fallback_has_explicit_empty_denominators():
    model = GlassSuggester()
    report = evaluate_serving([examples()[0]], model, POLICY, 0.85)
    assert not model.calls
    assert report["overall"]["accepted_accuracy"] is None
    assert report["overall"]["concept_weighted"]["supported_coverage"] is None
