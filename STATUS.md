# Status

Updated: 2026-10-17

## Implemented — parking-assisted driving

Owner: Codex, user-requested October 17, 2026. Driving now offers optional mapped
parking plus walking to containers, including return-to-car walks between stops.
The licensed, reproducible OSM/Geofabrik snapshot contains 144 public parking points;
space availability stays unknown. English/Macedonian UI, distinct parking markers,
source details and full-container exclusions are covered by 20 backend and seven
focused browser tests. A live ORS two-drop-off journey also succeeded. Full
regression/container delivery gates are recorded in [CI_STATUS.md](docs/CI_STATUS.md).
See [PARKING.md](docs/PARKING.md) for source refresh, access and timing limits.

## Implemented — JSP public transport

Owner: Codex, user-requested October 17, 2026. Implemented scheduled JSP journeys,
ORS walking connections, one same-stop transfer per collection leg, departure
selection and bilingual itinerary/map UI. Full-container exclusions and post-trip
check-ins apply. The live JSP/ORS smoke returned buses 18 and 8 to Karpoš yard.
The 24 backend and seven focused browser cases pass at 320/390/1280 px. Lock,
lint, formatting, 19 Node tests and all snapshot/coverage/upgrade reproduction
checks pass. The local app loads both language models with routing configured.
Delivery and full-regression gate results are recorded on
[PR #2](https://github.com/VikiShmiki/meowchine-learning-repo/pull/2) and in
[CI_STATUS.md](docs/CI_STATUS.md). See [TRANSIT.md](docs/TRANSIT.md) for limits.

## Completed — trip completion and container check-ins

Implemented the user-requested optional post-trip check-in without photos. Full
reports now exclude the specific asset from everyone's routes immediately, with a
12-hour expiry and reviewer rejection. Visited stops are tracked in memory across
replans; individual drop-offs keep multi-stop trips open and the final drop-off ends
the trip. Early completion keeps unfinished basket items. Both English and Macedonian
copy are included. Full browser-enabled regression checks pass, followed by 41
focused browser checks on the final interface, 28 community/backend tests, and 19
Node tests. Lock, lint, formatting, seed/infrastructure/geography validators and
visual checks at 320/360/1280 px passed. See [QUALITY.md](docs/QUALITY.md).
Hosted CI is tracked in [CI_STATUS.md](docs/CI_STATUS.md).

## Previous handoff — initial private-repository edition

Private repository edition prepared with a fresh initial commit, current project
documentation and a rebuilt technical report. Source data and historical experiment
evidence keep their original dates. No pending feature work is activated.

Local handoff checks passed: 564 Python tests, 19 Node tests, lock/lint/format and
seed/infrastructure/geography validation. The 389 opt-in skips and verification
limits are recorded in [QUALITY.md](docs/QUALITY.md).

## Completed capability — bilingual model integration

The corrected six-class bilingual dataset has five completed seed-42–46 runs (30
fits). Frozen MiniLM is the strongest of the tested methods on both languages:
English manual macro-F1 0.696 ± 0.000 and Macedonian 0.507 ± 0.000; grouped-test
macro-F1 is 0.505 ± 0.000 and 0.552 ± 0.000. These are sample SDs over seeds on
one fixed split, not independent test uncertainty. Full comparisons, timings and
limitations are in [ML.md](docs/ML.md); dataset provenance is in
[BILINGUAL_DATA.md](docs/BILINGUAL_DATA.md). Source artifacts and translations
still need human/native review. Model outputs are suggestions only; policy and
exact-item confirmation retain authority.

## Current state — documentation and demo handoff

The refreshed [README.md](README.md) links the source-backed
[technical report](docs/technical-report.pdf), its [LaTeX source](docs/technical-report.tex)
and the owner's [demo video](docs/assets/demo-app-video.mp4). The report documents
architecture, model evidence, route/City methods, validation limits and workflow.
This short file carries live state; [STATUS_HISTORY.md](STATUS_HISTORY.md) carries
earlier milestones.

The remaining release evidence is native Macedonian review, independent field/site
checks and hosted/container/physical-phone verification. CI for this private
repository is tracked separately from the historical source-repository restriction.
See [CI_STATUS.md](docs/CI_STATUS.md).

## Previous delivery — verified audit fixes (PR #24)

The colleague's audited application changes and documentation are preserved. These
include English/Macedonian UI, six disposal journeys, real collection-point routing,
City coverage/upgrades, moderated community reports and optional accounts. The
audit fixed blocking database calls, unnecessary SQLite writes, independent model
health, localized API errors, evaluation provenance, environment-file ignores and
stale documentation. See [AUDIT_FIXES.md](docs/AUDIT_FIXES.md) and
[QUALITY.md](docs/QUALITY.md) for the original verification and remaining limits.

## Reference

- [Quality and validation](docs/QUALITY.md)
- [Language/model contracts](docs/LANGUAGES.md)
- [Delivery scope](docs/DELIVERY_PLAN.md)
- [Historical delivery evidence](STATUS_HISTORY.md)
