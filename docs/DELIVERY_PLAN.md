# Delivery scope and remaining gates

Updated: October 17, 2026. Najdi Frli is delivered as a locally runnable,
container-tested Skopje application in English and Macedonian. Hosting and
physical-phone verification remain user-deferred; do not resume them without a
new request. This document describes scope, not an active task assignment.

## Delivered

| Area | Acceptance contract |
| --- | --- |
| Policy and item guidance | Reviewed local mappings, explicit holds and exact-item/condition confirmation; optional text/photo suggestions cannot authorize acceptance |
| Infrastructure and citizen map | Validated real source assets, material/search filters, device/map/manual origins, source dates, cached browsing and recovery |
| Trips | Up to six confirmed items; directed walking/driving, scheduled JSP connections, optional parking-assisted driving; full assets excluded and failures explicit |
| City analysis | Prepared population-weighted ten-minute pedestrian coverage, material/municipal totals, explicit connector uncertainty and additive upgrade scenarios |
| Community | Optional container check-ins, immediate shared full exclusions with expiry/review, moderated dumping reports and documented abuse/retention controls |
| Accounts | Optional private material activity, self-reported badges, deletion and guest compatibility; no production identity claim |
| ML | Verified pinned encoders and development-v3-audit suggestion heads, separate calibration, abstention and documented data/evaluation limitations |
| Delivery | Active quality/browser and Docker smoke CI; model/data bundles tested without application credentials |

Implementation milestones and original task IDs remain in
[STATUS_HISTORY.md](../STATUS_HISTORY.md). Current results are in
[QUALITY.md](QUALITY.md) and [CI_STATUS.md](CI_STATUS.md).

## Work requiring separate scope or external evidence

- Native Macedonian review, reviewed local acceptance labels and newly collected
  independent user tests. Existing authored development data is not a substitute.
- Field review of collection operations, entrances, walking connectors and parking
  access. Scheduled buses and mapped parking do not establish live availability.
- HTTPS deployment, capacity/cold-start measurement, persistent account/report
  storage, production identity/recovery review and device testing. Historical free
  hosting research is not a current capacity guarantee.
- Installation/offline support and actual iPhone Home Screen testing, if reopened.
  Record the device/iOS, deployed revision and observed failures/latency.
- Public voting, correction-feedback training and live vehicle tracking are outside
  the delivered scope; define privacy and retention before adding data collection.

## Completion rule

Every change updates affected contracts, adds meaningful regression coverage for
behavior fixes and passes lock, lint, formatting, tests and applicable artifact
validators. Browser and container gates must pass before merge. Record revision-
specific results and remaining limitations; never substitute a roadmap entry or
unreviewed model metric for delivered behavior.
