"""Validate the saved v2 runs and summarize their five-seed metric variation."""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from smart_recycling.data.common import sha256_file, write_json
from smart_recycling.data.translation import write_csv

DEFAULT_SEEDS = (42, 43, 44, 45, 46)
EVALUATIONS = (
    "manual",
    "test",
    "guidance_v3",
    "validation",
    "object_probe",
    "clothing_probe",
    "electronics_probe",
)


def summarize(results_root: Path, output_dir: Path, seeds: tuple[int, ...]) -> dict:
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Seeds must be a non-empty, unique list")
    if output_dir.exists():
        raise FileExistsError(f"Summary already exists: {output_dir}")
    reports = []
    report_paths = {}
    baseline = None
    all_metrics = defaultdict(list)
    for seed in seeds:
        path = results_root / f"bilingual_v2_seed{seed}" / f"bilingual_seed{seed}.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        if (
            report["random_seed"] != seed
            or len(report["methods"]) != 6
            or report["data"]["dataset_version"] != "object-classes-v2"
            or report["data"]["training_examples_per_language"] != 3052
        ):
            raise ValueError(f"Incomplete or wrong-seed report: {path}")
        invariant = {
            "classes": report["classes"],
            "dataset_hashes": report["data"]["input_sha256"],
            "training_class_counts": report["data"]["training_class_counts"],
            "hyperparameters": report["hyperparameters"],
            "methods": sorted(report["methods"]),
        }
        if baseline is not None and invariant != baseline:
            raise ValueError(f"Reports do not use the same dataset/settings: {path}")
        baseline = invariant
        for relative, fingerprint in report["data"]["input_sha256"].items():
            if sha256_file(Path(report["data"]["dataset_dir"]) / relative) != fingerprint:
                raise ValueError(f"Changed source dataset: {relative}")
        if seed != 42:
            for code_path, key in (
                (Path("src/smart_recycling/data/bilingual_benchmark.py"), "experiment_code_sha256"),
                (Path("src/smart_recycling/data/benchmark.py"), "reused_method_code_sha256"),
            ):
                if sha256_file(code_path) != report[key]:
                    raise ValueError(f"Experiment code changed after seed {seed}: {code_path}")
        for method_name, method in report["methods"].items():
            if method["classes"] != report["classes"] or method.get("seed", seed) != seed:
                raise ValueError(f"Incorrect saved label space or seed: {seed}/{method_name}")
            artifact = method["artifact"]
            artifact_path = Path(artifact["path"])
            if "sha256" in artifact:
                if sha256_file(artifact_path) != artifact["sha256"]:
                    raise ValueError(f"Artifact checksum mismatch: {artifact_path}")
            else:
                for name, fingerprint in artifact["files"].items():
                    if sha256_file(artifact_path / name) != fingerprint:
                        raise ValueError(f"Artifact checksum mismatch: {artifact_path / name}")
                labels = json.loads((artifact_path / "label_mapping.json").read_text())
                if labels["labels"] != report["classes"]:
                    raise ValueError(f"Adapter label map mismatch: {artifact_path}")
            language = method_name.split("_", 1)[0]
            for evaluation in EVALUATIONS:
                metrics = method["evaluations"][f"{evaluation}_{language}"]
                all_metrics[(method_name, evaluation)].append(metrics)
        report_paths[str(seed)] = {"path": str(path), "sha256": sha256_file(path)}
        reports.append(report)

    rows = []
    for (method, evaluation), metrics in sorted(all_metrics.items()):
        support = {item["supported_examples"] for item in metrics}
        if len(metrics) != len(seeds) or len(support) != 1:
            raise ValueError(f"Evaluation support differs across seeds: {method}/{evaluation}")
        row = {
            "method": method,
            "evaluation": evaluation,
            "supported_examples": support.pop(),
            "seeds": len(seeds),
        }
        for metric, short in (
            ("closed_set_supported_accuracy", "accuracy"),
            ("closed_set_supported_macro_f1", "macro_f1"),
        ):
            values = [float(item[metric]) for item in metrics]
            row.update(
                {
                    f"{short}_mean": round(statistics.mean(values), 6),
                    f"{short}_sample_sd": round(statistics.stdev(values), 6)
                    if len(values) > 1
                    else 0.0,
                    f"{short}_min": round(min(values), 6),
                    f"{short}_max": round(max(values), 6),
                }
            )
        rows.append(row)
    output_dir.mkdir(parents=True)
    summary_path = output_dir / "summary.csv"
    write_csv(summary_path, rows, list(rows[0]))
    report = {
        "seeds": list(seeds),
        "dataset_version": "object-classes-v2",
        "training_examples_per_language": 3052,
        "classes": baseline["classes"],
        "input_reports": report_paths,
        "output_summary_sha256": sha256_file(summary_path),
        "method_count_per_seed": 6,
        "total_fits": 6 * len(seeds),
        "benchmark_wall_seconds": {
            str(seed): item["wall_seconds"] for seed, item in zip(seeds, reports, strict=True)
        },
        "benchmark_wall_seconds_sum": round(sum(item["wall_seconds"] for item in reports), 3),
        "limitations": [
            "Same split and source texts across seeds; variation measures fit randomness only.",
            "Clothing has 11 training examples and one example in validation and test.",
            "All Macedonian translations need native review; probes are development authored.",
        ],
    }
    write_json(output_dir / "manifest.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=Path("results"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/bilingual_v2_seeds42_46"))
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    args = parser.parse_args()
    report = summarize(args.results_root, args.output_dir, tuple(args.seeds))
    print(f"Verified {report['total_fits']} fits; summary: {args.output_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
