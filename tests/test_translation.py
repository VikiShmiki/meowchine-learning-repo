import shutil
from pathlib import Path

import pytest

from smart_recycling.data.common import sha256_file, write_json
from smart_recycling.data.translation import (
    REVIEW_STATUS,
    Table,
    TranslationCache,
    build_experimental_splits,
    collect_sources,
    quality_flags,
    read_csv,
    run_translation,
    text_hash,
    translate_tables,
    write_csv,
)

ROOT = Path(__file__).resolve().parents[1]


def paired_row(**changes):
    return {
        "id": "one",
        "text": "стаклено шише",
        "text_en": "glass bottle",
        "target_label": "glass",
        "source": "dataset_a",
        "original_label": "GLASS BOTTLE",
        "mapping_status": "approved",
        "item_group": "bottle",
        "split": "train",
        "translation_qa_flags": "",
        "translation_review_status": REVIEW_STATUS,
        **changes,
    }


def test_mirrors_retain_source_columns_and_translate_instruction_arrays():
    source = {
        "id": "A001",
        "item": "bottle",
        "category": "Blue Bin",
        "instructions": ["Empty first.", ""],
        "find_out": "",
        "popular": False,
    }
    table = Table("raw/toronto.json", [source], ("item", "instructions", "find_out"), "json")
    translated = translate_tables(
        [table], {"bottle": ("шише", []), "Empty first.": ("Прво испразнете го.", [])}
    )[0].rows[0]
    assert translated["item"] == "шише"
    assert translated["item_en"] == source["item"]
    assert translated["instructions"] == ["Прво испразнете го.", ""]
    assert translated["instructions_en"] == source["instructions"]
    assert translated["popular"] is False
    assert translated["category"] == "Blue Bin"
    assert translated["english_text_sha256"] == text_hash("bottle")
    assert translated["translation_review_status"] == REVIEW_STATUS
    assert "Toronto" in translated["policy_scope"]
    assert source["item"] == "bottle"


def test_split_export_uses_current_reviews_not_stale_automatic_approvals():
    rows = [
        paired_row(),
        paired_row(id="two", source="dataset_b_augmented", mapping_status="auto_approved"),
        paired_row(id="three", original_label="PAPER CUP", target_label="paper_tetrapak"),
        paired_row(id="four", target_label="general"),
        paired_row(id="five", translation_qa_flags="no_cyrillic"),
    ]
    kept, excluded = build_experimental_splits(
        rows,
        {"GLASS BOTTLE": "glass", "PAPER CUP": "paper_tetrapak"},
        {"GLASS BOTTLE": "approved", "PAPER CUP": "needs_review"},
    )
    assert [row["id"] for row in kept] == ["one"]
    assert [row["exclusion_reason"] for row in excluded] == [
        "local_label_needs_review",
        "local_label_needs_review",
        "stale_target_label",
        "translation_qa",
    ]


@pytest.mark.parametrize("field", ["text", "text_en"])
def test_translation_or_english_collision_quarantines_both_sides(field):
    first = paired_row()
    second = paired_row(
        id="two", text="стаклена тегла", text_en="glass jar", split="test", item_group="jar"
    )
    second[field] = first[field]
    kept, excluded = build_experimental_splits(
        [first, second], {"GLASS BOTTLE": "glass"}, {"GLASS BOTTLE": "approved"}
    )
    assert not kept
    assert len(excluded) == 2
    assert {row["exclusion_reason"] for row in excluded} == {
        "cross_split_translation_or_source_collision"
    }


def test_inherited_item_group_may_not_cross_splits():
    with pytest.raises(ValueError, match="item group crosses"):
        build_experimental_splits(
            [paired_row(), paired_row(id="two", split="test", text="тегла", text_en="jar")],
            {"GLASS BOTTLE": "glass"},
            {"GLASS BOTTLE": "approved"},
        )


def test_conflicting_translated_labels_are_excluded():
    kept, excluded = build_experimental_splits(
        [
            paired_row(),
            paired_row(id="two", original_label="PLASTIC BOTTLE", target_label="plastic_metal"),
        ],
        {"GLASS BOTTLE": "glass", "PLASTIC BOTTLE": "plastic_metal"},
        {"GLASS BOTTLE": "approved", "PLASTIC BOTTLE": "approved"},
    )
    assert not kept
    assert len(excluded) == 2
    assert all(
        row["exclusion_reason"] == "conflicting_translation_or_source_labels" for row in excluded
    )


def test_duplicate_translations_in_same_split_keep_one_pair():
    kept, excluded = build_experimental_splits(
        [paired_row(), paired_row(id="two", text_en="a glass bottle")],
        {"GLASS BOTTLE": "glass"},
        {"GLASS BOTTLE": "approved"},
    )
    assert len(kept) == len(excluded) == 1
    assert excluded[0]["exclusion_reason"] == "duplicate_translation_or_source"


def test_cache_resumes_exact_sources_and_rejects_changed_configuration(tmp_path):
    path = tmp_path / "cache.sqlite3"
    cache = TranslationCache(path, {"revision": "one"})
    cache.save(["glass"], [("стакло", [])])
    cache.close()
    resumed = TranslationCache(path, {"revision": "one"})
    assert resumed.load() == {"glass": ("стакло", [])}
    with pytest.raises(ValueError, match="different number"):
        resumed.save(["jar"], [])
    with pytest.raises(ValueError, match="empty"):
        resumed.save(["jar"], [("", [])])
    resumed.close()
    with pytest.raises(ValueError, match="configuration/source checksums changed"):
        TranslationCache(path, {"revision": "two"})


def test_quality_checks_flag_english_and_repetitive_output():
    assert quality_flags("bottle", "bottle") == ["no_cyrillic", "unchanged"]
    assert quality_flags("bottle", "шише") == []
    assert "non_macedonian_cyrillic" in quality_flags("charger", "зарядник")
    assert "check_preserved_glass" in quality_flags("glass bottle", "шише")
    assert "check_preserved_charger" in quality_flags("battery charger", "батерија")
    assert "repetition" in quality_flags("a glass bottle", "ова е шише ова е шише")


@pytest.fixture
def source_root(tmp_path):
    root = tmp_path / "repo"
    hf = root / "data/raw/waste_classification_v2"
    files = {}
    for split, text in (("train", "glass bottle"), ("test", "jar"), ("unseen_phrases", "paper")):
        path = hf / f"{split}.csv"
        rows = [{"": "0", "Phrase": text, "Class": "GLASS BOTTLE", "Class_index": "3.0"}]
        write_csv(path, rows, list(rows[0]))
        files[split] = {"filename": path.name, "sha256": sha256_file(path)}
    write_json(hf / "download.json", {"files": files})
    toronto = root / "data/raw/toronto_waste_wizard/waste_wizard.json"
    write_json(
        toronto,
        [{"item": "jar", "category": "Blue Bin", "instructions": ["Empty first."], "find_out": ""}],
    )
    write_json(toronto.with_name("metadata.json"), {"sha256": sha256_file(toronto)})
    rows = [paired_row()]
    # The input is English; translation adds source text and metadata later.
    for row in rows:
        row["text"] = row.pop("text_en")
        row.pop("translation_qa_flags")
        row.pop("translation_review_status")
    write_csv(root / "data/processed/combined_with_splits.csv", rows, list(rows[0]))
    for relative in (
        "data/mappings/dataset_a_label_mapping.json",
        "data/mappings/needs_manual_review.csv",
        "data/policy/skopje_v1.json",
        "data/evaluation/manual_test.csv",
        "data/evaluation/manual_test_review.csv",
        "data/evaluation/manual_test_mk.csv",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return root


def test_complete_package_retains_rows_pairs_holds_and_resumes_without_model(source_root, tmp_path):
    class FakeTranslator:
        metadata = {"versions": {"fake": "1"}}

        def __init__(self, **kwargs):
            pass

        def __call__(self, texts):
            return [
                ("стаклено шише" if text == "glass bottle" else "превод " + text, [])
                for text in texts
            ]

    output = tmp_path / "output"
    before = {str(p): sha256_file(p) for p in source_root.rglob("*") if p.is_file()}
    report = run_translation(
        root=source_root, output=output, translator_factory=FakeTranslator, batch_size=8
    )
    assert report["status"] == "complete"
    raw = read_csv(output / "raw/waste_classification_v2/train_mk.csv")
    assert len(raw) == 1
    assert raw[0]["Phrase_en"] == "glass bottle"
    assert raw[0][""] == "0"
    en = read_csv(output / "experimental/train_en.csv")
    mk = read_csv(output / "experimental/train_mk.csv")
    assert en[0]["pair_id"] == mk[0]["pair_id"]
    assert en[0]["split"] == mk[0]["split"] == "train"
    assert en[0]["item_group"] == mk[0]["item_group"]
    assert len(read_csv(output / "experimental/train_bilingual.csv")) == 2
    assert (
        sum(
            row["evaluation_label"] != ""
            for row in read_csv(output / "evaluation/manual_test_existing_mk.csv")
        )
        == 59
    )
    assert {str(p): sha256_file(p) for p in source_root.rglob("*") if p.is_file()} == before
    assert (
        sum(
            row["evaluation_label"] != ""
            for row in read_csv(output / "evaluation/manual_test_mk.csv")
        )
        == 59
    )

    def no_model(**kwargs):
        raise AssertionError("A complete cache must not load the translation model")

    resumed = run_translation(
        root=source_root, output=output, resume=True, translator_factory=no_model, batch_size=8
    )
    assert resumed == report
    with pytest.raises(FileExistsError, match="already exists"):
        run_translation(root=source_root, output=output, translator_factory=no_model)
    for path, info in report["outputs"].items():
        assert sha256_file(output / path) == info["sha256"]


def test_tampered_source_is_rejected_before_translation(source_root):
    path = source_root / "data/raw/waste_classification_v2/train.csv"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        collect_sources(source_root)


def test_interrupted_translation_resumes_only_unfinished_batches(source_root, tmp_path):
    attempted = []

    class InterruptedTranslator:
        metadata = {"versions": {"fake": "1"}}

        def __init__(self, **kwargs):
            pass

        def __call__(self, texts):
            attempted.append(list(texts))
            if len(attempted) == 2:
                raise RuntimeError("interrupted")
            return [("превод " + text, []) for text in texts]

    output = tmp_path / "output"
    with pytest.raises(RuntimeError, match="interrupted"):
        run_translation(
            root=source_root, output=output, translator_factory=InterruptedTranslator, batch_size=8
        )
    assert not (output / "manifest.json").exists()
    already_translated = set(attempted[0])
    remaining = []

    class ResumedTranslator(InterruptedTranslator):
        def __call__(self, texts):
            assert not already_translated.intersection(texts)
            remaining.extend(texts)
            return [("превод " + text, []) for text in texts]

    report = run_translation(
        root=source_root,
        output=output,
        resume=True,
        translator_factory=ResumedTranslator,
        batch_size=8,
    )
    assert report["status"] == "complete"
    assert report["unique_translations"] == len(already_translated) + len(remaining)
