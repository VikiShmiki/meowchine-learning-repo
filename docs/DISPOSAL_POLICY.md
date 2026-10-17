# Skopje disposal policy review

Current guidance uses `skopje-policy-v2`; see the bounded
[general/electronics extension](GENERAL_AND_ELECTRONICS.md) reviewed 2026-09-22.
The same citizen policy includes [clothes donation](CLOTHING_DONATIONS.md), distinct
from damaged-textile recycling and never a fallback to general waste.
The unchanged infrastructure/City calculations retain v1. The historical review below
is version `skopje-policy-v1`, reviewed 2026-09-19 using operator publications.
This is agent source review, not human sign-off, municipal approval, field verification,
or a guarantee of current facility operation.

## Evidence

| ID | Source | Supported scope |
| --- | --- | --- |
| `pakomak_streams` | [Waste streams](https://pakomak.mk/Pages/Index/vidovi_na_otpad) | Green glass packaging; yellow plastic/metal packaging; blue paper/Tetra Pak |
| `pakomak_faq` | [Citizen FAQ](https://pakomak.mk/FaqItems) | Q18: Tetra Pak in blue; Q20: bags in yellow; Q25: plastic/glass packaging must be empty; Q26: contact for bulk caps |
| `pakomak_vending` | [Machine instructions](https://pakomak.mk/Pages/Index/povratni_vending_masini) | Plastic bottles/cans; PET is named; not all plastic/metal forms |
| `nula_categories` | [Nula Otpad](https://nulaotpad.com.mk/) | Electronics/batteries; no universal facility acceptance established |
| `nula_pickup` | [Collection requests](https://nulaotpad.com.mk/prijavi-e-otpad) | Electronic-waste pickup contact, not a verified walk-in facility |

Machine-readable sources and scoped profiles:
[`skopje_v1.json`](../data/policy/skopje_v1.json). The machine profile uses a
conservative beverage-bottle/can subset; this is an app constraint, not a claim that
the operator explicitly rejects all other cans. Broad stream evidence never overrides
narrower site capabilities or unknown item contents/condition.

## Review results

All 50 Dataset A families have explicit decisions in
[`needs_manual_review.csv`](../data/mappings/needs_manual_review.csv): 13 supported
for broad classification, 37 held. The legacy filename is retained. Plastic bags
are newly supported by direct FAQ evidence. Contaminated/composite packaging,
medical items, and unverified general-waste assumptions remain held. Missing review
records fail validation instead of becoming implicit approvals.

Toronto names remain proposals pending explicit review. New rule suggestions use
`needs_review`; legacy `auto_approved` rows cannot enter augmentation/combination.
The previously reported 2,291 unresolved items are not reviewed here: their generated
mapping file is absent. After regeneration, prioritize common bottle/can/paper
families, then ambiguous packaging and specialist subtypes with evidence.

The original 100-query manual test is unchanged. The separate
[`manual_test_review.csv`](../data/evaluation/manual_test_review.csv) records every
decision by query SHA-256: 59 supported, 41 held. Missing material details and
unverified general/specialist labels are held. Classification of damaged batteries
as specialist does not establish acceptance at ordinary battery collection points.

Baseline evaluation now selects supported queries and reports subset size, class
balance, review checksum, and review scope. The subset has no supported general-waste
examples and is not a balanced five-class release test. Historical provisional
100-query scores are not comparable. Training rejects stale approvals and missing
classes. Use `--skip-baselines` while preparing data with these gaps. No new model
was trained in this task.

## Handoff to ingestion and serving

Known-waste routing now has an explicitly acknowledged general-bin navigation mode:
it uses source records identifying mixed-municipal-waste containers and labels their
acceptance unverified. This is not an item-acceptance policy, a classifier fallback,
an approved training label, or a change to City coverage. Existing general/specialist
evidence holds remain intact; follow container instructions and exclude hazardous,
medical and bulky waste.

- Preserve asset source, collection mode, capabilities, and operational uncertainty
  when grouping sites. A site's union of labels must not broaden machine acceptance.
- Scope Tetra Pak support to the documented Pakomak blue-container profile, not all
  third-party paper sites.
- The snapshot advertises bottles/cans at yellow assets. Plastic-bag classification
  is supported, but routing bags remains unavailable until site acceptance is evidenced.
- No specialist facility is verified in the shared snapshot. Use Nula Otpad as an
  electronics/battery guidance contact; do not invent a destination at its office.
  Damaged batteries, medicines, chemicals, and lamps need subtype-specific evidence.
- Unknown acceptance requires clarification/guidance. Recycling exclusion never
  establishes general-waste acceptance.

T03 attaches these profiles to individual assets in the real snapshot API. T05 now
serves evidence-scoped rules with manual item/condition confirmation and specialist
guidance. The original review files and all evidence holds remain unchanged;
general waste and unreviewed Toronto proposals do not become approved ground truth.
Plastic bags remain unavailable for matching, even where their broad classification
is supported. No verified specialist facility exists. Item-specific real lookup is
still a subsequent task; the citizen page no longer uses the synthetic nearest API.
