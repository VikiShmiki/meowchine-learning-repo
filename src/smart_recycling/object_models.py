"""Pinned six-class English and Macedonian frozen-head suggestions."""

import math
import threading
from pathlib import Path

import joblib
import numpy as np

from smart_recycling.domain import WasteCategory
from smart_recycling.minilm import CategorySuggestion, MiniLMError, _sha256

LABELS = (
    "glass",
    "plastic_metal",
    "paper_tetrapak",
    "special_unsupported",
    "clothes",
    "electronics",
)
HEADS = {
    "en": (
        "en/frozen_english_minilm_logistic.joblib",
        "118d8b0a066b867c72e2d8fdb4881ea785469f78983f71b9443b5459ad9325d7",
        "sentence-transformers/all-MiniLM-L6-v2",
        "8b3219a92973c328a8e22fadcfa821b5dc75636a",
    ),
    "mk": (
        "mk/frozen_multilingual_minilm_logistic.joblib",
        "b35d29b219ee7de6908f6f6f78cc43e6bbd493f9084347669b6e5a54fe957eed",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
    ),
}


class ObjectSuggester:
    """Uncalibrated object label mapped to the existing conservative policy contract."""

    def __init__(self, classifier, encoder, language: str):
        self.classifier = classifier
        self.encoder = encoder
        self.language = language
        self.lock = threading.Lock()
        self.model_version = f"frozen-minilm-six-class-{language}-seed42-v2"

    def suggest(self, text: str) -> CategorySuggestion:
        try:
            with self.lock:
                vector = np.asarray(
                    self.encoder.encode(
                        [text],
                        batch_size=1,
                        show_progress_bar=False,
                        convert_to_numpy=True,
                        normalize_embeddings=True,
                    ),
                    dtype=np.float32,
                )
                scores = np.asarray(self.classifier.predict_proba(vector), dtype=float)
        except Exception as error:
            raise MiniLMError("Object suggestion inference failed") from error
        if (
            vector.shape != (1, 384)
            or scores.shape != (1, 6)
            or not np.isfinite(vector).all()
            or not np.isfinite(scores).all()
            or (scores < 0).any()
            or not math.isclose(float(scores.sum()), 1, abs_tol=1e-6)
        ):
            raise MiniLMError("Object model returned invalid values")
        winner = int(scores[0].argmax())
        label = str(self.classifier.classes_[winner])
        kind = {"clothes": "wearable_clothes", "electronics": "electronics"}.get(label)
        category = WasteCategory("special_unsupported" if kind else label)
        return CategorySuggestion(
            category, round(float(scores[0, winner]), 6), self.model_version, kind
        )


def load_object_suggester(
    root: Path, language: str, model_path: Path | None = None, *, encoder=None
) -> ObjectSuggester:
    """Load only a hash-pinned local artifact; never unpickle user input."""
    if language not in HEADS:
        raise MiniLMError("Unsupported object model language")
    relative, digest, model_id, revision = HEADS[language]
    artifact = root / "artifacts/models/bilingual_v2_seed42" / relative
    if not artifact.is_file() or _sha256(artifact) != digest:
        raise MiniLMError("Pinned object head is missing or has changed")
    try:
        payload = joblib.load(artifact)
        classifier = payload["classifier"]
        if (
            tuple(payload["labels"]) != LABELS
            or payload["encoder"] != {"id": model_id, "revision": revision}
            or tuple(classifier.classes_) != tuple(sorted(LABELS))
            or classifier.coef_.shape != (6, 384)
        ):
            raise MiniLMError("Object head metadata or dimensions differ")
        if encoder is None:
            if language == "en":
                from smart_recycling.minilm import load_encoder
            else:
                from smart_recycling.multilingual import load_encoder
            encoder = load_encoder(model_path)
        return ObjectSuggester(classifier, encoder, language)
    except MiniLMError:
        raise
    except Exception as error:
        raise MiniLMError("Pinned object model could not be loaded") from error
