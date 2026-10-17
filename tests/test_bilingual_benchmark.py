import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from smart_recycling.data import bilingual_benchmark as experiment
from smart_recycling.data.benchmark import CLASSES
from smart_recycling.data.common import sha256_file, write_json


@pytest.fixture
def paired_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(experiment, "EXPECTED_SPLITS", {"train": 4, "validation": 2, "test": 2})
    labels = {
        "train": CLASSES,
        "validation": ("plastic_metal", "paper_tetrapak"),
        "test": ("glass", "special_unsupported"),
    }
    manifest = {
        "status": "complete",
        "seed": 42,
        "flagged_unique_translations": 1,
        "translation_review_status": "needs_native_review",
        "outputs": {},
    }
    for split, categories in labels.items():
        for language in ("en", "mk"):
            rows = [
                {
                    "id": f"{split}-{index}::{language}",
                    "pair_id": f"{split}-{index}",
                    "text": f"{split} example {index} {language}",
                    "label": label,
                    "language": language,
                    "item_group": f"{split}-{index}",
                    "split": split,
                    "translation_review_status": (
                        "original" if language == "en" else "needs_native_review"
                    ),
                }
                for index, label in enumerate(categories)
            ]
            relative = f"experimental/{split}_{language}.csv"
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_csv(path, index=False)
            manifest["outputs"][relative] = {"sha256": sha256_file(path)}
    write_json(tmp_path / "manifest.json", manifest)
    return tmp_path


def test_paired_data_contains_same_labels_and_source_limited_probes(paired_package: Path):
    training, evaluations, provenance = experiment.load_paired_benchmark_data(paired_package)

    assert len(training["en"]) == len(training["mk"]) == 4
    assert set(training["en"]["label"]) == set(CLASSES)
    assert provenance["manual_supported_examples"] == 59
    assert provenance["manual_held_examples"] == 41
    for language in ("en", "mk"):
        by_name = {item.name: item for item in evaluations[language]}
        assert len(by_name[f"manual_{language}"].texts) == 100
        assert len(by_name[f"clothing_probe_{language}"].texts) == 5
        assert len(by_name[f"electronics_probe_{language}"].texts) == 9
        assert set(by_name[f"clothing_probe_{language}"].labels) == {"special_unsupported"}


def test_changed_translation_is_rejected_before_training(paired_package: Path):
    path = paired_package / "experimental/train_mk.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "text"] = "changed translation"
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="checksum mismatch"):
        experiment.load_paired_benchmark_data(paired_package)


def test_cross_split_item_group_is_rejected_even_when_texts_differ(paired_package: Path):
    manifest_path = paired_package / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for language in ("en", "mk"):
        relative = f"experimental/test_{language}.csv"
        path = paired_package / relative
        frame = pd.read_csv(path)
        frame.loc[0, "item_group"] = "train-0"
        frame.to_csv(path, index=False)
        manifest["outputs"][relative]["sha256"] = sha256_file(path)
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="item groups leak across"):
        experiment.load_paired_benchmark_data(paired_package)


def test_six_fits_use_language_specific_frozen_encoders_and_persist_summary(
    paired_package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    data = experiment.load_paired_benchmark_data(paired_package)
    monkeypatch.setattr(experiment, "load_paired_benchmark_data", lambda: data)
    calls = []

    def fake_method(train, evaluations, artifact_dir, **kwargs):
        calls.append((evaluations[1].name, kwargs))
        return {
            "model": "fake",
            "training_seconds": 0.1,
            "evaluation_seconds": 0.2,
            "evaluations": {
                item.name: {
                    "supported_examples": sum(bool(label) for label in item.labels),
                    "closed_set_supported_accuracy": 0.5,
                    "closed_set_supported_macro_f1": 0.5,
                }
                for item in evaluations
            },
        }

    monkeypatch.setattr(experiment, "run_tfidf", fake_method)
    monkeypatch.setattr(experiment, "run_frozen_minilm", fake_method)
    monkeypatch.setattr(experiment, "run_lora_multilingual_minilm", fake_method)
    report = experiment.run_bilingual_benchmark(
        results_dir=tmp_path / "results", artifacts_dir=tmp_path / "artifacts"
    )

    assert len(calls) == len(report["methods"]) == 6
    assert all(options["classes"] == CLASSES for _, options in calls)
    assert all(options["seed"] == 42 for _, options in calls)
    assert [name for name, _ in calls] == [
        "manual_en",
        "manual_en",
        "manual_en",
        "manual_mk",
        "manual_mk",
        "manual_mk",
    ]
    assert "encoder_id" not in calls[1][1]
    assert calls[4][1]["encoder_id"] == experiment.MULTILINGUAL_MINILM_ID
    assert calls[2][1]["epochs"] == calls[5][1]["epochs"] == 3
    assert len(pd.read_csv(tmp_path / "results/bilingual_seed42_summary.csv")) == 36
    with pytest.raises(FileExistsError, match="already exists"):
        experiment.run_bilingual_benchmark(
            results_dir=tmp_path / "results", artifacts_dir=tmp_path / "artifacts"
        )


@pytest.fixture
def object_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    counts = {"train": 6, "validation": 2, "test": 2}
    monkeypatch.setattr(experiment, "EXPECTED_V2_SPLITS", counts)
    classes = experiment.OBJECT_CLASSES
    manifest = {
        "version": "object-classes-v2",
        "status": "complete",
        "seed": 42,
        "labels": [*classes, "general"],
        "inputs": {},
        "outputs": {},
        "experimental_class_counts": {},
        "missing_labels": {},
    }

    def save(relative, rows):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(path, index=False)
        manifest["outputs"][relative] = {"sha256": sha256_file(path), "rows": len(rows)}

    for split, count in counts.items():
        labels = classes if split == "train" else ("clothes", "electronics")
        manifest["experimental_class_counts"][split] = {label: 1 for label in labels}
        for lang in ("en", "mk"):
            save(
                f"experimental/{split}_{lang}.csv",
                [
                    {
                        "id": f"{split}-{index}-{lang}",
                        "pair_id": f"{split}-{index}",
                        "text": f"{split} source {index} {lang}",
                        "label": labels[index],
                        "language": lang,
                        "item_group": f"{split}-{index}",
                        "split": split,
                        "english_text_sha256": hashlib.sha256(
                            f"{split} source {index} en".encode()
                        ).hexdigest(),
                        "translation_review_status": "original"
                        if lang == "en"
                        else "needs_native_review",
                    }
                    for index in range(count)
                ],
            )
    for name in ("manual_test_existing", "guidance_validation_v3", "object_probe"):
        for lang in ("en", "mk"):
            save(
                f"evaluation/{name}_{lang}.csv",
                [
                    {
                        "id": f"{name}-{index}",
                        "text": f"{name} probe {index} {lang}",
                        "text_en": f"{name} probe {index} en",
                        "label": label,
                        "evaluation_label": label,
                        "target_label": label,
                        "translation_review_status": "original"
                        if lang == "en"
                        else "needs_native_review",
                    }
                    for index, label in enumerate(("clothes", "electronics", "general"))
                ],
            )
    write_json(tmp_path / "manifest.json", manifest)
    return tmp_path


def test_v2_loader_uses_new_labels_and_does_not_evaluate_untrained_general(object_package):
    training, evaluations, provenance = experiment.load_paired_benchmark_data(object_package)
    assert set(training["en"]["label"]) == set(experiment.OBJECT_CLASSES)
    assert provenance["classes"] == list(experiment.OBJECT_CLASSES)
    assert provenance["dataset_version"] == "object-classes-v2"
    assert evaluations["en"][1].labels == ("clothes", "electronics", "")
    assert [item.labels for item in evaluations["en"]] == [
        item.labels for item in evaluations["mk"]
    ]
    assert evaluations["mk"][-2].labels == ("clothes",)
    assert evaluations["mk"][-1].labels == ("electronics",)


@pytest.mark.parametrize(
    "corruption,match",
    [("checksum", "checksum mismatch"), ("pair", "pairs differ"), ("group", "leak across")],
)
def test_v2_loader_rejects_corrupted_or_leaking_inputs(object_package, corruption, match):
    manifest_path = object_package / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for lang in ("mk",) if corruption in {"checksum", "pair"} else ("en", "mk"):
        relative = f"experimental/test_{lang}.csv"
        frame = pd.read_csv(object_package / relative)
        field, value = {
            "checksum": ("text", "changed"),
            "pair": ("pair_id", "unpaired"),
            "group": ("item_group", "train-0"),
        }[corruption]
        frame.loc[0, field] = value
        frame.to_csv(object_package / relative, index=False)
        if corruption != "checksum":
            manifest["outputs"][relative]["sha256"] = sha256_file(object_package / relative)
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match=match):
        experiment.load_paired_benchmark_data(object_package)


def test_new_seed_propagates_to_all_six_fits_and_uses_new_paths(
    object_package: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    calls = []

    def fake_method(train, evaluations, artifact_dir, **kwargs):
        calls.append(kwargs)
        return {
            "model": "fake",
            "training_seconds": 0.1,
            "evaluation_seconds": 0.2,
            "evaluations": {
                item.name: {
                    "supported_examples": sum(bool(label) for label in item.labels),
                    "closed_set_supported_accuracy": 0.5,
                    "closed_set_supported_macro_f1": 0.5,
                }
                for item in evaluations
            },
        }

    monkeypatch.setattr(experiment, "run_tfidf", fake_method)
    monkeypatch.setattr(experiment, "run_frozen_minilm", fake_method)
    monkeypatch.setattr(experiment, "run_lora_multilingual_minilm", fake_method)
    report = experiment.run_bilingual_benchmark(
        results_dir=tmp_path / "results43",
        artifacts_dir=tmp_path / "models43",
        data_dir=object_package,
        seed=43,
    )
    assert report["random_seed"] == 43
    assert len(calls) == 6
    assert all(
        call["seed"] == 43 and call["classes"] == experiment.OBJECT_CLASSES for call in calls
    )
    assert (tmp_path / "results43/bilingual_seed43.json").is_file()
    assert len(pd.read_csv(tmp_path / "results43/bilingual_seed43_summary.csv")) == 42
    assert not (tmp_path / "results43/bilingual_seed42.json").exists()
    with pytest.raises(FileExistsError):
        experiment.run_bilingual_benchmark(
            results_dir=tmp_path / "results43",
            artifacts_dir=tmp_path / "models43",
            data_dir=object_package,
            seed=43,
        )
