"""Download and normalize the Hugging Face natural-language dataset."""

from pathlib import Path
from typing import Any

import pandas as pd
from datasets import DatasetDict, load_dataset

from smart_recycling.data.common import normalize_key, normalize_whitespace, read_json, write_json
from smart_recycling.data.constants import (
    DATASET_A_ID,
    DATASET_A_REVISION,
    MAPPINGS_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    TARGET_LABELS,
)
from smart_recycling.data.review import load_mapping_review


def download_dataset_a(output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = output_dir or RAW_DIR / "dataset_a"
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset(DATASET_A_ID, revision=DATASET_A_REVISION)
    if not isinstance(dataset, DatasetDict):
        raise TypeError("Dataset A must expose named splits")

    labels: set[str] = set()
    split_sizes: dict[str, int] = {}
    columns: dict[str, list[str]] = {}
    examples_by_label: dict[str, list[str]] = {}

    for split_name, split in dataset.items():
        frame = split.to_pandas()
        split_sizes[split_name] = len(frame)
        columns[split_name] = list(frame.columns)
        if not {"Phrase", "Class"}.issubset(frame.columns):
            raise ValueError(f"unexpected Dataset A columns in {split_name}: {list(frame.columns)}")
        frame.to_csv(output_dir / f"{split_name}.csv", index=False)
        labels.update(frame["Class"].dropna().astype(str).str.strip())

    combined = pd.concat((split.to_pandas() for split in dataset.values()), ignore_index=True)
    for label, group in combined.groupby("Class", sort=True):
        examples_by_label[str(label)] = group["Phrase"].astype(str).head(3).tolist()

    sorted_labels = sorted(labels)
    write_json(output_dir / "original_labels.json", sorted_labels)
    report = {
        "dataset_id": DATASET_A_ID,
        "revision": DATASET_A_REVISION,
        "source_url": f"https://huggingface.co/datasets/{DATASET_A_ID}",
        "license": "not specified in dataset card metadata",
        "split_sizes": split_sizes,
        "columns": columns,
        "labels": sorted_labels,
        "examples_by_label": examples_by_label,
    }
    write_json(output_dir / "inspection.json", report)

    print(f"Dataset A: {sum(split_sizes.values()):,} rows across {len(sorted_labels)} labels")
    print("Labels:")
    for label in sorted_labels:
        print(f"- {label}")
    return report


def _item_name_from_label(label: str) -> str:
    corrections = {
        "PAPER MAGASINE": "paper magazine",
        "TETRAPACK": "tetrapak",
    }
    return corrections.get(label, label.casefold().replace("-", " "))


def process_dataset_a(
    raw_dir: Path | None = None,
    output_path: Path | None = None,
    mapping_path: Path | None = None,
    review_path: Path | None = None,
) -> dict[str, Any]:
    raw_dir = raw_dir or RAW_DIR / "dataset_a"
    output_path = output_path or PROCESSED_DIR / "dataset_a.csv"
    mapping_path = mapping_path or MAPPINGS_DIR / "dataset_a_label_mapping.json"
    review_path = review_path or MAPPINGS_DIR / "needs_manual_review.csv"

    csv_paths = sorted(raw_dir.glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError("Dataset A raw splits are missing; run download_dataset_a.py")

    frames: list[pd.DataFrame] = []
    for path in csv_paths:
        frame = pd.read_csv(path)
        frame["original_split"] = path.stem
        frames.append(frame)
    source = pd.concat(frames, ignore_index=True)

    mapping = read_json(mapping_path)
    if not isinstance(mapping, dict):
        raise TypeError("Dataset A mapping must be a JSON object")

    original_labels = set(source["Class"].dropna().astype(str).str.strip())
    unmapped = sorted(original_labels - set(mapping))
    extra = sorted(set(mapping) - original_labels)
    invalid_targets = sorted(set(mapping.values()) - set(TARGET_LABELS))
    if unmapped or extra or invalid_targets:
        raise ValueError(
            f"invalid Dataset A mapping: unmapped={unmapped}, extra={extra}, "
            f"invalid_targets={invalid_targets}"
        )

    review_status = load_mapping_review(review_path, mapping)

    processed = pd.DataFrame(
        {
            "text": source["Phrase"].map(normalize_whitespace),
            "target_label": source["Class"].map(mapping),
            "source": "dataset_a",
            "original_label": source["Class"].astype(str).str.strip(),
            "item_name": source["Class"].astype(str).map(_item_name_from_label),
            "generation_method": "source_phrase",
            "original_split": source["original_split"],
        }
    )
    processed["item_group"] = "dataset_a::" + processed["item_name"].map(normalize_key)
    processed["mapping_status"] = processed["original_label"].map(review_status)
    processed = processed[processed["text"] != ""].copy()

    before_deduplication = len(processed)
    processed = processed.drop_duplicates(subset=["text", "target_label"], keep="first")
    exact_duplicates_removed = before_deduplication - len(processed)

    processed["_near_duplicate_key"] = processed["text"].map(normalize_key)
    near_duplicate_groups = int(
        (processed.groupby("_near_duplicate_key", dropna=False).size() > 1).sum()
    )
    processed = processed.drop(columns="_near_duplicate_key")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    processed.to_csv(output_path, index=False)
    report = {
        "input_rows": int(len(source)),
        "output_rows": int(len(processed)),
        "exact_duplicates_removed": int(exact_duplicates_removed),
        "near_duplicate_groups": near_duplicate_groups,
        "mapping_status_counts": processed["mapping_status"].value_counts().to_dict(),
        "class_counts": processed["target_label"].value_counts().to_dict(),
    }
    write_json(PROCESSED_DIR / "dataset_a_report.json", report)
    print(
        f"Dataset A processed: {len(processed):,} rows; "
        f"{report['mapping_status_counts'].get('needs_review', 0):,} await mapping review"
    )
    return report
