"""Evaluation identity and provenance are checked before model scoring."""

import csv
import json
import shutil
from pathlib import Path

import pytest

from smart_recycling.data.common import sha256_file
from smart_recycling.data.ml_provenance import load_bound_rows, reviewed_manual_rows

ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def evaluation_root(tmp_path):
    shutil.copytree(ROOT / "data/evaluation", tmp_path / "data/evaluation")
    return tmp_path


def test_manual_identity_survives_independent_csv_reordering(evaluation_root):
    expected = {
        lang: {r["group"]: (r["text"], r["label"]) for r in reviewed_manual_rows(ROOT, lang)[0]}
        for lang in ("en", "mk")
    }
    for name in ("manual_test.csv", "manual_test_review.csv", "manual_test_mk.csv"):
        path = evaluation_root / "data/evaluation" / name
        with path.open() as stream:
            rows = list(csv.DictReader(stream))
        write_csv(
            path, list(reversed(rows)) if name.endswith("review.csv") else rows[7:] + rows[:7]
        )
    for lang in ("en", "mk"):
        actual = {
            r["group"]: (r["text"], r["label"])
            for r in reviewed_manual_rows(evaluation_root, lang)[0]
        }
        assert actual == expected[lang]


@pytest.mark.parametrize("damage", ["duplicate", "missing", "source_hash", "label", "empty"])
def test_macedonian_cases_must_match_reviewed_source(evaluation_root, damage):
    path = evaluation_root / "data/evaluation/manual_test_mk.csv"
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    if damage == "duplicate":
        rows.append(rows[0])
    elif damage == "missing":
        rows.pop()
    elif damage == "source_hash":
        rows[0]["english_text_sha256"] = "wrong"
    elif damage == "label":
        rows[0]["target_label"] = "electronics"
    else:
        rows[0]["text"] = ""
    write_csv(path, rows)
    with pytest.raises(ValueError):
        reviewed_manual_rows(evaluation_root, "mk")


@pytest.mark.parametrize("damage", [None, "rows", "manifest", "head", "different_model"])
def test_training_rows_are_bound_to_model_and_manifest(tmp_path, damage):
    rows = tmp_path / "rows.json"
    rows.write_text('[{"text":"glass bottle","role":"train"}]')
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(dict(outputs={"rows.json": sha256_file(rows)})))
    head = tmp_path / "head.json"
    head.write_text(json.dumps(dict(dataset_sha256=sha256_file(manifest))))
    pinned = sha256_file(head)
    if damage == "different_model":
        head.write_text(json.dumps(dict(dataset_sha256="different-training-run")))
        pinned = sha256_file(head)
    elif damage:
        path = {"rows": rows, "manifest": manifest, "head": head}[damage]
        path.write_text(path.read_text() + " ")
    if damage:
        with pytest.raises(ValueError):
            load_bound_rows(rows, manifest, head, pinned)
    else:
        relocated = tmp_path / "relocated"
        relocated.mkdir()
        for path in (rows, manifest, head):
            shutil.copy(path, relocated / path.name)
        result, hashes = load_bound_rows(
            relocated / rows.name, relocated / manifest.name, relocated / head.name, pinned
        )
        assert result == json.loads(rows.read_text())
        assert hashes["training_rows_sha256"] == sha256_file(rows)
