"""Combine approved normalized sources into one metadata-rich dataset."""

from pathlib import Path
from typing import Any

import pandas as pd

from smart_recycling.data.common import normalize_key, stable_id, write_json
from smart_recycling.data.constants import PROCESSED_DIR, TARGET_LABELS

COMBINED_COLUMNS = (
    "id",
    "text",
    "target_label",
    "source",
    "original_label",
    "item_name",
    "generation_method",
    "item_group",
    "mapping_status",
)


def combine_datasets(
    dataset_a_path: Path | None = None,
    dataset_b_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    dataset_a_path = dataset_a_path or PROCESSED_DIR / "dataset_a.csv"
    dataset_b_path = dataset_b_path or PROCESSED_DIR / "dataset_b_augmented.csv"
    output_path = output_path or PROCESSED_DIR / "combined_dataset.csv"

    frames: list[pd.DataFrame] = []
    excluded_by_source: dict[str, int] = {}
    for path, source_name in (
        (dataset_a_path, "dataset_a"),
        (dataset_b_path, "dataset_b_augmented"),
    ):
        if not path.exists():
            raise FileNotFoundError(f"processed source is missing: {path}")
        frame = pd.read_csv(path, dtype=str).fillna("")
        approved = frame[frame["mapping_status"] == "approved"].copy()
        excluded_by_source[source_name] = int(len(frame) - len(approved))
        frames.append(approved)

    combined = pd.concat(frames, ignore_index=True)
    invalid = sorted(set(combined["target_label"]) - set(TARGET_LABELS))
    if invalid:
        raise ValueError(f"invalid target labels while combining: {invalid}")

    combined["_text_key"] = combined["text"].map(normalize_key)
    before = len(combined)
    combined = combined.drop_duplicates(subset=["_text_key", "target_label"], keep="first")
    duplicates_removed = before - len(combined)
    combined["id"] = [
        stable_id(row.source, row.item_group, row.text, row.target_label)
        for row in combined.itertuples()
    ]
    combined = combined.drop(columns="_text_key")
    combined = combined[list(COMBINED_COLUMNS)].sort_values("id").reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path, index=False)
    class_counts = combined["target_label"].value_counts().reindex(TARGET_LABELS, fill_value=0)
    report = {
        "total_examples": int(len(combined)),
        "duplicates_removed": int(duplicates_removed),
        "excluded_pending_review": excluded_by_source,
        "class_counts": class_counts.to_dict(),
        "class_percentages": (class_counts / len(combined) * 100).round(2).to_dict(),
        "source_counts": combined["source"].value_counts().to_dict(),
    }
    write_json(PROCESSED_DIR / "combined_dataset_report.json", report)
    print(f"Combined dataset: {len(combined):,} approved examples")
    print(class_counts.to_string())
    return report
