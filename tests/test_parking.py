"""Parking access, directed car/walk continuity and honest failure behavior."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from smart_recycling.ors import NetworkRoute
from smart_recycling.parking import ParkingPlanner
from smart_recycling.parking_data import (
    ParkingCatalog,
    ParkingPlace,
    ParkingSnapshot,
    public_parking,
    records_hash,
)
from smart_recycling.routing_models import RoutingError, TripRequest
from smart_recycling.transit import distance

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def place(identifier=1, longitude=21.401):
    return ParkingPlace(
        id=f"osm-node-{identifier}",
        name=f"Parking {identifier}",
        latitude=42,
        longitude=longitude,
        access="yes",
        point_kind="mapped_point",
    )


def snapshot(places=None):
    places = places or [place(), place(2, 21.419)]
    return ParkingSnapshot(
        dataset_version="synthetic-parking",
        source_timestamp=NOW.isoformat(),
        source_url="https://example.invalid/fixture",
        source_sha256="a" * 64,
        records_sha256=records_hash(places),
        places=places,
    )


class Catalog:
    def __init__(self, places=None):
        self.snapshot = snapshot(places)

    def get(self):
        return self.snapshot


class Roads:
    def __init__(self):
        self.calls = []
        self.blocked = set()
        self.extra = 0

    def matrix(self, mode, points, **kwargs):
        self.calls.append(("matrix", mode, points))
        return [
            [
                None
                if (mode, tuple(a), tuple(b)) in self.blocked
                else distance(a, b) / (8 if mode == "driving" else 1.33)
                for b in points
            ]
            for a in points
        ]

    def directions(self, mode, points):
        self.calls.append(("directions", mode, points))
        length = sum(distance(a, b) for a, b in zip(points, points[1:], strict=False))
        return NetworkRoute(
            points,
            length,
            length / (8 if mode == "driving" else 1.33) + self.extra,
            [0] * len(points),
        )


def candidate(identifier="glass", longitude=21.402, kind="glass"):
    return SimpleNamespace(
        site=SimpleNamespace(id=identifier, latitude=42, longitude=longitude),
        kinds=frozenset({kind}),
    )


def request():
    return TripRequest(
        origin={"latitude": 42, "longitude": 21.4},
        mode="driving",
        include_parking=True,
        items=[{"material": "glass", "condition_confirmed": True}],
        share_coordinates=True,
    )


def test_drive_to_parking_and_walk_instead_of_driving_to_bin():
    roads = Roads()
    indices, route, extra = ParkingPlanner(Catalog(), roads).plan(
        request(), [candidate()], ("glass",)
    )
    assert indices == [0]
    assert route.geometry[-1] == [21.401, 42]
    visit = extra["parking"][0]
    assert visit["walk_to"]["geometry"]["coordinates"][-1] == [21.402, 42]
    assert visit["walk_back"] is None
    assert extra["driving_duration_s"] + extra["walking_duration_s"] == route.duration_s
    assert any("not a reserved or available space" in w for w in route.warnings)
    assert extra["profile"] == "driving-car+foot-walking"


def test_multi_stop_returns_to_car_and_includes_directional_walk_in_total():
    roads = Roads()
    indices, route, extra = ParkingPlanner(Catalog(), roads).plan(
        request(), [candidate(), candidate("paper", 21.42, "paper")], ("glass", "paper")
    )
    assert indices == [0, 1]
    first, last = extra["parking"]
    assert first["walk_back"]["geometry"]["coordinates"] == [[21.402, 42], [21.401, 42]]
    assert last["walk_back"] is None
    drive = next(c for c in roads.calls if c[:2] == ("directions", "driving"))
    assert drive[2] == [[21.4, 42], [21.401, 42], [21.419, 42]]
    assert (
        extra["walking_duration_s"]
        == first["walk_to"]["duration_s"]
        + first["walk_back"]["duration_s"]
        + last["walk_to"]["duration_s"]
    )


def test_unreachable_return_requires_that_dropoff_to_be_last():
    roads = Roads()
    roads.blocked.add(("walking", (21.402, 42), (21.401, 42)))
    indices, _, extra = ParkingPlanner(Catalog(), roads).plan(
        request(), [candidate(), candidate("paper", 21.42, "paper")], ("glass", "paper")
    )
    assert indices == [1, 0]
    assert extra["parking"][-1]["walk_back"] is None


def test_unreachable_parking_fails_whole_basket_without_direct_fallback():
    roads = Roads()
    roads.blocked.add(("driving", (21.4, 42), (21.401, 42)))
    with pytest.raises(RoutingError) as error:
        ParkingPlanner(Catalog(), roads).plan(request(), [candidate()], ("glass",))
    assert error.value.code == "parking_no_route"
    assert not any(call[0] == "directions" for call in roads.calls)


def test_actual_walk_must_still_fit_budget():
    roads = Roads()
    roads.extra = 601
    with pytest.raises(RoutingError) as error:
        ParkingPlanner(Catalog(), roads).plan(request(), [candidate()], ("glass",))
    assert error.value.code == "parking_connection"


def test_no_parking_in_radius_is_explicit():
    with pytest.raises(RoutingError, match="No mapped public parking"):
        ParkingPlanner(Catalog(), Roads()).plan(request(), [candidate(longitude=21.55)], ("glass",))


@pytest.mark.parametrize(
    "tags",
    [
        {"access": "private"},
        {"access": "customers"},
        {"access": "permit"},
        {"access": "visitors"},
        {"access": ""},
        {"access": "yes", "motorcar": "no"},
        {"access": "yes", "foot": "no"},
        {"access": "yes", "access:conditional": "no @ (Mo-Fr)"},
        {"access": "yes", "parking": "underground"},
    ],
)
def test_restricted_or_uncertain_parking_is_not_recommended(tags):
    assert not public_parking({"amenity": "parking", **tags})


def test_catalog_checksum_expiry_missing_file_and_future_date(tmp_path):
    path = tmp_path / "parking.json"
    with pytest.raises(RoutingError):
        ParkingCatalog(path, lambda: NOW).get()
    path.write_text(snapshot().model_dump_json(), encoding="utf-8")
    assert len(ParkingCatalog(path, lambda: NOW).get().places) == 2
    for time in [NOW + timedelta(days=91), NOW - timedelta(days=2)]:
        with pytest.raises(RoutingError):
            ParkingCatalog(path, lambda time=time: time).get()
    path.write_text(
        path.read_text(encoding="utf-8").replace("Parking 1", "Tampered"), encoding="utf-8"
    )
    with pytest.raises(RoutingError):
        ParkingCatalog(path, lambda: NOW).get()


def test_parking_requires_driving_and_strict_consent_boolean():
    payload = request().model_dump()
    payload["mode"] = "walking"
    with pytest.raises(ValidationError):
        TripRequest.model_validate(payload)
    payload["mode"] = "driving"
    payload["include_parking"] = "yes"
    with pytest.raises(ValidationError):
        TripRequest.model_validate(payload)


def test_bundled_snapshot_has_valid_checksum_and_provenance():
    data = ParkingSnapshot.model_validate_json(
        Path("data/parking/skopje-v1/parking.json").read_bytes()
    )
    assert len(data.places) > 100
    assert data.source_url.startswith("https://download.geofabrik.de/europe/macedonia-")
    assert all(p.source_url.startswith("https://www.openstreetmap.org/") for p in data.places)


def test_bad_first_parking_matrix_point_does_not_discard_other_candidates():
    import httpx

    from smart_recycling.ors import ORSProvider

    provider = ORSProvider(
        "fixture",
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "durations": [[0, 10], [20, 0]],
                    "sources": [None, {"location": [21.5, 42]}],
                    "destinations": [None, {"location": [21.5, 42]}],
                },
            )
        ),
    )
    points = [[21.4, 42], [21.5, 42]]
    assert provider.matrix("walking", points, require_origin=False) == [[None, None], [None, 0]]
    with pytest.raises(RoutingError, match="Starting point"):
        provider.matrix("walking", points)


def test_driveway_crossing_excludes_oneway_exits_and_tangencies():
    import importlib.util

    from shapely import LineString, box

    spec = importlib.util.spec_from_file_location("prepare_parking", "scripts/prepare_parking.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shape = box(0, 0, 1, 1)
    line = LineString([(-1, 0.5), (2, 0.5)])
    assert [p.x for p in module.entry_crossings(shape, line, "yes")] == [0]
    assert [p.x for p in module.entry_crossings(shape, line, "-1")] == [1]
    assert len(list(module.entry_crossings(shape, line, "no"))) == 2
    assert not list(module.entry_crossings(shape, LineString([(-1, 0), (2, 0)]), "no"))
