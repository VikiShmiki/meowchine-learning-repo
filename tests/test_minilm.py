import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from smart_recycling.data.constants import TARGET_LABELS
from smart_recycling.data.minilm import (
    classification_metrics,
    encode,
    load_dataset,
    select_development_threshold,
    select_threshold,
    selective_metrics_with_holds,
    train_frozen_minilm,
    train_frozen_minilm_development,
)


class FakeEncoder:
    def encode(self, sentences, **kwargs):
        del kwargs
        return np.asarray([[len(text), text.count("a") + 1] for text in sentences], dtype=float)


class FakeLabelEncoder:
    def encode(self, sentences, **kwargs):
        del kwargs
        return np.asarray([[float(label in text) for label in TARGET_LABELS] for text in sentences])


def test_encode_normalizes_contract_without_loading_remote_model() -> None:
    values = encode(FakeEncoder(), ["a", "bbb"], 2)

    assert values.shape == (2, 2)
    assert values.dtype == np.float32


def test_threshold_is_selected_on_accuracy_and_coverage() -> None:
    truth = ["glass", "glass", "general", "general"]
    classes = ["general", "glass"]
    probabilities = np.asarray([[0.01, 0.99], [0.1, 0.9], [0.8, 0.2], [0.49, 0.51]], dtype=float)

    threshold, sweep = select_threshold(truth, probabilities, classes)

    assert threshold == 0.8
    chosen = next(row for row in sweep if row["threshold"] == threshold)
    assert chosen["coverage"] == 0.75
    assert chosen["answered_accuracy"] == 1


def test_metrics_report_closed_and_selective_quality() -> None:
    probabilities = np.asarray([[0.9, 0.1], [0.4, 0.6]], dtype=float)
    metrics = classification_metrics(
        ["general", "general"], probabilities, ["general", "glass"], 0.8
    )

    assert metrics["closed_set_accuracy"] == 0.5
    assert metrics["coverage"] == 0.5
    assert metrics["answered_accuracy"] == 1


def test_development_threshold_rejects_confident_answers_to_held_cases() -> None:
    truth = ["glass", "glass", "", ""]
    classes = ["glass", "paper_tetrapak"]
    probabilities = np.asarray([[0.95, 0.05], [0.85, 0.15], [0.8, 0.2], [0.75, 0.25]], dtype=float)

    threshold, sweep = select_development_threshold(truth, probabilities, classes)

    assert threshold == 0.85
    unsafe = next(row for row in sweep if row["threshold"] == 0.8)
    assert unsafe["held_false_answers"] == 1
    selected = next(row for row in sweep if row["threshold"] == threshold)
    assert selected["coverage"] == 0.5
    assert selected["answered_accuracy"] == 1


def test_development_metrics_count_held_answers_as_errors() -> None:
    metrics = selective_metrics_with_holds(
        ["glass", ""],
        np.asarray([[0.9, 0.1], [0.8, 0.2]], dtype=float),
        ["glass", "paper_tetrapak"],
        0.5,
        ["bottle", "unknown object"],
    )

    assert metrics["closed_set_supported_accuracy"] == 1
    assert metrics["answered_accuracy"] == 0.5
    assert metrics["held_false_answers"] == 1
    assert metrics["error_examples"] == [
        {
            "text": "unknown object",
            "expected": "held",
            "predicted": "glass",
            "score": 0.8,
        }
    ]


def test_dataset_gate_rejects_missing_review_provenance(tmp_path: Path) -> None:
    path = tmp_path / "dataset.csv"
    pd.DataFrame(
        [
            {
                "text": label,
                "target_label": label,
                "item_group": label,
                "split": "train",
                "source": "test",
            }
            for label in TARGET_LABELS
        ]
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="review provenance"):
        load_dataset(path)


def test_dataset_gate_rejects_unreviewed_rows_before_model_download(tmp_path: Path) -> None:
    path = tmp_path / "dataset.csv"
    rows = []
    for split in ("train", "validation", "test"):
        for label in TARGET_LABELS:
            rows.append(
                {
                    "text": f"{split} {label}",
                    "target_label": label,
                    "item_group": f"{split}-{label}",
                    "split": split,
                    "mapping_status": "auto_approved",
                    "source": "test",
                    "original_label": label,
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)

    with pytest.raises(ValueError, match="unreviewed mappings"):
        load_dataset(path)


def test_full_experiment_uses_injected_frozen_embeddings(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    rows = []
    for split in ("train", "validation", "test"):
        repeats = 2 if split == "train" else 1
        for label in TARGET_LABELS:
            for repeat in range(repeats):
                rows.append(
                    {
                        "text": f"{label} example {split} {repeat}",
                        "target_label": label,
                        "item_group": f"{split}-{label}-{repeat}",
                        "split": split,
                        "mapping_status": "approved",
                        "source": "test",
                        "original_label": label,
                    }
                )
    pd.DataFrame(rows).to_csv(dataset_path, index=False)

    manual_path = tmp_path / "manual.csv"
    manual_rows = [
        {"text": f"{label} manual", "target_label": label, "review_status": "test"}
        for label in TARGET_LABELS
    ]
    pd.DataFrame(manual_rows).to_csv(manual_path, index=False)
    review_path = tmp_path / "manual_review.csv"
    pd.DataFrame(
        [
            {
                "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
                "target_label": row["target_label"],
                "review_status": "source_supported",
                "evidence_ids": "pakomak_streams",
                "reviewer": "test",
                "reviewed_on": "2026-09-20",
            }
            for row in manual_rows
        ]
    ).to_csv(review_path, index=False)

    report = train_frozen_minilm(
        dataset_path,
        manual_path,
        review_path,
        tmp_path / "results",
        tmp_path / "artifacts",
        encoder=FakeLabelEncoder(),
        progress=False,
    )

    assert report["model"]["frozen"] is True
    assert report["evaluations"]["test"]["closed_set_accuracy"] == 1
    assert report["selection"]["gate_passed"] is True
    assert (tmp_path / "results" / "minilm_frozen_metrics.json").is_file()
    assert (tmp_path / "artifacts" / "minilm_frozen_logistic.joblib").is_file()


def test_development_experiment_remains_four_class_and_non_serving(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    source_labels = {
        "GLASS SOURCE": "glass",
        "PLASTIC SOURCE": "plastic_metal",
        "PAPER SOURCE": "paper_tetrapak",
        "SPECIAL SOURCE": "special_unsupported",
    }
    pd.DataFrame(
        [
            {"Phrase": f"{target} source example {index}", "Class": source}
            for source, target in source_labels.items()
            for index in range(20)
        ]
    ).to_csv(raw_dir / "train.csv", index=False)
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps(source_labels), encoding="utf-8")
    mapping_review_path = tmp_path / "mapping_review.csv"
    pd.DataFrame(
        [
            {
                "original_label": source,
                "proposed_target_label": target,
                "mapping_status": "approved",
                "evidence_ids": "pakomak_streams",
                "reviewer": "test",
                "reviewed_on": "2026-09-20",
            }
            for source, target in source_labels.items()
        ]
    ).to_csv(mapping_review_path, index=False)

    validation_path = tmp_path / "validation.csv"
    pd.DataFrame(
        [
            {
                "case_id": f"v-{target}",
                "text": f"{target} validation",
                "target_label": target,
                "evidence_ids": "pakomak_streams",
            }
            for target in source_labels.values()
        ]
        + [
            {
                "case_id": "v-held",
                "text": "mystery validation",
                "target_label": "",
                "evidence_ids": "",
            }
        ]
    ).to_csv(validation_path, index=False)

    manual_path = tmp_path / "manual.csv"
    manual_rows = [
        {
            "text": f"{target} manual",
            "target_label": target,
            "review_status": "test",
        }
        for target in source_labels.values()
    ] + [{"text": "mystery manual", "target_label": "glass", "review_status": "test"}]
    pd.DataFrame(manual_rows).to_csv(manual_path, index=False)
    manual_review_path = tmp_path / "manual_review.csv"
    pd.DataFrame(
        [
            {
                "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
                "target_label": row["target_label"],
                "review_status": (
                    "needs_review" if row["text"] == "mystery manual" else "source_supported"
                ),
                "evidence_ids": ("" if row["text"] == "mystery manual" else "pakomak_streams"),
                "reviewer": "test",
                "reviewed_on": "2026-09-20",
            }
            for row in manual_rows
        ]
    ).to_csv(manual_review_path, index=False)

    report = train_frozen_minilm_development(
        raw_dir,
        mapping_path,
        mapping_review_path,
        validation_path,
        manual_path,
        manual_review_path,
        tmp_path / "results",
        tmp_path / "artifacts",
        encoder=FakeLabelEncoder(),
        progress=False,
    )

    assert report["development_only"] is True
    assert report["serving_eligible"] is False
    assert report["runtime"]["requested_device"] == "cpu"
    assert report["runtime"]["injected_encoder"] is True
    assert set(report["classifier"].keys()) >= {"type", "random_seed"}
    assert "general" not in report["data"]["training_class_counts"]
    assert report["evaluations"]["manual"]["held_examples"] == 1
    assert (tmp_path / "results" / "minilm_frozen_four_class_development.json").is_file()
