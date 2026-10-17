"""Verify the complete inference inputs for the two supported encoder revisions.

Hashes come from the pinned upstream snapshots, including their tokenizer,
pooling, and module configuration. A local directory name or embedding dimension
does not establish compatibility with a trained head.
"""

import hashlib
import shutil
import tempfile
from pathlib import Path

ENCODER_FILES = {
    (
        "sentence-transformers/all-MiniLM-L6-v2",
        "8b3219a92973c328a8e22fadcfa821b5dc75636a",
    ): {
        "1_Pooling/config.json": "4be450dde3b0273bb9787637cfbd28fe04a7ba6ab9d36ac48e92b11e350ffc23",
        "config.json": "953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41",
        "config_sentence_transformers.json": (
            "061ca9d39661d6c6d6de5ba27f79a1cd5770ea247f8d46412a68a498dc5ac9f3"
        ),
        "model.safetensors": "53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db",
        "modules.json": "84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf",
        "sentence_bert_config.json": (
            "fc1993fde0a95c24ec6c022539d41cf6e2f7c9721e5415d6fb6897472a9cd4b7"
        ),
        "special_tokens_map.json": (
            "303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3"
        ),
        "tokenizer.json": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
        "tokenizer_config.json": "acb92769e8195aabd29b7b2137a9e6d6e25c476a4f15aa4355c233426c61576b",
        "vocab.txt": "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3",
    },
    (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
    ): {
        "1_Pooling/config.json": "4be450dde3b0273bb9787637cfbd28fe04a7ba6ab9d36ac48e92b11e350ffc23",
        "config.json": "6300193cb75e01cf80c96decef7187dfb33094d97cc1490b7ead6ff134476e4e",
        "config_sentence_transformers.json": (
            "b8c64b5cece00d8424b4896ea75b512b6008576088497609dfeb6bd63e6d36b8"
        ),
        "model.safetensors": "eaa086f0ffee582aeb45b36e34cdd1fe2d6de2bef61f8a559a1bbc9bd955917b",
        "modules.json": "8f4b264b80206c830bebbdcae377e137925650a433b689343a63bdc9b3145460",
        "sentence_bert_config.json": (
            "70f4448f31320443fe3557cacea5abf2dcc4915dda8c80646bec9f3bb0aa5a1f"
        ),
        "special_tokens_map.json": (
            "378eb3bf733eb16e65792d7e3fda5b8a4631387ca04d2015199c4d4f22ae554d"
        ),
        "tokenizer.json": "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8",
        "tokenizer_config.json": "5036ea374ffedd706e3bef33e2e0d6953cb868ef8a490e76e32ba0faa37a6b9b",
    },
}
_INFORMATIONAL_FILES = {"README.md", ".gitattributes"}


class EncoderArtifactError(RuntimeError):
    """The requested encoder could not be bound to the expected inference files."""


def verified_encoder_path(model_id: str, revision: str, path: Path | None = None) -> Path:
    """Resolve a pinned snapshot, then verify it before any model code loads it.

    An explicit local path never triggers a download. Hugging Face's normal cache
    and offline settings apply when no path is provided. Snapshot symlinks to
    cached blobs are supported; hashes always cover the actual file contents.
    """
    files = ENCODER_FILES.get((model_id, revision))
    if files is None:
        raise EncoderArtifactError("Encoder identity or revision is not supported")
    if path is None:
        try:
            from huggingface_hub import constants, snapshot_download

            path = Path(
                snapshot_download(
                    repo_id=model_id,
                    revision=revision,
                    allow_patterns=[*files, "README.md"],
                    local_files_only=constants.HF_HUB_OFFLINE,
                )
            )
        except Exception as error:
            raise EncoderArtifactError("Pinned encoder snapshot could not be resolved") from error
    path = Path(path)
    if not path.is_dir():
        raise EncoderArtifactError(f"Bundled encoder path does not exist: {path}")
    directories = {str(parent) for name in files for parent in Path(name).parents} - {"."}
    try:
        for entry in path.rglob("*"):
            relative = entry.relative_to(path).as_posix()
            if entry.is_dir():
                if entry.is_symlink() or relative not in directories:
                    raise EncoderArtifactError(f"Unexpected encoder directory: {relative}")
            elif relative not in files and relative not in _INFORMATIONAL_FILES:
                # Extra adapter/tokenizer/module files can change loading behavior.
                raise EncoderArtifactError(f"Unexpected encoder file: {relative}")
        for name, expected in files.items():
            artifact = path / name
            if not artifact.is_file():
                raise EncoderArtifactError(f"Pinned encoder file is missing: {name}")
            with artifact.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected:
                raise EncoderArtifactError(f"Pinned encoder checksum differs: {name}")
    except OSError as error:
        raise EncoderArtifactError("Pinned encoder files could not be read") from error
    return path


def cache_encoder_files(model_id: str, revision: str, target: Path) -> None:
    """Bundle verified original bytes, with no reserialization or partial publish."""
    target = Path(target)
    if target.exists() or target.is_symlink():
        verified_encoder_path(model_id, revision, target)
        return
    source = verified_encoder_path(model_id, revision)
    files = ENCODER_FILES[(model_id, revision)]
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".encoder-", dir=target.parent) as temporary:
            staging = Path(temporary) / "encoder"
            staging.mkdir()
            for name in files:
                destination = staging / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, destination)
            if (source / "README.md").is_file():
                shutil.copyfile(source / "README.md", staging / "README.md")
            verified_encoder_path(model_id, revision, staging)
            if target.exists() or target.is_symlink():
                raise EncoderArtifactError("Encoder destination appeared during export")
            staging.rename(target)
    except OSError as error:
        raise EncoderArtifactError("Pinned encoder could not be bundled") from error
