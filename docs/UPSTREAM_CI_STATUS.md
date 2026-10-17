# Historical source-repository CI status and evaluation evidence

Verified 2026-09-22 through GitHub's API. CI is `disabled_manually` following an
explicit user decision to pause runs while the repository account restriction remains.

## What GitHub reported

[Run 35563102629](https://github.com/AI-Tech-Summit-Filip-Avramchev/meowchine-learning-repo/actions/runs/35563102629)
was marked failed without executing the quality/container jobs. The quality check's
[annotation API](https://api.github.com/repos/AI-Tech-Summit-Filip-Avramchev/meowchine-learning-repo/check-runs/106219577153/annotations)
contains (also preserved with job step counts in
[ci-blocker-evidence.json](ci-blocker-evidence.json)):

> The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings

This is a GitHub account billing/spending restriction, external to application code.
The annotation does not establish a GitHub platform outage or distinguish which of
its two billing explanations applies. No test assertion, lint check or container
build ran in those blocked jobs, so their failed run status is not evidence that
those checks failed. Conversely, tests that never executed cannot be called passing.

## How to evaluate this repository

The workflow remains checked in with real lock/lint/format/unit/browser/data and
container-smoke steps. There are no dummy success jobs, check overrides or artificial
status badges. Evaluate code/test quality using the versioned tests and the dated,
commit-specific local evidence in [QUALITY.md](QUALITY.md) and PR descriptions.
Distinguish the external inability to execute hosted CI from application defects.
Local results do not replace unperformed container, hosted or device verification.

Main reports `protected: false`; the rulesets API reports a GitHub plan restriction.
This is an outstanding enforcement limitation, not a claim that branch safeguards
exist. No account billing, plan, workflow-enable or protection settings were changed
as part of this audit fix. The user requested the pause to remain documented.

## Restoration

An account/organization owner must resolve Billing & plans or provide an eligible
runner with appropriate workflow configuration. Then enable CI, run the actual
quality and container jobs on the intended revision, inspect both results, and
configure branch safeguards supported by the plan. Do not bypass failing checks.

Local gate: `SRA_BROWSER_TESTS=1 make check`, followed by the seed, infrastructure,
geography, coverage and upgrade checks in [QUALITY.md](QUALITY.md). Ordinary tests
use isolated databases and simulated external providers; they are not paid-provider
accuracy measurements.

Branch housekeeping: 22 remote heads matching their merged PR head commit were
deleted; `test/system-pipeline` was retained because it is checked out in another
worktree. Enabling automatic branch deletion returned GitHub HTTP 404 with the
current credentials, so this repository setting was not changed. An administrator
can enable it in repository settings. Main/history/PR evidence were retained.
