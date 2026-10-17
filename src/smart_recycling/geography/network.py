"""Preserve OSM topology and restrictions; build conservative diagnostic mode graphs."""

from collections import Counter
from pathlib import Path

import networkx as nx
import osmium
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform
from shapely.prepared import prep
from shapely.strtree import STRtree

WALK_HIGHWAYS = {
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "service",
    "track",
    "path",
    "footway",
    "pedestrian",
    "steps",
    "cycleway",
    "bridleway",
}
DRIVE_HIGHWAYS = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
    "service",
    "track",
}
PUBLIC_ACCESS = {"yes", "designated", "permissive", "official"}


def allowed(tags: dict[str, str], mode: str, *, node: bool = False) -> bool:
    """Resolve mode-specific access first; conservatively exclude conditional/unknown access."""
    if mode not in {"walk", "drive"}:
        raise ValueError(f"Unsupported mode: {mode}")
    keys = (
        ("foot", "access") if mode == "walk" else ("motorcar", "motor_vehicle", "vehicle", "access")
    )
    if any(key in tags for key in ("construction", "proposed", "disused")):
        return False
    if any(key.endswith(":conditional") for key in tags):
        return False
    access = next((tags[key] for key in keys if key in tags), None)
    if access is not None and access not in PUBLIC_ACCESS:
        return False
    if node:
        barrier = tags.get("barrier")
        if barrier and barrier != "no" and access is None:
            return mode == "walk" and barrier in {"bollard", "cycle_barrier", "entrance"}
        return True
    if tags.get("area") == "yes" or tags.get("indoor") == "yes":
        return False
    highways = WALK_HIGHWAYS if mode == "walk" else DRIVE_HIGHWAYS
    if tags.get("highway") not in highways:
        return False
    if mode == "walk" and tags.get("highway") in {"cycleway", "bridleway"}:
        return tags.get("foot") in PUBLIC_ACCESS
    return not (
        mode == "walk" and tags.get("motorroad") == "yes" and tags.get("foot") not in PUBLIC_ACCESS
    )


def directions(tags: dict[str, str], mode: str) -> tuple[bool, bool]:
    """Return forward/backward permissions, treating pedestrian one-way tags separately."""
    if mode not in {"walk", "drive"}:
        raise ValueError(f"Unsupported mode: {mode}")
    if mode == "walk":
        value = tags.get("oneway:foot", "no")
    else:
        value = next(
            (
                tags[k]
                for k in ("oneway:motorcar", "oneway:motor_vehicle", "oneway:vehicle", "oneway")
                if k in tags
            ),
            None,
        )
        if value is None:
            value = (
                "yes"
                if tags.get("junction") == "roundabout" or tags.get("highway") == "motorway"
                else "no"
            )
    if value in {"yes", "1", "true"}:
        result = (True, False)
    elif value == "-1":
        result = (False, True)
    elif value in {"no", "0", "false"}:
        result = (True, True)
    else:
        return False, False
    keys = (
        ("foot", "access") if mode == "walk" else ("motorcar", "motor_vehicle", "vehicle", "access")
    )
    return tuple(
        permitted
        and next(
            (
                tags[f"{key}:{direction}"] in PUBLIC_ACCESS
                for key in keys
                if f"{key}:{direction}" in tags
            ),
            True,
        )
        for permitted, direction in zip(result, ("forward", "backward"), strict=True)
    )


def retain_restrictions(relations: list[dict], way_ids: set[int]) -> list[dict]:
    """Keep full members/tags of every restriction touching an extracted road."""
    return sorted(
        (
            relation
            for relation in relations
            if any(
                member["type"] == "w" and member["ref"] in way_ids for member in relation["members"]
            )
        ),
        key=lambda relation: relation["id"],
    )


def extract_network(pbf: Path, city, metric_crs: str, buffer_m: float) -> dict:
    """Keep whole ways intersecting the city buffer, without breaking topology or tags."""
    unproject = Transformer.from_crs(metric_crs, "EPSG:4326", always_xy=True).transform
    extent = city.buffer(buffer_m)
    geographic_extent = transform(unproject, extent)
    prepared_extent = prep(geographic_extent)
    ways, tagged_nodes, relations = [], {}, []
    coordinates = {}

    class Roads(osmium.SimpleHandler):
        def node(self, node: osmium.osm.Node) -> None:
            tags = dict(node.tags)
            if tags:
                tagged_nodes[node.id] = tags

        def way(self, way: osmium.osm.Way) -> None:
            tags = dict(way.tags)
            if "highway" not in tags:
                return
            if not all(node.location.valid() for node in way.nodes):
                raise ValueError(f"Incomplete highway geometry: OSM way {way.id}")
            coords = [(node.lon, node.lat) for node in way.nodes]
            if len(coords) < 2 or not prepared_extent.intersects(LineString(coords)):
                return
            ways.append({"id": way.id, "nodes": [node.ref for node in way.nodes], "tags": tags})
            for node in way.nodes:
                coordinates[node.ref] = [node.lon, node.lat]

        def relation(self, relation: osmium.osm.Relation) -> None:
            tags = dict(relation.tags)
            if tags.get("type", "").startswith("restriction"):
                relations.append(
                    {
                        "id": relation.id,
                        "tags": tags,
                        "members": [
                            {"type": member.type, "ref": member.ref, "role": member.role}
                            for member in relation.members
                        ],
                    }
                )

    # The location handler runs before filters, so untagged road-node coordinates
    # remain available. Only Python callbacks for irrelevant untagged objects vanish.
    Roads().apply_file(str(pbf), locations=True, filters=[osmium.filter.EmptyTagFilter()])
    return {
        "schema_version": 1,
        "nodes": [
            {
                "id": key,
                "longitude": value[0],
                "latitude": value[1],
                "tags": tagged_nodes.get(key, {}),
            }
            for key, value in sorted(coordinates.items())
        ],
        "ways": sorted(ways, key=lambda way: way["id"]),
        "restrictions": retain_restrictions(relations, {way["id"] for way in ways}),
        "buffer_m": buffer_m,
        "driving_routing_ready": False,
        "driving_note": "Turn restrictions are preserved, not enforced by diagnostic graphs",
    }


def diagnostic_graph(
    network: dict, mode: str, metric_crs: str, speed_kmh: float = 4.8
) -> tuple[nx.MultiDiGraph, dict]:
    """Construct topology for QA; driving graph must not be used for route instructions."""
    if speed_kmh <= 0:
        raise ValueError("Walking speed must be positive")
    project = Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True).transform
    nodes = {node["id"]: node for node in network["nodes"]}
    positions = {key: project(node["longitude"], node["latitude"]) for key, node in nodes.items()}
    graph = nx.MultiDiGraph()
    exclusions = Counter()
    # A foot-specific turn restriction cannot be silently ignored: exclude its ways for QA.
    foot_restricted = {
        member["ref"]
        for restriction in network["restrictions"]
        if any(key.startswith("restriction:foot") for key in restriction["tags"])
        for member in restriction["members"]
        if member["type"] == "w"
    }
    for way in network["ways"]:
        if not allowed(way["tags"], mode) or (mode == "walk" and way["id"] in foot_restricted):
            exclusions["access_or_profile_way"] += 1
            continue
        forward, backward = directions(way["tags"], mode)
        if not forward and not backward:
            exclusions["direction_way"] += 1
        for start, end in zip(way["nodes"], way["nodes"][1:], strict=False):
            if start not in nodes or end not in nodes:
                raise ValueError(f"Orphan node reference in way {way['id']}")
            if not all(allowed(nodes[n]["tags"], mode, node=True) for n in (start, end)):
                exclusions["barrier_or_node_access_segment"] += 1
                continue
            line = LineString([positions[start], positions[end]])
            if line.length == 0:
                exclusions["zero_length_segment"] += 1
                continue
            for u, v, enabled in ((start, end, forward), (end, start, backward)):
                if enabled:
                    attributes = {"length_m": line.length, "way_id": way["id"]}
                    if mode == "walk":
                        attributes["seconds"] = line.length / (speed_kmh / 3.6)
                    graph.add_edge(u, v, **attributes)
    nx.set_node_attributes(graph, {key: {"xy": positions[key]} for key in graph})
    components = sorted(nx.weakly_connected_components(graph), key=lambda c: (-len(c), min(c)))
    for index, component in enumerate(components):
        nx.set_node_attributes(graph, {node: index for node in component}, "component")
    return graph, {
        "nodes": len(graph),
        "directed_edges": graph.number_of_edges(),
        "weak_components": len(components),
        "largest_component_nodes": len(components[0]) if components else 0,
        "strong_components": nx.number_strongly_connected_components(graph),
        "exclusions": dict(exclusions),
        "routing_ready": False,
    }


def snap_records(
    records: list[dict], graph: nx.MultiDiGraph, metric_crs: str, limit_m: float
) -> list[dict]:
    """Audit nearest *segments*, never silently bridge long gaps or remove unsnapped demand."""
    project = Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True).transform
    segments = sorted(
        {(min(u, v), max(u, v), data["way_id"]) for u, v, data in graph.edges(data=True)}
    )
    if not segments:
        raise ValueError("No usable network segments")
    lines = [LineString([graph.nodes[u]["xy"], graph.nodes[v]["xy"]]) for u, v, _ in segments]
    tree = STRtree(lines)
    results = []
    for record in records:
        point = Point(project(record["longitude"], record["latitude"]))
        indices, distances = tree.query_nearest(point, return_distance=True)
        index = min(int(i) for i in indices)
        distance = float(min(distances))
        u, v, way = segments[index]
        connected = distance <= limit_m
        results.append(
            {
                **record,
                "snap_status": "candidate_unverified" if connected else "too_far",
                "snap_distance_m": distance,
                "way_id": way if connected else None,
                "segment_nodes": [u, v] if connected else None,
                "segment_fraction": lines[index].project(point, normalized=True)
                if connected
                else None,
                "component": graph.nodes[u]["component"] if connected else None,
            }
        )
    return results
