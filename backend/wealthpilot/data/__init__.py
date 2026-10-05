"""Data acquisition and quality checks. Code only — datasets live in datasets/raw/."""

from wealthpilot.data.acquisition import (
    DatasetMissingError,
    ensure_far_trans,
    ensure_kaggle,
    far_trans_is_present,
    kaggle_is_present,
)
from wealthpilot.data.quality import (
    FileQualityReport,
    generate_far_trans_report,
    generate_kaggle_report,
)

__all__ = [
    "DatasetMissingError",
    "ensure_far_trans",
    "ensure_kaggle",
    "far_trans_is_present",
    "kaggle_is_present",
    "FileQualityReport",
    "generate_far_trans_report",
    "generate_kaggle_report",
]
