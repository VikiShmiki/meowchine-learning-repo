"""Offline fixtures for geographic mass conservation, topology and access semantics."""

import json
import shutil
from pathlib import Path

import networkx as nx
import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

from smart_recycling.geography.boundaries import validate_boundaries
from smart_recycling.geography.io import fetch, read_json, sha256, write_json
from smart_recycling.geography.network import (
    allowed,
    diagnostic_graph,
    directions,
    extract_network,
    retain_restrictions,
    snap_records,
)
from smart_recycling.geography.population import apportion_cell, prepare_population
from smart_recycling.geography.validate import validate_package


def test_fractional_population_and_partial_border_cells() -> None:
    fragments = apportion_cell(box(0, 0, 10, 10), 7.5, [box(0, 0, 4, 10), box(4, 0, 8, 10)])
    assert [weight for _, weight, _ in fragments] == pytest.approx([3, 3])
    assert sum(weight for _, weight, _ in fragments) == 6  # 20% outside the city
    with pytest.raises(ValueError, match="duplicated"):
        apportion_cell(box(0, 0, 1, 1), 1, [box(0, 0, 1, 1)] * 2)
    with pytest.raises(ValueError, match="Invalid population"):
        apportion_cell(box(0, 0, 1, 1), float("nan"), [])


def test_raster_nodata_is_reported_not_zero(tmp_path) -> None:
    path = tmp_path / "counts.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        nodata=-99999,
        transform=from_origin(21, 42, 0.001, 0.001),
    ) as out:
        out.write(np.array([[2.5, 3.25], [0, -99999]], dtype="float32"), 1)
    # Keep boundaries just within the raster extent to avoid floating-point window expansion.
    collection = {
        "features": [
            {
                "properties": {"id": "a"},
                "geometry": mapping(box(21.00000001, 41.99800001, 21.00199999, 41.99999999)),
            }
        ]
    }
    boundaries, _ = validate_boundaries(collection, "EPSG:32634")
    rows, report = prepare_population(path, collection, boundaries, "EPSG:32634")
    assert report["total_modeled_population"] == pytest.approx(5.75, abs=0.001)
    assert report["nodata_area_km2"] > 0
    assert report["zero_cells"] == 1
    assert len(rows) == 2
    assert sum(row["population"] for row in rows) == report["total_modeled_population"]
    write_json(tmp_path / "population.json.gz", rows)
    assert read_json(tmp_path / "population.json.gz") == rows


def test_boundaries_reject_overlap_and_duplicate_ids() -> None:
    features = [
        {"properties": {"id": str(i)}, "geometry": mapping(box(21, 42, 21.1, 42.1))}
        for i in range(2)
    ]
    with pytest.raises(ValueError, match="overlap"):
        validate_boundaries({"features": features}, "EPSG:32634")
    features[1]["properties"]["id"] = "0"
    with pytest.raises(ValueError, match="duplicate"):
        validate_boundaries({"features": features}, "EPSG:32634")


@pytest.mark.parametrize(
    ("tags", "walk", "drive"),
    [
        ({"highway": "residential"}, True, True),
        ({"highway": "motorway"}, False, True),
        ({"highway": "footway"}, True, False),
        ({"highway": "service", "access": "private"}, False, False),
        ({"highway": "service", "access": "private", "foot": "yes"}, True, False),
        ({"highway": "service", "vehicle": "no", "motorcar": "yes"}, True, True),
        ({"highway": "service", "access:conditional": "yes @ (Mo-Fr)"}, False, False),
        ({"highway": "construction"}, False, False),
        ({"highway": "path", "foot": "no"}, False, False),
    ],
)
def test_mode_specific_access(tags, walk, drive) -> None:
    assert allowed(tags, "walk") is walk
    assert allowed(tags, "drive") is drive


def test_one_way_and_barriers() -> None:
    assert directions({"oneway": "yes"}, "walk") == (True, True)
    assert directions({"oneway": "yes"}, "drive") == (True, False)
    assert directions({"oneway": "-1"}, "drive") == (False, True)
    assert directions({"oneway:foot": "yes"}, "walk") == (True, False)
    assert directions({"junction": "roundabout"}, "drive") == (True, False)
    assert directions({"oneway": "reversible"}, "drive") == (False, False)
    assert directions({"foot:backward": "no"}, "walk") == (True, False)
    assert not allowed({"barrier": "gate"}, "walk", node=True)
    assert allowed({"barrier": "gate", "foot": "yes"}, "walk", node=True)
    assert not allowed({"barrier": "bollard"}, "drive", node=True)


def tiny_network() -> dict:
    return {
        "nodes": [
            {"id": i, "longitude": 21 + i * 0.001, "latitude": 42, "tags": {}} for i in range(1, 5)
        ],
        "ways": [
            {"id": 10, "nodes": [1, 2, 3], "tags": {"highway": "residential", "oneway": "yes"}},
            {"id": 20, "nodes": [3, 4], "tags": {"highway": "footway"}},
        ],
        "restrictions": [],
    }


def test_graph_uses_network_distance_and_mode_direction() -> None:
    walking, _ = diagnostic_graph(tiny_network(), "walk", "EPSG:32634")
    driving, _ = diagnostic_graph(tiny_network(), "drive", "EPSG:32634")
    assert nx.has_path(walking, 4, 1)
    assert not nx.has_path(driving, 3, 1)
    assert 4 not in driving
    length = nx.shortest_path_length(walking, 1, 4, weight="length_m")
    seconds = nx.shortest_path_length(walking, 1, 4, weight="seconds")
    assert seconds == pytest.approx(length / (4.8 / 3.6))


def test_restrictions_preserve_exceptions_via_and_conditional_tags() -> None:
    restriction = {
        "id": 100,
        "tags": {
            "type": "restriction",
            "restriction": "no_left_turn",
            "except": "bicycle",
            "restriction:conditional": "no_left_turn @ (Mo-Fr)",
        },
        "members": [
            {"type": "w", "ref": 10, "role": "from"},
            {"type": "w", "ref": 99, "role": "via"},
            {"type": "w", "ref": 20, "role": "to"},
        ],
    }
    retained = retain_restrictions([restriction], {10})
    assert retained == [restriction]  # Even out-of-extract member 99 survives.
    assert retain_restrictions([restriction], {30}) == []


def test_disconnected_population_and_nearest_segment_are_retained() -> None:
    graph, _ = diagnostic_graph(tiny_network(), "walk", "EPSG:32634")
    rows = [
        {"id": "near", "longitude": 21.0015, "latitude": 42, "population": 2.5},
        {"id": "far", "longitude": 22, "latitude": 42, "population": 7.5},
    ]
    result = snap_records(rows, graph, "EPSG:32634", 10)
    assert result[0]["snap_status"] == "candidate_unverified"
    assert result[0]["segment_fraction"] == pytest.approx(0.5, abs=0.001)
    assert result[1]["snap_status"] == "too_far"
    assert result[1]["component"] is None
    assert sum(row["population"] for row in result) == 10
    # A node-only snap would miss the segment's midpoint with the same 10m limit.
    project = Transformer.from_crs("EPSG:4326", "EPSG:32634", always_xy=True)
    assert project.transform(21.0015, 42) != graph.nodes[1]["xy"]


def test_download_verifies_cached_source_and_serialization(tmp_path) -> None:
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"source": "fixture"}), encoding="utf-8")
    fetch("https://invalid.example", path, sha256(path))
    with pytest.raises(ValueError, match="Checksum mismatch"):
        fetch("https://invalid.example", path, "0" * 64)
    target = tmp_path / "artifact.json.gz"
    write_json(target, {"fraction": 0.25})
    checksum = sha256(target)
    write_json(target, {"fraction": 0.25})
    assert sha256(target) == checksum
    assert read_json(target) == {"fraction": 0.25}


def test_osm_extraction_preserves_node_access_and_turn_relations(tmp_path) -> None:
    path = tmp_path / "fixture.osm"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
 <node id="1" lat="42.0" lon="21.0" version="1"/>
 <node id="2" lat="42.0" lon="21.001" version="1"><tag k="vehicle" v="no"/></node>
 <node id="3" lat="42.001" lon="21.001" version="1"/>
 <way id="10" version="1"><nd ref="1"/><nd ref="2"/>
  <tag k="highway" v="residential"/></way>
 <way id="20" version="1"><nd ref="2"/><nd ref="3"/>
  <tag k="highway" v="residential"/></way>
 <relation id="100" version="1">
  <member type="way" ref="10" role="from"/>
  <member type="node" ref="2" role="via"/>
  <member type="way" ref="20" role="to"/>
  <tag k="type" v="restriction"/><tag k="restriction" v="no_left_turn"/>
 </relation>
</osm>""",
        encoding="utf-8",
    )
    project = Transformer.from_crs("EPSG:4326", "EPSG:32634", always_xy=True)
    x, y = project.transform(21.001, 42)
    result = extract_network(path, box(x - 100, y - 100, x + 100, y + 100), "EPSG:32634", 100)
    assert len(result["ways"]) == 2
    assert result["nodes"][1]["tags"] == {"vehicle": "no"}
    assert result["restrictions"][0]["members"][1] == {"type": "n", "ref": 2, "role": "via"}
    assert result["restrictions"][0]["tags"]["restriction"] == "no_left_turn"
    graph, _ = diagnostic_graph(result, "drive", "EPSG:32634")
    assert graph.number_of_edges() == 0


def test_shared_geography_package() -> None:
    root = Path(__file__).resolve().parents[1]
    base = root / "data/geography/skopje-v1"
    result = validate_package(
        base / "prepared", base / "sources.json", root / "data/infrastructure/skopje-2026-09-19"
    )
    assert result["municipalities"] == 10
    assert result["demand_locations"] > 0


def test_shared_package_rejects_corruption(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    base = root / "data/geography/skopje-v1"
    shutil.copytree(base / "prepared", tmp_path / "package")
    (tmp_path / "package/qa.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum/size mismatch"):
        validate_package(
            tmp_path / "package",
            base / "sources.json",
            root / "data/infrastructure/skopje-2026-09-19",
        )
