# Macedonian dataset translations

## Current fitting corpus: development v3

`data/ml/v3/items.tsv` defines 72 train and 48 each tuning/calibration/test
object concepts, paired in English and Macedonian. Every role has all six object
classes. `held.tsv` adds 12 ambiguous, mixed or out-of-scope concepts per evaluation
role. Concept groups and normalized text cannot cross roles. Macedonian canonical
and simplified Latin spellings stay in the same group as Cyrillic; they are not
independent observations. These are agent-authored diagnostics requiring native
review, not collected user data or authoritative local disposal labels.

`src/smart_recycling/data/ml_v3.py` reconstructs fitting data from the immutable
`data/processed/dataset_a.csv` in an explicitly supplied source bundle. It uses
current mapping approvals, requires explicit material/object signals, protects
held-out authored concepts, and checks normalized-text/group separation. It keeps
English independently of translation availability: all 978 phone and 594 laptop
charger phrases survive. Of 25,711 source rows, 5,004 survive screening; 17,257
have no currently approved mapping, 3,302 lack explicit material/object evidence,
and 148 contain reserved development concepts. These conservative exclusions
include potentially valid descriptions; they are quarantines, not asserted errors.

Fitting samples at most 30 phrases per original source group to limit template
dominance. All legacy automatic Macedonian translations are excluded from fitting,
including the erroneous apple-charger and water-pump translations. English/source
approvals remain agent source review; authored Macedonian remains
`agent_authored_needs_native_review`. A positive training label identifies an
object stream, never the item's cleanliness or a site's acceptance.

Each run writes `rows.json`, the full retained-English inventory, hashed exclusion
records and a manifest with relative `source:`/`repo:` inputs and content hashes.
Raw/derived source text stays ignored under `data/processed/`; only authored
fixtures, model weights and aggregate evidence are tracked. Old v1/v2 packages
and their reports are unchanged. Historical v2 verification now accepts
`--source-root` to relocate its source bundle while checking every original hash
and rejecting path traversal or escaping symlinks.

For native review, review the paired TSVs with role/group assignments frozen;
record reviewer, date, accepted/corrected/ambiguous status and reason. Corrections
create a new version. Collect a separate user-query test without showing users
model output; include uncertainty and mixed items. Do not relabel this consumed
agent-authored test as independent evidence. Reproduction and results are in
[ML.md](ML.md).

## Historical dataset: v2 object classes

At the user's request, `data/processed/bilingual_mk_v2/` adds explicit `clothes`
and `electronics` labels alongside the original five. The full English/Macedonian
CSV/JSON mirrors are actually relabeled; this is not just a candidate list.
`data/mappings/object_classes_v2.json` records the source-ID review and exclusions.
Raw downloads, v1 and its completed benchmarks remain unchanged and reproducible.

HF charger/phone families account for 3,168 relabeled phrases: 2,041 official train,
455 official test and 672 supplementary rows. Toronto contributes 20 clothes and
182 electrical/electronic item records. Clothes includes garments and complete
footwear, not hangers, boxes, bedding or cleaning cloths. Electronics includes
devices, chargers, cables and clearly electrical appliances. Loose batteries,
ink/toner, manual devices and mixed electric/manual rows are not blanket-reclassified.
Object identity does not establish safe disposal or donation eligibility: damaged
electronics remain electronics, with their original policy metadata preserved.

Use `experimental/{train,validation,test}_{en,mk}.csv` for filtered paired data:

| Split | Rows per language | Clothes | Electronics |
| --- | ---: | ---: | ---: |
| Train | 3,052 | 11 | 133 |
| Validation | 1,116 | 1 | 22 |
| Test | 1,346 | 1 | 672 |

`experimental/paired.csv` carries both texts and source IDs; `*_bilingual.csv`
contains both languages. All 5,334 retained v1 pairs preserve text and split.
The additional 180 pairs use actual catalogue names, without generated templates.
New reviewed groups are assigned approximately 70/15/15 with seed 42; synonyms,
duplicate translations and inherited groups are kept together. Eleven translation
holds, eight reserved evaluation-text collisions and three duplicates are excluded.
The shirts translation means braids: its correct source label is retained in the
full mirror, but the pair is held pending text repair. All translations still need
native review, including unflagged outputs.

Other v2 files:

- `raw/waste_classification_v2/*_{en,mk}.csv`: all 34,155 original rows; `Class`,
  `Class_index` and `label` use the seven-label taxonomy. The original source fields
  survive as `source_class` and `source_class_index`.
- `raw/toronto_waste_wizard/*_{en,mk}.json` and `catalogue/toronto_{en,mk}.csv`:
  all 2,206 source items; reviewed clothes/electronics have `label` values, while
  unrelated/unreviewed catalogue entries keep blank labels. Toronto disposal
  categories/instructions are provenance, not Macedonian acceptance rules.
- `processed/*_{en,mk}.csv`: relabeled full legacy prepared tables, including
  unreviewed rows; these are not substitutes for the filtered experimental splits.
- `evaluation/*_{en,mk}.csv`: relabeled manual/guidance counterparts and 17
  clothes/electronics object probes. Prior policy evaluation holds are retained
  separately; object-label review does not lift disposal-policy holds. Torn/wet
  clothes remain clothes, whereas descriptions mixing clothes with unrelated waste
  remain unresolved rather than receiving a blanket clothing label.
- `relabel_audit.csv`, `manifest.json`: row-level label audit, source/output hashes,
  class counts, exclusions and limitations. All source-derived records stay ignored.

Clothing support is far too small for meaningful quality claims. Training supports
six labels: general still lacks reviewed examples. Validation still lacks glass,
general and specialist waste; test lacks plastic/metal, general and specialist waste.
These new splits do not fix the inherited imbalance or establish independent native
Macedonian quality. The later six-fit v2 retraining completed as Slurm job 951;
results and timing are in [ML.md](ML.md). The benchmark supports an explicit v2
dataset argument while keeping v1 as its historical default. No model was deployed.
Four additional v2 seeds (43–46) completed in Slurm array 952; their five-seed
comparison is recorded in [ML.md](ML.md).

```bash
uv run --group data python scripts/relabel_datasets.py
# Existing versions are never overwritten; use --output for a fresh reproduction.

# Retrain both languages and all three methods on v2 (job 951 already completed):
sbatch scripts/run_bilingual_benchmark_gpu.slurm v2
# Completed result/artifact directories are protected against overwrite.
```

## Historical translation package: v1

The local package is `data/processed/bilingual_mk_v1/`. It preserves English
sources and adds Macedonian Cyrillic translations for all 34,155 Hugging Face
query rows (including the separate supplementary file), all 2,206 Toronto
catalogue records, every prepared classifier text table, and the manual/guidance
evaluation tables. Repeated text is translated once and reused. All translated
rows have `translation_review_status: needs_native_review`.

Completed on 22 September 2026: 36,543 unique strings, 27 output tables. Slurm job
949 resumed the saved batches from job 948 and completed successfully. Input and
output checksums, source-row preservation, manual-review holds and experimental
split separation were verified. The filtered exports contain:

| Split | English rows | Macedonian rows | Bilingual rows |
| --- | ---: | ---: | ---: |
| Train | 2,917 | 2,917 | 5,834 |
| Validation | 1,093 | 1,093 | 2,186 |
| Test | 1,324 | 1,324 | 2,648 |

Of the 15,820 historical prepared rows, 7,664 have held local labels, 1,794 fail
translation screening, 144 collide across splits, seven have conflicting labels,
and 877 repeat an already retained source/translation. These exclusions leave
5,334 experimental pairs; every source row remains in the complete mirrors.
The QA table flags 3,396 unique translations, including two repetitive outputs
that reached the generation limit. Those failures need correction before use.

The first separate English/Macedonian seed-42 model comparison is documented in
[ML.md](ML.md). The filtered specialist training examples cover batteries and a
few laptop chargers, with no clothing or phones; the model results expose that
gap. The original complete source mirrors remain available for local-policy and
native-language review before expanding the training set.

Translation uses the local
[NLLB-200 distilled 600M model](https://huggingface.co/facebook/nllb-200-distilled-600M),
revision `f8d333a098d19b4fd9a8b18f94170487ad3f821d`, English `eng_Latn` to
Macedonian `mkd_Cyrl`, seed 42, four beams, no sampling, batch size 32, and a
256-token output limit. Model weights are cached under `runtime/huggingface/`.
The model is CC-BY-NC-4.0 and intended for research. Dataset-specific source
terms remain unresolved; all generated source/translation records stay local
and Git-ignored, as do the existing English source records.

## Files to use

| Path inside the package | Purpose |
| --- | --- |
| `experimental/train_mk.csv`, `validation_mk.csv`, `test_mk.csv` | Macedonian experimental splits filtered by current local label review and mechanical translation checks |
| `experimental/train_en.csv`, `validation_en.csv`, `test_en.csv` | Matching English rows for comparisons |
| `experimental/train_bilingual.csv`, `validation_bilingual.csv`, `test_bilingual.csv` | Both languages, with shared `pair_id`, `item_group`, and split |
| `experimental/paired.csv` | Full provenance and English/Macedonian text for retained pairs |
| `experimental/excluded.csv` | Every excluded prepared row with a reason |
| `raw/waste_classification_v2/*_mk.csv` | Complete translations of the official train/test and supplementary sources; original source splits retained |
| `raw/toronto_waste_wizard/waste_wizard_mk.json` | All item names, instruction arrays and nonempty additional text translated; Toronto categories/IDs retained |
| `processed/*_mk.csv` | Complete mirrors of existing prepared datasets, including historical/unreviewed rows |
| `evaluation/*_mk.csv` | Translated evaluation tables; the pre-existing authored manual translation is kept separately as `manual_test_existing_mk.csv` |
| `translation_qa.csv` | Unique translations flagged for review |
| `manifest.json` | Completion state, checksums, source/model versions, counts, exclusions, missing classes and limitations |

Translated text occupies the original input column (`text`, `Phrase`, `item`,
etc.); the corresponding `_en` column preserves the original value. Canonical
labels, source IDs, original categories and inherited splits retain their
meaning. `english_text_sha256` links each translated input to the exact English
text. Translation does not approve a disposal label. Source mirrors retain old
mapping fields and add `current_mapping_status` where applicable; use the
`experimental/` exports for the filtered comparison, not the unfiltered mirrors.

The 100 manual rows retain their review decisions: only 59 have a nonblank
`evaluation_label`. The existing authored Macedonian manual set is preserved
verbatim; the machine-translated version is a separate probe. Toronto instructions
remain Toronto policy even when written in Macedonian.

## Training and evaluation limits

The experimental exports reuse the existing grouped split assignment. An English
row and its Macedonian translation always belong to the same split. Current
local mapping review excludes stale automatic approvals and held families.
Normalized English or translated text that occurs in multiple splits or under
conflicting labels is quarantined on both sides. Repeated translations within
one split retain one pair. Exclusions remain available in the complete mirrors.

These inherited splits do **not** cover every class in every partition: among
currently reviewed labels, validation lacks glass and specialist waste, while
test lacks plastic/metal. There are no reviewed general-waste training examples.
The manifest reports actual remaining class counts. Do not interpret an aggregate
score on these splits as full four-/five-class quality, or repartition individual
English/Macedonian rows randomly to improve balance.

Mechanical checks flag empty/unchanged output, absent or non-Macedonian Cyrillic,
extreme expansion, repeated text, generation-limit hits, and possible loss of
selected material/condition terms. These are review hints with possible false
positives; they cannot establish translation correctness. Samples include wrong
word choices and dropped item details, so even unflagged rows need native review.
Translated tests measure performance on translated text. They do not replace a
separate evaluation with Macedonian descriptions written by native speakers.

## Reproduction

```bash
# Faculty GPU workflow; uses the same host/package overlay as the benchmark.
mkdir -p logs/slurm
sbatch scripts/translate_datasets_gpu.slurm

# Run directly in a compatible CUDA Python environment:
python scripts/translate_datasets.py

# Resume a stopped run, or rebuild exports from a complete cache without loading a model:
uv run --group data python scripts/translate_datasets.py --resume
```

The SQLite cache commits after each batch. Resumption rejects changed source
checksums or translation settings. `manifest.json` is written after all exports
are complete and source hashes are rechecked. A partial cache is not a completed
dataset. A different snapshot/settings combination needs a different `--output`
directory. Ordinary tests use a small fake translator and do not download a model.

This task prepares datasets only; it does not train a new classifier or change
the application's serving models.
