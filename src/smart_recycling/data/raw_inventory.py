"""Acquire raw waste sources and report keyword candidates, without preparing training data."""

import csv
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from smart_recycling.data.common import read_json, sha256_file, write_json
from smart_recycling.data.constants import DATASET_A_ID, DATASET_A_REVISION, RAW_DIR

CLOTHING_TERMS = (
    "clothing",
    "clothes",
    "textile",
    "shirt",
    "t-shirt",
    "jeans",
    "pants",
    "trousers",
    "shorts",
    "hoodie",
    "sweater",
    "jacket",
    "coat",
    "dress",
    "skirt",
    "socks",
    "underwear",
    "shoes",
    "sneakers",
    "boots",
    "blanket",
    "bedsheet",
    "linen",
    "towel",
    "curtain",
    "fabric",
)
ELECTRONICS_TERMS = (
    "phone",
    "smartphone",
    "laptop",
    "computer",
    "monitor",
    "television",
    "charger",
    "cable",
    "headphones",
    "keyboard",
    "mouse",
    "printer",
    "router",
    "tablet",
    "camera",
    "speaker",
    "electronics",
    "electronic",
)
_PATTERN_OVERRIDES = {
    "t-shirt": r"t[\s-]?shirts?",
    "bedsheet": r"bed[\s-]?sheets?",
    "dress": r"dress(?:es)?",
    "mouse": r"(?:mouse|mice)",
    **{term: rf"{term[:-1]}s?" for term in ("socks", "shoes", "sneakers", "boots", "headphones")},
}
_INVARIANT_TERMS = {"clothing", "clothes", "jeans", "pants", "trousers", "shorts", "underwear"}
KEYWORD_PATTERNS = {
    term: re.compile(
        r"\b(?:"
        + _PATTERN_OVERRIDES.get(term, re.escape(term) + ("" if term in _INVARIANT_TERMS else "s?"))
        + r")\b",
        re.IGNORECASE,
    )
    for term in (*CLOTHING_TERMS, *ELECTRONICS_TERMS)
}


def matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    """Word-boundary candidates, including common plurals; never class assignments."""
    return [term for term in terms if KEYWORD_PATTERNS[term].search(text)]


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    """Preserve all original fields; serialize nested JSON values inside CSV cells."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (list, dict, bool))
                    else value
                    for key, value in row.items()
                }
            )


def _candidates(
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
    terms: tuple[str, ...],
    source: str,
    split: str,
) -> list[dict[str, Any]]:
    candidates = []
    for index, row in enumerate(rows):
        hits = matched_terms("\n".join(str(row.get(field, "")) for field in fields), terms)
        if hits:
            candidates.append(
                {
                    **row,
                    "_dataset": source,
                    "_split": split,
                    "_source_row": index,
                    "_matched_terms": hits,
                }
            )
    return candidates


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(key for row in rows for key in row))


def inspect_raw_datasets(raw_dir: Path = RAW_DIR) -> dict[str, Any]:
    """Only write inventories/candidate exports. Never alter source rows or split files."""
    hf_dir = raw_dir / "waste_classification_v2"
    toronto_dir = raw_dir / "toronto_waste_wizard"
    manifest = read_json(hf_dir / "download.json")
    toronto_metadata = read_json(toronto_dir / "metadata.json")
    raw_path = toronto_dir / "waste_wizard.json"
    if sha256_file(raw_path) != toronto_metadata["sha256"]:
        raise ValueError("Toronto raw file differs from its downloaded checksum")

    hf_reports = {}
    label_counts = []
    all_labels: Counter[str] = Counter()
    samples = []
    electronics = []
    for split, metadata in manifest["files"].items():
        path = hf_dir / metadata["filename"]
        if sha256_file(path) != metadata["sha256"]:
            raise ValueError(f"Hugging Face raw checksum mismatch: {path.name}")
        columns, rows = _read_csv(path)
        if not {"Phrase", "Class"}.issubset(columns):
            raise ValueError(f"Unexpected Hugging Face columns: {columns}")
        counts = Counter(row["Class"] for row in rows)
        all_labels.update(counts)
        label_counts.extend(
            {"split": split, "label": label, "count": count}
            for label, count in sorted(counts.items())
        )
        matches = _candidates(rows, ("Phrase", "Class"), ELECTRONICS_TERMS, DATASET_A_ID, split)
        electronics.extend(matches)
        samples.extend(
            {**row, "_split": split, "_source_row": index} for index, row in enumerate(rows[:5])
        )
        hf_reports[split] = {
            **metadata,
            "rows": len(rows),
            "columns": columns,
            "label_counts": dict(counts),
            "electronics_candidates": len(matches),
            "clothing_candidates": len(
                _candidates(
                    rows,
                    ("Phrase", "Class"),
                    CLOTHING_TERMS,
                    DATASET_A_ID,
                    split,
                )
            ),
        }

    rows = json.loads(raw_path.read_text(encoding="utf-8-sig"))
    if (
        not isinstance(rows, list)
        or not rows
        or not all(isinstance(row, dict) and {"item", "category"}.issubset(row) for row in rows)
    ):
        raise ValueError("Unexpected Toronto Waste Wizard schema")
    clothing = _candidates(rows, ("item",), CLOTHING_TERMS, "toronto_waste_wizard", "raw")
    toronto_electronics = _candidates(
        rows,
        ("item",),
        ELECTRONICS_TERMS,
        "toronto_waste_wizard",
        "raw",
    )
    electronics.extend(toronto_electronics)
    toronto_columns = _columns(rows)
    metadata_columns = ["_dataset", "_split", "_source_row", "_matched_terms"]
    _write_csv(
        toronto_dir / "clothing_candidates.csv", toronto_columns + metadata_columns, clothing
    )
    electronics_columns = list(dict.fromkeys(metadata_columns + _columns(electronics)))
    _write_csv(raw_dir / "electronics_candidates.csv", electronics_columns, electronics)
    _write_csv(hf_dir / "label_counts.csv", ["split", "label", "count"], label_counts)
    _write_csv(hf_dir / "sample_rows.csv", _columns(samples), samples)
    _write_csv(toronto_dir / "sample_rows.csv", toronto_columns, rows[:5])
    category_counts = Counter(row["category"] for row in rows)
    _write_csv(
        toronto_dir / "category_counts.csv",
        ["category", "count"],
        [
            {"category": category, "count": count}
            for category, count in sorted(category_counts.items())
        ],
    )
    write_json(hf_dir / "original_labels.json", sorted(all_labels))
    report = {
        "scope": "Raw acquisition and keyword inventory only; no mapping or model training",
        "hugging_face": {**manifest, "files": hf_reports, "labels": sorted(all_labels)},
        "toronto": {
            **toronto_metadata,
            "columns": toronto_columns,
            "rows": len(rows),
            "field_roles": {
                "item_name": "item",
                "disposal_category": "category",
                "instructions": "instructions",
                "additional_information": "find_out",
            },
            "category_counts": dict(sorted(category_counts.items())),
            "clothing_candidates": len(clothing),
            "electronics_candidates": len(toronto_electronics),
        },
        "candidate_method": {
            "clothing_terms": CLOTHING_TERMS,
            "electronics_terms": ELECTRONICS_TERMS,
            "patterns": {term: pattern.pattern for term, pattern in KEYWORD_PATTERNS.items()},
            "hf_search_fields": ["Phrase", "Class"],
            "toronto_search_fields": ["item"],
            "notes": [
                "Case-insensitive whole words, common plurals, t-shirt and bed sheet variants.",
                "Count each matching source row once, even if multiple terms match.",
                "Zero-based source row indices; no deduplication or alias expansion.",
                "Candidates are NOT reviewed class labels; paper towels and cable ties can match.",
                "Preserve original fields; CSV nested arrays/booleans are JSON serialized.",
                "Supplementary HF file is separate, not an independent evaluation split.",
            ],
        },
    }
    write_json(raw_dir / "inventory.json", report)
    return report


def download_raw_datasets(raw_dir: Path = RAW_DIR) -> dict[str, Any]:
    """Download a new snapshot; refuse to overwrite a previous one."""
    from datasets import DatasetDict, load_dataset
    from huggingface_hub import hf_hub_download

    from smart_recycling.data.dataset_b import download_dataset_b

    hf_dir = raw_dir / "waste_classification_v2"
    toronto_dir = raw_dir / "toronto_waste_wizard"
    for path in (
        hf_dir,
        toronto_dir,
        raw_dir / "electronics_candidates.csv",
        raw_dir / "inventory.json",
    ):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite {path}; use --inspect-only or --raw-dir")

    retrieved_at = datetime.now(UTC).isoformat()
    dataset = load_dataset(DATASET_A_ID, revision=DATASET_A_REVISION, token=False)
    if not isinstance(dataset, DatasetDict):
        raise TypeError("Hugging Face dataset must expose named splits")
    hf_dir.mkdir(parents=True)
    files = {}
    for split, frame in dataset.items():
        path = hf_dir / f"{split}.csv"
        frame.to_csv(path, index=False)
        files[split] = {
            "filename": path.name,
            "kind": "official_split",
            "features": frame.features.to_dict(),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }

    # Repository companion file is not loaded as a split by load_dataset above.
    extra = Path(
        hf_hub_download(
            DATASET_A_ID,
            "unseen_phrases.csv",
            repo_type="dataset",
            revision=DATASET_A_REVISION,
            token=False,
        )
    )
    extra_path = hf_dir / "unseen_phrases.csv"
    extra_path.write_bytes(extra.read_bytes())
    files["supplementary_unseen_phrases"] = {
        "filename": extra_path.name,
        "kind": "supplementary_source_file",
        "sha256": sha256_file(extra_path),
        "bytes": extra_path.stat().st_size,
    }
    write_json(
        hf_dir / "download.json",
        {
            "dataset_id": DATASET_A_ID,
            "revision": DATASET_A_REVISION,
            "source_url": f"https://huggingface.co/datasets/{DATASET_A_ID}",
            "retrieved_at": retrieved_at,
            "license": "not specified in dataset card metadata",
            "files": files,
        },
    )
    metadata = download_dataset_b(toronto_dir)
    metadata["retrieved_at"] = datetime.now(UTC).isoformat()
    metadata["bytes"] = (toronto_dir / "waste_wizard.json").stat().st_size
    write_json(toronto_dir / "metadata.json", metadata)
    return inspect_raw_datasets(raw_dir)
