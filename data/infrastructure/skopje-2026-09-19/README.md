# Skopje infrastructure snapshot — 2026-09-19

Shared in the private team repository at the project owner's explicit request.
These are unchanged exports from the local `container_dataset_analysis/hackathon_demo`
workspace, built by `build_hackathon_demo.py` from its v2 research package.

## Files and scope

| File stem (GeoJSON and CSV) | Assets | Scope |
| --- | ---: | --- |
| `pakomak_recycling` | 538 | City: 500 containers and 38 reverse-vending machines |
| `city_mixed_waste` | 1,058 | City: general-waste assets, candidate upgrade locations |
| `pakomak_metro_extension` | 1 | Outside the City scope; exclude from default analysis |

The two City layers contain 1,596 assets at 1,583 distinct coordinates rounded to
six decimals. Coordinate grouping is not proof of physical identity. Recycling
capabilities include glass (407 assets), plastic bottles and metal cans (124 assets
accept each), and paper (7 assets). Material counts are non-exclusive.

GeoJSON points use WGS84 longitude/latitude. Preserve `asset_id`, `site_id`, source
references, material capabilities, collection mode, timestamps, and QA flags during
ingestion. `materials` contains source capability codes, not the app's five labels.
Do not infer that every plastic/metal item is accepted at a bottle/can machine or
that paper acceptance proves Tetra Pak acceptance. Asset compatibility requires
reviewed disposal rules as well as a broad predicted category.

## Provenance and limitations

- City GIS: https://gisportal.skopje.gov.mk/arcgis/rest/services/INFRA/Infra_FS/FeatureServer/30
- Pakomak containers: https://maps.pakomak.mk/
- Pakomak vending list: https://pakomak.mk/Pages/Index/povratni_vending_masini
- `summary.json` is preserved verbatim; its SHA-256 entries cover the six data files.
  It also references the original preview `index.html`, which is intentionally not
  included in this data snapshot.
- Source reuse terms remain unconfirmed. Team sharing does not change
  `reuse_status` or `publication_eligible`, or establish public redistribution rights.
- Locations have not been field-verified; unknown operational status is not active
  status. Fullness readings are dated observations, not live availability.
- These exports feed the real `/api/v1/sites` snapshot endpoint. The legacy citizen
  nearest-point lookup still uses synthetic seeds until item-specific integration.
- Population weights, neighborhood boundaries, and a pedestrian routing graph are
  not included. Collection-point counts cannot establish population coverage.

Validate the snapshot without third-party dependencies:

```bash
python scripts/validate_infrastructure_snapshot.py
```
