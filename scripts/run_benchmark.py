"""Run seed-42 TF-IDF, frozen MiniLM and LoRA MiniLM comparison on a CUDA node."""

import argparse
from pathlib import Path

from smart_recycling.data.benchmark import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    args = parser.parse_args()
    report = run_benchmark(
        results_dir=args.results_dir,
        artifacts_dir=args.artifacts_dir,
        device=args.device,
        batch_size=args.batch_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
    )
    print(f"Completed seed-42 benchmark in {report['wall_seconds']:.3f}s")
    for name, method in report["methods"].items():
        english = method["evaluations"]["manual_en"]
        macedonian = method["evaluations"]["manual_mk"]
        print(
            f"{name}: train={method['training_seconds']:.3f}s; "
            f"English macro-F1={english['closed_set_supported_macro_f1']:.3f}; "
            f"Macedonian probe macro-F1={macedonian['closed_set_supported_macro_f1']:.3f}"
        )


if __name__ == "__main__":
    main()
