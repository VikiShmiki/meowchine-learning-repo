"""Offline directed walking coverage with fractional segment connections."""

import heapq
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    """An eligible street segment in canonical node order, preserving direction."""

    u: int
    v: int
    way: int
    length_m: float
    forward: bool = True
    backward: bool = True


@dataclass(frozen=True)
class Connection:
    """A demand/site point attached to a split street node with access time."""

    node: int
    seconds: float


@dataclass
class WalkingNetwork:
    """Reverse adjacency supports travel FROM demand TO any accepting site."""

    reverse: dict[int, list[tuple[int, float]]]
    connections: dict[str, Connection | None]

    def covered(self, site_ids: list[str], seconds: float = 600) -> set[str]:
        """Return connected records within the inclusive budget; count IDs once."""
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Coverage time must be finite and nonnegative")
        distances: dict[int, float] = {}
        queue: list[tuple[float, int]] = []
        for site in site_ids:
            connection = self.connections[site]
            if (
                connection
                and connection.seconds <= seconds + 1e-9
                and connection.seconds < distances.get(connection.node, math.inf)
            ):
                distances[connection.node] = connection.seconds
                heapq.heappush(queue, (connection.seconds, connection.node))
        while queue:
            cost, node = heapq.heappop(queue)
            if cost > distances[node]:
                continue
            for previous, travel in self.reverse.get(node, []):
                candidate = cost + travel
                if candidate <= seconds + 1e-9 and candidate < distances.get(previous, math.inf):
                    distances[previous] = candidate
                    heapq.heappush(queue, (candidate, previous))
        return {
            key
            for key, connection in self.connections.items()
            if connection is not None
            and distances.get(connection.node, math.inf) + connection.seconds <= seconds + 1e-9
        }


def connect_network(
    segments: list[Segment], records: list[dict], speed_kmh: float = 4.8, limit_m: float = 100
) -> WalkingNetwork:
    """Split each segment at all demand/site fractions, including same-segment paths.

    Access links are terminal costs, never shortcuts between streets. Parallel ways
    retain their identities; only original shared node IDs connect different ways.
    """
    if not math.isfinite(speed_kmh) or speed_kmh <= 0 or not math.isfinite(limit_m) or limit_m < 0:
        raise ValueError("Invalid speed/access limit")
    speed = speed_kmh / 3.6
    by_key = {}
    fractions = {}
    for segment in segments:
        key = (segment.u, segment.v, segment.way)
        if (
            segment.u >= segment.v
            or key in by_key
            or not math.isfinite(segment.length_m)
            or segment.length_m <= 0
            or not (segment.forward or segment.backward)
        ):
            raise ValueError("Invalid or duplicate canonical segment")
        by_key[key] = segment
        fractions[key] = {0.0: segment.u, 1.0: segment.v}
    next_node = max((max(s.u, s.v) for s in segments), default=0) + 1
    connections = {}
    for row in records:
        if row["id"] in connections:
            raise ValueError("Duplicate connection ID")
        if row["snap_status"] == "too_far":
            connections[row["id"]] = None
            continue
        if row["snap_status"] != "candidate_unverified":
            raise ValueError("Unknown connection state")
        distance, fraction = row["snap_distance_m"], row["segment_fraction"]
        key = (*row["segment_nodes"], row["way_id"])
        if (
            key not in by_key
            or not math.isfinite(distance)
            or not 0 <= distance <= limit_m
            or not math.isfinite(fraction)
            or not 0 <= fraction <= 1
        ):
            raise ValueError("Connection does not match eligible walking segment")
        if fraction not in fractions[key]:
            fractions[key][fraction] = next_node
            next_node += 1
        connections[row["id"]] = Connection(fractions[key][fraction], distance / speed)
    reverse: dict[int, list[tuple[int, float]]] = {}
    for key, segment in by_key.items():
        points = sorted(fractions[key].items())
        for (a, u), (b, v) in zip(points, points[1:], strict=False):
            cost = (b - a) * segment.length_m / speed
            if segment.forward:
                reverse.setdefault(v, []).append((u, cost))
            if segment.backward:
                reverse.setdefault(u, []).append((v, cost))
    return WalkingNetwork(reverse, connections)
