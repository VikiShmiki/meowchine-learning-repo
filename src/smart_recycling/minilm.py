"""Pinned MiniLM category suggestions for the serving application."""

from __future__ import annotations

import hashlib
import json
import math
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import joblib
import numpy as np

from smart_recycling.domain import WasteCategory

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "8b3219a92973c328a8e22fadcfa821b5dc75636a"
MODEL_VERSION = "minilm-l6-v2-frozen-logreg-development-v1"
ARTIFACT_SHA256 = "8a03d7aa2cb3171f5fafd9cc69ee31c868cd5fab7de78ab171e3ea3fbc8b97c6"
EMBEDDING_DIMENSIONS = 384
LABELS = (
    WasteCategory.GLASS,
    WasteCategory.PAPER_TETRAPAK,
    WasteCategory.PLASTIC_METAL,
    WasteCategory.SPECIAL_UNSUPPORTED,
)


class SentenceEncoder(Protocol):
    """Small SentenceTransformer surface used at inference time."""

    def encode(
        self,
        sentences: Sequence[str],
        *,
        batch_size: int,
        show_progress_bar: bool,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
    ) -> np.ndarray: ...


@dataclass(frozen=True)
class CategorySuggestion:
    """A broad, uncalibrated suggestion that cannot establish item acceptance."""

    category: WasteCategory
    score: float
    model_version: str = MODEL_VERSION
    item_kind: str | None = None


class MiniLMError(RuntimeError):
    """Raised when the pinned model or trusted local artifact is invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_encoder(model_path: Path | None = None) -> SentenceEncoder:
    """Load local bundled weights or the immutable upstream model revision."""
    if model_path is not None and not model_path.is_dir():
        raise MiniLMError(f"Bundled MiniLM path does not exist: {model_path}")
    try:
        from sentence_transformers import SentenceTransformer

        if model_path is not None:
            model = SentenceTransformer(str(model_path), device="cpu", trust_remote_code=False)
        else:
            model = SentenceTransformer(
                MODEL_ID,
                revision=MODEL_REVISION,
                device="cpu",
                trust_remote_code=False,
            )
        model.eval()
        model.requires_grad_(False)
        return model
    except MiniLMError:
        raise
    except Exception as error:
        raise MiniLMError("Pinned MiniLM encoder could not be loaded") from error


def cache_encoder(target: Path) -> None:
    """Download the pinned encoder once and save it into a deployment image."""
    model = load_encoder()
    target.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(target), safe_serialization=True)


class MiniLMSuggester:
    """Run the frozen encoder and trusted logistic head as a suggestion only."""

    def __init__(self, classifier: Any, encoder: SentenceEncoder) -> None:
        classes = tuple(WasteCategory(value) for value in classifier.classes_.tolist())
        if classes != LABELS:
            raise MiniLMError("MiniLM head has an unexpected label order")
        if classifier.coef_.shape != (len(LABELS), EMBEDDING_DIMENSIONS):
            raise MiniLMError("MiniLM head has an unexpected coefficient shape")
        self._classifier = classifier
        self._encoder = encoder
        self._lock = threading.Lock()

    @property
    def model_version(self) -> str:
        return MODEL_VERSION

    def suggest(self, text: str) -> CategorySuggestion:
        """Return the closed-set top class without treating its score as calibrated."""
        try:
            with self._lock:
                embeddings = np.asarray(
                    self._encoder.encode(
                        [text],
                        batch_size=1,
                        show_progress_bar=False,
                        convert_to_numpy=True,
                        normalize_embeddings=True,
                    ),
                    dtype=np.float32,
                )
                probabilities = np.asarray(self._classifier.predict_proba(embeddings), dtype=float)
        except Exception as error:
            raise MiniLMError("MiniLM suggestion inference failed") from error
        if (
            embeddings.shape != (1, EMBEDDING_DIMENSIONS)
            or probabilities.shape != (1, len(LABELS))
            or not np.isfinite(embeddings).all()
            or not np.isfinite(probabilities).all()
            or (probabilities < 0).any()
            or not math.isclose(float(probabilities.sum()), 1.0, abs_tol=1e-6)
        ):
            raise MiniLMError("MiniLM returned invalid prediction values")
        winner = int(probabilities[0].argmax())
        return CategorySuggestion(
            category=LABELS[winner],
            score=round(float(probabilities[0, winner]), 6),
        )


def load_suggester(
    artifact_path: Path,
    metadata_path: Path,
    model_path: Path | None = None,
    *,
    encoder: SentenceEncoder | None = None,
) -> MiniLMSuggester:
    """Validate then load the fixed trusted artifact; never accept an uploaded pickle."""
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MiniLMError("MiniLM metadata is missing or invalid") from error
    artifact_digest = _sha256(artifact_path) if artifact_path.is_file() else ""
    if (
        artifact_digest != ARTIFACT_SHA256
        or metadata.get("artifact_sha256") != ARTIFACT_SHA256
        or metadata.get("model_id") != MODEL_ID
        or metadata.get("model_revision") != MODEL_REVISION
        or metadata.get("labels") != [label.value for label in LABELS]
        or metadata.get("development_only") is not True
        or metadata.get("serving_eligible") is not False
        or metadata.get("selection_gate_passed") is not False
        or metadata.get("selected_threshold") is not None
    ):
        raise MiniLMError("MiniLM suggestion artifact metadata does not match the pinned model")
    try:
        artifact = joblib.load(artifact_path)
    except Exception as error:
        raise MiniLMError("MiniLM suggestion artifact could not be loaded") from error
    if (
        artifact.get("development_only") is not True
        or artifact.get("model_id") != MODEL_ID
        or artifact.get("model_revision") != MODEL_REVISION
        or artifact.get("normalize_embeddings") is not True
        or artifact.get("labels") != [label.value for label in LABELS]
        or artifact.get("threshold") is not None
        or "classifier" not in artifact
    ):
        raise MiniLMError("MiniLM suggestion artifact has an invalid contract")
    return MiniLMSuggester(artifact["classifier"], encoder or load_encoder(model_path))
