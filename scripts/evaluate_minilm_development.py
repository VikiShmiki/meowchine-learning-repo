"""Run the reviewed four-class MiniLM signal check while five-class data is held."""

import argparse
from pathlib import Path

from smart_recycling.data.minilm import train_frozen_minilm_development


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--mapping-review", type=Path)
    parser.add_argument("--validation", type=Path)
    parser.add_argument("--manual", type=Path)
    parser.add_argument("--manual-review", type=Path)
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--no-progress", action="store_true")
    args = parser.parse_args()
    report = train_frozen_minilm_development(
        raw_dir=args.raw_dir,
        mapping_path=args.mapping,
        mapping_review_path=args.mapping_review,
        validation_path=args.validation,
        manual_path=args.manual,
        manual_review_path=args.manual_review,
        results_dir=args.results_dir,
        artifacts_dir=args.artifacts_dir,
        device=args.device,
        batch_size=args.batch_size,
        progress=not args.no_progress,
    )
    manual = report["evaluations"]["manual"]
    selected = report["selection"]["selected_threshold"]
    print(
        "Frozen MiniLM four-class development check complete: "
        f"closed-set supported accuracy={manual['closed_set_supported_accuracy']:.3f}; "
        f"macro-F1={manual['closed_set_supported_macro_f1']:.3f}; "
        f"threshold={selected if selected is not None else 'no passing threshold'}"
    )


if __name__ == "__main__":
    main()
