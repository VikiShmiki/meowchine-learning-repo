"""Encoder identity follows verified bytes, including relocated and bundled models."""

import hashlib
import runpy
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from smart_recycling import encoder_artifacts, minilm, multilingual
from smart_recycling.encoder_artifacts import (
    EncoderArtifactError,
    cache_encoder_files,
    verified_encoder_path,
)


@pytest.fixture
def encoders(tmp_path, monkeypatch):
    """Tiny distinct snapshots exercise verification without real model weights."""
    registry, snapshots = {}, {}
    files = (
        "config.json",
        "config_sentence_transformers.json",
        "modules.json",
        "model.safetensors",
        "tokenizer.json",
        "sentence_bert_config.json",
        "1_Pooling/config.json",
    )
    for language, module in (("en", minilm), ("mk", multilingual)):
        path = tmp_path / language
        manifest = {}
        for name in files:
            content = f"{language}: {name}\n".encode()
            destination = path / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            manifest[name] = hashlib.sha256(content).hexdigest()
        registry[module.MODEL_ID, module.MODEL_REVISION] = manifest
        snapshots[language] = path
    monkeypatch.setattr(encoder_artifacts, "ENCODER_FILES", registry)
    return snapshots


@pytest.fixture
def constructors(monkeypatch):
    calls = []

    class Encoder:
        def __init__(self, path, **kwargs):
            calls.append((Path(path), kwargs))
            self.frozen = False
            self.evaluating = False

        def eval(self):
            self.evaluating = True
            return self

        def requires_grad_(self, enabled):
            self.frozen = not enabled
            return self

        def get_sentence_embedding_dimension(self):
            return 384

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Encoder)
    )
    return calls


def test_verified_snapshot_survives_relocation(encoders, tmp_path):
    copied = tmp_path / "unrelated-directory-name"
    shutil.copytree(encoders["en"], copied)

    assert verified_encoder_path(minilm.MODEL_ID, minilm.MODEL_REVISION, copied) == copied


def test_hugging_face_file_symlinks_preserve_identity(encoders, tmp_path):
    snapshot = tmp_path / "snapshot"
    for source in encoders["en"].rglob("*"):
        if source.is_file():
            destination = snapshot / source.relative_to(encoders["en"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(source)

    assert verified_encoder_path(minilm.MODEL_ID, minilm.MODEL_REVISION, snapshot) == snapshot


@pytest.mark.parametrize("module,wrong", [(minilm, "mk"), (multilingual, "en")])
def test_swapped_encoder_is_rejected_before_model_construction(
    encoders, constructors, module, wrong
):
    with pytest.raises(minilm.MiniLMError):
        module.load_encoder(encoders[wrong])

    assert constructors == []


@pytest.mark.parametrize(
    "name",
    ["model.safetensors", "tokenizer.json", "modules.json", "1_Pooling/config.json"],
)
def test_changed_inference_asset_is_rejected_before_model_construction(
    encoders, constructors, name
):
    (encoders["en"] / name).write_bytes(b"changed after training")

    with pytest.raises(minilm.MiniLMError):
        minilm.load_encoder(encoders["en"])

    assert constructors == []


@pytest.mark.parametrize("name", ["model.safetensors", "config.json", "tokenizer.json"])
def test_missing_asset_is_rejected(encoders, name):
    (encoders["en"] / name).unlink()

    with pytest.raises(EncoderArtifactError):
        verified_encoder_path(minilm.MODEL_ID, minilm.MODEL_REVISION, encoders["en"])


@pytest.mark.parametrize(
    "name",
    [
        "adapter_config.json",
        "tokenizer.model",
        "model.safetensors.index.json",
        "1_Pooling/extra.json",
    ],
)
def test_unverified_extra_assets_cannot_change_inference(encoders, constructors, name):
    (encoders["en"] / name).write_text("unverified alternative configuration")

    with pytest.raises(minilm.MiniLMError):
        minilm.load_encoder(encoders["en"])

    assert constructors == []


def test_non_model_documentation_is_allowed(encoders):
    for name in ("README.md", ".gitattributes"):
        (encoders["en"] / name).write_text("documentation")

    assert (
        verified_encoder_path(minilm.MODEL_ID, minilm.MODEL_REVISION, encoders["en"])
        == encoders["en"]
    )


def test_directory_symlinks_are_rejected(encoders, tmp_path):
    pooling = encoders["en"] / "1_Pooling"
    relocated = tmp_path / "external-pooling"
    pooling.rename(relocated)
    pooling.symlink_to(relocated, target_is_directory=True)

    with pytest.raises(EncoderArtifactError):
        verified_encoder_path(minilm.MODEL_ID, minilm.MODEL_REVISION, encoders["en"])


@pytest.mark.parametrize("module,language", [(minilm, "en"), (multilingual, "mk")])
def test_verified_local_loading_is_offline_and_frozen(encoders, constructors, module, language):
    model = module.load_encoder(encoders[language])

    assert len(constructors) == 1
    path, options = constructors[0]
    assert path == encoders[language]
    assert options["local_files_only"] is True
    assert options["trust_remote_code"] is False
    assert options["device"] == "cpu"
    assert model.frozen and model.evaluating


@pytest.mark.parametrize("offline", [False, True])
def test_default_resolution_requests_only_pinned_files_and_verifies_cache(
    encoders, constructors, monkeypatch, offline
):
    calls = []

    def snapshot_download(**kwargs):
        calls.append(kwargs)
        # A complete cached snapshot must work without a remote repository listing.
        assert kwargs["local_files_only"] is offline
        return str(encoders["en"])

    monkeypatch.setenv("HF_HUB_OFFLINE", "1" if offline else "0")
    # Hub reads this once at import; changing the environment alone is insufficient.
    monkeypatch.setattr("huggingface_hub.constants.HF_HUB_OFFLINE", offline)
    monkeypatch.setattr("huggingface_hub.snapshot_download", snapshot_download)

    minilm.load_encoder()

    assert len(calls) == 1
    assert calls[0]["repo_id"] == minilm.MODEL_ID
    assert calls[0]["revision"] == minilm.MODEL_REVISION
    assert set(calls[0]["allow_patterns"]) == (
        set(encoder_artifacts.ENCODER_FILES[minilm.MODEL_ID, minilm.MODEL_REVISION]) | {"README.md"}
    )
    assert constructors[0][1]["local_files_only"] is True


def test_corrupted_download_cache_is_rejected(encoders, constructors, monkeypatch):
    (encoders["en"] / "model.safetensors").write_bytes(b"corrupt cached weights")
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda **kwargs: str(encoders["en"]))

    with pytest.raises(minilm.MiniLMError):
        minilm.load_encoder()

    assert constructors == []


def test_offline_cache_miss_does_not_construct_model(encoders, constructors, monkeypatch):
    def unavailable(**kwargs):
        assert kwargs["local_files_only"] is True
        raise OSError("No cached snapshot in offline mode")

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setattr("huggingface_hub.constants.HF_HUB_OFFLINE", True)
    monkeypatch.setattr("huggingface_hub.snapshot_download", unavailable)

    with pytest.raises(minilm.MiniLMError):
        minilm.load_encoder()

    assert constructors == []


@pytest.mark.parametrize("module", [minilm, multilingual])
def test_missing_explicit_path_cannot_fall_back_to_download(
    tmp_path, constructors, monkeypatch, module
):
    def unexpected_download(**kwargs):
        pytest.fail("An explicit local path must not fall back to remote weights")

    monkeypatch.setattr("huggingface_hub.snapshot_download", unexpected_download)

    with pytest.raises(minilm.MiniLMError):
        module.load_encoder(tmp_path / "missing")

    assert constructors == []


def test_export_copies_verified_assets_without_reserializing(encoders, tmp_path, monkeypatch):
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda **kwargs: str(encoders["en"]))
    (encoders["en"] / "README.md").write_text("Original model attribution and license")
    target = tmp_path / "deployment-bundle"

    cache_encoder_files(minilm.MODEL_ID, minilm.MODEL_REVISION, target)

    assert verified_encoder_path(minilm.MODEL_ID, minilm.MODEL_REVISION, target) == target
    for name in encoder_artifacts.ENCODER_FILES[minilm.MODEL_ID, minilm.MODEL_REVISION]:
        assert (target / name).read_bytes() == (encoders["en"] / name).read_bytes()
        assert not (target / name).is_symlink()
    assert (target / "README.md").read_bytes() == (encoders["en"] / "README.md").read_bytes()


def test_export_rejects_corrupt_cache_before_creating_bundle(encoders, tmp_path, monkeypatch):
    (encoders["en"] / "tokenizer.json").write_bytes(b"different tokenization")
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda **kwargs: str(encoders["en"]))
    target = tmp_path / "deployment-bundle"

    with pytest.raises(EncoderArtifactError):
        cache_encoder_files(minilm.MODEL_ID, minilm.MODEL_REVISION, target)

    assert not target.exists()


def test_existing_verified_bundle_can_be_reused_without_network(encoders, monkeypatch):
    def unexpected_download(**kwargs):
        pytest.fail("An existing verified bundle needs no download")

    monkeypatch.setattr("huggingface_hub.snapshot_download", unexpected_download)

    cache_encoder_files(minilm.MODEL_ID, minilm.MODEL_REVISION, encoders["en"])

    assert (
        verified_encoder_path(minilm.MODEL_ID, minilm.MODEL_REVISION, encoders["en"])
        == encoders["en"]
    )


def test_export_refuses_conflicting_existing_bundle(encoders, tmp_path, monkeypatch):
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda **kwargs: str(encoders["en"]))
    target = tmp_path / "existing"
    target.mkdir()
    weights = target / "model.safetensors"
    weights.write_bytes(b"existing operator model")

    with pytest.raises(EncoderArtifactError):
        cache_encoder_files(minilm.MODEL_ID, minilm.MODEL_REVISION, target)

    assert weights.read_bytes() == b"existing operator model"


def test_unknown_revision_is_rejected_before_download(encoders, monkeypatch):
    def unexpected_download(**kwargs):
        pytest.fail("Unknown model contract must not download anything")

    monkeypatch.setattr("huggingface_hub.snapshot_download", unexpected_download)

    with pytest.raises(EncoderArtifactError):
        verified_encoder_path(minilm.MODEL_ID, "unreviewed-revision")


def test_training_rejects_swapped_cached_encoder_before_fitting(
    encoders, constructors, tmp_path, monkeypatch
):
    source = tmp_path / "source"
    processed = source / "data/processed"
    processed.mkdir(parents=True)
    (processed / "dataset_a.csv").write_text("text,original_label,item_group\n")
    cache = tmp_path / "encoder-cache"
    expected_english = (
        cache
        / ("models--" + minilm.MODEL_ID.replace("/", "--"))
        / "snapshots"
        / minilm.MODEL_REVISION
    )
    shutil.copytree(encoders["mk"], expected_english)
    run = tmp_path / "training-run"
    script = Path(__file__).resolve().parents[1] / "scripts/train_ml_v3.py"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--source-root",
            str(source),
            "--encoder-cache",
            str(cache),
            "--run-dir",
            str(run),
        ],
    )

    with pytest.raises(EncoderArtifactError, match="checksum"):
        runpy.run_path(str(script), run_name="__main__")

    assert constructors == []
    assert not (run / "models").exists()
