# Data workspace

- `seed/`: small deterministic synthetic fixtures committed for tests.
- `raw/`: immutable source downloads; ignored by Git.
- `processed/`: validated derived snapshots; ignored until licensing is confirmed.
- `mappings/`: explicit local policy and a generated Toronto review queue. The Toronto
  item mapping stays ignored until redistribution terms are clear.
- `evaluation/`: provisional manual queries; every row is marked for human review.
- `policy/`: operator source register and conservative asset acceptance profiles.
  Manual query decisions are in `evaluation/manual_test_review.csv`; the original
  queries remain unchanged. Source review by an agent is not human sign-off.

For Toronto review, set `mapping_status` to `approved` with a local `target_label`, or
to `excluded`; these human decisions survive deterministic regeneration. Leave
machine-generated proposals as `needs_review`. Legacy `auto_approved` rows are
excluded from training. Record local evidence for each human approval.

See [the data contract](../docs/DATA.md). Do not treat seed coordinates as real
collection points.
