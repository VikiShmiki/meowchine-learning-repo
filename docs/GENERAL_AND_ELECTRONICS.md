# General waste and electronics — 22 September 2026

Follow-up: [Clothes donation](CLOTHING_DONATIONS.md) adds five citizen venues and a
sixth card. Current combined citizen totals are 1,590 sites / 1,603 records; the
electronics-only subtotal below documents the earlier stage.

## Delivered scope

- Text and photo review can suggest general waste for used household tissues/nappies.
  The user sees “This item is not recyclable. Use general waste.”
- Electronics has its own quick-pick card, map filter/colour and trip stops.
  It remains the canonical specialist category, with a specific `electronics` item kind.
- Walking, driving and scheduled JSP trips can combine electronics, general waste
  and existing recyclables; driving can optionally include parking.
- Batteries, hazardous conditions and unknown items do not default to general waste.
  Neither a model category nor a model-generated place name authorizes a destination.

## Location research

**Routable: Karpos recycling yard.** Municipal operator
[Komunalna Higiena](https://khigiena.com.mk/content/?id=4020) publishes electrical/
electronic-appliance drop-off at Karpos, free, daily 07:00–19:00.
[Karpos municipality's July 2026 notice](https://karpos.gov.mk/бесплатно-одлагање-на-кабаст-отпад-во/)
places it behind Makpetrol on Ilinden Boulevard, near Boris Trajkovski Sports Centre.
The coordinate is the mapped entrance
[OSM node 3910765530](https://www.openstreetmap.org/node/3910765530), belonging to the named
[Karpos station way 1497810842](https://www.openstreetmap.org/way/1497810842):
42.0085277, 21.4002845. This is a source cross-match, not an on-site inspection.
OSM coordinates are attributed under ODbL; municipal facts are paraphrased, not a copied database.
The app excludes loose batteries, lamps and hazardous conditions from this site's routing subset.
Published hours are not a live “open now” guarantee.

**Routable for small devices: East Gate Mall.** [Elkolekt's 18 December 2024 announcement](https://www.elkolekt.mk/елколект-и-електро-еко-грижа-со-ново-со/)
documents small electrical/electronic equipment and used-lamp collection at the mall.
It does not give a precise container entrance or current access confirmation.
Routes now end at the mapped main entrance, [OSM node 12249116577](https://www.openstreetmap.org/node/12249116577)
on [mall way 28221187](https://www.openstreetmap.org/way/28221187): 41.9977993, 21.4509501.
The stop visibly says to ask the information desk for the collection point. This is
an entrance-level destination, not an exact indoor bin or a live operational check.
Operator contact: +38971263500. No invented opening hours or large-appliance acceptance.
The conservative `small_electronics` subset covers phones, chargers, cables and earbuds.
Generic/larger electronics remain Karpos-only; small devices can use either destination.
The quick picker asks whether only those small devices are being carried. Text/photo
review uses the same typed subset and cannot override a fridge into a small-device route.

**Collection service / incomplete inventory: Nula Otpad.**
[Official collection/pickup information](https://nulaotpad.com.mk/) and
[pickup requests](https://nulaotpad.com.mk/prijavi-e-otpad) remain available from guidance.
This means requesting collection from the user's home/business, not walking to an
office or bin. The operator advertises free collection; call 070236000 or submit the
device list and collection address, then confirm eligibility and arrangements with them.
The site's embedded collection map (Google My Maps ID
`1IOPRL03VnIE3bA7ZtMxKCjzrSMQmXk8`) exported 377 address records but zero Point geometries
when checked. No bulk map data is redistributed or routed to. The office address is
not treated as a drop-off facility; battery-only containers are not electronics sites.

## General-waste evidence boundary

[Karpos household-waste guidance](https://karpos.gov.mk/карпош-потсетува-за-совесно-одложува/)
directs household waste to municipal containers, separately from bulky/electronic waste.
Mapping ordinary used personal tissues/nappies to that stream is an explicitly recorded
agent policy inference, **not** an item-by-item municipal approval or human sign-off.
The app does not infer that every item rejected by recycling belongs in general waste.
Medical/clinical waste, chemical contamination, ambiguous packaging and mixed descriptions
stay outside this automatic subset. General stops use the existing recorded municipal-bin
locations; their field verification and acceptance uncertainty remain in route metadata.

## Models and data

`policy-rules-v3` / `skopje-policy-v2` add the two guidance paths. Photo structured output
uses the same item vocabulary; the server derives category/status and preserves hazardous
signals through review. Confirmation copy differs for residuals, devices and empty packaging.
OpenAI integration retains strict JSON-schema output and the user's configured model, following
the [Structured Outputs contract](https://developers.openai.com/api/docs/guides/structured-outputs).

The original destination extension did not train a model. Current serving uses
six-object development-v3-audit suggestion heads, including clothes/electronics;
there is no `general` object label. Policy handles the bounded residual subset
before learned fallback. Independent general-waste accuracy remains unmeasured.
See [ML.md](ML.md) for current models and clearly separated historical evidence.

The pinned `city` snapshot, policy v1, coverage and upgrade artifacts are unchanged.
New `scope=citizen` composes those 1,583 sites with two separately versioned/checksummed
electronics destinations (1,585 sites / 1,598 assets), catalog `skopje-electronics-v2`.
Its as-of date conservatively retains
the oldest base date; each added asset records its own research date.
The new browser cache is separate from the old City cache.

## Reproduce

Run `uv run --group data python scripts/evaluate_guidance.py`, then `make check`.
If an existing ignored `.env` explicitly sets `SRA_CLASSIFIER_PATH=...rules-v2.json`,
change that setting to `data/classifier/rules-v3.json`; keep infrastructure
`SRA_POLICY_PATH` at v1 and guidance `SRA_GUIDANCE_POLICY_PATH` at v2.
Set `SRA_BROWSER_TESTS=1` for real HTTP/browser journeys with simulated provider transports.
New tests cover both modes, all three entry paths, multi-stream trips, provenance/checksum
validation, absent destinations and hazardous/unknown overrides. Ordinary tests spend
no OpenAI/ORS quota. Real-phone vision accuracy, field access and live provider journeys
are not established by fixtures.
