# Leaflet 1.9.4

Vendored from the URLs published by https://leafletjs.com/download.html:

- https://unpkg.com/leaflet@1.9.4/dist/leaflet.js
- https://unpkg.com/leaflet@1.9.4/dist/leaflet.css
- License: https://raw.githubusercontent.com/Leaflet/Leaflet/v1.9.4/LICENSE

Verified SHA-256 (base64) against the official download page:

- JS: `20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=`
- CSS: `p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=`

BSD 2-Clause license retained in LICENSE. The application uses circle markers and
no layer switcher, so no icon images are needed. Add the upstream images if those
controls are introduced. Source maps are not shipped. The client library is served
locally; only the configured tile provider receives external map requests.
