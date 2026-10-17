"""Repeatable, development-only benchmark for the currently reviewed four-class data.

This deliberately does not ingest Toronto keyword candidates: their local Skopje
mapping has not been reviewed.  It is a comparison experiment, not a serving path.
"""

import hashlib
import json
import platform
import random
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import FeatureUnion, Pipeline

from smart_recycling.data.common import sha256_file, write_json
from smart_recycling.data.constants import ARTIFACTS_DIR, EVALUATION_DIR, RANDOM_SEED, RESULTS_DIR
from smart_recycling.data.minilm import (
    DEVELOPMENT_LABELS,
    encode,
    load_development_validation,
    load_encoder,
    load_manual_with_holds,
    load_reviewed_development_training,
)
from smart_recycling.data.minilm import MODEL_ID as ENGLISH_MINILM_ID
from smart_recycling.data.minilm import MODEL_REVISION as ENGLISH_MINILM_REVISION

MULTILINGUAL_MINILM_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MULTILINGUAL_MINILM_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
CLASSES = tuple(DEVELOPMENT_LABELS)


class ProbabilisticPredictor(Protocol):
    def __call__(self, texts: Sequence[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class EvaluationSet:
    """A fixed evaluation set; blank labels are held/abstention cases."""

    name: str
    texts: tuple[str, ...]
    labels: tuple[str, ...]
    scope: str
    classes: tuple[str, ...] = CLASSES

    def __post_init__(self) -> None:
        if len(self.texts) != len(self.labels) or not self.texts:
            raise ValueError("evaluation texts and labels must be non-empty and aligned")
        if not self.classes or len(set(self.classes)) != len(self.classes) or "" in self.classes:
            raise ValueError("benchmark classes must be unique and non-empty")
        invalid = set(self.labels) - set(self.classes) - {""}
        if invalid:
            raise ValueError(f"evaluation labels outside this benchmark: {sorted(invalid)}")


def _sha256_texts(texts: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _build_tfidf_logistic(seed: int = RANDOM_SEED) -> Pipeline:
    """Duplicate the established baseline without importing Python-3.11 app code."""
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
                    random_state=seed,
                ),
            ),
        ]
    )


def _manual_macedonian_with_holds() -> pd.DataFrame:
    """Carry English review holds across the SHA-linked Macedonian translations."""
    manual = pd.read_csv(EVALUATION_DIR / "manual_test.csv", dtype=str).fillna("")
    review = pd.read_csv(EVALUATION_DIR / "manual_test_review.csv", dtype=str).fillna("")
    reviewed = manual.assign(
        english_text_sha256=manual["text"].map(
            lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest()
        )
    ).merge(
        review[["text_sha256", "review_status"]].rename(
            columns={"review_status": "source_review_status"}
        ),
        left_on="english_text_sha256",
        right_on="text_sha256",
        validate="1:1",
    )
    translated = pd.read_csv(EVALUATION_DIR / "manual_test_mk.csv", dtype=str).fillna("")
    merged = translated.merge(
        reviewed[["english_text_sha256", "target_label", "source_review_status"]],
        on="english_text_sha256",
        suffixes=("_translated", "_english"),
        validate="1:1",
    )
    if (
        len(merged) != len(translated)
        or not merged["translation_review_status"].eq("needs_native_review").all()
    ):
        raise ValueError("Macedonian manual set must remain SHA-linked and native-review held")
    merged.loc[merged["source_review_status"] != "source_supported", "target_label_english"] = ""
    return merged.rename(columns={"target_label_english": "target_label"})[["text", "target_label"]]


def _fixture_sets() -> tuple[EvaluationSet, EvaluationSet]:
    """Policy fixture probe, which includes clothing/electronics but is not a field test."""
    fixture_path = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "macedonian.json"
    rows = json.loads(fixture_path.read_text(encoding="utf-8"))
    labels_by_kind = {
        "empty_glass_packaging": "glass",
        "empty_plastic_bottle": "plastic_metal",
        "empty_metal_can": "plastic_metal",
        "clean_paper": "paper_tetrapak",
        "clean_cardboard": "paper_tetrapak",
        "empty_tetrapak": "paper_tetrapak",
        "batteries": "special_unsupported",
        "small_electronics": "special_unsupported",
        "electronics": "special_unsupported",
        "wearable_clothes": "special_unsupported",
    }
    mapped = []
    for row in rows:
        label = labels_by_kind.get(row["kind"], "")
        if row["status"] == "specialist":
            label = "special_unsupported"
        mapped.append((row["en"], row["mk"], label))
    scope = (
        "development-authored policy fixture; includes clothes/electronics, but is not "
        "independent data and is never used for model fitting or selection"
    )
    return (
        EvaluationSet(
            "policy_fixture_en",
            tuple(row[0] for row in mapped),
            tuple(row[2] for row in mapped),
            scope,
        ),
        EvaluationSet(
            "policy_fixture_mk",
            tuple(row[1] for row in mapped),
            tuple(row[2] for row in mapped),
            scope,
        ),
    )


def load_benchmark_data() -> tuple[pd.DataFrame, tuple[EvaluationSet, ...], dict[str, Any]]:
    """Load only the pre-existing source-reviewed English training families."""
    training, training_hashes = load_reviewed_development_training()
    guidance = load_development_validation(EVALUATION_DIR / "guidance_validation.csv")
    manual, manual_scope = load_manual_with_holds(
        EVALUATION_DIR / "manual_test.csv", EVALUATION_DIR / "manual_test_review.csv"
    )
    macedonian = _manual_macedonian_with_holds()
    fixture_en, fixture_mk = _fixture_sets()
    evaluations = (
        EvaluationSet(
            "guidance_validation_en",
            tuple(guidance["text"]),
            tuple(guidance["target_label"]),
            "development validation: 32 source-supported, 16 held; selection diagnostic only",
        ),
        EvaluationSet(
            "manual_en",
            tuple(manual["text"]),
            tuple(manual["target_label"]),
            manual_scope["scope"],
        ),
        EvaluationSet(
            "manual_mk",
            tuple(macedonian["text"]),
            tuple(macedonian["target_label"]),
            "SHA-linked translations of manual_en; all rows need native review",
        ),
        fixture_en,
        fixture_mk,
    )
    train_keys = set(training["text"].str.casefold().str.strip())
    for evaluation in evaluations:
        overlap = train_keys & {text.casefold().strip() for text in evaluation.texts}
        if overlap:
            raise ValueError(
                f"exact train/evaluation overlap in {evaluation.name}: {sorted(overlap)[:3]}"
            )
    provenance = {
        "training_hashes": training_hashes,
        "training_examples": len(training),
        "training_class_counts": training["target_label"].value_counts().to_dict(),
        "evaluations": {
            item.name: {
                "examples": len(item.texts),
                "supported_examples": sum(bool(label) for label in item.labels),
                "held_examples": sum(not label for label in item.labels),
                "texts_sha256": _sha256_texts(item.texts),
                "scope": item.scope,
            }
            for item in evaluations
        },
    }
    return training, evaluations, provenance


def _metrics(
    evaluation: EvaluationSet,
    probabilities: np.ndarray,
    classes: Sequence[str] | None = None,
) -> dict[str, Any]:
    classes = tuple(classes) if classes is not None else evaluation.classes
    if tuple(classes) != evaluation.classes:
        raise ValueError("probability columns must match the evaluation label order")
    classes_array = np.asarray(classes)
    if probabilities.shape != (len(evaluation.texts), len(classes)):
        raise ValueError("invalid probability matrix shape")
    if not np.isfinite(probabilities).all() or (probabilities < 0).any():
        raise ValueError("probabilities must be finite and non-negative")
    predictions = classes_array[probabilities.argmax(axis=1)]
    truth = np.asarray(evaluation.labels)
    supported = truth != ""
    supported_truth = truth[supported]
    supported_predictions = predictions[supported]
    report = (
        classification_report(
            supported_truth,
            supported_predictions,
            labels=list(classes),
            output_dict=True,
            zero_division=0,
        )
        if len(supported_truth)
        else {}
    )
    confidence = probabilities.max(axis=1)
    errors = [
        {
            "text": evaluation.texts[index],
            "expected": str(truth[index]),
            "predicted": str(predictions[index]),
            "confidence": round(float(confidence[index]), 6),
        }
        for index in range(len(truth))
        if supported[index] and predictions[index] != truth[index]
    ][:25]
    held_counts = {label: int(((~supported) & (predictions == label)).sum()) for label in classes}
    return {
        "examples": len(evaluation.texts),
        "supported_examples": int(supported.sum()),
        "held_examples": int((~supported).sum()),
        "closed_set_supported_accuracy": (
            round(float(accuracy_score(supported_truth, supported_predictions)), 6)
            if len(supported_truth)
            else None
        ),
        "closed_set_supported_macro_f1": (
            round(float(report["macro avg"]["f1-score"]), 6) if report else None
        ),
        "per_class": {
            label: {
                "precision": round(float(report[label]["precision"]), 6),
                "recall": round(float(report[label]["recall"]), 6),
                "f1": round(float(report[label]["f1-score"]), 6),
                "support": int(report[label]["support"]),
            }
            for label in classes
        }
        if report
        else {},
        "held_predicted_as": held_counts,
        "errors": errors,
    }


def _timed_evaluations(
    predictor: ProbabilisticPredictor,
    evaluations: Sequence[EvaluationSet],
) -> tuple[dict[str, Any], float]:
    output = {}
    started = time.perf_counter()
    for evaluation in evaluations:
        probabilities = predictor(evaluation.texts)
        output[evaluation.name] = _metrics(evaluation, probabilities)
    return output, time.perf_counter() - started


def _validate_label_space(
    training: pd.DataFrame, evaluations: Sequence[EvaluationSet], classes: tuple[str, ...]
) -> None:
    if set(training["target_label"]) != set(classes):
        raise ValueError("training labels differ from the requested model classes")
    if any(evaluation.classes != classes for evaluation in evaluations):
        raise ValueError("model and evaluation label orders differ")


def _latency(predictor: ProbabilisticPredictor, texts: Sequence[str]) -> dict[str, Any]:
    samples = []
    for text in texts[: min(100, len(texts))]:
        started = time.perf_counter()
        predictor([text])
        samples.append((time.perf_counter() - started) * 1_000)
    return {
        "examples": len(samples),
        "p50_single_example_ms": round(float(np.percentile(samples, 50)), 3),
        "p95_single_example_ms": round(float(np.percentile(samples, 95)), 3),
    }


def run_tfidf(
    training: pd.DataFrame,
    evaluations: Sequence[EvaluationSet],
    artifact_dir: Path,
    *,
    classes: tuple[str, ...] = CLASSES,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    """Fit the existing word/character TF-IDF logistic baseline on reviewed data."""
    _validate_label_space(training, evaluations, classes)
    model = _build_tfidf_logistic(seed)
    started = time.perf_counter()
    model.fit(training["text"].tolist(), training["target_label"].tolist())
    training_seconds = time.perf_counter() - started
    artifact_path = artifact_dir / "tfidf_logistic.joblib"
    joblib.dump(model, artifact_path)

    def predictor(texts: Sequence[str]) -> np.ndarray:
        values = model.predict_proba(list(texts))
        aligned = np.zeros((len(texts), len(classes)), dtype=np.float64)
        for index, label in enumerate(model.classes_):
            aligned[:, classes.index(str(label))] = values[:, index]
        return aligned

    metrics, evaluation_seconds = _timed_evaluations(predictor, evaluations)
    return {
        "model": "TF-IDF (word 1-2 gram + char 3-5 gram) + logistic regression",
        "classes": list(classes),
        "seed": seed,
        "training_seconds": round(training_seconds, 3),
        "evaluation_seconds": round(evaluation_seconds, 3),
        "latency": _latency(predictor, evaluations[1].texts),
        "artifact": {
            "path": str(artifact_path),
            "bytes": artifact_path.stat().st_size,
            "sha256": sha256_file(artifact_path),
        },
        "evaluations": metrics,
    }


def run_frozen_minilm(
    training: pd.DataFrame,
    evaluations: Sequence[EvaluationSet],
    artifact_dir: Path,
    *,
    device: str,
    batch_size: int,
    encoder_id: str = ENGLISH_MINILM_ID,
    encoder_revision: str = ENGLISH_MINILM_REVISION,
    classes: tuple[str, ...] = CLASSES,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    """Train only a logistic head over a pinned frozen MiniLM encoder."""
    _validate_label_space(training, evaluations, classes)
    setup_started = time.perf_counter()
    if encoder_id == ENGLISH_MINILM_ID and encoder_revision == ENGLISH_MINILM_REVISION:
        encoder = load_encoder(device)
    else:
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer(
            encoder_id,
            revision=encoder_revision,
            device=device,
            trust_remote_code=False,
        )
        encoder.eval()
        encoder.requires_grad_(False)
    setup_seconds = time.perf_counter() - setup_started
    training_started = time.perf_counter()
    embeddings = encode(encoder, training["text"].tolist(), batch_size, progress=False)
    classifier = LogisticRegression(max_iter=1_000, class_weight="balanced", random_state=seed)
    classifier.fit(embeddings, training["target_label"].tolist())
    training_seconds = time.perf_counter() - training_started
    artifact_name = (
        "frozen_english_minilm_logistic.joblib"
        if encoder_id == ENGLISH_MINILM_ID
        else "frozen_multilingual_minilm_logistic.joblib"
    )
    artifact_path = artifact_dir / artifact_name
    joblib.dump(
        {
            "encoder": {"id": encoder_id, "revision": encoder_revision},
            "labels": list(classes),
            "classifier": classifier,
        },
        artifact_path,
    )

    def predictor(texts: Sequence[str]) -> np.ndarray:
        values = classifier.predict_proba(encode(encoder, texts, batch_size, progress=False))
        aligned = np.zeros((len(texts), len(classes)), dtype=np.float64)
        for index, label in enumerate(classifier.classes_):
            aligned[:, classes.index(str(label))] = values[:, index]
        return aligned

    metrics, evaluation_seconds = _timed_evaluations(predictor, evaluations)
    return {
        "model": f"frozen {encoder_id} + logistic regression",
        "classes": list(classes),
        "seed": seed,
        "model_revision": encoder_revision,
        "setup_seconds": round(setup_seconds, 3),
        "training_seconds": round(training_seconds, 3),
        "evaluation_seconds": round(evaluation_seconds, 3),
        "latency": _latency(predictor, evaluations[1].texts),
        "artifact": {
            "path": str(artifact_path),
            "bytes": artifact_path.stat().st_size,
            "sha256": sha256_file(artifact_path),
        },
        "evaluations": metrics,
    }


def run_lora_multilingual_minilm(
    training: pd.DataFrame,
    evaluations: Sequence[EvaluationSet],
    artifact_dir: Path,
    *,
    device: str,
    batch_size: int,
    epochs: int,
    learning_rate: float,
    classes: tuple[str, ...] = CLASSES,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    """LoRA-tune a multilingual MiniLM classifier for the explicit label space."""
    _validate_label_space(training, evaluations, classes)
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if not device.startswith("cuda") or not torch.cuda.is_available():
        raise RuntimeError("LoRA benchmark requires the scheduled CUDA device")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    setup_started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        MULTILINGUAL_MINILM_ID, revision=MULTILINGUAL_MINILM_REVISION, trust_remote_code=False
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        MULTILINGUAL_MINILM_ID,
        revision=MULTILINGUAL_MINILM_REVISION,
        num_labels=len(classes),
        id2label=dict(enumerate(classes)),
        label2id={label: index for index, label in enumerate(classes)},
        ignore_mismatched_sizes=True,
        trust_remote_code=False,
    )
    lora = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["query", "key", "value"],
        modules_to_save=["classifier"],
    )
    model = get_peft_model(model, lora).to(device)
    setup_seconds = time.perf_counter() - setup_started
    label_to_id = {label: index for index, label in enumerate(classes)}
    encoded = tokenizer(
        training["text"].tolist(), truncation=True, padding=True, max_length=64, return_tensors="pt"
    )
    dataset = TensorDataset(
        encoded["input_ids"],
        encoded["attention_mask"],
        torch.tensor([label_to_id[label] for label in training["target_label"]], dtype=torch.long),
    )
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, generator=generator)
    optimizer = torch.optim.AdamW(
        (item for item in model.parameters() if item.requires_grad), lr=learning_rate
    )
    model.train()
    training_started = time.perf_counter()
    epoch_losses = []
    for _ in range(epochs):
        total_loss = 0.0
        for input_ids, attention_mask, labels in loader:
            optimizer.zero_grad(set_to_none=True)
            output = model(
                input_ids=input_ids.to(device),
                attention_mask=attention_mask.to(device),
                labels=labels.to(device),
            )
            output.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += float(output.loss.detach().cpu()) * len(labels)
        epoch_losses.append(round(total_loss / len(dataset), 6))
    torch.cuda.synchronize()
    training_seconds = time.perf_counter() - training_started
    adapter_dir = artifact_dir / "lora_multilingual_minilm_adapter"
    model.save_pretrained(adapter_dir, safe_serialization=True)
    tokenizer.save_pretrained(adapter_dir)
    write_json(
        adapter_dir / "label_mapping.json",
        {
            "labels": list(classes),
            "id2label": dict(enumerate(classes)),
            "label2id": label_to_id,
            "max_length": 64,
            "base_model": MULTILINGUAL_MINILM_ID,
            "revision": MULTILINGUAL_MINILM_REVISION,
        },
    )

    def predictor(texts: Sequence[str]) -> np.ndarray:
        model.eval()
        batches = []
        with torch.inference_mode():
            for start in range(0, len(texts), batch_size):
                tokenized = tokenizer(
                    list(texts[start : start + batch_size]),
                    truncation=True,
                    padding=True,
                    max_length=64,
                    return_tensors="pt",
                )
                logits = model(**{key: value.to(device) for key, value in tokenized.items()}).logits
                batches.append(torch.softmax(logits, dim=-1).cpu().numpy())
        return np.concatenate(batches, axis=0)

    metrics, evaluation_seconds = _timed_evaluations(predictor, evaluations)
    trainable_parameters = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    all_parameters = sum(parameter.numel() for parameter in model.parameters())
    artifact_files = sorted(path for path in adapter_dir.rglob("*") if path.is_file())
    artifact_bytes = sum(path.stat().st_size for path in artifact_files)
    return {
        "model": "LoRA-tuned paraphrase-multilingual-MiniLM-L12-v2 sequence classifier",
        "classes": list(classes),
        "seed": seed,
        "model_revision": MULTILINGUAL_MINILM_REVISION,
        "setup_seconds": round(setup_seconds, 3),
        "training_seconds": round(training_seconds, 3),
        "evaluation_seconds": round(evaluation_seconds, 3),
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "epoch_losses": epoch_losses,
        "trainable_parameters": trainable_parameters,
        "total_parameters": all_parameters,
        "trainable_parameter_percent": round(trainable_parameters / all_parameters * 100, 4),
        "latency": _latency(predictor, evaluations[1].texts),
        "artifact": {
            "path": str(adapter_dir),
            "bytes": artifact_bytes,
            "files": {
                str(path.relative_to(adapter_dir)): sha256_file(path) for path in artifact_files
            },
        },
        "evaluations": metrics,
    }


def run_benchmark(
    results_dir: Path | None = None,
    artifacts_dir: Path | None = None,
    *,
    device: str = "cuda",
    batch_size: int = 32,
    epochs: int = 3,
    learning_rate: float = 2e-4,
) -> dict[str, Any]:
    """Run each requested method once with seed 42, then persist detailed evidence."""
    if batch_size < 1 or epochs < 1 or learning_rate <= 0:
        raise ValueError("batch_size, epochs and learning_rate must be positive")
    _seed_everything(RANDOM_SEED)
    results_dir = results_dir or RESULTS_DIR / "benchmark_seed42"
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR / "models" / "benchmark_seed42"
    results_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    overall_started = time.perf_counter()
    training, evaluations, provenance = load_benchmark_data()
    report = {
        "schema_version": 1,
        "experiment": "seed-42 reviewed four-class comparison",
        "development_only": True,
        "serving_eligible": False,
        "random_seed": RANDOM_SEED,
        "runtime": {
            "python": platform.python_version(),
            "executable": sys.executable,
            "scikit_learn": sklearn.__version__,
            "requested_device": device,
        },
        "data": provenance,
        "methods": {},
        "limitations": [
            "Uses the current 8,454-row English, agent-source-reviewed development data only.",
            "No Toronto candidates, clothing labels or new electronics labels were mapped or "
            "trained.",
            "No reviewed general-waste training examples exist; this is four-class only.",
            "manual_mk is an SHA-linked translation probe and all translations need native review.",
            "Policy fixtures are development-authored and are not independent performance "
            "evidence.",
            "All outputs are closed-set predictions; no abstention threshold is selected for "
            "serving.",
        ],
    }
    report["methods"]["tfidf_logistic"] = run_tfidf(training, evaluations, artifacts_dir)
    report["methods"]["frozen_english_minilm"] = run_frozen_minilm(
        training, evaluations, artifacts_dir, device=device, batch_size=batch_size
    )
    report["methods"]["lora_multilingual_minilm"] = run_lora_multilingual_minilm(
        training,
        evaluations,
        artifacts_dir,
        device=device,
        batch_size=batch_size,
        epochs=epochs,
        learning_rate=learning_rate,
    )
    report["wall_seconds"] = round(time.perf_counter() - overall_started, 3)
    report["experiment_code_sha256"] = sha256_file(Path(__file__))
    write_json(results_dir / "benchmark_seed42.json", report)
    summary = []
    for name, method in report["methods"].items():
        for evaluation_name, metrics in method["evaluations"].items():
            summary.append(
                {
                    "method": name,
                    "evaluation": evaluation_name,
                    "supported_examples": metrics["supported_examples"],
                    "accuracy": metrics["closed_set_supported_accuracy"],
                    "macro_f1": metrics["closed_set_supported_macro_f1"],
                    "training_seconds": method["training_seconds"],
                    "evaluation_seconds": method["evaluation_seconds"],
                }
            )
    pd.DataFrame(summary).to_csv(results_dir / "benchmark_seed42_summary.csv", index=False)
    return report
