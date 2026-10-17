# Community reports and usage protection

User-approved mentor follow-up. One FastAPI service, one SQLite database, one worker.
Optional accounts and self-reported badges are described in [ACCOUNTS.md](ACCOUNTS.md).
No municipal submission integration or live Pakomak feed.

## Run locally

`uv run python scripts/run_local.py --env-file /path/to/your/.env`

The launcher binds only to 127.0.0.1. It creates an ignored `runtime/reviewer-key.txt`
if `SRA_REVIEW_TOKEN` is unset. Open `/review`, paste that key, then Lock when done.
The browser keeps the key in memory only; it is never placed in URLs or browser storage.
Do not share/commit the key or database. Source `.env` files are not modified.

For direct uvicorn/deployment, set `SRA_REVIEW_TOKEN` to a random secret of at least
32 characters. Without it, review APIs fail closed. This shared reviewer secret is
a prototype moderation gate, **not user registration or production role management**.

`SRA_COMMUNITY_DB` defaults to `runtime/community.sqlite3`. Mount persistent storage
for deployment; do not put it in the image or use an ephemeral filesystem. The
SQLite implementation is for a single instance. Multiple replicas need shared
storage/coordination and distributed concurrency limits before deployment.
Use HTTPS for deployment, body/request timeouts at the proxy, and explicitly trusted
proxy IPs. Never accept arbitrary client-provided forwarded IP headers. Client quotas
use the ASGI peer address; users on the same network can share an allowance.

## Behaviour and trust

- Anonymous visitors receive a signed, HttpOnly, SameSite=Strict cookie (one day;
  Secure on HTTPS). A pseudonymous browser identifier owns pending reports.
- A full report immediately excludes that container from everyone's new routes,
  without a photo or prior approval. It is labeled an unreviewed community report,
  not verified live telemetry. Reviewers can reject/mark duplicate a false report.
  Pending damaged/inaccessible reports affect only their reporter until approved.
  Cookie deletion does not remove shared full reports or reset network usage limits.
- Review accepts available/full/inaccessible/damaged. Full expires after 12 hours,
  inaccessible after 24, damaged after 72, available after 12, measured from submission.
  The newest unexpired approved report or pending full report wins. A newer reviewed
  available report can supersede an older full report. Newer personal negative
  reports can override the shared status only for that reporter. Unreviewed positive
  reports cannot reopen a shared problem, and no report can reopen a source-closed
  container. A reviewed availability observation resolves older warnings even after
  that clearance expires; those resolved warnings cannot return. An expired full
  report does not resolve a separate, still-current damaged/inaccessible report.
  With no unresolved active observation, current condition is unknown. Pending
  positive reports cannot erase personal negative observations either.
- Conditions are asset-scoped, not site-scoped. Filtering happens before the nearby
  shortlist and provider matrix. The existing bounded-shortlist optimizer remains;
  this is not a newly claimed city-wide best route.
- Route responses carry a status revision. Statuses are rechecked before responding;
  changed used assets yield 409. Visible clients refresh statuses every 30 seconds
  and on return to the tab, and mark affected routes stale. Replanning is explicit,
  not an automatic loop of paid calls. Users choose their origin and can mark a
  stop's assigned items dropped off. Signed-in users can save self-reported history
  and badges; no recycling verification or monetary reward is implied.
- No alternative returns an explicit error; no waste is silently omitted.
- Container conditions are in the route-stop and map-details disclosures. Source
  status remains distinct from current community reports.

## Container refresh decision (2026-10-17)

Use community observations now, with collection schedules as future context once
verified for the exact assets. Street cleaning, planned waste collection and an
observed empty container are different events.

| Approach | Benefit | Limitation and decision |
| --- | --- | --- |
| Scheduled resets | Work without many users | A planned visit may be missed and may cover another waste stream. Never mark available from a clock. |
| Anonymous majority voting | Could clear stale warnings quickly | Browser cookies are not independent people; repeated identities and coordinated votes can defeat a small threshold. Do not auto-clear from vote counts. |
| Observations, expiry and review | Works with existing data and preserves provenance | Review can delay recovery. Keep bounded warnings, invite fresh observations and label unknown conditions honestly. |

Evidence checked on October 17, 2026:

- [Komunalna Higiena's service overview](https://khigiena.com.mk/channel/?id=1)
  describes seven-day, three-shift container collection and twice-weekly household
  bin service. It does not give a current time for an individual recycling asset.
- [Pakomak's FAQ](https://pakomak.mk/FaqItems) identifies Komunalna Higiena as the
  operator emptying Skopje's igloo containers. That establishes responsibility,
  not completion of a collection visit.
- The utility's [operational programme](https://khigiena.com.mk/download/?f=OPERATIVNA+PROGRAMA.pdf)
  is explicitly for **2019**, despite recent search indexing. Its material-specific
  frequencies are historical and must not become a 2026 timetable.

No current asset-specific collection timetable or completed-service feed was
verified in this research. The existing 12-hour full/available, 24-hour inaccessible
and 72-hour damaged lifetimes are application policy, not measured cleaning cycles.
Do not extend them from the historical programme.

Implemented refresh behavior: active observations expose their validity end time.
Expired observations appear separately as **Needs a fresh check**, with the last
condition/time and an explicit unknown-current-condition message. They do not block
routes or count as availability evidence. The existing 30-second visible-page
refresh updates this state; a successful refresh also enables another observation
after that form's previous submission expires. Network failures can delay display
refresh; route planning always rechecks server state. Existing 30-day retention,
private pending reports, moderation and quota controls apply to stale context too.

Before adding schedule context, obtain an operator-approved asset/material mapping,
service windows in Europe/Skopje, effective dates, exceptions, source/version and
refresh permission. A scheduled visit should prompt a recheck, never clear a full,
damaged or inaccessible warning. An authenticated completed-service record could
support a fullness update after mapping and freshness validation; it would not
prove damage repaired or access restored. Operator outreach is a next step, not an
implemented integration, and no messages have been sent on the user's behalf.

## Stop check-in

Route cards use the map's stop numbers and the waste picker's material colors.
Multi-material stops keep each assigned color. Each card offers **Dropped off** and
**Report a problem**. Dropping off opens an optional **Still space / Full** popup;
reporting a problem offers **Full / Damaged / Blocked** without completing the stop.
Each tap sends one observation for the identified container. Stops with several
containers ask about each separately; Skip or Escape dismisses the remaining check.
Nothing is reported just by completing, ending, or skipping a trip.

Multi-stop routes remain open after individual drop-offs. The final drop-off ends
the route automatically. **Finish trip** ends early and preserves remaining basket
items. There is no second questionnaire at the end. Account-save failures preserve
items and allow retry or explicit completion without saving.

Successful reports disable the choices and advance to the next container; failures
keep the current container available for retry. An older status read or failed
refresh cannot undo a successful report. Full reports immediately affect routing;
positive observations still require review. Existing quotas, moderation, expiry,
and duplicate suppression apply. Check-in state stays in page memory; no photo,
GPS attendance proof, or stored location history is added.

## Dumping reports

City coverage only: `Community reports`. Recycle retains container-condition
reporting and rerouting, with no duplicate dumping form. Select a map point or enter
coordinates, describe the issue, and optionally attach a photo. Coordinate bounds
41.8–42.2 N, 21.2–21.7 E are a coarse Skopje prototype envelope, not municipal boundaries.
Reports are pending until reviewer approval. Approved/cleared reports appear in a
separate map layer; reject/duplicate hides them. They never become route destinations
and never silently change prepared City coverage percentages or upgrade suggestions.

Photos are reviewer-only, even after approval. JPEG/PNG/WebP only, 5 MB input maximum,
16 MP maximum decoded dimensions, resized to at most 1280 px and re-encoded to JPEG
without EXIF. Two concurrent uploads, 20-second timeout, 64 MiB total stored photo cap.
If upload fails, the text report remains saved and the UI offers photo retry.
Names, descriptions and other user text render as text, not HTML. Do not submit faces,
private details or private home locations. Public map coordinates are intentionally
published only after review; trip starting coordinates are not retained.

All reports and photos are deleted after 30 days on database access. Expired container
reports cease affecting routes earlier. SQLite secure-delete is enabled. There is
no external archival/backup integration. Repeated identical submissions by one visitor
within five minutes reuse the existing pending report.

## Allowances

Persistent counters reserve requests atomically before calling providers. UTC fixed
hour/day windows; failed attempts count conservatively. Limits survive restart.
Network pseudonyms rotate daily using an HMAC secret stored in the database; raw IPs
are not stored by this feature. Deployment access logs need a separate privacy policy.

| Service | Global/day | Per network/day | Per network/hour |
| --- | ---: | ---: | ---: |
| Vision | 100 | 10 | 5 |
| Routing | 500 | 100 | 30 |
| Reports, including photo uploads | 500 | 30 | 10 |

Provider limits use `SRA_VISION_DAILY_LIMIT`, `SRA_VISION_CLIENT_DAILY_LIMIT`,
`SRA_VISION_CLIENT_HOURLY_LIMIT`, and equivalent `SRA_ROUTING_*` variables.
Zero disables paid requests for that service. These are **request allowances, not
dollar billing caps**. Vision output is separately bounded to 800 tokens; a route
normally makes one matrix and one directions call. Two vision calls may run at once;
existing routing concurrency/twenty-per-minute safeguards remain. Manual classification
and waste selection remain usable when paid allowances are exhausted. Cookie resets
cannot bypass network/global caps. Distributed bots can still exhaust availability;
edge protections and stronger identity are needed before a wide public launch.

## API and tests

- `GET /api/v1/container-statuses`: personalized current overlays, separate expired
  `rechecks`, and active-overlay revision, no-store.
- `POST /api/v1/container-reports`: asset_id and condition, returns pending report.
  A pending `full` report already affects public route eligibility; status source
  `community_report` distinguishes it from `reviewed_community` and `your_report`.
- `POST /api/v1/dumping-reports`: latitude, longitude, description.
- `POST /api/v1/dumping-reports/{id}/photo`: raw image owned by current visitor.
- `GET /api/v1/dumping-reports`: approved/cleared points, never photos/identities.
- `GET /api/v1/review/reports`, `PATCH /api/v1/review/reports/{id}` and
  `GET /api/v1/review/reports/{id}/photo`: Bearer reviewer key required.
  Review states: approved, rejected, duplicate, cleared (dumping only).

`tests/test_community.py` covers persistence, atomic limits, visitor separation,
moderation, expiry/retention, image privacy, origin/body validation and asset-level
walking/driving routing. `tests/test_community_browser.py` covers report → reroute,
origin changes, dumping → private upload → approval → City map, reviewer lock and
network failure recovery. Tests isolate their database and mock paid providers;
test-only high quotas do not change production defaults.

Audit hardening: database schema initialization occurs once per store path. Reads
check expiry without obtaining a writer lock when nothing has expired; deletion-on-
access retention is preserved. Async HTTP middleware and upload/provider allowance
paths offload synchronous database work to the thread pool. Container configuration
runs as an unprivileged app user; mounted runtime storage must be writable by it.
The container runtime remains unverified until a Docker daemon is available.
