# Evaluated guidance artifact

Current serving artifact: `rules-v3.json`, model `policy-rules-v3`, policy
`skopje-policy-v2`. Reproduction below now generates v3 using the separately versioned
68-case `guidance_validation_v3.csv`, including clothing donation/hold cases.
The original validation, manual review, and
v2 artifacts remain unchanged. General has development-only fixtures, not independent
test support. See [extension scope](../../docs/GENERAL_AND_ELECTRONICS.md).

## Historical v2 evidence

Generated 2026-09-20. `rules-v2.json` configures the authoritative serving baseline
`policy-rules-v2`; `evaluation-v2.json` records its validation sweep, reviewed manual
test, errors, input/code/policy hashes and latency environment. No trained binary
or probability calibration is involved. The small JSON artifact is under 1 KiB;
serving also requires the checked-in rules source and policy.

Reproduce from the repository root:

```bash
uv run --group data python scripts/evaluate_guidance.py
```

Use `--out <directory>` for a comparison without replacing committed reports.
CI reruns evaluation and compares all deterministic fields, excluding timing and
platform. Startup rejects a rules/policy hash mismatch or a failed validation gate.

The separately tracked frozen MiniLM logistic head is not part of this evaluated rules
artifact and does not change these metrics. When rules cannot identify an exact item,
it can return a visibly separate broad suggestion while the classification remains
abstained and requires manual item/condition confirmation. Its own selection gate failed;
see [ML.md](../../docs/ML.md) for its evidence and artifact contract.

## Selection and evidence

The 48 original development-authored cases in
`data/evaluation/guidance_validation.csv` contain 32 supported examples and 16
explicit holds. Supported labels cite the existing Skopje policy source IDs; this
is agent source review, not human approval. Case/group IDs are preserved. No text
matches the reviewed manual test, but item families overlap. These fixtures are
development checks, not an independent field benchmark or a learned-model split.

Select among 0.60, 0.70, 0.80, 0.85, 0.90, 0.95 and 0.99 using validation only:
at least 95% answered accuracy, at least 50% coverage and no held false answers;
maximize coverage, then select the highest threshold. Selected threshold: **0.85**.
Validation: 32/48 answered (66.7%), all correct. No threshold tuning uses test metrics.

The unchanged 100-query manual source and its hash-linked review sidecar supply
59 supported test queries; 41 remain held. Test: 36/59 answered (61.0%), 34/36 correct
(94.4% answered accuracy); accuracy counting abstentions as misses is 57.6%.
Macro-F1 across the four supported classes is 0.684.

| Class | Support | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| glass | 13 | 1.000 | 0.462 | 0.632 |
| plastic_metal | 15 | 1.000 | 0.267 | 0.421 |
| paper_tetrapak | 18 | 1.000 | 0.722 | 0.839 |
| special_unsupported | 13 | 0.846 | 0.846 | 0.846 |
| general | 0 | unmeasured | unmeasured | unmeasured |

All errors are retained in the JSON report, including two conservative false
specialist detections: medicine-free glass packaging and rinsed bleach packaging.
Many alternate descriptions abstain and need manual recovery. These results do not
establish a 95% independent-test accuracy claim or complete five-class quality.

Local prediction p95 is below 1 ms against a 25 ms prediction budget on the recorded
Windows environment. The JSON stores the exact observation. This times `predict`
only over the small case set; it excludes HTTP, guidance serialization, cold startup,
mobile/network latency and hosting. It is not an iPhone performance measurement.

## Holds and remaining verification

No human sign-off, general-waste acceptance or verified specialist facility is
claimed. The 37 Dataset A family holds, 41 manual-query holds and all unreviewed
Toronto proposals remain held. Learned-model training gates remain unchanged.
Do not infer site acceptance from a broad classification; require explicit item
and condition confirmation and an accepting asset profile during later integration.

Backend contracts and six DOM-controller scenarios are automated. Actual visual
browser and iPhone verification remains outstanding: browser runtime setup failed
and no enabled browser surface was available during that original T05 check.
Later integrated browser and Docker checks are recorded in
[CI_STATUS.md](../../docs/CI_STATUS.md). Physical-device and independent quality
review remain outstanding; historical evaluation is not a device sign-off.
