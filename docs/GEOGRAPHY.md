# Geographic inputs and service feasibility

T04 prepared inputs; T08 now serves a labeled network coverage approximation at
`/city`. See [the coverage method](../data/coverage/skopje-v1/README.md) and
[the shared package](../data/geography/skopje-v1/README.md) for reproduction commands.

## Source choices

- Population: WorldPop Global2, 2025, constrained 3 arc-second population **counts**,
  R2025A v1. This is an alpha modeled product, not a census count or household map.
  It is nominally 100 m at the equator; pixel width is smaller at Skopje's latitude.
  [Product, attribution and CC BY 4.0 terms](https://hub.worldpop.org/geodata/listing?id=135).
- Network and municipal geometry: OpenStreetMap via the dated Geofabrik Macedonia
  extract, timestamp 2026-09-18T20:21:10Z. Ten explicitly pinned admin-level-7
  relation IDs define the city. [Extract](https://download.geofabrik.de/europe/macedonia.html),
  [ODbL attribution and terms](https://www.openstreetmap.org/copyright).
- Local Pakomak municipal boundaries were compared against OSM. Both have valid
  geometry for the ten municipalities, but borders differ. The comparison report
  records areas, differences and the original file checksum. Its geometry is not
  redistributed because its reuse terms remain unknown. Neither source is claimed
  to be a surveyed legal boundary.

Country source files remain in ignored `data/raw/geography/`. Every download is
checksum-verified. A changed or unavailable source fails explicitly. The compact
prepared package is committed so teammates do not need a new download to inspect it.

## Population contract

Each row retains its raster row/column, municipality ID, positive fractional
population, and representative WGS84 point. Pixels crossing municipal boundaries
are split by area in EPSG:32634. This assumes uniform distribution **within the
pixel**, not within an entire municipality. Portions outside the city are excluded.
Municipal sums must reconcile with an independent city-union clipping calculation.

WorldPop constrains modeled population to settlements. NoData pixels remain masked
and their area is reported; they are not automatically rewritten as zero. The
denominator is the valid **modeled population**. This input alone cannot establish
how many real residents were omitted by the model. Report the product/year and this
limitation in City Mode. Zero modeled population yields undefined municipal
coverage. There is no invented population or straight-line coverage fallback.

## Network contract and access audit

- Keep whole OSM highway ways intersecting a 5 km buffer around the city, their node
  order, complete way tags, barrier/access node tags, and full touching restriction
  relations. Shared OSM node IDs define connections; crossing lines do not automatically
  form junctions. Ways may extend beyond the buffer and the national extract bounds
  remain a limitation for long trips.
- Build separate directed **diagnostic graphs**. Respect specific foot/motorcar access
  over generic access, mode-specific direction tags, reverse one-ways and roundabouts.
  Conservatively exclude conditional/unknown access, construction, private access,
  unqualified barriers, and pedestrian-restriction ways. This is a documented profile,
  not a complete country-specific navigation engine.
- Walking edge time uses actual segment length / 4.8 km/h. It ignores slope, signals
  and individual mobility. Current City coverage uses a 600-second threshold,
  including terminal access connectors; its separate prepared report and method
  are documented in [CITY_MODE.md](CITY_MODE.md).
- Driving diagnostics preserve but **do not enforce turn restrictions**. They are
  explicitly not routing-ready. Citizen trips delegate mode and road restrictions
  to ORS rather than these diagnostic graphs; the provider's handling has not had
  an exhaustive local legality audit. The source package preserves via-way,
  exception and conditional tags and reports boundary-crossing references.
- Audit population and every real City site against the nearest eligible segment
  with a 100 m limit. Store the segment, fractional location, distance and component.
  These are `candidate_unverified` connections: proximity can cross a wall, river or
  private parcel. City coverage labels these connector assumptions as an
  approximation; citizen routes disclose provider network-access gaps. Never call these candidates verified entrances.
- Rows beyond the limit remain in the population denominator with null connection
  references. Smaller components also remain. Do not retain only the largest component.
  Driving travel times and current population coverage are deliberately not fabricated.

## Historical provider feasibility check — September 19, 2026

Checked 2026-09-19. The figures below record that inspection, not current account
quotas, hosting suitability or a deployment recommendation. No hosting account, key
or paid resource was created during that check. Later routing keys/integration
checks do not establish hosted capacity; deployment remains user-deferred.

| Component | Selection | Limits and integration gate |
| --- | --- | --- |
| Citizen routing | openrouteservice Standard; `foot-walking` and `driving-car`, server-side key | Published plan: directions 2,000/day, 40/min; matrix 500/day, 40/min. 50 direction waypoints; matrix 3,500 origin-destination pairs/request, or 25 with dynamic arguments. Confirm actual account quotas before release. |
| City analysis | Local pinned graph and precomputed reachability | Avoid hosted all-population matrices. Validate connectors and graph assumptions before coverage. Runtime should load compact prepared results, not national data or a graph-building toolchain. |
| Map | Leaflet with configurable OSM Standard raster tile URL for a small interactive prototype | Visible OSM attribution, browser HTTP caching and Referer. No bulk download, service-worker tile prefetch or offline map promise. Best-effort service, no SLA. |
| HTTPS app | One Render Free web service, static client served by FastAPI | 512 MB / 0.1 CPU; 750 instance hours/workspace/month. Sleeps after 15 minutes idle, with roughly minute-long wake-up. Ephemeral disk. Bake artifacts into the image; no preparation/training at startup. |

Sources: [ORS current plans](https://account.heigit.org/info/plans),
[ORS request restrictions](https://openrouteservice.org/restrictions/),
[OSM tile policy](https://operations.osmfoundation.org/policies/tiles/),
[Render Free](https://render.com/docs/free),
[Render compute limits](https://render.com/docs/compute-plans).
Plan quotas were inspected in the official plans page's published Standard configuration
(`chunk-7SF2PHKW.js`); they are not a guarantee for a future account.

An unauthenticated Skopje walking request returned HTTP 401 in 0.578 s. This proves
the need for an API key, **not** route correctness or successful-request latency.
T07 subsequently verified authenticated walking/driving itineraries and a known
one-way street with fixed public points; see [ROUTING.md](ROUTING.md). Specialist
items without explicit accepting-facility evidence are rejected; documented
electronics/donation destinations now have separate citizen contracts. Store keys
only in local/server environment configuration. Do not send
precise personal locations during provider feasibility tests; use fixed public test points.

The original 100-trip planning budget applied to direct walking/driving: at most
one matrix and one directions request per trip. It was not a load measurement.
JSP and parking now use additional bounded walking calls; see [ROUTING.md](ROUTING.md),
[TRANSIT.md](TRANSIT.md) and [PARKING.md](PARKING.md) for current per-mode limits.
Personal trip responses are not cached, and full-city hosted matrices are not used.
Recheck actual provider quotas before making any capacity claim.

## Remaining evidence boundaries

Public hosting and physical iPhone checks remain user-deferred. If reopened,
evaluate current plan terms, persistent storage, actual model memory use and
cold/warm latency before selecting a host. The historical Render Free inspection
above is not a capacity sign-off for the current two-encoder application.

Citizen routing delegates road restrictions to ORS and discloses unverified access
gaps; a live one-way spot check is not an exhaustive legality audit. City coverage
uses an explicitly labeled pedestrian-network approximation. Neither replaces
field review of connectors, operating facilities or physical installation sites.
Source reuse and human-review holds remain intact.
