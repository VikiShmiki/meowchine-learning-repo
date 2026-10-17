"""Report Macedonian policy parity and real multilingual model quality; never train here."""

import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report

from smart_recycling.data.review import load_reviewed_manual
from smart_recycling.guidance import load_classifier
from smart_recycling.multilingual import (
    MODEL_ID,
    MODEL_REVISION,
    MODEL_VERSION,
    load_multilingual,
    prototype_sha256,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "data/evaluation/manual_test_mk.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    english, review = load_reviewed_manual(ROOT / "data/evaluation/manual_test.csv")
    supported = dict(zip(english.text_sha256, english.target_label, strict=True))
    model = load_multilingual(ROOT)
    rules = load_classifier(
        ROOT / "data/classifier/rules-v3.json", ROOT / "data/policy/skopje_v2.json"
    )
    results, durations = [], []
    model.suggest("пробен предмет")  # Exclude model startup/warm-up from inference latency.
    for row in rows:
        start = time.perf_counter()
        prediction = model.suggest(row["text"])
        durations.append((time.perf_counter() - start) * 1000)
        decision = rules.decide(row["text"])
        results.append(
            {
                "text": row["text"],
                "english_text_sha256": row["english_text_sha256"],
                "provisional_target": row["target_label"],
                "source_supported": row["english_text_sha256"] in supported,
                "suggestion": prediction.category.value,
                "cosine_similarity": prediction.score,
                "policy_status": decision.status,
                "policy_kind": decision.item_kind,
            }
        )
    scored = [row for row in results if row["source_supported"]]
    report = {
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_version": MODEL_VERSION,
        "prototype_sha256": prototype_sha256(),
        "dataset_sha256": hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest(),
        "review": review,
        "translation_review_status": "needs_native_review",
        "scope": "100 paired translations; 59 inherited source-supported English labels. "
        "Development-authored translations, not an independent field or native-speaker benchmark. "
        "No training/threshold selection on these queries. Suggestions never authorize a route.",
        "metrics": classification_report(
            [row["provisional_target"] for row in scored],
            [row["suggestion"] for row in scored],
            output_dict=True,
            zero_division=0,
        ),
        "p95_inference_ms": float(np.percentile(durations, 95)),
        "errors": [row for row in scored if row["suggestion"] != row["provisional_target"]],
        "results": results,
    }
    output = ROOT / "data/classifier/evaluation-mk-v1.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "examples": len(rows),
                "scored": len(scored),
                "metrics": report["metrics"],
                "p95_inference_ms": report["p95_inference_ms"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
