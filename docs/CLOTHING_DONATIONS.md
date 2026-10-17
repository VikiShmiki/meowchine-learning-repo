# Clothes donation — reviewed 22 September 2026

Clothes is the sixth citizen card: clean, washed, wearable garments for **donation/reuse**.
This is not evidence of recycling damaged textiles. Selection, text and photo review all
require that condition before routing. No new LLM or MiniLM model was trained.
The existing canonical specialist category contains the exact item kind `wearable_clothes`;
citizen discovery uses `clothes`, separately from electronics. The vision prompt/schema
and server checks share that item vocabulary and keep the configured OpenAI model.

## Inventory

The [Red Cross's 20 April 2026 announcement](https://ckgs.org.mk/novosti/crven-krst-na-grad-skopje-doniraj-obleka-podari-nadezh/)
lists **8 physical containers at 6 venues**, plus **2 staffed donation venues**: eight
distinct documented destinations, not ten. Five have reviewed map matches:

| Mapped venue | Published/matched address | Containers in 2026 list | Coordinate reference |
| --- | --- | ---: | --- |
| Red Cross Karpos | Orce Nikolov 155v | 2 | [OSM entrance](https://www.openstreetmap.org/node/8615409557), parent way 547074225 |
| Dare Dzambaz | 11 Oktomvri 42a | 2 | [OSM venue](https://www.openstreetmap.org/node/9315908483) |
| Kopche | Kocho Racin 13 | Staffed donation | [OSM headquarters venue](https://www.openstreetmap.org/node/9315874307) |
| Kisela Voda municipality | Petar Deljan 17 | 1 | [OSM municipal grounds](https://www.openstreetmap.org/way/284928908) |
| Skopje City Hall | Ilinden 82 | 1 | [OSM City Hall grounds](https://www.openstreetmap.org/way/1367341315) |

[Kopche's operator page](https://ckgs.org.mk/centar/kopche/) supplies its exact address.
Its headquarters/shop/container are not counted as multiple routable destinations.
The 2026 announcement supplies donation hours where an older Kopche page differs.
OSM supplies the two municipal addresses; matching those venues to the publication
is agent-reviewed, not human/field verified. Grounds points are Nominatim representative
points of the cited OSM ways, not exact entrances. Every trip includes an arrival note.

Three documented venues are **held out of discovery and routing**:

- Gazi Baba: the donation article gives Anton Popov 26; the
  [branch contact page](https://www.ckgazibaba.org.mk/kontakt/) gives Blagoja Stefkovski bb.
  Resolve which address actually has the clothes container before adding a map pin.
- Chair: Pavle Ilik 1 is documented, but a street-only geocoder result is not an exact venue.
- Momin Potok: warehouse donation is documented, but no reliable warehouse entrance was
  located. The neighbourhood or nearby homeless shelter cannot substitute for the warehouse.

The [older national Red Cross list](https://api.ckrm.org.mk/doniraj-obleka/) supplies
three additional leads: Novo Lisice/Lisa Centre, Avtokomanda Square, Skopje City Mall.
They are absent from the 2026 list; do not count them as currently established locations.
H&M has Skopje shops, but local collection participation was not verified. Generic foreign
H&M policies and one-day Teksomak campaigns are not evidence for permanent Skopje drop-offs.

## What the app contains

| Citizen material | Distinct mapped locations |
| --- | ---: |
| Glass | 405 |
| Plastic bottles / cans | 120 |
| Paper / cartons | 7 |
| General waste | 1,051 |
| Electronics | 2 (East Gate small devices only) |
| Clothes donation | 5 |
| **Total** | **1,590** |

There are **1,603 asset/collection-point records**. Each new clothing venue has one
app record; two physical containers at one venue do not create two routes or invented
individual-bin coordinates. Five mapped clothing venues account for six published
containers plus Kopche's staffed drop-off. Counts are recorded destinations, not live
availability promises or field-surveyed bins.

The City coverage/upgrades snapshot stays **1,583 sites / 1,596 assets**, policy v1.
Clothes and electronics are additive citizen-only catalogs; no frozen geography or
coverage outputs were changed. Current data freshness remains per-record.

## Reproduce and review

`uv run python scripts/scrape_clothing_locations.py` extracts the bounded public list,
records a UTC retrieval time and source checksum, and checks reviewed venue/count matches.
Only factual rows are saved in `data/infrastructure/clothes-2026-09-22/research.json`;
no full copyrighted page or personal data is retained. A changed source structure/count
fails instead of silently publishing destinations. The manually matched `sites.json`
has a normalized-text checksum in `manifest.json`; OSM coordinates require ODbL attribution.
Source retrieval is not a live operating-status check.

After policy/rule edits run `uv run --group data python scripts/evaluate_guidance.py`.
Run `SRA_BROWSER_TESTS=1 uv run --all-groups pytest -ra` and the two Node suites.
Fixtures test text/photo/picker journeys in both modes, map separation, narrow acceptance,
damaged/unknown/hazardous holds, no fallback, catalog tampering, and scraper changes.
External providers and tiles are simulated; real-photo accuracy and field access remain
unmeasured. CI was paused for that original branch check; the later private-repository
integration passed browser and Docker gates. See [CI_STATUS.md](CI_STATUS.md).
