"""Opt-in live routing smoke using a fixed public Skopje point, never a user's location."""

import argparse
import json
from pathlib import Path

from smart_recycling.api import route_service
from smart_recycling.routing_models import RoutingError, TripRequest


def main() -> None:
    """Exercise both provider profiles and write only a credential-free report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--out", type=Path, default=Path(".git/t07-live.json"))
    args = parser.parse_args()
    reports = {}
    for mode in ("walking", "driving"):
        request = TripRequest(
            origin={"latitude": 41.9965, "longitude": 21.4314},
            mode=mode,
            items=[
                {
                    "text": "empty glass bottle",
                    "manual_kind": "empty_glass_packaging",
                    "condition_confirmed": True,
                },
                {"text": "clean paper", "manual_kind": "clean_paper", "condition_confirmed": True},
                {
                    "text": "empty plastic bottle",
                    "manual_kind": "empty_plastic_bottle",
                    "condition_confirmed": True,
                },
            ],
            share_coordinates=True,
        )
        try:
            report = route_service.plan(request).model_dump(mode="json")
        except RoutingError as error:
            raise SystemExit(f"{mode}: {error.code}: {error.message}") from None
        reports[mode] = report
        print(
            f"{mode}: {report['distance_m']} m, {report['duration_s']} s, "
            f"{len(report['stops'])} stops; {report['candidate_count']} candidates"
        )
    # Interior points of OSM way 360141020 (Maksim Gorki), tagged oneway=yes
    # in the pinned 2026-09-18 network. Car reverse travel should require a detour;
    # ordinary road one-way restrictions do not imply pedestrian one-way travel.
    points = [[21.4299531, 41.9960561], [21.4302707, 41.9967202]]
    probe = {"osm_way": 360141020, "points": points, "distances_m": {}}
    for mode in ("walking", "driving"):
        forward = route_service.provider.directions(mode, points).distance_m
        backward = route_service.provider.directions(mode, list(reversed(points))).distance_m
        probe["distances_m"][mode] = {"forward": forward, "reverse": backward}
        print(f"One-way probe {mode}: forward {forward} m; reverse {backward} m")
    measured = probe["distances_m"]
    if measured["driving"]["reverse"] <= measured["driving"]["forward"] * 2:
        raise SystemExit("One-way driving probe failed; investigate provider network/access.")
    if measured["walking"]["reverse"] > measured["walking"]["forward"] * 1.5:
        raise SystemExit(
            "Walking probe needs investigation; do not infer car restrictions for foot."
        )
    reports["oneway_probe"] = probe
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
