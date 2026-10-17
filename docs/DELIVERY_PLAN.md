# Delivery plan

Current edition: October 17, 2026. Hosting and physical-phone testing remain deferred.
The current demo is local/desktop only; those checks are not claimed complete.
Do not pursue deployment access or phone rehearsal unless the user reopens them.

Repository handoff date: October 17, 2026.
Launch scope: Skopje, English and Macedonian. All five core capabilities must work for judging:
classification, real collection points on a map, multi-item walking/driving routes,
City Mode coverage, and upgrade recommendations. Routes end at the final site.
Original delivery target: iPhone Safari with Home Screen installation; this is now
user-deferred and not the current local-demo acceptance gate. No existing hosting; prefer
free/free-tier HTTPS hosting, maps, and walking/driving routing. Community reports are implemented; public voting remains deferred. Clarify uncertain items or offer manual
selection; specialist guidance/facilities require explicit waste-type acceptance.

Dataset-sharing and requirements PRs are merged. T02 was completed by Codex as
source review with explicit holds; human sign-off is not claimed. Record the owner
when claiming the next implementation task. Implementation proceeds in focused PRs.

| Task | Deliverable and acceptance evidence | Dependencies |
| --- | --- | --- |
| T01 Done | Requirements, standards, scope, and backlog documented; remaining external inputs are explicit | Documentation PR |
| T02 Done | Review acceptance rules and the 100-query test; explicitly resolve/hold ambiguous mappings; document permitted item-to-site capabilities | Local policy evidence |
| T03 Done | Ingest shared City snapshot; validate provenance/IDs/coordinates; expose versioned snapshot; retain metro separation and QA flags | Shared data available |
| T04 Done | Codex: shared pinned population, OSM boundaries and street topology; reconciled totals, connectivity/access audit, preserved restrictions, provenance and provider feasibility. See GEOGRAPHY.md; connectors and driving route legality remain integration gates | Provider/source selection |
| T05 Done | Codex: evaluated policy rules, validation-selected threshold, manual recovery and specialist guidance. Metrics/holds in data/classifier; visual/device QA outstanding | T02 |
| T06 Done | Codex: real City map, material/search filters, source/acceptance details, device/manual origins, dated cache and failure recovery. Seven real-page browser cases including T05 guidance passed; physical iPhone/live provider remain T10 gates | T03; map/provider decision |
| T07 Done | Codex: confirmed-item basket, asset-compatible stops, directed ORS walking/driving routes ending at last stop; tiny optimum/failure tests and live one-way spot check. Shortlist and access-gap limits in ROUTING.md | T02, T04, T06 |
| T08 Done | Codex: prepared population-weighted 10-minute directed walking-network approximation, explicit access limits, material/municipal breakdown and 50% floor shortfalls; tiny-graph tests, reproducibility and City browser tests | T03, T04 |
| T09 Done | Codex: prepared 0..20 additive upgrades, weighted pedestrian catchments, municipal equity objective, exact/heuristic and feasibility evidence, before/after/gain/sites/gaps; exhaustive-oracle, artifact and browser checks | T08 |
| T10a Deferred | Installation/offline support and production/device readiness remain outside the current local-demo work; reopen only with user direction | T05-T09; no hosting access required |
| T10b Deferred by user | HTTPS deployment, iPhone-tested Home Screen installation and hosted capacity evidence; not required for the current local demo and not claimed complete | Reopen only at user's request |

Render currently lists no repositories after the repository-only access request flow.
Organization-owner approval is not verified. T10b is now deferred at the user's request;
do not resume just because repository access becomes available.

Population and network acquisition is an early feasibility check: inability to obtain
these inputs must be visible immediately, with any alternative explicitly labeled
and agreed. Do not wait until the final demo to discover missing coverage inputs.

## Implementation inputs still to resolve

These do not reopen confirmed scope. Resolve and record them in the relevant task:

- Release hold: T05 explicitly retains T02 evidence holds; obtain human review.
  General-waste labels, specialist facilities and Toronto proposals remain unverified.
- T06/T07/T10: validate the proposed free demo stack in GEOGRAPHY.md against walking/driving
  support, quotas, cold starts, network extraction limits, and redistribution terms.
  Prefer precomputed City Mode reachability to repeated large hosted API requests.
- T10: expand independent quality evidence and measure hosted/device latency before
  sign-off. T05 reports 94.4% answered accuracy at 61.0% coverage on 59 reviewed queries;
  this is not full five-class quality. Prediction budget is 25 ms; local p95 is below 1 ms.
- T10: record the actual iPhone model/iOS, exact submission time, and rehearsal result.
- Record a task owner on claim; do not assign work to teammates without agreement.

User-approved mentor extension: container reporting/rerouting and moderated dumping
reports now have explicit retention and abuse policies in [COMMUNITY.md](COMMUNITY.md).
Optional accounts, activity history and six self-reported badges are now user-approved;
see [ACCOUNTS.md](ACCOUNTS.md). Public voting remains deferred. This does not remove the T10b
hosting/iPhone rehearsal gates.

## Completion rule

Each implementation task records changed files, tests/results, remaining limitations,
and its demo acceptance evidence in STATUS.md. The five required capabilities are
not complete until the integrated demo passes; do not substitute roadmap entries
or unreviewed model metrics for delivered behavior.
