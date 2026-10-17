"""Serving checks for the development-only MiniLM suggestion boundary."""

import json
from pathlib import Path

import numpy as np
import pytest

from smart_recycling.domain import WasteCategory
from smart_recycling.minilm import (
    EMBEDDING_DIMENSIONS,
    MiniLMError,
    load_encoder,
    load_suggester,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/models/minilm_frozen_four_class_development.joblib"
METADATA = ROOT / "artifacts/models/minilm_frozen_four_class_development.metadata.json"


class ZeroEncoder:
    def encode(self, sentences, **kwargs):
        assert kwargs == {
            "batch_size": 1,
            "show_progress_bar": False,
            "convert_to_numpy": True,
            "normalize_embeddings": True,
        }
        return np.zeros((len(sentences), EMBEDDING_DIMENSIONS), dtype=np.float32)


def test_tracked_head_loads_only_after_contract_and_checksum_validation() -> None:
    suggester = load_suggester(ARTIFACT, METADATA, encoder=ZeroEncoder())

    answer = suggester.suggest("unseen item description")

    assert isinstance(answer.category, WasteCategory)
    assert 0 < answer.score < 1
    assert answer.model_version == suggester.model_version


def test_modified_artifact_is_rejected_before_unpickling(tmp_path) -> None:
    artifact = tmp_path / "changed.joblib"
    artifact.write_bytes(ARTIFACT.read_bytes() + b"changed")

    with pytest.raises(MiniLMError, match="metadata"):
        load_suggester(artifact, METADATA, encoder=ZeroEncoder())


def test_metadata_cannot_promote_failed_gate_to_serving_model(tmp_path) -> None:
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    metadata["selection_gate_passed"] = True
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(MiniLMError, match="metadata"):
        load_suggester(ARTIFACT, path, encoder=ZeroEncoder())


def test_missing_local_encoder_has_an_explicit_model_error(tmp_path) -> None:
    with pytest.raises(MiniLMError, match="does not exist"):
        load_encoder(tmp_path / "missing-model")
