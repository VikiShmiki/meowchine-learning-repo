"""Public, versioned population coverage contracts; estimates are never field claims."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Count = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Percent = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Material = Literal["glass", "plastic_metal", "paper_tetrapak", "general"]


class PopulationCoverage(BaseModel):
    """An inclusive population denominator and an optional supported estimate."""

    model_config = ConfigDict(extra="forbid")
    population: Count
    covered_population: Count | None
    coverage_percent: Percent | None
    unconnected_population: Count

    @model_validator(mode="after")
    def consistent(self):
        """Reject impossible totals or invented zero-population percentages."""
        if self.unconnected_population > self.population + 0.001:
            raise ValueError("Unconnected population exceeds denominator")
        if self.covered_population is None:
            if self.coverage_percent is not None:
                raise ValueError("Unavailable coverage must not have a percentage")
        else:
            if self.covered_population > self.population - self.unconnected_population + 0.001:
                raise ValueError("Covered population exceeds connected population")
            expected = 100 * self.covered_population / self.population if self.population else None
            if expected is None and self.coverage_percent is not None:
                raise ValueError("Zero-population coverage is undefined")
            if expected is not None and (
                self.coverage_percent is None or abs(expected - self.coverage_percent) > 0.001
            ):
                raise ValueError("Coverage percentage disagrees with totals")
        return self


class MunicipalityCoverage(PopulationCoverage):
    """Municipal coverage and shortfall against the project policy floor."""

    id: str
    name: str
    underserved: bool | None
    shortfall_pp: Percent | None


class MaterialCoverage(BaseModel):
    """Material service is scoped to the listed item types on a single asset."""

    material: Material
    label: str
    status: Literal["approximation", "unavailable"]
    reason: str | None = None
    required_item_kinds: list[str]
    compatible_site_count: int = Field(ge=0)
    connected_site_count: int = Field(ge=0)
    city: PopulationCoverage
    municipalities: list[MunicipalityCoverage]


class CoverageReport(BaseModel):
    """Prepared result consumed without a graph toolchain in the web server."""

    schema_version: Literal[1] = 1
    region: Literal["skopje"] = "skopje"
    method: Literal["population_weighted_walking_network_approximation"]
    threshold_seconds: Literal[600] = 600
    walking_speed_kmh: Count
    connector_limit_m: Count
    equity_floor_percent: Percent
    population_product: str
    population_year: int
    network_timestamp: str
    infrastructure_version: str
    policy_version: str
    source_as_of: str
    infrastructure_sha256: str
    input_sha256: dict[str, str]
    code_sha256: dict[str, str]
    nodata_area_km2: Count
    limitations: list[str]
    attribution: list[str]
    materials: list[MaterialCoverage]
