"""Validate dataset contracts, mappings, duplicates, and split isolation."""

from pathlib import Path
from typing import Any

import pandas as pd

from smart_recycling.data.common import normalize_key, read_json, write_json
from smart_recycling.data.constants import (
    EVALUATION_DIR,
    MAPPINGS_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    TARGET_LABELS,
)


def validate_dataset(
    dataset_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    dataset_path = dataset_path or PROCESSED_DIR / "combined_with_splits.csv"
    report_path = report_path or PROCESSED_DIR / "dataset_report.json"
    dataset = pd.read_csv(dataset_path, dtype=str).fillna("")
    hard_errors: list[str] = []
    warnings: list[str] = []

    missing_text = int((dataset["text"].map(str.strip) == "").sum())
    missing_labels = int((dataset["target_label"].map(str.strip) == "").sum())
    invalid_labels = sorted(set(dataset["target_label"]) - set(TARGET_LABELS))
    if missing_text:
        hard_errors.append(f"{missing_text} rows have missing text")
    if missing_labels:
        hard_errors.append(f"{missing_labels} rows have missing target labels")
    if invalid_labels:
        hard_errors.append(f"invalid target labels: {invalid_labels}")

    dataset["_text_key"] = dataset["text"].map(normalize_key)
    labels_per_text = dataset.groupby("_text_key")["target_label"].nunique()
    conflicting_texts = labels_per_text[labels_per_text > 1]
    duplicate_same_label = int(dataset.duplicated(["_text_key", "target_label"], keep=False).sum())
    if not conflicting_texts.empty:
        hard_errors.append(f"{len(conflicting_texts)} normalized texts have conflicting labels")
    if duplicate_same_label:
        warnings.append(f"{duplicate_same_label} rows duplicate text with the same label")

    groups_across_splits = dataset.groupby("item_group")["split"].nunique()
    leaking_groups = groups_across_splits[groups_across_splits > 1]
    if not leaking_groups.empty:
        hard_errors.append(f"{len(leaking_groups)} item groups leak across splits")

    original_labels_path = RAW_DIR / "dataset_a" / "original_labels.json"
    original_labels = (
        set(read_json(original_labels_path)) if original_labels_path.exists() else set()
    )
    mapping = read_json(MAPPINGS_DIR / "dataset_a_label_mapping.json")
    unmapped_a = sorted(original_labels - set(mapping))
    if unmapped_a:
        hard_errors.append(f"unmapped Dataset A labels: {unmapped_a}")

    dataset_a_review = pd.read_csv(MAPPINGS_DIR / "needs_manual_review.csv").fillna("")
    ambiguous_a = dataset_a_review[dataset_a_review["mapping_status"] == "needs_review"][
        "original_label"
    ].tolist()

    dataset_b_mapping_path = MAPPINGS_DIR / "dataset_b_item_mapping.csv"
    if dataset_b_mapping_path.exists():
        dataset_b_mapping = pd.read_csv(dataset_b_mapping_path, dtype=str).fillna("")
        needs_review_b = int((dataset_b_mapping["mapping_status"] == "needs_review").sum())
        invalid_b = sorted(
            set(dataset_b_mapping.loc[dataset_b_mapping["target_label"] != "", "target_label"])
            - set(TARGET_LABELS)
        )
        if invalid_b:
            hard_errors.append(f"invalid Dataset B mappings: {invalid_b}")
    else:
        needs_review_b = 0
        warnings.append("Dataset B mapping file is missing")

    word_lengths = dataset["text"].str.split().str.len()
    unusually_short = int((word_lengths < 2).sum())
    unusually_long = int((word_lengths > 40).sum())
    if unusually_short:
        warnings.append(f"{unusually_short} queries contain fewer than two words")
    if unusually_long:
        warnings.append(f"{unusually_long} queries contain more than 40 words")

    manual_path = EVALUATION_DIR / "manual_test.csv"
    manual_train_overlap = 0
    if manual_path.exists():
        manual = pd.read_csv(manual_path, dtype=str).fillna("")
        manual_keys = set(manual["text"].map(normalize_key))
        train_keys = set(dataset.loc[dataset["split"] == "train", "_text_key"])
        manual_train_overlap = len(manual_keys & train_keys)
        if manual_train_overlap:
            warnings.append(
                f"{manual_train_overlap} manual evaluation texts overlap normalized training text"
            )

    class_counts = dataset["target_label"].value_counts().reindex(TARGET_LABELS, fill_value=0)
    source_counts = dataset["source"].value_counts()
    report = {
        "valid": not hard_errors,
        "hard_errors": hard_errors,
        "warnings": warnings,
        "rows": int(len(dataset)),
        "class_counts": class_counts.to_dict(),
        "class_percentages": (class_counts / len(dataset) * 100).round(2).to_dict(),
        "source_counts": source_counts.to_dict(),
        "split_counts": dataset["split"].value_counts().to_dict(),
        "duplicate_same_label_rows": duplicate_same_label,
        "conflicting_texts": int(len(conflicting_texts)),
        "leaking_item_groups": int(len(leaking_groups)),
        "unmapped_dataset_a_labels": unmapped_a,
        "ambiguous_dataset_a_labels": ambiguous_a,
        "dataset_b_items_needing_review": needs_review_b,
        "unusually_short_queries": unusually_short,
        "unusually_long_queries": unusually_long,
        "manual_train_overlap": manual_train_overlap,
    }
    write_json(report_path, report)

    print(f"Dataset validation: {'PASS' if report['valid'] else 'FAIL'}")
    print(f"Rows: {len(dataset):,}")
    print(f"Class balance: {class_counts.to_dict()}")
    print(f"Source balance: {source_counts.to_dict()}")
    print(f"Dataset A mappings awaiting review: {len(ambiguous_a)}")
    print(f"Dataset B items awaiting review: {needs_review_b}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in hard_errors:
        print(f"ERROR: {error}")
    if hard_errors:
        raise ValueError("dataset validation failed; see dataset_report.json")
    return report
