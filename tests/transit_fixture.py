"""Small synthetic timetable, with no third-party timetable redistribution."""

import io
import zipfile
from datetime import date, timedelta

from smart_recycling.ors import NetworkRoute
from smart_recycling.transit import distance
from smart_recycling.transit_feed import TransitFeed


def archive(day=date(2026, 10, 17), changes=None):
    start, end = (
        (day - timedelta(days=2)).strftime("%Y%m%d"),
        (day + timedelta(days=7)).strftime("%Y%m%d"),
    )
    files = {
        "agency.txt": (
            "agency_id,agency_name,agency_url,agency_timezone\n"
            "2,JSP fixture,https://example.invalid,Europe/Skopje\n"
        ),
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "A,Board here,42,21.4\n"
            "B,Transfer here,42,21.45\n"
            "C,Glass stop,42,21.5\n"
            "D,Paper stop,42,21.55\n"
        ),
        "routes.txt": "route_id,route_short_name,route_type\nR1,5,3\nR2,22,3\n",
        "trips.txt": (
            "route_id,service_id,trip_id,trip_headsign,shape_id\n"
            "R1,S,T1,Glass terminus,shape\n"
            "R2,S,T2,Paper terminus,shape2\n"
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,10:10:00,10:10:00,A,1\n"
            "T1,10:20:00,10:20:00,B,2\n"
            "T1,10:30:00,10:30:00,C,3\n"
            "T2,10:24:00,10:24:00,B,1\n"
            "T2,10:35:00,10:35:00,D,2\n"
        ),
        "calendar.txt": (
            f"service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            f"S,1,1,1,1,1,1,1,{start},{end}\n"
        ),
        "calendar_dates.txt": "service_id,date,exception_type\n",
        "shapes.txt": (
            "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
            "shape,42,21.4,1\n"
            "shape,42,21.45,2\n"
            "shape,42,21.5,3\n"
            "shape2,42,21.45,1\n"
            "shape2,42,21.55,2\n"
        ),
        "feed_info.txt": (
            "feed_publisher_name,feed_publisher_url,feed_lang,feed_version\n"
            "Fixture,https://example.invalid,mk,synthetic-v1\n"
        ),
    }
    files.update(changes or {})
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zipped:
        for name, value in files.items():
            zipped.writestr(name, value)
    return output.getvalue()


class FixtureStore:
    def __init__(self, data=None):
        self.feed = TransitFeed(data or archive())
        self.feed.fetched_at = 1792224000

    def get(self):
        return self.feed


class Walking:
    def __init__(self):
        self.calls = []
        self.extra = 0

    def matrix(self, mode, points):
        assert mode == "walking"
        self.calls.append(("matrix", len(points)))
        return [[distance(a, b) / 1.33 for b in points] for a in points]

    def directions(self, mode, points):
        assert mode == "walking"
        self.calls.append(("directions", len(points)))
        length = distance(*points)
        return NetworkRoute(points, length, length / 1.33 + self.extra, [0, 0])
