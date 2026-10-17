"""Auditable development corpus; authored concepts are not independent user evidence."""

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from smart_recycling.data.common import normalize_key, sha256_file
from smart_recycling.language import latin
from smart_recycling.object_models import LABELS

ROLES = ("train", "tune", "calibration", "test")
MATERIAL = {
    "glass": r"\bglass\b",
    "plastic_metal": r"\b(plastic|alumini?um|steel|metal)\b",
    "paper_tetrapak": r"\b(paper|cardboard|newspaper|magazine|magasine|tetra\s?pa[ck]k?)\b",
    "special_unsupported": r"\bbatter(y|ies)\b",
    "electronics": r"\b(charger|phone|smartphone)\b",
}


def read_rows(path, delimiter=","):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def prepare(root: Path, source_root: Path, output: Path):
    """Keep source English independently; quarantine all unreviewed legacy translation."""
    fixture = root / "data/ml/v3"
    rows = []
    seen = {}
    for filename in ("items.tsv", "held.tsv"):
        for item in read_rows(fixture / filename, "\t"):
            role, label = item["role"], item.get("label", "")
            if role not in ROLES or (filename == "items.tsv" and label not in LABELS):
                raise ValueError("Invalid role or label")
            group = digest(normalize_key(item["en"]))[:20]
            for language in ("en", "mk"):
                text = item[language].strip()
                key = normalize_key(text)
                if not key or key in seen:
                    raise ValueError(f"Duplicate authored text: {text}")
                seen[key] = role
                variants = [text]
                if language == "mk":
                    variants += [
                        latin(text),
                        latin(text).replace("ch", "c").replace("sh", "s").replace("zh", "z"),
                    ]
                # Variants retain their concept group and split, including during evaluation.
                for index, variant in enumerate(dict.fromkeys(variants)):
                    rows.append(
                        dict(
                            text=variant,
                            label=label,
                            role=role,
                            group=group,
                            language=language,
                            variant=str(index),
                            source="authored",
                            review="agent_authored_needs_native_review"
                            if language == "mk"
                            else "agent_authored_development",
                        )
                    )
    for role in ROLES:
        counts = Counter(
            r["label"] for r in rows if r["role"] == role and r["language"] == "en" and r["label"]
        )
        if set(counts) != set(LABELS) or min(counts.values()) < 8:
            raise ValueError(f"Insufficient independent concept support: {role}")
    review_path = root / "data/mappings/needs_manual_review.csv"
    approved = {
        r["original_label"]: r["proposed_target_label"]
        for r in read_rows(review_path)
        if r["mapping_status"] == "approved"
    }
    source_path = source_root / "data/processed/dataset_a.csv"
    exclusions, retained = [], []
    reserved = {normalize_key(r["text"]) for r in rows if r["role"] != "train"}
    # Prevent old query templates containing a held-out concept from entering training.
    reserved_en = [
        normalize_key(r["text"]) for r in rows if r["role"] != "train" and r["language"] == "en"
    ]
    for item in read_rows(source_path):
        label = approved.get(item["original_label"])
        if item["original_label"] in {"PHONE CHARGER", "LAPTOP CHARGER", "SMARTPHONE"}:
            label = "electronics"
        text = item["text"].strip()
        key = normalize_key(text)
        reason = None
        if label not in MATERIAL:
            reason = "mapping_not_currently_approved"
        elif not re.search(MATERIAL[label], text, re.I):
            reason = "material_or_object_not_explicit"
        elif key in reserved or any(f" {term} " in f" {key} " for term in reserved_en):
            reason = "reserved_development_concept"
        elif key in seen:
            reason = "duplicate_text"
        if reason:
            exclusions.append(
                dict(text_sha256=digest(text), reason=reason, original_label=item["original_label"])
            )
            continue
        seen[key] = "train"
        retained.append(
            dict(
                text=text,
                label=label,
                role="train",
                group=item["item_group"],
                language="en",
                variant="0",
                source="dataset_a",
                review="agent_source_review_english_only",
            )
        )
    # Bound template dominance; deterministic representative sampling by source group.
    for group in sorted({r["group"] for r in retained}):
        candidates = sorted(
            (r for r in retained if r["group"] == group), key=lambda r: digest(r["text"])
        )
        rows.extend(candidates[:30])
    split_keys = {}
    split_groups = {}
    for row in rows:
        for mapping, key in (
            (split_keys, normalize_key(row["text"])),
            (split_groups, row["group"]),
        ):
            if key in mapping and mapping[key] != row["role"]:
                raise ValueError("Text or concept group crosses development roles")
            mapping[key] = row["role"]
    output.mkdir(parents=True, exist_ok=True)
    for name, values in [
        ("rows.json", rows),
        ("retained_english.json", retained),
        ("exclusions.json", exclusions),
    ]:
        (output / name).write_text(
            json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
    manifest = dict(
        version="ml-development-v3",
        seed=42,
        evidence="Agent-authored development splits; native and independent review pending",
        grouping="Specific authored object concept; broad material families overlap by design",
        inputs={
            "source:data/processed/dataset_a.csv": sha256_file(source_path),
            "repo:data/mappings/needs_manual_review.csv": sha256_file(review_path),
            **{f"repo:data/ml/v3/{f}": sha256_file(fixture / f) for f in ("items.tsv", "held.tsv")},
        },
        legacy_mk="All legacy automatic translations quarantined; not used for fitting",
        retained_english=len(retained),
        sampled_source_english=sum(r["source"] == "dataset_a" for r in rows),
        exclusions=dict(Counter(r["reason"] for r in exclusions)),
        outputs={
            f: sha256_file(output / f)
            for f in ("rows.json", "retained_english.json", "exclusions.json")
        },
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return rows, manifest
