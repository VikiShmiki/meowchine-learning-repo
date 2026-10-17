# ML

## Photo suggestion consistency (17 October 2026)

Photo suggestions now check the model's description **and reason** against the
same bilingual item/condition vocabulary used by text policy. An empty/clean enum
cannot override explicit contamination, excluded forms, multiple recyclable kinds,
or a conflicting item identity. Ordinary packaging candidates need a recognizable
matching item kind; an unidentifiable object goes to manual review.

Rejected suggestions return `status: needs_review`, `category: null` and
`item_kind: other`. Specialist hazards retain priority. Valid clothing/electronics
still require user confirmation; used household tissues/nappies retain their
separate residual rule. Editing a description or selecting a photo clears the old
manual selection, confirmation controls and operator links, preventing confirmation
state from carrying over from the previous item.

This checks consistency of model-generated text, not what the pixels actually show.
It does not establish photo-model accuracy or extend local acceptance. The frozen
text-model weights, thresholds and evaluated text-policy code are unchanged.

## Current serving models: development v3 audit correction (17 October 2026)

The current pinned JSON heads are `artifacts/models/ml_v3_audit/{en,mk}.json`.
The earlier heads and reports under `ml_v3` / `data/ml/v3` are preserved as baseline
evidence. These remain development suggestions; local policy and item confirmation
control disposal. A native-reviewed, independently collected user test is still required.

All five follow-up audit goals are implemented:

1. Descriptions matching multiple recyclable item kinds stay held through manual
   confirmation. The existing localized message asks for separate descriptions;
   explicit specialist hazards retain their guidance. This is bounded lexical
   protection, not a general-purpose multi-object parser.
2. Model selection, temperature fitting and gate selection give each concept total
   weight one, shared among its distinct spellings. Reports retain raw row metrics,
   concept-weighted metrics and separate spelling slices. More spellings no longer
   let a poorly performing concept set pass the 95% observed-accuracy gate.
3. Gate calibration uses only cases that actually reach ML through the current
   policy. Full serving replay reports rules-only answers, incremental suggestions,
   unsupported-input suggestions and coverage on that fallback subset. Policy/code
   hashes identify the decision flow used for calibration. Test rows are never used
   to select the settings.
4. Model-file read failures and suggestion-gate failures use the same optional-model
   fallback as encoder failures. The affected language loses suggestions; policy
   guidance and the other language remain available.
5. Historical evaluation joins reviews by source text hash (including the English
   source hashes on MK translations), checks labels and one-to-one coverage, and
   verifies the pinned head → dataset manifest → training rows chain before scoring.
   Fresh report paths are required so prior evidence is not overwritten.

Actual supported development-test inputs reaching ML:

| Language | Supported fallback rows | Baseline accepted | Corrected accepted | Corrected correct |
| --- | ---: | ---: | ---: | ---: |
| English | 30 | 18 (60%) | 18 (60%) | 18 |
| Macedonian, pooled spellings | 42 | 4 (9.5%) | 14 (33.3%) | 14 |

Neither corrected model suggested a label for the held cases reaching ML in this
small development test. This does not establish a population accuracy guarantee;
spellings are correlated and the test was previously inspected. The MK gate is now
confidence ≥ 0.95 and similarity ≥ 0.4, selected on its fallback calibration subset
(53 supported and 26 held rows); EN remains 0.99 / 0.6. No test-driven threshold
adjustment was made. Unknown-input detection and broad MK coverage still need work.

The broader historical manual diagnostic remains imperfect: of the suggestions
actually shown, EN has 16 correct and 2 held-input suggestions (unchanged); MK has
10 correct and 3 held-input suggestions, versus 1 correct and 2 held-input
suggestions with the previous head. These unsupported-case errors remain in the
report. Better development coverage does not remove the need for fresh negative
examples, native review and independent evaluation before release.

The [training report](../data/ml/v3_audit/report.json) includes every candidate,
calibration decision and complete serving replay. The
[serving report](../data/ml/v3_audit/serving_report.json) independently replays the
pinned artifacts on all historical manual cases and the authored development test.
The [baseline replay](../data/ml/v3/audit-serving.json) preserves the preceding heads'
actual fallback results. These reports distinguish suggestions from routing decisions.

Reproduction uses the commands below with a fresh run directory. The evaluator's
`--training-rows` must belong to the pinned head. Its sibling `manifest.json` is
verified by default; `--training-manifest` can identify a relocated manifest. The
same original v3 corpus is used here. New candidate models require explicit hash
promotion in `object_models.py`; training never overwrites serving models.

## Preserved baseline: development v3 (17 October 2026)

The v3 heads replace the v2 suggestions. They are **development models, not a
validated disposal classifier**. Raw weights, encoder revisions, temperature and
abstention settings are in `artifacts/models/ml_v3/{en,mk}.json`; the loader pins
both hashes and verifies metadata, dimensions and numerical values. Inference no
longer unpickles a scikit-learn model. Historical v1/v2 artifacts remain unchanged.

Encoder identity is also enforced: both MiniLM encoders emit 384-dimensional
vectors, so dimensions alone cannot detect accidentally swapped language models.
Before loading, the service checks pinned SHA-256 hashes for the weights,
tokenizer, module/pooling configuration and sentence-embedding settings. The
allowlist is in `src/smart_recycling/encoder_artifacts.py`. A relocated copy of
the pinned snapshot works; changed, missing or unexpected inference files are
rejected. Downloads resolve the fixed revision, pass the same checks, and then
load locally. Checks run at startup, not on each request.
New v3 training runs verify those same files before embedding examples and record
the verifier's code hash. Existing experiment reports retain their original hashes.

An invalid encoder disables suggestions only for that language; `/health` reports
it as `unavailable`, while policy guidance and clarification continue. Explicit
`SRA_MINILM_MODEL_PATH` / `SRA_MULTILINGUAL_MODEL_PATH` settings never silently
fall back to downloads. The Docker cache helpers copy verified upstream bytes
instead of reserializing them. Older directories created with
`SentenceTransformer.save()` may have rewritten metadata and must be replaced
with a fresh verified bundle. To build bundles in new directories:

```bash
uv run python -c "from pathlib import Path; from smart_recycling.minilm import cache_encoder; cache_encoder(Path('models/verified-english'))"
uv run python -c "from pathlib import Path; from smart_recycling.multilingual import cache_encoder; cache_encoder(Path('models/verified-macedonian'))"
```

Configure the corresponding environment variables to those directories. Encoder
verification binds inference to the evaluated representation; it does not add
independent accuracy evidence or change the development-only status of the heads.

On the new authored development test, comparing the old and new heads on the
**same inputs**:

| Slice | Concept support | Old macro-F1 | New macro-F1 |
| --- | --- | ---: | ---: |
| English | 8 objects/class, 48 supported objects | 0.732 | 0.979 |
| Macedonian Cyrillic | Same 48 paired objects | 0.528 | 0.870 |
| Macedonian, pooled distinct Cyrillic/Latin spellings | Same objects, 115 supported strings | 0.491 | 0.847 |

Spelling variants are correlated, not extra independent samples. Pooled variant
support differs by class because identical spellings are deduplicated. Use the
Cyrillic slice for the balanced Macedonian comparison. These explicit-material
noun phrases are easier than unconstrained user requests. Broad material families
overlap across splits; the disjoint unit is the specific authored object concept.
No native review or independent user collection is claimed.

Training retained **5,004** English source examples independently of translation
quality, including all **978 phone-charger and 594 laptop-charger** descriptions.
Only 30 deterministically selected phrases per source group enter fitting (390
source rows), alongside 72 authored training concepts and their language variants.
All legacy automatic Macedonian translations are quarantined from fitting.
Current mapping approvals, explicit material/object checks, duplicate checks and
held-out concept exclusions supersede stale processed approval flags. See
[BILINGUAL_DATA.md](BILINGUAL_DATA.md) for the corpus contract.

Model selection compares C = 0.1, 1, 10, 100 and uniform versus class/concept-balanced
weights, using identical rows and tuning sets for frozen embeddings and TF-IDF.
English selected balanced C=10; Macedonian selected uniform C=100. English-only
training feeds the English encoder; the multilingual head also receives the
retained English and authored English training rows. This is a cross-language
training choice, not a paired-language fairness experiment. TF-IDF's selected
models scored 0.787 EN / 0.753 pooled MK on this test. Complete candidates and
per-class metrics are in [`report.json`](../data/ml/v3/report.json); exact row/group
support is in [`support.json`](../data/ml/v3/support.json).

Temperature is fitted on the tuning set. A separate calibration set selects
confidence/similarity thresholds for maximum coverage, subject to at least 95%
observed accepted accuracy and zero suggestions on its held cases. If no setting
passes, the model abstains on everything. These finite-sample constraints are
**not population guarantees**; the calibration search can overfit.

On the final development test, EN accepted 29/60 inputs: 28 correct supported
suggestions and one held-input suggestion (58.3% supported coverage). MK accepted
20/144 distinct strings: 18 correct supported suggestions and two held-input
suggestions (15.7% supported coverage). Its Cyrillic slice accepted 8/60, all
correct. Unknown detection remains incomplete and Latin coverage is weak.
Do not turn these thresholds into an automatic-routing rule. An accepted model
suggestion only orders clarification choices; policy, exact-item confirmation and
facility acceptance still decide disposal. Negated/dirty/damaged Latin-typed
Macedonian clothing now retains the same holds as Cyrillic.

The false suggestions above are the English and two Latin spellings of “a shirt
and an aluminium can.” They expose a multi-object limitation in the broad model;
the policy layer still holds mixed requests. All supported-class errors and held
false suggestions are retained in [`test_errors.json`](../data/ml/v3/test_errors.json).

The older manual diagnostic has one exact training overlap per language (the
plastic-shampoo-bottle concept). [`serving_report.json`](../data/ml/v3/serving_report.json)
shows both raw and overlap-excluded results. After excluding it, four-stream
macro-F1 is 0.820 → 1.000 EN and 0.653 → 0.890 MK. This maps clothes/electronics
back to the specialist stream, so it is not comparable to six-class macro-F1.
It is a historical diagnostic with semantic overlap and previously inspected cases,
not fresh test evidence. Of its 41 held cases, the new model still suggests a label
for six EN and two MK inputs; policy remains authoritative.

The test contains only eight concepts per class and twelve held concepts. Even
8/8 class recall has an exact 95% binomial interval of approximately 63%–100%;
spelling variants do not narrow that uncertainty.
A fresh native-reviewed user test, including mixed objects, contamination, spelling
variation and unsupported objects, remains necessary before a quality claim.
Do not tune further against this consumed development test.

### Audit corrections to historical interpretation

The historical split has no plastic/metal or specialist test support, only one
clothing test item, and one training group each for glass and plastic/metal.
Plastic training is aluminium cans while validation is plastic bottles. Therefore
six-class macro-F1 and zero seed variation do not establish generalization.
The original LoRA comparison also changed encoder and/or class weighting: balanced
logistic regression versus unweighted cross-entropy. It does **not** isolate a
LoRA effect. The classifier head was trainable; a frozen-head bug was not found.
V3 compares weighting within each encoder and retains frozen models; it makes no
new claim that LoRA is intrinsically worse. Historical runs are evidence of those
configurations only, not a controlled architecture ranking.

### Reproduce without overwriting serving artifacts

After `uv sync --all-groups --locked`, supply the immutable source bundle and
pinned local Hugging Face cache. Use a fresh run directory:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=2 \
  uv run python scripts/train_ml_v3.py \
  --source-root /path/to/source-bundle \
  --encoder-cache /path/to/huggingface/hub \
  --run-dir data/processed/ml-v3-new-run
```

The command writes source/exclusion manifests, model-selection decisions before
test scoring, JSON candidates and a complete report. It refuses an existing run
directory. Both deployed JSON heads reproduced byte-for-byte in a second run.
Candidate promotion requires explicit hash updates in `object_models.py`; training
does not overwrite serving weights. The standard locked runtime needs no PEFT.
For real-encoder historical/manual and policy-boundary replay:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=2 \
  uv run python scripts/evaluate_ml_v3_serving.py \
  --encoder-cache /path/to/huggingface/hub \
  --training-rows data/processed/ml-v3-new-run/data/rows.json \
  --output data/processed/ml-v3-serving-replay.json
```

## V2 five-seed comparison (22 September 2026)

At the user's request, four additional seeds **43–46** ran after the seed-42 v2
experiment below. Slurm array **952** ran the four tasks sequentially on `gpgpu01`;
all finished with exit 0. The four allocations sum to **188s**, and elapsed time
from first start to last finish was **190s**. Python benchmark times were 46.190,
41.159, 40.030 and 43.416s, totaling **170.795s**. Each seed fit all six methods
on the same grouped 3,052 paired training examples per language; the data split
remained fixed at seed 42. Other hyperparameters and model revisions were unchanged.

The table pools seed 42 with the four new runs. Macro-F1 uses all six model labels.
Standard deviations are sample standard deviations across five saved runs.

| Fit | Manual macro-F1 mean ± SD | Grouped-test macro-F1 mean ± SD | Clothes probe correct |
| --- | ---: | ---: | ---: |
| English TF-IDF | 0.548 ± 0.000 | 0.455 ± 0.000 | 4/8 in every run |
| English frozen MiniLM | 0.696 ± 0.000 | 0.505 ± 0.000 | 8/8 in every run |
| English LoRA MiniLM | 0.644 ± 0.044 | 0.237 ± 0.083 | 0/8 in every run |
| Macedonian TF-IDF | 0.467 ± 0.000 | 0.434 ± 0.000 | 3/8 in every run |
| Macedonian frozen MiniLM | 0.507 ± 0.000 | 0.552 ± 0.000 | 7/8 in every run |
| Macedonian LoRA MiniLM | 0.459 ± 0.033 | 0.252 ± 0.034 | 0/8 in every run |

LoRA manual macro-F1 ranges from 0.581–0.698 in English and 0.412–0.496 in
Macedonian; its grouped-test F1 ranges from 0.108–0.333 and 0.220–0.291. TF-IDF
and frozen MiniLM are identical across these five seeds with their fixed features
and logistic solvers. Seed variation does not measure uncertainty from the tiny
clothing set, translations or the inherited test imbalance. These are fixed-split
development diagnostics, not independent evaluation or deployment evidence.

Per-seed reports/models live under `results/bilingual_v2_seed{42..46}/` and
`artifacts/models/bilingual_v2_seed{42..46}/`. The verified 42-row aggregate and
its input hashes are in `results/bilingual_v2_seeds42_46/{summary.csv,manifest.json}`;
Slurm accounting is beside them. Task logs are
`logs/slurm/bilingual_v2_seed952_{43..46}.{out,err}`. The verifier checked 30
artifacts, class maps, dataset hashes and common settings. The completed array
was submitted as shown below. Existing result directories reject another run;
the summary can be regenerated in a fresh directory.

```bash
sbatch --array=43-46%1 --output=logs/slurm/bilingual_v2_seed%A_%a.out \
  --error=logs/slurm/bilingual_v2_seed%A_%a.err \
  scripts/run_bilingual_benchmark_gpu.slurm v2
uv run --group data python scripts/summarize_bilingual_seed_runs.py \
  --output-dir results/bilingual_v2_seeds42_46_recheck
```

## V2 six-class retraining (22 September 2026)

Slurm job **951** completed all six seed-42 fits on `gpgpu01` (A100 MIG 7g.80gb,
CUDA 12.6). Allocation time was **55s**, with zero queue wait; the Python benchmark
took **49.315s**, including dataset verification. Each language trained on 3,052
same-label paired rows. The six output labels are `glass`, `plastic_metal`,
`paper_tetrapak`, `special_unsupported`, `clothes`, `electronics`; `general` has no
reviewed training support and is not a learned output class.

Methods/settings match the preceding experiment: balanced TF-IDF/logistic and
frozen-embedding/logistic heads; pinned English MiniLM for English, multilingual
MiniLM for Macedonian; separate multilingual LoRA adapters (three epochs, batch 32,
learning rate `2e-4`, rank 8, alpha 16, dropout 0.05). Explicit class maps are used
in metrics and persisted artifacts. Source data, prior runs and serving models
are unchanged.

| Fit | Manual accuracy / macro-F1 | Grouped test accuracy / macro-F1 | Clothes probe correct | Electronics probe correct |
| --- | ---: | ---: | ---: | ---: |
| English TF-IDF | 0.627 / 0.548 | 0.529 / 0.455 | 4/8 | 9/9 |
| English frozen MiniLM | 0.814 / 0.696 | 0.646 / 0.505 | 8/8 | 9/9 |
| English LoRA MiniLM | 0.814 / 0.654 | 0.504 / 0.333 | 0/8 | 6/9 |
| Macedonian TF-IDF | 0.559 / 0.467 | 0.499 / 0.434 | 3/8 | 8/9 |
| Macedonian frozen MiniLM | 0.627 / 0.507 | 0.585 / 0.552 | 7/8 | 9/9 |
| Macedonian LoRA MiniLM | 0.610 / 0.446 | 0.418 / 0.291 | 0/8 | 4/9 |

Manual accuracy evaluates 59 supported rows; 41 review-held rows are excluded.
This manual set has no clothing examples. Grouped test has 1,346 rows, including
672 electronics and only one clothing example, and lacks plastic/metal and specialist
waste. Validation has 1,116 rows, with one clothing example and no glass/specialist
waste. All macro-F1 scores average **six** model classes, including zero-support
classes; these scores are not directly comparable to earlier four-class metrics.
Single-class probe accuracy is the useful subset diagnostic, not six-class macro-F1.

The 17 object probes are development-authored: eight clothes (including three
damaged/dirty clothing descriptions) and nine electronics. Correctly identifying a
damaged garment does not authorize donation. Frozen MiniLM handles these probes best
in this run, but the tiny clothing sample and severe split imbalance prevent strong
quality claims. Electronics probe success also does not imply broad coverage: frozen
MiniLM recalls only 40.6%/33.6% of English/Macedonian grouped-test electronics.
LoRA missed all clothing probes in both languages; no additional tuning was performed.
All Macedonian translations still need native review. No independent field evaluation,
abstention calibration, deployment or disposal-policy approval is claimed.

| Fit | Setup | Training | Evaluation (all sets) | Method total | Warm p95 / query |
| --- | ---: | ---: | ---: | ---: | ---: |
| English TF-IDF | 0.000s | 0.192s | 0.155s | 0.479s | 1.017ms |
| English frozen MiniLM | 8.720s | 0.680s | 0.464s | 10.291s | 4.272ms |
| English LoRA MiniLM | 6.043s | 7.436s | 1.069s | 16.572s | 10.357ms |
| Macedonian TF-IDF | 0.000s | 0.267s | 0.179s | 0.609s | 1.140ms |
| Macedonian frozen MiniLM | 3.254s | 0.857s | 0.727s | 5.558s | 7.376ms |
| Macedonian LoRA MiniLM | 2.283s | 7.668s | 0.972s | 13.020s | 10.243ms |

Method totals also include saving and warm latency measurements. The Slurm total
includes Python startup and compatibility gates outside the benchmark timer.
Reports: `results/bilingual_v2_seed42/bilingual_seed42.json` and
`bilingual_seed42_summary.csv`, plus `slurm_accounting.json`. Artifacts:
`artifacts/models/bilingual_v2_seed42/{en,mk}/`. Logs:
`logs/slurm/bilingual_seed42_951.{out,err}`. All data/code/model checksums verify.
Use `sbatch scripts/run_bilingual_benchmark_gpu.slurm v2` for this configuration;
completed directories are protected against overwrite. The direct Python entry
point accepts `--data-dir`, `--results-dir`, `--artifacts-dir` for a fresh reproduction.

## Dataset taxonomy update (before retraining)

The user subsequently requested explicit clothes/electronics dataset labels.
The corrected paired package is `data/processed/bilingual_mk_v2/`, documented in
[BILINGUAL_DATA.md](BILINGUAL_DATA.md). It has seven defined labels and six with
filtered training support; general remains unsupported. Clothing has only 11 train,
one validation and one test example per language. The later v2 retraining is above.
The results below are historical four-class experiments, not measurements of the
new clothes/electronics classifiers.

## Paired English/Macedonian seed-42 run (22 September 2026)

Slurm job 950 completed six independent fits on `gpgpu01` (A100 MIG 7g.80gb,
CUDA 12.6). Each language used the 2,917-row, four-class filtered training split
from [BILINGUAL_DATA.md](BILINGUAL_DATA.md). English and Macedonian rows have the
same labels and paired item groups. TF-IDF used word/character features and a
balanced logistic head. Frozen MiniLM used the pinned English encoder for English,
the pinned multilingual encoder for Macedonian, and a balanced logistic head for
each. Both LoRA fits used the same pinned multilingual MiniLM base, separate
adapters, three epochs, batch size 32 and learning rate `2e-4`. Seed was reset to
42 before each fit. Neither serving model nor disposal policy changed.

Metrics below are closed-set diagnostics. Manual scores use the 59 source-supported
English rows or their development-authored Macedonian counterparts; 41 held rows
are excluded from accuracy/F1. Grouped test has 1,324 rows but no `plastic_metal`
examples. Policy fixture has 47 supported cases; clothing and electronics subsets
are development-authored probes with 5 and 9 cases respectively. All F1 values
include the four benchmark labels.

| Fit | Manual accuracy / macro-F1 | Grouped test accuracy / macro-F1 | Policy macro-F1 | Clothes correct | Electronics correct |
| --- | ---: | ---: | ---: | ---: | ---: |
| English TF-IDF | 0.678 / 0.653 | 0.400 / 0.319 | 0.513 | 0/5 | 1/9 |
| English frozen MiniLM | 0.780 / 0.760 | 0.593 / 0.461 | 0.563 | 0/5 | 1/9 |
| English LoRA MiniLM | 0.797 / 0.791 | 0.901 / 0.687 | 0.558 | 0/5 | 2/9 |
| Macedonian TF-IDF | 0.593 / 0.590 | 0.363 / 0.280 | 0.450 | 0/5 | 1/9 |
| Macedonian frozen MiniLM | 0.678 / 0.665 | 0.795 / 0.658 | 0.483 | 0/5 | 3/9 |
| Macedonian LoRA MiniLM | 0.712 / 0.707 | 0.853 / 0.659 | 0.536 | 0/5 | 3/9 |

| Fit | Model setup | Training | All evaluation sets | Method total | Warm p95 / query |
| --- | ---: | ---: | ---: | ---: | ---: |
| English TF-IDF | 0.000s | 0.157s | 0.148s | 0.428s | 1.031ms |
| English frozen MiniLM | 13.538s | 0.662s | 0.452s | 15.085s | 4.339ms |
| English LoRA MiniLM | 3.624s | 7.580s | 0.915s | 14.048s | 15.082ms |
| Macedonian TF-IDF | 0.000s | 0.222s | 0.170s | 0.538s | 1.119ms |
| Macedonian frozen MiniLM | 4.541s | 0.774s | 0.685s | 6.735s | 7.610ms |
| Macedonian LoRA MiniLM | 2.439s | 7.339s | 1.052s | 12.668s | 10.244ms |

The full Python benchmark took 50.078s; the Slurm allocation took 57s including
startup and compatibility checks. Method totals also include artifact saving and
warm single-query latency checks, so they exceed the setup/fit/evaluation columns.
Validation has 1,093 rows but no `glass` or `special_unsupported` examples.
The training specialist class has 304 examples: 295 battery phrases, nine laptop
charger phrases, zero clothing and zero phones. Consequently, all six fits missed
all five clothing probes. This exposed missing training coverage. In that historical
four-class dataset, clothing and electronics were folded into `special_unsupported`;
the subsequent v2 dataset separates their object labels. Serving-policy/manual
confirmation still controls actual routing and has not changed.

The Macedonian training text and manual probes need native review. The model
quality numbers cannot establish safe use, especially for clothing/electronics.
The previous 8,454-row English benchmark used a different training/evaluation
protocol, so its scores are not directly comparable. Detailed per-class reports,
errors, hashes, artifacts and timings are in
`results/bilingual_seed42/bilingual_seed42.json`; the compact CSV is beside it.
Artifacts are in `artifacts/models/bilingual_seed42/` and Slurm logs in
`logs/slurm/bilingual_seed42_950.*`. All remain ignored by Git.

## Seed-42 GPU comparison (22 September 2026)

One development-only comparison ran through Slurm job 947 on `gpgpu01`: NVIDIA
A100-SXM4-80GB MIG 7g.80gb, CUDA 12.6, host Python 3.10.12, no container. It uses
the specified faculty CUDA package cache on `PYTHONPATH` after the project source
and small pinned package overlay. The job validated Torch 2.13.0+cu126, Transformers
5.13.0, PEFT 0.19.1, Accelerate 1.14.0, Sentence Transformers 5.7.0 and scikit-learn
1.7.2 before work began. Seed is 42 for all methods.

All models used the same 8,454 existing English phrases from the 13 current
source-reviewed Dataset A families, across four labels: `glass`, `plastic_metal`,
`paper_tetrapak` and `special_unsupported`. There are no reviewed `general` training
examples. Toronto clothing/electronics candidates remain raw review lists, so they
were not silently mapped or used to fit a model. The English manual subset has 59
source-supported rows; its Macedonian translations are SHA-linked but all need native
review. The clothing/electronics policy fixture is development-authored and never used
for model fitting or model selection.

| Model | English manual macro-F1 (59) | Macedonian translation-probe macro-F1 (59) | Macedonian policy-fixture macro-F1 (47) | Training | Evaluation all sets | Warm GPU p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TF-IDF word/character + LR | 0.903 | 0.154 | 0.065 | 0.476s | 0.039s | 1.04ms |
| Frozen English `all-MiniLM-L6-v2` + LR | **0.950** | 0.224 | 0.130 | 4.179s | 0.108s | 4.46ms |
| LoRA multilingual `paraphrase-multilingual-MiniLM-L12-v2` | 0.937 | **0.776** | **0.653** | 22.940s | 0.198s | 9.80ms |

Frozen MiniLM setup was 177.052s and LoRA setup 36.524s; cold/cache loading dominates
their actual fitting. The benchmark itself took 245.832s; the Slurm allocation took
4m16s including startup. The LoRA adapter trained 222,724 of 117,878,024 parameters
(0.1889%) for three epochs at `2e-4`, batch size 32; losses were 0.544915, 0.030357
and 0.010361. The adapter weights are 0.9MB, while its saved directory is 18.0MB
because it also contains the tokenizer.

LoRA is the experimental bilingual leader, not an automatic serving choice. Its
Macedonian policy-fixture `special_unsupported` recall is 0.462 (12/26), including
clothes/electronics/hazard cases. It still makes high-confidence false packaging
predictions for some clothing and larger electronics. No abstention threshold was
selected; all numbers are closed-set diagnostics. Do not replace policy guardrails,
the existing serving models or manual confirmation with this adapter.

Ignored evidence is in `results/benchmark_seed42/benchmark_seed42.json` and `.csv`,
with artifacts in `artifacts/models/benchmark_seed42/` and logs in
`logs/slurm/benchmark_seed42_947.*`. Jobs 945 and 946 stopped before training because
their compatibility checks caught a Torch metadata/runtime version representation and
an app-layer Python-3.11 `StrEnum` import. Job 947 is the only result-bearing run.
Before a model choice, review new vocabulary against Skopje policy, obtain native
review, build a leak-resistant bilingual evaluation set and repeat on more seeds.

## Historical Macedonian extension (22 September 2026)

At this stage, policy added Macedonian Cyrillic and bounded Latin spellings.
A separate pinned multilingual encoder with bilingual prototypes supplied
uncalibrated Macedonian suggestions, while English kept its earlier learned head.
Current v3 audit heads replace those suggestions; neither generation can authorize
disposal. See [LANGUAGES.md](LANGUAGES.md) for the 100-query evaluation,
retained errors and native-review limitation.

## Contract

Input is a short item description. Output is one of `glass`, `plastic_metal`,
`paper_tetrapak`, `general`, or `special_unsupported`, plus confidence, model version,
and `abstained`. Specialist waste is a real class; uncertainty produces no category
and requires user confirmation.

## Original evaluation ladder

For the prototype, offer clarification or manual selection on abstention. Broad labels
do not prove site compatibility: preserve item-specific acceptance requirements.
Specialist guidance may link only explicitly accepting facilities; unknown support
must not become a general-waste route. Existing rule scores are heuristic, not
calibrated probabilities. Correction-feedback collection was deferred; current
community observations are a separate feature and do not become training labels.

1. Checked-in weighted keyword rules (`rules-v1`).
2. TF-IDF + logistic regression.
3. MiniLM/DistilBERT only if it materially improves the same evaluation set.

Use seed `42`. Keep an untouched test set, stratify by label, and group paraphrases or
synthetic variants of the same source item in one split. Report per-class precision,
recall, F1, macro-F1, coverage at the abstention threshold, error examples, artifact
size, and p95 inference latency.

Choose the abstention threshold on validation data using the cost of a wrong disposal
instruction. Fit calibration on validation data only. Version each artifact with code
revision, data checksum, split IDs, parameters, seed, metrics, and label map.

Corrections are review data, not automatic truth: deduplicate, quality-check, and
version them before the next training run.

## Historical extension (22 September 2026)

`policy-rules-v3` adds a bounded general-waste subset, confirmed electronics routing,
and clean/wearable clothes donation. `wearable_clothes` remains a specialist item kind,
not a new trained label. Clothing validation is development-authored, not an independent
quality benchmark; no model retraining or accuracy claim accompanies the new card.
The photo schema/instructions now use the same item kinds. No learned model was retrained;
the four-class MiniLM head still cannot suggest general waste.
See [scope, sources and limitations](GENERAL_AND_ELECTRONICS.md).

## Historical serving baseline (T05)

`policy-rules-v2` wraps the legacy rules with specific supported item forms,
condition confirmation, manual recovery and specialist precedence. A category
does not authorize a destination. General-waste and unresolved policy examples
remain held; no new five-class learned model is trained.

Threshold 0.85 is selected on 48 development-authored validation fixtures: maximize
coverage subject to at least 95% answered accuracy, 50% coverage and zero false
answers on held cases, then prefer the highest threshold. Validation answers 32/48
correctly. These fixtures share item families with the manual test and are not an
independent field benchmark or evidence of unseen-family generalization.

The frozen, agent source-reviewed manual subset has 59 queries: 36 answered, 34
correct (61.0% coverage, 94.4% answered accuracy), macro-F1 0.684 across four supported
classes. Forty-one queries remain excluded by the existing evidence review; general
has zero support and null metrics. Two false specialist detections are retained in
the report; the rules were not adjusted to remove those frozen-test errors.
This does not meet a 95% independent-test quality claim or establish release sign-off.

See [artifact report](../data/classifier/README.md) for per-class metrics, latency,
checksums, reproducibility and limitations. Startup rejects mismatched code/policy;
CI reproduces deterministic quality and threshold selection. Scores remain heuristic;
manual selections carry `confidence_kind: manual_selection`, not model confidence.

## Historical baselines

The numbers below are historical, before the local evidence gate. The reviewed
manual subset now has 59 supported/41 held queries and no supported general-waste
examples. It is not a balanced five-class benchmark. New training requires reviewed
coverage of all classes; no new model or updated score is claimed by the policy review.

On the conservative grouped test (2,376 examples), rules score 0.338 accuracy / 0.343
macro-F1 and TF-IDF + logistic regression scores 0.679 / 0.621. On the provisional,
balanced 100-query manual set, rules score 0.520 / 0.602 and TF-IDF scores 0.730 /
0.714. Rules cover 56% of manual queries with 0.929 accuracy when they do predict.

The grouped test withholds entire Dataset A fine-label families and is intentionally
hard; some classes have few examples in a split because the source has no finer item
ID. Treat manual metrics as provisional until every row is reviewed. Do not treat a
transformer result as release-eligible until mappings and item-family coverage improve.

## Historical four-class MiniLM suggestion model

The user-requested next comparison uses the immutable Apache-2.0
`sentence-transformers/all-MiniLM-L6-v2` revision
`8b3219a92973c328a8e22fadcfa821b5dc75636a`. It normalizes frozen 384-dimensional
sentence embeddings and trains only a balanced logistic-regression head with seed 42.
It does not fine-tune MiniLM and does not replace the authoritative policy rules.

At that stage, the application loaded the four-class head as an explicitly
uncalibrated, suggestion-only fallback when reviewed rules could not identify an
exact item form. It has since been replaced by the v3 audit heads documented above.
It may suggest `glass`, `plastic_metal`, `paper_tetrapak`, or
`special_unsupported`; it cannot suggest `general`. The API keeps `category: null`,
`abstained: true`, and `status: clarify`, while returning the suggestion separately
and placing matching exact-item choices first. Hazard/held rules run before the model.
The user must still select the exact item kind and confirm its condition, and routing
revalidates that item against asset-level acceptance. This limited integration does not
promote the model to an authoritative disposal classifier or claim that its failed
abstention gate passed.

`make minilm-development` provides an explicitly non-serving signal check using 8,454
deduplicated phrases from the 13 currently approved Dataset A families. It trains four
supported classes, selects abstention only on the 48-case development set (including
16 held cases), and evaluates the frozen 100-query manual set only after selection.
The local CPU run scored 0.938 accuracy / 0.937 macro-F1 on the 32 supported validation
queries and 0.949 / 0.950 on the 59 supported manual queries in closed-set mode.

Those closed-set numbers do not make the experiment safe to serve as an authoritative
classification. Every candidate
threshold failed the existing gate of at least 95% answered accuracy, 50% coverage and
zero answers on held validation cases. Even at 0.99, it answered four held cases and
covered only 39.6% of all validation cases. No threshold was selected. Local
single-query CPU latency was 15.4 ms p50 / 47.4 ms p95 in the final run, excluding HTTP
overhead. Item families overlap across source, validation and manual fixtures, so this
is not an unseen-family or independent field benchmark.

The bare-metal Slurm reproduction uses `gpgpu01`, one GPU, host `python3`, the faculty
CUDA 12.6 package cache and a small ignored project-local Python package layer—no
Singularity/Apptainer image or virtual environment. Run
`make minilm-cluster-bootstrap` once, then `make minilm-cluster-submit` from the repo
root. The job pins and checks every relevant host-package version before training and
writes separate ignored GPU results/artifacts.

Final Slurm job 893 completed on an NVIDIA A100-SXM4-80GB MIG 7g.80gb allocation with
PyTorch 2.13.0+cu126. Training embeddings plus the logistic head took 0.904 seconds,
versus 15.025 seconds in the final CPU run. Warm single-query GPU latency was 4.22 ms
p50 / 4.81 ms p95. The self-contained repeat took 21 seconds wall time with warm shared
filesystem caches; the preceding cold-cache run took 2:05, showing that bare-host import
and startup time dominate this small workload. Metrics and threshold failure were
identical to CPU. The host uses Python 3.10.12, outside the application's declared
Python 3.11–3.12 range, so this is a benchmark runtime only and not evidence for the
deployment environment.

`make minilm-evaluate` is the release-oriented five-class path. It validates review
provenance before loading the remote model, preserves grouped splits, selects
abstention on validation only, and writes ignored artifacts/results locally. It
intentionally refuses to train until reviewed train, validation and test splits contain
all five canonical classes. The current review has no supported `general` examples, so
completing source/human review is a data prerequisite rather than a model error. Never
bypass this check with the historical auto-approved dataset.

## Historical four-class serving and artifacts

The tracked 7.4 KiB CPU-trained joblib contains only the balanced logistic-regression
head. A matching metadata file records its immutable encoder revision, labels, data
hashes, failed selection gate and SHA-256. Runtime loading verifies a hard-coded artifact
digest and the full contract before deserialization; paths are operator configuration,
never user uploads. The GPU-generated head is not shipped because it was created with a
different scikit-learn version.

The approximately 87 MB encoder weights are not committed to Git. Local development
downloads the pinned Hugging Face revision on first use, or `SRA_MINILM_MODEL_PATH` can
point to an existing copy. The Docker build downloads that same revision once and stores
it in the image. The API loads both encoder and head at process startup and reuses them
for requests. On the faculty shared filesystem the observed cold process took about
two minutes, while warm single-query inference was about 5 ms on the tested GPU; neither
is a hosted/iPhone benchmark.

Set `SRA_MINILM_SUGGESTIONS=false` to disable the learned fallback. Missing or invalid
artifacts leave the evaluated rules available and make `/health` report the suggestion
model as unavailable. Never load a user-supplied pickle-compatible file.

If on-device inference becomes necessary, export the chosen model to ONNX, quantify
binary/model size and latency on representative phones, and run golden-input parity
tests against Python before release. Do not select a transformer or mobile runtime
before it beats the simpler baseline on the fixed evaluation set.
