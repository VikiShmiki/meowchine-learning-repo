"""Regression tests for evidence gates and conservative local acceptance policy."""

import json
from pathlib import Path

import pandas as pd
import pytest

from smart_recycling.data import augmentation, combination, dataset_b
from smart_recycling.data.constants import EVALUATION_DIR, MAPPINGS_DIR
from smart_recycling.data.review import (
    POLICY_PATH,
    load_mapping_review,
    load_reviewed_manual,
    validate_training_reviews,
)


def test_missing_mapping_decision_is_not_implicit_approval(tmp_path: Path) -> None:
    mapping = json.loads((MAPPINGS_DIR / "dataset_a_label_mapping.json").read_text())
    review = pd.read_csv(MAPPINGS_DIR / "needs_manual_review.csv")
    path = tmp_path / "review.csv"
    review.iloc[1:].to_csv(path, index=False)
    with pytest.raises(ValueError, match="every label exactly once"):
        load_mapping_review(path, mapping)


def test_approval_requires_identifiable_source(tmp_path: Path) -> None:
    mapping = json.loads((MAPPINGS_DIR / "dataset_a_label_mapping.json").read_text())
    review = pd.read_csv(MAPPINGS_DIR / "needs_manual_review.csv").fillna("")
    review.loc[review["original_label"] == "PLASTIC BAG", "evidence_ids"] = ""
    path = tmp_path / "review.csv"
    review.to_csv(path, index=False)
    with pytest.raises(ValueError, match="needs evidence"):
        load_mapping_review(path, mapping)


def test_local_mapping_decisions_preserve_ambiguous_holds() -> None:
    mapping = json.loads((MAPPINGS_DIR / "dataset_a_label_mapping.json").read_text())
    statuses = load_mapping_review(MAPPINGS_DIR / "needs_manual_review.csv", mapping)
    assert statuses["PLASTIC BAG"] == "approved"
    assert statuses["TETRAPACK"] == "approved"
    assert statuses["PIZZA BOX"] == "needs_review"
    assert statuses["COVID TEST"] == "needs_review"
    assert statuses["MEDS BLISTER"] == "needs_review"


def test_manual_review_selects_supported_queries_and_discloses_missing_class() -> None:
    selected, report = load_reviewed_manual(EVALUATION_DIR / "manual_test.csv")
    assert report["total_queries"] == 100
    assert len(selected) + report["held_queries"] == 100
    assert "general" not in set(selected["target_label"])
    assert "expired prescription medication" not in set(selected["text"])
    assert "AA batteries from a remote" in set(selected["text"])
    # The original immutable fixture is explicitly not human-approved.
    assert set(selected["review_status"]) == {"needs_human_review"}


def test_changed_manual_text_invalidates_review(tmp_path: Path) -> None:
    manual = pd.read_csv(EVALUATION_DIR / "manual_test.csv")
    manual.loc[0, "text"] = "a different item"
    path = tmp_path / "manual.csv"
    manual.to_csv(path, index=False)
    with pytest.raises(ValueError, match="every original query"):
        load_reviewed_manual(path)


def test_toronto_rules_propose_but_do_not_approve(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dataset_b, "PROCESSED_DIR", tmp_path)
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps([{"id": "1", "item": "glass bottle", "category": "Garbage"}]))
    mapping = tmp_path / "mapping.csv"
    dataset_b.process_dataset_b(raw, mapping)
    rows = pd.read_csv(mapping).fillna("")
    assert rows.loc[0, "proposed_target_label"] == "glass"
    assert rows.loc[0, "mapping_status"] == "needs_review"


def test_old_auto_approved_rows_never_enter_augmentation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(augmentation, "PROCESSED_DIR", tmp_path)
    path = tmp_path / "mapping.csv"
    pd.DataFrame([{"mapping_status": "auto_approved", "target_label": "glass"}]).to_csv(
        path,
        index=False,
    )
    output = tmp_path / "augmented.csv"
    report = augmentation.generate_augmented_queries(path, output)
    assert report["queries"] == 0
    assert pd.read_csv(output).empty  # Empty reviewed sets still produce a valid schema.


def test_old_auto_approved_rows_never_enter_combined_training(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(combination, "PROCESSED_DIR", tmp_path)
    base = {
        "text": "glass bottle",
        "target_label": "glass",
        "source": "dataset_a",
        "original_label": "GLASS BOTTLE",
        "item_name": "glass bottle",
        "generation_method": "source",
        "item_group": "glass bottle",
        "mapping_status": "approved",
    }
    a, b, output = (tmp_path / name for name in ("a.csv", "b.csv", "combined.csv"))
    pd.DataFrame([base]).to_csv(a, index=False)
    pd.DataFrame([{**base, "text": "unreviewed item", "mapping_status": "auto_approved"}]).to_csv(
        b,
        index=False,
    )
    combination.combine_datasets(a, b, output)
    assert pd.read_csv(output)["text"].tolist() == ["glass bottle"]


def test_site_profiles_cannot_broaden_machine_or_specialist_acceptance() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    profiles = {row["id"]: row for row in policy["profiles"]}
    assert "empty_tetrapak" in profiles["pakomak_blue"]["accepted_item_kinds"]
    machine = profiles["pakomak_vending"]["accepted_item_kinds"]
    assert "empty_pet_beverage_bottle" in machine
    assert "empty_plastic_bottle" not in machine
    assert all(not row["facility_ids"] for row in policy["specialist_guidance"].values())
    assert policy["defaults"]["unknown_site_acceptance"] == "do_not_route"


@pytest.mark.parametrize(
    ("source", "label", "status", "error"),
    [
        ("dataset_a", "CIGARETTE BUTT", "approved", "outdated Dataset A"),
        ("dataset_b_augmented", "glass", "auto_approved", "unreviewed mappings"),
    ],
)
def test_baselines_reject_stale_processed_data(source, label, status, error) -> None:
    frame = pd.DataFrame(
        [
            {
                "source": source,
                "original_label": label,
                "mapping_status": status,
                "target_label": "general" if source == "dataset_a" else "glass",
            }
        ]
    )
    with pytest.raises(ValueError, match=error):
        validate_training_reviews(frame)


def test_baselines_explain_missing_reviewed_class_before_fitting(tmp_path: Path) -> None:
    from smart_recycling.data.baselines import train_baselines

    path = tmp_path / "split.csv"
    pd.DataFrame(
        [
            {
                "source": "dataset_a",
                "original_label": "GLASS BOTTLE",
                "mapping_status": "approved",
                "target_label": "glass",
                "text": "glass bottle",
                "split": "train",
            }
        ]
    ).to_csv(path, index=False)
    with pytest.raises(ValueError, match="reviewed training data lacks classes"):
        train_baselines(path, results_dir=tmp_path / "results", artifacts_dir=tmp_path / "models")
    assert not list((tmp_path / "models").glob("*.joblib"))
