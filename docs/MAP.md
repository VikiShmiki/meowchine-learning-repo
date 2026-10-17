# City site discovery (T06)

The citizen page renders all 1,583 City site groups from `/api/v1/sites?scope=city`.
The separately scoped metro asset is not silently mixed in. Leaflet 1.9.4 is pinned
and served locally with its license and verified upstream checksums.

## Behavior

- Material filters and name/address/municipality search update markers and the
  keyboard-accessible search results. Results appear after two characters, with at
  most five matches and a prompt to narrow broad searches. There is no browse-all
  list or pagination, including on map failure. Changed filters fit the matching sites.
  Specialist filtering is an explicit empty state because no facility is verified.
- Site details retain each asset's material capability, acceptance limits, source,
  observation date, unknown operating status and QA flags. No site's material union
  broadens another asset's acceptance. This is discovery, not item-to-site matching.
- Starting points can come from opt-in geolocation, a deliberate map click, keyboard
  map-center selection, or validated coordinates. The list sorts by Haversine
  straight-line distance; this is never called walking/driving distance or a route.
- Device location reports its accuracy. Denied/unavailable/timed-out location has
  manual recovery. A late location callback cannot replace a newer manual origin.
- Origin stays in memory and disappears on reload/clear. Only explicit trip consent
  and planning submit it to our API and openrouteservice; site browsing does not.
  Routes draw provider network geometry and numbered stops; access gaps remain
  unverified. See [ROUTING.md](ROUTING.md). Tile requests disclose the viewed area to the tile provider. No geocoder is used.

## Trip focus

The page orders item confirmation, basket/origin setup, then map/stops. Manual
coordinates are expandable. Planning a route scrolls to the map and hides discovery
markers by default, retaining the origin, provider geometry and numbered stops.
A summary shows mode/distance/time; controls fit the route, edit the trip, show stop
details or explicitly show other collection points. Filters do not refit an active
route. Changing/clearing the trip restores discovery; search remains capped at five.
Map animations are stopped before route framing so an earlier origin zoom cannot
replace the route view. The 11th browser case covers focus, opt-in sites and reset.

## Data, caching and failures

Same-origin Cache Storage retains only the City snapshot, with ETag revalidation.
Invalid schemas, synthetic records, wrong scope and invalid/duplicate site records
are rejected. Network/body reads time out after 12 seconds. Refresh failure retains
the last valid snapshot and prominently labels its source date; no cache produces
an actionable error and retry button. Storage restrictions do not prevent live use.

Leaflet/configuration failure leaves search and manual coordinates usable. Tile
failure has its own message and retry action. Site-data availability does not imply
base-map availability. No service worker, offline page installation, tile archive
or offline map promise is introduced.

## Provider configuration

`web/map-config.json` controls tile URL, attribution, initial center and zoom limits.
Defaults use https://tile.openstreetmap.org/{z}/{x}/{y}.png and visible attribution.
Browser caching and Referer are preserved. No prefetch/bulk download is implemented;
OSM tiles are best-effort. Rechecked against the official policy on 2026-09-20:
https://operations.osmfoundation.org/policies/tiles/

Before public deployment, recheck provider capacity and dataset publication flags.
The existing source reuse/human-review holds remain; T06 does not grant approval.

## Verification

`make check` includes nine JavaScript controller/domain scenarios and Python tests.
Install a browser and run the explicit real-page gate (also required in CI):

```bash
uv run playwright install --with-deps chromium
SRA_BROWSER_TESTS=1 uv run pytest tests/test_web_browser.py
```

On Windows, set `$env:SRA_BROWSER_TESTS='1'`. An installed Edge can be selected with
`$env:SRA_BROWSER_CHANNEL='msedge'`. Tests start their own temporary local server and
use fresh browser contexts. They mock tiles to avoid automated public tile traffic.
Ten browser cases cover trip consent, baskets, mode changes, stale responses,
provider failures and missing configuration, alongside actual City data, filters/details, empty results, mobile
overflow, manual/map/device origins, denied/stale geolocation, cache/refresh failure,
tile/library failure and T05 clarification/specialist flows. Local Edge verification
at 390×844 passed; screenshots use neutral fixture tiles, not the live OSM base map.
This is browser evidence, not physical iPhone/Safari or live-provider sign-off.


The interaction pass keeps map-center/cancel actions beside the map while selecting
an origin and returns to trip setup after selection. Discovery markers are hidden
during selection so they cannot intercept taps. Delayed map loading preserves a
ready trip. Route markers focus the corresponding stop details. Tile retry is shown
only after failure; configuration retry preserves the trip basket. Coordinates remain
in memory and are submitted only by the disclosed Plan trip & share location action.
