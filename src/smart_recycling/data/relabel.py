"""Versioned object-class corrections, separate from local disposal-policy approval."""

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from smart_recycling.data.common import normalize_key, sha256_file, stable_id, write_json
from smart_recycling.data.translation import REVIEW_STATUS, read_csv, text_hash, write_csv

VERSION = "object-classes-v2"
NEW_LABELS = {"clothes", "electronics"}
SPLITS = ("train", "validation", "test")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def reviewed_items(review: dict, catalogue: list[dict]) -> dict[str, tuple[str, str]]:
    """Resolve explicit source IDs, never keywords in instructions or translated text."""
    source_ids = {row["id"] for row in catalogue}
    if len(source_ids) != len(catalogue):
        raise ValueError("Duplicate Toronto source IDs")
    items = {}
    for group, ids in review["toronto_groups"].items():
        label = "clothes" if group.startswith("clothes::") else "electronics"
        for source_id in ids:
            if source_id not in source_ids or source_id in items:
                raise ValueError(f"Missing or duplicate reviewed source ID: {source_id}")
            items[source_id] = (label, group)
    held = set(review["held_toronto_ids"])
    if held - source_ids or held & set(items):
        raise ValueError("Held IDs are missing or also approved")
    if set(review["translation_holds"]) - set(items):
        raise ValueError("Translation hold has no reviewed item")
    return items


def alias_overrides(mapping: list[dict], items: dict[str, tuple[str, str]]) -> dict[str, str]:
    """Use the existing alias-to-source link, including its ambiguous multi-ID cases."""
    aliases = {}
    for row in mapping:
        ids = [value.strip() for value in row["source_id"].split("|")]
        labels = {items[source_id][0] if source_id in items else "" for source_id in ids}
        if len(labels) == 1 and "" not in labels:
            aliases[row["normalized_item_name"]] = labels.pop()
    return aliases


def correct_row(row: dict, review: dict, aliases: dict, by_text: dict) -> dict:
    result = dict(row)
    previous = row.get("target_label", row.get("label", row.get("proposed_target_label", "")))
    english = row.get("text_en", row.get("text", row.get("Phrase_en", "")))
    source_class = row.get("original_label", row.get("Class", ""))
    override = review["hf_overrides"].get(source_class, "")
    if row.get("source") == "dataset_b_augmented":
        override = aliases.get(normalize_key(row["item_name"]), "")
    override = override or by_text.get(english, "")
    label = override or previous
    result["label"] = label
    result["previous_target_label"] = previous
    result["label_review_status"] = "agent_reviewed" if override else "unchanged"
    result["policy_mapping_status"] = row.get(
        "current_mapping_status", row.get("mapping_status", "")
    )
    for key in ("target_label", "proposed_target_label"):
        if key in row:
            result[key] = label
    if "evaluation_label" in row:
        result["policy_evaluation_label"] = row["evaluation_label"]
        result["evaluation_label"] = override or row["evaluation_label"]
    if "Class" in row:
        result["source_class"] = row["Class"]
        result["source_class_index"] = row["Class_index"]
        result["Class"] = label
        result["Class_index"] = str(review["labels"].index(label))
    return result


def english_mirror(row: dict) -> dict:
    result = dict(row)
    for key in ("text", "Phrase", "item", "instructions", "find_out"):
        if f"{key}_en" in row:
            result[key] = row[f"{key}_en"]
    result["language"] = "en"
    result["translation_review_status"] = "original"
    result["translation_method"] = "original"
    return result


def prepare_pairs(rows: list[dict], evaluation_keys: set[str]) -> tuple[list[dict], list[dict]]:
    """Keep inherited groups fixed; split only new groups, with paired-text leakage checks."""
    eligible, excluded = [], []
    for original in rows:
        row = dict(original)
        reason = ""
        if not row["text_en"].strip() or not row["text_mk"].strip():
            reason = "empty_text"
        elif row["translation_qa_flags"]:
            reason = "translation_qa"
        elif any(normalize_key(row[k]) in evaluation_keys for k in ("text_en", "text_mk")):
            reason = "reserved_evaluation_text"
        if reason:
            excluded.append({**row, "exclusion_reason": reason})
        else:
            eligible.append(row)

    # Merge synonymous groups when either language yields the same normalized text.
    parents = {row["item_group"]: row["item_group"] for row in eligible}

    def root(group: str) -> str:
        while parents[group] != group:
            parents[group] = parents[parents[group]]
            group = parents[group]
        return group

    key_group: dict[str, str] = {}
    for row in eligible:
        for field in ("text_en", "text_mk"):
            key = normalize_key(row[field])
            if key in key_group:
                left, right = sorted((root(row["item_group"]), root(key_group[key])))
                parents[right] = left
            key_group[key] = row["item_group"]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        grouped[root(row["item_group"])].append(row)
    assigned: dict[str, str] = {}
    new_groups: dict[str, list[str]] = defaultdict(list)
    for group, members in sorted(grouped.items()):
        splits = {r["split"] for r in members if r["split"]}
        if splits - set(SPLITS):
            raise ValueError("Invalid inherited split")
        reason = ""
        if len({r["label"] for r in members}) != 1:
            reason = "conflicting_labels"
        elif len(splits) > 1:
            reason = "conflicting_inherited_splits"
        if reason:
            excluded.extend({**r, "exclusion_reason": reason} for r in members)
        elif splits:
            assigned[group] = splits.pop()
        else:
            new_groups[members[0]["label"]].append(group)
    rng = random.Random(42)
    for groups in new_groups.values():
        rng.shuffle(groups)
        held = max(1, round(len(groups) * 0.15)) if len(groups) >= 3 else 0
        for index, group in enumerate(groups):
            assigned[group] = (
                "test" if index < held else "validation" if index < 2 * held else "train"
            )
    kept, seen = [], set()
    # Input order puts the existing reviewed pairs ahead of new catalogue synonyms.
    for row in eligible:
        group = root(row["item_group"])
        if group not in assigned:
            continue
        keys = {normalize_key(row[k]) for k in ("text_en", "text_mk")}
        if keys & seen:
            excluded.append({**row, "exclusion_reason": "duplicate_translation_or_source"})
            continue
        seen.update(keys)
        kept.append({**row, "item_group": group, "split": assigned[group]})
    return kept, excluded


def run_relabel(*, root: Path, source: Path, output: Path) -> dict:
    """Produce corrected real CSV/JSON datasets without invalidating historical runs."""
    if output.exists():
        raise FileExistsError("Relabeled output already exists; choose a fresh version directory")
    review_path = root / "data/mappings/object_classes_v2.json"
    review = read_json(review_path)
    if review["version"] != VERSION or not NEW_LABELS.issubset(review["labels"]):
        raise ValueError("Incorrect object-class review version")
    manifest_path = source / "manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("status") != "complete":
        raise ValueError("Incomplete translation package")
    fingerprints = {
        review_path: sha256_file(review_path),
        manifest_path: sha256_file(manifest_path),
    }
    for relative, expected in manifest["source_hashes"].items():
        fingerprints[root / relative] = expected
    for relative, metadata in manifest["outputs"].items():
        fingerprints[source / relative] = metadata["sha256"]
    mapping_path = root / "data/mappings/dataset_b_item_mapping.csv"
    fixture_path = root / "tests/fixtures/macedonian.json"
    fingerprints[mapping_path] = sha256_file(mapping_path)
    fingerprints[fixture_path] = sha256_file(fixture_path)

    def verify_inputs() -> None:
        for path, expected in fingerprints.items():
            if sha256_file(path) != expected:
                raise ValueError(f"Source checksum mismatch: {path}")

    verify_inputs()
    toronto_path = root / "data/raw/toronto_waste_wizard/waste_wizard.json"
    if sha256_file(toronto_path) != review["toronto_source_sha256"]:
        raise ValueError("Reviewed Toronto snapshot changed")
    catalogue = read_json(source / "raw/toronto_waste_wizard/waste_wizard_mk.json")
    items = reviewed_items(review, catalogue)
    aliases = alias_overrides(read_csv(mapping_path), items)
    by_text = dict(review["evaluation_overrides"])
    combined = read_csv(source / "processed/combined_with_splits_mk.csv")
    for row in combined:
        corrected = correct_row(row, review, aliases, {})
        if corrected["label_review_status"] == "agent_reviewed":
            key = row["text_en"]
            if key in by_text and by_text[key] != corrected["label"]:
                raise ValueError("Conflicting source labels for the same English text")
            by_text[key] = corrected["label"]
    outputs, audit, evaluations = {}, [], []

    def save(relative: str, rows: list[dict]) -> None:
        path = output / relative
        if path.suffix == ".json":
            write_json(path, rows)
        else:
            columns = list(dict.fromkeys(key for row in rows for key in row)) or ["id", "label"]
            write_csv(path, rows, columns)
        outputs[relative] = {
            "rows": len(rows),
            "sha256": sha256_file(path),
            "class_counts": dict(Counter(r.get("label", "") for r in rows)),
        }
        if relative == "relabel_audit.csv":
            return
        for index, row in enumerate(rows):
            previous = row.get("previous_target_label", "")
            if row.get("label") in NEW_LABELS and row["label"] != previous:
                audit.append(
                    {
                        "file": relative,
                        "row": index,
                        "source_id": row.get("source_id", row.get("id", row.get("source_row", ""))),
                        "previous_label": previous,
                        "label": row["label"],
                        "review_version": VERSION,
                    }
                )

    for relative in sorted(manifest["outputs"]):
        if not relative.startswith(("raw/waste_classification_v2/", "processed/", "evaluation/")):
            continue
        rows = [correct_row(r, review, aliases, by_text) for r in read_csv(source / relative)]
        save(relative, rows)
        save(relative.replace("_mk.csv", "_en.csv"), [english_mirror(r) for r in rows])
        if relative.startswith("evaluation/"):
            evaluations.extend(rows)
    for row in catalogue:
        row["label"] = items.get(row["id"], ("", ""))[0]
        row["label_review_status"] = "agent_reviewed" if row["label"] else "unchanged"
        row["label_review_note"] = review["held_toronto_ids"].get(row["id"], "")
        row["semantic_translation_hold"] = review["translation_holds"].get(row["id"], "")
    save("raw/toronto_waste_wizard/waste_wizard_mk.json", catalogue)
    save("raw/toronto_waste_wizard/waste_wizard_en.json", [english_mirror(r) for r in catalogue])
    for language in ("en", "mk"):
        save(
            f"catalogue/toronto_{language}.csv",
            [
                {
                    "id": r["id"],
                    "text": r["item_en"] if language == "en" else r["item"],
                    "text_en": r["item_en"],
                    "label": r["label"],
                    "source_category": r["category"],
                    "label_review_status": r["label_review_status"],
                    "label_review_note": r["label_review_note"],
                    "translation_review_status": "original" if language == "en" else REVIEW_STATUS,
                    "translation_qa_flags": r["translation_qa_flags"],
                    "semantic_translation_hold": r["semantic_translation_hold"],
                }
                for r in catalogue
            ],
        )

    # Export object-labeled counterparts; do not mutate serving-policy test fixtures.
    fixture_rows = read_json(fixture_path)
    for language in ("en", "mk"):
        fixture_export = []
        for index, row in enumerate(fixture_rows):
            label = review["evaluation_overrides"].get(row["en"]) or {
                "wearable_clothes": "clothes",
                "small_electronics": "electronics",
                "electronics": "electronics",
            }.get(row["kind"])
            if label:
                fixture_export.append(
                    {
                        "id": f"policy_probe_{index}",
                        "text": row[language],
                        "text_en": row["en"],
                        "label": label,
                        "policy_kind": row["kind"],
                        "policy_status": row["status"],
                        "label_review_status": "agent_reviewed",
                        "translation_review_status": "original"
                        if language == "en"
                        else REVIEW_STATUS,
                    }
                )
        save(f"evaluation/object_probe_{language}.csv", fixture_export)
    evaluation_keys = {
        normalize_key(row[field]) for row in evaluations for field in ("text", "text_en")
    } | {normalize_key(row[lang]) for row in fixture_rows for lang in ("en", "mk")}

    candidates = []
    for original in read_csv(source / "experimental/paired.csv"):
        row = correct_row(original, review, aliases, by_text)
        candidates.append(
            {
                "id": stable_id(VERSION, row["id"], row["label"]),
                "source_id": row["id"],
                "text_en": row["text_en"],
                "text_mk": row["text"],
                "label": row["label"],
                "source": row["source"],
                "item_group": row["item_group"],
                "split": row["split"],
                "previous_target_label": row["previous_target_label"],
                "label_review_status": row["label_review_status"],
                "translation_review_status": REVIEW_STATUS,
                "translation_qa_flags": row["translation_qa_flags"],
            }
        )
    for row in catalogue:
        if row["id"] not in items:
            continue
        label, group = items[row["id"]]
        flags = row["translation_qa_flags"]
        if row["semantic_translation_hold"]:
            flags = ";".join(filter(None, (flags, "semantic_translation_mismatch")))
        candidates.append(
            {
                "id": stable_id(VERSION, "toronto", row["id"], label),
                "source_id": row["id"],
                "text_en": row["item_en"],
                "text_mk": row["item"],
                "label": label,
                "source": "toronto_catalogue",
                "item_group": group,
                "split": "",
                "previous_target_label": "",
                "label_review_status": "agent_reviewed",
                "translation_review_status": REVIEW_STATUS,
                "translation_qa_flags": flags,
            }
        )
    kept, excluded = prepare_pairs(candidates, evaluation_keys)
    save("experimental/paired.csv", kept)
    save("experimental/excluded.csv", excluded)
    counts = {}
    for split in SPLITS:
        subset = [row for row in kept if row["split"] == split]
        counts[split] = dict(Counter(row["label"] for row in subset))
        for language in ("en", "mk", "bilingual"):
            rows = [
                {
                    "id": row["id"] + "::" + lang,
                    "pair_id": row["id"],
                    "text": row[f"text_{lang}"],
                    "label": row["label"],
                    "language": lang,
                    "item_group": row["item_group"],
                    "split": split,
                    "source_id": row["source_id"],
                    "english_text_sha256": text_hash(row["text_en"]),
                    "label_review_status": row["label_review_status"],
                    "translation_review_status": "original" if lang == "en" else REVIEW_STATUS,
                }
                for row in subset
                for lang in (("en", "mk") if language == "bilingual" else (language,))
            ]
            save(f"experimental/{split}_{language}.csv", rows)
    save("relabel_audit.csv", list(audit))
    verify_inputs()
    report = {
        "version": VERSION,
        "status": "complete",
        "seed": 42,
        "labels": review["labels"],
        "source_package": str(source),
        "review_method": review["review_method"],
        "inputs": {str(path): fingerprint for path, fingerprint in fingerprints.items()},
        "export_code_sha256": sha256_file(Path(__file__)),
        "outputs": outputs,
        "reviewed_toronto_counts": dict(Counter(label for label, _ in items.values())),
        "experimental_class_counts": counts,
        "experimental_exclusions": dict(Counter(r["exclusion_reason"] for r in excluded)),
        "missing_labels": {
            split: sorted(set(review["labels"]) - set(c)) for split, c in counts.items()
        },
        "limitations": [
            "Object labels do not approve local disposal, donation, or site acceptance.",
            "All Macedonian text needs native review, including unflagged translations.",
            "Existing review/translation exclusions and inherited split assignments remain.",
            "New catalogue groups are seeded 70/15/15 approximately; class support remains uneven.",
            "Clothes have very few catalogue examples; this is not representative evaluation data.",
            "No source licensing resolution; all derived records remain local and ignored.",
            "Historical benchmarks and serving models still use their original label space.",
            "Full mirrors are not training splits; use experimental/ for paired filtered data.",
            "Supplementary unseen_phrases remain a mirror, not independent evaluation data.",
        ],
    }
    write_json(output / "manifest.json", report)
    return report
