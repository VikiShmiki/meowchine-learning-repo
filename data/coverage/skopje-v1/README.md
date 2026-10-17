# Skopje population coverage v1

Prepared T08 report, served at `/api/v1/coverage` and displayed at `/city`.
This is a **population-weighted walking-network approximation**, not verified access.
The 13 KB report contains no personal location history. It is shared so teammates
can run the app without acquiring data or running a graph preparation job.

## Reproduce and validate

```bash
uv sync --all-groups --locked
uv run --group geo python scripts/prepare_coverage.py --check
# Write a separate candidate artifact for review; existing outputs are not overwritten:
uv run --group geo python scripts/prepare_coverage.py --out data/processed/coverage/new-run
```

`coverage.json` records results, source hashes, code hashes, model/network dates,
acceptance scope and limitations. `manifest.json` hashes exact report bytes.
`.gitattributes` preserves those bytes and pins policy JSON to LF so the serving
snapshot hash is identical on Windows and Linux. A changed policy/site snapshot or covered
implementation rejects the old report; rebuild, review and restart the service.
The generator also verifies the shared geographic package and source checksums.
CI requires full offline reproduction, unit/API tests and browser verification.

## Method and observed results

For each stream, require one asset at a site to explicitly accept every listed
reviewed item type. Do not infer broad stream acceptance from a narrower vending
profile. Exclude closed assets; unknown operation remains explicitly unverified.
General waste has no positively reviewed profile, so its estimate is unavailable.

Split the conservative directed OSM pedestrian graph at all candidate demand/site
fractions. This preserves same-segment paths and actual OSM junctions. Perform
multi-source Dijkstra on reverse edges, seeded by compatible sites' connector times,
then add demand connector time. Count demand iff total time is at most 600 seconds
(a 1e-9 second numerical tolerance handles floating-point boundary error).
Walk speed is 4.8 km/h. Unverified access links up to 100 m are assumed traversable;
they are terminal costs and cannot create shortcuts between separate streets.
No Euclidean radius or unweighted point-count coverage is substituted.

Denominator: 522,420.823288 modeled residents across all ten municipalities.
Unconnected population: 8,619.571328, retained in the denominator. Smaller components
are retained. NoData area is 345.0192 km2, unknown rather than assigned zero residents.
Each demand weight is counted once regardless of overlapping site catchments.

| Stream | Current estimate | Covered modeled residents | Compatible sites |
| --- | --- | --- | --- |
| Glass packaging | 58.137033% | 303,719.965147 | 405 (404 connected) |
| Plastic bottles / metal cans | 34.937949% | 182,523.122778 | 86 |
| Paper / cardboard / Tetra Pak | 5.037202% | 26,315.393350 | 7 |
| General waste | Unavailable | Unavailable | No reviewed acceptance |

The report includes per-municipality denominators, covered population, percentage,
unconnected population and shortfall from the project's 50% floor. Zero-population
coverage is undefined. A municipal average is not a smaller-neighborhood guarantee.
T09 upgrades and after-upgrade results are not implemented in this artifact.

## Sources and limitations

Inputs: [geographic package](../../geography/skopje-v1/README.md) and
[infrastructure snapshot](../../infrastructure/skopje-2026-09-19/README.md).
WorldPop Global2 R2025A v1 constrained alpha product, 2025, University of Southampton,
Bondarenko et al., DOI:10.5258/SOTON/WP00839, CC BY 4.0. Derived by clipping and
area-apportioning boundary cells, then applying the walking-network model.
Network/boundaries: OpenStreetMap contributors, Geofabrik extract timestamp
2026-09-18T20:21:10Z, ODbL 1.0. Preserve source attribution and upstream terms.
Collection-site reuse and policy review flags remain unchanged.

Field-verified entrances, barrier-crossing access paths and operating status are
missing. The profile conservatively excludes uncertain access/foot restrictions;
it ignores slope, signals, individual mobility and temporary conditions. Model
population is not a census, and NoData does not establish zero real residents.
These missing inputs are disclosed in the API and prominently on the City page.
