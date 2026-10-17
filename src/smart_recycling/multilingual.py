"""Pinned multilingual embeddings with bilingual, suggestion-only prototypes.

This is a separate model: the English logistic head is not compatible with this
encoder. Cosine similarity is not a probability and never authorizes disposal.
"""

import hashlib
import json
import os
import threading
from contextvars import ContextVar
from pathlib import Path

import numpy as np

from smart_recycling.domain import WasteCategory
from smart_recycling.encoder_artifacts import (
    EncoderArtifactError,
    cache_encoder_files,
    verified_encoder_path,
)
from smart_recycling.language import is_macedonian
from smart_recycling.minilm import CategorySuggestion, MiniLMError

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
MODEL_VERSION = "multilingual-minilm-l12-bilingual-prototypes-v1"
suggestion_language: ContextVar[str | None] = ContextVar("suggestion_language", default=None)
PROTOTYPES = {
    WasteCategory.GLASS: (
        "glass packaging bottle jar",
        "a container made of glass",
        "empty jam jar",
        "стаклена амбалажа",
        "шише од стакло",
        "тегла за мармалад",
        "стаклен сад",
    ),
    WasteCategory.PLASTIC_METAL: (
        "plastic packaging bottle",
        "metal food can",
        "aluminium drink can",
        "пластична амбалажа",
        "шише од пластика",
        "метална конзерва",
        "алуминиумска лименка",
    ),
    WasteCategory.PAPER_TETRAPAK: (
        "paper cardboard newspaper",
        "carton packaging",
        "Tetra Pak drink carton",
        "хартиена амбалажа",
        "картонска кутија",
        "весници и списанија",
        "тетрапак за пијалаци",
    ),
    WasteCategory.SPECIAL_UNSUPPORTED: (
        "electronic device battery medicine",
        "clothing donation",
        "hazardous waste",
        "електричен уред",
        "батерии и лекови",
        "донирање облека",
        "опасен отпад",
    ),
}


def prototype_sha256():
    """Bind evaluation evidence to the exact bilingual prototype list."""
    return hashlib.sha256(
        json.dumps(PROTOTYPES, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_encoder(path: Path | None = None):
    try:
        verified = verified_encoder_path(MODEL_ID, MODEL_REVISION, path)
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer(
            str(verified),
            local_files_only=True,
            device="cpu",
            trust_remote_code=False,
        )
        encoder.eval()
        encoder.requires_grad_(False)
        return encoder
    except EncoderArtifactError as error:
        raise MiniLMError(str(error)) from error
    except Exception as error:
        raise MiniLMError("Multilingual encoder could not be loaded") from error


def cache_encoder(path: Path):
    cache_encoder_files(MODEL_ID, MODEL_REVISION, path)


class MultilingualSuggester:
    model_version = MODEL_VERSION

    def __init__(self, encoder):
        self.encoder = encoder
        self.lock = threading.Lock()
        self.labels = [label for label, texts in PROTOTYPES.items() for _ in texts]
        self.vectors = self._encode([text for texts in PROTOTYPES.values() for text in texts])

    def _encode(self, texts):
        try:
            vectors = np.asarray(
                self.encoder.encode(
                    texts,
                    batch_size=32,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                ),
                dtype=np.float32,
            )
        except Exception as error:
            raise MiniLMError("Multilingual inference failed") from error
        if vectors.shape != (len(texts), 384) or not np.isfinite(vectors).all():
            raise MiniLMError("Invalid multilingual embeddings")
        if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-3):
            raise MiniLMError("Multilingual embeddings must be normalized")
        return vectors

    def suggest(self, text):
        with self.lock:
            similarities = self.vectors @ self._encode([text])[0]
        winner = int(similarities.argmax())
        return CategorySuggestion(
            self.labels[winner],
            round(float(np.clip(similarities[winner], 0, 1)), 6),
            self.model_version,
        )


class BilingualSuggester:
    def __init__(self, english, macedonian):
        self.english, self.macedonian = english, macedonian
        self.model_version = english.model_version if english else macedonian.model_version

    def suggest(self, text):
        language = suggestion_language.get()
        model = (
            self.macedonian
            if (language == "mk" or (language is None and is_macedonian(text)))
            else self.english
        )
        if model is None:
            raise MiniLMError("Requested language model is unavailable")
        return model.suggest(text)


def load_multilingual(root: Path):
    configured = os.getenv("SRA_MULTILINGUAL_MODEL_PATH", "").strip()
    local = (root / configured).resolve() if configured else root / "models/multilingual-minilm"
    return MultilingualSuggester(load_encoder(local if configured or local.is_dir() else None))
