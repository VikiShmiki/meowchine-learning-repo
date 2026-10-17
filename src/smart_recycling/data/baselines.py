"""Train and evaluate transparent rule and TF-IDF baselines."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.pipeline import FeatureUnion, Pipeline

from smart_recycling.classifier import RuleClassifier
from smart_recycling.data.common import sha256_file, write_json
from smart_recycling.data.constants import (
    ARTIFACTS_DIR,
    EVALUATION_DIR,
    PROCESSED_DIR,
    RANDOM_SEED,
    RESULTS_DIR,
    TARGET_LABELS,
)
from smart_recycling.data.review import load_reviewed_manual, validate_training_reviews

ABSTAIN_LABEL = "abstain"


def _evaluate(
    name: str,
    y_true: list[str],
    predictor: Callable[[list[str]], list[str]],
    texts: list[str],
    results_dir: Path,
) -> dict[str, Any]:
    start = time.perf_counter()
    y_pred = predictor(texts)
    elapsed = time.perf_counter() - start
    sampled_latencies: list[float] = []
    for text in texts[: min(len(texts), 500)]:
        sample_start = time.perf_counter()
        predictor([text])
        sampled_latencies.append((time.perf_counter() - sample_start) * 1000)
    labels = [*TARGET_LABELS, ABSTAIN_LABEL]
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    matrix_frame = pd.DataFrame(matrix, index=labels, columns=labels)
    matrix_frame.to_csv(results_dir / f"{name}_confusion_matrix.csv")
    report = classification_report(
        y_true,
        y_pred,
        labels=list(TARGET_LABELS),
        output_dict=True,
        zero_division=0,
    )
    covered = [prediction != ABSTAIN_LABEL for prediction in y_pred]
    covered_true = [truth for truth, include in zip(y_true, covered, strict=True) if include]
    covered_pred = [
        prediction for prediction, include in zip(y_pred, covered, strict=True) if include
    ]
    return {
        "examples": len(texts),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "macro_f1": round(float(report["macro avg"]["f1-score"]), 6),
        "coverage": round(float(np.mean(covered)), 6),
        "covered_accuracy": (
            round(float(accuracy_score(covered_true, covered_pred)), 6) if covered_true else 0.0
        ),
        "milliseconds_per_example": round(elapsed / max(len(texts), 1) * 1000, 6),
        "p95_single_example_milliseconds": round(float(np.percentile(sampled_latencies, 95)), 6),
        "classification_report": report,
    }


def _rule_predict(texts: list[str]) -> list[str]:
    classifier = RuleClassifier()
    predictions: list[str] = []
    for text in texts:
        prediction = classifier.predict(text)
        predictions.append(prediction.category.value if prediction.category else ABSTAIN_LABEL)
    return predictions


def _build_tfidf_model() -> Pipeline:
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.995, sublinear_tf=True),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                    max_features=100_000,
                    sublinear_tf=True,
                ),
            ),
        ]
    )
    return Pipeline(
        [
            ("features", features),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1_000,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def train_baselines(
    dataset_path: Path | None = None,
    manual_path: Path | None = None,
    results_dir: Path | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    dataset_path = dataset_path or PROCESSED_DIR / "combined_with_splits.csv"
    manual_path = manual_path or EVALUATION_DIR / "manual_test.csv"
    results_dir = results_dir or RESULTS_DIR
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR / "models"
    results_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    dataset = pd.read_csv(dataset_path, dtype=str).fillna("")
    validate_training_reviews(dataset)
    train = dataset[dataset["split"] == "train"]
    test = dataset[dataset["split"] == "test"]
    manual, manual_review = load_reviewed_manual(manual_path)
    missing_classes = sorted(set(TARGET_LABELS) - set(train["target_label"]))
    if missing_classes:
        raise ValueError(
            f"reviewed training data lacks classes {missing_classes}; "
            "review local examples before training a five-class model"
        )

    test_texts = test["text"].tolist()
    test_labels = test["target_label"].tolist()
    manual_texts = manual["text"].tolist()
    manual_labels = manual["target_label"].tolist()

    metrics: dict[str, Any] = {
        "manual_review": manual_review,
        "rule": {
            "test": _evaluate("rule_test", test_labels, _rule_predict, test_texts, results_dir),
            "manual": _evaluate(
                "rule_manual", manual_labels, _rule_predict, manual_texts, results_dir
            ),
        },
    }

    model = _build_tfidf_model()
    training_start = time.perf_counter()
    model.fit(train["text"].tolist(), train["target_label"].tolist())
    training_seconds = time.perf_counter() - training_start
    model_path = artifacts_dir / "tfidf_logistic.joblib"
    joblib.dump(model, model_path)
    write_json(
        artifacts_dir / "tfidf_logistic.metadata.json",
        {
            "artifact_sha256": sha256_file(model_path),
            "dataset_sha256": sha256_file(dataset_path),
            "labels": list(TARGET_LABELS),
            "random_seed": RANDOM_SEED,
            "scikit_learn_version": sklearn.__version__,
            "training_examples": int(len(train)),
        },
    )

    def predict(texts: list[str]) -> list[str]:
        return model.predict(texts).tolist()

    metrics["tfidf_logistic"] = {
        "training_examples": int(len(train)),
        "training_seconds": round(training_seconds, 3),
        "artifact_bytes": model_path.stat().st_size,
        "test": _evaluate("tfidf_test", test_labels, predict, test_texts, results_dir),
        "manual": _evaluate("tfidf_manual", manual_labels, predict, manual_texts, results_dir),
    }
    write_json(results_dir / "baseline_metrics.json", metrics)
    print(
        "Baselines complete: "
        f"rules test macro-F1={metrics['rule']['test']['macro_f1']:.3f}; "
        f"TF-IDF test macro-F1={metrics['tfidf_logistic']['test']['macro_f1']:.3f}"
    )
    return metrics
