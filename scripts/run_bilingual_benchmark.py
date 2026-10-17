"""Run one English and one Macedonian fit per benchmark method and seed."""

import argparse
from pathlib import Path

from smart_recycling.data.bilingual_benchmark import run_bilingual_benchmark


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    report = run_bilingual_benchmark(
        results_dir=args.results_dir,
        artifacts_dir=args.artifacts_dir,
        device=args.device,
        batch_size=args.batch_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        data_dir=args.data_dir,
        seed=args.seed,
    )
    print(f"Completed all six fits in {report['wall_seconds']:.3f}s")


if __name__ == "__main__":
    main()
