"""Offline verification of a shared geographic package and its provenance links."""

import argparse
import math
from pathlib import Path

from smart_recycling.geography.io import read_json, sha256


def validate_package(directory: Path, source_manifest: Path, infrastructure: Path) -> dict:
    """Reject corruption, duplicate IDs, orphan topology, and lost population mass."""
    manifest = read_json(directory / "manifest.json")
    if manifest["schema_version"] != 1 or manifest["preparation_version"] != 1:
        raise ValueError("Unsupported geography package version")
    if sha256(source_manifest) != manifest["source_manifest_sha256"]:
        raise ValueError("Geography source manifest changed")
    required = {
        "municipalities.geojson",
        "population.json.gz",
        "network.json.gz",
        "site_access.json.gz",
        "qa.json",
    }
    if set(manifest["artifacts"]) != required:
        raise ValueError("Unexpected/missing geography artifacts")
    for name, metadata in manifest["artifacts"].items():
        path = directory / name
        if sha256(path) != metadata["sha256"] or path.stat().st_size != metadata["bytes"]:
            raise ValueError(f"Geography artifact checksum/size mismatch: {name}")
    for name, checksum in manifest["infrastructure_checksums"].items():
        if name not in {"pakomak_recycling.geojson", "city_mixed_waste.geojson"}:
            raise ValueError("Unexpected infrastructure filename")
        if sha256(infrastructure / name) != checksum:
            raise ValueError(f"Infrastructure changed: {name}; rebuild access candidates")
    boundaries = read_json(directory / "municipalities.geojson")
    municipalities = {row["properties"]["id"] for row in boundaries["features"]}
    expected = {row["id"] for row in manifest["municipalities"]}
    if municipalities != expected or len(boundaries["features"]) != len(expected):
        raise ValueError("Missing or duplicate municipality IDs")
    network = read_json(directory / "network.json.gz")
    if network["schema_version"] != 1 or network["driving_routing_ready"] is not False:
        raise ValueError("Unsupported or incorrectly certified network")
    node_ids = {node["id"] for node in network["nodes"]}
    way_ids = {way["id"] for way in network["ways"]}
    if len(node_ids) != len(network["nodes"]) or len(way_ids) != len(network["ways"]):
        raise ValueError("Duplicate OSM IDs")
    for way in network["ways"]:
        if len(way["nodes"]) < 2 or not set(way["nodes"]) <= node_ids:
            raise ValueError("Invalid/orphan OSM way nodes")
    for node in network["nodes"]:
        if not (-180 <= node["longitude"] <= 180 and -90 <= node["latitude"] <= 90):
            raise ValueError("Invalid OSM coordinate")
    demand = read_json(directory / "population.json.gz")
    expected_site_ids = {
        feature["properties"]["site_id"]
        for name in manifest["infrastructure_checksums"]
        for feature in read_json(infrastructure / name)["features"]
    }
    access = read_json(directory / "site_access.json.gz")
    if set(access) != {"walk", "drive"}:
        raise ValueError("Missing access-audit mode")
    for mode, sites in access.items():
        if {row["id"] for row in sites} != expected_site_ids or len(sites) != len(
            expected_site_ids
        ):
            raise ValueError(f"Missing or duplicate site IDs for {mode}")
    for row in demand + access["walk"] + access["drive"]:
        if not (-180 <= row["longitude"] <= 180 and -90 <= row["latitude"] <= 90):
            raise ValueError("Invalid access coordinate")
        if not math.isfinite(row["snap_distance_m"]) or row["snap_distance_m"] < 0:
            raise ValueError("Invalid access distance")
        if row["snap_status"] not in {"candidate_unverified", "too_far"}:
            raise ValueError("Unknown or incorrectly certified access state")
        if row["snap_status"] == "too_far":
            if any(
                row[key] is not None
                for key in ("way_id", "segment_nodes", "segment_fraction", "component")
            ):
                raise ValueError("Disconnected access has network references")
        elif (
            row["way_id"] not in way_ids
            or not set(row["segment_nodes"]) <= node_ids
            or not 0 <= row["segment_fraction"] <= 1
            or row["snap_distance_m"] > manifest["snap_limit_m"]
        ):
            raise ValueError("Invalid/orphan access candidate")
    ids, weights = set(), {key: [] for key in municipalities}
    for row in demand:
        if row["id"] in ids or row["municipality_id"] not in municipalities:
            raise ValueError("Duplicate/orphan population ID")
        if not math.isfinite(row["population"]) or row["population"] <= 0:
            raise ValueError("Invalid population weight")
        ids.add(row["id"])
        weights[row["municipality_id"]].append(row["population"])
        if row["way_id"] is not None and row["way_id"] not in way_ids:
            raise ValueError("Orphan population network reference")
        if row["snap_status"] == "too_far" and row["component"] is not None:
            raise ValueError("Disconnected demand assigned a component")
    qa = read_json(directory / "qa.json")
    if len(demand) != qa["population"]["demand_locations"]:
        raise ValueError("Demand count mismatch")
    for key, values in weights.items():
        if not math.isclose(
            math.fsum(values),
            qa["population"]["municipal_population"][key],
            rel_tol=1e-10,
            abs_tol=1e-6,
        ):
            raise ValueError(f"Municipal population does not reconcile: {key}")
    if not math.isclose(
        math.fsum(row["population"] for row in demand),
        qa["population"]["total_modeled_population"],
        rel_tol=1e-10,
        abs_tol=1e-6,
    ):
        raise ValueError("City population does not reconcile")
    return {
        "municipalities": len(municipalities),
        "demand_locations": len(demand),
        "osm_nodes": len(node_ids),
        "osm_ways": len(way_ids),
    }


def main() -> None:
    """Verify the shared package without any network requests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/geography/skopje-v1/prepared"))
    parser.add_argument(
        "--sources", type=Path, default=Path("data/geography/skopje-v1/sources.json")
    )
    parser.add_argument(
        "--infrastructure", type=Path, default=Path("data/infrastructure/skopje-2026-09-19")
    )
    args = parser.parse_args()
    print(validate_package(args.directory, args.sources, args.infrastructure))


if __name__ == "__main__":
    main()
