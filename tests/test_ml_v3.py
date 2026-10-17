"""ML regression checks for leakage, provenance, numerical parity and abstention."""

import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from smart_recycling.data.ml_v3 import prepare
from smart_recycling.linear_head import LinearHead
from smart_recycling.object_models import LABELS

ROOT = Path(__file__).resolve().parents[1]


def payload():
    rng = np.random.default_rng(42)
    x = rng.normal(size=(60, 384))
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    y = np.tile(sorted(LABELS), 10)
    model = LogisticRegression().fit(x, y)
    data = dict(
        classes=model.classes_.tolist(),
        coef=model.coef_.tolist(),
        intercept=model.intercept_.tolist(),
        prototypes=x[:6].tolist(),
        temperature=1,
        threshold=0.8,
        similarity_threshold=0.6,
    )
    return model, x, data


def test_json_head_matches_training_library_and_abstains():
    model, x, data = payload()
    head = LinearHead(json.loads(json.dumps(data)))
    np.testing.assert_allclose(head.predict_proba(x), model.predict_proba(x), atol=1e-12)
    assert not head.accepts(x, head.predict_proba(x)).any()
    data.update(threshold=0, similarity_threshold=0)
    assert LinearHead(data).accepts(x[:6], head.predict_proba(x[:6])).all()
    data.update(threshold=1.01)
    assert not LinearHead(data).accepts(x, head.predict_proba(x)).any()


@pytest.mark.parametrize(
    "field,value",
    [
        ("temperature", 0),
        ("temperature", float("nan")),
        ("threshold", float("nan")),
        ("coef", [[1]]),
        ("prototypes", [[0] * 384]),
        ("classes", ["glass"] * 6),
        ("intercept", [float("inf")] * 6),
    ],
)
def test_invalid_head_fails_closed(field, value):
    _, _, data = payload()
    data[field] = value
    with pytest.raises(ValueError):
        LinearHead(data)


def test_source_english_survives_without_translation_and_reserved_text_is_removed(tmp_path):
    source = tmp_path / "source/data/processed"
    source.mkdir(parents=True)
    (source / "dataset_a.csv").write_text(
        "text,original_label,item_group\n"
        "an apple phone charger,PHONE CHARGER,phone_charger\n"
        "eco-friendly packaging,PAPER PACKAGING,paper\n"
        "glass champagne bottle,GLASS BOTTLE,bottle\n"
    )
    rows, manifest = prepare(ROOT, tmp_path / "source", tmp_path / "output")
    original = [r for r in rows if r["source"] == "dataset_a"]
    assert any(r["text"] == "an apple phone charger" for r in original)
    assert all(r["language"] == "en" for r in original)
    assert not any(r["text"] == "eco-friendly packaging" for r in original)
    assert manifest["exclusions"]["material_or_object_not_explicit"] == 1
    groups = {
        role: {r["group"] for r in rows if r["role"] == role}
        for role in ("train", "tune", "calibration", "test")
    }
    for left in groups:
        for right in groups:
            if left != right:
                assert not groups[left] & groups[right]
    for role in groups:
        assert {r["label"] for r in rows if r["role"] == role and r["label"]} == set(LABELS)
    assert all(not Path(p.split(":", 1)[1]).is_absolute() for p in manifest["inputs"])


def test_legacy_source_manifest_relocates_but_rejects_corruption_and_escape(tmp_path):
    from smart_recycling.data.bilingual_benchmark import validate_source_inputs
    from smart_recycling.data.common import sha256_file

    (tmp_path / "data").mkdir()
    source = tmp_path / "data/example.csv"
    source.write_text("unchanged source")
    manifest = dict(
        source_package="/old/root/data/processed/bilingual_mk_v1",
        inputs={"/old/root/data/example.csv": sha256_file(source)},
    )
    validate_source_inputs(manifest, tmp_path)
    source.write_text("changed source")
    with pytest.raises(ValueError, match="checksum"):
        validate_source_inputs(manifest, tmp_path)
    manifest["inputs"] = {"../outside.csv": "fake"}
    with pytest.raises(ValueError, match="escapes"):
        validate_source_inputs(manifest, tmp_path)


def test_calibration_rejects_a_confident_held_case_and_can_fail_closed():
    import runpy

    select = runpy.run_path(str(ROOT / "scripts/train_ml_v3.py"))["select_gate"]
    classes = sorted(LABELS)
    rows = [{"label": label, "group": label} for label in classes] + [
        {"label": "", "group": "held"}
    ]
    probabilities = np.vstack([np.eye(6), np.eye(6)[0]])
    # Confidence alone cannot distinguish the held case; similarity can.
    threshold, similarity = select(rows, probabilities, np.array([1] * 6 + [0.2]), classes)
    accepted = (probabilities.max(axis=1) >= threshold) & (np.array([1] * 6 + [0.2]) >= similarity)
    assert accepted.tolist() == [True] * 6 + [False]
    assert select(rows, probabilities, np.ones(7), classes) == (1.01, 1.01)


def test_spelling_multiplicity_cannot_hide_a_failing_concept():
    from smart_recycling.data.ml_evaluation import metrics, select_gate

    classes = sorted(LABELS)
    for variants in (1, 3, 20):
        rows = [dict(label="clothes", group=str(i)) for i in range(9) for _ in range(variants)]
        rows.append(dict(label="electronics", group="wrong"))
        scores = np.tile(np.eye(6)[0], (len(rows), 1))
        assert select_gate(rows, scores, np.ones(len(rows)), classes) == (1.01, 1.01)
        result = metrics(rows, scores, classes, np.ones(len(rows), dtype=bool))
        assert result["concept_weighted"]["accepted_accuracy"] == pytest.approx(0.9)
        assert result["concept_groups"] == 10


def test_concept_weighting_preserves_valid_gate_and_rejects_inconsistent_labels():
    from smart_recycling.data.ml_evaluation import concept_weights, select_gate

    classes = sorted(LABELS)
    rows = [dict(label="clothes", group="same") for _ in range(3)]
    np.testing.assert_allclose(concept_weights(rows), [1 / 3] * 3)
    assert select_gate(rows, np.tile(np.eye(6)[0], (3, 1)), np.ones(3), classes) == (0.99, 0.9)
    assert select_gate([], np.empty((0, 6)), np.empty(0), classes) == (1.01, 1.01)
    with pytest.raises(ValueError, match="consistent label"):
        concept_weights([*rows, dict(label="electronics", group="same")])
