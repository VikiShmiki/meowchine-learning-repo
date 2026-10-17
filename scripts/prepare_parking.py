"""Extract explicitly public parking and mapped driveway crossings from a pinned OSM PBF."""

import argparse
import hashlib
from pathlib import Path

import osmium
from shapely import LineString, Point, STRtree, from_wkb

from smart_recycling.parking_data import ParkingPlace, ParkingSnapshot, public_parking, records_hash


def build(path, source_url):
    factory = osmium.geom.WKBFactory()
    parks, roads = [], []

    class Extract(osmium.SimpleHandler):
        def node(self, node):
            if node.tags.get("amenity") != "parking":
                return
            tags = dict(node.tags)
            if public_parking(tags) and inside(node.location.lon, node.location.lat):
                parks.append(("node", node.id, tags, Point(node.location.lon, node.location.lat)))

        def area(self, area):
            if area.tags.get("amenity") != "parking":
                return
            tags = dict(area.tags)
            if not public_parking(tags):
                return
            polygon = from_wkb(bytes.fromhex(factory.create_multipolygon(area)))
            point = polygon.representative_point()
            if polygon.is_valid and inside(point.x, point.y):
                parks.append(
                    ("way" if area.from_way() else "relation", area.orig_id(), tags, polygon)
                )

        def way(self, way):
            if way.tags.get("highway") != "service":
                return
            tags = dict(way.tags)
            if (
                tags.get("highway") != "service"
                or any(
                    tags.get(k, "yes") not in {"yes", "permissive", "destination"}
                    for k in ("access", "vehicle", "motor_vehicle", "motorcar", "foot")
                )
                or any("conditional" in key for key in tags)
                or tags.get("oneway", "no") not in {"yes", "no", "1", "0", "true", "false", "-1"}
            ):
                return
            points = [(n.lon, n.lat) for n in way.nodes]
            if len(points) >= 2 and any(inside(*p) for p in points):
                roads.append((way.id, LineString(points), tags.get("oneway", "no")))

    Extract().apply_file(str(path), locations=True)
    tree = STRtree([line for _, line, _ in roads])
    places = []
    for kind, identifier, tags, shape in sorted(parks, key=lambda p: (p[0], p[1])):
        road_id = None
        if shape.geom_type == "Point":
            point, point_kind = shape, "mapped_point"
        else:
            crossings = []
            for index in tree.query(shape, predicate="intersects"):
                road, line, oneway = roads[index]
                crossings.extend((road, p.x, p.y) for p in entry_crossings(shape, line, oneway))
            if not crossings:
                continue  # Never route to an arbitrary polygon centre.
            road_id, x, y = min(crossings)
            point, point_kind = Point(x, y), "driveway_crossing"
        places.append(
            ParkingPlace(
                id=f"osm-{kind}-{identifier}",
                name=tags.get("name:en") or tags.get("name") or "Mapped public parking",
                latitude=round(point.y, 7),
                longitude=round(point.x, 7),
                access=tags["access"],
                point_kind=point_kind,
                fee=tags.get("fee", "unknown"),
                opening_hours=tags.get("opening_hours", "unknown"),
                operator=tags.get("operator", ""),
                driveway_osm_id=road_id,
            )
        )
    with osmium.io.Reader(str(path)) as reader:
        timestamp = reader.header().get("osmosis_replication_timestamp")
    return ParkingSnapshot(
        dataset_version="skopje-parking-" + timestamp[:10],
        source_timestamp=timestamp,
        source_url=source_url,
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        records_sha256=records_hash(places),
        places=places,
    )


def inside(lon, lat):
    return 21.2 <= lon <= 21.6 and 41.9 <= lat <= 42.1


def entry_crossings(shape, line, oneway):
    """Exclude tangencies, boundary overlaps and one-way exit-only crossings."""
    if oneway == "-1":
        line = LineString(list(line.coords)[::-1])
    hit = shape.boundary.intersection(line)
    hits = [hit] if hit.geom_type == "Point" else list(getattr(hit, "geoms", []))
    for point in hits:
        if point.geom_type != "Point":
            continue
        at = line.project(point)
        before = shape.contains(line.interpolate(max(0, at - 0.000002)))
        after = shape.contains(line.interpolate(min(line.length, at + 0.000002)))
        if (not before and after) or (oneway in {"no", "0", "false"} and before and not after):
            yield point


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", type=Path, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--output", type=Path, default=Path("data/parking/skopje-v1/parking.json"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    snapshot = build(args.pbf, args.source_url)
    content = snapshot.model_dump_json(indent=2) + "\n"
    if args.check:
        assert args.output.read_text(encoding="utf-8") == content, "Parking snapshot differs"
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(
        f"{'Verified' if args.check else 'Prepared'} {len(snapshot.places)} public parking points"
    )


if __name__ == "__main__":
    main()
