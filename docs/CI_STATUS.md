# CI status

Updated: 2026-10-17

The private repository's GitHub Actions workflow is **active**. It runs a quality
job and a Docker smoke job on pushes and pull requests. The repository URL remains
[VikiShmiki/meowchine-learning-repo](https://github.com/VikiShmiki/meowchine-learning-repo)
after the Najdi Frli product rename.

## Rename and maintenance gate

The Najdi Frli audit retains both required jobs and strengthens deployment smoke
to check the page/API product name. Runtime packaging now carries only the current
v3 audit heads. Local verification is recorded in [QUALITY.md](QUALITY.md); the
[Actions history](https://github.com/VikiShmiki/meowchine-learning-repo/actions)
records the full Linux/browser/container outcome for each submitted revision.

## Earlier merged baseline

[PR #4](https://github.com/VikiShmiki/meowchine-learning-repo/pull/4) integrated
Oliver's ML remediation with reporting, JSP and parking, merged as `c626c8d`.
[Run 39031926188](https://github.com/VikiShmiki/meowchine-learning-repo/actions/runs/39031926188)
passed both jobs: 737 backend tests, 429 browser cases, 21 Node tests, lock/lint/
formatting and artifact checks, plus Docker startup/deployment smoke with both
actual v3 audit language models. Windows can skip two symlink cases when the OS
denies the needed privilege; Linux CI exercises them.

These results belong to that tested revision. Subsequent changes require successful
checks on their own revision; a cancelled or superseded run is not pass evidence.
See [current Actions runs](https://github.com/VikiShmiki/meowchine-learning-repo/actions).

## Gate contents

- Quality: locked dependencies, Ruff, backend and Node tests; infrastructure and
  geography validation; exact coverage/upgrade reproduction; Chromium citizen,
  City, account, reporting, bilingual, JSP and parking tests.
- Container: build the non-root runtime image, load both pinned encoders and JSON
  heads, serve the real data bundles, and pass `smoke_deployment.py` without keys.
  A bounded readiness wait tolerates startup but still fails if readiness never arrives.

Prior private delivery checks are linked from
[PR #1](https://github.com/VikiShmiki/meowchine-learning-repo/pull/1),
[PR #2](https://github.com/VikiShmiki/meowchine-learning-repo/pull/2) and
[PR #3](https://github.com/VikiShmiki/meowchine-learning-repo/pull/3).
The source repository's account restriction and paused workflow are preserved in
[UPSTREAM_CI_STATUS.md](UPSTREAM_CI_STATUS.md); they do not describe this repository.

Local commands and test boundaries are in [QUALITY.md](QUALITY.md). Automated CI
does not establish public deployment, physical-device behavior, native-language
review, vacant parking spaces or live external-provider accuracy.
