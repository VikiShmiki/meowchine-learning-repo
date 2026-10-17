"""A rejected encoder disables only its language; policy guidance still starts."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("language", ["en", "mk"])
@pytest.mark.parametrize("failure", ["missing_encoder", "invalid_encoder", "unreadable_head"])
def test_invalid_model_falls_back_without_downloading(tmp_path, language, failure):
    invalid = tmp_path / "invalid-encoder"
    if failure == "invalid_encoder":
        invalid.mkdir()
        (invalid / "config.json").write_text("{}")
    # Isolate import-time startup from the app used by the rest of the suite.
    program = """
import sys
from types import SimpleNamespace
import huggingface_hub
from smart_recycling import object_models
from smart_recycling.multilingual import suggestion_language

failed = sys.argv[1]
if sys.argv[2] == "unreadable_head":
    def unreadable(path):
        raise PermissionError("Model file cannot be read")
    object_models._sha256 = unreadable
real_load = object_models.load_object_suggester
downloads = []
def no_download(*args, **kwargs):
    downloads.append(args)
    raise AssertionError("An explicitly configured invalid encoder must not download")
huggingface_hub.snapshot_download = no_download

def load(root, language, path=None):
    if language == failed:
        return real_load(root, language, path)
    return SimpleNamespace(model_version="healthy-" + language, suggest=lambda text: None)
object_models.load_object_suggester = load

from smart_recycling import api
health = api.health()
for language, field in (("en", "text_suggestion_model"), ("mk", "macedonian_suggestion_model")):
    assert health[field] == ("unavailable" if language == failed else "healthy-" + language)
assert not downloads
assert api.classifier.decide("glass bottle").status == "confirm_condition"
assert api.classifier.decide("battery", "empty_plastic_bottle", True).status == "specialist"
token = suggestion_language.set(failed)
try:
    response = api.classifier.decide("unidentified object")
    assert response.status == "clarify"
    assert response.suggested_category is None
finally:
    suggestion_language.reset(token)
"""
    env = {
        **os.environ,
        "SRA_PROJECT_ROOT": str(ROOT),
        "SRA_MINILM_SUGGESTIONS": "true",
        "SRA_MINILM_MODEL_PATH": str(invalid),
        "SRA_MULTILINGUAL_MODEL_PATH": str(invalid),
        "SRA_COMMUNITY_DB": str(tmp_path / "community.sqlite3"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    result = subprocess.run(
        [sys.executable, "-c", program, language, failure],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
