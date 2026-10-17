from pathlib import Path

import pytest

from smart_recycling.data.common import normalize_key, sha256_file, write_json
from smart_recycling.data.relabel import (
    alias_overrides,
    correct_row,
    english_mirror,
    prepare_pairs,
    read_json,
    reviewed_items,
    run_relabel,
)
from smart_recycling.data.translation import read_csv, write_csv

ROOT = Path(__file__).resolve().parents[1]
REVIEW = read_json(ROOT / "data/mappings/object_classes_v2.json")


def test_reviewed_ids_cover_devices_clothes_and_exclude_false_friends():
    ids = {source_id for values in REVIEW["toronto_groups"].values() for source_id in values}
    catalogue = [{"id": value} for value in ids | set(REVIEW["held_toronto_ids"])]
    items = reviewed_items(REVIEW, catalogue)
    assert items["A1222"][0] == "clothes"  # Shirts, but its translation is held.
    assert items["A1080"][0] == "clothes"  # Boots.
    assert items["A0685"][0] == "electronics"  # Clothes iron, not clothing.
    assert items["A1819"][0] == "electronics"  # Clothes dryer.
    assert items["A0618"][0] == "electronics"  # Battery charger, not a loose battery.
    assert items["A0030"][0] == "electronics"  # Whole device with embedded battery.
    assert not {"A0226", "A0678", "A1270", "A1001", "A1302", "A1158", "A1779"} & ids
    with pytest.raises(ValueError, match="Duplicate Toronto"):
        reviewed_items(REVIEW, catalogue + catalogue[:1])
    with pytest.raises(ValueError, match="Missing or duplicate reviewed"):
        reviewed_items(REVIEW, [])


@pytest.mark.parametrize("source_class", ["PHONE CHARGER", "LAPTOP CHARGER", "SMARTPHONE"])
def test_raw_labels_and_indices_change_but_source_classes_survive(source_class):
    source = {
        "Phrase": "пример",
        "Phrase_en": "an item",
        "Class": source_class,
        "Class_index": "26.0",
        "proposed_target_label": "special_unsupported",
        "current_mapping_status": "needs_review",
    }
    corrected = correct_row(source, REVIEW, {}, {})
    assert (
        corrected["Class"]
        == corrected["label"]
        == corrected["proposed_target_label"]
        == "electronics"
    )
    assert corrected["source_class"] == source_class
    assert corrected["source_class_index"] == "26.0"
    assert corrected["Class_index"] == str(REVIEW["labels"].index("electronics"))
    assert corrected["policy_mapping_status"] == "needs_review"
    assert corrected["previous_target_label"] == "special_unsupported"
    assert source["Class"] == source_class


def test_mk_uses_source_identity_not_translation_keywords():
    row = {
        "text_en": "shirts",
        "text": "Косички",
        "target_label": "general",
        "source": "dataset_b_augmented",
        "item_name": "shirts",
    }
    corrected = correct_row(row, REVIEW, {"shirts": "clothes"}, {})
    assert corrected["target_label"] == "clothes"
    assert corrected["text"] == "Косички"
    english = english_mirror(corrected)
    assert english["text"] == "shirts"
    assert english["label"] == corrected["label"]
    assert english["translation_review_status"] == "original"


def test_aliases_resolve_source_ids_and_do_not_autoapprove_ambiguous_aliases():
    mapping = [
        {"normalized_item_name": "laptop", "source_id": "one"},
        {"normalized_item_name": "accessory", "source_id": "one | two"},
        {"normalized_item_name": "clothes", "source_id": "three | four"},
    ]
    assert alias_overrides(
        mapping, {"one": ("electronics", "g"), "three": ("clothes", "h"), "four": ("clothes", "h")}
    ) == {"laptop": "electronics", "clothes": "clothes"}


def test_batteries_hazardous_items_and_disposal_holds_are_preserved():
    battery = {"original_label": "CYLINDRICAL BATTERY", "target_label": "special_unsupported"}
    assert correct_row(battery, REVIEW, {}, {})["target_label"] == "special_unsupported"
    source = {
        "text_en": "damaged power bank",
        "target_label": "special_unsupported",
        "evaluation_label": "",
        "source_review_status": "held",
    }
    row = correct_row(source, REVIEW, {}, REVIEW["evaluation_overrides"])
    assert row["label"] == row["evaluation_label"] == "electronics"
    assert row["policy_evaluation_label"] == ""
    assert row["source_review_status"] == "held"
    source = {"text_en": "torn trousers", "target_label": "", "review_method": "policy_hold"}
    row = correct_row(source, REVIEW, {}, REVIEW["evaluation_overrides"])
    assert row["target_label"] == "clothes"
    assert row["previous_target_label"] == ""
    assert row["review_method"] == "policy_hold"
    assert (
        correct_row(
            {"text_en": "shirt and a metal can", "target_label": ""},
            REVIEW,
            {},
            REVIEW["evaluation_overrides"],
        )["label"]
        == ""
    )


def pair(number=0, **changes):
    return {
        "id": f"pair_{number}",
        "text_en": f"item {number}",
        "text_mk": f"предмет {number}",
        "label": "electronics",
        "item_group": f"group_{number}",
        "split": "",
        "translation_qa_flags": "",
        **changes,
    }


def test_new_groups_seeded_repeatably_while_original_splits_stay_fixed():
    rows = [pair(0, split="test")] + [pair(i) for i in range(1, 21)]
    kept, excluded = prepare_pairs(rows, set())
    assert not excluded
    assert kept == prepare_pairs(rows, set())[0]
    assert kept[0]["split"] == "test"
    assert {r["split"] for r in kept} == {"train", "validation", "test"}


def test_duplicate_translation_merges_new_group_into_inherited_group():
    rows = [pair(0, split="test"), pair(1, text_mk="предмет 0"), pair(2, item_group="group_1")]
    kept, excluded = prepare_pairs(rows, set())
    assert [r["id"] for r in kept] == ["pair_0", "pair_2"]
    assert {r["split"] for r in kept} == {"test"}
    assert len({r["item_group"] for r in kept}) == 1
    assert excluded[0]["exclusion_reason"] == "duplicate_translation_or_source"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"split": "test"}, "conflicting_inherited_splits"),
        ({"label": "clothes"}, "conflicting_labels"),
    ],
)
def test_conflicting_text_or_inherited_groups_are_quarantined(changes, reason):
    kept, excluded = prepare_pairs(
        [pair(0, split="train"), pair(1, text_en="item 0", **changes)], set()
    )
    assert kept == []
    assert {r["exclusion_reason"] for r in excluded} == {reason}


def test_qa_and_evaluation_collisions_do_not_enter_training():
    kept, excluded = prepare_pairs(
        [pair(0, translation_qa_flags="semantic_translation_mismatch"), pair(1)],
        {normalize_key("предмет 1")},
    )
    assert kept == []
    assert [r["exclusion_reason"] for r in excluded] == [
        "translation_qa",
        "reserved_evaluation_text",
    ]


def test_real_csv_export_preserves_inputs_labels_pairing_and_refuses_overwrite(tmp_path):
    root, source, output = tmp_path / "root", tmp_path / "v1", tmp_path / "v2"
    source.mkdir()
    catalogue = [
        {
            "id": "A1222",
            "item": "кошули",
            "item_en": "shirts",
            "category": "Garbage",
            "translation_qa_flags": "",
            "translation_review_status": "needs_native_review",
        }
    ]
    raw_path = root / "data/raw/toronto_waste_wizard/waste_wizard.json"
    write_json(raw_path, catalogue)
    review = {
        **REVIEW,
        "toronto_source_sha256": sha256_file(raw_path),
        "toronto_groups": {"clothes::shirts": ["A1222"]},
        "held_toronto_ids": {},
        "translation_holds": {},
    }
    write_json(root / "data/mappings/object_classes_v2.json", review)
    write_csv(root / "data/mappings/dataset_b_item_mapping.csv", [], ["source_id"])
    write_json(
        root / "tests/fixtures/macedonian.json",
        [
            {"en": "torn clothes", "mk": "искината облека", "kind": None, "status": "held"},
            {
                "en": "clothes and plastic bottle",
                "mk": "облека и пластично шише",
                "kind": None,
                "status": "held",
            },
        ],
    )
    original = {
        "id": "source_id",
        "source": "dataset_a",
        "original_label": "LAPTOP CHARGER",
        "text": "полнач за лаптоп",
        "text_en": "laptop charger",
        "target_label": "special_unsupported",
        "item_group": "dataset_a::laptop charger",
        "split": "train",
        "translation_qa_flags": "",
    }
    manifest = {"status": "complete", "source_hashes": {}, "outputs": {}}
    for relative in ("processed/combined_with_splits_mk.csv", "experimental/paired.csv"):
        path = source / relative
        write_csv(path, [original], list(original))
        manifest["outputs"][relative] = {"sha256": sha256_file(path)}
    relative = "raw/toronto_waste_wizard/waste_wizard_mk.json"
    write_json(source / relative, catalogue)
    manifest["outputs"][relative] = {"sha256": sha256_file(source / relative)}
    write_json(source / "manifest.json", manifest)
    before = {
        p: sha256_file(p) for folder in (root, source) for p in folder.rglob("*") if p.is_file()
    }
    report = run_relabel(root=root, source=source, output=output)
    assert report["status"] == "complete"
    for path, fingerprint in before.items():
        assert sha256_file(path) == fingerprint
    en = read_csv(output / "experimental/train_en.csv")
    mk = read_csv(output / "experimental/train_mk.csv")
    assert [r["label"] for r in en] == [r["label"] for r in mk] == ["electronics", "clothes"]
    assert [r["pair_id"] for r in en] == [r["pair_id"] for r in mk]
    assert en[0]["text"] == "laptop charger"
    assert mk[0]["text"] == "полнач за лаптоп"
    probes = read_csv(output / "evaluation/object_probe_mk.csv")
    assert len(probes) == 1
    assert probes[0]["text"] == "искината облека"
    assert probes[0]["label"] == "clothes"
    assert probes[0]["policy_status"] == "held"
    assert (
        read_csv(output / "processed/combined_with_splits_en.csv")[0]["target_label"]
        == "electronics"
    )
    for relative, metadata in report["outputs"].items():
        assert sha256_file(output / relative) == metadata["sha256"]
    with pytest.raises(FileExistsError):
        run_relabel(root=root, source=source, output=output)
    write_csv(source / "experimental/paired.csv", [], ["id"])
    with pytest.raises(ValueError, match="Source checksum mismatch"):
        run_relabel(root=root, source=source, output=tmp_path / "v3")
