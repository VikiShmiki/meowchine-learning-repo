# Najdi Frli status

Updated: 2026-10-17

## Current application

The public repository's `main` includes Oliver's ML remediation and the container
check-in, JSP bus and parking integrations. The product is named **Najdi Frli**;
the repository URL, Python imports and `SRA_*` settings remain unchanged.

- English/Macedonian citizen guidance, map and six confirmed disposal flows.
- Walking, direct driving, scheduled JSP buses and optional parking-assisted driving.
- Optional per-stop container observations; full assets are immediately excluded
  for everyone for up to 12 hours, with reviewer rejection and expiry.
- Population-weighted City coverage and prepared upgrade scenarios.
- Optional accounts, material-only activity and self-reported badges.
- Hash-pinned development-v3-audit suggestion heads for each language. Policy,
  exact-item confirmation and asset acceptance remain authoritative.

Start locally with `uv run python scripts/run_local.py`. Route planning requires
`SRA_ORS_API_KEY`; optional photo analysis requires `OPENAI_API_KEY`. Both belong
in ignored `.env` or server configuration. See [README.md](README.md).

## Published presentation

The hackathon presentation is available at
https://vikishmiki.github.io/meowchine-learning-repo/. Its self-contained source is
`index.html`; GitHub Pages publishes from `gh-pages`. The application service
remains locally hosted.

## October 17 maintenance audit

New app identity: a generated recycling-loop/location-pin icon replaces the
header arrow in Recycle and City coverage. Matching browser-tab and Apple touch
icons are linked on all three pages. Source artwork and generation prompt are in
`assets/brand/`; web-size exports are in `web/brand/`. All 12 bilingual header
layout checks pass at 320, 390 and 1280 px; the mobile preview and small-size
exports were visually inspected.

Trip reporting now uses numbered, material-colored cards with two actions:
**Dropped off** and **Report a problem**. Drop-offs open a small optional
**Still space / Full** dialog, one identified container at a time. The old visit
checkbox and end-of-trip questionnaire are removed; account-save recovery and
report moderation remain intact. Mobile (360 px) and desktop (1100 px) previews
were inspected, including the Macedonian popup. `make check` and the affected
browser suites pass (trip check-in, community, accounts, transit, parking,
Macedonian and system journeys). The final system/account rerun passed 63 cases.

Container freshness follow-up: expired observations now appear as **Needs a fresh
check**, separate from routing exclusions. Reviewed clearances cannot expire back
into a resolved warning; expiry of a full report does not erase still-current
damage. Unreviewed positive reports cannot erase a personal warning. Validity times
and review requirements are visible in English
and Macedonian. Research found broad operator frequencies and a 2019 programme,
but no verified current asset-specific collection timetable. Scheduled resets remain
disabled; see [COMMUNITY.md](docs/COMMUNITY.md) for evidence and integration criteria.

Follow-up validation: `make check` passes with 769 Python tests, 441 opt-in browser
skips, and 21 Node tests, plus lock/lint/format checks. Nine focused store cases
cover renewal, clearance, unresolved damage, privacy, rejection and retention; an
API regression covers the separate stale-context response. The HPC sandbox stalls
the threaded API test client; the complete suite passes outside that sandbox.
Chromium initially lacked host libraries; isolated dependencies under `/tmp` now
allow local browser checks without changing the host installation.

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
public repository; upstream account restrictions are historical.

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
