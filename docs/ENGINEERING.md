# Engineering standards

Engineering excellence is a release requirement. Prefer small, explicit designs
that can be extended after the current prototype without replacing the core.

## Boundaries and extension

- Keep one deployable backend. HTTP adapters validate and orchestrate; domain code
  owns classification contracts, compatibility, routing objectives, and coverage.
- Use explicit typed inputs/outputs. Keep source material capabilities distinct
  from classifier categories. A category alone cannot establish site compatibility.
- Isolate external map/routing services and model loading behind small interfaces
  where they are actually used. Do not build speculative plugin frameworks.
- Keep region, language, thresholds, network assumptions, and artifact versions in
  configuration. The current product supports English and Macedonian within Skopje;
  do not claim other languages or geographic coverage before their data and tests exist.
- Keep training, data acquisition, and analysis out of request handlers. Precompute
  expensive stable network reachability where practical and version its inputs.

## Reliability and user experience

- Specify timeouts and bounded retries for safe external requests. Surface failures
  as actionable states; do not return invented predictions or fabricated routes.
- Cover denied location permission, manual starting points, missing materials,
  disconnected paths, empty candidates, malformed inputs, and provider outages.
- Prevent stale asynchronous responses from replacing newer user selections.
  Restore controls after failures and support keyboard and screen-reader use.
- Label cached data and its age. Define which operations work offline; installation
  does not imply that classification, routing, or map tiles work offline.
- Log request IDs, durations, failure types, and artifact versions without precise
  locations or raw personal queries. Never commit credentials.

## Evidence and reproducibility

- Pin dependencies, preserve immutable source snapshots and checksums, and record
  transforms, population year, network version, solver settings, and model versions.
- Reject invalid coordinates, duplicate IDs, orphan references, and incompatible
  schemas with useful errors. Preserve exclusions and source uncertainty.
- Use fixed grouped evaluation splits and reviewed labels; calibrate and select
  abstention thresholds on validation data. Do not call heuristic scores calibrated.
- Report approximate routes/optimization honestly. Never label straight-line
  coverage as population-weighted pedestrian access. Missing population is unknown,
  not zero. Disconnected network demand stays in the population denominator.

## Verification and delivery

- Test domain behavior with small deterministic examples and external providers
  with recorded/synthetic fixtures; ordinary tests require no network.
- Test route legality by mode, travel direction, deduplicated stops, and small known
  optimum cases. Compare coverage/optimization against hand-calculated tiny graphs.
- Exercise the full citizen and City Mode flows in a browser, including failures.
  Verify actual installation on the agreed device before claiming it works.
  Hosting and physical-phone work remain user-deferred unless explicitly reopened.
- Require lock validation, lint, tests, and snapshot validation before merge.
  Add a focused regression test for each behavior bug, not tests of implementation
  trivia. Set measured performance budgets before performance sign-off.
- Keep PRs focused. State the problem, resulting behavior, evidence, and limitations.
  Commit subjects, PR titles, and squash messages use `docs:`, `feat:`, `fix:`,
  `test:`, `build:`, `ci:`, or `refactor:` with a concise description.
  Update status and contracts when capabilities change. Never bypass failing checks
  to meet the deadline or claim a feature merely because its scaffolding exists.

## External evidence and scope

Use free/free-tier services where feasible, but recheck provider terms, quotas and
measured capacity before deployment. Native-language review, independent model
evaluation and physical access/device checks remain separate evidence requirements.
Community reports, optional accounts and their retention rules are implemented;
public voting and correction-feedback training remain outside delivered scope.
See [DELIVERY_PLAN.md](DELIVERY_PLAN.md) for deferred work.
