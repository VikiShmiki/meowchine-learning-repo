"""Stable dataset identifiers, labels, and paths."""

from pathlib import Path

RANDOM_SEED = 42

TARGET_LABELS = (
    "glass",
    "plastic_metal",
    "paper_tetrapak",
    "general",
    "special_unsupported",
)
LABEL_TO_ID = {label: index for index, label in enumerate(TARGET_LABELS)}

DATASET_A_ID = "thomasavare/waste-classification-v2"
DATASET_A_REVISION = "df082443773f2db01e165577c5d94c5dafe90f12"

TORONTO_PACKAGE_API = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/"
    "package_show?id=waste-wizard-lookup-table"
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPOSITORY_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MAPPINGS_DIR = DATA_DIR / "mappings"
EVALUATION_DIR = DATA_DIR / "evaluation"
RESULTS_DIR = REPOSITORY_ROOT / "results"
IMAGES_DIR = REPOSITORY_ROOT / "images"
ARTIFACTS_DIR = REPOSITORY_ROOT / "artifacts"
