"""Offline catchment preparation and bounded equitable upgrade optimization."""

import argparse
import hashlib
import math
from pathlib import Path

from smart_recycling.coverage import load_coverage
from smart_recycling.coverage_build import STREAMS, compatible_sites, load_inputs
from smart_recycling.coverage_models import CoverageReport
from smart_recycling.geography.io import read_json, sha256, write_json
from smart_recycling.upgrades import UpgradeReport, code_hashes, is_candidate
from smart_recycling.upgrades_solver import Candidate, Problem


def prepare(root: Path, max_upgrades: int = 20, floor: float = 50) -> UpgradeReport:
    """Precompute all budgets with shared directed pedestrian terminal catchments."""
    if not 0 <= max_upgrades <= 100 or not 0 <= floor <= 100:
        raise ValueError("Budget cap must be 0..100 and floor 0..100")
    manifest, rows, snapshot, snapshot_body, network = load_inputs(root)
    coverage_body = load_coverage(root / "data/coverage/skopje-v1", snapshot_body).body
    coverage = CoverageReport.model_validate_json(coverage_body)
    rows = sorted(rows, key=lambda r: r["id"])
    bits = {r["id"]: 1 << i for i, r in enumerate(rows)}

    def catchment(ids: list[str]) -> int:
        return sum(bits.get(key, 0) for key in network.covered(ids))

    municipalities = manifest["municipalities"]
    groups = [
        next(i for i, m in enumerate(municipalities) if m["id"] == r["municipality_id"])
        for r in rows
    ]
    weights = [r["population"] for r in rows]
    denominators = [
        math.fsum(w for w, g in zip(weights, groups, strict=True) if g == i)
        for i in range(len(municipalities))
    ]
    sites = {s.id: s for s in snapshot.sites if is_candidate(s)}
    candidates = [
        Candidate(key, catchment([key]))
        for key in sorted(sites)
        if network.connections[key] is not None
    ]
    print(f"Prepared {len(candidates)} connected general-waste catchments", flush=True)
    plans = []
    for material, (_, kinds) in STREAMS.items():
        if not kinds:
            continue
        compatible = compatible_sites(snapshot, kinds)
        baseline = catchment(compatible)
        eligible = [c for c in candidates if c.id not in compatible and c.mask & ~baseline]
        problem = Problem(weights, groups, denominators, baseline, eligible, floor)
        before = next(m for m in coverage.materials if m.material == material)
        baseline_totals = problem.totals(baseline)
        if abs(math.fsum(baseline_totals) - before.city.covered_population) > 1e-6:
            raise ValueError("Recomputed baseline differs from published coverage")
        for n in range(max_upgrades + 1):
            solution = problem.solve(n)
            after = round(100 * math.fsum(solution.totals) / math.fsum(weights), 6)
            changes = []
            for i, m in enumerate(municipalities):
                original = next(b for b in before.municipalities if b.id == m["id"])
                percent = (
                    round(100 * solution.totals[i] / denominators[i], 6)
                    if denominators[i]
                    else None
                )
                changes.append(
                    dict(
                        id=m["id"],
                        name=m["name"],
                        population=original.population,
                        before=original.coverage_percent,
                        after=percent,
                        shortfall_pp=None if percent is None else round(max(0, floor - percent), 6),
                    )
                )
            selected = []
            for key in solution.selected:
                site = sites[key]
                asset = next(
                    a for a in site.assets if "mixed_municipal_waste" in a.source_materials
                )
                selected.append(
                    dict(
                        id=key,
                        name=asset.name,
                        municipality=asset.municipality_name,
                        lat=site.latitude,
                        lon=site.longitude,
                    )
                )
            plans.append(
                dict(
                    material=material,
                    requested_upgrades=n,
                    equity_floor_percent=floor,
                    candidate_count=len(eligible),
                    before_percent=before.city.coverage_percent,
                    after_percent=after,
                    improvement_pp=round(after - before.city.coverage_percent, 6),
                    solver=solution.solver,
                    floor_status=solution.floor_status,
                    sites=selected,
                    municipalities=changes,
                )
            )
        print(f"Solved {material}: budgets 0..{max_upgrades}", flush=True)
    return UpgradeReport(
        coverage_sha256=hashlib.sha256(coverage_body).hexdigest(),
        code_sha256=code_hashes(),
        max_upgrades=max_upgrades,
        plans=plans,
        limitations=[
            (
                "Population-weighted walking-network approximation: inherits all current coverage "
                "source and unverified connector limits. Not navigation or installation approval."
            ),
            (
                "Upgrades add full reviewed stream acceptance and preserve general waste. Closed, "
                "disconnected, already compatible and zero-gain sites are excluded. Operation and "
                "physical suitability need field review."
            ),
            (
                "Exact enumeration when at most 10,000 subsets; otherwise deterministic "
                "equity-first "
                "greedy addition and two single-site exchange passes. Heuristic results are not "
                "proven "
                "globally optimal."
            ),
            (
                "Proven infeasible means exhaustive search failed or even upgrading every eligible "
                "candidate cannot meet all municipal floors. Not found means heuristic failure "
                "without "
                "proof."
            ),
            (
                "The municipal floor is project policy. Municipal averages can conceal underserved "
                "smaller neighborhoods. NoData remains unknown, not zero."
            ),
        ],
    )


def main() -> None:
    """Write a new deterministic artifact or reproduce the published scenarios."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("data/upgrades/skopje-v1"))
    parser.add_argument("--max-upgrades", type=int, default=20)
    parser.add_argument("--floor", type=float, default=50)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = prepare(args.root, args.max_upgrades, args.floor).model_dump(mode="json")
    if args.check:
        if read_json(args.out / "upgrades.json") != report:
            raise ValueError("Upgrade artifact differs; rebuild and review")
        print("PASS: upgrade scenarios reproduced")
        return
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError("Use a new empty output directory")
    args.out.mkdir(parents=True, exist_ok=True)
    write_json(args.out / "upgrades.json", report)
    write_json(
        args.out / "manifest.json",
        {"schema_version": 1, "sha256": sha256(args.out / "upgrades.json")},
    )


if __name__ == "__main__":
    main()
