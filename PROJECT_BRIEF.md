# Smart Recycling Access ? project brief

## Confirmed demo

The October 17, 2026 edition includes all five core features: classification, real collection
points on a map, multi-item routes, City Mode coverage, and container recommendations.
The local demo supports Skopje in English and Macedonian; keep region and language
configuration extensible. Hosting, iPhone rehearsal and Home Screen installation
remain deferred. Prefer free/free-tier services for any future deployment and check
current quotas before choosing providers. Paid services require a budget decision.

## Citizen flow

Classify each described item as `glass`, `plastic_metal`, `paper_tetrapak`, `general`,
or `special_unsupported`. A broad category does not prove site compatibility: a
bottle-only machine must not be recommended for every plastic/metal item.

Uncertainty requires a clarification question or manual selection. Select abstention
thresholds and calibration on validation data. Never present heuristic scores as
calibrated probabilities. Never default uncertainty or hazardous items to general
waste. Specialist items receive guidance and only facilities explicitly accepting
that specific waste type. If no verified facility exists, say so. Manual selection
must not bypass known hazardous-item restrictions.

Support current location and manual starting points. Multi-item routes support
walking and driving, ending at the final collection point. Use actual travel networks,
consolidate shared stops, respect access/direction restrictions, and disclose
unreachable items or approximate optimization.

## Infrastructure

The shared snapshot contains 1,596 City assets at 1,583 coordinate-defined sites:
538 Pakomak recycling assets and 1,058 general-waste assets. Recycling includes
407 glass assets, 124 accepting bottles/cans, and 7 paper assets. One metro asset
is separate. Counts describe source records, not verified operational availability.
See [snapshot documentation](data/infrastructure/skopje-2026-09-19/README.md) for
provenance and limitations. The real snapshot API, citizen map and confirmed-item routing use the versioned
local infrastructure and acceptance policy.

## City Mode

For each material, measure the percentage of the City's population within a 10-minute
walk of a compatible site along the pedestrian network. Recommend N upgrades at
existing general-waste sites without removing their existing service. Apply the
configurable municipal equity policy in [CITY_MODE.md](docs/CITY_MODE.md).

Show current/projected coverage, percentage-point gain, recommended sites, municipal
shortfalls, and underserved areas. Acquire and validate population, boundaries, and
network inputs. Never silently substitute straight-line or unweighted coverage;
state missing data and label approximations explicitly.

## Delivery boundaries

Correction feedback and public voting remain deferred beyond this edition.
Optional accounts, material-only activity and self-reported badges are implemented.
Live truck tracking and native App Store distribution remain outside the demo plan. Installation does not promise offline routing or classification.

Use one FastAPI service, a replaceable classifier, reviewed local mappings, and
repeatable rule/TF-IDF evaluation before transformers. Follow
[ENGINEERING.md](docs/ENGINEERING.md) and [DELIVERY_PLAN.md](docs/DELIVERY_PLAN.md).
Requirements are not implemented capabilities; STATUS.md records what actually works.
