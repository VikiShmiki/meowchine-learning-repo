"""Validate the shared Skopje snapshot against its original export checksums."""

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/infrastructure/skopje-2026-09-19"


def main() -> None:
    """Check export integrity, counts, identifiers, and coordinate validity."""
    summary = json.loads((SNAPSHOT / "summary.json").read_text(encoding="utf-8"))
    expected_counts = {
        "pakomak_recycling": 538,
        "city_mixed_waste": 1058,
        "pakomak_metro_extension": 1,
    }
    asset_ids: set[str] = set()
    city_coordinates: set[tuple[float, float]] = set()
    for stem, expected_count in expected_counts.items():
        for suffix in ("csv", "geojson"):
            name = f"{stem}.{suffix}"
            digest = hashlib.sha256((SNAPSHOT / name).read_bytes()).hexdigest()
            if digest != summary["outputs"][name]:
                raise ValueError(f"Snapshot checksum mismatch: {name}")
        payload = json.loads((SNAPSHOT / f"{stem}.geojson").read_text(encoding="utf-8"))
        if payload["type"] != "FeatureCollection" or len(payload["features"]) != expected_count:
            raise ValueError(f"Unexpected feature collection/count: {stem}")
        for feature in payload["features"]:
            asset_id = feature["properties"]["asset_id"]
            if not asset_id or asset_id in asset_ids:
                raise ValueError(f"Empty or duplicate asset ID: {asset_id}")
            asset_ids.add(asset_id)
            geometry = feature["geometry"]
            if geometry["type"] != "Point":
                raise ValueError(f"Expected Point geometry: {asset_id}")
            lon, lat = geometry["coordinates"]
            if not (
                math.isfinite(lon)
                and math.isfinite(lat)
                and -180 <= lon <= 180
                and -90 <= lat <= 90
            ):
                raise ValueError(f"Invalid coordinates: {asset_id}")
            if stem != "pakomak_metro_extension":
                city_coordinates.add((round(lon, 6), round(lat, 6)))
    if len(city_coordinates) != 1583:
        raise ValueError(f"Unexpected City coordinate groups: {len(city_coordinates)}")
    print("PASS: 6 checksums; 1,596 City assets; 1,583 coordinate groups; 1 metro asset")


if __name__ == "__main__":
    main()
