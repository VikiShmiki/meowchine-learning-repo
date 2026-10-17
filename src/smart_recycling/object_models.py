"""Pinned six-class suggestions with development-calibrated abstention."""

import json
import math
import threading
from pathlib import Path

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

OBJECT_HEAD_VERSION = "object-development-v3-audit"
JSON_HEAD_DIRECTORY = "artifacts/models/ml_v3_audit"

JSON_HEAD_HASHES = {
    "en": "efc4917d533f48f0fb64dacf6d1058e054c1dcb7aa01d42ad3b46af8787e3879",
    "mk": "98b3a4a253ff8981362372efef0c3365d571c236c3d772680e3e14887fa0911c",
}


class ObjectSuggester:
    """Object suggestions never authorize a disposal route or item acceptance."""

    def __init__(self, classifier, encoder, language: str):
        self.classifier = classifier
        self.encoder = encoder
        self.language = language
        self.lock = threading.Lock()
        self.model_version = (
            f"frozen-minilm-six-class-{language}-{OBJECT_HEAD_VERSION.removeprefix('object-')}"
        )

    def suggest(self, text: str) -> CategorySuggestion | None:
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
        try:
            if (
                hasattr(self.classifier, "accepts")
                and not self.classifier.accepts(vector, scores)[0]
            ):
                return None
        except Exception as error:
            raise MiniLMError("Object suggestion gate failed") from error
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
    """Load hash-pinned JSON weights with the matching pinned encoder."""
    if language not in HEADS:
        raise MiniLMError("Unsupported object model language")
    _, _, model_id, revision = HEADS[language]
    digest = JSON_HEAD_HASHES[language]
    artifact = root / JSON_HEAD_DIRECTORY / f"{language}.json"
    try:
        if not artifact.is_file() or _sha256(artifact) != digest:
            raise MiniLMError("Pinned object head is missing or has changed")
        from smart_recycling.linear_head import LinearHead

        payload = json.loads(artifact.read_text(encoding="utf-8"))
        if (
            payload.get("version") != OBJECT_HEAD_VERSION
            or payload.get("language") != language
            or payload.get("encoder") != {"id": model_id, "revision": revision}
        ):
            raise MiniLMError("Object head metadata differs")
        classifier = LinearHead(payload)
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
