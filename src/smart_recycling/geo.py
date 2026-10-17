"""Deterministic geospatial calculations."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

from smart_recycling.domain import Site, WasteCategory

EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class NearestSite:
    site: Site
    distance_m: float


def haversine_m(start: tuple[float, float], end: tuple[float, float]) -> float:
    """Return straight-line distance over Earth between two WGS84 coordinates."""
    lat1, lon1 = start
    lat2, lon2 = end
    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
        raise ValueError("latitude must be between -90 and 90")
    if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        raise ValueError("longitude must be between -180 and 180")

    lat_delta = radians(lat2 - lat1)
    lon_delta = radians(lon2 - lon1)
    value = (
        sin(lat_delta / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(lon_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * asin(sqrt(value))


def nearest_site(
    sites: Iterable[Site], material: WasteCategory, origin: tuple[float, float]
) -> NearestSite | None:
    if material is WasteCategory.SPECIAL_UNSUPPORTED:
        raise ValueError("special_unsupported is not a collection material")

    candidates = (
        NearestSite(site, haversine_m(origin, (site.latitude, site.longitude)))
        for site in sites
        if material in site.materials
    )
    return min(
        candidates, key=lambda result: (result.distance_m, result.site.site_id), default=None
    )
