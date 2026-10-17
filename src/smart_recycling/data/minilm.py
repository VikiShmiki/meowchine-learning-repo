"""Frozen MiniLM embeddings with a small supervised classification head."""

import hashlib
import json
import math
import platform
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

from smart_recycling.data.common import normalize_whitespace, read_json, sha256_file, write_json
from smart_recycling.data.constants import (
    ARTIFACTS_DIR,
    DATA_DIR,
    EVALUATION_DIR,
    MAPPINGS_DIR,
    PROCESSED_DIR,
    RANDOM_SEED,
    RAW_DIR,
    RESULTS_DIR,
    TARGET_LABELS,
)
from smart_recycling.data.review import (
    load_mapping_review,
    load_reviewed_manual,
    validate_training_reviews,
)

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "8b3219a92973c328a8e22fadcfa821b5dc75636a"
THRESHOLDS = (0.0, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99)
MIN_ANSWERED_ACCURACY = 0.95
MIN_COVERAGE = 0.5
DEVELOPMENT_LABELS = tuple(label for label in TARGET_LABELS if label != "general")


class SentenceEncoder(Protocol):
    """The small SentenceTransformer surface needed by this experiment."""

    def encode(
        self,
        sentences: Sequence[str],
        *,
        batch_size: int,
        show_progress_bar: bool,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
    ) -> np.ndarray: ...


def load_encoder(device: str = "cpu") -> SentenceEncoder:
    """Load an immutable upstream revision without permitting remote model code."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        MODEL_ID,
        revision=MODEL_REVISION,
        device=device,
        trust_remote_code=False,
    )
    model.eval()
    model.requires_grad_(False)
    return model


def runtime_environment(device: str) -> dict[str, Any]:
    """Capture enough runtime detail to distinguish CPU and scheduled GPU results."""
    import torch

    cuda_available = torch.cuda.is_available()
    if device.startswith("cuda") and not cuda_available:
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "requested_device": device,
        "torch_version": torch.__version__,
        "cuda_available": cuda_available,
        "cuda_runtime": torch.version.cuda,
        "cuda_device": torch.cuda.get_device_name(0) if cuda_available else None,
        "executable": sys.executable,
    }


def encode(
    encoder: SentenceEncoder,
    texts: Sequence[str],
    batch_size: int,
    *,
    progress: bool = False,
) -> np.ndarray:
    """Create normalized finite embeddings and reject malformed encoder output."""
    values = np.asarray(
        encoder.encode(
            list(texts),
            batch_size=batch_size,
            show_progress_bar=progress,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ),
        dtype=np.float32,
    )
    if (
        values.ndim != 2
        or values.shape[0] != len(texts)
        or values.shape[1] < 1
        or not np.isfinite(values).all()
    ):
        raise ValueError("MiniLM returned invalid embeddings")
    return values


def classification_metrics(
    truth: Sequence[str],
    probabilities: np.ndarray,
    classes: Sequence[str],
    threshold: float,
    texts: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Report closed-set quality and selective quality at one abstention threshold."""
    truth_array = np.asarray(truth)
    classes_array = np.asarray(classes)
    if (
        probabilities.shape != (len(truth_array), len(classes_array))
        or not np.isfinite(probabilities).all()
        or (probabilities < 0).any()
        or not 0 <= threshold <= 1
    ):
        raise ValueError("invalid classification probabilities or threshold")
    if texts is not None and len(texts) != len(truth_array):
        raise ValueError("metric texts and labels have different lengths")
    winners = probabilities.argmax(axis=1)
    scores = probabilities[np.arange(len(probabilities)), winners]
    predictions = classes_array[winners]
    answered = scores >= threshold
    answered_count = int(answered.sum())
    report = classification_report(
        truth_array,
        predictions,
        labels=list(TARGET_LABELS),
        output_dict=True,
        zero_division=0,
    )
    return {
        "examples": len(truth_array),
        "threshold": threshold,
        "closed_set_accuracy": round(float(accuracy_score(truth_array, predictions)), 6),
        "closed_set_macro_f1": round(float(report["macro avg"]["f1-score"]), 6),
        "coverage": round(answered_count / max(len(truth_array), 1), 6),
        "answered": answered_count,
        "answered_accuracy": (
            round(float(accuracy_score(truth_array[answered], predictions[answered])), 6)
            if answered_count
            else None
        ),
        "per_class": {
            label: {
                metric: round(float(report[label][metric]), 6)
                for metric in ("precision", "recall", "f1-score", "support")
            }
            for label in TARGET_LABELS
        },
        "error_examples": (
            [
                {
                    "text": texts[index],
                    "expected": truth_array[index],
                    "predicted": predictions[index] if answered[index] else "",
                    "score": round(float(scores[index]), 6),
                }
                for index in range(len(truth_array))
                if not answered[index] or predictions[index] != truth_array[index]
            ][:25]
            if texts is not None
            else []
        ),
    }


def select_threshold(
    truth: Sequence[str], probabilities: np.ndarray, classes: Sequence[str]
) -> tuple[float | None, list[dict[str, Any]]]:
    """Choose on validation only; never relax the declared quality/coverage gate."""
    sweep = [classification_metrics(truth, probabilities, classes, value) for value in THRESHOLDS]
    eligible = [
        row
        for row in sweep
        if (row["answered_accuracy"] or 0) >= MIN_ANSWERED_ACCURACY
        and row["coverage"] >= MIN_COVERAGE
    ]
    if not eligible:
        return None, sweep
    selected = max(eligible, key=lambda row: (row["coverage"], row["threshold"]))
    return float(selected["threshold"]), sweep


def selective_metrics_with_holds(
    truth: Sequence[str],
    probabilities: np.ndarray,
    classes: Sequence[str],
    threshold: float,
    texts: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Score supported labels and count every answer to a held query as an error."""
    truth_array = np.asarray(truth)
    classes_array = np.asarray(classes)
    if (
        probabilities.shape != (len(truth_array), len(classes_array))
        or not np.isfinite(probabilities).all()
        or (probabilities < 0).any()
        or not 0 <= threshold <= 1
    ):
        raise ValueError("invalid classification probabilities or threshold")
    if texts is not None and len(texts) != len(truth_array):
        raise ValueError("metric texts and labels have different lengths")
    invalid = sorted(set(truth_array) - set(classes_array) - {""})
    if invalid:
        raise ValueError(f"evaluation contains unsupported labels: {invalid}")

    winners = probabilities.argmax(axis=1)
    scores = probabilities[np.arange(len(probabilities)), winners]
    predictions = classes_array[winners]
    answered = scores >= threshold
    supported = truth_array != ""
    correct = answered & supported & (predictions == truth_array)
    answered_count = int(answered.sum())
    supported_count = int(supported.sum())
    per_class = {}
    for label in classes:
        support = int((truth_array == label).sum())
        predicted = int((answered & (predictions == label)).sum())
        true_positive = int((answered & (truth_array == label) & (predictions == label)).sum())
        precision = true_positive / predicted if predicted else None
        recall = true_positive / support if support else None
        per_class[label] = {
            "support": support,
            "predicted": predicted,
            "precision": round(precision, 6) if precision is not None else None,
            "recall": round(recall, 6) if recall is not None else None,
            "f1": (
                round(2 * true_positive / (support + predicted), 6) if support + predicted else None
            ),
        }
    present_f1 = [row["f1"] for row in per_class.values() if row["support"]]
    closed_report = classification_report(
        truth_array[supported],
        predictions[supported],
        labels=list(classes),
        output_dict=True,
        zero_division=0,
    )
    return {
        "examples": len(truth_array),
        "supported_examples": supported_count,
        "held_examples": len(truth_array) - supported_count,
        "threshold": threshold,
        "closed_set_supported_accuracy": round(
            float(accuracy_score(truth_array[supported], predictions[supported])), 6
        ),
        "closed_set_supported_macro_f1": round(float(closed_report["macro avg"]["f1-score"]), 6),
        "answered": answered_count,
        "coverage": round(answered_count / max(len(truth_array), 1), 6),
        "answered_accuracy": (
            round(int(correct.sum()) / answered_count, 6) if answered_count else None
        ),
        "supported_accuracy_including_abstention": (
            round(int(correct.sum()) / supported_count, 6) if supported_count else None
        ),
        "held_false_answers": int((answered & ~supported).sum()),
        "macro_f1_supported_classes": (
            round(sum(present_f1) / len(present_f1), 6) if present_f1 else None
        ),
        "per_class": per_class,
        "error_examples": (
            [
                {
                    "text": texts[index],
                    "expected": truth_array[index] or "held",
                    "predicted": predictions[index] if answered[index] else "",
                    "score": round(float(scores[index]), 6),
                }
                for index in range(len(truth_array))
                if (supported[index] and not correct[index])
                or (not supported[index] and answered[index])
            ][:25]
            if texts is not None
            else []
        ),
    }


def select_development_threshold(
    truth: Sequence[str], probabilities: np.ndarray, classes: Sequence[str]
) -> tuple[float | None, list[dict[str, Any]]]:
    """Select a development threshold while requiring zero answers on held cases."""
    sweep = [
        selective_metrics_with_holds(truth, probabilities, classes, threshold)
        for threshold in THRESHOLDS
    ]
    eligible = [
        row
        for row in sweep
        if (row["answered_accuracy"] or 0) >= MIN_ANSWERED_ACCURACY
        and row["coverage"] >= MIN_COVERAGE
        and row["held_false_answers"] == 0
    ]
    if not eligible:
        return None, sweep
    selected = max(eligible, key=lambda row: (row["coverage"], row["threshold"]))
    return float(selected["threshold"]), sweep


def load_dataset(path: Path) -> pd.DataFrame:
    """Load only a current, reviewed, leak-resistant five-class split."""
    dataset = pd.read_csv(path, dtype=str).fillna("")
    required = {
        "text",
        "target_label",
        "original_label",
        "item_group",
        "split",
        "mapping_status",
        "source",
    }
    if not required.issubset(dataset.columns):
        raise ValueError("MiniLM dataset is missing split or review provenance")
    validate_training_reviews(dataset)
    if set(dataset["split"]) != {"train", "validation", "test"}:
        raise ValueError("MiniLM requires train, validation and test splits")
    if dataset.groupby("item_group")["split"].nunique().max() != 1:
        raise ValueError("item groups cross data splits")
    invalid = sorted(set(dataset["target_label"]) - set(TARGET_LABELS))
    if invalid:
        raise ValueError(f"MiniLM dataset has invalid labels: {invalid}")
    for split in ("train", "validation", "test"):
        missing = sorted(
            set(TARGET_LABELS) - set(dataset.loc[dataset["split"] == split, "target_label"])
        )
        if missing:
            raise ValueError(
                f"reviewed {split} split lacks classes {missing}; complete source review before "
                "training MiniLM"
            )
    return dataset


def load_reviewed_development_training(
    raw_dir: Path | None = None,
    mapping_path: Path | None = None,
    review_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Build a four-class training frame from only currently approved source families."""
    raw_dir = raw_dir or RAW_DIR / "dataset_a"
    mapping_path = mapping_path or MAPPINGS_DIR / "dataset_a_label_mapping.json"
    review_path = review_path or MAPPINGS_DIR / "needs_manual_review.csv"
    csv_paths = sorted(raw_dir.glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError("Dataset A raw splits are missing")
    frames = []
    for path in csv_paths:
        frame = pd.read_csv(path, dtype=str).fillna("")
        if not {"Phrase", "Class"}.issubset(frame.columns):
            raise ValueError(f"unexpected Dataset A columns in {path.name}")
        frame["Class"] = frame["Class"].str.strip()
        frames.append(frame[["Phrase", "Class"]])
    source = pd.concat(frames, ignore_index=True)
    mapping = read_json(mapping_path)
    if not isinstance(mapping, dict):
        raise TypeError("Dataset A mapping must be a JSON object")
    statuses = load_mapping_review(review_path, mapping)
    original_labels = set(source["Class"].str.strip())
    if original_labels != set(mapping):
        raise ValueError("Dataset A raw labels and reviewed mapping do not match")
    training = pd.DataFrame(
        {
            "text": source["Phrase"].map(normalize_whitespace),
            "target_label": source["Class"].map(mapping),
            "original_label": source["Class"].str.strip(),
        }
    )
    training["mapping_status"] = training["original_label"].map(statuses)
    training = training[training["mapping_status"].eq("approved") & training["text"].ne("")].copy()
    training = training.drop_duplicates(subset=["text", "target_label"], keep="first")
    if set(training["target_label"]) != set(DEVELOPMENT_LABELS):
        raise ValueError(
            "reviewed development training must cover exactly the four currently supported labels"
        )
    hashes = {path.name: sha256_file(path) for path in (*csv_paths, mapping_path, review_path)}
    return training, hashes


def load_development_validation(path: Path) -> pd.DataFrame:
    """Load evidence-backed supported cases and explicitly held validation cases."""
    validation = pd.read_csv(path, dtype=str).fillna("")
    required = {"case_id", "text", "target_label", "evidence_ids"}
    if not required.issubset(validation.columns):
        raise ValueError("development validation is missing required columns")
    if validation["case_id"].duplicated().any():
        raise ValueError("development validation has duplicate case IDs")
    invalid = sorted(set(validation["target_label"]) - set(DEVELOPMENT_LABELS) - {""})
    if invalid:
        raise ValueError(f"development validation contains unsupported labels: {invalid}")
    if set(validation["target_label"]) - {""} != set(DEVELOPMENT_LABELS):
        raise ValueError("development validation must cover all four supported labels")
    if not validation["target_label"].eq("").any():
        raise ValueError("development validation must include explicitly held cases")
    policy = json.loads((DATA_DIR / "policy" / "skopje_v1.json").read_text(encoding="utf-8"))
    known_sources = set(policy["sources"])
    for row in validation.itertuples():
        evidence = set(filter(None, row.evidence_ids.split(";")))
        if evidence - known_sources or (row.target_label and not evidence):
            raise ValueError("development validation lacks known policy evidence")
    return validation


def load_manual_with_holds(
    manual_path: Path,
    review_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Return every frozen query, blanking labels that the sidecar review holds."""
    _, scope = load_reviewed_manual(manual_path, review_path)
    review_path = review_path or EVALUATION_DIR / "manual_test_review.csv"
    manual = pd.read_csv(manual_path, dtype=str).fillna("")
    review = pd.read_csv(review_path, dtype=str).fillna("")
    manual["text_sha256"] = manual["text"].map(
        lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest()
    )
    merged = manual.merge(review, on="text_sha256", suffixes=("", "_review"), validate="1:1")
    merged.loc[merged["review_status_review"] != "source_supported", "target_label"] = ""
    return merged[["text", "target_label"]].copy(), scope


def _predict_probabilities(
    classifier: LogisticRegression,
    encoder: SentenceEncoder,
    texts: Sequence[str],
    batch_size: int,
    *,
    progress: bool = False,
) -> np.ndarray:
    return classifier.predict_proba(encode(encoder, texts, batch_size, progress=progress))


def _latency(
    classifier: LogisticRegression,
    encoder: SentenceEncoder,
    texts: Sequence[str],
) -> dict[str, float | int]:
    observations = []
    for text in list(texts)[:100]:
        started = time.perf_counter()
        classifier.predict_proba(encode(encoder, [text], 1))
        observations.append((time.perf_counter() - started) * 1000)
    return {
        "examples": len(observations),
        "p50_single_example_ms": round(float(np.percentile(observations, 50)), 3),
        "p95_single_example_ms": round(float(np.percentile(observations, 95)), 3),
    }


def train_frozen_minilm(
    dataset_path: Path | None = None,
    manual_path: Path | None = None,
    manual_review_path: Path | None = None,
    results_dir: Path | None = None,
    artifacts_dir: Path | None = None,
    *,
    encoder: SentenceEncoder | None = None,
    device: str = "cpu",
    batch_size: int = 64,
    progress: bool = True,
) -> dict[str, Any]:
    """Train only the logistic head; the pinned MiniLM encoder remains frozen."""
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch size must be a positive integer")
    dataset_path = dataset_path or PROCESSED_DIR / "combined_with_splits.csv"
    manual_path = manual_path or EVALUATION_DIR / "manual_test.csv"
    manual_review_path = manual_review_path or EVALUATION_DIR / "manual_test_review.csv"
    results_dir = results_dir or RESULTS_DIR
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR / "models"
    dataset = load_dataset(dataset_path)
    manual, manual_review = load_reviewed_manual(manual_path, manual_review_path)

    if encoder is None:
        runtime = runtime_environment(device)
        encoder = load_encoder(device)
    else:
        runtime = {"requested_device": device, "injected_encoder": True}
    partitions = {
        name: dataset[dataset["split"] == name].copy() for name in ("train", "validation", "test")
    }
    started = time.perf_counter()
    train_embeddings = encode(
        encoder, partitions["train"]["text"].tolist(), batch_size, progress=progress
    )
    classifier = LogisticRegression(
        max_iter=1_000,
        class_weight="balanced",
        random_state=RANDOM_SEED,
    )
    classifier.fit(train_embeddings, partitions["train"]["target_label"].tolist())
    training_seconds = time.perf_counter() - started
    classes = classifier.classes_.tolist()
    if set(classes) != set(TARGET_LABELS):
        raise ValueError("trained MiniLM head does not cover the canonical labels")

    validation_probabilities = _predict_probabilities(
        classifier,
        encoder,
        partitions["validation"]["text"].tolist(),
        batch_size,
        progress=progress,
    )
    selected_threshold, sweep = select_threshold(
        partitions["validation"]["target_label"].tolist(),
        validation_probabilities,
        classes,
    )
    evaluation_threshold = selected_threshold if selected_threshold is not None else 0.0

    evaluations = {
        "validation": classification_metrics(
            partitions["validation"]["target_label"].tolist(),
            validation_probabilities,
            classes,
            evaluation_threshold,
            partitions["validation"]["text"].tolist(),
        )
    }
    for name, frame in (("test", partitions["test"]), ("manual", manual)):
        probabilities = _predict_probabilities(
            classifier,
            encoder,
            frame["text"].tolist(),
            batch_size,
            progress=progress,
        )
        evaluations[name] = classification_metrics(
            frame["target_label"].tolist(),
            probabilities,
            classes,
            evaluation_threshold,
            frame["text"].tolist(),
        )

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / "minilm_frozen_logistic.joblib"
    joblib.dump(
        {
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "normalize_embeddings": True,
            "labels": classes,
            "threshold": selected_threshold,
            "classifier": classifier,
        },
        artifact_path,
    )
    report = {
        "schema_version": 1,
        "experiment_code_sha256": sha256_file(Path(__file__)),
        "runtime": runtime,
        "model": {
            "id": MODEL_ID,
            "revision": MODEL_REVISION,
            "frozen": True,
            "embedding_dimensions": int(train_embeddings.shape[1]),
            "normalize_embeddings": True,
        },
        "classifier": {
            "type": "logistic_regression",
            "class_weight": "balanced",
            "random_seed": RANDOM_SEED,
            "scikit_learn_version": sklearn.__version__,
        },
        "data": {
            "dataset_sha256": sha256_file(dataset_path),
            "training_examples": len(partitions["train"]),
            "validation_examples": len(partitions["validation"]),
            "test_examples": len(partitions["test"]),
            "manual_sha256": sha256_file(manual_path),
            "manual_review": manual_review,
        },
        "training_seconds": round(training_seconds, 3),
        "selection": {
            "selected_threshold": selected_threshold,
            "gate_passed": selected_threshold is not None,
            "minimum_answered_accuracy": MIN_ANSWERED_ACCURACY,
            "minimum_coverage": MIN_COVERAGE,
            "validation_sweep": sweep,
        },
        "evaluations": evaluations,
        "latency": _latency(classifier, encoder, partitions["test"]["text"].tolist()),
        "artifact": {
            "path": artifact_path.name,
            "bytes": artifact_path.stat().st_size,
            "sha256": sha256_file(artifact_path),
        },
        "limitations": [
            "The encoder is pretrained for general sentence similarity, not Skopje "
            "disposal policy.",
            "A predicted category does not establish site acceptance or override specialist rules.",
            "The logistic probabilities are not claimed to be calibrated probabilities.",
            "The artifact is experimental and is not loaded by the serving application.",
        ],
    }
    if not math.isfinite(report["latency"]["p95_single_example_ms"]):
        raise ValueError("invalid MiniLM latency measurement")
    results_dir.mkdir(parents=True, exist_ok=True)
    write_json(results_dir / "minilm_frozen_metrics.json", report)
    write_json(
        artifacts_dir / "minilm_frozen_logistic.metadata.json",
        {
            "artifact_sha256": report["artifact"]["sha256"],
            "experiment_code_sha256": report["experiment_code_sha256"],
            "dataset_sha256": report["data"]["dataset_sha256"],
            "manual_sha256": report["data"]["manual_sha256"],
            "manual_review_sha256": manual_review["review_sha256"],
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "selected_threshold": selected_threshold,
            "selection_gate_passed": selected_threshold is not None,
            "labels": classes,
            "random_seed": RANDOM_SEED,
        },
    )
    return report


def train_frozen_minilm_development(
    raw_dir: Path | None = None,
    mapping_path: Path | None = None,
    mapping_review_path: Path | None = None,
    validation_path: Path | None = None,
    manual_path: Path | None = None,
    manual_review_path: Path | None = None,
    results_dir: Path | None = None,
    artifacts_dir: Path | None = None,
    *,
    encoder: SentenceEncoder | None = None,
    device: str = "cpu",
    batch_size: int = 64,
    progress: bool = True,
) -> dict[str, Any]:
    """Run a non-serving four-class signal check while five-class data remains blocked."""
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch size must be a positive integer")
    validation_path = validation_path or EVALUATION_DIR / "guidance_validation.csv"
    manual_path = manual_path or EVALUATION_DIR / "manual_test.csv"
    manual_review_path = manual_review_path or EVALUATION_DIR / "manual_test_review.csv"
    results_dir = results_dir or RESULTS_DIR
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR / "models"
    training, training_hashes = load_reviewed_development_training(
        raw_dir, mapping_path, mapping_review_path
    )
    validation = load_development_validation(validation_path)
    manual, manual_scope = load_manual_with_holds(manual_path, manual_review_path)

    training_text = set(training["text"].str.casefold().str.strip())
    for name, frame in (("validation", validation), ("manual", manual)):
        overlap = training_text & set(frame["text"].str.casefold().str.strip())
        if overlap:
            raise ValueError(f"development training has exact text overlap with {name}")
    if set(validation["text"].str.casefold().str.strip()) & set(
        manual["text"].str.casefold().str.strip()
    ):
        raise ValueError("development validation has exact text overlap with manual test")

    if encoder is None:
        runtime = runtime_environment(device)
        encoder = load_encoder(device)
    else:
        runtime = {"requested_device": device, "injected_encoder": True}
    started = time.perf_counter()
    train_embeddings = encode(encoder, training["text"].tolist(), batch_size, progress=progress)
    classifier = LogisticRegression(
        max_iter=1_000,
        class_weight="balanced",
        random_state=RANDOM_SEED,
    )
    classifier.fit(train_embeddings, training["target_label"].tolist())
    training_seconds = time.perf_counter() - started
    classes = classifier.classes_.tolist()
    if set(classes) != set(DEVELOPMENT_LABELS):
        raise ValueError("development MiniLM head does not cover all four supported labels")

    validation_probabilities = _predict_probabilities(
        classifier,
        encoder,
        validation["text"].tolist(),
        batch_size,
        progress=progress,
    )
    selected_threshold, sweep = select_development_threshold(
        validation["target_label"].tolist(), validation_probabilities, classes
    )
    diagnostic_threshold = selected_threshold if selected_threshold is not None else 0.0
    manual_probabilities = _predict_probabilities(
        classifier,
        encoder,
        manual["text"].tolist(),
        batch_size,
        progress=progress,
    )
    evaluations = {
        "validation": selective_metrics_with_holds(
            validation["target_label"].tolist(),
            validation_probabilities,
            classes,
            diagnostic_threshold,
            validation["text"].tolist(),
        ),
        "manual": selective_metrics_with_holds(
            manual["target_label"].tolist(),
            manual_probabilities,
            classes,
            diagnostic_threshold,
            manual["text"].tolist(),
        ),
    }

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / "minilm_frozen_four_class_development.joblib"
    joblib.dump(
        {
            "development_only": True,
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "normalize_embeddings": True,
            "labels": classes,
            "threshold": selected_threshold,
            "classifier": classifier,
        },
        artifact_path,
    )
    report = {
        "schema_version": 1,
        "experiment_code_sha256": sha256_file(Path(__file__)),
        "development_only": True,
        "serving_eligible": False,
        "runtime": runtime,
        "model": {
            "id": MODEL_ID,
            "revision": MODEL_REVISION,
            "frozen": True,
            "embedding_dimensions": int(train_embeddings.shape[1]),
            "normalize_embeddings": True,
        },
        "classifier": {
            "type": "logistic_regression",
            "class_weight": "balanced",
            "random_seed": RANDOM_SEED,
            "scikit_learn_version": sklearn.__version__,
        },
        "data": {
            "training_examples": len(training),
            "training_class_counts": training["target_label"].value_counts().to_dict(),
            "training_input_sha256": training_hashes,
            "validation_examples": len(validation),
            "validation_sha256": sha256_file(validation_path),
            "manual_sha256": sha256_file(manual_path),
            "manual_review": manual_scope,
        },
        "training_seconds": round(training_seconds, 3),
        "selection": {
            "selected_threshold": selected_threshold,
            "diagnostic_threshold_when_gate_fails": (0.0 if selected_threshold is None else None),
            "gate_passed": selected_threshold is not None,
            "minimum_answered_accuracy": MIN_ANSWERED_ACCURACY,
            "minimum_coverage": MIN_COVERAGE,
            "maximum_held_false_answers": 0,
            "validation_sweep": sweep,
        },
        "evaluations": evaluations,
        "latency": _latency(classifier, encoder, manual["text"].tolist()),
        "artifact": {
            "path": artifact_path.name,
            "bytes": artifact_path.stat().st_size,
            "sha256": sha256_file(artifact_path),
        },
        "limitations": [
            "Development-only four-class signal check; no reviewed general examples exist.",
            "The encoder is frozen and only the logistic-regression head is trained.",
            "Development and manual fixtures overlap source item families and are not an "
            "independent field benchmark.",
            "Agent source review is not human release sign-off.",
            "A predicted category does not establish site acceptance or override specialist rules.",
            "The artifact is not loaded by the serving application.",
        ],
    }
    if not math.isfinite(report["latency"]["p95_single_example_ms"]):
        raise ValueError("invalid MiniLM latency measurement")
    results_dir.mkdir(parents=True, exist_ok=True)
    write_json(results_dir / "minilm_frozen_four_class_development.json", report)
    write_json(
        artifacts_dir / "minilm_frozen_four_class_development.metadata.json",
        {
            "development_only": True,
            "serving_eligible": False,
            "artifact_sha256": report["artifact"]["sha256"],
            "experiment_code_sha256": report["experiment_code_sha256"],
            "training_input_sha256": training_hashes,
            "validation_sha256": report["data"]["validation_sha256"],
            "manual_sha256": report["data"]["manual_sha256"],
            "manual_review_sha256": manual_scope["review_sha256"],
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "selected_threshold": selected_threshold,
            "selection_gate_passed": selected_threshold is not None,
            "labels": classes,
            "random_seed": RANDOM_SEED,
        },
    )
    return report
