"""Opt-in JSP/ORS smoke from public Transport Center coordinates, never personal data."""

import argparse

from smart_recycling.api import route_service
from smart_recycling.routing_models import RoutingError, TripRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    request = TripRequest(
        origin={"latitude": 41.9906, "longitude": 21.4445},
        mode="transit",
        items=[{"material": "electronics", "condition_confirmed": True}],
        share_coordinates=True,
    )
    try:
        result = route_service.plan(request)
    except RoutingError as error:
        raise SystemExit(f"{error.code}: {error.message}") from None
    buses = [leg.line for leg in result.legs if leg.mode == "bus"]
    if not buses or not result.stops or not result.transit_feed_version:
        raise SystemExit("No complete bus itinerary returned; inspect current service.")
    print(f"JSP buses: {', '.join(buses)}; scheduled duration {result.duration_s / 60:.1f} min")
    print(f"Feed {result.transit_feed_version}; service through {result.transit_service_end}")
    print("Scheduled integration verified; live delays and field access remain unverified.")


if __name__ == "__main__":
    main()
