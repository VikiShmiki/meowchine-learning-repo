"""Bind evaluation identities and training overlap checks to immutable model evidence."""

import hashlib
import json
from pathlib import Path

from smart_recycling.data.common import sha256_file
from smart_recycling.data.ml_v3 import read_rows
from smart_recycling.data.review import load_reviewed_manual


def load_bound_rows(rows_path: Path, manifest_path: Path, head_path: Path, head_sha256: str):
    """Verify the complete head -> manifest -> rows chain before accepting overlap evidence."""
    if sha256_file(head_path) != head_sha256:
        raise ValueError("Evaluation head checksum differs from the pinned model")
    head = json.loads(head_path.read_text(encoding="utf-8"))
    manifest_hash = sha256_file(manifest_path)
    if head.get("dataset_sha256") != manifest_hash:
        raise ValueError("Training manifest does not belong to this model")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows_hash = sha256_file(rows_path)
    if manifest.get("outputs", {}).get("rows.json") != rows_hash:
        raise ValueError("Training rows checksum differs from the bound manifest")
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    return rows, dict(
        head_sha256=head_sha256,
        dataset_manifest_sha256=manifest_hash,
        training_rows_sha256=rows_hash,
    )


def reviewed_manual_rows(root: Path, language: str):
    """Join by English text hash, never by CSV position; retain held cases explicitly."""
    if language not in {"en", "mk"}:
        raise ValueError("Unsupported evaluation language")
    directory = root / "data/evaluation"
    english_path = directory / "manual_test.csv"
    review_path = directory / "manual_test_review.csv"
    # Existing evidence validation checks all original labels and source approvals.
    load_reviewed_manual(english_path, review_path)
    review = read_rows(review_path)
    if len({r["case_id"] for r in review}) != len(review) or any(not r["case_id"] for r in review):
        raise ValueError("Manual case IDs must be unique and nonempty")
    by_hash = {r["text_sha256"]: r for r in review}
    table_path = directory / ("manual_test.csv" if language == "en" else "manual_test_mk.csv")
    table = read_rows(table_path)
    seen = set()
    rows = []
    for item in table:
        identity = (
            hashlib.sha256(item["text"].encode()).hexdigest()
            if language == "en"
            else item["english_text_sha256"]
        )
        if identity in seen or identity not in by_hash:
            raise ValueError("Evaluation case is duplicated or has no matching source review")
        seen.add(identity)
        source = by_hash[identity]
        if item["target_label"] != source["target_label"]:
            raise ValueError("Evaluation label differs from its reviewed source")
        if not item["text"].strip():
            raise ValueError("Evaluation text must be nonempty")
        rows.append(
            dict(
                item,
                label=source["target_label"]
                if source["review_status"] == "source_supported"
                else "",
                group=source["case_id"],
                variant="0",
                language=language,
                english_text_sha256=identity,
            )
        )
    if seen != set(by_hash):
        raise ValueError("Evaluation must cover every reviewed source case exactly once")
    return rows, {path.name: sha256_file(path) for path in {english_path, review_path, table_path}}
