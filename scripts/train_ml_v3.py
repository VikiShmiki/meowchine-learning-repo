"""Rebuild development models with separated tuning, calibration and final reporting."""

import argparse
import json
import platform
from collections import Counter
from pathlib import Path

import numpy as np
import sklearn
from scipy.optimize import minimize_scalar
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

from smart_recycling.data.common import sha256_file
from smart_recycling.data.ml_evaluation import concept_weights, metrics, select_gate
from smart_recycling.data.ml_serving import evaluate_serving, policy_fallback_mask
from smart_recycling.data.ml_v3 import prepare
from smart_recycling.encoder_artifacts import verified_encoder_path
from smart_recycling.guidance import code_digest, load_classifier
from smart_recycling.linear_head import LinearHead, softmax
from smart_recycling.object_models import HEADS, OBJECT_HEAD_VERSION, ObjectSuggester


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def weights(rows):
    # Equal class mass, equal concept mass within a class, equal variants per concept.
    counts = Counter((r["label"], r["group"]) for r in rows)
    groups = Counter(label for label, _ in counts)
    values = np.array([1 / (groups[r["label"]] * counts[r["label"], r["group"]]) for r in rows])
    return values / values.mean()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--encoder-cache", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.run_dir.exists():
        raise ValueError("Use a new run directory; preserve previous evidence")
    output = args.run_dir / "data"
    rows, manifest = prepare(root, args.source_root, output)
    policy_path = root / "data/policy/skopje_v2.json"
    policy_classifier = load_classifier(root / "data/classifier/rules-v3.json", policy_path)
    policy = policy_classifier.policy
    policy_threshold = policy_classifier.rules.threshold
    report = dict(
        dataset=manifest,
        environment=dict(python=platform.python_version(), sklearn=sklearn.__version__),
        code_sha256={
            str(p.relative_to(root)): sha256_file(p)
            for p in (
                Path(__file__).resolve(),
                root / "src/smart_recycling/data/ml_v3.py",
                root / "src/smart_recycling/data/ml_evaluation.py",
                root / "src/smart_recycling/data/ml_serving.py",
                root / "src/smart_recycling/linear_head.py",
                root / "src/smart_recycling/encoder_artifacts.py",
            )
        },
        calibration_scope="actual policy fallback; equal concept weighting",
        policy_code_sha256=code_digest(),
        policy_sha256=sha256_file(policy_path),
        policy_threshold=policy_threshold,
        languages={},
    )
    # Embedding all splits is stateless; no labels/test predictions inform fitting/selection.
    from sentence_transformers import SentenceTransformer

    for language in ("en", "mk"):
        print(f"Fitting {language}", flush=True)
        _, _, encoder_id, revision = HEADS[language]
        encoder = SentenceTransformer(
            str(
                verified_encoder_path(
                    encoder_id,
                    revision,
                    args.encoder_cache
                    / ("models--" + encoder_id.replace("/", "--"))
                    / "snapshots"
                    / revision,
                )
            ),
            device="cpu",
            local_files_only=True,
            trust_remote_code=False,
        )
        selected = [
            r
            for r in rows
            if r["language"] == language
            or (language == "mk" and r["role"] == "train" and r["language"] == "en")
        ]
        vectors = encoder.encode(
            [r["text"] for r in selected],
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        parts = {
            role: [i for i, r in enumerate(selected) if r["role"] == role]
            for role in ("train", "tune", "calibration", "test")
        }
        tr, tu = parts["train"], parts["tune"]
        train = [selected[i] for i in tr]
        tune = [selected[i] for i in tu]
        y = [r["label"] for r in train]
        sample_weight = weights(train)
        candidates = []
        heads = []
        # Same embeddings, class/group weighting ablation and validation-selected regularization.
        for weighting in ("uniform", "class_group"):
            for c in (0.1, 1.0, 10.0, 100.0):
                head = LogisticRegression(C=c, max_iter=2000, random_state=42)
                head.fit(
                    vectors[tr],
                    y,
                    sample_weight=sample_weight if weighting == "class_group" else None,
                )
                score = metrics(tune, head.predict_proba(vectors[tu]), head.classes_)
                candidates.append(dict(weighting=weighting, C=c, tune=score))
                heads.append(head)
        winner = max(
            range(len(heads)),
            key=lambda i: (
                candidates[i]["tune"]["concept_weighted"]["class_report"]["macro avg"]["f1-score"],
                -candidates[i]["tune"]["concept_weighted"]["nll"],
                -candidates[i]["C"],
            ),
        )
        head = heads[winner]
        # Text baseline uses exactly the same rows, weighting and tuning role.
        tfidf = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        tf_train = tfidf.fit_transform([r["text"] for r in train])
        baseline_candidates, baseline_heads = [], []
        for weighting in ("uniform", "class_group"):
            for c in (0.1, 1.0, 10.0, 100.0):
                candidate = LogisticRegression(C=c, max_iter=2000, random_state=42)
                candidate.fit(
                    tf_train,
                    y,
                    sample_weight=(sample_weight if weighting == "class_group" else None),
                )
                scores = metrics(
                    tune,
                    candidate.predict_proba(tfidf.transform([r["text"] for r in tune])),
                    candidate.classes_,
                )
                baseline_candidates.append(dict(C=c, weighting=weighting, tune=scores))
                baseline_heads.append(candidate)
        baseline_winner = max(
            range(len(baseline_heads)),
            key=lambda i: (
                baseline_candidates[i]["tune"]["concept_weighted"]["class_report"]["macro avg"][
                    "f1-score"
                ],
                -baseline_candidates[i]["tune"]["concept_weighted"]["nll"],
                -baseline_candidates[i]["C"],
            ),
        )
        baseline = baseline_heads[baseline_winner]
        tune_supported = np.array([r["label"] != "" for r in tune])
        logits = head.decision_function(vectors[tu])[tune_supported]
        tune_y = [r["label"] for r in tune if r["label"]]
        tune_weight = concept_weights(tune)[tune_supported]
        temperature = float(
            np.exp(
                minimize_scalar(
                    lambda log_t, y=tune_y, z=logits, classes=head.classes_, w=tune_weight: (
                        log_loss(y, softmax(z / np.exp(log_t)), labels=classes, sample_weight=w)
                    ),
                    bounds=(-3, 3),
                    method="bounded",
                ).x
            )
        )
        # Only authored training concepts become applicability prototypes, not source templates.
        prototype_indices = [i for i in tr if selected[i]["source"] == "authored"]
        payload = dict(
            version=OBJECT_HEAD_VERSION,
            classes=head.classes_.tolist(),
            coef=head.coef_.tolist(),
            intercept=head.intercept_.tolist(),
            prototypes=vectors[prototype_indices].tolist(),
            temperature=temperature,
            threshold=1.01,
            similarity_threshold=1.01,
            encoder=dict(id=encoder_id, revision=revision),
            dataset_sha256=sha256_file(output / "manifest.json"),
            language=language,
        )
        portable = LinearHead(payload)
        cal = parts["calibration"]
        fallback = policy_fallback_mask([selected[i] for i in cal], policy, policy_threshold)
        cal = [i for i, called in zip(cal, fallback, strict=True) if called]
        probabilities = portable.predict_proba(vectors[cal])
        payload["calibration_policy_code_sha256"] = code_digest()
        payload["calibration_policy_sha256"] = sha256_file(policy_path)
        payload["calibration_scope"] = "policy_fallback_equal_concept"
        payload["threshold"], payload["similarity_threshold"] = select_gate(
            [selected[i] for i in cal],
            probabilities,
            (vectors[cal] @ portable.prototypes.T).max(axis=1),
            head.classes_,
        )
        # Persist the decision before computing any test predictions.
        destination = args.run_dir / "models" / f"{language}.json"
        write(destination, payload)
        selection = dict(
            calibration_fallback_rows=len(cal),
            calibration_fallback_concepts=len({selected[i]["group"] for i in cal}),
            evaluation_weighting="equal concept; equal spelling weight within concept",
            candidates=candidates,
            selected=winner,
            tfidf_candidates=baseline_candidates,
            tfidf_selected=baseline_winner,
            temperature=temperature,
            threshold=payload["threshold"],
            similarity_threshold=payload["similarity_threshold"],
            artifact_sha256=sha256_file(destination),
        )
        write(output / f"selection_{language}.json", selection)
        portable = LinearHead(payload)
        evaluations = {}
        import joblib

        old = joblib.load(root / "artifacts/models/bilingual_v2_seed42" / HEADS[language][0])[
            "classifier"
        ]
        for role in ("calibration", "test"):
            indices = parts[role]
            examples = [selected[i] for i in indices]
            p = portable.predict_proba(vectors[indices])
            evaluations[role] = dict(
                new=metrics(examples, p, head.classes_, portable.accepts(vectors[indices], p)),
                old=metrics(examples, old.predict_proba(vectors[indices]), old.classes_),
                tfidf=metrics(
                    examples,
                    baseline.predict_proba(tfidf.transform([r["text"] for r in examples])),
                    baseline.classes_,
                ),
            )
            evaluations[role]["serving"] = evaluate_serving(
                examples, ObjectSuggester(portable, encoder, language), policy, policy_threshold
            )
            evaluations[role]["by_variant"] = {}
            evaluations[role]["old_by_variant"] = {}
            for variant in sorted({r["variant"] for r in examples}):
                ids = [j for j, r in enumerate(examples) if r["variant"] == variant]
                evaluations[role]["by_variant"][variant] = metrics(
                    [examples[j] for j in ids],
                    p[ids],
                    head.classes_,
                    portable.accepts(vectors[indices][ids], p[ids]),
                )
                evaluations[role]["old_by_variant"][variant] = metrics(
                    [examples[j] for j in ids],
                    old.predict_proba(vectors[indices][ids]),
                    old.classes_,
                )
            write(
                output / f"predictions_{language}_{role}.json",
                [
                    dict(
                        **r,
                        prediction=str(head.classes_[p[j].argmax()]),
                        confidence=float(p[j].max()),
                        accepted=bool(
                            portable.accepts(vectors[indices][j : j + 1], p[j : j + 1])[0]
                        ),
                    )
                    for j, r in enumerate(examples)
                ],
            )
        report["languages"][language] = dict(selection=selection, evaluations=evaluations)
        write(args.run_dir / "report.json", report)
        print(language, json.dumps(evaluations["test"]["new"]), flush=True)


if __name__ == "__main__":
    main()
