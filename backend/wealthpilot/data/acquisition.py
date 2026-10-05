"""Raw dataset acquisition.

Idempotent by design: every `ensure_*` function checks what is already on
disk under `datasets/raw/` first and returns immediately if the expected
files are present. Nothing here re-downloads, moves, renames, or modifies an
existing raw file — datasets/raw/ is treated as immutable once populated.

FAR-Trans is downloaded and unzipped directly (CC-BY 4.0, no auth). Kaggle
data requires either a Kaggle account (`~/.kaggle/kaggle.json`) or a manual
download placed in `datasets/raw/kaggle/` — this module never attempts to
authenticate to Kaggle itself; if the file is absent, it fails with a clear,
actionable message naming the expected path (CLAUDE.md rule, PROJECT_PLAN.md
Part 0).

Yahoo Finance / yfinance acquisition is intentionally NOT implemented here —
it belongs to Phase 6 (market analysis), not Phase 2.
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

# acquisition.py -> data/ -> wealthpilot/ -> backend/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = _REPO_ROOT / "datasets" / "raw"
FAR_TRANS_DIR = RAW_DIR / "FAR-Trans"
KAGGLE_DIR = RAW_DIR / "kaggle"

FAR_TRANS_ZIP_URL = "https://researchdata.gla.ac.uk/1658/1/FAR-Trans.zip"

FAR_TRANS_EXPECTED_FILES = [
    "customer_information.csv",
    "asset_information.csv",
    "markets.csv",
    "close_prices.csv",
    "limit_prices.csv",
    "transactions.csv",
    "questionnaires.csv",
]


class DatasetMissingError(RuntimeError):
    """Raised when a required dataset is not present and cannot be acquired automatically."""


def far_trans_is_present() -> bool:
    return all((FAR_TRANS_DIR / name).is_file() for name in FAR_TRANS_EXPECTED_FILES)


def ensure_far_trans() -> Path:
    """Return the FAR-Trans directory, downloading it only if not already present.

    Never overwrites an existing file — if `FAR_TRANS_DIR` already has every
    expected file, this is a pure no-op.
    """
    if far_trans_is_present():
        return FAR_TRANS_DIR

    FAR_TRANS_DIR.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(FAR_TRANS_ZIP_URL, timeout=60) as response:
        archive_bytes = response.read()
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        archive.extractall(FAR_TRANS_DIR)

    missing = [name for name in FAR_TRANS_EXPECTED_FILES if not (FAR_TRANS_DIR / name).is_file()]
    if missing:
        raise DatasetMissingError(
            f"FAR-Trans download completed but these expected files are still "
            f"missing from {FAR_TRANS_DIR}: {missing}"
        )
    return FAR_TRANS_DIR


def kaggle_is_present() -> bool:
    return KAGGLE_DIR.is_dir() and any(KAGGLE_DIR.glob("*.csv"))


def ensure_kaggle() -> Path:
    """Verify the Kaggle personal-finance data is present; never download or authenticate.

    Raises `DatasetMissingError` with the exact expected path if nothing is
    there, per CLAUDE.md: "read from a local path and fail with a clear
    message if absent — it must not attempt to authenticate."
    """
    if kaggle_is_present():
        return KAGGLE_DIR

    raise DatasetMissingError(
        f"No Kaggle CSV files found under {KAGGLE_DIR}. Download the personal-finance "
        "dataset manually from Kaggle (see docs/PROJECT_PLAN.md Part 0) and place the "
        f"CSV file(s) in {KAGGLE_DIR} — this module will not attempt to authenticate "
        "to Kaggle on your behalf."
    )
