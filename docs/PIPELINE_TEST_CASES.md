# Six-category pipeline checks

## Try it yourself

Use the running app at `http://127.0.0.1:8000/`. Start a fresh page for each case.
Pictures are in [the sample gallery](../tests/fixtures/pipeline/README.md).

| Category | Text to enter | Picture | Expected destination |
| --- | --- | --- | --- |
| Glass | `empty glass jar` | [Jar](../tests/fixtures/pipeline/images/glass.png) | Glass collection |
| Plastic & cans | `empty plastic bottle` | [Bottle](../tests/fixtures/pipeline/images/plastic.png) | Plastic/metal collection |
| Paper & cartons | `clean cardboard box` | [Box](../tests/fixtures/pipeline/images/paper.png) | Paper/carton collection |
| General waste | `used tissue` | [Tissue](../tests/fixtures/pipeline/images/general.png) | Recorded general-waste bin |
| Electronics | `old phone` | [Phone](../tests/fixtures/pipeline/images/electronics.png) | Small-electronics collection |
| Clothes | `clean blue shirt` | [Shirt](../tests/fixtures/pipeline/images/clothes.png) | Clothing donation |

For each row, try all three entry paths:

1. **Select:** click its material card and confirm. For the phone, select the small-device option.
2. **Text:** open the identification helper, enter the example, Check, inspect the suggested type,
   and confirm. Do not change the type just to make a test pass.
3. **Photo:** upload the linked picture, request a suggestion, Review suggestion, then confirm.
   A picture alone must never add an item to the trip. A held/incorrect prediction is a result
   to record, not permission to override the safety checks.

Then choose a starting point, select Walking or Driving, and Find my route. Try GPS,
Choose on map (tap a point or Use map center), and manual coordinates. A fixed public
Skopje test point is **41.9965, 21.4314**; do not submit somebody's home location.
Selecting the point should collapse the location editor. Walking uses a dashed line,
driving a solid line; each stop should show the correct drop-off colour and item.

Also select all six cards together: every category must be covered, without duplicate
stops at the same site. General-waste navigation uses recorded bin identity, not verified
acceptance rules. Clothing is clean/wearable donation, not recycling for damaged textiles.

## Repeatable automated checks

```powershell
$env:SRA_BROWSER_TESTS = '1'
uv run --all-groups pytest tests/test_pipeline_browser.py tests/test_pipeline_live_runner.py
```

The browser matrix has 108 journeys: six categories × select/text/photo × GPS/map/manual
origin × walking/driving. Walking uses a 360px viewport, driving 1280px. Eight additional
cases cover all-six baskets, battery/swollen-phone/dirty-clothes/unknown-item holds, and
vision/routing outages followed by recovery. Existing suites cover denied GPS, real map
clicks, stale responses, coordinate validation, route invalidation and provider contracts.

These tests run real pages, endpoints, policy, data matching and route planning. External
OpenAI/ORS responses and map tiles are simulated; the photo response is selected explicitly
by the fixture ID, **not inferred from the image**. This verifies integration, not recognition
accuracy. Tests inspect actual automatically selected kinds, compatible asset IDs, origin,
travel profile, confirmation boundaries, stop colours, route styles and console errors.
Their test-only control endpoints are absent from the production app.

## Real providers (explicit opt-in; may cost API quota)

Start the normal app with its configured OpenAI/ORS credentials, then:

```powershell
uv run python scripts/check_six_stream_pipeline.py --live
```

One invocation sends at most six synthetic images to OpenAI and six trips (each normally
one matrix plus one directions request) to ORS. No automatic retries. It first identifies
and confirms each text/image, then routes three complete six-item baskets in both modes.
Photo routes use the model's actual descriptions/kinds. An incomplete or incorrect photo
basket is not silently repaired or routed. The fixed public origin and candidate coordinates
go to ORS; item text and images do not. The script calls the local app, never reads keys,
and writes ignored `artifacts/pipeline-live-results.json`; a failed check exits nonzero.

To repeat only text and picker routing without spending vision quota:

```powershell
uv run python scripts/check_six_stream_pipeline.py --live --without-photos --output artifacts/pipeline-live-routes.json
```

The app's metadata-stripped JPEG data URL follows the documented
[OpenAI image-input format](https://developers.openai.com/api/docs/guides/images-vision).
The test keeps the server's configured vision model; it does not train or switch models.

See [recorded results and limitations](PIPELINE_TEST_RESULTS.md). Synthetic images are
smoke-test examples, not an independent accuracy benchmark. Rehearse with consenting real
phone photos and the actual demo device before claiming production reliability.
