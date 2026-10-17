# Najdi Frli project brief

Najdi Frli supports correct disposal and access to collection points in Skopje,
in English and Macedonian. Its delivered scope combines item guidance, a real-site
map, multi-item journeys, population-weighted City coverage and upgrade suggestions.
Hosting and physical-phone verification remain user-deferred.

## Citizen journey

Residents can pick a known stream or use text/optional photo guidance, confirm the
item and its condition, then plan for up to six items from a device, map or manual
origin. Walking, driving, scheduled JSP buses and optional parking-assisted driving
are supported. Trips end at the last collection point. Parking journeys include
return walks between drop-offs, but exclude the final return to the car.

The five internal policy categories are `glass`, `plastic_metal`, `paper_tetrapak`,
`general` and `special_unsupported`. Electronics and wearable-clothes donation are
distinct citizen flows with their own item and destination evidence. Learned object
labels and broad map categories do not establish acceptance.

Uncertainty requires clarification or manual selection. Specialist/unsafe signals
cannot be overridden by selecting an ordinary bin. General-waste navigation requires
explicit acknowledgment of unverified acceptance and is never an automatic fallback.
When no compatible destination or route exists, explain the gap rather than invent one.

After a journey, residents may report visited containers without photos. A full
report immediately excludes that asset for everyone for up to 12 hours, subject to
reviewer rejection. Skipping the check-in submits nothing. Optional accounts save
material-only activity and self-reported badges; guests retain the core flows.

## Infrastructure and City Mode

The City snapshot has 1,596 assets at 1,583 coordinate-defined sites: 538 Pakomak
recycling assets and 1,058 general-waste assets. One metro asset is separate.
Citizen routing adds documented electronics/clothing destinations. Counts describe
source records, not current operating facilities. See the
[snapshot documentation](data/infrastructure/skopje-2026-09-19/README.md).

City Mode reports the modeled population within a ten-minute pedestrian-network
walk of a compatible site. It compares additive upgrades at existing general-waste
sites without removing their service, with material and municipal coverage,
percentage-point gains, shortfalls and solver limits. Unknown population and
unverified access connectors remain explicit. See [CITY_MODE.md](docs/CITY_MODE.md).

## Engineering and evidence

One FastAPI service serves a build-free client, versioned policy/data and optional
development models. Training and geographic preparation happen offline. Preserve
source dates, checksums, measured evaluation history and licensing limitations.
Never represent source-recorded access, scheduled arrivals or parking spaces as live
verified availability. Follow [ENGINEERING.md](docs/ENGINEERING.md).

Independent model/native-language review, physical site checks and deployment/device
evidence remain separate from automated checks. Public voting, correction-feedback
training, live vehicle tracking and native app distribution are outside delivered
scope. [STATUS.md](STATUS.md) and [DELIVERY_PLAN.md](docs/DELIVERY_PLAN.md) record the
current delivery boundaries.
