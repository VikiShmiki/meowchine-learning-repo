"""Evidence gates for local labels; agent source review is not human sign-off."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from smart_recycling.data.constants import DATA_DIR, EVALUATION_DIR, MAPPINGS_DIR

POLICY_PATH = DATA_DIR / "policy" / "skopje_v1.json"


def _validate_evidence(frame: pd.DataFrame, status_column: str, approved: str) -> None:
    """Reject approved records lacking traceable sources and review identity."""
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    known_sources = set(policy["sources"])
    for row in frame.to_dict(orient="records"):
        evidence = set(filter(None, row["evidence_ids"].split(";")))
        if evidence - known_sources:
            raise ValueError("review contains unknown evidence IDs")
        if row[status_column] == approved and (
            not evidence or not row["reviewer"].strip() or not row["reviewed_on"].strip()
        ):
            raise ValueError("approved review needs evidence, reviewer and date")


def load_mapping_review(path: Path, mapping: dict[str, str]) -> dict[str, str]:
    """Require an explicit evidence decision for every Dataset A source label."""
    review = pd.read_csv(path, dtype=str).fillna("")
    required = {
        "original_label",
        "proposed_target_label",
        "mapping_status",
        "evidence_ids",
        "reviewer",
        "reviewed_on",
    }
    if not required.issubset(review.columns):
        raise ValueError("Dataset A review is missing required evidence columns")
    if review["original_label"].duplicated().any() or set(review["original_label"]) != set(mapping):
        raise ValueError("Dataset A review must cover every label exactly once")
    if not set(review["mapping_status"]).issubset({"approved", "needs_review", "excluded"}):
        raise ValueError("invalid Dataset A review status")
    if any(mapping[row.original_label] != row.proposed_target_label for row in review.itertuples()):
        raise ValueError("Dataset A review target differs from the label mapping")
    _validate_evidence(review, "mapping_status", "approved")
    return dict(zip(review["original_label"], review["mapping_status"], strict=True))


def load_reviewed_manual(
    manual_path: Path,
    review_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Select supported labels without editing or silently approving the original test."""
    review_path = review_path or EVALUATION_DIR / "manual_test_review.csv"
    manual = pd.read_csv(manual_path, dtype=str).fillna("")
    review = pd.read_csv(review_path, dtype=str).fillna("")
    required = {
        "text_sha256",
        "target_label",
        "review_status",
        "evidence_ids",
        "reviewer",
        "reviewed_on",
    }
    if not required.issubset(review.columns):
        raise ValueError("manual review is missing required evidence columns")
    manual["text_sha256"] = manual["text"].map(
        lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest()
    )
    if (
        manual["text_sha256"].duplicated().any()
        or review["text_sha256"].duplicated().any()
        or set(manual["text_sha256"]) != set(review["text_sha256"])
    ):
        raise ValueError("manual review must match every original query exactly once")
    if not set(review["review_status"]).issubset({"source_supported", "needs_review", "excluded"}):
        raise ValueError("invalid manual review status")
    _validate_evidence(review, "review_status", "source_supported")
    merged = manual.merge(review, on="text_sha256", suffixes=("", "_review"), validate="1:1")
    if (merged["target_label"] != merged["target_label_review"]).any():
        raise ValueError("manual review target differs from the original test")
    selected = merged[merged["review_status_review"] == "source_supported"].copy()
    if selected.empty:
        raise ValueError("no source-supported manual queries are available")
    return selected, {
        "total_queries": len(manual),
        "evaluated_queries": len(selected),
        "held_queries": len(manual) - len(selected),
        "class_counts": selected["target_label"].value_counts().to_dict(),
        "review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "scope": "agent source-reviewed subset; not human-approved or a full five-class test",
    }


def validate_training_reviews(dataset: pd.DataFrame) -> None:
    """Reject stale automatic approvals and superseded Dataset A decisions."""
    required = {"mapping_status", "source", "original_label", "target_label"}
    if not required.issubset(dataset.columns):
        raise ValueError("training data lacks review provenance; regenerate the data pipeline")
    if not dataset["mapping_status"].eq("approved").all():
        raise ValueError("training data contains unreviewed mappings; regenerate the data pipeline")
    mapping = json.loads(
        (MAPPINGS_DIR / "dataset_a_label_mapping.json").read_text(encoding="utf-8")
    )
    statuses = load_mapping_review(MAPPINGS_DIR / "needs_manual_review.csv", mapping)
    for row in dataset[dataset["source"] == "dataset_a"].itertuples():
        if statuses.get(row.original_label) != "approved" or (
            mapping.get(row.original_label) != row.target_label
        ):
            raise ValueError(
                "training data has outdated Dataset A approval; regenerate the pipeline"
            )
