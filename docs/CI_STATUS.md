# CI status and evaluation evidence

Updated: 2026-10-17

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

The source repository's earlier account restriction and paused workflow are
historical evidence, preserved in [UPSTREAM_CI_STATUS.md](UPSTREAM_CI_STATUS.md).
They do not establish the status of this repository or its owner's account.

Run `make check`, or the PowerShell equivalents in [README.md](../README.md),
for the local gate. See [QUALITY.md](QUALITY.md) for dated local outcomes.
Local checks do not establish hosted deployment, physical-device behavior,
native-speaker review, or live external-provider accuracy.
