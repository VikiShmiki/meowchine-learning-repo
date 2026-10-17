import json
from pathlib import Path

import pytest

from smart_recycling.domain import WasteCategory
from smart_recycling.repository import load_sites

ROOT = Path(__file__).resolve().parents[1]


def test_seed_matches_site_contract() -> None:
    path = ROOT / "data" / "seed" / "sites.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["synthetic"] is True
    sites = load_sites(path)
    assert len(sites) == 4
    assert all(WasteCategory.SPECIAL_UNSUPPORTED not in site.materials for site in sites)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sites.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "sites": [
                    {
                        "id": "same",
                        "name": "one",
                        "latitude": 0,
                        "longitude": 0,
                        "materials": ["glass"],
                    },
                    {
                        "id": "same",
                        "name": "two",
                        "latitude": 1,
                        "longitude": 1,
                        "materials": ["paper_tetrapak"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unique"):
        load_sites(path)
