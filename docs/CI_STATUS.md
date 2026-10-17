# CI status and evaluation evidence

Updated: 2026-10-17

This private repository has its own [Actions runs](https://github.com/VikiShmiki/meowchine-learning-repo/actions).
The checked-in workflow runs quality checks and a container smoke test on pushes
and pull requests. No hosted pass is claimed until those jobs complete successfully.

The source repository's earlier account restriction and paused workflow are
historical evidence, preserved in [UPSTREAM_CI_STATUS.md](UPSTREAM_CI_STATUS.md).
They do not establish the status of this repository or its owner's account.

Run `make check`, or the PowerShell equivalents in [README.md](../README.md),
for the local gate. See [QUALITY.md](QUALITY.md) for dated local outcomes.
Local checks do not establish hosted deployment, physical-device behavior,
native-speaker review, or live external-provider accuracy.
