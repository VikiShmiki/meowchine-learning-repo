import json
from pathlib import Path

import pandas as pd

from smart_recycling.data.augmentation import _query_variants
from smart_recycling.data.common import normalize_key
from smart_recycling.data.constants import MAPPINGS_DIR, TARGET_LABELS
from smart_recycling.data.dataset_b import _is_manual_mapping, _suggest_target
from smart_recycling.data.splitting import create_grouped_splits

ROOT = Path(__file__).resolve().parents[1]


def test_dataset_a_mapping_is_complete_and_uses_only_target_labels() -> None:
    mapping = json.loads(
        (MAPPINGS_DIR / "dataset_a_label_mapping.json").read_text(encoding="utf-8")
    )

    assert len(mapping) == 50
    assert set(mapping.values()) == set(TARGET_LABELS)


def test_manual_evaluation_is_balanced_and_marked_for_review() -> None:
    manual = pd.read_csv(ROOT / "data" / "evaluation" / "manual_test.csv")

    assert len(manual) == 100
    assert manual["target_label"].value_counts().to_dict() == {label: 20 for label in TARGET_LABELS}
    assert set(manual["review_status"]) == {"needs_human_review"}


def test_toronto_mapping_rules_use_item_vocabulary() -> None:
    assert _suggest_target("empty aluminium drink can")[0] == "plastic_metal"
    assert _suggest_target("glass pasta sauce jar")[0] == "glass"
    assert _suggest_target("broken phone charger")[0] == "special_unsupported"
    assert _suggest_target("mystery household object")[0] == ""


def test_toronto_mapping_preserves_only_human_decisions() -> None:
    assert _is_manual_mapping({"mapping_status": "approved"})
    assert _is_manual_mapping({"mapping_status": "excluded"})
    assert _is_manual_mapping({"mapping_status": "needs_review", "mapping_method": "manual"})
    assert not _is_manual_mapping(
        {"mapping_status": "needs_review", "mapping_method": "unresolved"}
    )


def test_empty_template_is_limited_to_packaging_items() -> None:
    bottle_variants = dict(_query_variants("plastic bottle"))
    sponge_variants = dict(_query_variants("dirty sponge"))

    assert bottle_variants["empty plastic bottle"] == "template_empty"
    assert "empty dirty sponge" not in sponge_variants


def test_grouped_splits_keep_items_together(tmp_path: Path) -> None:
    rows = []
    for label in TARGET_LABELS:
        for group_index in range(6):
            for variant in range(group_index + 1):
                rows.append(
                    {
                        "id": f"{label}-{group_index}-{variant}",
                        "text": f"{label} item {group_index} variant {variant}",
                        "target_label": label,
                        "source": "test",
                        "original_label": label,
                        "item_name": f"item {group_index}",
                        "generation_method": "test",
                        "item_group": f"{label}::{group_index}",
                        "mapping_status": "approved",
                    }
                )
    input_path = tmp_path / "combined.csv"
    output_path = tmp_path / "split.csv"
    pd.DataFrame(rows).to_csv(input_path, index=False)

    create_grouped_splits(input_path, output_path)

    split = pd.read_csv(output_path)
    assert split.groupby("item_group")["split"].nunique().max() == 1
    assert set(split["split"]) == {"train", "validation", "test"}


def test_normalized_item_keys_collapse_cosmetic_variation() -> None:
    assert normalize_key("  Plastic   Bottle ") == normalize_key("plastic-bottle")
