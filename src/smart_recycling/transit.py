"""Schedule-aware bus journeys with provider-verified walking connections."""

import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from smart_recycling.geo import haversine_m
from smart_recycling.ors import NetworkRoute
from smart_recycling.routing_models import RoutingError
from smart_recycling.transit_feed import JSP_FEED_URL, SKOPJE, TransitFeedStore

MAX_WALK_SECONDS = 900
BOARDING_BUFFER = 120
DISPOSAL_SECONDS = 180


def distance(a, b):
    return haversine_m((a[1], a[0]), (b[1], b[0]))


def stamp(value):
    return datetime.fromtimestamp(value, UTC).isoformat()


@dataclass(frozen=True)
class Walk:
    start: list[float]
    end: list[float]
    seconds: float
    start_name: str
    end_name: str


@dataclass(frozen=True)
class Ride:
    base: float
    trip: object
    board: int
    alight: int


@dataclass(frozen=True)
class Label:
    arrival: float
    path: tuple


def scan(feed, runs, seeds, departure):
    """Two boarding rounds; transfers use the same recorded stop plus two minutes."""
    previous, best = seeds, {}
    for _ in range(2):
        current = {}
        for base, trip in runs:
            boarded = None
            for index, call in enumerate(trip.calls):
                arrival, leave = base + call.arrival, base + call.departure
                if arrival > departure + 14400:
                    break
                if boarded is not None and call.dropoff:
                    board, label = boarded
                    if arrival < current.get(call.stop, Label(math.inf, ())).arrival:
                        current[call.stop] = Label(
                            arrival, (*label.path, Ride(base, trip, board, index))
                        )
                if boarded is None and call.pickup:
                    label = previous.get(call.stop)
                    if label and label.arrival + BOARDING_BUFFER <= leave:
                        boarded = index, label
        for key, label in current.items():
            if label.arrival < best.get(key, Label(math.inf, ())).arrival:
                best[key] = label
        previous = current
    return best


def ride_geometry(feed, ride):
    """Cut the published bus shape in stop order; omit uncertain geometry."""
    shape = feed.shapes.get(ride.trip.shape, [])
    if len(shape) < 2:
        return None
    positions, previous = [], 0
    for call in ride.trip.calls[: ride.alight + 1]:
        point = feed.stops[call.stop].point
        closest = min(range(previous, len(shape)), key=lambda i: distance(point, shape[i]))
        if distance(point, shape[closest]) > 200:
            return None
        positions.append(closest)
        previous = closest
    points = shape[positions[ride.board] : positions[ride.alight] + 1]
    return {"type": "LineString", "coordinates": points} if len(points) >= 2 else None


class TransitPlanner:
    def __init__(self, store: TransitFeedStore, provider, clock=time.time):
        self.store, self.provider, self.clock = store, provider, clock

    def plan(self, request, candidates, kinds):
        started = time.monotonic()
        now = self.clock()
        departure = request.departure_at.timestamp() if request.departure_at else now + 60
        if not now - 60 <= departure <= now + 7 * 86400:
            raise RoutingError(
                "transit_departure", "Choose a departure within the next seven days."
            )
        feed = self.store.get()
        local_day = datetime.fromtimestamp(departure, SKOPJE).date()
        if not feed.start <= local_day <= feed.end:
            raise RoutingError(
                "transit_expired",
                "JSP has no valid timetable for this date. Choose another departure.",
            )
        runs = feed.runs(departure)
        if not runs:
            raise RoutingError(
                "transit_no_service",
                "No scheduled JSP service at this departure. Choose another time.",
            )
        points = [
            request.origin.lonlat(),
            *[[c.site.longitude, c.site.latitude] for c in candidates],
        ]
        names = ["Starting point", *[c.site.assets[0].name for c in candidates]]
        nearby, stop_indices = [], {}
        # <=19 endpoints + 39 stops =58 locations /3364 directed matrix cells.
        used_stops = {call.stop for _, trip in runs for call in trip.calls}
        for index, point in enumerate(points.copy()):
            stops = sorted(
                (feed.stops[key] for key in used_stops),
                key=lambda stop: (distance(point, stop.point), stop.id),
            )
            eligible = [s for s in stops if distance(point, s.point) <= 1200][
                : 3 if index == 0 else 2
            ]
            nearby.append([s.id for s in eligible])
            for stop in eligible:
                if stop.id not in stop_indices:
                    stop_indices[stop.id] = len(points)
                    points.append(stop.point)
        matrix = self.provider.matrix("walking", points)
        selected, journeys, remaining, current, at = [], [], set(kinds), 0, departure
        while remaining:
            if time.monotonic() - started > 50:
                raise RoutingError(
                    "provider_timeout", "Transit planning timed out. Please retry.", 503
                )
            seeds = {}
            for stop_id in nearby[current]:
                cost = matrix[current][stop_indices[stop_id]]
                if cost is not None and cost <= MAX_WALK_SECONDS:
                    stop = feed.stops[stop_id]
                    seeds[stop_id] = Label(
                        at + cost,
                        (Walk(points[current], stop.point, cost, names[current], stop.name),),
                    )
            labels = scan(feed, runs, seeds, at)
            options = []
            for index, candidate in enumerate(candidates):
                if not remaining & candidate.kinds:
                    continue
                target = index + 1
                direct = matrix[current][target]
                if direct is not None and direct <= MAX_WALK_SECONDS:
                    options.append(
                        (
                            at + direct,
                            index,
                            (
                                Walk(
                                    points[current],
                                    points[target],
                                    direct,
                                    names[current],
                                    names[target],
                                ),
                            ),
                        )
                    )
                for stop_id in nearby[target]:
                    label = labels.get(stop_id)
                    cost = matrix[stop_indices[stop_id]][target]
                    if label and cost is not None and cost <= MAX_WALK_SECONDS:
                        stop = feed.stops[stop_id]
                        options.append(
                            (
                                label.arrival + cost,
                                index,
                                (
                                    *label.path,
                                    Walk(
                                        stop.point, points[target], cost, stop.name, names[target]
                                    ),
                                ),
                            )
                        )
            if not options:
                raise RoutingError(
                    "transit_no_route",
                    "No JSP journey covers all items within the walking and "
                    "transfer limits. Try another time or starting point.",
                )
            arrival, index, path = min(options, key=lambda option: (option[0], option[1]))
            if arrival > departure + 14400:
                raise RoutingError(
                    "transit_no_route",
                    "This trip exceeds the four-hour transit planning window. Split the basket.",
                )
            selected.append(index)
            journeys.append((candidates[index].site.id, at, path))
            remaining.difference_update(candidates[index].kinds)
            current, at = index + 1, arrival + DISPOSAL_SECONDS
        legs, gaps, total_distance, warnings = [], [0.0], 0.0, []
        actual = max(departure, self.clock())
        for journey_index, (site_id, planned_start, path) in enumerate(journeys):
            actual = max(actual, planned_start)
            last_gap = 0.0
            for step in path:
                if time.monotonic() - started > 50:
                    raise RoutingError(
                        "provider_timeout", "Transit planning timed out. Please retry.", 503
                    )
                if isinstance(step, Walk):
                    if step.start == step.end:
                        network = NetworkRoute([], 0, 0, [0, 0])
                    else:
                        network = self.provider.directions("walking", [step.start, step.end])
                    if network.duration_s > MAX_WALK_SECONDS:
                        raise RoutingError(
                            "transit_connection",
                            "A walking connection changed. Replan before travelling.",
                        )
                    if not legs:
                        gaps[0] = network.gaps_m[0]
                    last_gap = network.gaps_m[-1]
                    end = actual + network.duration_s
                    legs.append(
                        dict(
                            mode="walking",
                            from_name=step.start_name,
                            to_name=step.end_name,
                            departure_at=stamp(actual),
                            arrival_at=stamp(end),
                            duration_s=network.duration_s,
                            distance_m=network.distance_m,
                            geometry={"type": "LineString", "coordinates": network.geometry}
                            if network.geometry
                            else None,
                            from_point=step.start,
                            to_point=step.end,
                            site_id=site_id,
                        )
                    )
                    total_distance += network.distance_m
                    warnings.extend(network.warnings)
                    actual = end
                else:
                    first, last = step.trip.calls[step.board], step.trip.calls[step.alight]
                    leaves, arrives = step.base + first.departure, step.base + last.arrival
                    if actual + 60 > leaves:
                        raise RoutingError(
                            "transit_connection",
                            "A walking connection changed. Replan before travelling.",
                        )
                    geometry = ride_geometry(feed, step)
                    if geometry is None:
                        warnings.append(
                            "A bus shape is unavailable; that ride is listed without a map line."
                        )
                    length = (
                        sum(
                            distance(a, b)
                            for a, b in zip(
                                geometry["coordinates"], geometry["coordinates"][1:], strict=False
                            )
                        )
                        if geometry
                        else 0
                    )
                    legs.append(
                        dict(
                            mode="bus",
                            from_name=feed.stops[first.stop].name,
                            to_name=feed.stops[last.stop].name,
                            departure_at=stamp(leaves),
                            arrival_at=stamp(arrives),
                            duration_s=arrives - leaves,
                            distance_m=length,
                            geometry=geometry,
                            line=step.trip.line,
                            headsign=step.trip.headsign,
                            stop_count=step.alight - step.board,
                            from_point=feed.stops[first.stop].point,
                            to_point=feed.stops[last.stop].point,
                            site_id=site_id,
                        )
                    )
                    total_distance += length
                    actual = arrives
            gaps.append(last_gap)
            if journey_index < len(journeys) - 1:
                actual += DISPOSAL_SECONDS
        warnings.extend(
            [
                "Scheduled JSP times, not live arrivals. Check JSP notices "
                "before leaving; delays and cancellations may change your "
                "journey.",
                "Up to 15 minutes walking per connection and one same-stop bus "
                "transfer per collection leg. Other transfers are not searched.",
                "Earliest next drop-off within a nearby shortlist; not a "
                "city-wide optimum. Three minutes per intermediate drop-off are "
                "included.",
                "Walking access gaps, barriers, fares and accessibility are "
                "unverified. Follow signs and JSP ticket rules.",
            ]
        )
        if not any(leg["mode"] == "bus" for leg in legs):
            warnings.append(
                "A short walking journey is available; no bus is needed for this itinerary."
            )
        return (
            selected,
            NetworkRoute(
                [], total_distance, actual - departure, gaps, tuple(dict.fromkeys(warnings))
            ),
            {
                "provider": "jsp_gtfs_openrouteservice",
                "profile": "jsp-scheduled-bus+foot-walking",
                "legs": legs,
                "departure_at": stamp(departure),
                "arrival_at": stamp(actual),
                "transit_feed_version": feed.version,
                "transit_fetched_at": stamp(feed.fetched_at),
                "transit_service_end": feed.end.isoformat(),
                "transit_source": JSP_FEED_URL,
                "optimizer": (
                    "Earliest next drop-off using scheduled buses within a nearby shortlist"
                ),
                "attribution": (
                    "JSP Skopje / Modeshift timetable | © openrouteservice by HeiGIT | "
                    "© OpenStreetMap contributors"
                ),
            },
        )
