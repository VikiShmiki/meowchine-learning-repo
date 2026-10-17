# Status

Updated: 2026-10-17

## Photo consistency improvement (Codex)

Goal: prevent contradictory AI photo suggestions and stale prior-item confirmation
from entering the review flow. Description/reason checks now reuse bilingual text
policy signals; rejected suggestions have no category or preselected item. Editing
or selecting another description clears the previous confirmation and contacts.
Positive candidates, specialist hazards and the residual exception are preserved.
Goal achieved. `make check` passed: 677 Python tests, 391 opt-in skips, 21 Node tests,
lock/lint/format. The 34 new Python cases cover rejected contradictions, supported
candidates and specialist precedence; two Node regressions cover photo review and
stale confirmation. Three targeted Chromium checks could not launch because the
host lacks `libatk-1.0.so.0`. Text model weights and thresholds are unchanged.
See [photo flow](docs/PHOTO_GUIDANCE.md) and [verification](docs/QUALITY.md).

## ML follow-up audit — five goals implemented (Codex)

The mixed-item confirmation guard, equal-concept calibration, actual-fallback
serving evaluation, unreadable-model fallback, and label/provenance verification
are implemented. New development-v3-audit heads preserve the earlier artifacts.
On the existing development test, MK suggestions cover 14/42 supported fallback
inputs (previously 4/42), all correct; EN remains 18/30, all correct. Thresholds
were selected only on calibration data. Native review and independent user data
remain necessary. Verification and report links: [ML.md](docs/ML.md).

All five goals completed. Final `make check` passed: 643 Python tests, 389 expected
opt-in skips, 19 Node tests, lock/lint/format. Both real encoders replayed offline;
a second training run reproduced weights, temperatures and gates. Historical
manual replay still has 2 EN / 3 MK held-input suggestions; these remain reported.
See [verification details](docs/QUALITY.md).

## Completed improvement — verified serving encoders (Codex)

Serving and future v3 training verify pinned encoder weights, tokenizer and
configuration before use. Swapped, incomplete or changed encoders fail closed;
only the affected language loses suggestions and policy guidance remains available.
Offline bundle export preserves verified bytes and upstream attribution.

`make check` passed: 619 Python tests, 389 opt-in skips, 19 Node tests, lock/lint/format.
Seed/infrastructure/geography validation passed. Both real encoder bundles reloaded
offline with identical embeddings and scores on ten probes; both swaps were rejected.
Historical models/evaluations are unchanged. Older reserialized encoder directories
need rebuilding; see [ML.md](docs/ML.md) and [verification details](docs/QUALITY.md).

## Completed — ML/data remediation (Codex)

User-authorized audit follow-through implemented and verified. Serving now uses
hash-pinned development-v3 JSON heads with abstention; policy/confirmation retains
control. Latin-typed Macedonian negation/dirty-clothing holds are repaired.

- Retained 5,004 English source examples independently of translations, including
  all 1,572 phone/laptop charger descriptions; sampled 390 template phrases for
  fitting. Quarantined legacy MK translations and ambiguous source text.
- Added paired, explicitly agent-authored train/tune/calibration/test concept
  groups covering all six classes, held cases and Latin spelling variants. These
  are development diagnostics, not independent or native-reviewed user evidence.
- Tuned frozen and TF-IDF candidates on the tuning set; selected abstention on a
  separate calibration set. New heads reproduce byte-for-byte. Historical v1/v2
  artifacts remain unchanged; source-root relocation preserves checksum checks.
- Same-input development test macro-F1: EN 0.732 → 0.979; MK Cyrillic 0.528 → 0.870;
  pooled MK spellings 0.491 → 0.847. Unknown-input errors and low MK suggestion
  coverage remain visible. No automatic disposal or production-quality claim.
- `make check`: 617 Python tests passed, 389 opt-in skips, 19 Node tests passed;
  lock/lint/format pass. Real encoders also preserve policy holds. The sandbox
  blocked API TestClient event-loop behavior; the full suite passed outside it.

Results, limitations and reproduction: [ML.md](docs/ML.md),
[BILINGUAL_DATA.md](docs/BILINGUAL_DATA.md), and `data/ml/v3/`.
External native review and a newly collected independent user test remain required.
Historical LoRA results do not isolate architecture effects; the new controlled
comparisons cover weighting and regularization for frozen/TF-IDF models, not a new
LoRA experiment. No hosted/browser/device/container verification is claimed here.

## Current handoff — October 17, 2026

Private repository edition prepared with a fresh initial commit, current project
documentation and a rebuilt technical report. Source data and historical experiment
evidence keep their original dates. No pending feature work is activated.

Local handoff checks passed: 564 Python tests, 19 Node tests, lock/lint/format and
seed/infrastructure/geography validation. The 389 opt-in skips and verification
limits are recorded in [QUALITY.md](docs/QUALITY.md).

## Historical capability — v2 bilingual model integration

The corrected six-class bilingual dataset has five completed seed-42–46 runs (30
fits). Frozen MiniLM had the highest scores in those confounded configurations:
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
