"""Shared domain types with no framework dependencies."""

from dataclasses import dataclass
from enum import StrEnum


class WasteCategory(StrEnum):
    GLASS = "glass"
    PLASTIC_METAL = "plastic_metal"
    PAPER_TETRAPAK = "paper_tetrapak"
    GENERAL = "general"
    SPECIAL_UNSUPPORTED = "special_unsupported"


@dataclass(frozen=True)
class Prediction:
    category: WasteCategory | None
    confidence: float
    abstained: bool
    model_version: str


@dataclass(frozen=True)
class Site:
    site_id: str
    name: str
    latitude: float
    longitude: float
    materials: frozenset[WasteCategory]
