# API v1

JSON errors use FastAPI's standard validation response. Text is limited to 200
characters; coordinates must be valid WGS84 values.

## Container observations

`POST /api/v1/container-reports` accepts an existing `asset_id` and `condition`
(`available`, `full`, `inaccessible`, or `damaged`). It returns a pending report;
`full` immediately excludes that individual asset from everyone's new routes,
without an image or account. Full reports expire 12 hours after submission.
Unreviewed availability cannot reopen a shared problem or a source-closed asset.

`GET /api/v1/container-statuses` returns `statuses` and a revision `version`, with
`Cache-Control: no-store`. Each overlay contains `condition`, `reported_at`,
`expires`, and `source`: `community_report` for an unreviewed shared full report,
`reviewed_community` for an approved observation, or `your_report` for another
personal pending problem. No overlay means unknown, not confirmed available.
Existing routes recheck this revision; browser clients refresh every 30 seconds
and offer explicit replanning. [Community contracts](COMMUNITY.md) cover moderation,
rate limits, expiry, and the optional post-trip check-in.

## `GET /health`

Returns service state, rule version, real City `site_count` (1,583), real
`asset_count` (1,596), `legacy_seed_site_count` (4), and
`nearest_data_source: "synthetic"`. `text_suggestion_model` reports the loaded MiniLM
suggestion version or `unavailable`. Counts describe published records, not verified
operating facilities.

## `GET /api/v1/sites?scope=city`

Downloads the real infrastructure snapshot without accepting a user's location.
`scope` is `city` (default), `citizen` (City plus documented electronics/clothes destinations),
or `metro_extension` (one separate asset); invalid values
return 422. Each response has `schema_version: 1`, `synthetic: false`, dataset/policy
versions, as-of date, input checksums, source evidence, counts, and `sites`.

Each site contains its stable source `id`, representative coordinates rounded to
six decimals, broad `materials`, and separate `assets`. Each asset retains its exact
coordinates, source site/record identity, original material codes, collection mode,
municipality, provenance, dated telemetry when present, operating status, reuse
flags, and a matched acceptance profile or `null`.

`categories_are_discovery_only: true`: category unions support map filtering, not
item-level routing. Acceptance is scoped per asset. General-waste assets currently
have no positively reviewed item-acceptance profile; specialist facilities are not
invented. Unknown operation must not be displayed as open/working.

Responses are deterministic and include a strong SHA-256 `ETag` and
`Cache-Control: private, max-age=300, must-revalidate`. Send `If-None-Match` on refresh;
a matching strong/weak tag or `*` returns 304 with no body. Data or policy changes
invalidate the ETag. Clients may explicitly store the last downloaded snapshot for
offline browsing, retaining its as-of date; cacheability does not imply live data.

The citizen map uses the citizen scope (1,590 sites / 1,603 assets), ETag revalidation
and a separate Cache Storage key. City coverage/upgrades keep the unchanged City scope.
Material filtering, list search and straight-line sorting happen in the browser;
the starting point is not submitted to this endpoint. Metro records remain separate.

Citizen discovery additionally accepts `materials: ["clothes"]`; its assets retain the
canonical `special_unsupported` category with exact `wearable_clothes` acceptance.
`TripStream.material: "clothes"` requires `condition_confirmed: true` (clean, washed,
wearable donation); exact text/photo review uses `manual_kind: "wearable_clothes"`.
It never falls back to electronics or general-waste destinations. See
[clothing inventory and source limitations](CLOTHING_DONATIONS.md).

Inputs are loaded and checked at startup. Corrupt/missing data, unknown capabilities,
duplicate IDs, inconsistent coordinate/site grouping, scope mismatches, and invalid
coordinates fail with an actionable error; there is no silent seed fallback.

## `POST /api/v1/classify`

Request: `{"text":"wine bottle"}`

The response retains `category`, `confidence`, `abstained` and `model_version`
(`policy-rules-v3`) and adds `policy_version`, `confidence_kind`, `status`, `message`,
`item_kind`, `clarification_question`, `choices`, `evidence_ids`, `contact_url`,
`phone`, `facility_ids`, `routing_available`, `suggested_category`,
`suggestion_score`, and `suggestion_model_version`.

`ordinary_residual` identifies the bounded household-tissue/nappy subset and returns
`category: general`; it is never the fallback for an unrecognised item. `electronics`
retains `category: special_unsupported` but can now be confirmed for an explicitly
accepting collection centre. Its `facility_ids` contains the documented Karpos yard,
not Nula Otpad's office or pickup address. `small_electronics` covers phones, chargers,
cables and earbuds, with both Karpos and East Gate Mall in `facility_ids`.
Larger devices cannot be overridden into that smaller subset. `routing_available: false` still means that
classification itself is not a computed route; use the separate trips endpoint.

| Status | Client action |
| --- | --- |
| `clarify` | Ask the question and offer the returned specific item choices |
| `confirm_condition` | Confirm item-specific conditions: clean/empty packaging, ordinary household residuals, or safe household devices |
| `ready_for_site_matching` | Item details confirmed; may be added to a trip |
| `specialist` | Show guidance and any evidenced operator contact, never a general-waste route |
| `held` | Acceptance is unverified; ask for more detail or operator confirmation |

Descriptions matching multiple recyclable item kinds return `held`, including
when `manual_kind` and `condition_confirmed` are supplied. Describe and confirm each
item separately before adding it to a trip; selecting one kind cannot silently
discard another recognized recyclable from the original description.

Confirm a choice with, for example:

```json
{"text":"a jar","manual_kind":"empty_glass_packaging","condition_confirmed":true}
```

`manual_kind` is one of the returned choice IDs, not a broad category.
`condition_confirmed` must be a JSON boolean; `true` requires a manual selection.
Whitespace-only descriptions and invalid selections return 422. Specialist signals
and explicitly unsupported conditions cannot be overridden by a recycling selection.
An uncertain response returns `category: null`; scores are heuristic, not calibrated
probabilities. Manual selections use `confidence_kind: manual_selection` and score 0.
When reviewed rules cannot identify an exact item form, the optional frozen MiniLM
fallback can populate the three `suggestion_*` fields and order matching exact-item
choices first. Its score is an uncalibrated closed-set logistic output, not
`confidence`; the response remains `status: clarify` and `abstained: true`. The model
cannot output `general`, and specialist/held rules take precedence. Set
`SRA_MINILM_SUGGESTIONS=false` to disable it.
Classification responses have `routing_available: false` and no facility IDs:
classification alone does not establish a route. Use `/api/v1/routing` for provider
configuration and `/api/v1/trips` for authoritative matching and routing.
An operator contact is not a verified facility. Classification requires no coordinates.

## `POST /api/v1/photo-suggestions`

Accepts one JPEG, PNG or WebP image up to 8 MB as the raw request body with its matching
`Content-Type`. The server reads it through a bounded in-memory stream, corrects EXIF
orientation, limits the image to 1,280 pixels, strips metadata by re-encoding in memory
and sends it to the configured OpenAI vision model. Images are not written to
application storage. Responses and errors use `Cache-Control: no-store`.

The response contains up to six `items`, each with `description`, policy-bounded
`item_kind`, derived `category` or null, `visible_condition`, `status` (`candidate`,
`specialist` or `needs_review`) and a short `reason`. It also returns `model_version`,
`policy_version`, `requires_user_confirmation: true` and a user message. No confidence
probability or facility acceptance is claimed. Candidates must pass through
`POST /api/v1/classify` with explicit user confirmation before entering a trip.
The description and reason are checked for conflicting item kinds, excluded forms
and condition signals, even when the model claims the item appears empty/clean.
`needs_review` always returns `category: null` and `item_kind: "other"`; clients
must request manual clarification rather than preselect a confirmable item.
Specialist hazards retain priority.

Missing credentials return 503; rejected credentials/provider outages return 503;
rate limits return 429; invalid/unsupported images return 413, 415 or 422; malformed
provider output returns 502. The rest of the app remains usable. See
[PHOTO_GUIDANCE.md](PHOTO_GUIDANCE.md).

## `POST /api/v1/nearest`

Request:

```json
{"material":"glass","latitude":41.996,"longitude":21.431}
```

Response includes `site` (`id`, `name`, coordinates, materials) and straight-line
`distance_m` and `synthetic: true`. This legacy endpoint still uses the four seed
points; it is not the new infrastructure lookup or a walking route.
`special_unsupported` is rejected because it
needs guidance rather than an ordinary collection site; a missing material returns
404. The citizen page no longer calls this endpoint; once site snapshots are cached, clients
should perform basic nearest-site lookup locally. Precise coordinates must not be
written to application logs or feedback records.

Planned demo endpoint: candidate upgrades. Current coverage is described below. Clarification/guidance is part of classification above.
Specialist routing requires item-specific acceptance evidence, not the broad
`special_unsupported` label. The existing nearest endpoint remains as documented
until a reviewed contract replaces it. No verified facility means guidance and an
explicit unavailable result, never general-waste fallback. Feedback/voting are
deferred beyond the current edition. Add endpoints with schemas, privacy decisions, and
contract tests.


## `GET /api/v1/routing`

Returns `configured`, `max_items: 6`, `modes` and `provider`; never the API key.
Configured means a nonempty key is present, not that provider quota/auth is valid.

## `POST /api/v1/trips`

```json
{
  "origin": {"latitude": 41.9965, "longitude": 21.4314},
  "mode": "walking",
  "items": [{"text": "glass jar", "manual_kind": "empty_glass_packaging", "condition_confirmed": true}],
  "share_coordinates": true
}
```

Mode is `walking`, `driving` or `transit`; 1-6 items, strict JSON booleans and finite WGS84
coordinates are required. Extra request fields are rejected. The entire basket is
validated before provider use. Description-based items are revalidated against
item-level policy and asset acceptance. Known-waste cards can instead submit stream
entries, and both entry shapes can share a basket:

Electronics streams accept optional `small_only: true` for phones, chargers, cables
and earbuds. Omitted/false means generic household electronics (Karpos only).
`small_only` on another material is invalid. Description/photo review uses the
`small_electronics` kind; both documented locations accept this narrower subset.
Route stops include `arrival_notes`; East Gate identifies the mall entrance and
asks the user to locate the collection point at the information desk.

```json
[
  {"material": "glass", "condition_confirmed": true},
  {"material": "general", "condition_confirmed": true, "accept_unverified": true}
]
```

Stream materials are `glass`, `plastic_metal`, `paper_tetrapak`, and `general`.
Recycling streams require one asset accepting every supported subtype in the stream.
General waste requires explicit `accept_unverified: true` and matches only recorded
mixed-municipal-waste drop-off containers, excluding closed/unavailable assets. It
is navigation to a recorded bin, not verified item acceptance. Missing acknowledgement
returns 422 with code `unverified_acceptance`. Hazardous/held description-based items
still block the entire basket; general waste is never an automatic fallback.

Returns provider/profile, network `distance_m` / `duration_s`, GeoJSON `geometry`,
ordered `stops` with assigned item kinds, source asset IDs, acceptance limits and
`network_access_gap_m`; `unverified_materials: ["general"]` marks general-waste stops
(otherwise empty). General-waste warnings do not invent acceptance limits or profiles.
Also returns dataset/policy versions, source date, candidate count,
optimizer description, warnings, attribution and `ends_at_last_stop: true`.
See [ROUTING.md](ROUTING.md) for shortlist, snap, privacy and optimization limits.

Application failures use `{"detail":{"code":"...","message":"..."}}`:
422 for missing consent, unconfirmed items, missing compatible sites or unreachable
routes; 429 for process/provider quota; 503 for missing credentials, provider auth,
unavailability or timeouts; 502 for invalid provider data. Schema errors use the
standard FastAPI 422 shape. All trip responses use `Cache-Control: no-store`.


For `transit`, optional `departure_at` is an ISO timestamp with timezone offset;
blank means now plus one minute. The server accepts up to seven days ahead within
available service calendars. Response `provider` is `jsp_gtfs_openrouteservice`,
`profile` is `jsp-scheduled-bus+foot-walking`, and top-level `geometry` is null.
Use separate `legs` with mode `walking|bus`, `from_name`, `to_name`, longitude-first
`from_point`/`to_point`, departure/arrival timestamps, duration/distance, nullable
geometry and destination `site_id`. Bus legs also include `line`, `headsign` and
`stop_count`. Missing shape distance is zero and disclosed; it is not a zero-length ride.
Totals include scheduled waits and intermediate drop-off allowances. Metadata includes
`departure_at`, `arrival_at`, `transit_feed_version`, `transit_fetched_at`,
`transit_service_end` and `transit_source`. Road-mode fields retain their meanings.

Transit errors use the same no-store `{detail: {code, message}}` envelope:
`transit_unavailable` (503), `transit_departure`, `transit_expired`,
`transit_no_service`, `transit_no_route` or `transit_connection` (422).
Existing provider errors/quotas apply to walking connections. `/api/v1/routing`
advertises all three modes; `configured` describes the ORS key, not feed health.
See [TRANSIT.md](TRANSIT.md) for search/freshness limits.

## Parking-assisted driving

For `POST /api/v1/trips`, optional `include_parking: true` is accepted only with
`mode: "driving"`. It is a strict JSON boolean, default false; the direct-driving
contract remains unchanged when omitted. Existing consent and item validation apply.

Parking responses use `profile: "driving-car+foot-walking"`. Top-level `geometry`
contains the car path; total `duration_s` / `distance_m` include driving and walking.
`driving_duration_s` and `walking_duration_s` break down time. `parking` is ordered
with `stops`, with one entry per drop-off: `site_id`, `parking_id`, name, coordinates,
`access`, `fee` / `opening_hours` (source strings or `"unknown"`), `point_kind` (`mapped_point` or
`driveway_crossing`), OSM `source_url`, `drive_access_gap_m`, and always
`availability: "unknown"`. Each `walk_to` and optional `walk_back` contains network
duration/distance, nullable LineString `geometry`, and start/end access gaps. A null
walk geometry means coincident network points, not verified zero physical distance.
`walk_back` exists at intermediate stops only. The trip ends at the last drop-off,
leaving the car at its last parking location; the final return is not included.
`parking_dataset_version` and `parking_source_as_of` disclose source version/age.

Parking-specific errors: `parking_unavailable` (503), `parking_no_route` and
`parking_connection` (422). Provider errors and no-store semantics still apply.
There is no direct-driving fallback. [PARKING.md](PARKING.md) defines bounds and
timing; source fees/hours are not verified live prices/opening decisions.

`GET /api/v1/parking` accepts no location and returns the full licensed snapshot:
schema/version, source timestamp/URL/SHA-256, canonical record checksum, ODbL
license/attribution and `places`. It uses `Cache-Control: public, max-age=3600`.
Missing, corrupt or stale data returns 503. Parking information is not an occupancy
or reservation service.

## `GET /api/v1/coverage`

Returns the prepared `CoverageReport` used by `/city`. No location input or provider
key is needed. `method` is `population_weighted_walking_network_approximation`;
threshold is 600 seconds. Metadata includes population product/year, network timestamp,
site/policy versions, source/code hashes, speed, access limit, NoData area, limitations
and attribution. The report is not a verified access or live availability claim.

Each material includes its explicit item-acceptance scope, compatible/connected site
counts, City population/covered population/percentage and the same metrics for every
municipality. Unconnected residents stay in denominators. Municipal `underserved`
and `shortfall_pp` use the reported 50% project floor. Zero-population percentages
are null; unavailable general-waste coverage and shortfalls are null rather than zero.

Responses have a content ETag and `public, max-age=300, must-revalidate`; matching
`If-None-Match` supports 304. Missing, corrupt or stale reports return 503 with an
explicit unavailable message while citizen guidance remains usable. Runtime loading
checks artifact/code/serving-snapshot hashes and report consistency. Full geography
reproduction runs offline in CI. Set `SRA_COVERAGE_PATH` to select a prepared directory;
rebuild and restart after changing inputs. No request-time graph computation occurs.


### GET /api/v1/upgrades

Query: `material=glass|plastic_metal|paper_tetrapak`, `n=0..20` (default 5).
Returns schema version, prepared maximum budget, exact coverage artifact SHA256,
limitations and a plan: current/after population percentages, gain in percentage points,
candidate count, selected sites, municipal before/after/shortfalls, `solver`
(`optimal` or `heuristic`) and `floor_status` (`met`, `proven_infeasible`, `not_found`).
Unsupported materials or budgets return 422. Missing, corrupt or stale preparation
returns 503 without changing the citizen app or substituting a different metric.
Scenarios are offline prepared; requests perform no graph search or provider calls.

## Response languages

English/Macedonian copy is negotiated through Accept-Language. Classification also
accepts optional language en/mk, overriding the header. Canonical item kinds, IDs,
policy and routing semantics are unchanged. Photo descriptions/reasons follow the
request language. See [language contracts](LANGUAGES.md).
