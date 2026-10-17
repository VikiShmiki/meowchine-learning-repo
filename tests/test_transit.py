"""Transit behaviour: real calendar semantics, transfers, walking and failure paths."""

from datetime import date, datetime
from types import SimpleNamespace

import httpx
import pytest
from transit_fixture import FixtureStore, Walking, archive

from smart_recycling.routing_models import RoutingError, TripRequest
from smart_recycling.transit import Label, TransitPlanner, scan
from smart_recycling.transit_feed import SKOPJE, TransitFeed, TransitFeedStore, seconds

NOW = datetime(2026, 10, 17, 10, 0, tzinfo=SKOPJE).timestamp()


def candidate(identifier, longitude, kind="glass"):
    return SimpleNamespace(
        site=SimpleNamespace(
            id=identifier,
            longitude=longitude,
            latitude=42,
            assets=[SimpleNamespace(name=identifier)],
        ),
        kinds=frozenset({kind}),
    )


def request():
    return TripRequest(
        origin={"latitude": 42, "longitude": 21.4001},
        mode="transit",
        items=[{"material": "glass", "condition_confirmed": True}],
        share_coordinates=True,
        departure_at=datetime.fromtimestamp(NOW, SKOPJE),
    )


def test_direct_bus_has_real_walking_schedule_and_separate_geometry():
    walking = Walking()
    selected, network, extra = TransitPlanner(FixtureStore(), walking, lambda: NOW).plan(
        request(), [candidate("glass", 21.5001)], ("glass",)
    )
    assert selected == [0]
    assert [leg["mode"] for leg in extra["legs"]] == ["walking", "bus", "walking"]
    ride = extra["legs"][1]
    assert ride["line"] == "5" and ride["from_name"] == "Board here"
    assert ride["to_name"] == "Glass stop" and ride["stop_count"] == 2
    assert network.duration_s > 30 * 60
    assert ride["geometry"]["coordinates"] == [[21.4, 42], [21.45, 42], [21.5, 42]]
    assert walking.calls[0][0] == "matrix" and len(walking.calls) == 3
    assert extra["transit_feed_version"] == "synthetic-v1"


def test_transfer_wait_and_minimum_connection_time():
    feed = FixtureStore().feed
    labels = scan(feed, feed.runs(NOW), {"A": Label(NOW, ())}, NOW)
    assert [leg.trip.line for leg in labels["D"].path] == ["5", "22"]
    data = archive(
        changes={
            "stop_times.txt": (
                "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                "T1,10:10:00,10:10:00,A,1\n"
                "T1,10:23:00,10:23:00,B,2\n"
                "T2,10:24:00,10:24:00,B,1\n"
                "T2,10:35:00,10:35:00,D,2\n"
            )
        }
    )
    feed = TransitFeed(data)
    assert "D" not in scan(feed, feed.runs(NOW), {"A": Label(NOW, ())}, NOW)


def test_service_exceptions_override_weekday_and_remove_bus():
    feed = TransitFeed(
        archive(
            changes={
                "calendar_dates.txt": "service_id,date,exception_type\nS,20261017,2\nS,20261028,1\n"
            }
        )
    )
    assert feed.services(date(2026, 10, 17)) == set()
    assert feed.services(date(2026, 10, 28)) == {"S"}


def test_after_midnight_uses_previous_service_day():
    feed = TransitFeed(
        archive(
            changes={
                "stop_times.txt": (
                    "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                    "T1,25:10:00,25:10:00,A,1\n"
                    "T1,25:30:00,25:30:00,C,2\n"
                    "T2,25:24:00,25:24:00,B,1\n"
                    "T2,25:35:00,25:35:00,D,2\n"
                )
            }
        )
    )
    after_midnight = datetime(2026, 10, 18, 1, tzinfo=SKOPJE).timestamp()
    result = scan(feed, feed.runs(after_midnight), {"A": Label(after_midnight, ())}, after_midnight)
    assert result["C"].arrival == after_midnight + 1800
    assert seconds("25:30:00") == 91800


@pytest.mark.parametrize("value", ["48:00:00", "10:60:00", "-1:00:00", "bad"])
def test_rejects_invalid_times(value):
    with pytest.raises(ValueError):
        seconds(value)


def test_bus_shape_outside_area_is_omitted_without_losing_timetable():
    feed = TransitFeed(
        archive(
            changes={
                "shapes.txt": (
                    "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
                    "shape,42,21.4,1\n"
                    "shape,42,25,2\n"
                )
            }
        )
    )
    assert "shape" not in feed.shapes
    assert len(feed.trips) == 2


def test_missed_bus_does_not_become_invented_service():
    payload = request().model_copy(
        update={"departure_at": datetime.fromtimestamp(NOW + 1200, SKOPJE)}
    )
    with pytest.raises(RoutingError, match="No JSP journey"):
        TransitPlanner(FixtureStore(), Walking(), lambda: NOW).plan(
            payload, [candidate("glass", 21.5001)], ("glass",)
        )


def test_expired_date_and_past_departure_fail_explicitly():
    planner = TransitPlanner(FixtureStore(), Walking(), lambda: NOW)
    payload = request().model_copy(
        update={"departure_at": datetime.fromtimestamp(NOW - 3600, SKOPJE)}
    )
    with pytest.raises(RoutingError) as failure:
        planner.plan(payload, [candidate("glass", 21.5)], ("glass",))
    assert failure.value.code == "transit_departure"
    planner.clock = lambda: NOW + 10 * 86400
    payload = request().model_copy(update={"departure_at": None})
    with pytest.raises(RoutingError) as failure:
        planner.plan(payload, [candidate("glass", 21.5)], ("glass",))
    assert failure.value.code == "transit_expired"


def test_short_walk_is_not_mislabelled_as_bus_ride():
    _, _, extra = TransitPlanner(FixtureStore(), Walking(), lambda: NOW).plan(
        request(), [candidate("glass", 21.401)], ("glass",)
    )
    assert [leg["mode"] for leg in extra["legs"]] == ["walking"]


def test_all_items_covered_and_dropoff_time_included():
    selected, network, extra = TransitPlanner(FixtureStore(), Walking(), lambda: NOW).plan(
        request(),
        [candidate("glass", 21.5001), candidate("paper", 21.501, "paper")],
        ("glass", "paper"),
    )
    assert set(selected) == {0, 1}
    assert {leg["site_id"] for leg in extra["legs"]} == {"glass", "paper"}
    assert network.duration_s > 33 * 60


def test_changed_walking_connection_is_not_returned_as_catchable_bus():
    walk = Walking()
    walk.extra = 899
    with pytest.raises(RoutingError) as failure:
        TransitPlanner(FixtureStore(), walk, lambda: NOW).plan(
            request(), [candidate("glass", 21.5)], ("glass",)
        )
    assert failure.value.code == "transit_connection"


def test_store_caches_valid_feed_and_never_serves_expired_cache(tmp_path):
    calls = []

    def respond(req):
        calls.append(str(req.url))
        return httpx.Response(200, content=archive())

    store = TransitFeedStore(tmp_path / "feed.zip", httpx.MockTransport(respond))
    assert store.get() is store.get()
    assert len(calls) == 1
    assert (
        TransitFeedStore(store.path, httpx.MockTransport(lambda req: pytest.fail("network")))
        .get()
        .version
        == "synthetic-v1"
    )
    store._loaded = 0
    import os

    os.utime(store.path, (0, 0))
    store.transport = httpx.MockTransport(lambda req: httpx.Response(503))
    with pytest.raises(RoutingError) as failure:
        store.get()
    assert failure.value.code == "transit_unavailable"


def test_corrupt_feed_and_oversized_archive_fail_without_extracting(tmp_path):
    store = TransitFeedStore(
        tmp_path / "feed.zip",
        httpx.MockTransport(lambda req: httpx.Response(200, content=b"broken")),
    )
    with pytest.raises(RoutingError):
        store.get()
    assert not store.path.exists()
    with pytest.raises(ValueError):
        TransitFeed(b"x" * 10_000_001)


def test_dst_service_day_uses_noon_minus_twelve_hours():
    feed = TransitFeed(archive(day=date(2026, 10, 25)))
    start = datetime(2026, 10, 25, 10, tzinfo=SKOPJE).timestamp()
    labels = scan(feed, feed.runs(start), {"A": Label(start, ())}, start)
    assert datetime.fromtimestamp(labels["C"].arrival, SKOPJE).hour == 10
    assert labels["C"].arrival == start + 1800


@pytest.mark.parametrize(
    "changes",
    [
        {"routes.txt": "route_id,route_short_name,route_type\nR1,5,3\nR1,22,3\n"},
        {"calendar_dates.txt": "service_id,date,exception_type\nS,20261017,4\n"},
        {"calendar_dates.txt": "service_id,date,exception_type\nS,not-a-date,2\n"},
        {"frequencies.txt": "trip_id,start_time,end_time,headway_secs\nT1,10:00,11:00,600\n"},
        {"transfers.txt": "from_stop_id,to_stop_id,transfer_type\nA,B,3\n"},
    ],
)
def test_unsupported_or_invalid_feed_fails_closed(changes):
    with pytest.raises(ValueError):
        TransitFeed(archive(changes=changes))


def test_no_pickup_restriction_and_direction_are_respected():
    from dataclasses import replace

    feed = FixtureStore().feed
    trip = feed.trips[0]
    feed.trips[0] = replace(trip, calls=(replace(trip.calls[0], pickup=False), *trip.calls[1:]))
    assert not scan(feed, feed.runs(NOW), {"A": Label(NOW, ())}, NOW)
    assert "A" not in scan(feed, feed.runs(NOW), {"C": Label(NOW, ())}, NOW)


def test_disconnected_walk_never_becomes_straight_line_connection():
    class Disconnected(Walking):
        def matrix(self, mode, points):
            return [[None for _ in points] for _ in points]

    walking = Disconnected()
    with pytest.raises(RoutingError, match="No JSP journey"):
        TransitPlanner(FixtureStore(), walking, lambda: NOW).plan(
            request(), [candidate("glass", 21.5001)], ("glass",)
        )
    assert walking.calls == []
