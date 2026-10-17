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
The citizen map and confirmed-item routing use the real citizen snapshot, including
separately documented electronics/clothing destinations. Only the unused legacy
`/api/v1/nearest` endpoint retains synthetic seeds. See [API.md](API.md) for schemas
and cache behavior.

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
The current fitting corpus is development v3, with pinned audit-corrected serving
heads. Authored bilingual concept groups separate train, tuning, calibration and
test roles; retained English source data is independent of translation coverage.
Legacy automatic Macedonian translations are quarantined. `clothes` and `electronics`
are object labels, not extra disposal-policy categories or acceptance evidence.
Historical v1/v2 data and measured results remain unchanged. See [ML.md](ML.md) and
[BILINGUAL_DATA.md](BILINGUAL_DATA.md) for exact support, exclusions and review holds.

Infrastructure locations do not train the text classifier. Classification needs a
separate reviewed dataset with at least:

| Field | Purpose |
| --- | --- |
| `text` | item description presented to the classifier |
| `target_label` | reviewed object/stream label under the versioned task taxonomy; not destination acceptance |
| `source`, `original_label` | source and source-label provenance |
| `item_group` | keeps paraphrases of one item in the same split |
| `generation_method` | distinguishes source text from template variants |
| `mapping_status` | distinguishes approved labels from review candidates |
| `split` | fixed grouped role; v3 separates train, tuning, calibration and test |

Disposal policy is local: label examples against accepted container rules, not only
the item's material. Preserve an immutable reviewed test set before generating
synthetic training examples.

## Sources and preparation

For the September 22 raw-only acquisition and clothing/electronics vocabulary
review, see [DATASET_INVENTORY.md](DATASET_INVENTORY.md). Its descriptive raw folders
are separate from the legacy pipeline below. That acquisition did not train models;
later v3 preparation and fitting are documented in [BILINGUAL_DATA.md](BILINGUAL_DATA.md).

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

## Parking and timetable data

The licensed 144-point parking snapshot is reproducible from a pinned OSM/Geofabrik
extract; [PARKING.md](PARKING.md) and its [data README](../data/parking/skopje-v1/README.md)
define access filters, age limits, attribution and source checksums. Source tags
are not live occupancy, fee or opening verification.

JSP's validated timetable is downloaded into ignored runtime storage, with source,
version, fetch time and actual service-calendar limits exposed to journeys. No
redistribution license was established, so real feed archives are not committed.
Tests use independently authored schedules. See [TRANSIT.md](TRANSIT.md).

## Feedback and privacy

Classification needs no location, and text queries are not retained as feedback.
Trip origins/geometries are not stored. Community reports have separate 30-day
retention, and account history stores only material types and completion time.
See [COMMUNITY.md](COMMUNITY.md) and [ACCOUNTS.md](ACCOUNTS.md).

Correction-feedback training is not implemented. Define consent, minimum fields,
aggregation, review and retention before collecting it; never infer authorization
to collect user text or precise location trails from model-improvement goals.
