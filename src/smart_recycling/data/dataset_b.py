"""Download Toronto Waste Wizard vocabulary and build a reviewable local mapping."""

import json
import re
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd

from smart_recycling.data.common import normalize_key, sha256_file, write_json
from smart_recycling.data.constants import (
    MAPPINGS_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    TARGET_LABELS,
    TORONTO_PACKAGE_API,
)


def _download_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "najdi-frli/0.1"})
    with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed HTTPS source
        return response.read()


def download_dataset_b(output_dir: Path | None = None) -> dict[str, Any]:
    output_dir = output_dir or RAW_DIR / "dataset_b"
    output_dir.mkdir(parents=True, exist_ok=True)

    package_payload = json.loads(_download_bytes(TORONTO_PACKAGE_API))
    if not package_payload.get("success"):
        raise RuntimeError("Toronto catalogue API did not return success")
    package = package_payload["result"]
    resources = [resource for resource in package["resources"] if resource["format"] == "JSON"]
    if len(resources) != 1:
        raise ValueError(f"expected one Toronto JSON resource, found {len(resources)}")

    resource = resources[0]
    raw_path = output_dir / "waste_wizard.json"
    raw_path.write_bytes(_download_bytes(resource["url"]))
    rows = json.loads(raw_path.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list) or not rows or "item" not in rows[0]:
        raise ValueError("unexpected Toronto Waste Wizard JSON structure")

    metadata = {
        "dataset_id": package["id"],
        "title": package["title"],
        "source_url": resource["url"],
        "information_url": package["information_url"],
        "license": package.get("license_title") or "not specified",
        "last_modified": resource.get("last_modified"),
        "rows": len(rows),
        "sha256": sha256_file(raw_path),
    }
    write_json(output_dir / "metadata.json", metadata)
    print(f"Dataset B downloaded: {len(rows):,} Toronto Waste Wizard rows")
    return metadata


def _suggest_target(item_name: str) -> tuple[str, str]:
    """Return only high-precision proposals based on item vocabulary, not Toronto streams."""
    text = normalize_key(item_name)
    rules: tuple[tuple[str, str, str], ...] = (
        (
            r"\b(batter(?:y|ies)|chargers?|smartphones?|cell phones?|mobile phones?|"
            r"computers?|laptops?|"
            r"electronic|fluorescent|medication|medicine|syringe|sharp|mercury|pesticide|"
            r"propane|paint thinner|hazardous chemical)\b",
            "special_unsupported",
            "special or electronic waste keyword",
        ),
        (
            r"\b(glass (?:bottles?|jars?)|wine bottles?|beer bottles?|mason jars?|"
            r"sauce jars?)\b",
            "glass",
            "glass packaging phrase",
        ),
        (
            r"\b(tetra ?paks?|aseptic cartons?|newspapers?|magazines?|corrugated cardboard|"
            r"cardboard boxes|paper bags?|notebooks?)\b",
            "paper_tetrapak",
            "paper or carton vocabulary",
        ),
        (
            r"\b(plastic (?:bottles?|detergent containers?|shampoo bottles?)|"
            r"alumin(?:um|ium) cans?|steel cans?|tin cans?|drink cans?|metal food cans?)\b",
            "plastic_metal",
            "supported plastic bottle or metal packaging phrase",
        ),
        (
            r"\b(diapers?|napp(?:y|ies)|used tissues?|facial tissues?|dirty sponges?|"
            r"toothbrushes?|ceramics?|drinking glasses|mirrors?|face masks?|"
            r"plastic cutlery|plastic straws?)\b",
            "general",
            "ordinary unsupported or non-packaging item phrase",
        ),
    )
    for pattern, target, reason in rules:
        if re.search(pattern, text):
            return target, reason
    return "", "no high-confidence local mapping rule matched"


def _is_manual_mapping(row: dict[str, str] | None) -> bool:
    if not row:
        return False
    return bool(
        row.get("mapping_status") in {"approved", "excluded"}
        or row.get("mapping_method") == "manual"
    )


def process_dataset_b(
    raw_path: Path | None = None,
    mapping_path: Path | None = None,
) -> dict[str, Any]:
    raw_path = raw_path or RAW_DIR / "dataset_b" / "waste_wizard.json"
    mapping_path = mapping_path or MAPPINGS_DIR / "dataset_b_item_mapping.csv"
    if not raw_path.exists():
        raise FileNotFoundError("Dataset B raw JSON is missing; run download_dataset_b.py")

    rows = json.loads(raw_path.read_text(encoding="utf-8-sig"))
    source = pd.DataFrame(rows)
    if not {"id", "item", "category"}.issubset(source.columns):
        raise ValueError(f"unexpected Dataset B columns: {list(source.columns)}")

    source["source_item_name"] = source["item"]
    source["item"] = source["item"].astype(str).str.split(r"\s*/\s*", regex=True)
    source = source.explode("item", ignore_index=True)
    source["normalized_item_name"] = source["item"].map(normalize_key)
    source = source[source["normalized_item_name"] != ""].copy()
    grouped = (
        source.groupby("normalized_item_name", as_index=False)
        .agg(
            item_name=("item", "first"),
            source_item_name=("source_item_name", lambda values: " | ".join(sorted(set(values)))),
            original_toronto_category=("category", lambda values: " | ".join(sorted(set(values)))),
            source_id=("id", lambda values: " | ".join(sorted(set(values)))),
        )
        .sort_values("normalized_item_name")
    )

    previous: dict[str, dict[str, str]] = {}
    if mapping_path.exists():
        existing = pd.read_csv(mapping_path, dtype=str).fillna("")
        previous = {row["normalized_item_name"]: row.to_dict() for _, row in existing.iterrows()}

    mapped_rows: list[dict[str, str]] = []
    for row in grouped.to_dict(orient="records"):
        old = previous.get(row["normalized_item_name"])
        if _is_manual_mapping(old):
            proposed = old.get("proposed_target_label", "")
            target = old.get("target_label", "")
            status = old["mapping_status"]
            reason = old.get("mapping_reason", "manual review state preserved")
            method = "manual"
        else:
            proposed, reason = _suggest_target(row["item_name"])
            target = proposed
            status = "needs_review"
            method = "rule" if proposed else "unresolved"
        if target and target not in TARGET_LABELS:
            raise ValueError(f"invalid Dataset B target for {row['item_name']!r}: {target}")
        mapped_rows.append(
            {
                **row,
                "proposed_target_label": proposed,
                "target_label": target,
                "mapping_status": status,
                "mapping_reason": reason,
                "mapping_method": method,
            }
        )

    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping = pd.DataFrame(mapped_rows)
    mapping.to_csv(mapping_path, index=False)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    mapping["_token_key"] = mapping["normalized_item_name"].map(
        lambda value: " ".join(sorted(value.split()))
    )
    near_duplicate_counts = mapping.groupby("_token_key").size()
    near_duplicate_keys = near_duplicate_counts[near_duplicate_counts > 1].index
    near_duplicates = mapping[mapping["_token_key"].isin(near_duplicate_keys)].drop(
        columns="_token_key"
    )
    near_duplicates.to_csv(PROCESSED_DIR / "dataset_b_near_duplicates.csv", index=False)
    report = {
        "source_rows_after_alias_expansion": int(len(source)),
        "unique_items": int(len(mapping)),
        "duplicate_items_collapsed": int(len(source) - len(mapping)),
        "near_duplicate_groups": int(len(near_duplicate_keys)),
        "mapping_status_counts": mapping["mapping_status"].value_counts().to_dict(),
        "proposed_class_counts": mapping["proposed_target_label"].value_counts().to_dict(),
        "note": "Toronto categories were retained for review but not used by mapping rules.",
    }
    write_json(PROCESSED_DIR / "dataset_b_mapping_report.json", report)
    print(
        f"Dataset B mapping: {len(mapping):,} unique items; "
        f"{report['mapping_status_counts'].get('needs_review', 0):,} need review"
    )
    return report
