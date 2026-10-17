# Najdi Frli — recycling guidance for Skopje

Najdi Frli helps residents identify an item, confirm its condition and reach a
suitable collection point. City Mode shows modeled walking access and compares
where existing general-waste sites could add recycling. Both pages support
**English and Macedonian**.

[Technical report](docs/technical-report.pdf) · [Report source](docs/technical-report.tex) ·
[Current status](STATUS.md) · [Private repository](https://github.com/VikiShmiki/meowchine-learning-repo)

## Run locally

Install [Python 3.11 or 3.12](https://www.python.org/downloads/) and
[uv](https://docs.astral.sh/uv/), then run from the repository root:

```bash
uv sync --all-groups --locked
uv run python scripts/run_local.py
```

Open [citizen guidance](http://127.0.0.1:8000/),
[City Mode](http://127.0.0.1:8000/city) or [API documentation](http://127.0.0.1:8000/docs).
First launch can download two pinned MiniLM encoders; later launches reuse the
cache. The loopback launcher creates a private reviewer key in ignored `runtime/`.

Copy `.env.example` to ignored `.env` and set `SRA_ORS_API_KEY` for actual routes,
including bus walking connections and parking journeys. Optional photo suggestions
also need server-side `OPENAI_API_KEY`; see [photo setup](docs/PHOTO_GUIDANCE.md).
Restart after changing configuration. Without these keys, manual/text guidance,
site discovery and City Mode still work. Never commit credentials.

## What works

| Capability | Behavior and limits |
| --- | --- |
| Item guidance | Six citizen flows: glass, plastic/metal, paper/cartons, ordinary residual waste, electronics and wearable-clothes donation. Reviewed policy and explicit condition confirmation control acceptance. [Policy](docs/DISPOSAL_POLICY.md) |
| Map and trips | Real versioned collection assets, manual/map/device origin and up to six confirmed items. Direct walking and driving use ORS network directions. Proximity browsing is straight-line. [Map](docs/MAP.md), [routing](docs/ROUTING.md) |
| JSP bus | Scheduled bus journeys with walking connections, line numbers, boarding/exit stops and bounded transfer search. This is timetable planning, not live arrivals. [JSP setup and limits](docs/TRANSIT.md) |
| Parking | Optional **Driving → Park and walk to drop-offs** uses 144 mapped public parking points and includes return-to-car walks between drop-offs. Space availability is unknown; the final return to the car is excluded. [Parking](docs/PARKING.md) |
| Container check-in | After a trip, optionally report visited containers without photos. Full reports immediately exclude that asset for everyone for up to 12 hours, subject to reviewer rejection. Skipping sends nothing. [Community](docs/COMMUNITY.md) |
| City coverage and upgrades | Population-weighted ten-minute pedestrian-network coverage and material/municipality upgrade scenarios. Connectors and physical installation feasibility remain unverified. [City method](docs/CITY_MODE.md) |
| Optional accounts | Material-only activity and six self-reported badges; guests can use guidance and routes. No location history or verified recycling claim. [Account limits](docs/ACCOUNTS.md) |

This is a Skopje prototype, not a universal disposal authority. Source records do
not establish current operation, access or item acceptance. The authority chain is
**local policy and exact-item confirmation → source-recorded asset acceptance → route**.
General-waste navigation requires acknowledgment of unverified acceptance and is
never a fallback for unknown or hazardous items.

## Models and evidence

The app serves hash-pinned `development-v3-audit` English/Macedonian MiniLM
suggestion heads, with separate development tuning/calibration splits and
confidence/similarity abstention. The six object labels are not site-acceptance
categories. Suggestions order manual review choices; they never authorize disposal.
Photo analysis is a separate optional service with the same confirmation boundary.

On the authored development test's supported inputs that actually reached ML,
English accepted 18/30 and Macedonian accepted 14/42, all correct among those
accepted inputs. These are small, previously inspected development sets with
correlated spelling variants. Historical manual replay still has unsupported-input
suggestions. Native review and a fresh independent user test remain outstanding.
[ML.md](docs/ML.md) records current results, errors and reproduction; older v1/v2
measurements remain clearly historical and are not evidence for current accuracy.

## Development and checks

The build-free client in `web/` calls one FastAPI service in
`src/smart_recycling/`. Training and geographic preparation run offline. Docker
bundles verified model files and compact serving datasets. The repository URL,
Python import path `smart_recycling` and `SRA_*` configuration names remain stable
after the product rename.

`make check` runs lock validation, Ruff, Python tests and Node tests. It requires
Node 22 and `make`; these equivalents also work in PowerShell:

```powershell
uv lock --check
uv run --all-groups ruff check .
uv run --all-groups ruff format --check .
uv run --all-groups pytest
node --test tests/web_guidance.test.js tests/web_map.test.js
```

For browser checks, run `uv run playwright install chromium`, set
`$env:SRA_BROWSER_TESTS='1'` and rerun pytest. Snapshot/reproduction commands and
test boundaries are in [QUALITY.md](docs/QUALITY.md). GitHub Actions runs quality
and Docker smoke gates; [CI_STATUS.md](docs/CI_STATUS.md) links merged evidence.
Hosted deployment and physical-phone verification remain user-deferred.

| Document | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md), [STATUS.md](STATUS.md) | Contributor entry point and current state |
| [PROJECT_BRIEF.md](PROJECT_BRIEF.md), [docs/PRODUCT.md](docs/PRODUCT.md) | Product scope and boundaries |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/API.md](docs/API.md) | Components and HTTP contracts |
| [docs/DATA.md](docs/DATA.md), [docs/LANGUAGES.md](docs/LANGUAGES.md) | Provenance, language behavior and evidence |
| [STATUS_HISTORY.md](STATUS_HISTORY.md), [docs/QUALITY_HISTORY.md](docs/QUALITY_HISTORY.md) | Dated implementation and validation history |

Rebuild the report with `tectonic --outdir docs docs/technical-report.tex` or
XeLaTeX using the same source/output directory. It uses Arial when available and
DejaVu Sans otherwise.

## Data and reuse

The City source snapshot has 1,596 assets grouped into 1,583 sites. Citizen routing
adds documented electronics/clothing destinations; source dates and acceptance
limits are retained. Seed coordinates are synthetic fixtures and never evidence of
real coverage. Policy and model development data retain review and licensing holds.

This repository began a new Git history from the
[source project](https://github.com/AI-Tech-Summit-Filip-Avramchev/meowchine-learning-repo).
Original provenance, experiment dates and third-party notices are preserved. No
project-code license has been selected. Third-party code and data retain their own
terms; see [DATA.md](docs/DATA.md) and each dataset README.
