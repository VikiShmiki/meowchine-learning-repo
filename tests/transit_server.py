"""Isolated browser server with a synthetic JSP timetable and fake walking network."""

from datetime import datetime

from system_server import app, reset_routing_budget
from transit_fixture import FixtureStore, Walking, archive

from smart_recycling import api
from smart_recycling.routing_models import RoutingError
from smart_recycling.transit import TransitPlanner
from smart_recycling.transit_feed import SKOPJE

NOW = datetime(2026, 10, 17, 10, 0, tzinfo=SKOPJE).timestamp()
destination = next(s for s in api.route_service.snapshot.sites if s.id == "ewaste-karpos-yard")
store = FixtureStore(archive())
# Move the synthetic stops/shapes together onto a real, compatible collection site.
for stop in store.feed.stops.values():
    stop.point[0] += destination.longitude - 21.5001
    stop.point[1] = destination.latitude
for points in store.feed.shapes.values():
    for point in points:
        point[0] += destination.longitude - 21.5001
        point[1] = destination.latitude
unavailable = False


class BrowserStore:
    def get(self):
        if unavailable:
            raise RoutingError(
                "transit_unavailable", "JSP timetable is unavailable. Retry shortly.", 503
            )
        return store.get()


api.route_service.transit = TransitPlanner(BrowserStore(), Walking(), lambda: NOW)


@app.post("/__test/transit")
def configure(fail: bool = False):
    global unavailable
    unavailable = fail
    reset_routing_budget()
    return {
        "latitude": destination.latitude,
        "longitude": destination.longitude - 0.1,
        "departure": "2026-10-17T10:00:00+02:00",
    }
