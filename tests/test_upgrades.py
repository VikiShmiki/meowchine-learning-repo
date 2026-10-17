"""Weighted overlap, exhaustive objective and prepared API regression checks."""

import itertools
import json
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_recycling.geography.io import sha256, write_json
from smart_recycling.infrastructure_models import SiteSnapshot
from smart_recycling.upgrades import is_candidate, load_upgrades
from smart_recycling.upgrades_solver import Candidate, Problem

ROOT = Path(__file__).resolve().parents[1]


def test_overlap_floor_and_stable_ties():
    problem = Problem(
        [40, 60, 50, 50],
        [0, 0, 1, 1],
        [100, 100],
        1,
        [Candidate("a", 3), Candidate("b", 4), Candidate("c", 4)],
    )
    plan = problem.solve(1)
    assert plan.selected == ("b",)  # Worst municipality first, not larger city gain.
    assert plan.totals == (40, 50)
    assert plan.floor_status == "proven_infeasible"
    assert problem.solve(2).selected == ("a", "b")
    assert problem.solve(3).selected == ("a", "b")  # No redundant site.
    assert problem.solve(2).floor_status == "met"
    assert problem.solve(0).covered == 1


def test_feasible_floor_maximizes_population_not_extra_equity():
    problem = Problem(
        [50, 50, 50, 10, 40],
        [0, 0, 1, 1, 1],
        [100, 100],
        5,
        [Candidate("city", 2), Candidate("balance", 8)],
    )
    assert problem.solve(1).selected == ("city",)


@pytest.mark.parametrize("seed", range(12))
def test_exact_solver_matches_independent_exhaustive_oracle(seed):
    rng = random.Random(seed)
    weights = [rng.randint(1, 10) for _ in range(8)]
    candidates = [Candidate(str(i), rng.randrange(256)) for i in range(5)]
    baseline = rng.randrange(256)
    problem = Problem(
        weights, [0] * 4 + [1] * 4, [sum(weights[:4]), sum(weights[4:])], baseline, candidates
    )
    scores = []
    for k in range(4):
        for selection in itertools.combinations(candidates, k):
            reached = {
                i
                for i in range(8)
                if baseline & (1 << i) or any(c.mask & (1 << i) for c in selection)
            }
            totals = [sum(weights[i] for i in reached if i // 4 == g) for g in range(2)]
            p = sorted(100 * totals[g] / sum(weights[g * 4 : g * 4 + 4]) for g in range(2))
            score = (1, sum(totals)) if min(p) >= 50 else (0, *p, sum(totals))
            scores.append((score, tuple(c.id for c in selection)))
    best_score = max(s[0] for s in scores)
    best = min(
        (ids for score, ids in scores if score == best_score), key=lambda ids: (len(ids), ids)
    )
    solution = problem.solve(3)
    assert solution.selected == best
    assert solution.solver == "optimal"
    assert solution.covered & baseline == baseline


def test_heuristic_status_distinguishes_no_proof_from_union_certificate():
    # All candidates together meet the floor, but this budget does not.
    problem = Problem(
        [1, 1, 1], [0, 1, 2], [1, 1, 1], 0, [Candidate(str(i), 1 << i) for i in range(3)]
    )
    assert problem.solve(1, exact_limit=1).floor_status == "not_found"
    assert problem.solve(1).floor_status == "proven_infeasible"
    assert problem.solve(3, exact_limit=1).floor_status == "met"
    impossible = Problem([1, 1], [0, 1], [1, 1], 0, [Candidate("a", 1)])
    assert impossible.solve(1, exact_limit=1).floor_status == "proven_infeasible"


def test_zero_population_no_candidates_and_invalid_inputs():
    problem = Problem([1], [0], [1, 0], 1, [])
    assert problem.solve(20).floor_status == "met"
    assert problem.solve(20).selected == ()
    with pytest.raises(ValueError):
        problem.solve(-1)
    with pytest.raises(ValueError, match="Duplicate"):
        Problem([1], [0], [1], 0, [Candidate("a", 1), Candidate("a", 1)])
    with pytest.raises(ValueError, match="unknown demand"):
        Problem([1], [0], [1], 0, [Candidate("a", 2)])


def test_heuristic_missed_feasible_plan_is_not_reported_as_impossible():
    # A local exchange optimum misses a feasible three-site combination.
    masks = [1888, 988, 1577, 2584, 979, 1516, 1569, 1772]
    problem = Problem(
        [1] * 12,
        [i // 4 for i in range(12)],
        [4] * 3,
        0,
        [Candidate(str(i), mask) for i, mask in enumerate(masks)],
        100,
    )
    heuristic = problem.solve(3, exact_limit=1)
    exact = problem.solve(3)
    assert heuristic.solver == "heuristic"
    assert heuristic.floor_status == "not_found"
    assert exact.floor_status == "met"
    assert exact.selected == ("3", "4", "5")


def test_prepared_recommendations_and_api_failure_modes(monkeypatch):
    from smart_recycling import api

    client = TestClient(api.app)
    response = client.get("/api/v1/upgrades?material=glass&n=5")
    assert response.status_code == 200
    plan = response.json()["plan"]
    assert len(plan["sites"]) <= 5
    assert plan["after_percent"] >= plan["before_percent"]
    assert len(plan["municipalities"]) == 10
    for query in (
        "material=general&n=5",
        "material=glass&n=-1",
        "material=glass&n=21",
        "material=glass&n=1.5",
    ):
        assert client.get("/api/v1/upgrades?" + query).status_code == 422
    monkeypatch.setattr(api, "upgrade_report", None)
    assert client.get("/api/v1/upgrades?material=glass").status_code == 503
    assert client.get("/api/v1/coverage").status_code == 200


def test_artifact_rejects_stale_baseline_and_all_scenarios_preserve_coverage():
    body = (ROOT / "data/coverage/skopje-v1/coverage.json").read_bytes()
    directory = ROOT / "data/upgrades/skopje-v1"
    from smart_recycling import api

    infrastructure = api.snapshots["city"].body
    report = load_upgrades(directory, body, infrastructure)
    assert len(report.plans) == 63
    with pytest.raises(ValueError, match="inputs/code"):
        load_upgrades(directory, body + b" ", infrastructure)
    for plan in report.plans:
        assert plan.after_percent >= plan.before_percent
        if plan.requested_upgrades == 0:
            assert plan.after_percent == plan.before_percent
            assert not plan.sites
    assert json.loads(body)["materials"][0]["city"]["coverage_percent"] == 58.137033


def test_candidate_requires_eligible_general_waste_asset():
    from smart_recycling import api

    snapshot = SiteSnapshot.model_validate_json(api.snapshots["city"].body)
    source = next(s for s in snapshot.sites if is_candidate(s))
    closed = source.model_copy(
        update={
            "assets": tuple(
                a.model_copy(update={"operational_status": "closed"}) for a in source.assets
            )
        }
    )
    assert not is_candidate(closed)
    recycling = source.model_copy(
        update={
            "assets": tuple(
                a.model_copy(update={"asset_type": "recycling_container"}) for a in source.assets
            )
        }
    )
    assert not is_candidate(recycling)


@pytest.mark.parametrize(
    "change", ["code", "checksum", "site", "municipality", "gap", "gain", "missing"]
)
def test_corrupt_upgrade_artifact_fails_closed(tmp_path, change):
    from smart_recycling import api

    source = ROOT / "data/upgrades/skopje-v1/upgrades.json"
    body = json.loads(source.read_bytes())
    plan = body["plans"][5]
    if change == "code":
        body["code_sha256"] = {}
    elif change == "site":
        plan["sites"][0]["id"] = "unknown"
    elif change == "municipality":
        plan["municipalities"][0]["before"] = 99
    elif change == "gap":
        plan["municipalities"][0]["shortfall_pp"] = 99
    elif change == "gain":
        plan["improvement_pp"] = 99
    elif change == "missing":
        body["plans"].pop()
    write_json(tmp_path / "upgrades.json", body)
    write_json(
        tmp_path / "manifest.json",
        {
            "schema_version": 1,
            "sha256": "bad" if change == "checksum" else sha256(tmp_path / "upgrades.json"),
        },
    )
    with pytest.raises(ValueError):
        load_upgrades(
            tmp_path,
            (ROOT / "data/coverage/skopje-v1/coverage.json").read_bytes(),
            api.snapshots["city"].body,
        )
