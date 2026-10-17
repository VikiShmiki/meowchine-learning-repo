"""Six development-only seed-42 fits on the paired English/Macedonian exports."""

import hashlib
import json
import platform
import sys
import time
from collections import Counter
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import pandas as pd
import sklearn

from smart_recycling.data.benchmark import (
    CLASSES,
    MULTILINGUAL_MINILM_ID,
    MULTILINGUAL_MINILM_REVISION,
    EvaluationSet,
    _fixture_sets,
    _manual_macedonian_with_holds,
    _seed_everything,
    run_frozen_minilm,
    run_lora_multilingual_minilm,
    run_tfidf,
)
from smart_recycling.data.common import normalize_key, sha256_file, write_json
from smart_recycling.data.constants import (
    ARTIFACTS_DIR,
    DATA_DIR,
    EVALUATION_DIR,
    RANDOM_SEED,
    RESULTS_DIR,
)
from smart_recycling.data.minilm import load_manual_with_holds

DATASET_DIR = DATA_DIR / "processed" / "bilingual_mk_v1"
EXPECTED_SPLITS = {"train": 2917, "validation": 1093, "test": 1324}
EXPECTED_V2_SPLITS = {"train": 3052, "validation": 1116, "test": 1346}
OBJECT_CLASSES = (*CLASSES, "clothes", "electronics")


def validate_source_inputs(manifest: dict, source_root: Path | None = None) -> None:
    """Relocate an immutable source bundle without weakening its checksum checks."""
    for source_path, fingerprint in manifest["inputs"].items():
        path = Path(source_path)
        if source_root is not None:
            # Manifest paths describe the source machine, not the current host.
            flavor = PureWindowsPath if PureWindowsPath(source_path).drive else PurePosixPath
            original = flavor(source_path)
            if original.is_absolute():
                original_root = flavor(manifest["source_package"]).parents[2]
                original = original.relative_to(original_root)
            if original.root or original.drive or ".." in original.parts:
                raise ValueError("Dataset source path escapes its source root")
            path = source_root.joinpath(*original.parts)
            if not path.resolve().is_relative_to(source_root.resolve()):
                raise ValueError("Dataset source symlink escapes its source root")
        if sha256_file(path) != fingerprint:
            raise ValueError(f"Dataset source checksum mismatch: {source_path}")


def load_object_benchmark_data(
    data_dir: Path,
    *,
    source_root: Path | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, tuple[EvaluationSet, ...]], dict[str, Any]]:
    """Validate v2 pairing/provenance and use object labels, not old policy labels."""
    manifest_path = data_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("version") != "object-classes-v2"
        or manifest.get("status") != "complete"
        or manifest.get("seed") != RANDOM_SEED
    ):
        raise ValueError("Incorrect/incomplete object-class dataset version or seed")
    if set(manifest["labels"]) != set(OBJECT_CLASSES) | {"general"}:
        raise ValueError("Unexpected v2 label taxonomy")
    hashes = {"manifest.json": sha256_file(manifest_path)}
    validate_source_inputs(manifest, source_root)

    def read_table(relative: str) -> pd.DataFrame:
        path = data_dir / relative
        fingerprint = sha256_file(path)
        metadata = manifest["outputs"][relative]
        if fingerprint != metadata["sha256"]:
            raise ValueError(f"Dataset table checksum mismatch: {relative}")
        frame = pd.read_csv(path, dtype=str).fillna("")
        if len(frame) != metadata["rows"]:
            raise ValueError(f"Dataset row count mismatch: {relative}")
        hashes[relative] = fingerprint
        return frame

    frames, keys, groups, pair_ids = {}, {}, {}, {}
    for split, expected in EXPECTED_V2_SPLITS.items():
        frames[split], keys[split], groups[split], pair_ids[split] = {}, set(), set(), set()
        for language in ("en", "mk"):
            frame = read_table(f"experimental/{split}_{language}.csv")
            required = {
                "id",
                "pair_id",
                "text",
                "label",
                "language",
                "item_group",
                "split",
                "english_text_sha256",
                "translation_review_status",
            }
            if not required.issubset(frame) or len(frame) != expected:
                raise ValueError(f"Invalid v2 split schema or size: {split}/{language}")
            if (
                frame["id"].duplicated().any()
                or frame["pair_id"].duplicated().any()
                or frame[["id", "pair_id", "text", "item_group"]].eq("").any().any()
                or not frame["language"].eq(language).all()
                or not frame["split"].eq(split).all()
                or not frame["translation_review_status"]
                .eq("original" if language == "en" else "needs_native_review")
                .all()
                or set(frame["label"]) - set(OBJECT_CLASSES)
                or dict(Counter(frame["label"])) != manifest["experimental_class_counts"][split]
            ):
                raise ValueError(f"Invalid v2 split rows or labels: {split}/{language}")
            frames[split][language] = frame
            keys[split].update(frame["text"].map(normalize_key))
            groups[split].update(frame["item_group"])
            pair_ids[split].update(frame["pair_id"])
        en, mk = frames[split]["en"], frames[split]["mk"]
        columns = ["pair_id", "label", "item_group", "english_text_sha256"]
        if not en[columns].equals(mk[columns]) or not en["english_text_sha256"].equals(
            en["text"].map(lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest())
        ):
            raise ValueError(f"English/Macedonian v2 pairs differ in {split}")
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if (
            keys[left] & keys[right]
            or groups[left] & groups[right]
            or pair_ids[left] & pair_ids[right]
        ):
            raise ValueError(f"Text, groups or pair IDs leak across {left}/{right}")
    if set(frames["train"]["en"]["label"]) != set(OBJECT_CLASSES):
        raise ValueError("v2 training must contain all six supported classes")

    evaluations, eval_frames, eval_scope = {}, {}, {}
    for language in ("en", "mk"):
        tables = {
            "manual": read_table(f"evaluation/manual_test_existing_{language}.csv"),
            "guidance_v3": read_table(f"evaluation/guidance_validation_v3_{language}.csv"),
            "object_probe": read_table(f"evaluation/object_probe_{language}.csv"),
        }
        eval_frames[language] = tables
        output = []
        for name, frame, label_column in (
            ("test", frames["test"][language], "label"),
            ("manual", tables["manual"], "evaluation_label"),
            ("guidance_v3", tables["guidance_v3"], "target_label"),
            ("validation", frames["validation"][language], "label"),
            ("object_probe", tables["object_probe"], "label"),
        ):
            labels = tuple(
                label if label in OBJECT_CLASSES else "" for label in frame[label_column]
            )
            if set(frame[label_column]) - set(manifest["labels"]) - {""}:
                raise ValueError(f"Unknown evaluation labels: {name}/{language}")
            scope = (
                "v2 grouped split; report missing class support"
                if name in {"test", "validation"}
                else "v2 object-label development probe; policy holds do not define identity; "
                "untrained general and unresolved labels excluded; no native-language review"
            )
            output.append(
                EvaluationSet(
                    f"{name}_{language}", tuple(frame["text"]), labels, scope, OBJECT_CLASSES
                )
            )
        for name, label in (("clothing", "clothes"), ("electronics", "electronics")):
            subset = tables["object_probe"].loc[tables["object_probe"]["label"].eq(label)]
            output.append(
                EvaluationSet(
                    f"{name}_probe_{language}",
                    tuple(subset["text"]),
                    tuple(subset["label"]),
                    "development-only object diagnostic",
                    OBJECT_CLASSES,
                )
            )
        if keys["train"] & {normalize_key(text) for item in output for text in item.texts}:
            raise ValueError(f"Exact training/evaluation overlap for {language}")
        evaluations[language] = tuple(output)
        eval_scope[language] = {
            item.name: {
                "examples": len(item.texts),
                "supported_examples": sum(bool(x) for x in item.labels),
                "held_examples": sum(not x for x in item.labels),
                "scope": item.scope,
                "class_counts": dict(Counter(label for label in item.labels if label)),
            }
            for item in output
        }
    for name in eval_frames["en"]:
        en, mk = eval_frames["en"][name], eval_frames["mk"][name]
        if (
            en["text"].tolist() != mk["text_en"].tolist()
            or en["label"].tolist() != mk["label"].tolist()
            or not mk["translation_review_status"].eq("needs_native_review").all()
        ):
            raise ValueError(f"Evaluation language pairs differ: {name}")
    if [item.labels for item in evaluations["en"]] != [item.labels for item in evaluations["mk"]]:
        raise ValueError("English/Macedonian evaluation labels differ")
    return (
        frames["train"],
        evaluations,
        {
            "dataset_dir": str(data_dir),
            "dataset_version": manifest["version"],
            "classes": list(OBJECT_CLASSES),
            "untrained_labels": ["general"],
            "input_sha256": hashes,
            "training_examples_per_language": len(frames["train"]["en"]),
            "training_class_counts": manifest["experimental_class_counts"]["train"],
            "split_class_counts": manifest["experimental_class_counts"],
            "missing_labels": manifest["missing_labels"],
            "evaluations": eval_scope,
            "translation_review_status": "needs_native_review",
        },
    )


def load_paired_benchmark_data(
    data_dir: Path = DATASET_DIR,
    *,
    source_root: Path | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, tuple[EvaluationSet, ...]], dict[str, Any]]:
    """Verify source fingerprints and pairing before fitting any method."""
    manifest_path = data_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") == "object-classes-v2":
        return load_object_benchmark_data(data_dir, source_root=source_root)
    if manifest.get("status") != "complete" or manifest.get("seed") != RANDOM_SEED:
        raise ValueError("Macedonian translation package is incomplete or has the wrong seed")
    frames: dict[str, dict[str, pd.DataFrame]] = {}
    hashes = {"manifest.json": sha256_file(manifest_path)}
    keys_by_split: dict[str, set[str]] = {}
    groups_by_split: dict[str, set[str]] = {}
    for split, expected_count in EXPECTED_SPLITS.items():
        frames[split] = {}
        keys_by_split[split] = set()
        groups_by_split[split] = set()
        for language in ("en", "mk"):
            relative = f"experimental/{split}_{language}.csv"
            path = data_dir / relative
            fingerprint = sha256_file(path)
            if manifest["outputs"][relative]["sha256"] != fingerprint:
                raise ValueError(f"Translated dataset checksum mismatch: {relative}")
            frame = pd.read_csv(path, dtype=str).fillna("")
            required = {
                "id",
                "pair_id",
                "text",
                "label",
                "language",
                "item_group",
                "split",
                "translation_review_status",
            }
            if not required.issubset(frame.columns) or len(frame) != expected_count:
                raise ValueError(
                    f"Translated dataset has unexpected schema or row count: {relative}"
                )
            if (
                frame["id"].duplicated().any()
                or frame["pair_id"].duplicated().any()
                or frame["text"].eq("").any()
                or frame["item_group"].eq("").any()
                or not frame["language"].eq(language).all()
                or not frame["split"].eq(split).all()
                or not frame["translation_review_status"]
                .eq("original" if language == "en" else "needs_native_review")
                .all()
                or set(frame["label"]) - set(CLASSES)
            ):
                raise ValueError(f"Translated dataset contains invalid rows: {relative}")
            frames[split][language] = frame
            hashes[relative] = fingerprint
            keys_by_split[split].update(frame["text"].map(normalize_key))
            groups_by_split[split].update(frame["item_group"])
        english, macedonian = frames[split]["en"], frames[split]["mk"]
        if (
            english["pair_id"].tolist() != macedonian["pair_id"].tolist()
            or english["label"].tolist() != macedonian["label"].tolist()
            or english["item_group"].tolist() != macedonian["item_group"].tolist()
        ):
            raise ValueError(f"English/Macedonian pairs differ in {split}")
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if (
            keys_by_split[left] & keys_by_split[right]
            or groups_by_split[left] & groups_by_split[right]
        ):
            raise ValueError(f"Text or item groups leak across {left}/{right}")
    if set(frames["train"]["en"]["label"]) != set(CLASSES):
        raise ValueError("Training split must contain all four reviewed classes")

    manual_en, scope = load_manual_with_holds(
        EVALUATION_DIR / "manual_test.csv", EVALUATION_DIR / "manual_test_review.csv"
    )
    manual_mk = _manual_macedonian_with_holds()
    if manual_en["target_label"].tolist() != manual_mk["target_label"].tolist():
        raise ValueError("English/Macedonian manual labels differ")
    fixture_en, fixture_mk = _fixture_sets()
    fixture_rows = json.loads(
        (Path(__file__).resolve().parents[3] / "tests/fixtures/macedonian.json").read_text(
            encoding="utf-8"
        )
    )
    fixtures = {"en": fixture_en, "mk": fixture_mk}
    evaluations = {}
    for language in ("en", "mk"):
        test = frames["test"][language]
        validation = frames["validation"][language]
        manual = manual_en if language == "en" else manual_mk
        fixture = fixtures[language]
        output = [
            EvaluationSet(
                f"test_{language}",
                tuple(test["text"]),
                tuple(test["label"]),
                "inherited grouped test; plastic_metal has zero support",
            ),
            EvaluationSet(
                f"manual_{language}",
                tuple(manual["text"]),
                tuple(manual["target_label"]),
                scope["scope"]
                if language == "en"
                else "authored translation probe; needs native review",
            ),
            fixture,
            EvaluationSet(
                f"validation_{language}",
                tuple(validation["text"]),
                tuple(validation["label"]),
                "inherited grouped validation; glass and special_unsupported have zero support",
            ),
        ]
        for name, kinds in (
            ("clothing", {"wearable_clothes"}),
            ("electronics", {"small_electronics", "electronics"}),
        ):
            selected = [
                (row[language], label)
                for row, label in zip(fixture_rows, fixture.labels, strict=True)
                if row["kind"] in kinds and label == "special_unsupported"
            ]
            output.append(
                EvaluationSet(
                    f"{name}_probe_{language}",
                    tuple(text for text, _ in selected),
                    tuple(label for _, label in selected),
                    "development-authored, specialist-only diagnostic; never used to fit",
                )
            )
        if keys_by_split["train"] & {
            normalize_key(text) for evaluation in output[1:] for text in evaluation.texts
        }:
            raise ValueError(f"Exact training/evaluation text overlap for {language}")
        evaluations[language] = tuple(output)
    provenance = {
        "dataset_dir": str(data_dir),
        "input_sha256": hashes,
        "training_examples_per_language": len(frames["train"]["en"]),
        "training_class_counts": dict(Counter(frames["train"]["en"]["label"])),
        "split_class_counts": {
            split: dict(Counter(frames[split]["en"]["label"])) for split in EXPECTED_SPLITS
        },
        "manual_supported_examples": sum(bool(label) for label in manual_en["target_label"]),
        "manual_held_examples": sum(not label for label in manual_en["target_label"]),
        "translation_qa_flagged_unique": manifest["flagged_unique_translations"],
        "translation_review_status": manifest["translation_review_status"],
    }
    return frames["train"], evaluations, provenance


def run_bilingual_benchmark(
    results_dir: Path | None = None,
    artifacts_dir: Path | None = None,
    *,
    device: str = "cuda",
    batch_size: int = 32,
    epochs: int = 3,
    learning_rate: float = 2e-4,
    data_dir: Path | None = None,
    seed: int = RANDOM_SEED,
    source_root: Path | None = None,
) -> dict[str, Any]:
    if batch_size < 1 or epochs < 1 or learning_rate <= 0 or seed < 0:
        raise ValueError("Invalid benchmark hyperparameters")
    run_name = f"bilingual_seed{seed}"
    results_dir = results_dir or RESULTS_DIR / run_name
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR / "models" / run_name
    if (results_dir / f"{run_name}.json").exists() or (
        artifacts_dir.exists() and any(artifacts_dir.iterdir())
    ):
        raise FileExistsError(f"A completed bilingual seed-{seed} report already exists")
    results_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    training, evaluations, provenance = (
        load_paired_benchmark_data(data_dir, source_root=source_root)
        if data_dir is not None
        else load_paired_benchmark_data()
    )
    classes = tuple(provenance.get("classes", CLASSES))
    report: dict[str, Any] = {
        "schema_version": 1,
        "experiment": f"paired English/Macedonian {len(classes)}-class comparison",
        "development_only": True,
        "serving_eligible": False,
        "random_seed": seed,
        "classes": list(classes),
        "runtime": {
            "python": platform.python_version(),
            "executable": sys.executable,
            "scikit_learn": sklearn.__version__,
            "requested_device": device,
        },
        "data": provenance,
        "hyperparameters": {
            "batch_size": batch_size,
            "epochs": epochs,
            "learning_rate": learning_rate,
        },
        "methods": {},
        "limitations": [
            "Macedonian training and manual probes are machine/development-authored "
            "translations without native review.",
            "The inherited validation split omits glass and special_unsupported; "
            "test omits plastic_metal.",
            "Train specialist examples are predominantly batteries, with a few "
            "laptop chargers and no clothes or phones.",
            "Clothing/electronics probes are development-authored and are not "
            "independent field tests.",
            "No reviewed general examples or new Toronto mappings are included.",
            "Closed-set predictions only; no abstention threshold or serving change.",
        ],
    }
    if provenance.get("dataset_version") == "object-classes-v2":
        report["limitations"] = [
            "Machine/development-authored Macedonian translations still need native review.",
            "Training has only 11 clothes examples; validation and test each have one.",
            "General has no reviewed training support and is not a model output class.",
            "Validation lacks glass/specialist waste; test lacks plastic_metal/specialist waste.",
            "Macro-F1 includes all six model classes, even classes with zero evaluation support.",
            "Manual and object probes are development diagnostics, not independent field tests.",
            "Clothing probe includes three damaged/dirty-clothing descriptions; identity is "
            "separate from disposal/donation eligibility.",
            "Data and label space differ from historical four-class runs; scores are not "
            "directly comparable.",
            "Closed-set predictions only; no abstention calibration or serving change.",
        ]
    for language in ("en", "mk"):
        train = training[language].rename(columns={"label": "target_label"})
        eval_sets = evaluations[language]
        artifact_dir = artifacts_dir / language
        artifact_dir.mkdir(parents=True, exist_ok=True)
        for method in ("tfidf_logistic", "frozen_minilm", "lora_multilingual_minilm"):
            _seed_everything(seed)
            method_started = time.perf_counter()
            print(f"Starting {language}/{method}", flush=True)
            if method == "tfidf_logistic":
                result = run_tfidf(train, eval_sets, artifact_dir, classes=classes, seed=seed)
            elif method == "frozen_minilm":
                options = (
                    {
                        "encoder_id": MULTILINGUAL_MINILM_ID,
                        "encoder_revision": MULTILINGUAL_MINILM_REVISION,
                    }
                    if language == "mk"
                    else {}
                )
                result = run_frozen_minilm(
                    train,
                    eval_sets,
                    artifact_dir,
                    device=device,
                    batch_size=batch_size,
                    classes=classes,
                    seed=seed,
                    **options,
                )
            else:
                result = run_lora_multilingual_minilm(
                    train,
                    eval_sets,
                    artifact_dir,
                    device=device,
                    batch_size=batch_size,
                    epochs=epochs,
                    learning_rate=learning_rate,
                    classes=classes,
                    seed=seed,
                )
            result["total_seconds"] = round(time.perf_counter() - method_started, 3)
            result["setup_seconds"] = result.get("setup_seconds", 0.0)
            report["methods"][f"{language}_{method}"] = result
            manual = result["evaluations"][f"manual_{language}"]
            print(
                f"Finished {language}/{method}: total={result['total_seconds']:.3f}s, "
                f"manual_macro_f1={manual['closed_set_supported_macro_f1']:.3f}",
                flush=True,
            )
    report["wall_seconds"] = round(time.perf_counter() - started, 3)
    report["experiment_code_sha256"] = sha256_file(Path(__file__))
    report["reused_method_code_sha256"] = sha256_file(Path(__file__).with_name("benchmark.py"))
    write_json(results_dir / f"{run_name}.json", report)
    summary = []
    for name, result in report["methods"].items():
        for evaluation, metrics in result["evaluations"].items():
            summary.append(
                {
                    "method": name,
                    "evaluation": evaluation,
                    "supported_examples": metrics["supported_examples"],
                    "accuracy": metrics["closed_set_supported_accuracy"],
                    "macro_f1": metrics["closed_set_supported_macro_f1"],
                    "setup_seconds": result["setup_seconds"],
                    "training_seconds": result["training_seconds"],
                    "evaluation_seconds_all_sets": result["evaluation_seconds"],
                    "total_method_seconds": result["total_seconds"],
                }
            )
    pd.DataFrame(summary).to_csv(results_dir / f"{run_name}_summary.csv", index=False)
    return report
