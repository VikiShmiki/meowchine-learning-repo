# Audit follow-up — 22 September 2026

## Fixed

- Offloaded synchronous DB work from async middleware, provider allowance and photo
  upload paths. Schema creation occurs once per store path; ordinary reads no longer
  acquire a writer lock merely to run empty cleanup deletes. Retention remains enforced.
- Added concurrency/read-lock regressions, independent English/Macedonian model-health
  regressions and localized dynamic/middleware error checks.
- Added server catalog-template interpolation and translated middleware rejections.
- Reported English availability independently from the bilingual fallback wrapper.
- Added `.env.*` ignores while keeping `.env.example` trackable.
- Normalized nine-file formatting drift and included formatting in the normal gate.
- Updated stale README/setup/roadmap/architecture claims and moved the long old status
  log into STATUS_HISTORY.md, preserving relative links and historical evidence.
- Added CI_STATUS.md and a GitHub API evidence snapshot: both blocked jobs had zero
  steps, and GitHub reported account payments/spending limits. No false CI pass claimed.
- Added prototype SHA-256 provenance and offline freshness checks to the Macedonian
  evaluation; reran the model evaluation, retaining 54/59 correct.
- Added a non-root container user and writable runtime directory. Container execution
  still needs verification because the local Docker daemon is unavailable.
- Evaluated lossless fixture compression: only 28,160 bytes (about 0.2%) could be saved.
  Kept original files to avoid binary-history churn and preserve visual test evidence.
- Deleted 22 remote heads only after verifying exact equality with merged PR heads,
  using atomic deletion with expected-SHA leases. Preserved main and the branch checked
  out in another worktree. A branch/SHA recovery manifest is retained in task outputs.

## Remaining external or owner decisions

CI billing/runner availability, plan-dependent branch safeguards, and automatic
branch deletion need account/repository administration. The automatic-deletion API
request returned HTTP 404; that setting was not changed. No license was invented;
project licensing needs the owner's choice. Native Macedonian review and independent
field evaluation need external evidence. Hosted/device work remains user-deferred.
The Docker user change is configuration hardening, not a claimed container test pass.

Verification of application/test revision `287a62c`: 897 Python tests with browser
journeys enabled, 19 Node tests, lock/lint/full formatting, staged credential-pattern
scan, whitespace, data validators, coverage/upgrade reproduction and live bilingual
smoke all pass. The full suite reports 11 existing dependency deprecation warnings.
See QUALITY.md and STATUS.md. No container/hosted/device or native-review pass is claimed.
