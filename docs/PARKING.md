# Parking-assisted driving

Driving offers **Park and walk to drop-offs**. It uses mapped public parking in
Skopje, actual ORS driving/walking directions, and the existing item acceptance and
full-container exclusions. Direct driving remains available with the option off.
The itinerary and map identify parking separately from the recycling containers.
Between drop-offs, walking back to the car is included before the next drive.
The trip ends at the last drop-off: the car remains at the final parking location,
and the final walk back is explicitly excluded.

## Feasibility and source limits

The October 17, 2026 audit found official zone/payment information at
[Gradski Parking](https://www.gradskiparking.com.mk/pocetna.nspx),
[parking.mk](https://parking.mk/) and [POC](https://poc.mk/?page_id=167), but did not
establish a documented publicly usable live vacant-space feed. This feature finds
mapped parking; it does not reserve a space or promise occupancy, opening or price.
Every response reports `availability: "unknown"`.

The bundled snapshot derives from the [Geofabrik North Macedonia extract](https://download.geofabrik.de/europe/macedonia.html)
at **2026-10-16T20:21:21Z**, under ODbL. Of 880 mapped parking features within
longitude 21.2–21.6 / latitude 41.9–42.1, 217 explicitly permit public access;
additional access/geometry checks retain **144 parking points**. This is a bounded
inventory, not complete parking coverage. Missing-access, private/customer/permit
parking, conditional restrictions, restricted vehicle/foot access, parking lanes,
underground/multilevel/rooftop parking and disused/closed records are excluded.

Mapped parking nodes retain their coordinates. Areas require a mapped public
driveway crossing; polygon centres are never used. One-way exit-only crossings,
tangencies and boundary overlaps are excluded. Gates, entrances and on-site
conditions remain unverified. ORS validates network connectivity with a maximum
100 m snap gap; each gap is disclosed rather than drawn as a traversable path.
Two nearby points can snap to the same network point: a zero network walk does not
establish direct physical access between them.

Fees, hours and operator names are source tags, not live prices or opening checks.
The UI exposes fees/hours and source links in Parking details, and asks users to
check signs. OSM's [parking](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dparking)
and [access](https://wiki.openstreetmap.org/wiki/Access) contracts define the tags.
Snapshot provenance and licensing are in the [data README](../data/parking/skopje-v1/README.md).
`GET /api/v1/parking` publishes the complete derived database with attribution.

## Search, time and failure contracts

The existing shortlist retains three nearest compatible sites per item type,
deduplicated to at most 18. For each, consider the two nearest eligible parking
points within 800 m straight-line distance. Each actual walking connection must
take at most ten minutes. The exact coverage solver runs over site/parking pairs,
minimizing matrix driving plus walking time within these shortlists, not city-wide.
Each transition includes the previous site's directed return walk. A site without
a routable return walk may only be the final stop.

A final driving request preserves the complete car waypoint order and approach
constraints. Walking directions are requested independently in each direction.
Reported totals come from final directions, including intermediate return walks;
they exclude parking search, payment, disposal, access gaps and the final return.
One driving matrix has at most 37 points (1,369 cells); one walking matrix has at
most 54 (2,916 cells). Up to six stops require one driving and eleven walking
directions calls: **14 provider calls maximum**, with no automatic retries.
Planning checks a 50-second budget between operations; the client waits up to 75
seconds. Individual ORS request limits and shared process/client quotas still apply.

Missing/corrupt/stale parking data returns `parking_unavailable` (503). No viable
combination returns `parking_no_route` (422); a final walking connection exceeding
ten minutes returns `parking_connection` (422). Provider failures retain their
existing codes. Failure preserves the basket and allows retry; it never silently
replaces a requested parking journey with direct driving or straight-line paths.
Changing the parking option invalidates the previous result and pending response.

Origins/candidate coordinates go to ORS only through the disclosed route action.
Parking download needs no user location. Routes remain memory-only and no-store;
precise coordinates and credentials are not written to application logs.

## Refresh and verification

The catalog rejects snapshots older than 90 days or more than one day in the
future. Acquire a current licensed extract, regenerate using the data README,
review its differences and restart the server. Loading is cached; there is no
request-time download or automatic snapshot refresh. Direct driving and other
modes remain usable when the parking snapshot is unavailable.

Normal tests use deterministic providers and require no key. Twenty focused backend
tests cover directed return walks, exclusions, source integrity/freshness, one-way
driveway entry, connection limits and strict API contracts. Seven browser tests
exercise English/Macedonian at 320/390/1280 px, parking markers, full-container
check-in exclusion, failures, retry and switching back to direct driving/walking.

An October 17 live ORS check from public Transport Center coordinates returned a
two-drop-off glass/electronics journey in 2.31 seconds, with 23.4 minutes of network
travel and a 485 m walking connection. This validates provider integration, not
available spaces or field access. Reproduce with a configured server-only ORS key:

```bash
uv run python scripts/smoke_parking.py --live
```

Native Macedonian review and physical-site/phone checks remain separate evidence.
