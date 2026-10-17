"""Relabel clothes/electronics and export matching English/Macedonian dataset v2."""

import argparse
from pathlib import Path

from smart_recycling.data.relabel import run_relabel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_relabel(
        root=args.root,
        source=args.source or args.root / "data/processed/bilingual_mk_v1",
        output=args.output or args.root / "data/processed/bilingual_mk_v2",
    )
    print(f"Relabeled Toronto source items: {report['reviewed_toronto_counts']}")
    print(f"Paired split class counts: {report['experimental_class_counts']}")
    print(f"Exclusions: {report['experimental_exclusions']}")


if __name__ == "__main__":
    main()
