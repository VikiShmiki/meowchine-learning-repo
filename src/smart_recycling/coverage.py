"""Lightweight serving of validated, precomputed City coverage; no geo dependencies."""

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from smart_recycling.coverage_build import code_hashes
from smart_recycling.coverage_models import CoverageReport
from smart_recycling.geography.io import read_json

MUNICIPALITIES = {
    "aerodrom",
    "butel",
    "centar",
    "chair",
    "gazi_baba",
    "gjorche_petrov",
    "karposh",
    "kisela_voda",
    "saraj",
    "shuto_orizari",
}


@dataclass(frozen=True)
class CoverageSnapshot:
    """Validated public payload and its content-based cache validator."""

    body: bytes
    etag: str


def load_coverage(directory: Path, infrastructure_body: bytes) -> CoverageSnapshot:
    """Reject corruption, stale acceptance inputs/code, and inconsistent report totals."""
    body = (directory / "coverage.json").read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    manifest = read_json(directory / "manifest.json")
    if manifest != {"schema_version": 1, "sha256": digest}:
        raise ValueError("Coverage checksum/version mismatch; rebuild coverage")
    report = CoverageReport.model_validate_json(body)
    if report.infrastructure_sha256 != hashlib.sha256(infrastructure_body).hexdigest():
        raise ValueError("Coverage acceptance inputs changed; rebuild coverage")
    if report.code_sha256 != code_hashes():
        raise ValueError("Coverage implementation changed; rebuild coverage")
    if {r.material for r in report.materials} != {
        "glass",
        "plastic_metal",
        "paper_tetrapak",
        "general",
    } or len(report.materials) != 4:
        raise ValueError("Missing/duplicate material results")
    populations = []
    for result in report.materials:
        if {m.id for m in result.municipalities} != MUNICIPALITIES or len(
            result.municipalities
        ) != 10:
            raise ValueError("Missing/duplicate municipalities")
        if result.connected_site_count > result.compatible_site_count:
            raise ValueError("Impossible site count")
        available = result.status == "approximation"
        if available != bool(result.required_item_kinds) or (not available and not result.reason):
            raise ValueError("Unexplained or unsupported coverage")
        for value in [result.city, *result.municipalities]:
            if available != (value.covered_population is not None):
                raise ValueError("Inconsistent coverage availability")
        for field in ("population", "unconnected_population", "covered_population"):
            total = getattr(result.city, field)
            if total is not None and not math.isclose(
                total, math.fsum(getattr(m, field) for m in result.municipalities), abs_tol=0.001
            ):
                raise ValueError("Municipal totals do not reconcile")
        for m in result.municipalities:
            percent = m.coverage_percent
            expected = None if percent is None else max(0, report.equity_floor_percent - percent)
            if (
                m.underserved
                != (None if percent is None else percent < report.equity_floor_percent)
                or (expected is None) != (m.shortfall_pp is None)
                or (expected is not None and abs(m.shortfall_pp - expected) > 0.001)
            ):
                raise ValueError("Incorrect municipal shortfall")
        populations.append((result.city.population, result.city.unconnected_population))
    if len(set(populations)) != 1:
        raise ValueError("Material denominators differ")
    return CoverageSnapshot(body, f'"{digest}"')
