# Product

## Outcome

Help residents dispose of an item correctly and reach an appropriate collection
point. Reuse aggregated demand and infrastructure data to help cities improve access.

## Users and MVP

| User | MVP task |
| --- | --- |
| Resident | Pick recyclable items, confirm their condition, and plan a walking/driving route; use text/photo help if unsure |
| City planner | See coverage gaps and compare suggested upgrade locations |

The supported classes are glass, plastic/metal packaging, paper/Tetra Pak, general
waste, and specialist/unsupported waste. `special_unsupported` is a real confident
prediction; low confidence is handled by abstention and manual choice, not an unknown
class.

The October 17, 2026 edition supports Skopje in English and Macedonian. All five core
capabilities are required: classification, real-site map, multi-item walking/driving
routes, City Mode coverage, and upgrade recommendations. Routes end at the final
collection point. Keep geography and language configuration extensible.

The current demo runs locally on desktop; iPhone Safari and Home Screen installation
remain deferred targets. The current webpage
has no installation manifest or offline cache; both remain implementation work.
There is no existing hosting. Prefer free/free-tier HTTPS hosting, maps, and routing;
check service limits before selection. Cache sites for browsing/basic nearest-site
lookup, but do not promise offline network routing or classification.

Installation reference: [Apple's iPhone web-app guide](https://support.apple.com/en-lb/guide/iphone/iphea86e5236/ios).
Record the actual iOS version and verify launch from the Home Screen during rehearsal.

Uncertain items require clarification or manual selection. Hazardous/specialist
items get guidance and only explicitly compatible facilities; never general-waste
fallback. When no verified facility exists, report that rather than invent a route.

## Delivery order

The citizen page is route-first: all four material cards select directly, followed
by explicit condition confirmation, starting point and travel mode. Recycling streams
match assets accepting every supported subtype. Text/photo suggestions sit inside
optional help and retain manual review. General waste routes to recorded bin locations
with a visible unverified-acceptance warning, not a verified disposal recommendation;
it can be combined with recyclables and is never an automatic fallback for held items.
Long source/method explanations are expandable; essential safety and location-sharing
notices stay beside the relevant action. City Mode remains a separate page.

1. Classification + nearest compatible site.
2. Multi-item route and map.
3. Coverage scoring and paper-site recommendations.
4. Correction feedback and public voting after this edition; neither is a demo gate.

Optional accounts, activity history and six self-reported badges are implemented.
Live truck tracking and automated policy decisions remain outside the demo scope.

## Demo success

City Mode's confirmed population-weighted walking coverage objective is specified
in [CITY_MODE.md](CITY_MODE.md), including the delegated municipal equity policy.

- A resident completes the classify-to-destination flow without explanation.
- Uncertain items never silently receive a confident recycling instruction.
- Baselines and learned models use the same fixed split and published metrics.
- Every city recommendation shows its objective, inputs, and before/after coverage.
