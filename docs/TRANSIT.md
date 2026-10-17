# JSP journeys

Added October 17, 2026. Choose **JSP bus** beside Walking and Driving. Leave departure
blank for now, or choose a time in the browser's local timezone. The itinerary shows
all scheduled times in **Europe/Skopje**, walking directions, bus numbers/headsigns,
boarding and exit stops, transfer waits and collection stops. Blue solid lines show
published bus shapes; green dashed lines show ORS walking routes. The existing
drop-off, optional check-in and immediate full-container exclusions also apply.

## Feasibility and source evidence

The [JSP website](https://skopjebus.mk/mk/),
[timetable page](https://skopjebus.mk/mk/schedule/) and
[line viewer](https://skopjebus.mk/mk/app/lines/) are available. Mobility Database
[identifies the official JSP feed](https://mobilitydatabase.org/feeds/gtfs/mdb-3045),
served by Modeshift at the fixed HTTPS URL in `transit_feed.py`. It requires no key.
The October 17 download contained 83 bus routes, 1,294 stops, 2,732 trips and 70,300
stop times. Its actual service calendars covered October 17–27; `feed_info` claimed
a later end date. The planner trusts calendars and exceptions, not that broader claim.

These are **scheduled journeys, not live arrivals or vehicle tracking**. Delays,
cancellations, fares, accessibility and stop entrances are not verified. A
[realtime feed listing](https://mobilitydatabase.org/feeds/gtfs_rt/mdb-3067) exists,
but realtime integration is outside this version. Follow the linked JSP notices.

The audit did not establish an explicit redistribution license. Real archives stay
in ignored runtime storage; none are bundled or committed. Tests use independently
authored synthetic timetables. Recheck terms before redistributing a feed snapshot.

## Planning contract and limits

- Full, closed and otherwise excluded assets are removed before shortlisting,
  using the same exact-item acceptance rules as other modes. All items must be
  covered; partial baskets are never returned as successful trips.
- Reuse up to three nearby compatible sites per item. Select the earliest next
  drop-off greedily. This bounded heuristic can miss a different feasible order;
  it is not an exhaustive city-wide or globally optimal journey search.
- Search up to three nearby boarding stops at the origin and two at each candidate,
  within 1,200 m straight-line discovery distance. ORS verifies actual directed
  walking connections, each limited to 15 minutes; distance alone never creates a path.
- Search one bus or one same-stop transfer per collection leg. Allow two minutes
  before boarding/transferring. Final walking directions must preserve at least one
  minute before departure or the itinerary fails with an explicit replan message.
  Walking transfers between different stop IDs are not searched.
- Include waits and three minutes at intermediate drop-offs. End at the last
  collection site. A short walking-only solution is identified explicitly.
- Search a four-hour journey window, departures up to seven days ahead and only
  dates represented by actual service calendars. Overnight GTFS times, exceptions
  and daylight-saving transitions follow the
  [GTFS service-day definition](https://gtfs.org/documentation/schedule/reference/).
- Use published bus shapes only when their stop alignment is credible. Bad or
  missing shapes leave a textual ride with an explicit warning, never an invented
  connector. API distances omit rides without shapes; the UI emphasizes elapsed
  time rather than presenting an incomplete distance total.

## Configuration, budgets and failure handling

Set `SRA_ORS_API_KEY` in the ignored root `.env` and restart the server. No JSP or
OpenAI key is needed for the timetable itself. ORS receives origin/candidate/stop
coordinates for walking, never waste descriptions. The server downloads the same
public timetable regardless of a user's location. It does not save trip histories.

The one-hour runtime cache is `runtime/jsp-gtfs.zip`. Responses identify feed
version, fetch timestamp, service end and source URL. Expired cache is not served
after a failed refresh. Failed downloads back off for 60 seconds. Downloads have
a 10 MB compressed / 80 MB expanded limit, fixed URL, bounded HTTP/decode handling
and atomic cache replacement. Duplicates, orphan routes/services, invalid stop
coordinates/times and unsupported frequency/transfer tables fail closed. An entire
invalid shape is quarantined while its valid timetable remains usable.

Each plan uses one walking matrix (at most 58 points / 3,364 cells) and up to 12
walking directions calls for six drop-offs. The existing two-concurrent / 20-starts
per-minute process budget and daily/client quotas apply. Planning checks a 50-second
elapsed deadline between operations; a current HTTP operation may finish afterwards.
The browser cancels after 75 seconds. ORS has its own bounded request timeouts.
No automatic provider retries or straight-line walking fallback are used.

Missing keys, failed/invalid/stale feeds, no scheduled service, disconnected walking,
missed connections and quota errors produce actionable failures. Changing origin,
basket, mode or departure invalidates pending/previous results. Opening the page or
selecting bus mode does not send coordinates or download the feed.

## Verification

Deterministic tests cover direct buses, transfers and missed connections, after-midnight
service, calendar exceptions/DST, corrupt/expired feeds, bad shapes, pickup restrictions,
directionality, disconnected walking, multi-item drop-offs and walking-only journeys.
Seven real-page cases exercise both languages at 320/390/1280 px, map geometry,
completion/check-in, another visitor's full exclusion, outage/retry and input changes.
Map tiles and external services use fixtures in automated tests.

A live request on October 17 used public coordinates at Skopje Transport Center and
returned ORS walking plus JSP **18 and 8** to Karpoš recycling yard, approximately
92.4 minutes including its scheduled wait and transfer. This verifies the provider
integration; it is not a completed bus ride, real-time arrival or field-access audit.
Reproduce (uses the configured ORS quota and the current timetable):

```sh
uv run python scripts/smoke_transit.py --live
```

See [QUALITY.md](QUALITY.md) and [CI_STATUS.md](CI_STATUS.md) for delivery gates.
Native Macedonian review, actual phone testing and public deployment remain deferred.
