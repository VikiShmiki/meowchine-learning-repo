"""Test-only app with real catalog/policy/community and deterministic road journeys."""

from system_server import app, reset_routing_budget
from test_parking import NOW, Roads

from smart_recycling import api
from smart_recycling.routing_models import RoutingError

api.parking_catalog.clock = lambda: NOW
api.route_service.parking.provider = Roads()
original_get = api.parking_catalog.get


@app.post("/__test/parking")
def configure(fail: bool = False):
    reset_routing_budget()

    def unavailable():
        raise RoutingError(
            "parking_unavailable",
            "Parking data is unavailable or needs refreshing. Try another travel option.",
            503,
        )

    api.parking_catalog.get = unavailable if fail else original_get
    return {"fixture": True}
