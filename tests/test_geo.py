import pytest

from smart_recycling.domain import Site, WasteCategory
from smart_recycling.geo import haversine_m, nearest_site


def site(site_id: str, latitude: float, longitude: float) -> Site:
    return Site(
        site_id=site_id,
        name=site_id,
        latitude=latitude,
        longitude=longitude,
        materials=frozenset({WasteCategory.GLASS}),
    )


def test_haversine_is_zero_for_same_coordinate() -> None:
    assert haversine_m((41.99, 21.43), (41.99, 21.43)) == pytest.approx(0.0)


def test_nearest_site_uses_distance() -> None:
    result = nearest_site(
        [site("far", 42.02, 21.43), site("near", 41.991, 21.43)],
        WasteCategory.GLASS,
        (41.99, 21.43),
    )

    assert result is not None
    assert result.site.site_id == "near"
    assert result.distance_m == pytest.approx(111.2, abs=1.0)


def test_nearest_site_has_deterministic_tie_break() -> None:
    result = nearest_site(
        [site("b", 41.99, 21.43), site("a", 41.99, 21.43)],
        WasteCategory.GLASS,
        (41.99, 21.43),
    )

    assert result is not None
    assert result.site.site_id == "a"


def test_special_waste_is_not_a_physical_collection_material() -> None:
    with pytest.raises(ValueError, match="not a collection material"):
        nearest_site([], WasteCategory.SPECIAL_UNSUPPORTED, (41.99, 21.43))
