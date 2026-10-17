# Historical delivery log

Archived on 2026-09-22. Entries below describe their original point in time;
current priorities and verification are in [STATUS.md](STATUS.md).

# Status

Updated: 2026-09-22 | Phase: English/Macedonian implemented and locally verified

## Active Task — City community map layout (2026-09-22)

User requested community reports above the method/sources section and an always-visible
map in both English and Macedonian. The shared City layout now uses a normal section
and initializes the community map on page load; methods remain collapsible below it.
Validation: 501 default Python tests, 19 Node tests and 5 focused browser journeys
pass; lock, Ruff, changed-file formatting, JS syntax and whitespace checks pass.
Reviewed English desktop and Macedonian mobile screenshots with live map tiles.
User authorized committing, pushing and merging this verified layout change on
`fix/city-community-map`. CI remains paused; the checks above are local results.
Local provider configuration was restored from the original checkout into ignored
`.env`; the live routing provider successfully returned a test walking route.

## Completed — English and Macedonian (2026-09-22)

Latest user direction: start the current app, support English/Macedonian throughout
its interface and model workflows, and add Macedonian counterparts to English tests.
Codex owns this local implementation on `feat/macedonian-support`, based on the
completed accounts checkout. The app runs at http://127.0.0.1:8000.

Implemented persistent bidirectional UI switching, bilingual policy/route/photo
validation, a pinned multilingual suggestion model, Macedonian photo instructions,
and Cyrillic location search. User data and canonical item/site identifiers stay
unchanged. Added 68 paired policy fixtures (Cyrillic and Latin), all 100 paired manual
queries, and the full 108-case Macedonian pipeline matrix. All 885 tests passed with
browsers enabled. After the final copy/encoding and hazard-inflection corrections,
92 citizen/Macedonian browser cases and 259 focused backend cases passed. The final
default check passes 501 tests (389 opt-in browser cases skipped), plus 19 Node tests,
Ruff, formatting, lock and whitespace checks. Seed/infrastructure/geography validation
and coverage/upgrade reproduction pass. Both learned models pass the refreshed live
smoke. Screenshots reviewed at 320/390/1280 px. User authorized committing and
pushing this implementation on `feat/macedonian-support`, then requested a merge
after verification. Current `main` is incorporated; its accounts squash has the
identical accounts tree used as this feature base. Before push, lock validation, Ruff lint, 501 Python tests and 19 Node
tests passed (389 browser cases skipped); all 14 changed Python files pass format
checks. A fresh whole-repository format check also reports pre-existing issues in
untouched files. CI remains paused as previously directed.
The real multilingual report scores 54/59 source-supported labels (91.5%, macro-F1
0.922); all errors and original evidence holds are retained. No native review,
live paid vision, hosted/container or physical-phone pass is claimed.
See [language contracts and evaluation](docs/LANGUAGES.md).

Fresh PR #22 merge gate (application/test revision `f635632`): all 890 Python
cases passed with browsers enabled (11 dependency warnings), plus 19 Node tests.
Lock, Ruff lint, all 14 changed Python-file formatting checks, JavaScript syntax,
whitespace and credential-pattern checks passed. Seed/infrastructure/geography
validation, coverage and upgrade reproduction, and live smoke requiring both
language models passed. User authorized the normal merge; CI remains manually
paused. Native review, container/hosted and physical-phone checks remain unclaimed.

## Delivery wrap-up (2026-09-21)

User authorized merging the current kept version through PR #18. The rejected full-site
workspace redesign is not included. The PR now matches application revision `e6bbec9`
for active web, backend and tests, excluding unfinished hosting/PWA/offline assets.
Includes direct selection of all four waste types, glass/general recorded-bin routes,
correct location editing states, dashed walking/solid driving, material-colored stops,
and the five-location City carousel with visual collection actions and whole-plan gains.
Coverage mathematics and policy limitations remain unchanged.

Fresh isolated-PR validation: 275 Python tests including all 75 browser/system cases,
14 Node tests, Ruff, lock and whitespace checks pass. Seed, infrastructure and geography
validators pass. The unchanged pinned coverage/upgrade artifacts reproduced successfully
in the development checkout; the local running app passes MiniLM-required smoke.
External routing/vision transports and automated tiles are mocked in system tests.
CI stays disabled for billing; no green-CI claim, check override or branch-protection
change. Commit-specific local evidence is recorded on the PR before the normal merge attempt.
Docker, hosted HTTPS and physical-iPhone sign-off remain outstanding.
The earlier CI-blocker paragraphs below describe historical delivery holds; the user's
new merge request authorizes a normal merge while CI is paused, not bypassing checks.

User-requested temporary CI pause: GitHub reports the CI workflow as
`disabled_manually`. Workflow code/jobs, branch protection and merge rules are
unchanged. New pushes will not run CI; historical billing failures remain visible.
This does not mean CI passed. Local evidence is tied to application revision
`7b61b011a23c701a7d1dcbd95d1b8b12d91655b1`: 244 Python and 12 Node tests, lint/lock,
infrastructure/geography validation, coverage/upgrade reproduction and the running
app's MiniLM-required smoke passed. Container, hosted and physical-device checks
remain outstanding. Restoration and per-PR local checks are in docs/QUALITY.md.

PR #18 combines the system-test foundation with the completed route-first Recycle,
map readability, shared City styling and municipal coverage chart. The isolated
`test/system-pipeline` worktree excludes unfinished Render/PWA scaffolding; the
original development checkout and its pending T10 files remain untouched.

GitHub run 35557406013 did not start either quality or container tests. Both jobs
report failed account payments or an insufficient spending limit. An organization
owner must resolve Billing & plans, then rerun CI. Do not bypass checks or merge on
local evidence alone. Container build/run and physical-iPhone sign-off remain open.

Fresh isolated-PR validation: 244 Python cases (including browser/system tests),
12 Node cases, Ruff, lock and whitespace checks pass. Used the equivalent Makefile
commands because make is unavailable on this Windows host. Infrastructure/geography
validation and coverage reproduction pass; the running app's MiniLM-required smoke
also passes. No new live-provider requests were made for this wrap-up.

## Route-first citizen redesign (2026-09-21)

City section 02 chart: ranked horizontal municipality coverage bars on a fixed
0–100% scale, exact percentage labels, green/amber floor status and a dashed project
floor marker sourced from the report. Material selection updates the chart; null
and zero-population values remain unavailable, distinct from real zero coverage.
The original accessible table is available under Exact figures. No chart dependency
or model/data changes. Added numeric fidelity, ordering, zero/unknown handling,
material switching and responsive chart checks; visual review at 320/1280 px.
Validation: 244 Python cases and 12 Node tests pass; Ruff, lock and whitespace
checks pass. The updated chart is verified in the live City preview.

Whole-site visual pass: replaced waste illustrations with a consistent two-tone SVG
set; both pages use matching arrow-free navigation with 44px targets. Replaced text
glyphs in helper/add/remove controls, improved card labels and mobile input sizes,
stacked narrow/tablet layouts, aligned material colours between cards and map, and
fixed cramped map legends/City unavailable metrics. Photo selection now has a full
width camera control and safe text-only filename. Removed duplicate site headings
and moved coordinates into source details; acceptance/access warnings remain.
Reviewed overview, helper, route/site details and expanded City recommendations.
Regression coverage now includes 320/390/768/1280 px navigation/icons/helpers and
320/360/390/768/1280 px map/City layouts. A photo journey test now waits for its
first confirmation before editing the next item (editing cancels pending work).
Validation: 243 Python cases and 12 Node tests pass; Ruff, lock, whitespace and
MiniLM-required local deployment smoke pass. Live Recycle and saved responsive
screenshots were visually reviewed; physical-device sign-off remains outstanding.

City visual consistency follow-up: uses Recycle's Goodsort header, shared citizen
palette/type/controls, numbered sections and rounded panels. Coverage metrics lead;
municipalities and upgrade planning share a responsive dashboard. Removed idle copy
and moved source/method details, access-gap lists and impact tables into disclosures.
Visible estimate/unverified-access and unsupported-material notices remain. No data,
coverage calculation or upgrade solver changes. Added 360/390/1280 px checks for
initial/expanded/unavailable states and updated the deployment page assertion.
Verified live City overview and recommendations; 233 Python cases, 12 Node tests,
Ruff, lock, whitespace and MiniLM-required local deployment smoke pass.

Copy reduction follow-up: removed redundant card subtitles, selection prompts,
AI teaser caption, idle basket/origin/trip copy, legend instructions and repeated
footer. Dataset totals and map-report link live in existing disclosures. Retained
material labels, item-condition confirmation, provider-sharing notice, acceptance
warnings and actionable error states. Essential status text is darker and readable;
no blanket hiding of errors. Added initial-state regressions at all three widths.
Verified live layout; 230 Python cases, 12 Node tests, Ruff, lock and whitespace
checks pass after the copy reduction.

Map readability follow-up: start at zoom 16 in central Skopje; use a compact in-map
legend, overview/recenter buttons, viewport counts, scale, white-edged site marks and
individual sites at their recorded coordinates (numbered groups removed after user
feedback). Dots shrink at overview zoom and grow on hover/selection; mixed-material
sites have their own legend colour. Starting points and route
stops are distinct, with a white route outline and a route-specific key. OSM provider
and attribution are unchanged; tile colours are softened in CSS only. No automatic
location request, dependency, data/acceptance inference, or backend change was added.

Map validation: 230 Python tests (40 browser/system cases), 12 Node tests, Ruff,
lock, seed/geography checks and MiniLM-required local deployment smoke pass. Added
overlay bounds/non-overlap checks at 360/390/1280 px, real Enter/Space activation,
individual-dot sizing, overview/recenter and origin-selection safeguards. Live desktop
OSM tiles were visually inspected; phone-sized Chromium checks are not physical iPhone
sign-off. The final closer zoom was also rechecked at all three widths.

Ungrouped-marker follow-up: all 230 Python cases, 12 Node tests, Ruff and lock
checks pass again. Removed grouping logic and key, retained each site's coordinates,
and verified the live individual-dot map. Marker sizing now varies with zoom rather
than replacing nearby sites with counts; route stop numbers remain unchanged.

Visual follow-up: replaced promotional headings/taglines with neutral labels, redrew
the plastic bottle/can, replaced circle glyphs with centered vector icons, and aligned
the desktop columns with matching panel boundaries. Responsive browser checks assert
equal panel/header alignment and centered icons as well as selected-state visibility.

Whole-page follow-up: applied the same citizen styling to expanded AI/photo panels,
map search/legend/controls, source disclosures and numbered route stops. Route lines
and badges share the forest-green palette. Site acceptance and operating-status notes
remain visible; provenance is expandable. Added mobile/desktop expanded-panel layout
regressions. City Mode and backend behavior remain unchanged.

Implemented the user's new priority: a shorter, visual citizen page with four material
cards, optional text/photo help, and a compact walking/driving trip panel. Exact item
subtypes and a single explicit condition confirmation remain required; quick picks use
the existing server policy, not AI guesses. General waste offers guidance only because
destinations remain unverified. Search, data sources and long route details are expandable.
City Mode and backend/model behavior are unchanged. Added citizen-only styling and
inline vector icons; no new dependencies or externally hosted assets.

Quick picks support atomic confirmation/retry, basket synchronization, six-item limits,
keyboard use and blocking routes while selected items remain unconfirmed. Verified
360/390/1280 px layouts and the live local preview. All 225 Python cases pass, including
35 browser/system cases; all 11 Node cases, Ruff, lock, seed/geography validation and
the running app's MiniLM-required deployment smoke pass. System tests cover quick-pick,
text and photo journeys in both modes using simulated external provider transports.
This is local evidence, not physical-iPhone or hosted-deployment sign-off.

## System-test follow-up (2026-09-21)

Added complete browser journeys for text/photo inputs and walking/driving, keeping real
application HTTP endpoints, policy, site data and route solver; only provider transports
are simulated. Checks confirm every selected stop accepts its assigned items and exercise
City coverage/upgrades. Added a deployment smoke script and a separate opt-in live smoke
script, plus a Docker build/start/smoke CI job. Test servers isolate local API keys.
Excluded local secrets/logs/results from the Docker build context and corrected the local
Render scaffold's health path to the existing `/health`. Reformatted the unfinished
app-cache preparation script to resolve its two lint errors; offline installation remains
unfinished.

Observed: full suite passes 217 Python cases including all 27 browser/system cases, plus
11 JavaScript cases; Ruff, lock and whitespace checks pass. Live vision
handled a blank synthetic image; live walking/driving each returned two compatible stops.
The running local app passes the deployment smoke with MiniLM required, including actual
inference that remains suggestion-only. Docker Desktop's
WSL backend fails startup (`Service ntp errored out`), so no local container build/run pass
is claimed; the new CI job still needs a remote run. Real-phone photos, physical iPhone
rehearsal and hosted HTTPS checks remain outstanding. Render access remains pending.

## Completed accounts task (historical)

Latest user direction: wrap up, commit and push the complete accounts/activity/badges
work on `feat/accounts-and-badges`. No PR or merge requested for this delivery.

Completed badge correction: removed crossing
flourishes and inset the central symbols, retaining the existing palette/shapes.
All 18 account browser cases pass with a new symbol-to-border clearance assertion
at both sizes; screenshots and the live badge gallery checked. The normal check
suite passes (342 Python, 262 browser cases skipped), plus 18 Node cases, lint,
lock, syntax, formatting and whitespace. No account behavior or stored data changed.
Codex owns this local implementation.
Keep guest routing, the existing layout and provider limits; do not start hosting,
phone testing or another PR/merge without a new request.

Implemented locally: optional username/password accounts on both pages, expiring
opaque sessions, material/date-only history, six custom vector recycling/donation
badges, and password-confirmed account deletion. Overview/Badges/History tabs add
milestone progress, a 28-day UTC activity view, lifetime material collection and
filtered history. Earned dates/progress include entries beyond the latest 50.
Guests retain the existing flows;
general-only drop-offs do not earn badges. Failed saves preserve the basket and
offer retry or explicit unsaved completion. Also fixed Clothes quick-pick completion
not clearing its basket entry. No email/recovery/MFA or verified-recycling claim.
Fresh expanded-activity regression: all 604 Python tests passed with browsers enabled
(262 browser/system cases), with 11 existing dependency warnings. All 18 Node tests,
lock, Ruff, changed-file format, JS syntax, whitespace, data validators, coverage/
upgrade reproducibility and MiniLM-required live smoke passed. The 41 focused account
tests passed separately. Reviewed narrow/desktop empty and earned badge screenshots
and verified the expanded live My activity panel after restarting the local app.
Browser skill connection failed; isolated Playwright supplied journey/screenshots
and the available browser-control fallback verified the live dialog. No paid calls;
no synthetic accounts/history were added to the live DB. Test accounts use temporary DBs.
CI definition includes account journeys but stays disabled. Work is on
`feat/accounts-and-badges`; no new PR/merge. See [account contracts,
privacy, security and limitations](docs/ACCOUNTS.md).

Latest user direction (2026-09-22): package the completed community reporting and
logo changes into a PR and merge after fresh verification. Accounts/badges, hosting
and physical-phone testing remain deferred. CI remains manually paused; record
local evidence without claiming hosted checks passed or bypassing merge rules.

Fresh pre-merge gate for `c606f34`: 563 Python cases (all 244 browser/system cases
enabled), 18 Node cases, lock/lint/format/whitespace/credential checks, data validators,
coverage/upgrade reproduction and MiniLM-required localhost smoke passed. No paid
provider calls; test reports stayed in isolated databases. The new community browser
module is included in the still-disabled CI workflow. See docs/QUALITY.md.

Latest user direction: keep dumping reports only in City coverage and do a local
desktop demo review of container reporting/rerouting and dumping moderation.
Hosting and physical-phone testing are explicitly deferred; do not pursue them.
This does not imply those checks passed. Accounts/badges remain deferred.
Local review completed: dumping appears only in City coverage, container reporting
remains on Recycle, walking/driving reroutes preserve the basket, and completed stops
clear finished items. Dumping map/manual entry, private photo, review approval and
City display pass. Visual review fixed a cramped condition dropdown and redundant
reroute button on narrow screens. Latest checks: 319 default Python tests passed
(244 opt-in cases skipped there), 10 focused browser journeys passed separately,
18 Node tests, Ruff, lock and whitespace checks passed. Paid providers were simulated;
no synthetic reports were added to the running demo database. Broader browser suite
was not rerun for this small follow-up; previous full run remains recorded below.

Mentor follow-up, owned by Codex: implement persistent provider allowances,
container reports/review and asset-scoped rerouting, then moderated dumping reports.
User approved the staged plan. Accounts and badges remain optional/deferred.
Existing logo alignment is preserved. PR/merge is now authorized above.
Implementation is now available locally: signed anonymous visitors, SQLite reports and
atomic quotas, reviewed/global versus pending/personal container overlays with expiry,
walking/driving rerouting, explicit origin changes and completed-stop item removal,
dumping map/submissions/private photos and a key-protected reviewer page.
Full opt-in regression passed 561 tests (11 existing dependency warnings); after final
upload/cookie/UI hardening, 27 community tests passed again. 18 Node tests, Ruff and
lock check passed. Browser visual check corrected the report-layer checkbox sizing.
No paid provider calls were made for this implementation. Hosted CI remains paused;
physical iPhone, public deployment and production authentication are not claimed.
Local launcher preserves the user's existing env file and writes only an ignored
reviewer key; see [setup, defaults, privacy and limits](docs/COMMUNITY.md).

Logo alignment follow-up: grouped the wordmark and dot and optically centered their
visible lettering against the unchanged circle/arrow on Recycle and City coverage.
Verified screenshots at 360, 390 and 1280px; all nine focused browser/layout cases
passed. Default Python suite, 18 Node tests, Ruff and lock checks passed; full opt-in
browser suite not rerun for this CSS-only visual change. CI pause remains unchanged.

Delivery wrap-up: PR #19 packages the six-category implementation and pipeline tests.
Fresh pre-merge verification of `b376fea`: 528 Python cases, including 228 browser/system
cases, and 18 Node tests passed. Lock, Ruff, whitespace/credential-pattern scans, data
validators and the MiniLM-required app smoke passed. The earlier intermittent phone-photo
and map-loading observations remain documented; the clean run is not a claimed fix.
CI remains manually paused and unfinished hosting/offline work stays excluded.
See [PR #19](https://github.com/AI-Tech-Summit-Filip-Avramchev/meowchine-learning-repo/pull/19)
and the [pre-merge evidence](docs/PIPELINE_TEST_RESULTS.md#pr-19-pre-merge-verification).

Latest follow-up, owned by Codex: six-category select/text/photo → origin → route test
cases, recognisable synthetic image fixtures, and user-authorized real API checks.
116 new browser cases cover all six categories, three entry paths, three origin methods,
both travel modes, unsafe-item holds, provider recovery and a combined six-item basket.
Final live run passed six text, six photo and six route checks; an earlier phone photo
returned batteries and is retained as an unresolved reliability issue, not hidden by reruns.
Full local regression: 527 passed, one intermittent map-initialization failure; the
individual failing case passed on rerun. This is not a clean full-suite/hosted-CI claim.
The subsequent complete new-browser-module run passed all 116 cases unchanged.
See [examples and commands](docs/PIPELINE_TEST_CASES.md) and
[live evidence/limitations](docs/PIPELINE_TEST_RESULTS.md). No application behaviour or
visual changes in this test follow-up. CI pause and deferred T10 remain unchanged.

Latest user-directed work, owned by Codex: add Clothes as the sixth citizen category,
scrape Skopje donation locations and report the usable inventory. This extends general-waste
guidance and electronics collection/routing in the isolated `feat/general-electronics-guidance`
worktree based on merged main; implementation and local verification complete.
Preserve the kept UI and CI pause.
Visual follow-up: simplified the Clothes SVG to its outline and soft fill, removing
the double collar, seams and pocket at the user's request. Shared styling and card
behaviour remain unchanged.
See [scope and source evidence](docs/GENERAL_AND_ELECTRONICS.md).

Clothes is implemented across the six-card grid, text/photo review, discovery, stop colours
and both route modes. The source scraper extracted eight published venues: five have
reviewed OSM venue matches and are routable; Gazi Baba, Chair and Momin Potok are held
pending address/coordinate resolution. Three additional older leads are recorded, not
published as current destinations. Donation requires clean, washed, wearable garments;
no damaged-textile recycling claim, no invented pins and no new trained model.
Current citizen inventory: 1,590 sites / 1,603 asset/collection-point records. City remains
1,583 / 1,596. See [clothing source audit and exact counts](docs/CLOTHING_DONATIONS.md).

Clothing verification: 408 Python tests including 112 browser/system cases, 18 Node tests,
Ruff, lock, whitespace, seed, pinned infrastructure and geography validation. Layout
screenshots checked at 360/1280 px; picker/text/photo journeys pass in walking/driving.
The restarted localhost app passes smoke with real MiniLM loaded. Providers/tiles are
simulated in browser tests; no paid/live photo or route requests. In-app browser connection
failed; project headless Playwright supplied visual evidence. No field or live-opening
verification, hosted CI, push, PR or merge claimed. CI pause and deferred T10 are preserved.

East Gate Mall added as the second documented destination, limited to phones,
chargers, cables and earbuds. Pin is the mapped main entrance; arrival instructions
direct users to the information desk. Generic/larger devices remain Karpos-only.
Text/photo suggestions and the picker share this small-device boundary. Nula Otpad
is explicitly labelled home pickup, not a third walk-in destination.

Earlier electronics verification: 360 Python cases including 99 browser/system cases;
17 Node controller/map
tests; Ruff, lock, whitespace, pinned infrastructure, seed and geography checks.
The running localhost app passes deployment smoke with the real MiniLM required.
Text/photo/picker journeys for general + electronics pass in both travel modes,
at 360 and 1280 px, using simulated external transports. No paid/live photo or route
calls were made for this change. Local visual QA confirms the fifth card, material-
specific confirmation and electronics map filtering. Browser plugin connection failed;
project Playwright supplied the browser evidence. Independent journeys reset their
test-only routing budget; production limits and their unit tests remain intact.
No field verification, real-phone
vision accuracy, hosted CI run, push, PR or merge is claimed.
The earlier T10 work remains deferred, not part of this merge:

T10a - Deferred, owned by Codex: finish and test the installation/offline support and
deployment preparation locally. Wire the manifest, icons and service worker into the
app; verify offline behavior and updates; add production readiness checks and protect
secrets in the Docker build context. Prepare the deployment and iPhone rehearsal guide.
The T10 files are separately checkpointed unfinished scaffolding, not delivered features.
See [DELIVERY_PLAN.md](docs/DELIVERY_PLAN.md) for the complete T10 acceptance criteria.

## Blocked deployment

T10b - Blocked on Render access to the private organization repository. The user
authorized the repository-only Render request; Codex clicked Request, GitHub required
identity confirmation, and the user subsequently returned to Render. On rechecking,
Render still shows "No repositories found". Successful owner approval is not verified.

Unblock: an owner of AI-Tech-Summit-Filip-Avramchev must confirm/approve Render access
to meowchine-learning-repo; then verify that Render lists that repository. If no request
is pending, complete the repository-only request through GitHub. Do not broaden access
or make the repository public as a workaround. No service or public URL exists yet.

After access is available: deploy the tested build on the free tier, configure the
routing secret securely, verify HTTPS and live citizen/City flows, measure cold starts
and provider capacity, and test Home Screen installation on the actual iPhone.
Device model/iOS and physical-device evidence remain outstanding. T10 as a whole is
incomplete; this split allows useful local work without claiming deployment success.

## Photo-suggestion follow-up

User-requested OpenAI vision integration is implemented without changing T10 priority.
The citizen page accepts one camera/gallery JPEG, PNG or WebP and shows up to six typed
item suggestions. Every recyclable suggestion must still pass through the existing
manual item/condition confirmation before it enters the basket; specialist and uncertain
items cannot become ordinary-bin routes. Categories remain backend-derived and neither
the model nor a broad category establishes site acceptance.

The ignored project-root `.env` is ready for `OPENAI_API_KEY`; the browser never receives
it. Uploads are limited to 8 MB, EXIF-oriented, resized to 1,280 px, metadata-stripped by
in-memory JPEG re-encoding, sent with `store: false`, and not persisted by the service.
Missing credentials, invalid images, timeouts, quota/auth/provider failures and malformed
outputs fail explicitly while text guidance remains available.

Files: src/smart_recycling/{vision,api,settings}.py, web/{index.html,app.js,styles.css},
tests/{test_vision,test_api,test_web_browser}.py, pyproject.toml,
uv.lock, .env.example, README.md, docs/{PHOTO_GUIDANCE,API,ARCHITECTURE}.md.
Validation: lock and Ruff pass; 174 Python cases and ten Node 22 cases pass (22 opt-in
browser cases skipped), including offline OpenAI request/response fixtures, raw-image
client behavior and image privacy/limit checks. A new real-page photo-to-confirmed-basket
case is committed, but downloaded Chromium cannot start on this cluster because its
system GUI libraries are absent; CI/browser execution is still required. The actual
OpenAI key, representative phone photos, live latency/quota, physical iPhone and
provider-data handling remain release gates. T10 remains active.

## Garbage Classification

User-requested ML integration: the pinned, frozen `all-MiniLM-L6-v2` encoder plus a
balanced logistic-regression head is wired into typed guidance as a broad suggestion
when the authoritative policy rules cannot identify an exact item form. It returns one
of four streams (never `general`), reorders matching item choices, and remains visibly
`clarify`/abstained; specialist/held policy, exact item/condition confirmation and
asset-level routing acceptance remain authoritative. OpenAI photo suggestions already
return policy-bounded item kinds/categories and do not cascade through MiniLM.

The 7.4 KiB CPU head and metadata are tracked and checksum/contract-verified before
deserialization; pinned encoder weights are downloaded at local first use and bundled
in Docker. Invalid/missing model files leave policy rules active and appear as unavailable
in `/health`. The model is deliberately labeled development-only: it trained on 8,454
deduplicated phrases and had closed-set accuracy/macro-F1 of 0.938/0.937 on 32 supported
validation cases and 0.949/0.950 on 59 supported manual cases, but no abstention threshold
met the 95% answered-accuracy, 50% coverage, zero-held-answer gate. No threshold was
selected, so the score is uncalibrated and cannot be an authoritative classification.
The five-class path remains held because reviewed data has no supported `general` cases.

GPU reproduction: bare-metal Slurm job 893 completed on `gpgpu01` using one NVIDIA
A100 80 GB MIG device, CUDA 12.6 and host Python package caches; no container or venv.
The embedding/head phase took 0.904 seconds versus 15.025 seconds on CPU, with 4.81 ms
warm p95 single-query latency. Scores and the failed abstention gate were identical.
The node's Python 3.10.12 remains an experiment-only compatibility exception because
the application supports Python 3.11–3.12.

Serving validation: 190 Python tests and 11 Node 22 controller tests pass; 22 opt-in
browser cases remain skipped on this cluster. Lint, lock, whitespace, infrastructure,
geography, coverage and all upgrade-budget reproduction checks pass. A live pinned-model
probe returned the intended four streams for a plastic bottle, glass bottle, cereal box
and phone charger. Docker could not be executed on the login node because its daemon
socket is unavailable; CI must still build/run the deployment image and browser suite.


## Completed City upgrade task

T09 - Done by Codex. Added prepared equitable upgrade recommendations at `/city` and
`/api/v1/upgrades`: budgets 0..20 for three reviewed recycling streams, existing
general-waste candidates, the same weighted 600-second pedestrian catchments, and the
50% municipal-floor / lexicographic max-min objective. Reports before/after, pp gain,
selected source locations and every municipal shortfall. No paid routing calls.

Small searches enumerate all subsets (10,000 limit); larger searches use deterministic
greedy additions and two single-site exchange passes. Optimality and equity feasibility
are separate: only exhaustive search or the all-candidate upper bound proves a floor
infeasible. A tested local-search counterexample correctly reports not_found when an
exact feasible solution exists. Overlap is counted once; existing coverage cannot fall.
General waste is not a supported target without reviewed acceptance evidence.

Five upgrades: glass 58.137033% -> 59.336719%; plastic/metal 34.937949% -> 36.876599%;
paper 5.037202% -> 11.435812%. The municipal floor remains infeasible under the current
candidate/access model. Results are planning approximations, not installation approvals.
All source/connector/operation and smaller-neighborhood limits remain explicit.

Files: src/smart_recycling/{upgrades,upgrades_build,upgrades_solver,coverage_build,
api,settings}.py, scripts/prepare_upgrades.py, data/{upgrades,coverage}/skopje-v1/,
web/{city.html,upgrades.js,styles.css}, tests/{test_upgrades,test_web_browser}.py,
Dockerfile, .env.example, .gitattributes, .github/workflows/ci.yml, README.md,
STATUS.md, docs/{CITY_MODE,API,ARCHITECTURE,DECISIONS,DELIVERY_PLAN}.md.
Validation: 186 Python/browser cases (21 browser), nine JavaScript cases, Ruff, lock,
source validators, exact T08 reproduction and all 63 scenarios recomputed identically
after a population-summation optimization. T08 values are unchanged except code hashes.
CI reproduces the complete prepared outputs before merge. Mobile/desktop screenshots
inspected; no overflow. Local warm HTTP p95 6.69 ms across 20 requests, not a hosted
or iPhone benchmark. The static report is 167.4 KiB; preparation runs offline in minutes.
Physical iPhone, hosting/capacity, verified entrances and human policy review remain
release gates. T10 is active; no deployment or installation success is claimed.

## Completed City coverage task

T08 - Done by Codex with explicit approximation limits. Added `/city` and prepared
`/api/v1/coverage`: population-weighted 600-second directed pedestrian access by
reviewed material stream, all ten municipalities, covered/total population, unconnected
population, the 50% project floor and shortfalls. No double counting or dropped small
components. General waste is unavailable until acceptance evidence exists.

The offline engine splits street segments at actual connection fractions, preserves
one-way access, includes both terminal connector times and runs reverse multi-source
Dijkstra. Access candidates up to 100 m remain unverified; output prominently states
this approximation and the WorldPop/OSM/operating-status limits. No Euclidean or
unweighted fallback. The 13 KB report is served without graph dependencies and checked
against artifact/code/site-policy hashes. CI reproduces the full report offline.

Results: glass 58.137033% (405 sites, 404 connected); plastic bottles/metal cans
34.937949% (86 sites); paper/cardboard/Tetra Pak 5.037202% (7 sites). Denominator
522,420.823288 modeled residents; 8,619.571328 unconnected remain included. Glass is
below the municipal floor in Butel, Saraj and Shuto Orizari. All paper municipalities
remain below it. No upgraded coverage or recommendations are claimed.

Files: src/smart_recycling/coverage{,_build,_graph,_models}.py, api.py, settings.py,
scripts/prepare_coverage.py, data/coverage/skopje-v1/, tests/{test_coverage,
test_web_browser}.py, web/{city.html,city.js,index.html,styles.css}, Dockerfile,
.env.example, .gitattributes, .github/workflows/ci.yml, README.md, STATUS.md,
docs/{CITY_MODE,API,ARCHITECTURE,GEOGRAPHY,DECISIONS,DELIVERY_PLAN}.md.
Validation: 157 Python/browser cases (19 browser), nine JavaScript cases, Ruff,
locked dependencies, exact offline report reproduction and source artifact validators.
CI caught policy line-ending drift in the snapshot hash; policy JSON is now pinned
to LF and the report rebuilt, preserving strict integrity checks.
City UI inspected at mobile/desktop widths; no overflow. Physical iPhone, verified
entrances, human policy review and hosted capacity remain release gates. T09 is active.

## Completed citizen interaction pass

User-requested pass across classification, basket, origins, map, routing and failures:
replaced checkbox/confirm/add with Confirm & add to trip; replaced sharing checkbox
plus planning with the explicitly disclosed Plan trip & share location action.
Manual specialist choices show guidance instead. Server confirmation/consent contracts
remain unchanged. Modes are radio choices; next-step text explains disabled planning.

Fixed duplicate basket adds, stale continuation actions, confirmation retry losing
choices, delayed map initialization resetting completed routes, and routing reconnect
requiring a reload. Added map-local center/cancel controls, return to setup after
selection, marker-to-stop details and failure-only tile retry. Reduced repeated copy.

Files: web/{app,trip,map}.js, web/{index.html,styles.css}, tests/{web_guidance.test.js,
test_web_browser.py}, README.md, docs/{MAP,ROUTING}.md, STATUS.md.
Validation: 133 Python/browser cases (17 browser), nine JavaScript cases, Ruff, lock
and whitespace checks. Phone-width and desktop Edge flows/screenshots inspected using
real classification and fixture routes/tiles. Physical iPhone remains a T10 gate.
T08 remains next; this is a user-requested UX follow-up, not City Mode implementation.

## Completed citizen UX follow-up

User-requested follow-up to T07: the page now follows add items, plan trip, view map.
Basket and origin controls are together; manual coordinates are expandable. A ready
route automatically focuses the map, hides discovery markers/search controls, shows
numbered stops and a distance/time summary, and offers fit/edit/details controls.
Other collection points are opt-in; clearing/changing a trip restores discovery.
Stopped outstanding map animation before fitting a route to prevent stale framing.

Files: web/{index.html,map.js,trip.js,styles.css}, tests/test_web_browser.py,
docs/{MAP,ROUTING}.md, STATUS.md. Validation: 127 Python/browser tests (11 browser
cases), nine JavaScript cases, Ruff and lock checks. Mobile Edge screenshots inspected
with fixture routes/tiles; no new provider or physical iPhone claim. T08 remains next.

## Completed routing task

T07 - Done by Codex. Added a six-item confirmed basket, explicit coordinate-sharing
consent, authoritative asset acceptance checks, directed minimum-time routing within
a bounded nearby shortlist, walking/driving ORS profiles, and actual route geometry.
Trips end at the last stop. Unsupported baskets fail as a whole. Provider failures,
quota limits, invalid responses and stale client results have explicit handling.
The local key is configured in ignored `.env`; it is never sent to the browser.

Files: src/smart_recycling/{routing_models,route_planner,ors,routing,api,settings,
guidance}.py, web/{trip,app,map}.js, web/{index.html,styles.css}, tests/{test_routing,
test_web_browser}.py, scripts/smoke_routing.py, pyproject.toml, uv.lock, .env.example,
data/classifier/{rules-v2,evaluation-v2}.json, README.md, STATUS.md,
docs/{ROUTING,API,MAP,ARCHITECTURE,GEOGRAPHY,DECISIONS,DELIVERY_PLAN}.md.
Classifier artifacts were reproduced after a guidance-message change; prediction
quality/threshold are unchanged. Validation: 126 Python/browser tests, nine JavaScript
cases, Ruff, lock and infrastructure/geography checks. Live ORS three-material trips:
walking 2.48 km / 30 min; driving 3.13 km / 9 min, three stops. Known one-way reverse
probe: driving 642.5 m versus 78.4 m forward; walking 78.4 m both ways. Live mobile
Edge basket flow also passed. See ROUTING.md for reproduction and evidence limits.

Limitations: shortlist is not a city-wide optimum; network access gaps up to 100 m
are unverified and excluded from totals. Unknown operation/human policy review,
physical iPhone, hosting and account capacity remain gates. No personal trips are
cached. CI must pass before merge. T08 is next; no City coverage is claimed.

## Completed map task

T06 UX follow-up: replaced the site list with search-only results beneath the search
bar. At least two characters reveal at most five matches; broader queries prompt
refinement. No browse-all list, expansion control or pagination remains. Search
still works when the map fails. This supersedes the earlier collapsed-list approach;
T07 remains next.

T06 - Done by Codex. Added a real Leaflet map of all 1,583 City site groups, material
discovery filters, name/address/municipality search and a paginated accessible list.
Asset details preserve source, acceptance limits, QA and unknown operating status.
Specialist filtering explicitly reports no verified records; no acceptance or route
is inferred from broad categories. Metro scope remains separate.

Opt-in device location, deliberate map/keyboard-center selection and manual coordinates
set an in-memory starting point. Distances are explicitly straight-line. Late location
callbacks cannot replace newer selections. ETag/Cache Storage preserves dated site data
through refresh failures; map/tile/data failures have separate recovery paths.
Leaflet 1.9.4 is locally served with its license and verified upstream checksums.

Files: web/{index.html,styles.css,map.js,site-data.js,map-config.json,vendor/leaflet/},
tests/{test_web_browser.py,web_map.test.js}, pyproject.toml, uv.lock, Makefile,
.github/workflows/ci.yml, .gitattributes, README.md, STATUS.md,
docs/{MAP,API,ARCHITECTURE,DELIVERY_PLAN}.md.
Validation: 97 Python/browser cases, nine JavaScript cases, Ruff, locked dependencies,
infrastructure/geography validators and whitespace checks. Seven headless Edge cases
exercise the real page at 390×844, including T05 manual/specialist guidance, site details,
empty results, origins, denied/stale geolocation, cached refresh and tile/library failure.
Visual inspection caught and fixed filter viewport framing. Browser tests are required
in CI; they use fixture tiles to avoid automated OSM traffic. Physical iPhone/Safari,
live tile capacity and hosting remain T10 gates; source/human-review holds remain.
CI must pass before merge. No routing or City coverage is claimed.

## Completed classifier task

T05 - Done by Codex with explicit policy/release holds. Served `policy-rules-v2`,
with threshold 0.85 selected only on 48 development validation cases. Added typed
clarification, manual item/condition confirmation and specialist guidance. Hazard
signals cannot be overridden by a recycling selection; no specialist destinations
or general-waste acceptance are fabricated. Removed synthetic nearest lookup from
the citizen page. Source/code hashes guard startup against unevaluated changes.

Manual test: 59 agent source-reviewed queries, 36 answered (61.0%), 34 correct
(94.4% answered accuracy), four-supported-class macro-F1 0.684. General has no
supported examples. Forty-one manual queries, 37 Dataset A families and unreviewed
Toronto proposals remain held; human review is outstanding. Validation is authored
development data with overlapping item families, not independent field evidence.
Local prediction p95 is below 1 ms against a 25 ms budget; HTTP/iPhone/hosting latency
is unmeasured. Full errors and per-class metrics are in data/classifier/.

Files: src/smart_recycling/{guidance,api,settings}.py, scripts/evaluate_guidance.py,
data/classifier/, data/evaluation/guidance_validation.csv, tests/{test_guidance,
test_api}.py, tests/web_guidance.test.js, web/{app.js,index.html,styles.css},
.env.example, Dockerfile, Makefile, .github/workflows/ci.yml, README.md,
docs/{ML,API,DISPOSAL_POLICY,DECISIONS,DELIVERY_PLAN}.md, STATUS.md.
Validation: 90 pytest cases including fresh artifact/quality reproduction; six UI
controller scenarios; Ruff; locked dependencies; infrastructure/geography validators;
live HTTP guidance/health smoke. CI must pass before merge. Browser bootstrap failed
and there were no enabled browser surfaces, so visual/iPhone verification is explicitly
outstanding for T06/T10. Docker image build remains unverified locally.

## Completed geographic inputs task

T04 - Done by Codex. Acquired checksum-pinned WorldPop 2025 R2025A v1 modeled population
and the 2026-09-18 OSM extract. Shared ten OSM municipal polygons, 35,716 demand locations
(total modeled population 522,420.8233), 198,114 street nodes, 25,541 ways and 2,248
restriction relations. Compared local Pakomak boundaries without redistributing their
geometry. Added reproducible offline preparation, package validation, fixtures and CI.

QA: municipal/city population sums reconcile; no municipal overlap above 1 square metre,
no interior union gaps, no missing restriction members. Walking graph: 190,066 nodes,
397,812 directed edges, 232 weak components. Driving diagnostic graph: 162,144 nodes,
319,799 edges, 235 weak components. Preserved turn restrictions are not applied by the
diagnostic graph, which is explicitly not routing-ready.

Access audit: 8,619.5713 modeled residents beyond the 100 m candidate-connection limit;
6,835.9707 on smaller walking components. One City site lacks a walking candidate,
two lack driving candidates. All population remains in the modeled denominator.
Nearest-segment candidates are unverified, not proof of unobstructed/legal access.
WorldPop NoData covers 345.0192 square km and is reported, not converted to zero.
No coverage metric, route or upgrade recommendation has been implemented in T04.

Files: src/smart_recycling/geography/, scripts/{prepare,validate}_geography.py,
data/geography/skopje-v1/, tests/test_geography.py, pyproject.toml, uv.lock,
.gitattributes, .github/workflows/ci.yml, Makefile, README.md,
docs/{GEOGRAPHY,ARCHITECTURE,DATA,CITY_MODE,DECISIONS,DELIVERY_PLAN}.md, STATUS.md.
Validation: 73 pytest cases, Ruff, locked dependency validation, infrastructure and
geography artifact validators, full real-input preparation and Markdown links.
CI must pass before merge. Provider feasibility is documented; authenticated ORS
route tests (401 without a key), actual Render capacity and iPhone verification remain
T07/T10 gates. No paid services or public deployment were created.

## Completed infrastructure task

T03 - Done by Codex. Strict ingestion loads 1,596 City assets into 1,583 source sites
and one separately scoped metro asset. Assets retain source capabilities, acceptance
profiles, provenance, QA/reuse flags, exact coordinates and dated observations.
GET /api/v1/sites serves deterministic schema-v1 snapshots with ETag/304 caching.
Health distinguishes real counts from the four legacy synthetic nearest-lookup sites.
No map rendering or item-specific real-site routing is claimed yet.

Files: src/smart_recycling/{infrastructure,infrastructure_models,api,settings}.py,
tests/{test_infrastructure,test_api}.py, Dockerfile, .env.example, README.md,
docs/{API,ARCHITECTURE,DATA,DELIVERY_PLAN,DISPOSAL_POLICY}.md, PROJECT_BRIEF.md,
data/infrastructure/skopje-2026-09-19/README.md, STATUS.md.
Checks passed: 53 pytest cases; Ruff; lock validation; input checksums; live HTTP
City/metro/304/home/docs smoke; whitespace and Markdown link checks. Docker runtime
now copies infrastructure/policy inputs; image build not run because the local Docker
daemon is unavailable. CI must pass before merge.

## Completed policy task

T02 - Done by Codex (agent source review, not human sign-off). Reviewed all 50 Dataset
A families: 13 supported, 37 explicitly held. Reviewed all 100 manual queries via
an immutable-text hash-linked sidecar: 59 supported, 41 held. Added operator source
references and conservative asset profiles; no specialist facilities fabricated.
Toronto suggestions and legacy automatic approvals no longer enter training.
Baseline training rejects stale approvals/missing classes and reports the supported
manual subset explicitly. No model retrained; the live classifier is unchanged.

Files: data/policy/skopje_v1.json, data/mappings/needs_manual_review.csv,
data/evaluation/manual_test_review.csv, src/smart_recycling/data/{review,dataset_a,
dataset_b,augmentation,combination,baselines}.py, tests/test_policy_review.py,
README.md, data/README.md, docs/{DISPOSAL_POLICY,DATA,ML,DELIVERY_PLAN}.md, STATUS.md.
Checks passed: focused policy/data tests; full pytest suite; Ruff; uv lock --check;
infrastructure checksum validation; git diff --check. Original manual_test.csv
remains unchanged. General-waste evidence and unreviewed Toronto items are explicit
follow-ups for T05, not approved training ground truth.

## Completed requirements task

T01 - Requirements and engineering standards documented. Confirmed September 22
scope: Skopje, English, all five core features, iPhone Home Screen installation,
walking/driving routes ending at the last site, and free/free-tier services where
feasible. Feedback/voting deferred. Uncertainty requires clarification/manual choice;
specialist items require guidance and explicitly compatible facilities, never general
waste. Municipal equity policy is specified in CITY_MODE.md.

Files: AGENTS.md, PROJECT_BRIEF.md, STATUS.md, docs/ENGINEERING.md,
docs/DELIVERY_PLAN.md, docs/CITY_MODE.md, docs/PRODUCT.md, docs/ARCHITECTURE.md,
docs/API.md, docs/ML.md, docs/QUALITY.md, docs/DECISIONS.md.
Validation: local Markdown link and whitespace checks; PR CI must pass before merge.
No new application behavior is claimed by this documentation task.

## Working

- City upgrade recommendations with population/equity objectives, selected source sites,
  before/after gains, municipal gaps and explicit heuristic/infeasibility evidence.

- Current City population-weighted walking-network coverage approximation at `/city`,
  with material comparison, ten municipal breakdowns and 50% floor shortfalls.

- Confirmed multi-item basket and live ORS walking/driving routes through explicitly
  accepting assets, ending at the last stop; bounded shortlist and access-gap disclosures.

- Real Skopje map, material discovery/search, source details, origins and dated cache.
- Real Skopje infrastructure snapshot shared for team ingestion: 1,596 City assets
  at 1,583 coordinate groups, plus one separately scoped metro asset. Source
  checksums and QA flags are preserved; the real snapshot API is live. Legacy nearest
  lookup still uses synthetic sites pending item-specific integration.

- Evaluated policy-scoped rules, heuristic scores, clarification/manual confirmation
  and specialist contacts; no automatic general-waste guidance.
- Nearest compatible collection-site lookup using Haversine distance.
- FastAPI endpoints and a build-free, mobile-first citizen page.
- Deterministic synthetic site seed, unit tests, lint config, CI, and container setup.
- Target architecture agreed: mobile client + FastAPI, server-first inference, local
  site caching, and an optional ONNX path for later on-device inference.
- Locked `uv` environment and multi-stage runtime image.
- Reproducible Dataset A + Toronto vocabulary pipeline with grouped 70/15/15 splits.
- Rule and TF-IDF/logistic baselines evaluated on grouped and provisional manual tests.

## Next

1. T10a: locally verified installation/offline support and deployment preparation.
2. T10b: resume HTTPS deployment and physical iPhone rehearsal after repository access.
3. Release holds: obtain human policy review and general-waste evidence; review Toronto
   proposals before training. Broaden independent evaluation before quality sign-off.

## Open decisions

- City Mode uses population-weighted 10-minute walking-network coverage per material.
  Delegated equity policy: 50% municipal floor; max-min coverage if unattainable;
  disclose solver limits. Coverage is computed with explicit approximation limits; field connector validation remains pending.

- Validate source-to-app capability mappings and confirm outstanding reuse terms.
- Confirm the local policy for composite/contaminated packaging and specialist waste.
- Verify iPhone Home Screen installation on the actual demo device; select HTTPS hosting.
- Proposed free demo stack: ORS Standard, interactive OSM tiles, Render Free.
  Authenticated routes passed T07; confirm account quotas and hosted performance before release.
- Threshold is now validation-selected; independent quality and human review remain open.

## Risks

- Sparse paper infrastructure can make a technically correct route impractical.
- Synthetic labels can inflate evaluation scores through paraphrase leakage.
- Dataset A has only coarse item-family identifiers, limiting per-class split balance.
- User location and feedback require minimization, aggregation, and retention limits.
- Server inference needs connectivity, so cached site data and graceful failures matter.
