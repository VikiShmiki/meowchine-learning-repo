"""Resumable local English/Macedonian dataset export; never grants label approval."""

import csv
import hashlib
import importlib.metadata
import json
import re
import sqlite3
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smart_recycling.data.common import normalize_key, sha256_file, write_json

MODEL_ID = "facebook/nllb-200-distilled-600M"
MODEL_REVISION = "f8d333a098d19b4fd9a8b18f94170487ad3f821d"
FORMAT_VERSION = "bilingual-mk-v1"
REVIEW_STATUS = "needs_native_review"
MACEDONIAN_LETTERS = set("абвгдѓежзѕијклљмнњопрстќуфхцчџш")
# Review hints, not automatic corrections: synonyms can legitimately trigger these.
PRESERVATION_HINTS = (
    (r"\bglass\b", r"стакл", "glass"),
    (r"\bplastic\b", r"пласт|полиетилен", "plastic"),
    (r"\bpaper\b", r"харти", "paper"),
    (r"\bbatter(?:y|ies)\b", r"батери|акумулатор", "battery"),
    (r"\bchargers?\b", r"полнач|полн[еи]|напојува", "charger"),
    (r"\bempty\b", r"праз", "empty"),
    (r"\bdirty\b", r"валкан|нечист", "dirty"),
    (r"\bwet\b", r"мокр|влаж", "wet"),
    (r"\bgreasy\b", r"масн|мрсн", "greasy"),
    (r"\bunwaxed\b", r"восо|вос[о]?ч", "unwaxed"),
)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def quality_flags(source: str, translated: str) -> list[str]:
    """Mechanical screening only; passing is not a semantic or native review."""
    flags = []
    if not translated.strip():
        flags.append("empty")
    if not re.search(r"[Ѐ-ӿ]", translated):
        flags.append("no_cyrillic")
    if any("Ѐ" <= char <= "ӿ" and char.casefold() not in MACEDONIAN_LETTERS for char in translated):
        flags.append("non_macedonian_cyrillic")
    if normalize_key(source) == normalize_key(translated):
        flags.append("unchanged")
    if len(translated) > max(100, len(source) * 4):
        flags.append("expansion")
    words = translated.casefold().split()
    if any(words[i : i + 3] == words[i + 3 : i + 6] for i in range(len(words) - 5)):
        flags.append("repetition")
    for english, macedonian, term in PRESERVATION_HINTS:
        if re.search(english, source, re.IGNORECASE) and not re.search(
            macedonian, translated, re.IGNORECASE
        ):
            flags.append(f"check_preserved_{term}")
    return flags


@dataclass
class Table:
    path: str
    rows: list[dict[str, Any]]
    text_fields: tuple[str, ...]
    kind: str = "csv"


def collect_sources(root: Path) -> tuple[list[Table], dict[str, str]]:
    """Read canonical snapshots plus every existing prepared/evaluation text table."""
    tables: list[Table] = []
    hashes: dict[str, str] = {}

    def record(path: Path) -> None:
        hashes[str(path.relative_to(root))] = sha256_file(path)

    raw = root / "data/raw"
    hf = raw / "waste_classification_v2"
    manifest_path = hf / "download.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record(manifest_path)
    for name, metadata in sorted(manifest["files"].items()):
        path = hf / metadata["filename"]
        if sha256_file(path) != metadata["sha256"]:
            raise ValueError(f"Source checksum mismatch: {path}")
        rows = read_csv(path)
        for index, row in enumerate(rows):
            row["source_row"] = str(index)
            row["source_split"] = name
        tables.append(Table(f"raw/waste_classification_v2/{path.stem}_mk.csv", rows, ("Phrase",)))
        record(path)

    toronto_path = raw / "toronto_waste_wizard/waste_wizard.json"
    metadata_path = toronto_path.with_name("metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if sha256_file(toronto_path) != metadata["sha256"]:
        raise ValueError(f"Source checksum mismatch: {toronto_path}")
    tables.append(
        Table(
            "raw/toronto_waste_wizard/waste_wizard_mk.json",
            json.loads(toronto_path.read_text(encoding="utf-8")),
            ("item", "instructions", "find_out"),
            "json",
        )
    )
    record(toronto_path)
    record(metadata_path)

    for directory in ("processed", "evaluation"):
        for path in sorted((root / "data" / directory).glob("*.csv")):
            if path.stem.endswith("_mk"):
                continue
            rows = read_csv(path)
            if rows and "text" in rows[0]:
                tables.append(Table(f"{directory}/{path.stem}_mk.csv", rows, ("text",)))
                record(path)
    for relative in (
        "data/mappings/dataset_a_label_mapping.json",
        "data/mappings/needs_manual_review.csv",
        "data/policy/skopje_v1.json",
        "data/evaluation/manual_test_review.csv",
        "data/evaluation/manual_test_mk.csv",
    ):
        record(root / relative)
    return tables, hashes


def source_texts(tables: Sequence[Table]) -> list[str]:
    texts = set()
    for table in tables:
        for row in table.rows:
            for field in table.text_fields:
                values = row[field] if isinstance(row[field], list) else [row[field]]
                for value in values:
                    if not isinstance(value, str):
                        raise ValueError(f"Non-text value in {table.path}: {field}")
                    if value.strip():
                        texts.add(value)
    return sorted(texts, key=lambda text: (len(text), text))


class TranslationCache:
    """Transactional checkpoints keyed by exact English text and pinned run config."""

    def __init__(self, path: Path, configuration: dict[str, Any]):
        # A read-only QA scan on the shared filesystem can hold a short read lock.
        self.connection = sqlite3.connect(path, timeout=60)
        self.connection.execute("CREATE TABLE IF NOT EXISTS config (value TEXT NOT NULL)")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS translations "
            "(sha256 TEXT PRIMARY KEY, source TEXT NOT NULL, "
            "text TEXT NOT NULL, flags TEXT NOT NULL)"
        )
        encoded = json.dumps(configuration, sort_keys=True)
        previous = self.connection.execute("SELECT value FROM config").fetchone()
        if previous and previous[0] != encoded:
            self.connection.close()
            raise ValueError("Translation cache configuration/source checksums changed")
        if previous is None:
            self.connection.execute("INSERT INTO config VALUES (?)", (encoded,))
            self.connection.commit()

    def load(self) -> dict[str, tuple[str, list[str]]]:
        result = {}
        for digest, source, translated, flags in self.connection.execute(
            "SELECT sha256, source, text, flags FROM translations"
        ):
            if digest != text_hash(source):
                raise ValueError("Corrupt translation cache source hash")
            result[source] = (
                translated,
                sorted(set(json.loads(flags) + quality_flags(source, translated))),
            )
        return result

    def save(self, sources: Sequence[str], translations: Sequence[tuple[str, list[str]]]) -> None:
        if len(sources) != len(translations):
            raise ValueError("Translation batch returned a different number of rows")
        with self.connection:
            for source, (translated, flags) in zip(sources, translations, strict=True):
                if not translated.strip():
                    raise ValueError("Translation returned empty text")
                all_flags = sorted(set(flags + quality_flags(source, translated)))
                self.connection.execute(
                    "INSERT INTO translations VALUES (?, ?, ?, ?)",
                    (text_hash(source), source, translated, json.dumps(all_flags)),
                )

    def close(self) -> None:
        self.connection.close()


class NllbTranslator:
    def __init__(self, *, device: str, beams: int, max_new_tokens: int):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, set_seed

        set_seed(42)
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("The requested CUDA translation device is unavailable")
        self.torch = torch
        self.beams = beams
        self.max_new_tokens = max_new_tokens
        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID, revision=MODEL_REVISION, src_lang="eng_Latn", token=False
        )
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_ID,
            revision=MODEL_REVISION,
            token=False,
            dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device)
        self.model.eval()
        self.language_id = self.tokenizer.convert_tokens_to_ids("mkd_Cyrl")
        if self.language_id == self.tokenizer.unk_token_id:
            raise ValueError("Tokenizer lacks Macedonian language token")
        self.metadata = {
            "device": device,
            "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
            "versions": {
                name: importlib.metadata.version(name)
                for name in ("torch", "transformers", "tokenizers", "huggingface-hub")
            },
        }

    def __call__(self, texts: Sequence[str]) -> list[tuple[str, list[str]]]:
        inputs = self.tokenizer(list(texts), return_tensors="pt", padding=True, truncation=False)
        if inputs["input_ids"].shape[1] > 512:
            raise ValueError("Source exceeds 512 tokens; split explicitly, never silently truncate")
        inputs = inputs.to(self.model.device)
        with self.torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                forced_bos_token_id=self.language_id,
                num_beams=self.beams,
                do_sample=False,
                max_new_tokens=self.max_new_tokens,
            )
        decoded = self.tokenizer.batch_decode(generated, skip_special_tokens=True)
        return [
            (
                text.strip(),
                ["generation_limit"]
                if int((tokens != self.tokenizer.pad_token_id).sum()) >= self.max_new_tokens + 1
                else [],
            )
            for text, tokens in zip(decoded, generated, strict=True)
        ]


def translate_tables(
    tables: Sequence[Table], translations: dict[str, tuple[str, list[str]]]
) -> list[Table]:
    exports = []
    for table in tables:
        rows = []
        for index, original in enumerate(table.rows):
            row = dict(original)
            flags = set()
            for field in table.text_fields:
                value = original[field]
                values = value if isinstance(value, list) else [value]
                translated_values = []
                for source in values:
                    translated, issues = translations[source] if source.strip() else (source, [])
                    translated_values.append(translated)
                    flags.update(issues)
                row[field + "_en"] = value
                row[field] = translated_values if isinstance(value, list) else translated_values[0]
            primary = original[table.text_fields[0]]
            row.update(
                source_row=row.get("source_row", str(index)),
                english_text_sha256=text_hash(primary),
                language="mk",
                translation_method="machine_translation_nllb",
                translation_review_status=REVIEW_STATUS,
                translation_qa_flags=";".join(sorted(flags)),
            )
            if "toronto" in table.path:
                row["policy_scope"] = "Toronto source instructions; not Skopje disposal policy"
            rows.append(row)
        exports.append(Table(table.path, rows, table.text_fields, table.kind))
    return exports


def build_experimental_splits(
    rows: Sequence[dict[str, Any]],
    mapping: dict[str, str],
    statuses: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply CURRENT label reviews, pair languages, retain groups, quarantine collisions."""
    eligible = []
    excluded = []
    for original in rows:
        row = dict(original)
        reason = ""
        if row["source"] != "dataset_a" or statuses.get(row["original_label"]) != "approved":
            reason = "local_label_needs_review"
        elif row["target_label"] != mapping.get(row["original_label"]):
            reason = "stale_target_label"
        elif row["translation_qa_flags"]:
            reason = "translation_qa"
        if reason:
            excluded.append({**row, "exclusion_reason": reason})
        else:
            eligible.append(row)

    group_splits: dict[str, set[str]] = defaultdict(set)
    key_splits: dict[str, set[str]] = defaultdict(set)
    key_labels: dict[str, set[str]] = defaultdict(set)
    for row in eligible:
        if row["split"] not in {"train", "validation", "test"} or not row["item_group"]:
            raise ValueError("Missing/invalid inherited split or item group")
        group_splits[row["item_group"]].add(row["split"])
        for text in (row["text"], row["text_en"]):
            key_splits[normalize_key(text)].add(row["split"])
            key_labels[normalize_key(text)].add(row["target_label"])
    if any(len(splits) > 1 for splits in group_splits.values()):
        raise ValueError("An inherited item group crosses train/validation/test splits")
    kept = []
    seen = set()
    for row in eligible:
        keys = [normalize_key(row["text"]), normalize_key(row["text_en"])]
        reason = ""
        if any(len(key_splits[key]) > 1 for key in keys):
            reason = "cross_split_translation_or_source_collision"
        elif any(len(key_labels[key]) > 1 for key in keys):
            reason = "conflicting_translation_or_source_labels"
        elif any(key in seen for key in keys):
            reason = "duplicate_translation_or_source"
        if reason:
            excluded.append({**row, "exclusion_reason": reason})
        else:
            seen.update(keys)
            kept.append({**row, "mapping_status": "approved"})
    return kept, excluded


def export_package(
    root: Path,
    output: Path,
    tables: Sequence[Table],
    translations: dict[str, tuple[str, list[str]]],
) -> dict[str, Any]:
    translated = translate_tables(tables, translations)
    files = {}

    def save(table: Table) -> None:
        path = output / table.path
        if table.kind == "json":
            write_json(path, table.rows)
        else:
            write_csv(path, table.rows, list(table.rows[0]) if table.rows else ("text", "label"))
        files[table.path] = {"rows": len(table.rows), "sha256": sha256_file(path)}

    # Preserve the existing authored probe separately rather than replacing its wording.
    original_manual = read_csv(root / "data/evaluation/manual_test.csv")
    manual = read_csv(root / "data/evaluation/manual_test_mk.csv")
    manual_review = {
        row["text_sha256"]: row for row in read_csv(root / "data/evaluation/manual_test_review.csv")
    }
    english = {text_hash(row["text"]): row for row in original_manual}
    if (
        len(manual) != len(english)
        or {row["english_text_sha256"] for row in manual} != set(english)
        or set(manual_review) != set(english)
    ):
        raise ValueError("Existing Macedonian manual probe is not SHA-linked to the English set")
    for row in manual:
        key = row["english_text_sha256"]
        if row["target_label"] != english[key]["target_label"]:
            raise ValueError("Existing Macedonian manual label differs from English")
        row["text_en"] = english[key]["text"]
        row["source_review_status"] = manual_review[key]["review_status"]
        row["translation_method"] = "existing_agent_authored"
        row["evaluation_label"] = (
            row["target_label"] if row["source_review_status"] == "source_supported" else ""
        )
    save(Table("evaluation/manual_test_existing_mk.csv", manual, ("text",)))

    from smart_recycling.data.review import load_mapping_review

    mapping = json.loads(
        (root / "data/mappings/dataset_a_label_mapping.json").read_text(encoding="utf-8")
    )
    statuses = load_mapping_review(root / "data/mappings/needs_manual_review.csv", mapping)
    for table in translated:
        for row in table.rows:
            if "waste_classification_v2" in table.path:
                label = row["Class"].strip()
                row["proposed_target_label"] = mapping.get(label, "")
                row["current_mapping_status"] = statuses.get(label, "needs_review")
            elif "processed/" in table.path:
                row["current_mapping_status"] = (
                    statuses.get(row["original_label"], "needs_review")
                    if row.get("source") == "dataset_a"
                    and row["target_label"] == mapping.get(row["original_label"])
                    else "needs_review"
                )
            elif table.path == "evaluation/manual_test_mk.csv":
                review = manual_review[row["english_text_sha256"]]
                row["source_review_status"] = review["review_status"]
                row["evaluation_label"] = (
                    row["target_label"] if review["review_status"] == "source_supported" else ""
                )
        save(table)
    combined = next(
        table for table in translated if table.path == "processed/combined_with_splits_mk.csv"
    )
    kept, excluded = build_experimental_splits(combined.rows, mapping, statuses)
    save(Table("experimental/paired.csv", kept, ("text",)))
    save(Table("experimental/excluded.csv", excluded, ("text",)))
    counts = {}
    for split in ("train", "validation", "test"):
        subset = [row for row in kept if row["split"] == split]
        counts[split] = dict(Counter(row["target_label"] for row in subset))
        for language in ("en", "mk", "bilingual"):
            rows = []
            for row in subset:
                for lang in ("en", "mk") if language == "bilingual" else (language,):
                    rows.append(
                        {
                            "id": row["id"] + "::" + lang,
                            "pair_id": row["id"],
                            "text": row["text_en"] if lang == "en" else row["text"],
                            "label": row["target_label"],
                            "language": lang,
                            "item_group": row["item_group"],
                            "split": split,
                            "translation_review_status": REVIEW_STATUS
                            if lang == "mk"
                            else "original",
                        }
                    )
            save(Table(f"experimental/{split}_{language}.csv", rows, ("text",)))
    qa = [
        {"text_en": source, "text_mk": translated_text, "flags": ";".join(flags)}
        for source, (translated_text, flags) in translations.items()
        if flags
    ]
    write_csv(output / "translation_qa.csv", qa, ("text_en", "text_mk", "flags"))
    files["translation_qa.csv"] = {
        "rows": len(qa),
        "sha256": sha256_file(output / "translation_qa.csv"),
    }
    return {
        "outputs": files,
        "experimental_class_counts": counts,
        "experimental_missing_supported_labels": {
            split: sorted(
                {mapping[label] for label, status in statuses.items() if status == "approved"}
                - set(class_counts)
            )
            for split, class_counts in counts.items()
        },
        "experimental_exclusions": dict(Counter(row["exclusion_reason"] for row in excluded)),
        "flagged_unique_translations": len(qa),
    }


def run_translation(
    *,
    root: Path,
    output: Path,
    device: str = "cuda",
    batch_size: int = 32,
    beams: int = 4,
    max_new_tokens: int = 256,
    resume: bool = False,
    translator_factory: Callable[..., Any] = NllbTranslator,
) -> dict[str, Any]:
    if min(batch_size, beams, max_new_tokens) < 1:
        raise ValueError("Batch size, beams and generation limit must be positive")
    if output.exists() and not resume:
        raise FileExistsError("Output already exists; use --resume or a new output directory")
    tables, hashes = collect_sources(root)
    texts = source_texts(tables)
    configuration = {
        "format_version": FORMAT_VERSION,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "source_language": "eng_Latn",
        "target_language": "mkd_Cyrl",
        "seed": 42,
        "beams": beams,
        "batch_size": batch_size,
        "max_new_tokens": max_new_tokens,
        "device": device,
        "source_hashes": hashes,
    }
    output.mkdir(parents=True, exist_ok=True)
    cache = TranslationCache(output / "translations.sqlite3", configuration)
    started = time.monotonic()
    try:
        translations = cache.load()
        pending = [text for text in texts if text not in translations]
        print(
            f"Unique texts: {len(texts)}; cached: {len(translations)}; pending: {len(pending)}",
            flush=True,
        )
        translator = None
        if pending:
            translator = translator_factory(
                device=device, beams=beams, max_new_tokens=max_new_tokens
            )
            write_json(output / "translator_runtime.json", translator.metadata)
        for index in range(0, len(pending), batch_size):
            batch = pending[index : index + batch_size]
            cache.save(batch, translator(batch))
            if index % (batch_size * 10) == 0 or index + batch_size >= len(pending):
                print(
                    f"Translated {min(index + batch_size, len(pending))}/{len(pending)} "
                    f"pending texts in {time.monotonic() - started:.1f}s",
                    flush=True,
                )
        translations = cache.load()
        report = export_package(root, output, tables, translations)
        # Verify sources again before marking the package complete.
        for relative, expected in hashes.items():
            if sha256_file(root / relative) != expected:
                raise ValueError(f"Source changed during translation: {relative}")
        manifest = {
            **configuration,
            **report,
            "status": "complete",
            "unique_translations": len(translations),
            "runtime": json.loads((output / "translator_runtime.json").read_text(encoding="utf-8")),
            "export_code_sha256": sha256_file(Path(__file__)),
            "translation_review_status": REVIEW_STATUS,
            "limitations": [
                "Machine translations have no native-speaker sign-off.",
                "Raw/processed mirrors retain source labels, including stale/unreviewed mappings.",
                "Only experimental exports apply the current local label review.",
                "Inherited grouped splits do not cover every class in every split.",
                "Translated tests are translation probes, not independent Macedonian field tests.",
                "Official raw source splits are not leakage-safe item-family evaluation splits.",
                "Toronto instructions describe Toronto policy, not Skopje acceptance.",
                "NLLB model license: CC-BY-NC-4.0; source dataset terms remain unresolved.",
            ],
        }
        write_json(output / "manifest.json", manifest)
        return manifest
    finally:
        cache.close()
