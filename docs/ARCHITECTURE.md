# Architecture

A mobile client communicates with one FastAPI backend over HTTPS/JSON. The current
build-free mobile page is the starting client; iPhone Home Screen installation is
the demo target. The diagram is the target design, not a list of shipped features.

```text
mobile client / PWA ----HTTPS----> FastAPI ----> evaluated policy rules
        |                              |-------> OpenAI vision (optional, online)
        |                              |-------> frozen MiniLM suggestion (local)
        |                              |-------> infrastructure + City Mode
        `---- cached sites + local nearest search

offline Python training ----------------------> versioned model artifact
```

## Boundaries

- Mobile client / `web/`: screens, permissions, map, cached sites, and local proximity;
  no training or city-planning logic.
- `api.py`: HTTP validation and orchestration.
- `domain.py`: shared labels and immutable value objects.
- `classifier.py`: replaceable baseline/model adapter.
- `object_models.py` / `linear_head.py`: pinned encoders and portable JSON heads with
  development-calibrated abstention; they only
  propose a broad stream after policy rules abstain and cannot establish acceptance.
- `vision.py`: bounded image preprocessing, OpenAI Responses adapter and typed photo
  suggestions; it cannot establish site acceptance or add trip items.
- `geo.py`: deterministic geospatial calculations.
- `routing_models.py`: typed trip contracts; `routing.py`: policy revalidation and
  bounded orchestration; `route_planner.py`: exact asset matching, shortlist and
  directed minimum-time coverage search; `ors.py`: fixed-host provider adapter.
- `repository.py`: external data parsing and validation.
- `infrastructure.py` / `infrastructure_models.py`: strict snapshot ingestion,
  asset-scoped policy matching, coordinate grouping, and deterministic cached payloads.
- `src/smart_recycling/data/`: download, mapping, grouped splitting, validation,
  analysis, and baseline evaluation.
- `src/smart_recycling/geography/`: offline population/boundary/network preparation
  and validation. The `geo` dependency group is not part of the production runtime.
  Versioned artifacts carry provenance and QA; diagnostic graphs are not routing APIs.
- `data/`: local inputs; the explicitly shared infrastructure snapshot is tracked;
  raw/derived classification sources remain untracked pending source-term review.

Classification is synchronous and initially runs in FastAPI. Keep training out of the
request process: an explicit training job produces metrics and a versioned artifact,
and the API loads the evaluated rules plus the development MiniLM head at startup.
The latter is exposed only as a separate development-model suggestion because its
authoritative abstention gate failed. Export to ONNX and move
inference on-device only when offline use, privacy, latency, or cost justifies the
extra mobile integration and parity testing.

The client should download a versioned site snapshot and compute basic nearest-site
results locally. `/classify` never needs coordinates. Server endpoints that receive
location must not log or retain precise coordinates.

`/api/v1/sites` now serves the real City or metro snapshot from validated inputs loaded
once at startup. It preserves separate assets and their acceptance profiles; broad
site categories are only for discovery. The existing `/nearest` remains explicitly
synthetic until item-specific lookup is connected. T06 adds a locally served Leaflet
client, pure snapshot/discovery helpers and a map controller. Cache Storage holds
the City snapshot only; origins remain in memory. Limited search results preserve access
when maps fail. Browser-side straight-line sorting is discovery, not item acceptance
or navigation. `trip.js` adds an in-memory confirmed basket, explicit coordinate
sharing consent, stale-response cancellation and provider route rendering. Trips
are never cached; submitted coordinates pass through the API to ORS without
application retention or logging. See [ROUTING.md](ROUTING.md). No offline page/tile
support is implied. See [MAP.md](MAP.md).

Photo guidance is an optional synchronous backend call. The browser never receives the
OpenAI key. Images are validated, resized and metadata-stripped in memory, then sent with
provider storage disabled. Suggestions use the same item-kind vocabulary as text
guidance and require a separate user confirmation before the trip flow can consume them.
See [PHOTO_GUIDANCE.md](PHOTO_GUIDANCE.md).

Text and photo models are independent. OpenAI vision already returns policy-bounded
item kinds and categories, so photo results are not passed through MiniLM. Typed text
first uses specialist/held and exact-item rules; MiniLM runs only for unresolved broad
text and places its stream suggestion above the manual confirmation choices.

## Current City coverage

`coverage_graph.py` is a pure directed shortest-path engine with split segments and
terminal access costs. `coverage_build.py` prepares scoped material results offline
from the pinned geography and validated asset acceptance. `coverage_models.py` owns
typed totals/metadata; `coverage.py` checks the compact report and source/code identity.
`GET /api/v1/coverage` serves it to the separate `web/city.html` / `city.js` page.
The production image includes data/coverage only; it does not load population rasters,
network topology or geo dependencies. A missing report disables City results explicitly
without breaking citizen guidance. Full offline reproduction is a CI gate. T09 upgrades now use these connection/coverage rules and serve prepared scenarios
through `/api/v1/upgrades`.

## Delivery

`pyproject.toml` declares dependencies and committed `uv.lock` pins the resolved
environment. CI and images use `uv sync --locked`. A multi-stage Dockerfile builds a
non-editable virtual environment, downloads the pinned MiniLM encoder into the image,
then copies it and the checksum-verified head into the runtime image. Model training
never runs during image construction.

Do not put synchronous predictions on a queue. User-approved community reports now
use a separate SQLite store and reviewed status overlays; see [COMMUNITY.md](COMMUNITY.md).
Optional local accounts, sessions and material-only history share that store;
[ACCOUNTS.md](ACCOUNTS.md) defines the self-reported badges and demo limitations.
Public voting and monetary rewards remain deferred. Split services only when independent scaling or
deployment becomes a measured need. Prefer free/free-tier hosting and providers;
validate capacity and routing capabilities before committing to a provider.

Configuration comes from `SRA_*` environment variables and an ignored project-root
`.env` file (existing environment variables take precedence); the project root defaults to
the current working directory. API paths are versioned under `/api/v1`; health is
unversioned. Coordinates use WGS84 decimal degrees.


T09 separates the pure weighted/equitable solver (`upgrades_solver.py`), offline
catchment preparation (`upgrades_build.py`) and typed/static serving (`upgrades.py`).
Shared coverage input loading preserves T08 pedestrian semantics. Runtime artifacts
link to the exact coverage report and source/code fingerprints; deployment includes
`data/upgrades` without the offline graph dependency group. `web/upgrades.js` handles
bounded scenarios and cancellation independently of citizen routing.
