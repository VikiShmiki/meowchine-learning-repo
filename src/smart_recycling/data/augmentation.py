"""Deterministically turn approved Toronto item names into realistic queries."""

from pathlib import Path
from typing import Any

import pandas as pd

from smart_recycling.data.common import normalize_key, normalize_whitespace, write_json
from smart_recycling.data.constants import MAPPINGS_DIR, PROCESSED_DIR

PACKAGING_TERMS = {
    "bottle",
    "jar",
    "can",
    "container",
    "carton",
    "box",
    "tube",
    "cup",
    "tray",
    "tin",
    "packaging",
}


def _query_variants(item_name: str) -> list[tuple[str, str]]:
    item_name = normalize_whitespace(item_name)
    normalized = normalize_key(item_name)
    variants = [
        (item_name, "raw_item"),
        (f"where do I throw {item_name}?", "template_where_throw"),
        (f"where should I throw away {item_name}?", "template_where_throw_away"),
        (f"can I recycle {item_name}?", "template_recycle"),
        (f"what bin does {item_name} go in?", "template_what_bin"),
        (f"how do I dispose of {item_name}?", "template_dispose"),
    ]
    if any(term in normalized.split() for term in PACKAGING_TERMS):
        variants.append((f"empty {item_name}", "template_empty"))
    elif not normalized.startswith("old "):
        variants.append((f"old {item_name}", "template_old"))
    return variants


def generate_augmented_queries(
    mapping_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    mapping_path = mapping_path or MAPPINGS_DIR / "dataset_b_item_mapping.csv"
    output_path = output_path or PROCESSED_DIR / "dataset_b_augmented.csv"
    if not mapping_path.exists():
        raise FileNotFoundError("Dataset B mapping is missing; run process_dataset_b.py")

    mapping = pd.read_csv(mapping_path, dtype=str).fillna("")
    approved = mapping[(mapping["mapping_status"] == "approved") & (mapping["target_label"] != "")]

    records: list[dict[str, str]] = []
    for row in approved.to_dict(orient="records"):
        for text, method in _query_variants(row["item_name"]):
            records.append(
                {
                    "text": text,
                    "target_label": row["target_label"],
                    "source": "dataset_b_augmented",
                    "original_label": row["original_toronto_category"],
                    "item_name": row["item_name"],
                    "generation_method": method,
                    "item_group": f"dataset_b::{row['normalized_item_name']}",
                    "mapping_status": row["mapping_status"],
                }
            )

    augmented = pd.DataFrame(
        records,
        columns=[
            "text",
            "target_label",
            "source",
            "original_label",
            "item_name",
            "generation_method",
            "item_group",
            "mapping_status",
        ],
    )
    if not augmented.empty:
        augmented = augmented.drop_duplicates(subset=["text", "target_label"], keep="first")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    augmented.to_csv(output_path, index=False)
    report = {
        "approved_items": int(len(approved)),
        "queries": int(len(augmented)),
        "class_counts": augmented["target_label"].value_counts().to_dict(),
        "generation_method_counts": augmented["generation_method"].value_counts().to_dict(),
    }
    write_json(PROCESSED_DIR / "dataset_b_augmentation_report.json", report)
    print(f"Dataset B augmented: {len(augmented):,} queries from {len(approved):,} items")
    return report
