"""Run the complete reproducible data preparation and baseline workflow."""

import argparse

from smart_recycling.data.analysis import analyze_dataset
from smart_recycling.data.augmentation import generate_augmented_queries
from smart_recycling.data.baselines import train_baselines
from smart_recycling.data.combination import combine_datasets
from smart_recycling.data.dataset_a import download_dataset_a, process_dataset_a
from smart_recycling.data.dataset_b import download_dataset_b, process_dataset_b
from smart_recycling.data.splitting import create_grouped_splits
from smart_recycling.data.validation import validate_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="reuse existing raw downloads",
    )
    parser.add_argument(
        "--skip-baselines",
        action="store_true",
        help="prepare and validate data without fitting models",
    )
    args = parser.parse_args()

    if not args.skip_download:
        download_dataset_a()
        download_dataset_b()
    process_dataset_a()
    process_dataset_b()
    generate_augmented_queries()
    combine_datasets()
    create_grouped_splits()
    validate_dataset()
    analyze_dataset()
    if not args.skip_baselines:
        train_baselines()


if __name__ == "__main__":
    main()
