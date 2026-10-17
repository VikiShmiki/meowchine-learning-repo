"""Regressions for the repository audit; no live credentials or provider calls."""

import asyncio
import hashlib
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from smart_recycling import api
from smart_recycling.community import CommunityStore
from smart_recycling.multilingual import BilingualSuggester, prototype_sha256


def test_database_reads_do_not_wait_for_unrelated_writer(tmp_path):
    store = CommunityStore(tmp_path / "test.sqlite3")
    expected = store.client_key("test")
    db = sqlite3.connect(store.path)
    db.execute("BEGIN IMMEDIATE")
    with ThreadPoolExecutor() as pool:
        future = pool.submit(store.client_key, "test")
        try:
            assert future.result(timeout=1) == expected
        finally:
            db.rollback()
            db.close()


def test_slow_database_identity_does_not_block_event_loop(monkeypatch):
    original = api.community_store.visitor
    entered, release = threading.Event(), threading.Event()

    def slow(cookie):
        entered.set()
        release.wait(3)
        return original(cookie)

    monkeypatch.setattr(api.community_store, "visitor", slow)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://audit"
        ) as client:
            started = time.monotonic()
            task = asyncio.create_task(client.get("/api/v1/routing"))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                # This coroutine must run while the DB operation is still waiting.
                assert time.monotonic() - started < 1
                assert not task.done()
                assert not release.is_set()
            finally:
                release.set()
                response = await task
            assert response.status_code == 200

    asyncio.run(run())


@pytest.mark.parametrize("english,mk", [(False, True), (True, False), (False, False)])
def test_health_reports_independent_model_failures(monkeypatch, english, mk):
    en_model = SimpleNamespace(model_version="english") if english else None
    mk_model = SimpleNamespace(model_version="macedonian") if mk else None
    monkeypatch.setattr(api, "english_suggester", en_model)
    monkeypatch.setattr(api, "multilingual_suggester", mk_model)
    monkeypatch.setattr(
        api, "text_suggester", BilingualSuggester(en_model, mk_model) if english or mk else None
    )
    with TestClient(api.app) as client:
        body = client.get("/health").json()
    assert body["text_suggestion_model"] == ("english" if english else "unavailable")
    assert body["macedonian_suggestion_model"] == ("macedonian" if mk else "unavailable")


def test_macedonian_dynamic_and_middleware_errors():
    with TestClient(api.app) as client:
        response = client.post(
            "/api/v1/trips",
            headers={"Accept-Language": "mk"},
            json={
                "origin": {"latitude": 41.998, "longitude": 21.43},
                "mode": "walking",
                "share_coordinates": True,
                "items": [
                    {
                        "text": "battery",
                        "manual_kind": "empty_glass_packaging",
                        "condition_confirmed": True,
                    }
                ],
            },
        )
        assert response.status_code == 422
        assert response.json()["detail"]["message"].startswith("Предметот 1")
        response = client.post(
            "/api/v1/classify",
            headers={"Accept-Language": "mk", "Origin": "https://example.invalid"},
            json={"text": "glass bottle"},
        )
        assert response.status_code == 403
        assert response.json()["detail"] != "Cross-origin writes are not allowed"


def test_macedonian_evaluation_is_bound_to_dataset_and_prototypes():
    root = Path(__file__).resolve().parents[1]
    report = json.loads((root / "data/classifier/evaluation-mk-v1.json").read_text("utf-8"))
    data = (root / "data/evaluation/manual_test_mk.csv").read_text("utf-8").encode()
    assert report["dataset_sha256"] == hashlib.sha256(data).hexdigest()
    assert report["prototype_sha256"] == prototype_sha256()
