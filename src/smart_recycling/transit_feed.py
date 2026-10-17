"""Bounded JSP GTFS ingestion. Timetables are runtime data, never bundled fixtures."""

import csv
import hashlib
import io
import math
import threading
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as daytime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from smart_recycling.routing_models import RoutingError

JSP_FEED_URL = (
    "https://www.modeshift.app/api/v1/9814b106-2afe-47c8-919b-bdec6a5e521e/transport/gtfs/gtfs.zip"
)
SKOPJE = ZoneInfo("Europe/Skopje")
MAX_ZIP = 10_000_000
MAX_EXPANDED = 80_000_000
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def gtfs_date(value):
    return datetime.strptime(value, "%Y%m%d").date()


def seconds(value):
    h, m, s = map(int, value.split(":"))
    if not (0 <= h < 48 and 0 <= m < 60 and 0 <= s < 60):
        raise ValueError("Invalid GTFS time")
    return h * 3600 + m * 60 + s


@dataclass(frozen=True)
class BusStop:
    id: str
    name: str
    point: list[float]


@dataclass(frozen=True)
class Call:
    stop: str
    arrival: int
    departure: int
    pickup: bool
    dropoff: bool


@dataclass(frozen=True)
class BusTrip:
    id: str
    service: str
    line: str
    headsign: str
    shape: str
    calls: tuple[Call, ...]


class TransitFeed:
    """Validated in-memory timetable with actual calendars and exceptions."""

    def __init__(self, data: bytes):
        if len(data) > MAX_ZIP:
            raise ValueError("GTFS archive too large")
        self.sha256 = hashlib.sha256(data).hexdigest()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 40 or sum(x.file_size for x in entries) > MAX_EXPANDED:
                raise ValueError("GTFS expansion limit")
            if len({x.filename for x in entries}) != len(entries):
                raise ValueError("Duplicate GTFS member")

            def rows(name, required=True):
                if name not in archive.namelist() and not required:
                    return []
                with archive.open(name) as stream:
                    return list(csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig")))

            agency = rows("agency.txt")
            if rows("frequencies.txt", False) or rows("transfers.txt", False):
                raise ValueError("Unsupported frequency or transfer rules in JSP feed")
            if len(agency) != 1 or agency[0]["agency_timezone"] != "Europe/Skopje":
                raise ValueError("Expected JSP agency timezone")
            self.stops = {}
            for row in rows("stops.txt"):
                if row.get("location_type", "0") not in {"", "0"}:
                    continue
                point = [float(row["stop_lon"]), float(row["stop_lat"])]
                if not all(math.isfinite(x) for x in point) or not (
                    20 <= point[0] <= 23 and 40 <= point[1] <= 43
                ):
                    raise ValueError("Invalid JSP stop")
                if row["stop_id"] in self.stops or not row["stop_name"].strip():
                    raise ValueError("Duplicate or unnamed stop")
                self.stops[row["stop_id"]] = BusStop(row["stop_id"], row["stop_name"], point)

            def unique(name, key):
                records = rows(name)
                if len({r[key] for r in records}) != len(records):
                    raise ValueError("Duplicate GTFS identifier")
                return records

            all_routes = unique("routes.txt", "route_id")
            routes = {r["route_id"]: r for r in all_routes if r["route_type"] == "3"}
            trips = unique("trips.txt", "trip_id")
            route_ids = {r["route_id"] for r in all_routes}
            if any(r["route_id"] not in route_ids for r in trips):
                raise ValueError("Unknown route")
            trip_rows = {r["trip_id"]: r for r in trips if r["route_id"] in routes}
            calls = {key: [] for key in trip_rows}
            for row in rows("stop_times.txt"):
                if row["trip_id"] not in calls:
                    continue
                if row["stop_id"] not in self.stops:
                    raise ValueError("Unknown stop")
                calls[row["trip_id"]].append(
                    (
                        int(row["stop_sequence"]),
                        Call(
                            row["stop_id"],
                            seconds(row["arrival_time"]),
                            seconds(row["departure_time"]),
                            row.get("pickup_type", "0") in {"", "0"},
                            row.get("drop_off_type", "0") in {"", "0"},
                        ),
                    )
                )
            self.trips = []
            for key, row in trip_rows.items():
                ordered = sorted(calls[key], key=lambda item: item[0])
                if len(ordered) < 2 or len({n for n, _ in ordered}) != len(ordered):
                    raise ValueError("Invalid stop sequence")
                previous = -1
                for _, call in ordered:
                    if call.arrival < previous or call.departure < call.arrival:
                        raise ValueError("Nonmonotonic trip times")
                    previous = call.departure
                self.trips.append(
                    BusTrip(
                        key,
                        row["service_id"],
                        routes[row["route_id"]]["route_short_name"],
                        row.get("trip_headsign", ""),
                        row.get("shape_id", ""),
                        tuple(c for _, c in ordered),
                    )
                )
            self.calendars = rows("calendar.txt", False)
            self.exceptions = rows("calendar_dates.txt", False)
            if len({r["service_id"] for r in self.calendars}) != len(self.calendars):
                raise ValueError("Duplicate calendar service")
            if len({(r["service_id"], r["date"]) for r in self.exceptions}) != len(self.exceptions):
                raise ValueError("Duplicate service-day exception")
            for row in self.exceptions:
                gtfs_date(row["date"])
            for row in self.calendars:
                if gtfs_date(row["start_date"]) > gtfs_date(row["end_date"]):
                    raise ValueError("Reversed service dates")
                if any(row[weekday] not in {"0", "1"} for weekday in WEEKDAYS):
                    raise ValueError("Invalid weekday service flag")
            known_services = {r["service_id"] for r in self.calendars + self.exceptions}
            if any(t.service not in known_services for t in self.trips):
                raise ValueError("Unknown service")
            if any(r["exception_type"] not in {"1", "2"} for r in self.exceptions):
                raise ValueError("Invalid calendar exception")
            dates = [gtfs_date(r[k]) for r in self.calendars for k in ("start_date", "end_date")]
            dates += [gtfs_date(r["date"]) for r in self.exceptions if r["exception_type"] == "1"]
            if not dates or not self.trips or not self.stops:
                raise ValueError("Empty timetable")
            self.start, self.end = min(dates), max(dates)
            self.shapes = {}
            invalid_shapes = set()
            for row in rows("shapes.txt", False):
                point = [float(row["shape_pt_lon"]), float(row["shape_pt_lat"])]
                if not all(math.isfinite(x) for x in point) or not (
                    20 <= point[0] <= 23 and 40 <= point[1] <= 43
                ):
                    invalid_shapes.add(row["shape_id"])
                    continue
                self.shapes.setdefault(row["shape_id"], []).append(
                    (int(row["shape_pt_sequence"]), point)
                )
            self.shapes = {
                key: [p for _, p in sorted(points)]
                for key, points in self.shapes.items()
                if key not in invalid_shapes
            }
            info = rows("feed_info.txt", False)
            self.version = (
                info[0].get("feed_version", self.sha256[:12]) if info else self.sha256[:12]
            )

    def services(self, day: date) -> set[str]:
        weekday = WEEKDAYS[day.weekday()]
        active = {
            r["service_id"]
            for r in self.calendars
            if gtfs_date(r["start_date"]) <= day <= gtfs_date(r["end_date"]) and r[weekday] == "1"
        }
        for row in self.exceptions:
            if gtfs_date(row["date"]) == day:
                if row["exception_type"] == "1":
                    active.add(row["service_id"])
                else:
                    active.discard(row["service_id"])
        return active

    def runs(self, departure: float):
        """GTFS service seconds are measured from local noon minus twelve hours."""
        day = datetime.fromtimestamp(departure, SKOPJE).date()
        result = []
        for offset in (-1, 0, 1):
            service_day = day + timedelta(days=offset)
            base = datetime.combine(service_day, daytime(12), SKOPJE).timestamp() - 43200
            active = self.services(service_day)
            result.extend(
                (base, trip)
                for trip in self.trips
                if trip.service in active
                and base + trip.calls[-1].arrival >= departure
                and base + trip.calls[0].departure <= departure + 14400
            )
        return result


class TransitFeedStore:
    """One-hour cache, bounded downloads, atomic replacement, no stale fallback."""

    def __init__(self, path: Path, transport=None):
        self.path, self.transport = path, transport
        self._lock = threading.Lock()
        self._feed = None
        self._loaded = 0.0
        self._failed = 0.0

    def get(self) -> TransitFeed:
        with self._lock:
            now = time.time()
            if self._feed is not None and now - self._loaded < 3600:
                return self._feed
            if now - self._failed < 60:
                raise RoutingError(
                    "transit_unavailable", "JSP timetable is unavailable. Retry shortly.", 503
                )
            try:
                if self.path.exists() and now - self.path.stat().st_mtime < 3600:
                    data = self.path.read_bytes()
                    fetched = self.path.stat().st_mtime
                else:
                    started = time.monotonic()
                    with (
                        httpx.Client(
                            timeout=10, transport=self.transport, follow_redirects=False
                        ) as client,
                        client.stream("GET", JSP_FEED_URL) as response,
                    ):
                        response.raise_for_status()
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_ZIP or time.monotonic() - started > 15:
                                raise ValueError("GTFS download budget")
                    data, fetched = bytes(body), now
                feed = TransitFeed(data)
                if fetched == now:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = self.path.with_suffix(".tmp")
                    temporary.write_bytes(data)
                    temporary.replace(self.path)
                feed.fetched_at = fetched
                self._feed, self._loaded = feed, fetched
                return feed
            except (
                httpx.HTTPError,
                OSError,
                ValueError,
                KeyError,
                zipfile.BadZipFile,
                UnicodeError,
                csv.Error,
                TypeError,
            ) as error:
                self._failed = now
                raise RoutingError(
                    "transit_unavailable", "JSP timetable is unavailable. Retry shortly.", 503
                ) from error
