# CI status and evaluation evidence

Updated: 2026-10-17

Parking delivery adds 20 backend and seven browser tests to the same quality gate,
and the container smoke now verifies the bundled public-parking endpoint. The
current parking revision's quality and container jobs in
[Actions](https://github.com/VikiShmiki/meowchine-learning-repo/actions?query=branch%3Afeat%2Fparking-routes)
are the merge gate. Focused local checks and a live ORS parking journey passed;
these do not substitute for those complete gates or field access checks.

The JSP delivery is [PR #2](https://github.com/VikiShmiki/meowchine-learning-repo/pull/2).
Its [checks](https://github.com/VikiShmiki/meowchine-learning-repo/pull/2/checks)
include the new transit tests alongside all existing regression/browser checks and
the container smoke test. A successful check on the current PR revision is the
merge gate; a cancelled superseded/duplicate run is not pass evidence. The local
key and real GTFS cache remain ignored and are not available to CI.

This private repository has its own [Actions runs](https://github.com/VikiShmiki/meowchine-learning-repo/actions).
The checked-in workflow runs quality checks and a container smoke test on pushes
and pull requests. No hosted pass is claimed until those jobs complete successfully.

The [initial private-repository run](https://github.com/VikiShmiki/meowchine-learning-repo/actions/runs/39022132656)
executed its jobs: Docker failed because `.dockerignore` excluded the bilingual
model heads, and six browser cases failed on narrow-screen layouts. The trip-check-in
delivery fixes both causes. Its own quality/container results should be read from
the latest run on the delivery revision, independently of those historical results.
The first feature run built the image but exposed an early connection reset before
the app was ready. The smoke test's bounded startup wait now handles that transient
failure, with six regression tests; it still fails if readiness never arrives.
The next run exposed a runtime import failure: model-cache commands had resynced
the installed package into editable mode. They now use `uv run --no-sync` to retain
the non-editable installation. Bundled model files receive explicit read permissions
for the runtime user; the runtime build loads both encoders as that non-root user,
verifying the package, file access and model serialization together.
That container check passed on revision `ec3f8a6`. The Linux browser run also
identified 320 px map-control overlap and Macedonian status-summary overflow;
fixed-width control space and wrapping status labels address these. The 22 focused
local layout checks pass with system and wider Verdana fonts. Final combined CI
remains the latest delivery revision's quality and container jobs.

The source repository's earlier account restriction and paused workflow are
historical evidence, preserved in [UPSTREAM_CI_STATUS.md](UPSTREAM_CI_STATUS.md).
They do not establish the status of this repository or its owner's account.

Run `make check`, or the PowerShell equivalents in [README.md](../README.md),
for the local gate. See [QUALITY.md](QUALITY.md) for dated local outcomes.
Local checks do not establish hosted deployment, physical-device behavior,
native-speaker review, or live external-provider accuracy.
