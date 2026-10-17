# Decisions

## D-010 — Confirmed demo scope (2026-09-19)

Skopje in English by September 22; all five core capabilities are required.
Citizen routes support walking and driving and end at the last collection point.

## D-011 — Population access and municipal equity (2026-09-19)

Measure per-material population coverage within 10 minutes on the walking network.
Use the configurable municipal equity policy in CITY_MODE.md; disclose approximations.

## D-012 — Engineering and commit conventions (2026-09-19)

Engineering standards and task acceptance evidence are required for delivery.
Use conventional type-prefixed commit subjects, PR titles, and squash messages.

Append decisions that constrain future work; keep each entry to one line of context and
one line of consequence.

## D-001 — Mobile client, one backend service (2026-09-19)

A mobile client calls FastAPI over HTTPS; the build-free PWA is the reference client
until an installable app is required. Revisit client technology or service splits only
after the validated demo exposes a concrete limitation.

## D-002 — Baselines before transformers (2026-09-19)

Rules and TF-IDF establish measurable value and failure cases before model complexity.

## D-003 — Canonical sites and labels (2026-09-19)

All features share one WGS84 site schema and five labels, preventing UI/model/data
drift. `special_unsupported` is a real model class but not a physical container
material; uncertainty is represented by abstention, never an `unknown` class.

## D-004 — Server-first inference with an on-device path (2026-09-19)

FastAPI initially loads the approved model for quick iteration and consistent results.
Move inference to ONNX on-device only for a measured offline, privacy, latency, or cost
need; Python remains the training environment.

## D-005 — Cache sites and minimize location sharing (2026-09-19)

Clients cache a versioned site snapshot and perform basic nearest-site lookup locally.
Classification never receives location, and backend location inputs are not retained.

## D-006 — Locked Python and multi-stage images (2026-09-19)

Commit `uv.lock`, validate it in CI, and build a locked environment in a Docker builder
stage copied into a minimal runtime stage. Training is separate from image builds.

## D-007 — Synchronous predictions; defer queues (2026-09-19)

Classification stays on the request path. Add producer/consumer infrastructure only
when feedback processing has measured asynchronous work and defined retry/idempotency
behavior.

## D-008 — External vocabulary is not local policy (2026-09-19)

Dataset A labels map explicitly and ambiguous families are held out; Toronto provides
vocabulary only. No foreign disposal stream or unresolved proposal becomes training
ground truth.

## D-009 — Group before splitting (2026-09-19)

All variants of one normalized item stay in one split. Accept imperfect per-class
ratios rather than inflate evaluation through template or item leakage.

## D-013 ? iPhone and free-tier demo delivery (2026-09-19)

Demo on iPhone with HTTPS and Safari Home Screen installation; no hosting exists yet.
Prefer free/free-tier hosting/maps/routing; defer feedback and voting beyond September 22.

## D-014 ? Uncertainty and specialist acceptance (2026-09-19)

Uncertain items require clarification/manual selection; specialist items get guidance.
Only explicitly accepting specialist facilities may be shown; no general-waste fallback.

## D-015 - Pinned geographic preparation outside the runtime (2026-09-20)

Use WorldPop 2025 Global2 modeled counts and dated OSM municipality/network data.
Preserve fractional population, NoData and disconnected demand; retain full turn
restrictions. Commit compact attributed artifacts, pin raw downloads by checksum,
and keep geospatial build dependencies out of the web runtime. Access candidates
are unverified; driving diagnostic graphs cannot provide legal routes.
See [GEOGRAPHY.md](GEOGRAPHY.md) for source choices, provider limits and integration gates.

## D-016 - Evaluated conservative guidance before learned-model expansion (2026-09-20)

Serve versioned policy-scoped rules with a validation-selected abstention threshold;
retain policy holds and disclose missing general-waste evidence and human review.
Require explicit item/condition confirmation and specialist precedence. Pin code,
policy and evaluation hashes; reject ad hoc threshold environment overrides.
Development validation and the reviewed manual subset do not establish independent
five-class quality. Broaden evidence and evaluation before expanding automatic answers.


## 2026-09-20: Bounded citizen routing

T07 uses server-only ORS credentials and explicit coordinate-sharing consent.
Revalidate confirmed items and match exact asset acceptance; unsupported baskets
fail as a whole. Shortlist three nearby sites per item type, then minimize directed
network travel time within that shortlist, ending at the last stop. Use provider
network geometry and expose unverified access gaps rather than inventing connectors.
Keep trips in memory and out of caches/logs. Details and live evidence: [ROUTING.md](ROUTING.md).


## 2026-09-20: T08 population coverage approximation

Use the pinned conservative pedestrian graph and WorldPop weights with both access
costs included in 600 seconds. Split fractional segment connections, preserve direction
and actual OSM junctions, and count each demand weight once. Keep every disconnected
resident in the denominator. Explicitly label unverified connectors, model population
and operation limits. Full material-stream service requires all reviewed types on one
asset; narrower vending profiles cannot broaden acceptance. General waste remains
unavailable. Precompute and reproduce the compact report offline; expose `/city` and
`/api/v1/coverage` without the graph toolchain in production. T09 retains the agreed
50% municipal equity objective and owns upgrades.


## 2026-09-20: bounded offline upgrade scenarios (T09)

Prepare budgets 0..20 and the three reviewed recycling streams against the exact
T08 pedestrian/population baseline. General-waste sites receive hypothetical additive
recycling capacity; the serving acceptance snapshot is never modified. Use exhaustive
search up to 10,000 subsets, otherwise deterministic greedy additions and two exchange
passes under the delegated municipal equity objective. Report local-search limits,
with union-of-all-candidates or exhaustive evidence required for infeasibility claims.
The compact artifact avoids runtime graph dependencies and paid routing calls. Expose
before/after/gain, source locations and remaining municipal shortfalls through one City
action; changes cancel stale requests. Budget cap and floor remain offline parameters.
