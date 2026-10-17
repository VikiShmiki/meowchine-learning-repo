"""Select abstention on separate development validation, then report the frozen manual test."""

import argparse
import csv
import hashlib
import json
import math
import platform
import time
from collections import Counter
from pathlib import Path

from smart_recycling.data.review import load_reviewed_manual
from smart_recycling.domain import WasteCategory
from smart_recycling.guidance import MODEL_VERSION, GuidanceClassifier, code_digest

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    """Hash normalized text for cross-platform reproducibility."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def evaluate(classifier: GuidanceClassifier, rows: list[dict]) -> dict:
    """Report abstention, per-class quality, hold errors and observed local latency."""
    predictions, latencies = [], []
    for row in rows:
        start = time.perf_counter()
        prediction = classifier.predict(row["text"]).category
        latencies.append((time.perf_counter() - start) * 1000)
        predictions.append(prediction.value if prediction else "")
    pairs = list(zip(rows, predictions, strict=True))
    answered = [(row, prediction) for row, prediction in pairs if prediction]
    supported = [row for row in rows if row["target_label"]]
    correct = sum(row["target_label"] == prediction for row, prediction in answered)
    per_class = {}
    for category in WasteCategory:
        support = sum(row["target_label"] == category for row in rows)
        tp = sum(row["target_label"] == prediction == category for row, prediction in pairs)
        predicted = predictions.count(category.value)
        precision = tp / predicted if predicted else None
        recall = tp / support if support else None
        per_class[category.value] = {
            "support": support,
            "predicted": predicted,
            "precision": precision,
            "recall": recall,
            "f1": (2 * tp / (support + predicted) if support else None),
        }
    present_f1 = [value["f1"] for value in per_class.values() if value["f1"] is not None]
    return {
        "examples": len(rows),
        "supported_examples": len(supported),
        "answered": len(answered),
        "coverage": len(answered) / len(rows),
        "answered_accuracy": correct / len(answered) if answered else None,
        "supported_accuracy_including_abstention": correct / len(supported) if supported else None,
        "held_false_answers": sum(bool(p) and not r["target_label"] for r, p in pairs),
        "macro_f1_supported_classes": sum(present_f1) / len(present_f1) if present_f1 else None,
        "per_class": per_class,
        "p95_predict_ms": sorted(latencies)[math.ceil(0.95 * len(latencies)) - 1],
        "errors": [
            {"text": r["text"], "expected": r["target_label"], "predicted": p}
            for r, p in pairs
            if r["target_label"] != p
        ],
    }


def main() -> None:
    """Write a small JSON serving artifact; training gates for learned models stay intact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "data/classifier")
    args = parser.parse_args()
    policy_path = ROOT / "data/policy/skopje_v2.json"
    validation_path = ROOT / "data/evaluation/guidance_validation_v3.csv"
    manual_path = ROOT / "data/evaluation/manual_test.csv"
    review_path = ROOT / "data/evaluation/manual_test_review.csv"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    with validation_path.open(encoding="utf-8", newline="") as stream:
        validation = list(csv.DictReader(stream))
    if len({row["case_id"] for row in validation}) != len(validation):
        raise ValueError("Duplicate validation case IDs")
    for row in validation:
        if row["target_label"] and row["evidence_ids"] not in policy["sources"]:
            raise ValueError("Validation label lacks known policy evidence")
    manual, scope = load_reviewed_manual(manual_path, review_path)
    # Git checkouts may use CRLF or LF. This report uses normalized text hashes
    # consistently, including the review metadata returned by the legacy loader.
    scope["review_sha256"] = digest(review_path)
    scope["review_hash_encoding"] = "UTF-8 text with normalized LF newlines"
    if {r["text"].casefold().strip() for r in validation} & set(
        manual["text"].str.casefold().str.strip()
    ):
        raise ValueError("Validation text overlaps the manual evaluation")
    sweep = []
    for threshold in (0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 0.99):
        metrics = evaluate(GuidanceClassifier(policy, threshold), validation)
        sweep.append({"threshold": threshold, **metrics})
    eligible = [
        m
        for m in sweep
        if (m["answered_accuracy"] or 0) >= 0.95
        and m["coverage"] >= 0.50
        and m["held_false_answers"] == 0
    ]
    if not eligible:
        raise ValueError("No threshold meets validation precision/coverage/hold gates")
    selected = max(eligible, key=lambda m: (m["coverage"], m["threshold"]))
    classifier = GuidanceClassifier(policy, selected["threshold"])
    test = evaluate(classifier, manual.to_dict(orient="records"))
    report = {
        "model_version": MODEL_VERSION,
        "threshold": selected["threshold"],
        "validation_gate": {
            "min_answered_accuracy": 0.95,
            "min_coverage": 0.50,
            "max_held_false_answers": 0,
        },
        "selection": "maximize validation coverage, then highest threshold; never select on test",
        "validation": selected,
        "threshold_sweep": sweep,
        "manual_test": test,
        "manual_test_scope": scope,
        "validation_groups": dict(Counter(r["group_id"] for r in validation)),
        "limitations": [
            "Development-authored validation fixtures; not an independent field benchmark",
            "No trained model and no probability calibration; scores remain heuristic",
            "Item families overlap between validation and manual test; no unseen-family claim",
            "General waste has development fixtures only; five-class field quality is unknown",
            "The frozen manual test excludes held v1 queries and does not evaluate residual items",
            "Agent inference is not human sign-off; residual scope is household tissues/nappies",
            "Clothes use development fixtures, not an independent textile/photo benchmark",
        ],
        "latency_environment": platform.platform(),
        "latency_target_ms": 25,
        "input_sha256": {p.name: digest(p) for p in (validation_path, manual_path, review_path)},
        "code_sha256": code_digest(),
        "policy_sha256": digest(policy_path),
    }
    artifact = {
        "model_version": MODEL_VERSION,
        "threshold": selected["threshold"],
        "validation_gate_passed": True,
        "code_sha256": code_digest(),
        "policy_sha256": digest(policy_path),
        "input_sha256": report["input_sha256"],
        "confidence_kind": "heuristic_score",
        "human_signoff": False,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in (("rules-v3.json", artifact), ("evaluation-v3.json", report)):
        (args.out / name).write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "threshold": selected["threshold"],
                "test": test,
                "artifact_bytes": (args.out / "rules-v3.json").stat().st_size,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
