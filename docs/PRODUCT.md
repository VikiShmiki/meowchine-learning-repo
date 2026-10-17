# Product

Najdi Frli helps residents identify a waste item, confirm its condition and reach
a compatible collection point. City planners can compare modeled walking access
and additive recycling upgrades. The supported region is Skopje, with English
and Macedonian interfaces.

## Citizen behavior

The route-first page has six flows: glass, plastic/metal packaging, paper/cartons,
ordinary residual waste, electronics and wearable-clothes donation. Text and photo
help are optional. Exact-item/condition confirmation and asset-level acceptance
control routing; learned suggestions never authorize disposal.

A resident chooses device, map or manual origin and Walking, Driving or JSP bus.
Driving can add mapped parking and walking connections. Up to six confirmed items
can share a trip, which ends at the final drop-off. Parking adds return-to-car walks
between stops; its final return is excluded. Scheduled bus journeys do not promise
live arrivals, and parking does not promise a vacant space.

Unknown/unsafe items stay held for clarification or specialist guidance. A broad
category cannot establish compatibility with a bottle-only machine. General-waste
navigation needs explicit acknowledgment of unverified acceptance and is never a
fallback for held items. Source and method details are expandable; essential
confirmation, uncertainty and location-sharing notices remain beside their actions.

Visited stops can be marked and the journey finished. Optional post-trip reports
cover only visited containers; full reports remove the asset from public routing
for up to 12 hours, subject to review. Guests can use the core flow. Accounts add
material-only activity and self-reported badges without recording location history.

## City behavior

The separate City page shows population-weighted ten-minute walking-network access
by material and municipality. Prepared scenarios compare 0–20 upgrades at existing
general-waste sites, retaining that service. Results expose objective, inputs,
before/after coverage, municipal shortfalls and exact/heuristic solver status.
See [CITY_MODE.md](CITY_MODE.md) for the modeled-access limits.

## Scope and acceptance

- Residents can complete item confirmation, route selection and optional check-in.
- Uncertain items never silently receive a confident disposal instruction.
- Failures preserve actionable recovery; a missing provider does not invent a route.
- Models use documented splits and evidence; historical benchmarks are clearly dated.
- Every City recommendation explains its metric and limitations.

The app is locally runnable and container-tested. Public hosting, physical iPhone
testing and Home Screen installation remain user-deferred. There is no installation
manifest or offline application shell; caching sites for browsing is not offline
classification, routing or maps. Public voting, correction-feedback training, live
vehicle tracking and production account recovery are not delivered features.
