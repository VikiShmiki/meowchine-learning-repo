# Skopje public parking snapshot

`parking.json` contains 144 map-derived parking points, version
`skopje-parking-2026-10-16`, with source timestamp `2026-10-16T20:21:21Z`.
It is not an occupancy, reservation, current price or verified-entrance database.

**© OpenStreetMap contributors.** This derived database is available under the
[Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
See [OSM copyright and attribution](https://www.openstreetmap.org/copyright).
The database license applies to this dataset, not automatically to application code.
The complete database is distributed in this directory and through `/api/v1/parking`;
retain attribution and comply with ODbL when redistributing or modifying it.

Source: [Geofabrik's October 16 North Macedonia PBF](https://download.geofabrik.de/europe/macedonia-261016.osm.pbf),
29,819,691 bytes. Raw input SHA-256:

```text
58fff37d1b8266fba263eb921315156f0d0c26b28fd883c4b0a3cfd720ccfa5d
```

Canonical output-record SHA-256 (embedded in the snapshot):

```text
f58f61ebf2c134083b516d5323c50bbd674a77e525b6c4116b330ee62918d516
```

Download the PBF separately; it is not bundled. Reproduce from the repository root:

```bash
uv sync --all-groups --locked
uv run python scripts/prepare_parking.py --pbf /path/to/macedonia-261016.osm.pbf --source-url https://download.geofabrik.de/europe/macedonia-261016.osm.pbf --check
```

Omit `--check` to write the prepared output. For a refresh use the new dated PBF and
its matching source URL, review the diff, run the focused tests and restart the app.
The source timestamp comes from the PBF header; raw/record checksums are recomputed.
Records preserve OSM identities and the driveway way identity where applicable.
The runtime validates schema, region, uniqueness, checksum and freshness (90 days).

Extraction requires explicit `access=yes|permissive` and conservative vehicle/foot
access. Nodes use their mapped point; areas require a public driveway entry crossing.
See [the feature audit](../../../docs/PARKING.md) for exclusions, one-way handling,
planning bounds and uncertainty. No capacity tag is interpreted as free spaces.
