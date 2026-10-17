"""Export full local dataset translations and reviewed-label experimental splits."""

import argparse
from pathlib import Path

from smart_recycling.data.translation import run_translation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--beams", type=int, default=4)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    report = run_translation(
        root=args.root,
        output=args.output or args.root / "data/processed/bilingual_mk_v1",
        device=args.device,
        batch_size=args.batch_size,
        beams=args.beams,
        max_new_tokens=args.max_new_tokens,
        resume=args.resume,
    )
    print(f"Complete: {report['unique_translations']} unique translations")
    print(f"Experimental class counts: {report['experimental_class_counts']}")


if __name__ == "__main__":
    main()
