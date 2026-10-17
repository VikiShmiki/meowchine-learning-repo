# Goodsort — recycling guidance for Skopje

**Project edition: October 17, 2026** · [Private repository](https://github.com/VikiShmiki/meowchine-learning-repo)

Goodsort helps a resident identify an item, confirm its condition, and find a suitable collection point. It also gives city planners a population-weighted view of walking access and suggests where existing general-waste sites could be upgraded. The citizen and City pages work in **English and Macedonian**.

**[Watch the demo](docs/assets/demo-app-video.mp4) · [Read the technical report source](docs/technical-report.tex) · [Read the technical report](docs/technical-report.pdf)**

> **Scope and evidence.** This is a Skopje hackathon prototype, not a universal disposal authority. Site acceptance comes from a versioned local snapshot; operation and access can change. The app asks for item/condition confirmation and shows uncertainty rather than silently guessing. The technical report explains the methods, measurements, and limits.

**ML update:** The app now uses development-v3-audit suggestion heads with abstention,
portable weights and repaired data splits. [Measured results and limitations](docs/ML.md)
supersede the historical model section of the PDF; native and independent user
validation remain outstanding.

## Why Goodsort matters

Knowing that an item is recyclable is not enough if the nearby container does not
accept it or the resident cannot reach a suitable collection point. Goodsort brings
item guidance, explicit acceptance checks and multi-item trip planning into one
flow. Its English and Macedonian interface makes that flow available in both
languages, while uncertain or hazardous items are held for confirmation instead of
being sent to an arbitrary bin.

For city planners, the same infrastructure data becomes a view of who can reach a
compatible site within a modeled ten-minute walk, broken down by material and
municipality. Hypothetical upgrades make access gaps concrete enough to compare
priorities. These are practical decision aids, not measured changes in recycling
behavior or proof that a proposed site is suitable without field review.

## Try it locally

Install [Python 3.11 or 3.12](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/), then run from the repository root:

```bash
uv sync --all-groups --locked
uv run python scripts/run_local_demo.py
```

Open **<http://127.0.0.1:8000/>** for citizen guidance, **<http://127.0.0.1:8000/city>** for City Mode, or **<http://127.0.0.1:8000/docs>** for the HTTP API. First launch can download two pinned MiniLM encoders; later launches reuse the cache. The local launcher creates a private reviewer key under the ignored `runtime/` directory.

For a quick tour, change language in the header, select a material or describe an item, confirm its condition, add it to a trip, and choose a map or manual starting point. A **live walking/driving route needs an OpenRouteService key**. Copy `.env.example` to the ignored `.env`, set `SRA_ORS_API_KEY`, then restart the server. Without it, guidance, site discovery, and City Mode remain available, but the app cannot draw a real route. Optional photo suggestions similarly need a server-side `OPENAI_API_KEY`; see [photo setup and privacy](docs/PHOTO_GUIDANCE.md). Do not commit either key.

The [demo video](docs/assets/demo-app-video.mp4) shows the product; it is a walkthrough, not evidence that external providers or collection sites are currently available. The video is checked into the repository so a reviewer can inspect it without local files.

## What the prototype does

| Capability | How it works | Evidence and limits |
| --- | --- | --- |
| Bilingual guidance | English/Macedonian UI and API copy; language-selected, six-class frozen MiniLM suggestion heads, with policy-based item recognition | [Language contract and five-seed evaluation](docs/LANGUAGES.md). Suggestions are not authoritative disposal decisions. |
| Six citizen journeys | Glass; plastic/metal; paper/cartons; ordinary residual waste; electronics; wearable-clothes donation | [Policy and evidence boundaries](docs/GENERAL_AND_ELECTRONICS.md), [routing](docs/ROUTING.md). The model's **six object labels are not six site-acceptance categories**. |
| Collection map and trips | 1,596 source assets grouped into 1,583 City sites; asset-specific acceptance; up to six confirmed trip items; OpenRouteService walking/driving matrix and directions | [Map provenance](docs/MAP.md), [routing algorithm](docs/ROUTING.md). Browsing proximity is straight-line; actual trips require the provider. |
| City coverage and upgrades | Modeled population within a 10-minute pedestrian-network walk of a compatible site; material-specific, municipality-aware upgrade scenarios | [Coverage](data/coverage/skopje-v1/README.md), [City method](docs/CITY_MODE.md). Access connectors and physical installation feasibility are unverified. |
| Community and activity | Moderated site-condition reports, reviewer panel, optional account, material-only history and self-reported badges | [Community controls](docs/COMMUNITY.md), [account and privacy limits](docs/ACCOUNTS.md). |

The authority chain is deliberate: **reviewed local policy and exact-item confirmation → source-recorded asset acceptance → route**. The six-class MiniLM heads suggest objects/streams only when rules abstain; optional photo analysis proposes item kinds; neither can authorize a bin or bypass specialist/unsafe-item handling. Electronics and clothes have explicit training labels, but their routing still depends on policy and destination evidence.

## Five-seed model results

Seeds **42–46** compare three methods per language on the same fixed, grouped
six-class dataset. Scores are macro-F1 mean ± **sample standard deviation** over
the five runs; the manual set contains 59 supported examples per language.

| Method | English manual | English grouped test | Macedonian manual | Macedonian grouped test |
| --- | ---: | ---: | ---: | ---: |
| TF-IDF + logistic | 0.548 ± 0.000 | 0.455 ± 0.000 | 0.467 ± 0.000 | 0.434 ± 0.000 |
| Frozen MiniLM + logistic | **0.696 ± 0.000** | 0.505 ± 0.000 | **0.507 ± 0.000** | **0.552 ± 0.000** |
| Multilingual MiniLM LoRA | 0.644 ± 0.044 | 0.237 ± 0.083 | 0.459 ± 0.033 | 0.252 ± 0.034 |

The frozen heads were selected for both language pages. Zero SD here reflects the
fixed split and deterministic fits, **not** certainty about real-world quality.
Clothing has only 11 training examples, and Macedonian translations still need
native review. The full protocol, probe results, timings and limitations are in
[ML.md](docs/ML.md); these development scores do not authorize disposal decisions.

## Architecture and repository guide

The build-free client in `web/` calls one FastAPI service in `src/smart_recycling/`. The service loads validated policy, model and infrastructure artifacts at startup; offline scripts in `scripts/` and `src/smart_recycling/data/` prepare and evaluate data separately. City coverage and upgrade scenarios are precomputed from versioned geography inputs and served as compact reports. The [technical report](docs/technical-report.pdf) contains an architecture diagram, algorithms, evidence table, and the agent-assisted development workflow.

| Where | Start here for |
| --- | --- |
| [AGENTS.md](AGENTS.md) and [STATUS.md](STATUS.md) | Task routing, current state, blockers, and working rules for human/AI contributors |
| [docs/](docs/) | Product, architecture, policy, routing, language, data, quality, privacy and decision contracts |
| [data/](data/) | Versioned local policy, infrastructure, geography, coverage and model-evaluation evidence |
| [tests/](tests/) | Domain, API, data-contract, bilingual and browser/system regressions |
| [STATUS_HISTORY.md](STATUS_HISTORY.md) | Earlier milestones without growing the active status context |

`AGENTS.md` intentionally points a contributor to the **one relevant document** instead of copying all project knowledge into every task. `STATUS.md` is the short live ledger; stable decisions and detailed evidence stay in `docs/`. The report explains how this reduced stale context during the agentic build.

The report is authored in LaTeX and its PDF is rebuilt for this edition. Rebuild it with
`tectonic --outdir docs docs/technical-report.tex` (or XeLaTeX with the same
source and output directory); the document uses Arial where available and DejaVu
Sans otherwise.

## Reproduce the checks

`make check` requires Node 22 and `make`; on Windows, the equivalent commands below work in PowerShell after `uv sync --all-groups --locked`:

```powershell
uv lock --check
uv run --all-groups ruff check .
uv run --all-groups ruff format --check .
uv run --all-groups pytest
node --test tests/web_guidance.test.js tests/web_map.test.js
```

For the browser/system suite, install Chromium with `uv run playwright install chromium`, set `$env:SRA_BROWSER_TESTS='1'`, and rerun pytest. The deterministic tests replace external provider transports; they do not establish paid-vision accuracy or live road availability. [QUALITY.md](docs/QUALITY.md) records commit-specific local results, dataset validators, and reproduction commands. [LANGUAGES.md](docs/LANGUAGES.md) explains the paired Macedonian fixtures and model-evaluation holds.

This repository includes GitHub Actions for quality and container checks. Its run status is independent of the source repository’s historical account restriction; see [CI_STATUS.md](docs/CI_STATUS.md). Hosted service, physical-phone and native-speaker sign-off remain outstanding.

## Data and responsible use

The five internal targets are `glass`, `plastic_metal`, `paper_tetrapak`, `general`, and `special_unsupported`; abstention is separate. Dataset A's text queries and Dataset B's Toronto vocabulary are mapped or held for review, not treated as proof of Skopje acceptance. The evaluated rules answer 36 of 59 source-supported manual queries (34 correct among answers); 41 further queries are held. The provisional Macedonian set scores 54/59 on those inherited supported labels, with native wording review still needed. See the [classification evidence](data/classifier/README.md), [policy review](docs/DISPOSAL_POLICY.md), and [language evidence](docs/LANGUAGES.md) before interpreting these numbers.

This edition starts a new Git history from [the source project](https://github.com/AI-Tech-Summit-Filip-Avramchev/meowchine-learning-repo). Original data provenance, experiment dates, historical evidence, and third-party notices are retained. No project-code license has been selected by the owner. Third-party code and data keep their own terms; the repository does not grant extra reuse rights. See [DATA.md](docs/DATA.md) for provenance and exclusions.
