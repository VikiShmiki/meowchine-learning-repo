"""Coverage invariants on hand-calculated directed graphs and serving artifacts."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_recycling.coverage import load_coverage
from smart_recycling.coverage_build import compatible_sites, summarize
from smart_recycling.coverage_graph import Segment, connect_network
from smart_recycling.coverage_models import PopulationCoverage
from smart_recycling.geography.io import write_json
from smart_recycling.infrastructure import load_infrastructure
from smart_recycling.infrastructure_models import SiteSnapshot

ROOT = Path(__file__).resolve().parents[1]


def point(
    key, fraction, *, gap=0, nodes=(1, 2), way=10, population=1, status="candidate_unverified"
):
    return dict(
        id=key,
        segment_nodes=list(nodes),
        way_id=way,
        segment_fraction=fraction,
        snap_distance_m=gap,
        snap_status=status,
        population=population,
    )


def test_inclusive_budget_includes_both_terminal_connections():
    rows = [point("d", 0.45, gap=20), point("s", 0.55, gap=30)]
    network = connect_network([Segment(1, 2, 10, 600)], rows, speed_kmh=3.6)
    assert "d" in network.covered(["s"], 110)  # 20 + 60 + 30, not via endpoints.
    assert "d" not in network.covered(["s"], 109.999)


def test_directed_coverage_is_demand_to_site_not_the_reverse():
    rows = [point("left", 0.1), point("right", 0.9)]
    network = connect_network([Segment(1, 2, 10, 500, backward=False)], rows, speed_kmh=3.6)
    assert "left" in network.covered(["right"])
    assert "right" not in network.covered(["left"])


def test_exact_ten_minutes_and_real_detour():
    rows = [point("d", 0), point("s", 1), point("late", 0, gap=1)]
    network = connect_network([Segment(1, 2, 10, 600)], rows, speed_kmh=3.6)
    assert "d" in network.covered(["s"])
    assert "late" not in network.covered(["s"])
    detour = connect_network([Segment(1, 2, 10, 601)], rows, speed_kmh=3.6)
    assert "d" not in detour.covered(["s"])


def test_parallel_streets_and_disconnected_components_do_not_get_bridged():
    rows = [point("d", 0.5), point("s", 0.5, nodes=(3, 4), way=20)]
    network = connect_network([Segment(1, 2, 10, 100), Segment(3, 4, 20, 100)], rows)
    assert "d" not in network.covered(["s"])
    assert "s" in network.covered(["s"])  # Smaller components are retained.


def test_weighted_union_counts_residents_once_and_retains_unconnected():
    rows = [
        point("dense", 0.5, population=80),
        point("sparse", 1, population=10),
        point("unconnected", 0, population=10, status="too_far"),
    ]
    sites = [point("s1", 0.4), point("s2", 0.6)]
    network = connect_network([Segment(1, 2, 10, 2000)], rows + sites, speed_kmh=3.6)
    covered = network.covered(["s1", "s2", "s1"])
    result = summarize(rows, covered)
    assert result["population"] == 100
    assert result["covered_population"] == 80
    assert result["coverage_percent"] == 80  # Not 1/3 sample-point coverage or 160%.
    assert result["unconnected_population"] == 10


def test_zero_population_and_unavailable_are_not_invented_percentages():
    assert summarize([], set())["coverage_percent"] is None
    assert summarize([point("d", 0, population=12)], None)["covered_population"] is None
    with pytest.raises(ValueError):
        PopulationCoverage(
            population=0, covered_population=0, coverage_percent=100, unconnected_population=0
        )


@pytest.mark.parametrize(
    "change",
    [
        dict(segment_fraction=1.1),
        dict(snap_distance_m=101),
        dict(way_id=999),
        dict(snap_status="verified"),
    ],
)
def test_invalid_connections_are_rejected(change):
    with pytest.raises(ValueError):
        connect_network([Segment(1, 2, 10, 100)], [point("d", 0.5) | change])


def test_duplicate_population_and_connections_are_rejected():
    row = point("d", 0.5)
    with pytest.raises(ValueError):
        connect_network([Segment(1, 2, 10, 100)], [row, row])
    with pytest.raises(ValueError):
        summarize([row, row], set())


@pytest.fixture
def snapshot_body():
    return load_infrastructure(
        ROOT / "data/infrastructure/skopje-2026-09-19", ROOT / "data/policy/skopje_v1.json"
    )["city"].body


def test_acceptance_requires_full_profile_on_one_open_or_unknown_asset(snapshot_body):
    snapshot = SiteSnapshot.model_validate_json(snapshot_body)
    kinds = {"empty_plastic_bottle", "empty_metal_can"}
    eligible = compatible_sites(snapshot, kinds)
    assert len(eligible) == 86
    closed = snapshot.model_copy(
        update={
            "sites": tuple(
                site.model_copy(
                    update={
                        "assets": tuple(
                            asset.model_copy(update={"operational_status": "closed"})
                            for asset in site.assets
                        )
                    }
                )
                for site in snapshot.sites
            )
        }
    )
    assert compatible_sites(closed, kinds) == []
    assert compatible_sites(snapshot, set()) == []
    assert all(
        any(a.acceptance and kinds <= set(a.acceptance.accepted_item_kinds) for a in site.assets)
        for site in snapshot.sites
        if site.id in eligible
    )


def test_artifact_serving_and_changed_acceptance_input_rejection(snapshot_body):
    path = ROOT / "data/coverage/skopje-v1"
    result = load_coverage(path, snapshot_body)
    assert json.loads(result.body)["method"].endswith("approximation")
    with pytest.raises(ValueError, match="acceptance inputs"):
        load_coverage(path, snapshot_body + b" ")


@pytest.mark.parametrize("corruption", ["checksum", "total", "floor", "code", "municipality"])
def test_corrupt_or_stale_artifacts_fail_closed(tmp_path, snapshot_body, corruption):
    source = ROOT / "data/coverage/skopje-v1"
    data = json.loads((source / "coverage.json").read_bytes())
    if corruption == "total":
        data["materials"][0]["city"]["coverage_percent"] = 100
    elif corruption == "floor":
        data["materials"][0]["municipalities"][0]["shortfall_pp"] = 49.123
    elif corruption == "code":
        data["code_sha256"]["coverage_graph.py"] = "changed"
    elif corruption == "municipality":
        data["materials"][0]["municipalities"].pop()
    write_json(tmp_path / "coverage.json", data)
    digest = hashlib.sha256((tmp_path / "coverage.json").read_bytes()).hexdigest()
    write_json(
        tmp_path / "manifest.json",
        {"schema_version": 1, "sha256": "wrong" if corruption == "checksum" else digest},
    )
    with pytest.raises(ValueError):
        load_coverage(tmp_path, snapshot_body)


def test_http_report_cache_and_missing_report_have_no_fallback(monkeypatch):
    from smart_recycling import api

    client = TestClient(api.app)
    response = client.get("/api/v1/coverage")
    assert response.status_code == 200
    report = response.json()
    assert report["threshold_seconds"] == 600
    assert len(report["materials"][0]["municipalities"]) == 10
    assert report["materials"][-1]["city"]["coverage_percent"] is None
    assert (
        client.get(
            "/api/v1/coverage", headers={"If-None-Match": response.headers["etag"]}
        ).status_code
        == 304
    )
    assert client.get("/city").status_code == 200
    monkeypatch.setattr(api, "coverage_snapshot", None)
    assert client.get("/api/v1/coverage").status_code == 503
    assert client.get("/").status_code == 200


def test_api_startup_does_not_import_offline_graph_toolchain():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import smart_recycling.api; "
            "assert not {'networkx', 'osmium', 'rasterio', 'scipy'} & set(sys.modules)",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(("extra", "expected"), [(0.5e-9, True), (2e-9, False)])
def test_time_boundary_tolerance_is_consistent(extra, expected):
    network = connect_network(
        [Segment(1, 2, 10, 600 + extra)], [point("d", 0), point("s", 1)], speed_kmh=3.6
    )
    assert ("d" in network.covered(["s"])) is expected
