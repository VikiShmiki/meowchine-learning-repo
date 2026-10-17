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
  container. Expiry without another current report means unknown, not available.
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

## End-of-trip check-in

Route stops offer **I visited this stop**, **Dropped these off**, and **Report a
problem**. Marking a drop-off also marks that stop visited. Multi-stop trips remain
open after individual drop-offs, and **Finish trip** lets a resident end early.
The last drop-off ends the trip automatically and clears its route from the map.
Ending early preserves uncompleted basket items and does not award drop-off activity.

After completion, the optional check-in lists only containers at explicitly visited
or completed stops, deduplicated across replans. Each container starts at **Didn't
check / skip**; nothing is submitted automatically. Residents choose a condition
and send each report, or dismiss the remaining check-in. The same report endpoint
is used during and after a trip; full reports take effect immediately for everyone.
No container-photo upload or GPS attendance proof is required. Visit/check-in state
stays in page memory and is cleared when the trip ends; it is not a stored location
history. Refreshing or leaving the page loses that unfinished trip state.

Successful reports cannot be submitted twice from the same form. A failed submission
keeps the selection for retry; server-side duplicate suppression remains in force.
A failed status refresh after a successful submission does not turn it into a failed
report. Existing quotas, moderation and expiry remain active; photos for separate
dumping reports are unchanged.

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

- `GET /api/v1/container-statuses`: personalized current overlays + revision, no-store.
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
