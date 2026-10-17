"""Container readiness retries transport startup failures without hiding bad data."""

import importlib.util
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import URLError

import pytest


@pytest.fixture
def smoke():
    path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_deployment.py"
    spec = importlib.util.spec_from_file_location("smoke_deployment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "error", [ConnectionResetError(), RemoteDisconnected(), TimeoutError(), URLError("not ready")]
)
def test_transient_startup_failure_is_retried(smoke, monkeypatch, error):
    calls = []
    sleeps = []

    def request(url, path):
        calls.append((url, path))
        if len(calls) == 1:
            raise error
        return {"status": "ok", "site_count": 1}

    monkeypatch.setattr(smoke, "get", request)
    monkeypatch.setattr(smoke.time, "sleep", sleeps.append)
    assert smoke.wait_for_health("http://localhost", 5)["status"] == "ok"
    assert calls == [("http://localhost", "/health")] * 2
    assert sleeps == [1]


def test_startup_timeout_still_fails(smoke, monkeypatch):
    def request(*args):
        raise ConnectionResetError

    monkeypatch.setattr(smoke, "get", request)
    with pytest.raises(SystemExit, match="did not become healthy"):
        smoke.wait_for_health("http://localhost", 0)


def test_invalid_health_payload_is_not_hidden_by_retries(smoke, monkeypatch):
    def request(*args):
        raise ValueError("invalid JSON")

    monkeypatch.setattr(smoke, "get", request)
    with pytest.raises(ValueError, match="invalid JSON"):
        smoke.wait_for_health("http://localhost", 5)
