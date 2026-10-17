# Data

## Population and street inputs

The [versioned geographic package](../data/geography/skopje-v1/README.md) shares
WorldPop 2025 modeled demand, OSM municipal boundaries and street topology, preserved
turn restrictions, and unverified population/site access candidates. Its manifest
pins sources, dependencies, parameters and artifact checksums. CI validates hashes,
IDs, topology references and population reconciliation without external requests.
See [GEOGRAPHY.md](GEOGRAPHY.md) for NoData, boundary, connector and provider limits.
Acquisition/preparation lives in `src/smart_recycling/geography/`, outside app startup.

## Site contract

The real infrastructure snapshot is now available in
[`data/infrastructure/skopje-2026-09-19/`](../data/infrastructure/skopje-2026-09-19/README.md).
It preserves the original GeoJSON/CSV exports and checksums. At startup, the app
validates and groups the real assets for `/api/v1/sites`, keeping City/metro scopes
separate. Source site IDs must agree with coordinate groups at six decimal places;
exact asset coordinates are retained. It never merges distinct asset capabilities.
The current nearest-point UI/API still uses synthetic seeds pending item-specific
lookup integration. See [API.md](API.md) for the real snapshot schema and cache contract.

`data/seed/sites.json` demonstrates the ingestion contract:

| Field | Type | Rule |
| --- | --- | --- |
| `id` | string | stable and unique |
| `name` | string | display label |
| `latitude`, `longitude` | number | WGS84, valid ranges |
| `materials` | string[] | routable labels; never `special_unsupported` |

The seed is synthetic. Do not use it for analysis or claims about real coverage.

## Waste-item contract

Full local English/Macedonian dataset counterparts and filtered experimental
splits are documented in [BILINGUAL_DATA.md](BILINGUAL_DATA.md). Translations
retain source links and review holds; machine translation does not approve labels.
The current v2 experimental dataset additionally uses `clothes` and `electronics`
object classes, per the user's explicit taxonomy extension. Its prior disposal
labels/statuses remain provenance: object classification is not site acceptance.
This does not change the serving/API five-category contract or historical datasets.

Infrastructure locations do not train the text classifier. Classification needs a
separate reviewed dataset with at least:

| Field | Purpose |
| --- | --- |
| `text` | item description presented to the classifier |
| `target_label` | locally correct category in the legacy pipeline; v2 adds the documented object classes |
| `source`, `original_label` | source and source-label provenance |
| `item_group` | keeps paraphrases of one item in the same split |
| `generation_method` | distinguishes source text from template variants |
| `mapping_status` | distinguishes approved labels from review candidates |
| `split` | fixed train, validation, or test assignment |

Disposal policy is local: label examples against accepted container rules, not only
the item's material. Preserve an immutable reviewed test set before generating
synthetic training examples.

## Sources and preparation

For the September 22 raw-only acquisition and clothing/electronics vocabulary
review, see [DATASET_INVENTORY.md](DATASET_INVENTORY.md). Its descriptive raw folders
are separate from the legacy pipeline below; no new mapping or training was run.

See [DISPOSAL_POLICY.md](DISPOSAL_POLICY.md) for the local evidence review: all 50
Dataset A labels have explicit decisions (13 supported, 37 held). Toronto suggestions
are proposals; `needs_review` and legacy `auto_approved` rows do not enter training.

Dataset A (`thomasavare/waste-classification-v2`, pinned revision) provides 26,910
template-based natural-language queries across 50 original labels. Every label has an
explicit target mapping; policy-sensitive labels remain `needs_review` and are
excluded from combined training data.

Dataset B (Toronto Waste Wizard) provides item vocabulary. Its disposal category is
stored for provenance only: item-name rules propose local mappings, and
all other items remain unresolved. Neither source catalogue currently declares a
clear dataset-specific license, so raw/derived source records stay untracked pending
confirmation.

Run `make data-all` for the full workflow or individual scripts in `scripts/`. The
pipeline preserves realistic text, removes exact duplicates, reports near duplicates,
augments approved Toronto items deterministically, and emits metadata-rich and
`text,label` exports.

Splitting is grouped by normalized item. Dataset A exposes no clean item identifier,
so its original fine-grained label is the conservative group. This prevents leakage
but makes exact per-class 70/15/15 balance impossible; the separate manual set is
therefore essential.

## Pipeline

Preserve source files unchanged in untracked `data/raw/`. Normalize into one row per
physical site, retaining source asset IDs and allowing several materials per site.
Validate schema, coordinates, IDs, duplicates, nulls, category counts, and the stated
1,596 assets / 1,583 sites before publishing a versioned processed snapshot.

Record for every snapshot: source, license, retrieval date, checksum, transform
version, row counts, and rejected rows. Never silently repair invalid coordinates.

## Feedback and privacy

Store the minimum needed: normalized query, predicted/corrected label, coarse area,
model version, and time bucket. Do not retain precise location trails or direct
identifiers. Publish only aggregated cells that meet an agreed minimum count and set
a retention period before collecting real feedback. Classification requests never
need location; clients should prefer local nearest-site lookup from cached site data.
