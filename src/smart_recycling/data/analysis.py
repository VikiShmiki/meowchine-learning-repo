"""Generate compact exploratory tables and plots."""

from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from smart_recycling.data.common import normalize_key, write_json
from smart_recycling.data.constants import IMAGES_DIR, PROCESSED_DIR, TARGET_LABELS


def analyze_dataset(
    dataset_path: Path | None = None,
    images_dir: Path | None = None,
) -> dict[str, Any]:
    dataset_path = dataset_path or PROCESSED_DIR / "combined_with_splits.csv"
    images_dir = images_dir or IMAGES_DIR
    images_dir.mkdir(parents=True, exist_ok=True)
    dataset = pd.read_csv(dataset_path, dtype=str).fillna("")
    dataset["word_count"] = dataset["text"].str.split().str.len()
    dataset["text_key"] = dataset["text"].map(normalize_key)

    class_counts = dataset["target_label"].value_counts().reindex(TARGET_LABELS, fill_value=0)
    source_counts = dataset["source"].value_counts()
    item_counts = dataset["item_group"].value_counts()
    summary = {
        "examples": int(len(dataset)),
        "unique_texts": int(dataset["text_key"].nunique()),
        "unique_item_groups": int(dataset["item_group"].nunique()),
        "class_counts": class_counts.to_dict(),
        "class_percentages": (class_counts / len(dataset) * 100).round(2).to_dict(),
        "source_counts": source_counts.to_dict(),
        "text_word_count": {
            key: round(float(value), 2)
            for key, value in dataset["word_count"].describe().to_dict().items()
        },
        "examples_per_item": {
            key: round(float(value), 2) for key, value in item_counts.describe().to_dict().items()
        },
        "duplicate_normalized_text_rows": int(dataset.duplicated("text_key", keep=False).sum()),
        "examples_per_class": {
            label: dataset.loc[dataset["target_label"] == label, "text"].head(5).tolist()
            for label in TARGET_LABELS
        },
    }
    write_json(PROCESSED_DIR / "analysis_summary.json", summary)

    class_counts.plot(kind="bar", color="#176b45", title="Examples per target class")
    plt.ylabel("examples")
    plt.tight_layout()
    plt.savefig(images_dir / "dataset_class_distribution.png", dpi=140)
    plt.close()

    dataset["word_count"].plot(
        kind="hist", bins=30, color="#47785e", title="Query length distribution"
    )
    plt.xlabel("words")
    plt.tight_layout()
    plt.savefig(images_dir / "dataset_text_length.png", dpi=140)
    plt.close()

    print(f"Analysis written for {len(dataset):,} examples and {len(item_counts):,} item groups")
    return summary
