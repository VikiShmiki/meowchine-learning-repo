# Skopje geographic inputs v1

Shared inputs for the ten-municipality Skopje scope. These are modeled population,
community boundaries and street data, not computed coverage or navigation results.
See [methodology and limitations](../../../docs/GEOGRAPHY.md).

## Reproduce

From the repository root (Python 3.11 or 3.12):

```sh
uv sync --all-groups --locked
uv run --group geo python scripts/prepare_geography.py
uv run python scripts/validate_geography.py --directory data/processed/geography/skopje-v1
```

Downloads use dated/versioned URLs from `sources.json`, bounded retries and SHA-256
verification. Raw downloads are about 33 MB combined. An existing output directory
must be empty: use `--out data/processed/geography/my-new-run` to compare a rerun.
Preparation does not overwrite existing snapshots or require a routing API key.

To verify the committed package without network access:

```sh
uv run python scripts/validate_geography.py
```

## Files and contracts

- `sources.json`: pinned URLs, checksums, attribution, municipality IDs and parameters.
- `prepared/manifest.json`: input links, dependency versions, artifact hashes and sizes.
- `prepared/municipalities.geojson`: OSM geometry and source relation IDs.
- `prepared/population.json.gz`: fractional modeled demand with municipality IDs and
  unverified walking connection candidates. Disconnected population is retained.
- `prepared/network.json.gz`: nodes, highway ways, tags, full touching restriction
  relations. Driving diagnostic topology is **not routing-ready**.
- `prepared/site_access.json.gz`: walking/driving connection candidates keyed by the
  existing infrastructure `site_id`; metro sites excluded. These do not assert acceptance.
- `prepared/qa.json`: population reconciliation, topology and access-gap report.
- `boundary_comparison.json`: one-time comparison with the owner's local Pakomak
  boundaries; geometry withheld because reuse terms are unknown. This comparison is
  not a required input to reproduction.

Coordinates are WGS84 longitude/latitude; distances and clipping areas use UTM 34N.
The 100 m snap limit is an audit threshold, not a coverage metric. Network candidates
must not be treated as proof of an unobstructed/legal access path. The website does
not load these development artifacts yet.

## Attribution and distribution

Population: WorldPop / University of Southampton, Bondarenko et al.,
DOI:10.5258/SOTON/WP00839, Global2 R2025A v1, 2025, CC BY 4.0.
Changes: clipped/apportioned to the selected municipalities; representative points
and connection candidates added. Preserve model/year/alpha-product limitations.

Boundaries and network: © OpenStreetMap contributors, ODbL 1.0, downloaded from
Geofabrik. Derived OSM databases retain ODbL obligations; keep layers and their source
notices identifiable when distributing the package. Population attribution is also
required for the combined derived demand layer. Full source terms are linked in
`sources.json`. Existing collection-site records retain their original source/reuse
flags; adding an OSM access candidate does not resolve the site's source terms.

## Measured snapshot

Prepared 2026-09-20: 35,716 demand locations, 522,420.8233 modeled residents,
198,114 OSM nodes, 25,541 ways and 2,248 restriction relations. Municipal polygons
form one union without interior gaps or overlaps above the 1 square metre tolerance.
The committed artifact payload is about 5.8 MB; the national raw inputs remain untracked.

The access audit retains 8,619.5713 modeled residents beyond the 100 m connection limit
and 6,835.9707 on smaller walking components. One site lacks a walking candidate and
two lack driving candidates. See `qa.json` for site IDs, per-municipality totals,
component counts and the 345.0192 square km population NoData mask. These are input
quality findings, not percentages of population covered by recycling infrastructure.
