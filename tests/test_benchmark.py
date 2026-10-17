import numpy as np
import pandas as pd
import pytest

from smart_recycling.data import benchmark
from smart_recycling.data.benchmark import CLASSES, EvaluationSet, _fixture_sets, _metrics


def test_policy_fixture_probe_keeps_clothing_electronics_and_holds_out_of_metrics():
    english, macedonian = _fixture_sets()

    assert english.labels == macedonian.labels
    assert len(english.texts) == len(macedonian.texts) == 68
    assert english.labels.count("special_unsupported") >= 20
    assert english.labels.count("") == 21
    assert "clothes/electronics" in english.scope
    assert "clean shirt" in english.texts
    assert "чиста маица" in macedonian.texts


def test_metrics_exclude_held_rows_from_quality_but_record_predictions():
    evaluation = EvaluationSet(
        "example",
        ("glass", "paper", "ambiguous"),
        ("glass", "paper_tetrapak", ""),
        "test-only",
    )
    probabilities = np.array(
        [
            [0.9, 0.05, 0.03, 0.02],
            [0.1, 0.2, 0.6, 0.1],
            [0.1, 0.7, 0.1, 0.1],
        ]
    )

    metrics = _metrics(evaluation, probabilities)

    assert metrics["supported_examples"] == 2
    assert metrics["held_examples"] == 1
    assert metrics["closed_set_supported_accuracy"] == 1.0
    assert metrics["held_predicted_as"] == {
        "glass": 0,
        "plastic_metal": 1,
        "paper_tetrapak": 0,
        "special_unsupported": 0,
    }
    assert set(metrics["per_class"]) == set(CLASSES)


def test_six_class_metrics_include_clothes_and_electronics_and_reject_wrong_order():
    classes = (*CLASSES, "clothes", "electronics")
    evaluation = EvaluationSet(
        "objects", ("shirt", "laptop"), ("clothes", "electronics"), "unit test", classes
    )
    metrics = _metrics(evaluation, np.eye(6)[[4, 5]])
    assert metrics["closed_set_supported_accuracy"] == 1.0
    assert metrics["per_class"]["clothes"]["recall"] == 1.0
    assert metrics["per_class"]["electronics"]["recall"] == 1.0
    assert metrics["per_class"]["special_unsupported"]["support"] == 0
    with pytest.raises(ValueError, match="label order"):
        _metrics(evaluation, np.eye(6)[[4, 5]], tuple(reversed(classes)))
    with pytest.raises(ValueError, match="outside this benchmark"):
        EvaluationSet("old", ("shirt",), ("clothes",), "four-class default")


@pytest.mark.parametrize("method", ["tfidf", "frozen"])
def test_six_class_fits_persist_new_labels(tmp_path, monkeypatch, method):
    import joblib

    classes = (*CLASSES, "clothes", "electronics")
    vocabulary = (
        "glass bottle",
        "plastic metal can",
        "paper carton",
        "hazardous battery",
        "cotton shirt clothes",
        "electronic laptop charger",
    )
    training = pd.DataFrame(
        [
            {"text": f"{text} sample {index}", "target_label": label}
            for text, label in zip(vocabulary, classes, strict=True)
            for index in range(3)
        ]
    )
    evaluation = EvaluationSet("objects", vocabulary, classes, "unit test", classes)
    if method == "tfidf":
        result = benchmark.run_tfidf(
            training, [evaluation, evaluation], tmp_path, classes=classes, seed=43
        )
        saved = joblib.load(result["artifact"]["path"])
        assert set(saved.classes_) == set(classes)
        assert saved["classifier"].random_state == 43
    else:
        monkeypatch.setattr(benchmark, "load_encoder", lambda device: object())

        def encode(encoder, texts, batch_size, progress):
            return np.array(
                [
                    np.eye(6)[
                        next(i for i, prefix in enumerate(vocabulary) if text.startswith(prefix))
                    ]
                    for text in texts
                ]
            )

        monkeypatch.setattr(benchmark, "encode", encode)
        result = benchmark.run_frozen_minilm(
            training,
            [evaluation, evaluation],
            tmp_path,
            device="cpu",
            batch_size=2,
            classes=classes,
            seed=43,
        )
        saved = joblib.load(result["artifact"]["path"])
        assert saved["labels"] == list(classes)
        assert set(saved["classifier"].classes_) == set(classes)
        assert saved["classifier"].random_state == 43
    assert result["classes"] == list(classes)
    assert result["seed"] == 43
    assert result["evaluations"]["objects"]["closed_set_supported_accuracy"] == 1.0
