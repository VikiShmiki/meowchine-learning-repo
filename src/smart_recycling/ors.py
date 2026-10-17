"""Bounded openrouteservice adapter; no credentials or raw provider errors leave this module."""

import json
import math
import time
from dataclasses import dataclass

import httpx

from smart_recycling.geo import haversine_m
from smart_recycling.routing_models import Mode, RoutingError

PROFILES = {"walking": "foot-walking", "driving": "driving-car"}
MAX_SNAP_M = 100


def number(value: object) -> bool:
    """Accept only finite nonnegative provider numbers, not JSON booleans."""
    return type(value) in {int, float} and math.isfinite(value) and value >= 0


def gap(point: list[float], snapped: object) -> float:
    """Validate longitude-first coordinates and calculate the network-access gap."""
    if (
        not isinstance(snapped, list)
        or len(snapped) != 2
        or any(type(value) not in {int, float} or not math.isfinite(value) for value in snapped)
        or not -180 <= snapped[0] <= 180
        or not -90 <= snapped[1] <= 90
    ):
        raise ValueError("Invalid snapped point")
    return haversine_m((point[1], point[0]), (snapped[1], snapped[0]))


@dataclass(frozen=True)
class NetworkRoute:
    """Validated geometry, totals and gaps for the requested waypoint order."""

    geometry: list[list[float]]
    distance_m: float
    duration_s: float
    gaps_m: list[float]
    warnings: tuple[str, ...] = ()


class ORSProvider:
    """Use only fixed HTTPS ORS paths and server-held authentication."""

    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None) -> None:
        self._key = api_key
        self._transport = transport

    def _post(self, path: str, payload: dict) -> dict:
        if not self._key:
            raise RoutingError(
                "routing_not_configured",
                "Live routing is not configured yet. Try again later.",
                503,
            )
        try:
            started = time.monotonic()
            with (
                httpx.Client(
                    timeout=10, transport=self._transport, follow_redirects=False
                ) as client,
                client.stream(
                    "POST",
                    "https://api.openrouteservice.org/v2/" + path,
                    headers={
                        "Authorization": self._key,
                        "Accept": "application/geo+json"
                        if path.endswith("/geojson")
                        else "application/json",
                    },
                    json=payload,
                ) as response,
            ):
                status = response.status_code
                if status in {401, 403}:
                    raise RoutingError(
                        "provider_auth", "Routing provider credentials need attention.", 503
                    )
                if status == 429:
                    raise RoutingError(
                        "provider_limit", "Routing quota reached. Try again later.", 429
                    )
                if status >= 500:
                    raise RoutingError(
                        "provider_unavailable",
                        "Routing provider is unavailable. Try again later.",
                        503,
                    )
                if status != 200:
                    raise RoutingError(
                        "provider_no_route",
                        "The provider could not route these points. Try another origin or mode.",
                    )
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > 2_000_000 or time.monotonic() - started > 12:
                        raise RoutingError(
                            "provider_limit",
                            "Routing response exceeded the request budget.",
                            503,
                        )
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError("Not an object")
            return result
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise RoutingError(
                "provider_timeout", "Routing timed out. Please retry.", 503
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise RoutingError(
                "provider_invalid", "Routing provider returned unusable data.", 502
            ) from error

    def matrix(self, mode: Mode, points: list[list[float]]) -> list[list[float | None]]:
        """Keep directionality/null paths and reject excessively snapped candidates."""
        data = self._post(
            f"matrix/{PROFILES[mode]}", {"locations": points, "metrics": ["duration"]}
        )
        try:
            count = len(points)
            durations = data["durations"]
            if len(durations) != count or any(len(row) != count for row in durations):
                raise ValueError("Matrix shape")
            if any(value is not None and not number(value) for row in durations for value in row):
                raise ValueError("Invalid duration")
            usable = [True] * count
            for key in ("sources", "destinations"):
                if len(data[key]) != count:
                    raise ValueError("Endpoint count")
                for index, endpoint in enumerate(data[key]):
                    usable[index] &= (
                        endpoint is not None
                        and gap(points[index], endpoint["location"]) <= MAX_SNAP_M
                    )
            if not usable[0]:
                raise RoutingError(
                    "origin_access",
                    "Starting point is more than 100 m from the routable network. "
                    "Select a street-accessible point.",
                )
            return [
                [value if usable[i] and usable[j] else None for j, value in enumerate(row)]
                for i, row in enumerate(durations)
            ]
        except (KeyError, TypeError, ValueError, IndexError) as error:
            raise RoutingError(
                "provider_invalid", "Routing matrix is incomplete or invalid.", 502
            ) from error

    def directions(self, mode: Mode, points: list[list[float]]) -> NetworkRoute:
        """Request every stop in order, with no return leg or skipped segments."""
        data = self._post(
            f"directions/{PROFILES[mode]}/geojson",
            {
                "coordinates": points,
                "radiuses": [MAX_SNAP_M] * len(points),
                "instructions": True,
                "continue_straight": mode == "driving",
            },
        )
        try:
            features = data["features"]
            if len(features) != 1:
                raise ValueError("Expected one itinerary")
            feature = features[0]
            properties = feature["properties"]
            coords = feature["geometry"]["coordinates"]
            indices = properties["way_points"]
            summary = properties["summary"]
            if (
                feature["geometry"]["type"] != "LineString"
                or len(coords) < 2
                or len(indices) != len(points)
                or indices != sorted(indices)
                or indices[0] != 0
                or indices[-1] != len(coords) - 1
                or any(
                    type(index) is not int or index < 0 or index >= len(coords) for index in indices
                )
                or len(properties["segments"]) != len(points) - 1
                or any(
                    not isinstance(warning, dict) or warning.get("code") != 4
                    for warning in properties.get("warnings", [])
                )
                or not number(summary["distance"])
                or not number(summary["duration"])
            ):
                raise ValueError("Incomplete itinerary")
            for coordinate in coords:
                gap(points[0], coordinate)
            gaps = [gap(point, coords[index]) for point, index in zip(points, indices, strict=True)]
            if any(value > MAX_SNAP_M + 0.5 for value in gaps):
                raise RoutingError(
                    "site_access",
                    "A route endpoint is too far from the recorded site. "
                    "Try another mode or origin.",
                )
            warnings = (
                (
                    "Provider reports unavailable additional road-access metadata. "
                    "Follow local access signs and restrictions.",
                )
                if properties.get("warnings")
                else ()
            )
            return NetworkRoute(coords, summary["distance"], summary["duration"], gaps, warnings)
        except (KeyError, TypeError, ValueError, IndexError) as error:
            raise RoutingError(
                "provider_invalid", "The provider returned an incomplete itinerary.", 502
            ) from error
