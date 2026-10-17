"""Download and inspect raw waste vocabulary without invoking the preparation pipeline."""

import argparse
import json
from pathlib import Path

from smart_recycling.data.constants import RAW_DIR
from smart_recycling.data.raw_inventory import download_raw_datasets, inspect_raw_datasets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument(
        "--inspect-only", action="store_true", help="Reuse checksum-verified raw files"
    )
    args = parser.parse_args()
    inspect = inspect_raw_datasets if args.inspect_only else download_raw_datasets
    report = inspect(args.raw_dir)
    print(
        json.dumps(
            {
                "hf": {
                    split: {
                        key: details[key]
                        for key in (
                            "rows",
                            "electronics_candidates",
                            "clothing_candidates",
                        )
                    }
                    for split, details in report["hugging_face"]["files"].items()
                },
                "toronto": {
                    key: report["toronto"][key]
                    for key in (
                        "rows",
                        "clothing_candidates",
                        "electronics_candidates",
                    )
                },
                "report": str(args.raw_dir / "inventory.json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
