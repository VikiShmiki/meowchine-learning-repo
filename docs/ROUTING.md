# Citizen trips

Select known waste directly using the six material cards, then **Add to route**
to confirm condition and add the selected streams together. Every selected card has
the same green outline/checkmark. Optional text/photo help still uses item-level
review and confirmation; electronics can use documented accepting centres, while
other specialist items receive disposal guidance. Select a
starting point and Walking, Driving or JSP bus, then **Find my route**; the adjacent disclosure
explains coordinate sharing. Up to six basket entries are supported. Trips finish
at the last collection point, with no final return leg. Driving optionally offers
**Park and walk to drop-offs**: park at a mapped public location and walk to the
container, returning to the car between stops. The final walk back is excluded and
the car's final location is shown. See [PARKING.md](PARKING.md) for the source,
unknown space availability, walking limits and separate provider budget.
Mark each visited stop explicitly or use **Dropped these off** after disposal.
Individual drop-offs keep a multi-stop route open; the last drop-off ends it.
**Finish trip** ends early without marking remaining items disposed. Both endings
clear the route and offer an optional status check-in for visited containers only.
Reporting a container full immediately excludes that asset from everyone's new
routes for up to 12 hours; other assets at the same site stay eligible. Existing
routes show a change notice on the next status refresh and offer explicit replanning.
See [COMMUNITY.md](COMMUNITY.md) for expiry, review and privacy behavior.
Electronics offers an optional "Only phones, chargers, cables or earbuds" selection.
That subset can use Karpos or East Gate Mall; unchecked generic devices remain
Karpos-only. East Gate routes end at the mall entrance, with a visible instruction
to ask the information desk for the collection point. Nula Otpad is a pickup service,
not a third route destination.
The basket displays a selection count, not progress toward the six-entry API limit.
That limit is explained only if reached; it does not represent six waste categories.
Both location methods begin as neutral actions. A chosen point replaces them with
a compact summary and Change action; coordinates/accuracy are in Location details.
Change opens the editor without discarding the existing point or completed route.
Keep current point cancels the edit; clearing is available inside the editor only.
Route submission is disabled while editing, and late GPS callbacks cannot replace
a newer map/manual choice. Location data remains memory-only.
A ready trip focuses the map on the route and numbered stops; other sites are hidden
until explicitly enabled. Fit-route, edit-trip and stop-details controls remain visible.
Walking routes use a dashed green line; driving routes use a solid green line.
Both retain a white contrast outline, and the in-map key mirrors the travel mode.
Stop numbers on the map and in the itinerary use assigned drop-off colors: glass
gold, plastic/metal green, paper/cartons blue, general waste gray, electronics teal,
clothes donation mauve. Exact item kinds
map to the same palette as quick-pick streams. A stop assigned multiple streams uses
those colors around a neutral number; it does not introduce a mixed-waste category.
The material legend stays visible with routes; fit-route leaves room for both
keys on small screens. The unused purple mixed-material entry has been removed:
every site in the current City snapshot has just one recorded material stream.
Editing the basket, origin or mode clears the old route and cancels stale
responses. The existing site search remains limited to five matches after two characters.

## Matching and optimization

The server revalidates every description/confirmation against the serving policy.
Recycling streams require explicit acceptance for all supported stream subtypes on
one asset, not a union of unrelated capabilities. Closed assets are excluded;
unknown operation is allowed with a visible warning. Hazardous, held and unsupported
description-based items block the whole trip; no partial or automatic general-waste
fallback is returned.

Explicit general-waste selection is a separate recorded-bin navigation mode. It
requires condition confirmation and an explicit API opt-in to unverified acceptance,
which the UI sends for a selected general-waste stream. It matches recorded
mixed-municipal-waste drop-off containers only. The warning appears at general-waste
route stops, not in the selection panel. This supports general alone
or mixed baskets such as glass + general, in all three travel modes. It does not create
an acceptance profile or establish permission to dispose of hazardous, medical or
bulky waste. Confirmed `ordinary_residual` items use those same recorded bins;
electronics matches only assets explicitly accepting `electronics`, never all specialist
waste. See [bounded guidance and evidence](GENERAL_AND_ELECTRONICS.md).
City coverage/upgrade calculations and original training/evaluation review holds are unchanged.

For direct walking/driving, choose the three nearest compatible source sites per
unique item type by straight-line distance, then deduplicate (at most 18 candidates).
This is a heuristic shortlist,
not a city-wide optimum. ORS supplies a directed travel-time matrix including the
origin. Null/unreachable edges and candidates snapped over 100 m are excluded.
A shortest-path search over (covered item types, last site) minimizes matrix travel
time until all types are covered. Stops are deduplicated; tiny cases are checked
against exhaustive enumeration. The objective excludes parking and disposal time.

One directions request supplies actual network geometry for the selected order.
Walking uses `foot-walking`; driving uses `driving-car` with `continue_straight`.
Mode/access/turn restrictions are delegated to ORS, not our T04 diagnostic graph.
Matrix costs do not carry arrival-direction state between stops; final directions
may therefore differ from the summed matrix estimate. Reported totals come from
final directions. ORS's hosted graph version is independent of the pinned T04 extract.

## Provider and privacy

Set `SRA_ORS_API_KEY` locally in the ignored project-root `.env`, or in the server
environment, then restart. Existing environment variables override `.env`.
The key is server-only; configuration responses expose only whether it is set.
Do not commit the file or paste the key into issues, logs or chat.

Only clicking **Find my route**, beside its coordinate-sharing disclosure, sends
origin and candidate coordinates through our API to ORS. Item descriptions go to
our API for policy checks, never ORS. Application
logs contain request ID, mode, outcome, duration and dataset version, not coordinates,
descriptions or credentials. Trip responses, including validation errors, use
`Cache-Control: no-store`; basket/origin/geometry remain in memory only.

Walking/direct driving use at most one matrix and one directions request per plan;
parking-assisted driving uses at most two matrices and twelve directions requests.
There are no automatic retries. Parking uses a 75-second client timeout.
JSP uses a bounded walking matrix and up to 12 walking directions requests, with
a 75-second client timeout. See [TRANSIT.md](TRANSIT.md) for scheduled journeys,
source freshness, transfer/walking limits and the different optimization objective.
The process permits two concurrent plans and 20 starts/minute. This is a prototype budget,
not a distributed quota or account daily-limit guarantee. Provider requests use
10-second HTTP timeouts, a 2 MB response cap and a 12-second elapsed budget checked
between streamed chunks. For direct walking/driving, the client cancels after 40
seconds; cancellation does not guarantee an already-started server/provider request
stops. Quota/auth/network/invalid
response failures are explicit. No invented route or straight-line fallback is used.

Official contracts consulted for this integration:
- https://giscience.github.io/openrouteservice/api-reference/endpoints/matrix/
- https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/requests-and-return-types
- https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options
- https://openrouteservice.org/restrictions/

## Access limitations

Network endpoints can be up to 100 m from recorded sites. These gaps are measured
and displayed, but entrances, barriers and legal off-network access are unverified.
No straight connector is presented as a traversable path. Time/distance exclude
these gaps, parking, live traffic and disposal time. Site operation and local policy
human review remain unverified. Follow local access signs and container instructions.

Malformed geometry, missing waypoints/segments, skipped-route warnings and excessive
snapping fail closed. ORS warning code 4 (unavailable additional road-access metadata)
is accepted with a visible disclosure; other warnings are rejected. This metadata
warning is not evidence that every local restriction has been independently verified.

## Verification and reproduction

Normal unit/browser tests use mock provider responses and require no key. Coverage
includes directed optimum, disconnected baskets, exact asset acceptance, hazardous
manual-override rejection, profile selection, quota/auth/timeouts, malformed data,
access gaps, no-store errors, consent, stale UI results and missing configuration.

Opt-in live test with fixed public coordinates, never a personal location:

```bash
uv run python scripts/smoke_routing.py --live
```

Default report is ignored `runtime/routing-live.json`. On 2026-09-20, a three-material trip
from 41.9965, 21.4314 returned three stops: walking 2477.4 m / 1783.7 s; driving
3127.7 m / 556.8 s. Nine candidates were considered. A Maksim Gorki one-way probe
(OSM way 360141020 in the pinned extract) returned walking 78.4 m in each direction,
driving 78.4 m forward and 642.5 m reverse. This is a concrete directionality spot
check, not an exhaustive audit of turn restrictions or entrances.

A live Edge browser at 390 x 844 completed a two-item walking trip through the real
backend/provider (2.16 km, 26 min, two stops), with no horizontal overflow. Only map
tiles were fixtures. All 126 Python/browser tests and nine JavaScript cases passed.
Physical iPhone/Safari, hosted capacity and installation remain T10 gates. City Mode
coverage and upgrades remain T08/T09; no coverage result is claimed here.


## Citizen interaction pass

Known streams need only card selection and condition confirmation, without a classifier
request or subtype menu. Uncertain items still require choosing the type in the helper.
Confirmation failure preserves the choice for retry; stale responses after
an edit cannot add items. Repeated identical descriptions/types do not duplicate the
basket. The six-item cap explains how to recover. Add another clears/focuses the input.
Route planning is disabled until basket, origin and provider configuration are ready,
with a next-step explanation. Switching mode is one radio selection. A routing
connection failure can be retried without reloading or losing the basket.

Map selection presents nearby center/cancel controls and returns to trip setup once
selected. Cancel preserves any existing trip. Delayed map initialization draws an
already-completed route without resetting the origin/trip. Numbered stops open their
matching details. Retry-map controls appear only after tile failure. Mobile/desktop
browser checks use fixture routes/tiles; physical iPhone verification remains pending.
