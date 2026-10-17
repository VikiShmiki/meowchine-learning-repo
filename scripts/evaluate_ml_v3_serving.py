"""Replay historical manual diagnostics and exercise real-encoder policy boundaries."""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import classification_report

from smart_recycling.data.common import normalize_key, sha256_file
from smart_recycling.data.ml_provenance import load_bound_rows, reviewed_manual_rows
from smart_recycling.data.ml_serving import evaluate_serving
from smart_recycling.guidance import GuidanceClassifier, code_digest, load_classifier
from smart_recycling.object_models import (
    HEADS,
    JSON_HEAD_DIRECTORY,
    JSON_HEAD_HASHES,
    load_object_suggester,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoder-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--training-rows", type=Path, required=True)
    parser.add_argument("--training-manifest", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new report path; preserve previous evidence")
    manifest_path = args.training_manifest or args.training_rows.parent / "manifest.json"
    root = Path(__file__).resolve().parents[1]
    policy_path = root / "data/policy/skopje_v2.json"
    policy_classifier = load_classifier(root / "data/classifier/rules-v3.json", policy_path)
    policy = policy_classifier.policy
    policy_threshold = policy_classifier.rules.threshold
    report = {"scope": "Historical diagnostic, not an independent final test", "languages": {}}
    report["policy_code_sha256"] = code_digest()
    report["policy_sha256"] = sha256_file(policy_path)
    report["policy_threshold"] = policy_threshold
    report["evaluator_sha256"] = sha256_file(Path(__file__))
    for language in ("en", "mk"):
        relative, legacy_hash, model_id, revision = HEADS[language]
        training_rows, provenance = load_bound_rows(
            args.training_rows,
            manifest_path,
            root / JSON_HEAD_DIRECTORY / f"{language}.json",
            JSON_HEAD_HASHES[language],
        )
        training_keys = {
            normalize_key(r["text"])
            for r in training_rows
            if r["role"] == "train" and (r["language"] == language or language == "mk")
        }
        table, input_hashes = reviewed_manual_rows(root, language)
        labels = [r["label"] for r in table]
        path = (
            args.encoder_cache / ("models--" + model_id.replace("/", "--")) / "snapshots" / revision
        )
        suggester = load_object_suggester(root, language, path)
        # Manual labels are broad streams: specialist object labels map back for this diagnostic.
        vectors = suggester.encoder.encode(
            [r["text"] for r in table], normalize_embeddings=True, show_progress_bar=False
        )
        head = suggester.classifier
        new = head.predict_proba(vectors)
        legacy_path = root / "artifacts/models/bilingual_v2_seed42" / relative
        if sha256_file(legacy_path) != legacy_hash:
            raise ValueError("Legacy comparison head checksum differs")
        legacy = joblib.load(legacy_path)["classifier"]
        output = dict(provenance=provenance, evaluation_inputs_sha256=input_hashes)
        supported = np.array([bool(label) for label in labels])
        overlap = np.array([normalize_key(r["text"]) in training_keys for r in table])
        output["training_rows_sha256"] = sha256_file(args.training_rows)
        output["exact_training_overlap"] = [
            r["text"] for r, hit in zip(table, overlap, strict=True) if hit
        ]
        output["excluding_exact_overlap"] = {}
        for name, scores, classes in [
            ("old", legacy.predict_proba(vectors), legacy.classes_),
            ("new", new, head.classes_),
        ]:
            predictions = [str(classes[i]) for i in scores.argmax(axis=1)]
            predictions = [
                "special_unsupported" if p in {"clothes", "electronics"} else p for p in predictions
            ]
            output[name] = classification_report(
                np.array(labels)[supported],
                np.array(predictions)[supported],
                labels=["glass", "plastic_metal", "paper_tetrapak", "special_unsupported"],
                output_dict=True,
                zero_division=0,
            )
            mask = supported & ~overlap
            output["excluding_exact_overlap"][name] = classification_report(
                np.array(labels)[mask],
                np.array(predictions)[mask],
                labels=["glass", "plastic_metal", "paper_tetrapak", "special_unsupported"],
                output_dict=True,
                zero_division=0,
            )
        accepted = head.accepts(vectors, new)
        output["accepted_rows"] = int(accepted.sum())
        output["held_suggestions"] = int((accepted & ~supported).sum())
        output["manual_serving"] = evaluate_serving(
            table, suggester, policy, policy_threshold, broad_labels=True
        )
        development_test = [
            r for r in training_rows if r["role"] == "test" and r["language"] == language
        ]
        output["development_test_serving"] = evaluate_serving(
            development_test, suggester, policy, policy_threshold
        )
        classifier = GuidanceClassifier(policy, policy_threshold, category_suggester=suggester)
        checks = []
        for query in (
            "ne e cista obleka",
            "valkana kosula",
            "mokra maica",
            "glass bottle and a phone",
            "unknown material container",
        ):
            result = classifier.decide(query)
            if result.status not in {"held", "clarify"}:
                raise AssertionError(f"Unsafe direct decision: {query}: {result.status}")
            checks.append(dict(query=query, status=result.status))
        output["policy_boundary_checks"] = checks
        report["languages"][language] = output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
