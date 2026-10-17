"""Opt-in ORS parking smoke from public Transport Center coordinates."""

import argparse

from smart_recycling.api import route_service
from smart_recycling.routing_models import RoutingError, TripRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    request = TripRequest(
        origin={"latitude": 41.9906, "longitude": 21.4445},
        mode="driving",
        include_parking=True,
        items=[
            {"material": "glass", "condition_confirmed": True},
            {"material": "electronics", "condition_confirmed": True},
        ],
        share_coordinates=True,
    )
    try:
        result = route_service.plan(request)
    except RoutingError as error:
        raise SystemExit(f"{error.code}: {error.message}") from None
    if (
        not result.parking
        or len(result.parking) != len(result.stops)
        or not result.parking_dataset_version
        or any(visit.walk_back is None for visit in result.parking[:-1])
        or result.parking[-1].walk_back is not None
    ):
        raise SystemExit("No complete parking itinerary returned.")
    print(f"Parking journey: {len(result.stops)} drop-offs; {result.duration_s / 60:.1f} min")
    print(f"Snapshot: {result.parking_dataset_version}")
    print(f"Parking IDs: {', '.join(visit.parking_id for visit in result.parking)}")
    print("Provider integration verified; spaces, prices and field access remain unverified.")


if __name__ == "__main__":
    main()
