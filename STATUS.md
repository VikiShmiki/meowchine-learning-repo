# Status

Updated: 2026-10-17

## Current handoff — October 17, 2026

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
