# Skopje upgrade scenarios, version 1

Prepared budgets 0..20 for glass packaging, plastic bottles/metal cans and clean
paper/cardboard/Tetra Pak. The 50% municipal floor uses the objective documented
in ../../../docs/CITY_MODE.md. These are hypothetical additive upgrades of existing
general-waste sites, not changes to real acceptance or installation approvals.

The report links to the exact T08 coverage artifact, which carries the pinned
WorldPop/OSM/operator sources, attribution and geographic QA. All T08 population,
pedestrian direction, terminal access and uncertainty assumptions remain applicable.

- `upgrades.json`: scenarios, selected source IDs/locations, municipal changes,
  optimality and equity-feasibility status, limitations and code/input fingerprints.
- `manifest.json`: exact report byte checksum. JSON is preserved as bytes in Git.

Reproduce with `uv run --group geo python scripts/prepare_upgrades.py --check`.
For a revised budget cap or floor, write a new empty `--out` directory with
`--max-upgrades` and `--floor`; review results before publishing. Production only
loads these small scenarios; it does not import the graph toolchain or call ORS.

Five upgrades: glass 58.137033% -> 59.336719%; plastic/metal 34.937949% -> 36.876599%;
paper 5.037202% -> 11.435812%. The floor remains infeasible under this candidate/access
model. Heuristic selections are not claimed globally optimal. Municipal percentages
can conceal smaller neighborhood gaps; physical access and suitability need review.
