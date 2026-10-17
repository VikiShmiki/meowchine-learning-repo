"""Freshness never implies collection or resurrects a superseded observation."""

import pytest

from smart_recycling.community import CommunityStore


@pytest.fixture
def clock_store(tmp_path, monkeypatch):
    clock = [1_800_000_000.0]
    monkeypatch.setattr("smart_recycling.community.time.time", lambda: clock[0])
    return clock, CommunityStore(tmp_path / "community.sqlite3")


def test_expired_newer_clearance_does_not_resurrect_old_damage(clock_store):
    clock, store = clock_store
    damaged = store.submit("container", "one", asset_id="glass", condition="damaged")
    store.moderate(damaged["id"], "approved")
    clock[0] += 60
    available = store.submit("container", "two", asset_id="glass", condition="available")
    store.moderate(available["id"], "approved")
    _, active_version = store.statuses()
    clock[0] = available["expires"]
    active, rechecks, version = store.status_snapshot()
    assert active == {}
    assert rechecks["glass"]["condition"] == "available"
    assert version != active_version
    assert store.statuses() == (active, version)


def test_renewal_replaces_stale_context_without_extending_original_report(clock_store):
    clock, store = clock_store
    first = store.submit("container", "one", asset_id="glass", condition="full")
    clock[0] = first["expires"]
    active, rechecks, _ = store.status_snapshot()
    assert not active
    assert rechecks["glass"]["expires"] == first["expires"]
    clock[0] += 60
    assert store.status_snapshot()[1] == rechecks
    second = store.submit("container", "two", asset_id="glass", condition="full")
    active, rechecks, _ = store.status_snapshot()
    assert not rechecks
    assert active["glass"]["reported_at"] == second["created"]


@pytest.mark.parametrize("reviewed", [True, False])
def test_expired_full_does_not_resolve_still_current_damage(clock_store, reviewed):
    clock, store = clock_store
    damaged = store.submit("container", "one", asset_id="glass", condition="damaged")
    if reviewed:
        store.moderate(damaged["id"], "approved")
    clock[0] += 60
    full = store.submit("container", "two", asset_id="glass", condition="full")
    clock[0] = full["expires"]
    active, rechecks, _ = store.status_snapshot("one")
    assert active["glass"]["condition"] == "damaged"
    assert not rechecks


def test_expired_reviewed_clearance_also_resolves_older_personal_damage(clock_store):
    clock, store = clock_store
    store.submit("container", "one", asset_id="glass", condition="damaged")
    clock[0] += 60
    cleared = store.submit("container", "two", asset_id="glass", condition="available")
    store.moderate(cleared["id"], "approved")
    clock[0] = cleared["expires"]
    active, rechecks, _ = store.status_snapshot("one")
    assert not active
    assert rechecks["glass"]["condition"] == "available"


def test_pending_positive_cannot_erase_older_personal_or_public_problem(clock_store):
    clock, store = clock_store
    store.submit("container", "one", asset_id="glass", condition="full")
    clock[0] += 60
    store.submit("container", "one", asset_id="glass", condition="damaged")
    clock[0] += 60
    store.submit("container", "one", asset_id="glass", condition="available")
    assert store.statuses("one")[0]["glass"]["condition"] == "damaged"
    assert store.statuses("other")[0]["glass"]["condition"] == "full"


def test_stale_personal_reports_stay_private_and_retention_still_applies(clock_store):
    clock, store = clock_store
    report = store.submit("container", "one", asset_id="glass", condition="damaged")
    clock[0] = report["expires"]
    assert store.status_snapshot("one")[1]["glass"]["source"] == "your_report"
    assert store.status_snapshot("other")[1] == {}
    store.moderate(report["id"], "approved")
    stale = store.status_snapshot("other")[1]["glass"]
    assert set(stale) == {"condition", "reported_at", "expires", "source"}
    clock[0] = report["created"] + 31 * 86400
    assert store.status_snapshot("one")[0:2] == ({}, {})


@pytest.mark.parametrize("state", ["rejected", "duplicate"])
def test_rejected_stale_reports_are_not_recheck_evidence(clock_store, state):
    clock, store = clock_store
    report = store.submit("container", "one", asset_id="glass", condition="full")
    clock[0] = report["expires"]
    store.moderate(report["id"], state)
    assert store.status_snapshot("one")[0:2] == ({}, {})
