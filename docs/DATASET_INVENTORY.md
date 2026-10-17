# Raw waste dataset inventory

Acquired 2026-09-22. Raw downloads and keyword inventory only: no label mapping,
normalization, alias expansion, deduplication, augmentation, new split assignment,
model training or model selection. Existing app models and legacy `dataset_a/` and
`dataset_b/` files are unchanged. All downloaded records remain ignored by Git.

## Sources and sizes

| Source | Rows | Local raw size | Original labels/categories |
| --- | ---: | ---: | ---: |
| Hugging Face, train | 21,528 | 1,481,210 bytes | 50 |
| Hugging Face, test | 5,382 | 368,482 bytes | 50 |
| Hugging Face, supplementary `unseen_phrases.csv` | 7,245 | 492,889 bytes | 50 |
| Toronto Waste Wizard JSON | 2,206 | 947,316 bytes | 15 exact strings |

[Hugging Face source](https://huggingface.co/datasets/thomasavare/waste-classification-v2):
revision `df082443773f2db01e165577c5d94c5dafe90f12`, verified as current at acquisition.
Used the `datasets` library to load **all two default splits** and export CSVs with
their original columns and row ordering (26,910 rows total). The companion CSV was
downloaded byte-for-byte from the same pinned repository revision. It is not an
additional official split, and its filename does not establish an independent
held-out test set. The dataset card's train count is stale; the loaded split has
21,528 rows. These English phrases were generated with templates, not collected
as independent real-user queries.

[Official Toronto catalogue](https://open.toronto.ca/dataset/waste-wizard-lookup-table/):
used its CKAN API's JSON resource, titled “Waste Wizard Data from TOwaste App.”
Saved its bytes untouched, including arrays, spelling, whitespace and categories.
Resource last modified: 2023-12-12; download date is not evidence of current policy.
The catalogue also lists an XLSX resource; it was not needed in addition to JSON.

## Columns and original categories

Hugging Face splits: `Unnamed: 0` (int64 source index), `Phrase` (string query),
`Class` (string original label), `Class_index` (float64 original numeric label).
The untouched supplementary CSV has an empty first column header instead of
`Unnamed: 0`; this is preserved, including in candidate exports.

All 50 original HF labels (spelling retained):

```text
ALUMINIUM CAN, ALUMINIUM SHEET, ALUMINIUM TRAY, CIGARETTE BUTT,
CIGARETTE PACK, COMPOSTABLE PACKAGING, CONDIMENT PACKETS, COVID TEST,
CRUMBLED TISSUE, CYLINDRICAL BATTERY, FACE MASK, GLASS BOTTLE, GLASS JAR,
LAPTOP CHARGER, MEDS BLISTER, METAL CAP, MIXED PAPER-PLASTIC PACKAGING,
ORGANIC SCRAPS, PAPER BOWL, PAPER CUP, PAPER FOOD PACKAGING, PAPER MAGASINE,
PAPER PACKAGING, PAPER PLATE, PAPER SHEET, PAPER SUGAR BAG, PAPER TRAY,
PHONE CHARGER, PIZZA BOX, PLASTIC BAG, PLASTIC BOTTLE, PLASTIC BOWL,
PLASTIC CAP, PLASTIC CUP, PLASTIC CUTLERY, PLASTIC DISH, PLASTIC GLOVES,
PLASTIC PACKAGING, PLASTIC SNACK PACKAGING, PLASTIC STICKS, PLASTIC STRAW,
PLASTIC TRAY, RECEIPT, SMARTPHONE, TEA BAG, TETRAPACK, TOBACCO PACK,
TRANSPORT TICKET, WOODEN CUTLERY, WOODEN STICKS
```

Toronto columns: `category` (original disposal category), `item` (item names, often
slash-separated aliases), `image`, `popular`, `find_out` (additional information),
`id`, and `instructions` (array of disposal instructions). No aliases were split.

| Exact Toronto category | Rows |
| --- | ---: |
| `Blue Bin` | 373 |
| `Christmas Tree` | 1 |
| `Depot` | 88 |
| `Electronic Waste` | 108 |
| `Garbage` | 2 |
| `Garbage Bin` | 783 |
| `Green Bin` | 208 |
| `HHW` | 275 |
| `Metal` | 53 |
| `Not Accepted` | 99 |
| `Not Accepted ` (trailing space) | 1 |
| `Not accepted` | 1 |
| `Oversized Item` | 128 |
| `Oversized item` | 29 |
| `Yard Waste` | 57 |

## Clothing and electronics coverage

Search is case-insensitive, uses word boundaries and common plurals, and accepts
`t-shirt`/`t shirt` and `bedsheet`/`bed sheet` variants. It searches HF `Phrase` plus
`Class`, and Toronto `item` only, not generic disposal instructions. Each matching
source row counts once even when it matches multiple terms; source duplicates
remain. Exact term lists and regexes are saved in `data/raw/inventory.json`.

| Source | Clothing/textile keyword candidates | Electronics keyword candidates |
| --- | ---: | ---: |
| HF train | 0 | 2,041 |
| HF test | 0 | 455 |
| HF supplementary file (separate) | 0 | 672 |
| Toronto | 45 | 63 |

HF has 2,496 electronics matches in its official splits, all belonging to
`LAPTOP CHARGER` (624), `PHONE CHARGER` (1,014), or `SMARTPHONE` (858).
These are many query variants of only three original categories, not thousands of
distinct device types. Toronto adds broader real item vocabulary. Its 108
`Electronic Waste` rows are distinct from the keyword count: only 44 of the 63
keyword hits carry that category. Keywords also find accessories, packaging and
false positives such as a dead mouse; some real electronics lack those keywords.

Toronto's 45 clothing candidates include clothing, shirts, jeans, pants, sweaters,
coats, jackets, dresses, skirts, shoes, boots, linens, curtains and textiles. The
export also deliberately retains false positives/related accessories such as
paper towels, clothes hangers and shoe boxes. It is a review list, **not 45 approved
clothing training examples**. No third dataset was downloaded: Toronto provides
useful breadth for the initial vocabulary review. A balanced training set is not
established; some requested terms, including hoodies, shorts and socks, had no hits.

## Local files and reproduction

```text
data/raw/
  inventory.json
  electronics_candidates.csv              # 3,231 rows, including HF supplementary
  waste_classification_v2/
    train.csv
    test.csv
    unseen_phrases.csv                     # separate supplementary source, untouched
    download.json                         # revision, timestamp, features, SHA-256
    original_labels.json
    label_counts.csv                      # original label counts per split/source
    sample_rows.csv                        # first five rows per split/source
  toronto_waste_wizard/
    waste_wizard.json                      # untouched source bytes
    metadata.json                         # URL, timestamp, license, SHA-256
    category_counts.csv
    sample_rows.csv
    clothing_candidates.csv               # 45 rows
```

Candidate CSVs keep original columns plus `_dataset`, `_split`, `_source_row`
(zero-based) and `_matched_terms`. Nested arrays and booleans use JSON inside CSV
cells. No canonical target labels are added. Download manifests and the full
inventory contain checksums; offline reinspection verifies raw-file integrity.

```bash
# Acquire once; refuses to overwrite an existing snapshot.
uv run --group data python scripts/inventory_raw_datasets.py
# Rebuild only inventories/candidate exports from checksum-verified local files.
uv run --group data python scripts/inventory_raw_datasets.py --inspect-only
# For a later fresh snapshot, use --raw-dir with a different directory.
```

Do not use `make data-all` for this task: that invokes the older mapping/preparation
pipeline. The source metadata does not provide clear dataset-specific licenses;
keep records local until redistribution/training terms are confirmed. Toronto
disposal categories are not automatically Skopje acceptance rules.

## Deferred ML work

These are English sources, not native Macedonian training/evaluation evidence.
Later work needs reviewed local labels and a grouped bilingual test set, including
Cyrillic, Latin transliterations, clothing, electronics and ambiguous/hazardous
items. No claim of perfect Macedonian accuracy is possible from this inventory.

User-requested next experiment: compare TF-IDF, frozen MiniLM and LoRA using the
same approved data and evaluation protocol. Train/evaluate through Slurm on
`gpgpu01` with `--gres=gpu:1`, host `python3`, and the shared package directory
`/home/hpc/users/ml_models/rebeka.maneva/py_pkgs_cuda126` on `PYTHONPATH`, without a
container. Validate interpreter/dependency compatibility before submitting jobs.
No such jobs, new mappings, model artifacts or app changes were made in this pass.
