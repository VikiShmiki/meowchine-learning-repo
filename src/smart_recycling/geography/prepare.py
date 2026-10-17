"""CLI preparing versioned population and network inputs outside the web runtime."""

import argparse
import importlib.metadata
import math
from pathlib import Path

import osmium
from shapely.ops import unary_union

from smart_recycling.geography.boundaries import extract_boundaries, validate_boundaries
from smart_recycling.geography.io import fetch, read_json, sha256, write_json
from smart_recycling.geography.network import diagnostic_graph, extract_network, snap_records
from smart_recycling.geography.population import prepare_population


def infrastructure_sites(directory: Path) -> list[dict]:
    """Preserve established City site identifiers; never include the metro extension."""
    sites = {}
    for name in ("pakomak_recycling.geojson", "city_mixed_waste.geojson"):
        collection = read_json(directory / name)
        for feature in collection["features"]:
            properties = feature["properties"]
            lon, lat = feature["geometry"]["coordinates"]
            identifier = properties["site_id"]
            entry = {"id": identifier, "longitude": round(lon, 6), "latitude": round(lat, 6)}
            if identifier in sites and sites[identifier] != entry:
                raise ValueError(f"Inconsistent source site ID {identifier}")
            sites[identifier] = entry
    return [sites[key] for key in sorted(sites)]


def run(config_path: Path, raw: Path, output: Path, infrastructure: Path) -> dict:
    """Acquire pinned inputs, validate them, and emit a self-describing artifact package."""
    config = read_json(config_path)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output {output} is not empty; choose a new output directory")
    output.mkdir(parents=True, exist_ok=True)
    for source in config["sources"]:
        print(f"Verify/download {source['filename']}", flush=True)
        fetch(source["url"], raw / source["filename"], source["sha256"])
    pbf = raw / "macedonia.osm.pbf"
    with osmium.io.Reader(str(pbf)) as reader:
        timestamp = reader.header().get("osmosis_replication_timestamp")
    if timestamp != config["network_timestamp"]:
        raise ValueError("OSM header timestamp does not match the source manifest")
    print("Extract/validate municipal boundaries", flush=True)
    collection = extract_boundaries(pbf, config["municipalities"])
    boundaries, boundary_report = validate_boundaries(collection, config["metric_crs"])
    write_json(output / "municipalities.geojson", collection)
    print("Apportion population to municipalities", flush=True)
    demand, population_report = prepare_population(
        raw / "population.tif", collection, boundaries, config["metric_crs"]
    )
    print("Extract street topology and complete restriction records", flush=True)
    network = extract_network(
        pbf, unary_union(boundaries), config["metric_crs"], config["network_buffer_m"]
    )
    write_json(output / "network.json.gz", network)
    print("Validate walking and driving topology; audit access candidates", flush=True)
    walking, walk_report = diagnostic_graph(
        network, "walk", config["metric_crs"], config["walking_speed_kmh"]
    )
    driving, drive_report = diagnostic_graph(network, "drive", config["metric_crs"])
    demand = snap_records(demand, walking, config["metric_crs"], config["snap_limit_m"])
    sites = infrastructure_sites(infrastructure)
    walk_sites = snap_records(sites, walking, config["metric_crs"], config["snap_limit_m"])
    drive_sites = snap_records(sites, driving, config["metric_crs"], config["snap_limit_m"])
    write_json(output / "population.json.gz", demand)
    write_json(output / "site_access.json.gz", {"walk": walk_sites, "drive": drive_sites})
    way_ids = {way["id"] for way in network["ways"]}
    node_ids = {node["id"] for node in network["nodes"]}
    incomplete = [
        relation["id"]
        for relation in network["restrictions"]
        if any(
            (member["type"] == "w" and member["ref"] not in way_ids)
            or (member["type"] == "n" and member["ref"] not in node_ids)
            for member in relation["members"]
        )
    ]
    report = {
        "schema_version": 1,
        "boundaries": boundary_report,
        "population": population_report,
        "walking": walk_report,
        "driving": drive_report,
        "restriction_count": len(network["restrictions"]),
        "boundary_crossing_restrictions": incomplete,
        "access_audit": {
            "snap_limit_m": config["snap_limit_m"],
            "population_beyond_snap_limit": math.fsum(
                row["population"] for row in demand if row["snap_status"] == "too_far"
            ),
            "population_on_smaller_components": math.fsum(
                row["population"] for row in demand if row["component"] not in (None, 0)
            ),
            "walk_sites_beyond_snap_limit": [
                r["id"] for r in walk_sites if r["snap_status"] == "too_far"
            ],
            "drive_sites_beyond_snap_limit": [
                r["id"] for r in drive_sites if r["snap_status"] == "too_far"
            ],
            "note": "Nearest segments do not prove legal access; coverage not computed",
        },
        "limitations": [
            "WorldPop alpha modeled population, not current census or household locations",
            "NoData population is unknown; coverage denominator is modeled population only",
            "Border pixels split uniformly by area; representative locations approximate demand",
            "OSM roads/boundaries are community data, not a field audit",
            "Conservative access profile excludes conditional/unknown access and foot restrictions",
            "Drive diagnostic graph does not apply preserved turn restrictions; not for routing",
            "Snapping may cross walls/water/private land; connectors need review before coverage",
            "Flat walking speed ignores slope, traffic lights and individual mobility",
        ],
    }
    write_json(output / "qa.json", report)
    manifest = {
        **config,
        "preparation_version": 1,
        "source_manifest_sha256": sha256(config_path),
        "preparation_code_sha256": {
            path.name: sha256(path) for path in sorted(Path(__file__).parent.glob("*.py"))
        },
        "infrastructure_checksums": {
            name: sha256(infrastructure / name)
            for name in ("pakomak_recycling.geojson", "city_mixed_waste.geojson")
        },
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "osmium", "pyproj", "rasterio", "shapely", "networkx")
        },
        "artifacts": {
            path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in sorted(output.iterdir())
            if path.is_file()
        },
    }
    write_json(output / "manifest.json", manifest)
    return report


def main() -> None:
    """Prepare a fresh artifact directory; reruns may reuse verified downloads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources", type=Path, default=Path("data/geography/skopje-v1/sources.json")
    )
    parser.add_argument("--raw", type=Path, default=Path("data/raw/geography"))
    parser.add_argument("--out", type=Path, default=Path("data/processed/geography/skopje-v1"))
    parser.add_argument(
        "--infrastructure", type=Path, default=Path("data/infrastructure/skopje-2026-09-19")
    )
    args = parser.parse_args()
    try:
        report = run(args.sources, args.raw, args.out, args.infrastructure)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(
            1,
            f"Geography preparation failed: {error}\nSources: {args.sources}\n"
            f"Output: {args.out}\nRestore pinned inputs or use a fresh --out directory.\n",
        )
    print(f"Prepared {report['population']['demand_locations']} demand locations in {args.out}")


if __name__ == "__main__":
    main()
