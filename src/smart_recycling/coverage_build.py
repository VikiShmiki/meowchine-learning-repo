"""Offline coverage preparation using pinned inputs; no external routing calls."""

import argparse
import hashlib
import math
from pathlib import Path

from smart_recycling.coverage_graph import Segment, connect_network
from smart_recycling.coverage_models import CoverageReport, PopulationCoverage
from smart_recycling.geography.io import read_json, sha256, write_json
from smart_recycling.infrastructure import load_infrastructure
from smart_recycling.infrastructure_models import SiteSnapshot

STREAMS = {
    "glass": ("Glass packaging", {"empty_glass_packaging"}),
    "plastic_metal": ("Plastic bottles / metal cans", {"empty_plastic_bottle", "empty_metal_can"}),
    "paper_tetrapak": (
        "Paper / cardboard / Tetra Pak",
        {"clean_paper", "clean_cardboard", "empty_tetrapak"},
    ),
    "general": ("General waste", set()),
}
CODE_FILES = (
    "coverage_build.py",
    "coverage_graph.py",
    "coverage_models.py",
    "geography/network.py",
)


def code_hashes() -> dict[str, str]:
    """Normalize source newlines to make Windows/Linux provenance identical."""
    root = Path(__file__).parent
    return {
        name: hashlib.sha256((root / name).read_text(encoding="utf-8").encode()).hexdigest()
        for name in CODE_FILES
    }


def compatible_sites(snapshot: SiteSnapshot, kinds: set[str]) -> list[str]:
    """Require one eligible asset accepting every reviewed item type in the stream."""
    if not kinds:
        return []
    return sorted(
        site.id
        for site in snapshot.sites
        if any(
            asset.operational_status in {"unknown", "open", "operational"}
            and asset.acceptance is not None
            and kinds <= set(asset.acceptance.accepted_item_kinds)
            for asset in site.assets
        )
    )


def summarize(rows: list[dict], covered: set[str] | None) -> dict:
    """Sum each weighted demand record once, retaining all disconnected population."""
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)) or any(
        not math.isfinite(row["population"]) or row["population"] < 0 for row in rows
    ):
        raise ValueError("Duplicate demand IDs or invalid population")
    total = math.fsum(row["population"] for row in rows)
    reached = (
        None
        if covered is None
        else math.fsum(row["population"] for row in rows if row["id"] in covered)
    )
    return PopulationCoverage(
        population=round(total, 6),
        covered_population=None if reached is None else round(reached, 6),
        coverage_percent=None if reached is None or not total else round(100 * reached / total, 6),
        unconnected_population=round(
            math.fsum(row["population"] for row in rows if row["snap_status"] == "too_far"), 6
        ),
    ).model_dump()


def load_inputs(root: Path) -> tuple:
    """Load verified population, site and pedestrian inputs for offline City analysis."""
    # Offline extras stay out of API startup and the production dependency set.
    from smart_recycling.geography.network import diagnostic_graph
    from smart_recycling.geography.validate import validate_package

    geography = root / "data/geography/skopje-v1"
    directory = geography / "prepared"
    infrastructure = root / "data/infrastructure/skopje-2026-09-19"
    policy = root / "data/policy/skopje_v1.json"
    validate_package(directory, geography / "sources.json", infrastructure)
    manifest = read_json(directory / "manifest.json")
    if manifest["coverage_seconds"] != 600:
        raise ValueError("T08 requires the agreed 10-minute threshold")
    snapshot_body = load_infrastructure(infrastructure, policy)["city"].body
    snapshot = SiteSnapshot.model_validate_json(snapshot_body)
    population = read_json(directory / "population.json.gz")
    access = read_json(directory / "site_access.json.gz")["walk"]
    if {row["id"] for row in access} != {site.id for site in snapshot.sites}:
        raise ValueError("Site connections do not match the serving snapshot")
    graph, _ = diagnostic_graph(
        read_json(directory / "network.json.gz"),
        "walk",
        manifest["metric_crs"],
        manifest["walking_speed_kmh"],
    )
    segments = {}
    for u, v, data in graph.edges(data=True):
        key = (min(u, v), max(u, v), data["way_id"])
        row = segments.setdefault(
            key, dict(length_m=data["length_m"], forward=False, backward=False)
        )
        if not math.isclose(row["length_m"], data["length_m"], abs_tol=1e-6):
            raise ValueError("Inconsistent parallel segment lengths")
        row["forward" if u < v else "backward"] = True
    network = connect_network(
        [Segment(*key, **value) for key, value in sorted(segments.items())],
        population + access,
        manifest["walking_speed_kmh"],
        manifest["snap_limit_m"],
    )
    return manifest, population, snapshot, snapshot_body, network


def prepare(root: Path) -> CoverageReport:
    """Build the full fixed 600-second report from verified shared inputs."""
    manifest, population, snapshot, snapshot_body, network = load_inputs(root)
    geography = root / "data/geography/skopje-v1"
    directory = geography / "prepared"
    results = []
    for material, (label, kinds) in STREAMS.items():
        site_ids = compatible_sites(snapshot, kinds)
        covered = network.covered(site_ids) if kinds else None
        municipalities = []
        for municipality in manifest["municipalities"]:
            summary = summarize(
                [r for r in population if r["municipality_id"] == municipality["id"]], covered
            )
            percent = summary["coverage_percent"]
            municipalities.append(
                dict(
                    id=municipality["id"],
                    name=municipality["name"],
                    **summary,
                    underserved=None if percent is None else percent < 50,
                    shortfall_pp=None if percent is None else round(max(0, 50 - percent), 6),
                )
            )
        results.append(
            dict(
                material=material,
                label=label,
                status="approximation" if kinds else "unavailable",
                reason=None
                if kinds
                else "No positively reviewed general-waste item acceptance profile.",
                required_item_kinds=sorted(kinds),
                compatible_site_count=len(site_ids),
                connected_site_count=sum(network.connections[key] is not None for key in site_ids),
                city=summarize(population, covered),
                municipalities=municipalities,
            )
        )
    qa = read_json(directory / "qa.json")
    return CoverageReport(
        method="population_weighted_walking_network_approximation",
        walking_speed_kmh=manifest["walking_speed_kmh"],
        connector_limit_m=manifest["snap_limit_m"],
        equity_floor_percent=50,
        population_product=manifest["population_product"],
        population_year=manifest["population_year"],
        network_timestamp=manifest["network_timestamp"],
        infrastructure_version=snapshot.dataset_version,
        policy_version=snapshot.policy_version,
        source_as_of=snapshot.as_of_date,
        infrastructure_sha256=hashlib.sha256(snapshot_body).hexdigest(),
        input_sha256={name: metadata["sha256"] for name, metadata in manifest["artifacts"].items()}
        | {
            "geography_manifest": sha256(directory / "manifest.json"),
            "geography_sources": sha256(geography / "sources.json"),
        },
        code_sha256=code_hashes(),
        nodata_area_km2=qa["population"]["nodata_area_km2"],
        limitations=[
            (
                "Approximation: population and site access connectors are unverified and may "
                "cross barriers, water or private land. Field-verified entrances/access paths "
                "are missing."
            ),
            (
                "Both terminal connector distances are included in 600 seconds, at 4.8 km/h; "
                "connectors never bridge different streets. Links beyond 100 m are excluded, "
                "but their population stays in the denominator."
            ),
            (
                "WorldPop 2025 alpha modeled population is not a census. NoData is unknown, not "
                "zero; the denominator includes only valid modeled residents. Border pixels are "
                "apportioned by area."
            ),
            (
                "The conservative pinned OSM walking profile excludes conditional/unknown "
                "access and foot-restricted ways. Flat speed ignores slope, signals, mobility "
                "differences and temporary closures; this is not navigation."
            ),
            (
                "Coverage requires a single asset accepting all listed reviewed item types. "
                "Narrow vending profiles do not establish full material-stream service. Unknown "
                "operation is included; human policy/field review remains pending."
            ),
            (
                "The 50% municipal floor is project policy, not a public standard. Municipal "
                "averages cannot establish coverage in every smaller neighborhood. Upgrade "
                "recommendations are not part of this report."
            ),
        ],
        attribution=[
            source["attribution"] + " | " + source["license"] for source in manifest["sources"]
        ],
        materials=results,
    )


def main() -> None:
    """Write a new artifact or verify deterministic reproduction without overwriting."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("data/coverage/skopje-v1"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = prepare(args.root).model_dump(mode="json")
    if args.check:
        if read_json(args.out / "coverage.json") != report:
            raise ValueError("Coverage artifact differs; reproduce and review a new snapshot")
        print("PASS: coverage reproduced from pinned population, network and acceptance inputs")
        return
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("Output must be empty; use --check or a new --out directory")
    args.out.mkdir(parents=True, exist_ok=True)
    write_json(args.out / "coverage.json", report)
    write_json(
        args.out / "manifest.json",
        {"schema_version": 1, "sha256": sha256(args.out / "coverage.json")},
    )
    for material in report["materials"]:
        print(
            material["material"],
            material["city"]["coverage_percent"],
            material["compatible_site_count"],
        )


if __name__ == "__main__":
    main()
