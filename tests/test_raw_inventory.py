import csv
import json
from pathlib import Path

import pytest
from datasets import Dataset, DatasetDict

from smart_recycling.data.common import sha256_file, write_json
from smart_recycling.data.constants import DATASET_A_ID, DATASET_A_REVISION
from smart_recycling.data.raw_inventory import (
    CLOTHING_TERMS,
    ELECTRONICS_TERMS,
    download_raw_datasets,
    inspect_raw_datasets,
    matched_terms,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("T-Shirts / shirts / bed sheets / boots", {"t-shirt", "shirt", "bedsheet", "boots"}),
        ("DRESSES and jackets", {"dress", "jacket"}),
        ("coating / dressing / linenote / fabrications", set()),
        ("paper towels", {"towel"}),  # Intentionally a candidate, not a curated textile label.
    ],
)
def test_clothing_keyword_boundaries(text: str, expected: set[str]) -> None:
    assert set(matched_terms(text, CLOTHING_TERMS)) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("smartphones / chargers / cables / mice", {"smartphone", "charger", "cable", "mouse"}),
        ("PHONE CHARGER", {"phone", "charger"}),
        ("telephone / microphone / phonetic / cablecar", set()),
        ("mouse traps / cable ties", {"mouse", "cable"}),
    ],
)
def test_electronic_candidates_are_not_substring_or_label_inferences(
    text: str,
    expected: set[str],
) -> None:
    assert set(matched_terms(text, ELECTRONICS_TERMS)) == expected


@pytest.fixture
def snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    hf = DatasetDict(
        {
            "train": Dataset.from_dict(
                {
                    "Phrase": ["discard this phone", "discard paper"],
                    "Class": ["PHONE", "PAPER"],
                    "Class_index": [3.0, 5.0],
                }
            ),
            "test": Dataset.from_dict({"Phrase": ["this thing"], "Class": ["LAPTOP CHARGER"]}),
            "validation": Dataset.from_dict({"Phrase": ["Cables"], "Class": ["ELECTRONIC"]}),
        }
    )

    def load(dataset_id, *, revision, token):
        assert (dataset_id, revision, token) == (DATASET_A_ID, DATASET_A_REVISION, False)
        return hf

    monkeypatch.setattr("datasets.load_dataset", load)
    extra = tmp_path / "source-extra.csv"
    extra.write_bytes(b',Phrase,Class,Class_index\n0,"more phones",PHONE,3.0\n')

    def download_extra(dataset_id, filename, *, repo_type, revision, token):
        assert (dataset_id, filename, repo_type, revision, token) == (
            DATASET_A_ID,
            "unseen_phrases.csv",
            "dataset",
            DATASET_A_REVISION,
            False,
        )
        return str(extra)

    monkeypatch.setattr("huggingface_hub.hf_hub_download", download_extra)

    def download_toronto(output_dir):
        output_dir.mkdir(parents=True)
        # Preserve CRLF/formatting, arrays, alias names and blank fields in the raw file.
        payload = (
            b'[\r\n{"id":"C1","item":"shirts/clothes","category":"Reuse",'
            b'"instructions":["Donate, if wearable."],"popular":false,"find_out":""},\r\n'
            b'{"id":"E1","item":"phones/chargers","category":"Electronics",'
            b'"instructions":["Use a collection point."],"popular":true,"find_out":""},\r\n'
            b'{"id":"P1","item":"paper","category":"Blue Bin",'
            b'"instructions":["Not clothing or phones."],"popular":false,"find_out":""}\r\n]'
        )
        path = output_dir / "waste_wizard.json"
        path.write_bytes(payload)
        return {"sha256": sha256_file(path), "rows": 3, "source_url": "https://example.test/raw"}

    monkeypatch.setattr("smart_recycling.data.dataset_b.download_dataset_b", download_toronto)
    root = tmp_path / "raw"
    download_raw_datasets(root)
    return root


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_download_inventory_keeps_every_split_and_original_labels(snapshot: Path) -> None:
    report = json.loads((snapshot / "inventory.json").read_text())
    hf = report["hugging_face"]
    assert set(hf["files"]) == {"train", "test", "validation", "supplementary_unseen_phrases"}
    assert hf["files"]["train"]["rows"] == 2
    assert hf["files"]["test"]["electronics_candidates"] == 1  # Label field searched too.
    assert hf["files"]["supplementary_unseen_phrases"]["kind"] == "supplementary_source_file"
    assert hf["labels"] == ["ELECTRONIC", "LAPTOP CHARGER", "PAPER", "PHONE"]
    counts = read_csv(snapshot / "waste_classification_v2" / "label_counts.csv")
    assert sum(int(row["count"]) for row in counts) == 5
    assert not (snapshot.parent / "processed").exists()
    assert (snapshot / "waste_classification_v2" / "unseen_phrases.csv").read_bytes() == (
        snapshot.parent / "source-extra.csv"
    ).read_bytes()


def test_candidate_exports_keep_source_values_and_count_each_row_once(snapshot: Path) -> None:
    clothing = read_csv(snapshot / "toronto_waste_wizard" / "clothing_candidates.csv")
    assert len(clothing) == 1
    assert clothing[0]["item"] == "shirts/clothes"
    assert clothing[0]["category"] == "Reuse"
    assert json.loads(clothing[0]["instructions"]) == ["Donate, if wearable."]
    assert json.loads(clothing[0]["popular"]) is False
    assert clothing[0]["_source_row"] == "0"
    electronics = read_csv(snapshot / "electronics_candidates.csv")
    assert len(electronics) == 5
    toronto = [row for row in electronics if row["_dataset"] == "toronto_waste_wizard"]
    assert len(toronto) == 1  # Not the paper row's generic instructions.
    assert set(json.loads(toronto[0]["_matched_terms"])) == {"phone", "charger"}
    assert "target_label" not in electronics[0]


def test_inspection_is_repeatable_and_never_rewrites_sources(snapshot: Path) -> None:
    paths = [
        *snapshot.glob("waste_classification_v2/*.csv"),
        snapshot / "toronto_waste_wizard" / "waste_wizard.json",
    ]
    before = {path: path.read_bytes() for path in paths}
    report = inspect_raw_datasets(snapshot)
    assert report == inspect_raw_datasets(snapshot)
    assert all(path.read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize(
    "filename",
    [
        "waste_classification_v2/train.csv",
        "toronto_waste_wizard/waste_wizard.json",
    ],
)
def test_changed_raw_files_are_rejected(snapshot: Path, filename: str) -> None:
    path = snapshot / filename
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum"):
        inspect_raw_datasets(snapshot)


def test_download_refuses_existing_snapshot(snapshot: Path) -> None:
    before = (snapshot / "inventory.json").read_bytes()
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        download_raw_datasets(snapshot)
    assert (snapshot / "inventory.json").read_bytes() == before


def test_no_keyword_matches_still_exports_headers(snapshot: Path) -> None:
    raw = snapshot / "toronto_waste_wizard" / "waste_wizard.json"
    write_json(raw, [{"item": "jar", "category": "Blue Bin"}])
    metadata_path = raw.with_name("metadata.json")
    metadata = json.loads(metadata_path.read_text())
    metadata["sha256"] = sha256_file(raw)
    write_json(metadata_path, metadata)
    report = inspect_raw_datasets(snapshot)
    assert report["toronto"]["clothing_candidates"] == 0
    path = raw.with_name("clothing_candidates.csv")
    assert read_csv(path) == []
    with path.open(newline="") as handle:
        assert {"item", "category", "_matched_terms"}.issubset(csv.DictReader(handle).fieldnames)
