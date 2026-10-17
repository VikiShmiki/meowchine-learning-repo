# Historical pipeline check — 2026-09-22

This records the original source-repository branch and provider checks. Statements
about paused CI or missing container evidence apply to that revision only. The
current private repository has active CI; see [CI_STATUS.md](CI_STATUS.md).

Tested the uncommitted `feat/general-electronics-guidance` worktree based on
`59869e2441db8dda5705d8e14b6ba5928fc4494d`, including general/electronics/clothes additions.
This is local evidence, not a test result for unchanged main or a hosted CI pass.

## Live APIs

Final complete run began **2026-09-22 03:17 UTC** against the running localhost app.
Text model: `policy-rules-v3`; vision: `openai:gpt-5.6-luna`; policy: `skopje-policy-v2`;
data: `2.0.0+skopje-electronics-v2+skopje-clothes-v1`. Real OpenAI and ORS calls;
synthetic non-personal images; fixed public Skopje origin 41.9965, 21.4314.

| Check | Final run |
| --- | --- |
| Six text examples, automatic kinds and confirmation | 6/6 passed |
| Six photo examples, automatic kinds and confirmation | 6/6 passed |
| Select → six-item basket → walking/driving | Both passed |
| Text → six-item basket → walking/driving | Both passed |
| Photo → six-item basket → walking/driving | Both passed |

All six routes returned six compatible stops. Walking was 4,706.1m; driving 6,346.6m.
These are provider routes within the app's shortlist, not a global shortest-route proof.
Raw final checks are in ignored `artifacts/pipeline-live-results.json`.

### Failure retained from the first run

The first phone photo returned **`batteries`** instead of **`small_electronics`**. The other
five images and all six text examples passed. One targeted phone retry returned
`small_electronics`, `candidate`, description `Smartphone`; the final complete run also
passed. No application/model/prompt change was made to manufacture that recovery.

This is unresolved nondeterminism: one passing rerun does not erase the failure or establish
accuracy. The first raw model response was not captured, so its exact cause is unproven.
The adapter's description/reason hazard-keyword override is a possible contributor, not
a confirmed diagnosis. Keep user review and do not suppress real battery hazards.

The initial test runner also failed on a general-waste asset's null acceptance profile
after its first live route. The harness now checks recorded general-bin identity separately;
a regression test covers that case. A routing-only run then passed all four picker/text
routes, followed by the complete final run above. No tests were weakened to accept an
incorrect kind. Across this investigation: 13 photo requests (six + one targeted retry +
six), and 11 trip requests (one + four routing-only + six final); no automatic retry loop.

## Scope limits

- Browser runs use simulated external providers/tiles, including simulated GPS, not personal location.
- Live tests use HTTP; browser interaction is separately covered by the same real API contracts.
- Six generated pictures are not a real-photo benchmark. Phone-photo reliability remains open.
- General bins remain acceptance-unverified; routes do not verify opening hours or field access.
- No physical iPhone, HTTPS deployment, Docker build or hosted CI pass claimed.
- Git delivery is tracked in PR #19; the original live observations above predate that commit.
- GitHub CI remains manually paused. Its existing browser command includes the new module for restoration.

## Local regression evidence

Full browser-enabled run: **527 passed, one failed** (528 collected). The failing case was
`Driving-map-picker-clothes`: the map-selection button stayed disabled for the 15-second
test timeout. The same case passed in an isolated rerun without application changes.
Cause is unconfirmed; do not report this original full run as green or silently relax
its assertion. Heavy coverage/upgrade reproduction was running concurrently, but that
does not establish the cause. Existing map-failure/manual-origin fallback tests passed.

The subsequent complete run of the new browser module passed **116/116** in 180.59s,
with no skipped assertions or application changes. This bounds the issue as intermittent;
it does not erase the earlier full-suite failure.

Four live-runner/fixture tests and all 18 Node tests passed. Ruff, dependency lock, seed,
pinned infrastructure/geography validators, coverage/upgrade reproduction and the running app's
MiniLM-required deployment smoke passed. Key desktop/mobile journey screenshots were
inspected; browser routes/tiles in those screenshots are explicitly simulated.

## PR #19 pre-merge verification

The fresh complete browser-enabled gate on the code committed as
`b376feaec8fddc2c37e6d88a80f0b75f902a43d4` passed **528/528 tests**, including **228 browser/system
cases**, in 301.03s. Eleven dependency deprecation warnings remain; no skipped tests,
relaxed assertions or production changes were used. Unlike the earlier run, heavy
coverage/upgrade preparation was not running concurrently. This clean run does not
prove that the earlier intermittent map failure is fixed.

Lock validation, Ruff, 18 Node tests, seed/infrastructure/geography validators, whitespace
and credential-pattern scans, and the MiniLM-required running-app smoke also passed.
Coverage/upgrade reproduction had passed on the same application/data code in the prior
test session; no paid API calls were repeated just to open the PR. The final live 18/18
result and original phone-photo failure are both retained above.

The follow-up commit only records this evidence in Markdown. Main was still
`59869e2441db8dda5705d8e14b6ba5928fc4494d` at review, with no conflicts. CI remains
`disabled_manually`, and no protection or check bypass is requested. These checks support
the prototype merge, not production/field/real-photo-accuracy sign-off.
