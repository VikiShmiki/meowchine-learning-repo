"""Population-weighted demand with explicit raster and boundary approximations."""

import math
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask, shapes
from rasterio.windows import Window, from_bounds
from shapely.geometry import box, mapping, shape
from shapely.ops import transform, unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree


def apportion_cell(cell, population: float, boundaries: list) -> list[tuple[int, float, object]]:
    """Split a cell by municipal area; keep fractional weights and representative points."""
    if not math.isfinite(population) or population < 0 or cell.area <= 0:
        raise ValueError("Invalid population or cell area")
    result = []
    for index, boundary in enumerate(boundaries):
        intersection = cell if boundary.covers(cell) else cell.intersection(boundary)
        if intersection.area > 0:
            result.append(
                (
                    index,
                    population * intersection.area / cell.area,
                    intersection.representative_point(),
                )
            )
    if sum(weight for _, weight, _ in result) > population + max(1e-8, population * 1e-8):
        raise ValueError("Population duplicated by overlapping boundaries")
    return result


def prepare_population(
    raster: Path, collection: dict, boundaries: list, metric_crs: str
) -> tuple[list[dict], dict]:
    """Clip count pixels proportionally to municipal area, without rounding people."""
    project = Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True).transform
    unproject = Transformer.from_crs(metric_crs, "EPSG:4326", always_xy=True).transform
    city = unary_union(boundaries)
    prepared_city = prep(city)
    prepared_boundaries = [prep(boundary) for boundary in boundaries]
    tree = STRtree(boundaries)
    rows, totals = [], [0.0] * len(boundaries)
    nodata_area, zero_cells, expected = 0.0, 0, 0.0
    with rasterio.open(raster) as source:
        if source.crs != "EPSG:4326" or source.count != 1:
            raise ValueError("Expected a single-band WGS84 population-count raster")
        if source.transform.b != 0 or source.transform.d != 0:
            raise ValueError("Rotated population rasters are unsupported")
        bounds = transform(unproject, city).bounds
        fractional = from_bounds(*bounds, source.transform)
        left, top = math.floor(fractional.col_off), math.floor(fractional.row_off)
        right = math.ceil(fractional.col_off + fractional.width)
        bottom = math.ceil(fractional.row_off + fractional.height)
        if left < 0 or top < 0 or right > source.width or bottom > source.height:
            raise ValueError("Population raster does not fully cover the city")
        window = Window(left, top, right - left, bottom - top)
        values = source.read(1, window=window, masked=True)
        window_transform = source.window_transform(window)
        inside = geometry_mask(
            [mapping(transform(unproject, city))],
            values.shape,
            window_transform,
            all_touched=True,
            invert=True,
        )
        missing = np.ma.getmaskarray(values) & inside
        # Polygonize missing regions once; avoid expensive intersections per empty pixel.
        for geometry, _ in shapes(
            missing.astype("uint8"), mask=missing, transform=window_transform
        ):
            nodata_area += transform(project, shape(geometry)).intersection(city).area
        for row, column in np.argwhere(inside & ~np.ma.getmaskarray(values)):
            r, c = int(row) + top, int(column) + left
            x1, y1 = source.transform * (c, r)
            x2, y2 = source.transform * (c + 1, r + 1)
            cell = transform(project, box(x1, y2, x2, y1))
            indices = sorted(
                int(i) for i in tree.query(cell) if prepared_boundaries[int(i)].intersects(cell)
            )
            if not indices:
                continue
            value = values[row, column]
            if not math.isfinite(float(value)) or value < 0:
                raise ValueError(f"Invalid population value at raster cell {r}/{c}")
            if value == 0:
                zero_cells += 1
                continue
            if len(indices) == 1 and prepared_boundaries[indices[0]].covers(cell):
                fragments = [(0, float(value), cell.representative_point())]
            else:
                fragments = apportion_cell(cell, float(value), [boundaries[i] for i in indices])
            expected += (
                float(value)
                if prepared_city.covers(cell)
                else (float(value) * cell.intersection(city).area / cell.area)
            )
            for local_index, weight, point in fragments:
                index = indices[local_index]
                municipality = collection["features"][index]["properties"]["id"]
                lon, lat = unproject(point.x, point.y)
                totals[index] += weight
                rows.append(
                    {
                        "id": f"wp2025:{r}:{c}:{municipality}",
                        "municipality_id": municipality,
                        "population": weight,
                        "longitude": lon,
                        "latitude": lat,
                        "raster_row": r,
                        "raster_column": c,
                    }
                )
        resolution = list(source.res)
    observed = math.fsum(row["population"] for row in rows)
    if not math.isclose(observed, expected, abs_tol=1e-5, rel_tol=1e-10):
        raise ValueError("Population does not reconcile after municipal assignment")
    return rows, {
        "total_modeled_population": observed,
        "union_clipped_population": expected,
        "municipal_population": {
            f["properties"]["id"]: total
            for f, total in zip(collection["features"], totals, strict=True)
        },
        "demand_locations": len(rows),
        "resolution_degrees": resolution,
        "nodata_area_km2": nodata_area / 1e6,
        "zero_cells": zero_cells,
        "method": "area-proportional border cells; representative point per municipal fragment",
        "status": "modeled_population_only; nodata is unknown, never zero",
    }
