# Najdi Frli status

Updated: 2026-10-17

## Current application

The private repository's `main` includes Oliver's ML remediation and the container
check-in, JSP bus and parking integrations. The product is named **Najdi Frli**;
the repository URL, Python imports and `SRA_*` settings remain unchanged.

- English/Macedonian citizen guidance, map and six confirmed disposal flows.
- Walking, direct driving, scheduled JSP buses and optional parking-assisted driving.
- Optional post-trip container observations; full assets are immediately excluded
  for everyone for up to 12 hours, with reviewer rejection and expiry.
- Population-weighted City coverage and prepared upgrade scenarios.
- Optional accounts, material-only activity and self-reported badges.
- Hash-pinned development-v3-audit suggestion heads for each language. Policy,
  exact-item confirmation and asset acceptance remain authoritative.

Start locally with `uv run python scripts/run_local.py`. Route planning requires
`SRA_ORS_API_KEY`; optional photo analysis requires `OPENAI_API_KEY`. Both belong
in ignored `.env` or server configuration. See [README.md](README.md).

## October 17 maintenance audit

Renamed the app, documentation, package and API to Najdi Frli; removed the stale
walkthrough asset and its links. Current contracts are consolidated, with dated
evidence retained in the history documents. Fixed private-response caching,
malformed photo output, blocking image preprocessing, ambiguous JSP calendars,
reviewer/report races, duplicate photo retries and relative launcher configuration.
Docker now includes only the current serving heads.

Local checks passed: 757 backend tests (two OS-dependent symlink skips), 21 Node
tests, 46 distinct focused browser cases, lock/lint/format checks and deployment
smoke with both real language models. See [QUALITY.md](docs/QUALITY.md) for scope
and the [Actions workflow](https://github.com/VikiShmiki/meowchine-learning-repo/actions)
for the full Linux/browser/container gate on each revision.

## Earlier merged baseline

[PR #4](https://github.com/VikiShmiki/meowchine-learning-repo/pull/4) merged at
`c626c8d`. Its [successful CI run](https://github.com/VikiShmiki/meowchine-learning-repo/actions/runs/39031926188)
passed 737 backend tests, 429 browser cases, 21 Node tests and the Docker smoke gate.
This evidence belongs to that revision; later changes must pass their own checks.
The local app also loaded both v3 audit language models. CI is active in this
private repository; upstream account restrictions are historical.

Live October 17 checks exercised JSP/ORS and parking/ORS integration using public
test coordinates. They do not establish live arrivals, vacant parking spaces or
physical site access. See [TRANSIT.md](docs/TRANSIT.md) and [PARKING.md](docs/PARKING.md).

## Remaining boundaries

- Native Macedonian review and independent user/model evaluation are outstanding.
- Source dates, unknown operating/access status and policy evidence holds remain
  visible. The parking snapshot needs refresh before its 90-day freshness limit;
  JSP calendars refresh through the runtime feed cache.
- Hosted deployment, iPhone testing and Home Screen installation are user-deferred.
  Desktop browser checks and Docker smoke are not physical-device verification.
- Public voting, correction-feedback training, account recovery and live vehicle
  tracking are not implemented. Accounts and badges are not production identity
  or verified reward infrastructure.

See [QUALITY.md](docs/QUALITY.md) for checks, [DELIVERY_PLAN.md](docs/DELIVERY_PLAN.md)
for scope and [STATUS_HISTORY.md](STATUS_HISTORY.md) for dated implementation notes.
