# English and Macedonian

Goodsort supports `en` and `mk`. The header selector switches both ways without a
reload, retaining input, selected item kinds, basket, origin, route and open panels.
The choice is stored as `goodsort-language` and survives page navigation/reload.
English is the default. Citizen, City, account/activity, community and reviewer copy,
accessible labels, placeholders and validation messages have Macedonian translations.
If the catalog cannot load, the page keeps English controls and displays a retry notice.

`web/locales/mk.json` is the shared copy catalog. English source text is the key;
`{0}`, `{1}`, etc. are ordered template arguments. More specific templates take
precedence. `web/i18n.js` localizes the rendered presentation and remembers source
text per node; application state and machine identifiers stay unchanged. New dynamic
nodes and accessible attributes are observed. User input, usernames, submitted
descriptions, model-written descriptions/reasons and filenames remain verbatim.
Recorded street addresses, operator names, links and source identifiers retain their
source spelling; municipality names have translations. Search matches Cyrillic and
Latin spellings. No translation API receives user text or account data.

## Text and photo behavior

The language of an item description is independent of the interface language.
`language.py` normalizes explicitly listed Macedonian forms and their Latin spellings
at every policy boundary, including trip revalidation and photo guardrails. It keeps
unknown tokens and preserves negative, contaminated and hazardous signals. It does
not translate arbitrary prose or establish that an item is clean. Existing manual
confirmation, specialist precedence and asset-level acceptance checks still apply.
The classifier artifact hashes this lexicon along with the rules.

Learned suggestions now use the hash-pinned, seed-42 six-class frozen MiniLM heads
selected from the five-seed comparison in [ML.md](ML.md). English uses
`all-MiniLM-L6-v2`; Macedonian uses the separate
[`paraphrase-multilingual-MiniLM-L12-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
encoder. Both heads predict object labels including `clothes` and `electronics`,
which map to the app's `special_unsupported` stream and distinct review choices.
The English head is never applied to multilingual embeddings. Scores are
uncalibrated closed-set probabilities, not disposal confidence; the classifier
remains abstained until exact-item selection/condition confirmation. No automatic
general-waste prediction is introduced. The request's selected language chooses
the head, even when the description uses another script; translation is not applied.
Native review and independent quality evidence remain outstanding.

Both models load when `SRA_MINILM_SUGGESTIONS=true` (the default). Optionally set
`SRA_MULTILINGUAL_MODEL_PATH=models/multilingual-minilm` to a local saved encoder.
Otherwise the pinned revision is downloaded once. Docker bundles both encoders.
Macedonian model failures are reported separately in `/health`; policy/manual flows
remain usable. Ordinary tests disable downloads and inject encoders/provider responses.

Photo requests send `Accept-Language: mk` to request Macedonian Cyrillic descriptions
and reasons. JSON keys, item-kind enums, upload/privacy limits and confirmation
requirements remain unchanged. The existing Responses adapter uses request-local
language context, so simultaneous English/Macedonian requests cannot overwrite each
other's language. Photo descriptions and hazard reasons are checked by bilingual rules.
Changing UI language does not rewrite a previously generated description or resend a
photo; a new analysis uses the selected language.

## API

- `Accept-Language` negotiates `en`/`mk`, including regional tags and quality weights.
- `/api/v1/classify` also accepts optional `language: "en" | "mk"`; it overrides
  the header for guidance copy, questions, choices and learned-head selection.
- Known application errors are localized; stable status codes, enum values and IDs
  are preserved. Snapshot data/ETags remain canonical. API responses vary by
  `Accept-Language`; private trip/account cache protections still apply.
- `/health` adds `supported_languages` and `macedonian_suggestion_model`.

## Tests and evidence

`tests/fixtures/macedonian.json` contains 68 paired policy cases, tested in Cyrillic
and Latin transliteration: supported forms, inflections, six flows, unknown/mixed
items, specialist priority and unsafe manual overrides. The existing six-category
pipeline now runs in both languages: picker/text/photo × GPS/map/manual origin ×
walking/driving (108 cases per language), with real policy/data/route solver and
simulated external transports. Macedonian photo fixtures return Cyrillic content.
Additional browser cases cover switching during work, persistent navigation,
accounts/badges, City upgrades, catalog failure, Cyrillic search and responsive layout.

`data/evaluation/manual_test_mk.csv` pairs all 100 original English manual queries
using SHA-256 links. Original English labels and their review holds are unchanged.
Translations are marked `needs_native_review`. Run:

```powershell
uv run python scripts/evaluate_macedonian.py
$env:SRA_BROWSER_TESTS = '1'
uv run --all-groups pytest
node --test tests/web_guidance.test.js tests/web_map.test.js
uv run python scripts/smoke_deployment.py --require-minilm --require-macedonian
```

The historical prototype-model report is `data/classifier/evaluation-mk-v1.json`: 54/59 correct
(91.5% closed-set accuracy), macro-F1 0.922, p95 about 28 ms on this host excluding
startup. Five mistakes are retained. Only the 59 inherited source-supported labels
are scored; the other 41 retain their holds. No fitting or threshold selection uses
these queries. The translations and prototypes are development-authored, so this is
not an independent native-speaker or field-quality claim. Native wording review and
broader independent model evaluation remain useful follow-ups. Live paid vision,
hosted/container execution and physical-phone checks are not claimed by these tests.

That historical evaluation report includes the exact prototype-set SHA-256 alongside the paired
dataset hash. Offline tests reject stale evidence after either input changes; rerun
`scripts/evaluate_macedonian.py` after reviewed prototype/data changes. The refreshed
report retains 54/59 correct; native-language and field validation remain outstanding.
