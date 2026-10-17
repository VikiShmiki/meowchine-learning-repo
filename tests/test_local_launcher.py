"""Local configuration is resolved from the caller before entering the project."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def launcher():
    spec = importlib.util.spec_from_file_location("run_local", ROOT / "scripts/run_local.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_relative_environment_file_is_loaded_from_callers_directory(
    launcher, tmp_path, monkeypatch
):
    config = tmp_path / "config"
    config.mkdir()
    (config / "app.env").write_text("NAJDI_FRLI_TEST_LAUNCHER=relative-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NAJDI_FRLI_TEST_LAUNCHER", raising=False)
    monkeypatch.setenv("SRA_REVIEW_TOKEN", "t" * 32)
    monkeypatch.setattr(
        sys, "argv", ["run_local.py", "--env-file", "config/app.env", "--port", "8123"]
    )
    starts = []

    def start(app, **options):
        starts.append((app, options, Path.cwd()))

    monkeypatch.setattr(launcher.uvicorn, "run", start)
    launcher.main()
    assert os.environ["NAJDI_FRLI_TEST_LAUNCHER"] == "relative-file"
    assert starts == [
        (
            "smart_recycling.api:app",
            {"host": "127.0.0.1", "port": 8123, "proxy_headers": False},
            ROOT,
        )
    ]


@pytest.mark.parametrize("name", ["missing.env", "directory"])
def test_explicit_invalid_environment_file_stops_before_startup(
    launcher, tmp_path, monkeypatch, capsys, name
):
    (tmp_path / "directory").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_local.py", "--env-file", name])
    monkeypatch.setattr(launcher.uvicorn, "run", lambda *a, **k: pytest.fail("server started"))
    with pytest.raises(SystemExit) as failure:
        launcher.main()
    assert failure.value.code == 2
    assert "Environment file does not exist or is not a file" in capsys.readouterr().err
    assert Path.cwd() == tmp_path
