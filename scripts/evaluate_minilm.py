"""Train and evaluate the frozen MiniLM embedding baseline."""

import argparse
from pathlib import Path

from smart_recycling.data.minilm import train_frozen_minilm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--manual", type=Path)
    parser.add_argument("--manual-review", type=Path)
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--no-progress", action="store_true")
    args = parser.parse_args()
    report = train_frozen_minilm(
        dataset_path=args.dataset,
        manual_path=args.manual,
        manual_review_path=args.manual_review,
        results_dir=args.results_dir,
        artifacts_dir=args.artifacts_dir,
        device=args.device,
        batch_size=args.batch_size,
        progress=not args.no_progress,
    )
    selected = report["selection"]["selected_threshold"]
    test = report["evaluations"]["test"]
    print(
        "Frozen MiniLM complete: "
        f"test accuracy={test['closed_set_accuracy']:.3f}; "
        f"macro-F1={test['closed_set_macro_f1']:.3f}; "
        f"threshold={selected if selected is not None else 'no passing threshold'}"
    )


if __name__ == "__main__":
    main()
