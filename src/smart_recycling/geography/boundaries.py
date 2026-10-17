"""Extract explicitly identified OSM municipalities and reject broken topology."""

from pathlib import Path

import osmium
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union


def extract_boundaries(pbf: Path, municipalities: list[dict]) -> dict:
    """Assemble original OSM relation geometry, preserving IDs and tags."""
    wanted = {entry["osm_relation_id"]: entry for entry in municipalities}
    features = []
    factory = osmium.geom.GeoJSONFactory()

    class Areas(osmium.SimpleHandler):
        def area(self, area: osmium.osm.Area) -> None:
            if area.from_way() or area.orig_id() not in wanted:
                return
            import json

            tags = dict(area.tags)
            if tags.get("boundary") != "administrative" or tags.get("admin_level") != "7":
                raise ValueError(f"Unexpected municipality relation {area.orig_id()}")
            features.append(
                {
                    "type": "Feature",
                    "properties": {**wanted[area.orig_id()], "osm_tags": tags},
                    "geometry": json.loads(factory.create_multipolygon(area)),
                }
            )

    Areas().apply_file(str(pbf), locations=True)
    if {f["properties"]["osm_relation_id"] for f in features} != set(wanted):
        raise ValueError("Municipality relations missing or incomplete in the pinned OSM extract")
    return {
        "type": "FeatureCollection",
        "features": sorted(features, key=lambda f: f["properties"]["id"]),
    }


def validate_boundaries(collection: dict, metric_crs: str) -> tuple[list, dict]:
    """Validate distinct polygon IDs, geometry, overlaps, and report union holes."""
    project = Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True).transform
    shapes, ids = [], set()
    for feature in collection["features"]:
        identifier = feature["properties"]["id"]
        geometry = shape(feature["geometry"])
        if identifier in ids or geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Invalid/duplicate municipal geometry: {identifier}")
        if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"Non-polygon municipality: {identifier}")
        ids.add(identifier)
        shapes.append(transform(project, geometry))
    for index, geometry in enumerate(shapes):
        for other in shapes[index + 1 :]:
            if geometry.intersection(other).area > 1:
                raise ValueError("Municipal polygons overlap by more than 1 square metre")
    city = unary_union(shapes)
    polygons = [city] if city.geom_type == "Polygon" else list(city.geoms)
    from shapely.geometry import Polygon

    return shapes, {
        "municipality_count": len(ids),
        "area_km2": city.area / 1e6,
        "union_components": len(polygons),
        "interior_gap_area_m2": sum(Polygon(ring).area for p in polygons for ring in p.interiors),
        "overlap_tolerance_m2": 1,
    }
