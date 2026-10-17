"""Validated static upgrade plans, served without the geographic toolchain."""

import hashlib
import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from smart_recycling.coverage_models import CoverageReport
from smart_recycling.geography.io import read_json
from smart_recycling.infrastructure_models import InfrastructureSite, SiteSnapshot

Material = Literal["glass", "plastic_metal", "paper_tetrapak"]


def code_hashes() -> dict[str, str]:
    """Fingerprint all upgrade preparation and contract code with portable newlines."""
    return {
        name: hashlib.sha256(
            (Path(__file__).parent / name).read_text(encoding="utf-8").encode()
        ).hexdigest()
        for name in ("upgrades.py", "upgrades_build.py", "upgrades_solver.py")
    }


def is_candidate(site: InfrastructureSite) -> bool:
    """Require a potentially operational asset explicitly recorded as general waste."""
    return any(
        a.asset_type == "waste_container"
        and "mixed_municipal_waste" in a.source_materials
        and a.operational_status in {"unknown", "open", "operational"}
        for a in site.assets
    )


class MunicipalChange(BaseModel):
    """Coverage before and after, including undefined zero-population areas."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str
    name: str
    population: float = Field(ge=0)
    before: float | None = Field(ge=0, le=100)
    after: float | None = Field(ge=0, le=100)
    shortfall_pp: float | None = Field(ge=0, le=100)


class UpgradeSite(BaseModel):
    """Existing general-waste location proposed for additive recycling service."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str
    name: str
    municipality: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class UpgradePlan(BaseModel):
    """Public plan with bounded search and independent equity evidence."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    material: Material
    requested_upgrades: int = Field(ge=0)
    equity_floor_percent: float = Field(ge=0, le=100)
    candidate_count: int = Field(ge=0)
    before_percent: float = Field(ge=0, le=100)
    after_percent: float = Field(ge=0, le=100)
    improvement_pp: float = Field(ge=0, le=100)
    solver: Literal["optimal", "heuristic"]
    floor_status: Literal["met", "proven_infeasible", "not_found"]
    sites: list[UpgradeSite]
    municipalities: list[MunicipalChange]

    @model_validator(mode="after")
    def consistent(self) -> "UpgradePlan":
        """Reject impossible budgets, decreasing coverage and misleading gaps."""
        if (
            len(self.sites) > min(self.requested_upgrades, self.candidate_count)
            or len({s.id for s in self.sites}) != len(self.sites)
            or self.after_percent < self.before_percent
            or abs(self.after_percent - self.before_percent - self.improvement_pp) > 2e-6
            or len({m.id for m in self.municipalities}) != len(self.municipalities)
        ):
            raise ValueError("Inconsistent upgrade plan")
        for m in self.municipalities:
            if not m.population:
                if any(v is not None for v in (m.before, m.after, m.shortfall_pp)):
                    raise ValueError("Zero-population coverage must be undefined")
            elif (
                m.before is None
                or m.after is None
                or m.shortfall_pp is None
                or m.after < m.before
                or abs(m.shortfall_pp - max(0, self.equity_floor_percent - m.after)) > 2e-6
            ):
                raise ValueError("Invalid municipal change")
        met = all(
            m.after is None or m.after >= self.equity_floor_percent for m in self.municipalities
        )
        if met != (self.floor_status == "met"):
            raise ValueError("Incorrect equity status")
        return self


class UpgradeReport(BaseModel):
    """Prepared scenarios tied to the exact current-coverage artifact."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    coverage_sha256: str
    code_sha256: dict[str, str]
    max_upgrades: int = Field(ge=0, le=100)
    limitations: list[str]
    plans: list[UpgradePlan]


def load_upgrades(
    directory: Path, coverage_body: bytes, infrastructure_body: bytes
) -> UpgradeReport:
    """Fail closed on stale source/model data, corrupted output or missing scenarios."""
    body = (directory / "upgrades.json").read_bytes()
    if read_json(directory / "manifest.json") != {
        "schema_version": 1,
        "sha256": hashlib.sha256(body).hexdigest(),
    }:
        raise ValueError("Upgrade checksum mismatch")
    report = UpgradeReport.model_validate_json(body)
    if (
        report.coverage_sha256 != hashlib.sha256(coverage_body).hexdigest()
        or report.code_sha256 != code_hashes()
    ):
        raise ValueError("Upgrade inputs/code changed; rebuild recommendations")
    coverage = CoverageReport.model_validate_json(coverage_body)
    snapshot = SiteSnapshot.model_validate_json(infrastructure_body)
    if coverage.infrastructure_sha256 != hashlib.sha256(infrastructure_body).hexdigest():
        raise ValueError("Upgrade infrastructure inputs changed")
    candidate_sites = {s.id: s for s in snapshot.sites if is_candidate(s)}
    expected = {
        (material, n)
        for material in ("glass", "plastic_metal", "paper_tetrapak")
        for n in range(report.max_upgrades + 1)
    }
    if {(p.material, p.requested_upgrades) for p in report.plans} != expected or len(
        report.plans
    ) != len(expected):
        raise ValueError("Missing or duplicate upgrade scenarios")
    for plan in report.plans:
        for selected in plan.sites:
            source = candidate_sites.get(selected.id)
            if source is None or (selected.lat, selected.lon) != (
                source.latitude,
                source.longitude,
            ):
                raise ValueError("Recommended site is not an eligible source location")
        baseline = next(m for m in coverage.materials if m.material == plan.material)
        if plan.before_percent != baseline.city.coverage_percent or {
            m.id for m in plan.municipalities
        } != {m.id for m in baseline.municipalities}:
            raise ValueError("Upgrade baseline differs from current coverage")
        for m in plan.municipalities:
            original = next(b for b in baseline.municipalities if b.id == m.id)
            if m.population != original.population or m.before != original.coverage_percent:
                raise ValueError("Municipal baseline differs")
        after = math.fsum(m.population * (m.after or 0) for m in plan.municipalities)
        if abs(after / baseline.city.population - plan.after_percent) > 2e-6:
            raise ValueError("City and municipal changes do not reconcile")
    return report


def payload(report: UpgradeReport, plan: UpgradePlan) -> dict:
    """Include shared reproducibility and uncertainty in each API response."""
    return dict(
        schema_version=1,
        max_upgrades=report.max_upgrades,
        coverage_sha256=report.coverage_sha256,
        limitations=report.limitations,
        plan=json.loads(plan.model_dump_json()),
    )
