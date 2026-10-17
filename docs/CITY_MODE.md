# City Mode requirements

Confirmed by the project owner on 2026-09-19. T08 current coverage is implemented
at `/city`; T09 upgrade recommendations are also available.

For each material, coverage is the percentage of the City's population able to
reach a compatible collection site within a 10-minute walk along the pedestrian
network. Demand locations carry population weights. Report the population source,
reference year, geographic scope, walking-speed assumptions, and network version.

Given N upgrades, select existing general-waste sites to maximize newly covered
population for the chosen material, subject to an equity safeguard. Count each
demand location's population once even when several sites cover it. Keep material
results separate and use asset-specific acceptance rules for compatibility.

Report current coverage, coverage after upgrades, percentage-point improvement,
the recommended sites, and neighborhoods that remain underserved. If an algorithm
is approximate, disclose it and do not claim a proven globally optimal selection.

The initial equity policy uses the 10 City municipalities and a configurable 50%
minimum population coverage per municipality, per material. This is a project
policy default selected under the owner's delegation, not an external standard.
Show smaller-area gaps where population data supports them; municipal averages
must not be presented as proof that every neighborhood has adequate access.

If N upgrades can satisfy every municipal floor, maximize total covered population
subject to those floors. Otherwise prioritize municipal coverage in lexicographic
max-min order (compare coverage percentages sorted from lowest to highest), then
total covered population, then stable site IDs for deterministic ties. Existing
coverage must not decrease. Municipalities with zero modeled population have
undefined coverage and must be reported separately, not assigned artificial 100%.

Distinguish proven infeasibility from an approximate solver finding no qualifying
solution. Report each municipal shortfall and the solver status. Use at most N
distinct candidate sites; report fewer if fewer eligible sites exist or additional
upgrades cannot improve the objective. Do not treat a recommendation as physical
installation approval or remove the existing general-waste service.

Required inputs are a population layer, neighborhood boundaries, compatible-site
data, candidate upgrade sites, and a pedestrian graph with travel times. The shared
infrastructure snapshot supplies the site inputs. The [geographic package](GEOGRAPHY.md)
adds modeled population, municipal boundaries and street topology with an access
audit. Its nearest-segment connectors remain unverified. T08 computes and prominently
labels a population-weighted walking-network approximation that includes both
connector times; no field-verified access is claimed. See the [prepared report and
algorithm](../data/coverage/skopje-v1/README.md).

Missing inputs must be stated explicitly. Any fallback must be labeled as an
approximation with its different metric and limitations; never silently substitute
Euclidean distance or unweighted sample-point coverage.

Citizen routing separately supports walking, driving and scheduled JSP buses, starts from a current or
selected location, and ends at the last collection point. Driving routes do not
change City Mode's walking-accessibility objective.


## T08 implementation decisions

The initial stream metric requires one source asset to explicitly accept all reviewed
item types in the stream: glass packaging; plastic bottles and metal cans; clean paper,
clean cardboard and empty Tetra Pak. These are scoped subsets, not all objects in a
broad material class. Narrow reverse-vending profiles do not qualify as full-stream
service. General waste is unavailable pending acceptance evidence. Closed sites are
excluded; unknown operation is disclosed rather than claimed operational.

Current coverage uses terminal access costs and fractional street splitting with
reverse multi-source shortest paths. The model keeps disconnected demand and counts
each population record once. Results are precomputed, validated and reproduced in CI;
the API loads the compact report without the offline graph dependencies. Source/code
changes require a rebuild; unavailable/stale results return 503, never another metric.
The UI supports per-material comparison and all ten municipal shortfalls. Smaller-area
access and real entrances still need validation; the UI makes no neighborhood-wide
access guarantee. Upgrade results are served separately and retain the same baseline.


## T09 upgrade recommendations

`GET /api/v1/upgrades?material=glass&n=5` serves prepared scenarios for budgets 0..20
and the three reviewed recycling streams. The budget cap (up to 100) and municipal
floor are preparation settings, not request-time computations. General waste itself
is not a supported target. All scenarios retain the exact T08 baseline and source
fingerprint. No live routing calls or additional paid provider are needed.

Candidates must have a potentially operational source waste-container asset explicitly
recorded as mixed municipal waste. Exclude already compatible sites, disconnected
sites and catchments that add no population. Hypothetical upgrades add the full reviewed
stream profile without changing any real acceptance data or removing general waste.
The same directed 600-second catchments include both terminal access costs. Integer
bit sets union demand IDs before summing weights; overlapping sites never double count.

Search enumerates all subsets up to N when there are at most 10,000 combinations.
Larger searches use deterministic greedy additions and at most two single-site exchange
passes, with the same municipal-floor/lexicographic max-min objective. Ties prefer
fewer sites, then stable sorted IDs. The heuristic is not a global optimum certificate.
A floor can be declared infeasible only by exhaustive search or when even the union
of all eligible candidates leaves a municipality below the floor. Other unsuccessful
heuristic searches say `not_found`. Results distinguish solver optimality from equity
feasibility. A larger independently searched budget need not produce a nested plan.

The UI displays a material-colored action heading and a map carousel of selected locations (five by
default). One thin, dark-green outlined star marks the current site's recorded coordinates. Previous/next
arrows and keyboard navigation change the site, counter, reason and OpenStreetMap
link together; controls stop at the first/last site and never auto-advance. The same
map is reused. Empty plans show no map; tile/library/configuration failures preserve
the site details and location link with a retry action.

Reasons describe adding the selected recycling stream to an existing waste site,
using the municipality's current coverage/floor as context when it is below target.
They do not claim a per-site marginal population gain: the prepared API provides
plan-level impacts only. Site order is the prepared plan order, not an impact ranking.
Below each map, a collection-type illustration shows general waste staying in place
and the selected recycling stream being added. It is schematic, not a claim about
equipment type or bin count. Reasons use qualitative municipal context, without
numeric copy. Citywide before/after bars and expandable municipal comparisons use
the actual percentages on a shared zero-to-full-access scale; exact values remain
in accessible chart labels. These comparisons are explicitly for the whole plan,
not the current site. Unknown values stay unavailable, not zero. Solver details and
evidence limits live in the page-level methodology disclosure and clear on reset.
Material/budget changes cancel outstanding requests
and remove stale results. A failed request offers retry with the current choices.
Recommendations remain a planning approximation, not installation approval; operation,
entrances, smaller-neighborhood equity and physical suitability need review.

Reproduce: `uv run --group geo python scripts/prepare_upgrades.py --check`.
Write a revised configuration to a new empty directory with `--out`, `--max-upgrades`
and `--floor`, review it, then publish the artifact. CI reproduces default scenarios.
