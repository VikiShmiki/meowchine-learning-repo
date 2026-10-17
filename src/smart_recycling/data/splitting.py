"""Create deterministic grouped train, validation, and test splits."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from smart_recycling.data.common import write_json
from smart_recycling.data.constants import PROCESSED_DIR, RANDOM_SEED, TARGET_LABELS

SPLIT_TARGETS = {"train": 0.70, "validation": 0.15, "test": 0.15}


def _score_assignment(group_table: pd.DataFrame, assignment: dict[str, str]) -> float:
    split_rows = dict.fromkeys(SPLIT_TARGETS, 0)
    label_rows = dict.fromkeys(TARGET_LABELS, 0)
    label_split_rows = {label: dict.fromkeys(SPLIT_TARGETS, 0) for label in TARGET_LABELS}
    total_rows = 0
    for record in group_table.itertuples(index=False):
        split = assignment[record.item_group]
        rows = int(record.rows)
        total_rows += rows
        split_rows[split] += rows
        label_rows[record.target_label] += rows
        label_split_rows[record.target_label][split] += rows

    score = 10 * sum(
        abs(split_rows[split] / total_rows - target) for split, target in SPLIT_TARGETS.items()
    )
    for label in TARGET_LABELS:
        if label_rows[label] == 0:
            return float("inf")
        for split, target in SPLIT_TARGETS.items():
            count = label_split_rows[label][split]
            if count == 0:
                score += 100
            score += abs(count / label_rows[label] - target)
    return float(score)


def _candidate_assignment(group_table: pd.DataFrame, seed: int) -> dict[str, str]:
    first = GroupShuffleSplit(n_splits=1, train_size=0.70, random_state=seed)
    train_indices, remainder_indices = next(
        first.split(group_table, groups=group_table["item_group"])
    )
    remainder = group_table.iloc[remainder_indices]
    second = GroupShuffleSplit(n_splits=1, train_size=0.50, random_state=seed + 10_000)
    validation_local, test_local = next(second.split(remainder, groups=remainder["item_group"]))

    assignment = {group_table.iloc[index]["item_group"]: "train" for index in train_indices}
    assignment.update(
        {remainder.iloc[index]["item_group"]: "validation" for index in validation_local}
    )
    assignment.update({remainder.iloc[index]["item_group"]: "test" for index in test_local})
    return assignment


def _refine_assignment(
    group_table: pd.DataFrame, assignment: dict[str, str]
) -> tuple[dict[str, str], float]:
    """Improve row/class balance without ever splitting an item group."""
    current = assignment.copy()
    current_score = _score_assignment(group_table, current)
    records = group_table[["item_group", "target_label"]].to_dict(orient="records")

    for _ in range(12):
        best_score = current_score
        best_assignment: dict[str, str] | None = None

        for record in records:
            group = record["item_group"]
            original_split = current[group]
            for candidate_split in SPLIT_TARGETS:
                if candidate_split == original_split:
                    continue
                candidate = current.copy()
                candidate[group] = candidate_split
                score = _score_assignment(group_table, candidate)
                if score < best_score - 1e-9:
                    best_score = score
                    best_assignment = candidate

        by_label: dict[str, list[str]] = {}
        for record in records:
            by_label.setdefault(record["target_label"], []).append(record["item_group"])
        for groups in by_label.values():
            for left_index, left in enumerate(groups):
                for right in groups[left_index + 1 :]:
                    if current[left] == current[right]:
                        continue
                    candidate = current.copy()
                    candidate[left], candidate[right] = current[right], current[left]
                    score = _score_assignment(group_table, candidate)
                    if score < best_score - 1e-9:
                        best_score = score
                        best_assignment = candidate

        if best_assignment is None:
            break
        current = best_assignment
        current_score = best_score

    return current, current_score


def create_grouped_splits(
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    input_path = input_path or PROCESSED_DIR / "combined_dataset.csv"
    output_path = output_path or PROCESSED_DIR / "combined_with_splits.csv"
    dataset = pd.read_csv(input_path, dtype=str).fillna("")

    labels_per_group = dataset.groupby("item_group")["target_label"].nunique()
    mixed_groups = labels_per_group[labels_per_group > 1]
    if not mixed_groups.empty:
        raise ValueError(
            f"item groups contain conflicting labels: {mixed_groups.index.tolist()[:10]}"
        )

    group_table = (
        dataset.groupby("item_group", as_index=False)
        .agg(target_label=("target_label", "first"), rows=("id", "size"))
        .sort_values("item_group")
        .reset_index(drop=True)
    )
    best_score = float("inf")
    best_assignment: dict[str, str] | None = None
    best_seed = RANDOM_SEED
    for seed in range(RANDOM_SEED, RANDOM_SEED + 500):
        assignment = _candidate_assignment(group_table, seed)
        score = _score_assignment(group_table, assignment)
        if score < best_score:
            best_score = score
            best_assignment = assignment
            best_seed = seed

    if best_assignment is None or not np.isfinite(best_score):
        raise RuntimeError("could not create grouped splits with every class represented")
    best_assignment, best_score = _refine_assignment(group_table, best_assignment)

    dataset["split"] = dataset["item_group"].map(best_assignment)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_path, index=False)
    for split in SPLIT_TARGETS:
        export = dataset.loc[dataset["split"] == split, ["text", "target_label"]].rename(
            columns={"target_label": "label"}
        )
        export.to_csv(output_path.parent / f"{split}.csv", index=False)

    split_counts = dataset["split"].value_counts().reindex(SPLIT_TARGETS, fill_value=0)
    class_by_split = pd.crosstab(dataset["target_label"], dataset["split"]).reindex(
        index=TARGET_LABELS, columns=SPLIT_TARGETS, fill_value=0
    )
    report = {
        "seed": best_seed,
        "search_score": round(best_score, 6),
        "examples": int(len(dataset)),
        "groups": int(len(group_table)),
        "split_counts": split_counts.to_dict(),
        "split_percentages": (split_counts / len(dataset) * 100).round(2).to_dict(),
        "class_by_split": class_by_split.to_dict(orient="index"),
        "limitation": (
            "Dataset A exposes no item identifier; its fine-grained original label is used as "
            "the conservative group, which can limit per-class ratio precision."
        ),
    }
    write_json(output_path.parent / "split_report.json", report)
    print(f"Grouped splits created with seed {best_seed}: {split_counts.to_dict()}")
    return report
