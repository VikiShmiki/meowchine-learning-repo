"""Drive to mapped parking, walk to disposal, return to the car before the next drive."""

import time
from dataclasses import dataclass

from smart_recycling.geo import haversine_m
from smart_recycling.ors import NetworkRoute
from smart_recycling.route_planner import solve
from smart_recycling.routing_models import RoutingError

MAX_WALK_SECONDS = 600
SEARCH_METRES = 800


@dataclass(frozen=True)
class Option:
    site: int
    park: int
    mask: int
    walk_to: float
    walk_back: float | None


def walk_payload(route):
    return dict(
        duration_s=route.duration_s,
        distance_m=route.distance_m,
        geometry={"type": "LineString", "coordinates": route.geometry} if route.geometry else None,
        start_gap_m=route.gaps_m[0],
        end_gap_m=route.gaps_m[-1],
    )


class ParkingPlanner:
    def __init__(self, catalog, provider):
        self.catalog, self.provider = catalog, provider

    def plan(self, request, candidates, kinds):
        started = time.monotonic()

        def budget():
            if time.monotonic() - started > 50:
                raise RoutingError(
                    "provider_timeout", "Parking planning timed out. Please retry.", 503
                )

        snapshot = self.catalog.get()
        parks, park_indices, pairs = [], {}, []
        for site_index, candidate in enumerate(candidates):
            site = candidate.site
            nearby = sorted(
                snapshot.places,
                key=lambda park: (
                    haversine_m((site.latitude, site.longitude), (park.latitude, park.longitude)),
                    park.id,
                ),
            )
            for park in nearby[:2]:
                if (
                    haversine_m((site.latitude, site.longitude), (park.latitude, park.longitude))
                    > SEARCH_METRES
                ):
                    continue
                if park.id not in park_indices:
                    park_indices[park.id] = len(parks)
                    parks.append(park)
                pairs.append((site_index, park_indices[park.id]))
        if not pairs:
            raise RoutingError(
                "parking_no_route",
                (
                    "No mapped public parking near the compatible sites. Try another starting "
                    "point or travel option."
                ),
            )
        budget()
        drive_points = [request.origin.lonlat(), *[p.lonlat() for p in parks]]
        driving = self.provider.matrix("driving", drive_points)
        budget()
        walk_points = [p.lonlat() for p in parks] + [
            [c.site.longitude, c.site.latitude] for c in candidates
        ]
        walking = self.provider.matrix("walking", walk_points, require_origin=False)
        options = []
        for site_index, park_index in pairs:
            cost = walking[park_index][len(parks) + site_index]
            back = walking[len(parks) + site_index][park_index]
            if cost is None or cost > MAX_WALK_SECONDS:
                continue
            options.append(
                Option(
                    site_index,
                    park_index,
                    sum(
                        1 << i
                        for i, kind in enumerate(kinds)
                        if kind in candidates[site_index].kinds
                    ),
                    cost,
                    back if back is not None and back <= MAX_WALK_SECONDS else None,
                )
            )
        # The state tracks the parked car. Each non-final transition includes returning to it.
        costs = [[None] * (len(options) + 1) for _ in range(len(options) + 1)]
        for j, target in enumerate(options, 1):
            edge = driving[0][target.park + 1]
            if edge is not None:
                costs[0][j] = edge + target.walk_to
            for i, previous in enumerate(options, 1):
                edge = driving[previous.park + 1][target.park + 1]
                if edge is not None and previous.walk_back is not None:
                    costs[i][j] = previous.walk_back + edge + target.walk_to
        try:
            selected = [
                options[i] for i in solve([o.mask for o in options], costs, (1 << len(kinds)) - 1)
            ]
        except RoutingError as error:
            raise RoutingError(
                "parking_no_route",
                (
                    "No connected parking journey covers all items within a ten-minute walk per "
                    "connection. Try another starting point or travel option."
                ),
            ) from error
        budget()
        # A single directed driving itinerary preserves the provider's turn/approach constraints.
        car_points = [request.origin.lonlat()]
        car_index = []
        for option in selected:
            point = parks[option.park].lonlat()
            if point != car_points[-1]:
                car_points.append(point)
            car_index.append(len(car_points) - 1)
        car = (
            self.provider.directions("driving", car_points)
            if len(car_points) > 1
            else NetworkRoute([], 0, 0, [0])
        )
        visits, gaps, warnings = [], [car.gaps_m[0]], list(car.warnings)
        walk_duration = walk_distance = 0
        for position, option in enumerate(selected):
            park, site = parks[option.park], candidates[option.site].site
            point = [site.longitude, site.latitude]
            routes = []
            for start, end in [(park.lonlat(), point)] + (
                [(point, park.lonlat())] if position < len(selected) - 1 else []
            ):
                budget()
                route = (
                    self.provider.directions("walking", [start, end])
                    if start != end
                    else NetworkRoute([], 0, 0, [0, 0])
                )
                if route.duration_s > MAX_WALK_SECONDS:
                    raise RoutingError(
                        "parking_connection",
                        (
                            "A parking walk exceeds ten minutes. "
                            "Replan or choose another travel option."
                        ),
                    )
                walk_duration += route.duration_s
                walk_distance += route.distance_m
                warnings.extend(route.warnings)
                routes.append(route)
            gaps.append(routes[0].gaps_m[-1])
            visits.append(
                dict(
                    site_id=site.id,
                    parking_id=park.id,
                    name=park.name,
                    latitude=park.latitude,
                    longitude=park.longitude,
                    access=park.access,
                    fee=park.fee,
                    opening_hours=park.opening_hours,
                    point_kind=park.point_kind,
                    source_url=park.source_url,
                    drive_access_gap_m=car.gaps_m[car_index[position]],
                    walk_to=walk_payload(routes[0]),
                    walk_back=walk_payload(routes[1]) if len(routes) > 1 else None,
                )
            )
        warnings.extend(
            [
                (
                    "Mapped public parking, not a reserved or available space. Check signs, "
                    "opening hours, charges and entry restrictions before parking."
                ),
                (
                    "Parking points and driveway crossings are map-derived, not verified "
                    "entrances. Network access gaps remain unverified."
                ),
                (
                    "Up to two parking candidates within 800 m of each shortlisted site; walking "
                    "is limited to ten minutes per connection. This is not a city-wide optimum."
                ),
                (
                    "Time includes driving, walking to each drop-off and returning to the car "
                    "between drop-offs. It excludes searching for a space, payment and disposal "
                    "time."
                ),
                (
                    "The trip ends at the last drop-off. Your car remains at the final parking "
                    "location; the final walk back is not included."
                ),
            ]
        )
        return (
            [o.site for o in selected],
            NetworkRoute(
                car.geometry,
                car.distance_m + walk_distance,
                car.duration_s + walk_duration,
                gaps,
                tuple(dict.fromkeys(warnings)),
            ),
            dict(
                profile="driving-car+foot-walking",
                parking=visits,
                parking_dataset_version=snapshot.dataset_version,
                parking_source_as_of=snapshot.source_timestamp,
                driving_duration_s=car.duration_s,
                walking_duration_s=walk_duration,
                optimizer="Minimum driving plus walking time within site and parking shortlists",
                attribution=(
                    "© openrouteservice by HeiGIT | © OpenStreetMap contributors; parking "
                    "extract by Geofabrik"
                ),
            ),
        )
