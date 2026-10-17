# Architecture

Najdi Frli uses a build-free browser client and one FastAPI service. The current
client supports narrow/desktop layouts; installation and an offline app shell are
not implemented. Production HTTPS/device verification remains user-deferred.

```text
browser client ── JSON ──> FastAPI ──> policy + verified local suggestion models
       │                    ├──────> optional OpenAI photo suggestions
       │                    ├──────> ORS network routing + JSP timetable
       │                    ├──────> versioned sites / parking / City reports
       │                    └──────> SQLite reports / accounts / quotas
       └── cached site snapshot + local proximity discovery

offline training / geographic preparation ──> versioned serving artifacts
```

## Component boundaries

- `web/`: guidance, permissions, in-memory trip state, maps, site cache and local
  proximity discovery. Coordinates are shared only through an explicit route action.
- `api.py`: typed HTTP validation, orchestration, configuration and error handling.
- `guidance.py`, `classifier.py` and versioned `data/policy/` inputs: local item/condition rules and
  confirmation. `object_models.py` / `linear_head.py` load pinned development JSON
  heads after verified encoder loading; optional failures affect only that language.
- `vision.py`: bounded image preprocessing, Responses adapter and typed suggestions.
  It does not choose sites or add confirmed items to a trip.
- `infrastructure.py` / `infrastructure_models.py`: source validation, coordinate
  grouping, per-asset acceptance and deterministic versioned snapshots.
- `routing.py`, `routing_models.py`, `route_planner.py`: basket revalidation,
  exclusions, bounded nearby candidates and directed coverage search. `ors.py`
  provides actual network matrices and directions through a fixed-host adapter.
- `transit.py` / `transit_feed.py`: bounded scheduled JSP journey search and
  validated runtime timetable cache. `parking.py` / `parking_data.py`: mapped
  parking, car/walk search and licensed snapshot integrity/freshness.
- `coverage_graph.py`, `coverage_build.py`, `upgrades_solver.py`, `upgrades_build.py`:
  pure/offline population-weighted preparation. Runtime loaders validate compact
  coverage/upgrade reports without population rasters or graph-building dependencies.
- Community/account modules: one SQLite store for moderated reports, usage counters,
  optional sessions and material-only activity. This is a single-instance design.
- `src/smart_recycling/data/`, `src/smart_recycling/geography/`, `scripts/`: offline
  acquisition, training, evaluation and reproducible artifact preparation.

## Authority and data flow

Text policy runs before optional learned fallback. The current v3 audit heads use
development-selected temperature and abstention gates; their outputs only order
manual clarification choices. Photo output is independently checked for policy
consistency and needs user confirmation. Neither model establishes site acceptance.
Trips revalidate the confirmed basket against exact source-asset capabilities and
current community exclusions before paid provider work.

`/api/v1/sites` serves real City, citizen and separate metro snapshots. The citizen
client browses the citizen snapshot and computes straight-line proximity locally.
The legacy `/api/v1/nearest` endpoint remains explicitly synthetic and is unused by
that client. Discovery distance is not a network route or acceptance decision.

Walking/direct driving use ORS; transit adds published JSP schedules and verified
walking; parking adds drive/walk/return-to-car legs. Trips end at the final drop-off.
Responses are no-store and origins stay in page memory. Provider coordinates are
not application location history or logs. Access gaps, source dates and unknown
operation/availability remain visible. See [ROUTING.md](ROUTING.md),
[TRANSIT.md](TRANSIT.md), [PARKING.md](PARKING.md) and [MAP.md](MAP.md).

Photo bytes are validated, resized and metadata-stripped in memory, then sent to
the configured provider with storage disabled. The application does not store
them. Separate moderated dumping photos have their own documented retention.
Account activity contains material types and completion times, not routes or sites.
See [PHOTO_GUIDANCE.md](PHOTO_GUIDANCE.md), [COMMUNITY.md](COMMUNITY.md) and
[ACCOUNTS.md](ACCOUNTS.md).

## Runtime and delivery

`pyproject.toml` declares dependencies and `uv.lock` pins them. The multi-stage
Dockerfile builds a non-editable environment and bundles verified pinned encoders,
JSON heads and serving datasets for a non-root runtime. It does not train models
or build geographic reports. CI validates the image and both models with a bounded
startup/deployment smoke. Missing optional reports/models fail explicitly while
unrelated guidance remains available.

Configuration comes from `SRA_*` variables and ignored project-root `.env`; existing
environment variables take precedence. The root defaults to the working directory.
The product/distribution is Najdi Frli, while Python imports remain `smart_recycling`
and API paths remain `/api/v1`; `/health` is unversioned. Coordinates use WGS84.

Keep one service until measured independent scaling justifies a split. Training,
data acquisition and expensive geographic computation stay outside requests.
Multiple runtime replicas need coordinated storage and concurrency/usage controls;
the current SQLite implementation does not establish that capability.
