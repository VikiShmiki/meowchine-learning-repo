# Quality and verification

## October 17 rename and maintenance audit

Local verification passed 757 backend tests, 21 Node tests and 46 distinct focused
browser cases (32 account/community and 16 rename/layout cases, with two overlapping).
Two encoder-symlink tests skip on Windows; 440 browser cases are opt-in in the
ordinary backend run. Lock, lint, formatting and deployment smoke with both real
language models passed. All five rebuilt technical-report pages were visually
checked, and 217 documentation links resolved locally.

New regressions cover sensitive validation/early-rejection response headers,
malformed vision envelopes, image preprocessing responsiveness, invalid JSP
calendars, caller-relative launcher paths, reviewer races, stale map responses,
duplicate report retries and saved-language migration. Bilingual layout checks
cover 320, 390 and 1280 px. Provider fixtures establish application behavior only.
Full browser, Linux and Docker results belong to the tested revision in
[GitHub Actions](https://github.com/VikiShmiki/meowchine-learning-repo/actions).

## Earlier merged baseline

The October 17, 2026 integration in
[PR #4](https://github.com/VikiShmiki/meowchine-learning-repo/pull/4), merge `c626c8d`,
passed **737 backend tests, 429 browser cases and 21 Node tests**, plus lock,
lint/formatting, artifact reproduction and Docker smoke. The
[successful run](https://github.com/VikiShmiki/meowchine-learning-repo/actions/runs/39031926188)
loads both actual pinned v3 audit language models. These counts describe that
revision, not every later checkout. [CI_STATUS.md](CI_STATUS.md) defines the merge gate.

## Reproduce locally

Use Python 3.11/3.12, Node 22 and the committed lockfile:

```powershell
uv sync --all-groups --locked
uv lock --check
uv run --all-groups ruff check .
uv run --all-groups ruff format --check .
uv run --all-groups pytest
node --test tests/web_guidance.test.js tests/web_map.test.js
uv run python scripts/validate_seed.py
uv run python scripts/validate_infrastructure_snapshot.py
uv run python scripts/validate_geography.py
uv run --group geo python scripts/prepare_coverage.py --check
uv run --group geo python scripts/prepare_upgrades.py --check
```

`make check` is equivalent to the lock/lint/format/Python/Node portion. Browser
cases opt in separately; install the matching Chromium binary first:

```powershell
uv run playwright install chromium
$env:SRA_BROWSER_TESTS = '1'
uv run --all-groups pytest
```

Linux CI installs Chromium's system dependencies with `--with-deps`. Two symlink
tests may skip on Windows without Developer Mode/privilege; Linux runs them.
Ordinary tests inject encoders/provider transports and disable downloads. Test
servers use temporary databases and never write synthetic accounts/reports to the
running app. Browser screenshots use fixture tiles unless explicitly stated.

Against a running server, check bundled models and data without paid-provider calls:

```powershell
uv run python scripts/smoke_deployment.py --require-minilm --require-macedonian --wait-seconds 120
```

## Coverage and limits

Policy/model tests cover exact acceptance, hazards, mixed items, confirmation,
Latin/Cyrillic Macedonian, optional-model failures, verified encoder/head identity,
calibration and provenance. Photo checks validate output consistency and review
state; they do not measure recognition accuracy from real photographs.

Routing tests cover directed travel, source-asset acceptance, shared stops, known
tiny optima, failures, quotas and stale responses. JSP tests include calendars,
transfers, missed connections and unavailable geometry. Parking tests include
directed return walks, source freshness, one-way driveway entry and access gaps.
Browser cases cover both languages, narrow/desktop layouts, all travel modes,
post-trip reporting, shared full exclusions, accounts and City upgrades.

Coverage/upgrades tests compare tiny graphs to hand-calculated or exhaustive
results and reproduce prepared artifacts. They verify the implemented model, not
physical entrances, installation feasibility or real population access.

Opt-in live scripts consume provider quota and use fixed public test coordinates:
`smoke_live_pipeline.py --live`, `smoke_transit.py --live` and
`smoke_parking.py --live`. Read their contracts first. The October 17 JSP and parking
checks succeeded; details and limitations are in [TRANSIT.md](TRANSIT.md) and
[PARKING.md](PARKING.md). No occupancy, real bus ride or field-access claim follows.

## Evidence policy

Record the tested revision, commands, failures/skips and meaningful limitations.
Keep original source/experiment dates. A historical branch's inability to run a
browser or container is not a current failure if a later integration tested it;
neither is a past pass evidence for changed code. Earlier measured results remain
in [QUALITY_HISTORY.md](QUALITY_HISTORY.md), [ML.md](ML.md) and
[PIPELINE_TEST_RESULTS.md](PIPELINE_TEST_RESULTS.md).

Native Macedonian review and independent user/model evaluation remain outstanding.
Hosting and physical-phone testing are user-deferred. If resumed, record device,
iOS, deployed revision, observed latency and installation/offline behavior. Desktop
viewport checks and Docker smoke do not substitute for those checks.
