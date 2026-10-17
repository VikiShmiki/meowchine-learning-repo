# Quality

## JSP scheduled transit — October 17, 2026

The 24 new backend cases and seven new browser cases pass locally. They cover
direct buses, same-stop transfers, missed connections, calendar exceptions,
overnight/DST service, pickup/direction restrictions, invalid/stale feeds, missing
shapes, disconnected walking, multi-item disposal and short walking-only trips.
Browser checks use the real API/catalog with a synthetic timetable and walking
provider: English/Macedonian at 320/390/1280 px, bus/walk map lines, trip completion,
post-trip reporting, a full facility excluded for another visitor, outage retry,
departure invalidation and switching back to Walking. Narrow screenshots were
visually inspected; this does not establish native-language or physical-phone QA.

Lock validation (including CI's uv 0.12.17), lint, formatting, JavaScript syntax,
19 Node tests, seed/infrastructure/geography checks and exact coverage/upgrade
reproduction pass. `/health` confirms both models on the local app; routing
configuration advertises Walking, Driving and Transit. An opt-in live JSP/ORS
request returned buses 18 and 8 with walking and transfer legs to Karpoš yard.
See [TRANSIT.md](TRANSIT.md) for what that evidence establishes and its limits.

The full Python/browser suite and Linux/container workflow are delivery gates.
Their final revision-specific outcomes are on
[PR #2](https://github.com/VikiShmiki/meowchine-learning-repo/pull/2/checks).
No real feed archive, secret or personal route is committed.

## Trip completion and immediate full-container exclusions — October 17, 2026

The complete `SRA_BROWSER_TESTS=1 pytest` regression run passed locally on Windows.
After the final timing/layout refinements, all **41** focused browser tests in
`test_trip_checkin_browser.py`, `test_community_browser.py`, and
`test_accounts_browser.py` passed with zero skips/failures. This includes 13 new
check-in scenarios across 320/360/1280-pixel layouts and both travel modes.
The 28 community/backend tests and 19 Node tests passed. Lock validation, Ruff lint,
formatting, whitespace checks and seed/infrastructure/geography
validators passed. The system/Macedonian browser regression selection also passed.

Covered: no unsolicited reports; skip/early finish; per-asset full exclusions for
another visitor; expiry/reviewer rejection; pending availability cannot reopen a
problem; remaining basket items; multi-stop completion; visit preservation and
deduplication across replans; a fresh trip resets visits; failed submission retry;
late status responses and failed refresh after a successful write; guest/account
activity; English/Macedonian switching. Mobile and desktop check-in screenshots
were visually inspected. Routes and map tiles use test transports; these results
do not claim physical-device, native-speaker, or live-provider verification.

The initial private-repository CI exposed an existing Docker ignore rule excluding
both bilingual model heads, plus Linux narrow-screen card/navigation layout failures.
The delivery includes explicit Docker model-file exceptions and responsive grid/nav
fixes. The next container run built successfully and exposed a transient connection
reset in the smoke test's startup wait. The wait now retries connection resets and
early HTTP disconnects within its existing deadline; six focused readiness tests
pass, including terminal timeout and malformed-payload failures. Hosted results are
tracked in [CI_STATUS.md](CI_STATUS.md).

## October 17, 2026 private-repository edition

The PowerShell equivalent of `make check` passed locally on Windows with Python
3.11.16 and Node 24.19.0: lock validation, Ruff lint, formatting (167 files),
564 Python tests and 19 Node tests. There were 389 skipped opt-in tests and 11
dependency deprecation warnings. Browser-enabled and container suites were not
run for this documentation-only refresh. Seed, infrastructure and geography
validators passed. The technical-report PDF was rebuilt and all six pages visually
checked. Data, model artifacts and application code are unchanged from source
revision `7bcf9951a88f58e7ee82f98a5849191f5bd2d83a`.

## Historical source-repository verification

Current CI status and reviewer guidance: [CI_STATUS.md](CI_STATUS.md).
Repository-wide formatting is now included in `make check`; audit fixes normalize
the previous nine-file formatting drift. Audit-fix verification of application/test revision `287a62c`: all 897 Python
cases passed with browsers enabled (11 existing dependency warnings), plus 19 Node
cases. Lock, Ruff lint, full formatting, whitespace, credential-pattern scan,
seed/infrastructure/geography validation and coverage/upgrade reproduction pass.
The restarted local app passes smoke requiring both English/Macedonian models.
Real multilingual evaluation retains 54/59 correct with prototype and dataset hashes.
Container execution remains unverified: the Docker daemon is unavailable; native
review, hosted deployment and physical-device verification are still unclaimed.

## English/Macedonian local gate (2026-09-22)

PR #22 pre-merge verification of application/test revision `f635632`: all 890 Python
cases passed with browsers enabled, with 11 dependency warnings; all 19 Node tests
passed. Lock, Ruff lint, formatting of all 14 changed Python files, JavaScript syntax,
whitespace, credential-pattern scan, all data validators, coverage/upgrade reproduction
and live smoke requiring both models passed. CI remains manually disabled. The
whole-repository formatter still reports pre-existing issues in untouched files.
No native review, paid vision, container/hosted or physical-phone pass is claimed.

All 885 Python cases passed with browsers enabled, including the complete 108-case
Macedonian pipeline matrix alongside English. Final copy/encoding and hazard-inflection
corrections were checked with 92 citizen/Macedonian browser cases and 259 backend cases.
The final default gate passes 501 Python cases (389 opt-in browser cases skipped),
19 Node cases, Ruff, formatting, lock and whitespace checks. Seed/infrastructure/
geography validation and coverage/upgrade reproduction pass. Refreshed live smoke
passes with both `--require-minilm` and `--require-macedonian`. Reviewed Macedonian
320/390/1280px screenshots. All provider transports in browser tests are simulated;
no paid vision, Docker, hosted or physical-phone pass is claimed. CI remains paused.
See [language contracts and the retained model errors](LANGUAGES.md).

Apply [ENGINEERING.md](ENGINEERING.md) and the task-specific acceptance criteria in
[DELIVERY_PLAN.md](DELIVERY_PLAN.md). These are requirements, not claims that all
checks and capabilities have already been implemented.

## Temporary CI pause (2026-09-21)

Expanded activity gate (2026-09-22, local verification): all 604 Python tests passed
with browsers enabled (262 browser/system cases; 11 existing dependency warnings).
The 41 account tests also passed independently. All 18 Node tests, lock, Ruff,
changed-file formatting, JS syntax, whitespace, data validators, coverage/upgrade
reproducibility and MiniLM-required live smoke passed. Checked 360/1280px empty,
first/tenth/twenty-fifth activity states, keyboard navigation and material filters.
Backend tests verify lifetime achievements beyond the latest 50 entries, earned
dates, UTC activity counts and replay/general-waste exclusions. Reviewed screenshots
and the refreshed live activity panel. No new paid API calls or synthetic live data.

Badge-outline follow-up: all 18 account browser cases passed, including symbol-to-
border clearance at 360/1280px and locked/earned visual states. The normal check
suite passed again (342 Python; 262 opt-in browser cases skipped), plus 18 Node tests,
lock, lint, formatting, syntax and whitespace. Full-suite evidence above predates
this artwork-only correction; the targeted browser suite checks the final artwork.

Optional-account implementation gate (2026-09-22, local verification): all 594 Python
tests passed with browser tests enabled, including 254 browser/system cases, in
409 seconds (11 existing dependency warnings). All 18 Node tests, lock, Ruff lint,
changed Python-file formatting, JS syntax, whitespace, seed/infrastructure/geography
validation and the running MiniLM-required smoke passed. New evidence covers private
sessions/history, replay-safe drop-offs, first/tenth badge accounting, deletion,
guest compatibility, walking/driving account journeys, failure recovery and the
Clothes-completion regression. Narrow/desktop screenshots were reviewed; live
sign-in/signup was inspected without creating a demo account. Tests use temporary
databases and simulated paid providers. No new paid requests; no test accounts/history
in the live database. CI remains disabled; hosting and phone tests remain deferred.
See [ACCOUNTS.md](ACCOUNTS.md) for security choices and demo-only limitations.

Community PR pre-merge gate (2026-09-22, application/test revision `c606f34`):
all 563 Python cases passed with browser tests enabled, including 244 browser/system
cases; 11 existing dependency warnings. All 18 Node tests, lock, Ruff lint, changed
Python-file formatting, JavaScript syntax, whitespace and staged credential-pattern
checks passed. Seed, pinned infrastructure and geography validators passed; coverage
and upgrade artifacts reproduced. The running app passed the MiniLM-required smoke.
Paid services were simulated in tests; no new paid API calls or live database test
reports. CI remains manually disabled; no hosted CI, Docker or physical-phone pass
is claimed. The workflow now includes community browser tests when re-enabled.

Latest local demo review (2026-09-22): 319 default Python tests passed, 244 browser
cases skipped in that command; 10 focused community browser journeys passed separately.
18 Node tests, Ruff, lock and whitespace checks passed. Dumping is City-only;
walking/driving reporting/rerouting, completed stops and dumping approval were exercised
with simulated providers and isolated data. Screenshots cover 360/1280px desktop
browser viewports, not a physical phone. Hosting/phone testing is now user-deferred.

Local mentor-extension gate (2026-09-22, uncommitted): full opt-in suite passed 561
tests in 333 seconds; 18 Node tests, Ruff and lock check passed. The final cookie,
upload and visual hardening was followed by another passing 27-case community run.
Tests use isolated temporary databases and mocked paid services. No new live API,
hosted, Docker or physical-device success is implied. See [COMMUNITY.md](COMMUNITY.md).

At the user's request, the repository's CI workflow is disabled through GitHub
(`disabled_manually`). Its push/pull-request triggers and both jobs remain defined
in `.github/workflows/ci.yml`; no dummy passing check replaces them. Historical failed
runs remain visible. Branch protection and merge requirements were not changed.

Reason: run 35563102629 could not start quality or container jobs because GitHub
reported failed account payments or an insufficient spending limit. No remote test
result exists for that revision. The workflow will not run while disabled.

PR #19 pre-merge gate (`b376fea` application/test code): 528 Python tests, including
228 browser/system cases, and 18 Node tests passed. Lock, Ruff, whitespace, credential-pattern
scan, data validators and MiniLM-required smoke passed. Earlier same-code coverage/upgrade
reproduction and live 18/18 checks are recorded in [the results](PIPELINE_TEST_RESULTS.md),
alongside the original intermittent phone-photo and map-loading failures. No hosted CI,
Docker/device sign-off or independent accuracy claim is made.

Earlier isolated PR #18 gate: 275 Python tests (including 75 browser/system cases),
14 Node tests, Ruff, lock and whitespace checks pass. Seed/infrastructure/geography
validators and the running app's MiniLM-required smoke pass. The rejected workspace
redesign and unfinished hosting/offline assets are excluded. The exact tested commit
is recorded on PR #18; CI remains paused and Docker/device sign-off remains outstanding.

Historical local evidence for application revision `7b61b011a23c701a7d1dcbd95d1b8b12d91655b1`:

- 244 Python cases passed with browser/system tests enabled; 12 Node cases passed.
- Ruff, lock and whitespace checks passed.
- Infrastructure/geography validators and coverage/upgrade reproduction passed.
- The running local app passed the MiniLM-required deployment smoke.
- Docker build/startup, hosted HTTPS and physical-iPhone checks remain unverified.

These results are local, not a CI pass or blanket approval of future commits.
While paused, contributors should record the tested commit and results on each PR.
After installing the locked dependencies and Playwright Chromium, run:

```powershell
uv lock --check
uv run --all-groups ruff check .
$env:SRA_BROWSER_TESTS = '1'
uv run --all-groups pytest
node --test tests/web_guidance.test.js tests/web_map.test.js
uv run python scripts/validate_infrastructure_snapshot.py
uv run python scripts/validate_geography.py
uv run --group geo python scripts/prepare_coverage.py --check
uv run --group geo python scripts/prepare_upgrades.py --check
```

Require each command to succeed; a later passing command does not erase an earlier
failure. On systems with make, `SRA_BROWSER_TESTS=1 make check` covers the first
five commands; still run the data validators/reproduction checks separately.

Restore once billing is resolved or a suitable runner is configured: GitHub Actions
→ CI → Enable workflow, or `gh workflow enable ci.yml` from this repository. Then
trigger a new push/PR update and verify both quality and container jobs actually run
and pass. A self-hosted runner also needs the workflow's runner labels updated before
re-enabling. No automatic re-enable date is set; review this pause before release.

## Local gate

`make check` runs Ruff and pytest. Tests use synthetic data and must not need network
access. The CI definition runs the same command on Python 3.11, but the GitHub
workflow is temporarily disabled because of account billing. Local passes are not
green CI; see the pause record and restoration instructions in PR #18.

`uv.lock` is committed. `make check` verifies the lock, then delegates lint and tests
to the locked environment. CI installs the pinned uv release and uses
`uv sync --all-groups --locked`.

Test pure domain behavior first, then repository contracts, then a small number of API
flows. Add regression tests for every fixed bug. Geospatial tests should compare with
tolerances and include invalid coordinates, empty results, and deterministic ties.
Dataset tests also enforce the label set, mapping completeness, manual-test review
status, deterministic augmentation, and group isolation.

## System and deployment checks

Install Chromium with `uv run playwright install chromium`, then set
`SRA_BROWSER_TESTS=1` and run `uv run --all-groups pytest`. On PowerShell use
`$env:SRA_BROWSER_TESTS='1'` before the command. CI installs Chromium with its Linux
dependencies and runs all five browser modules explicitly, including community and account journeys.

The [six-category pipeline guide](PIPELINE_TEST_CASES.md) provides text/image examples,
116 additional real-page checks and a bounded opt-in live runner. See the
[2026-09-22 results](PIPELINE_TEST_RESULTS.md), including the retained intermittent
phone-photo failure. Mocked journeys are integration evidence, not vision accuracy.

`tests/test_system_browser.py` runs quick-pick/text/photo journeys in walking/driving modes through
the real page, HTTP endpoints, policy checks, site snapshot and route solver. Only the
external OpenAI and ORS HTTP transports are replaced in a test-only server. It verifies
that recycling stops explicitly accept every confirmed item/stream, then opens
coverage and upgrade results. Separate glass + general journeys in both modes check
recorded general-bin identity and visible unverified-acceptance warnings. Ordinary
test servers override local API credentials with empty values.
These deterministic journeys do not measure recognition quality or real road conditions.

Citizen browser regressions also cover collapsed help/search, keyboard card selection,
direct selection of every stream, general-waste warnings, basket/card synchronization,
capacity failure/retry and preventing unconfirmed picks from being omitted. Backend
regressions require all stream capabilities and explicit general-waste acknowledgement;
hazardous description-based items still block the entire basket.
Layout checks run at 360, 390 and 1280 pixels. Set `SRA_LAYOUT_SCREENSHOTS` to a local
directory to capture those initial layouts; fixture tiles are not real map imagery.

Location-flow regressions at 320/390/1280 px verify neutral method buttons, selection
counts without an implied six-category target, compact selected-point summaries,
change/cancel/clear behavior, hidden redundant controls, keyboard focus and disabled
routing during edits. Late GPS responses are ignored after switching methods or
cancelling; GPS loading state resets correctly. Successful location metadata lives
in the expandable details, while permission/errors remain visible.

Map regressions check the closer initial zoom, in-map legend/control bounds and
non-overlap at those widths, ungrouped discovery, overview/recenter, route-only keys,
and preventing overlay clicks from setting an origin. Pure marker-size tests verify
compact overview dots and prominent selection at every zoom; no sites are merged.

City layout checks cover the shared header, responsive panels, expanded upgrade
results and municipal impact, and unavailable general-waste states at 360/390/1280 px.

Upgrade-carousel tests cover all five sites forward/backward, exact coordinate links,
centered single-star markers, municipality-based reasons, keyboard navigation,
44px controls and responsive bounds at 320/390/1280 px. Zero/one-site scenarios,
material resets, delayed map loading and tile/configuration/library failures with
recovery are checked. Tests use neutral fixture tiles rather than requesting OSM.
Visual-action tests cover glass, plastic/cans and paper/cartons: headings, material
colors, retained general-waste collection and added-stream illustrations stay in sync.
Whole-plan and municipal comparison bars are checked against actual API percentages;
visible explanations contain no figures, accessible labels retain values, and unknown
coverage stays unavailable rather than becoming zero. Evidence moves to the page-level
methodology disclosure, with its solver state cleared when inputs change.

Visual-pass regressions extend map/City checks to 320 and 768 px and verify shared
navigation text, 44px navigation targets, square SVG icons, mobile input sizing,
expanded helper layouts and selected-photo filenames. Screenshots are optional via
`SRA_LAYOUT_SCREENSHOTS`; visual QA covers the compact helper and both full pages.

`python scripts/smoke_deployment.py --url http://127.0.0.1:8000 --require-minilm`
checks startup, model availability/inference, pages/static assets, confirmed guidance, real sites,
coverage and upgrades without provider calls. CI builds the Docker image, starts it
without secrets, then runs this check. It fails on a missing model or broken data bundle.

For an explicitly requested live check, run
`uv run python scripts/smoke_live_pipeline.py --live --url http://127.0.0.1:8000`.
This spends one vision request plus two matrix/two directions requests. It sends only a
blank synthetic image and a fixed public Skopje origin. It verifies the photo contract
and two real text-to-route journeys with asset acceptance checks; it does not establish
real-photo recognition accuracy. Provider quotas and connectivity can cause failures.
Use representative consenting phone photos and a physical iPhone for the final rehearsal.

Record the phone model/iOS and deployed revision for that rehearsal. On HTTPS Safari,
try a glass jar photo, a mixed recyclable photo and a battery photo; verify review and
specialist handling. Confirm two recyclable items and plan both travel modes from a
deliberately selected public point. Check stop details, City coverage and five upgrades.
Finally verify Home Screen installation and the documented offline behavior once T10a
is finished. Record failures and observed latency; desktop browser tests do not substitute
for these device checks.

## Completion criteria

Municipality-chart regressions verify descending rank, source percentage fidelity,
fixed 0–100% scale, report-derived floor, material updates, inline percentage labels,
responsive bounds and unknown/no-population values remaining distinct from zero.

- Behavior and failure modes are tested.
- Inputs, logs, and user-facing uncertainty are safe.
- Random operations use an explicit seed; data/model versions are recorded.
- If a model is exported, its predictions match the server on a fixed golden sample.
- Relevant API/docs and `STATUS.md` reflect the change.
- `make check` passes; the demo still starts from a clean environment.

Do not add a tool, service, abstraction, or dependency without a current use. Prefer
small fixtures and short docs over generated boilerplate.
