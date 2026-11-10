"""Deploy-time helper: fetch the FAR-Trans CSVs onto a fresh server (stdlib only).

The raw FAR-Trans files are third-party data and are deliberately NOT in git.
The backend's startup (`api/lifespan.py` -> `load_far_trans_tables`) needs four
of them in `datasets/raw/FAR-Trans/`. On a fresh Render instance they are absent,
so this script downloads a zip containing them from a private URL you control.

It is a no-op when all four files already exist (local dev, or a Render
Persistent Disk mounted at datasets/raw/FAR-Trans). It only ever WRITES missing
files; it never modifies or overwrites an existing one.

Environment:
  FAR_TRANS_URL          required when files are missing; https URL of the zip
  FAR_TRANS_SHA256       optional; hex SHA-256 of the zip, verified before use
  FAR_TRANS_AUTH_HEADER  optional; full Authorization header value, e.g.
                         "Bearer <token>" (the URL/token are never printed)

Usage: python scripts/fetch_far_trans.py
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = REPO_ROOT / "datasets" / "raw" / "FAR-Trans"
REQUIRED = (
    "customer_information.csv",
    "asset_information.csv",
    "transactions.csv",
    "close_prices.csv",
)
MAX_BYTES = 500 * 1024 * 1024  # refuse absurdly large downloads


def _missing() -> list[str]:
    return [name for name in REQUIRED if not (TARGET_DIR / name).is_file()]


def main() -> int:
    missing = _missing()
    if not missing:
        print("FAR-Trans: all required files present; nothing to fetch.")
        return 0

    url = os.environ.get("FAR_TRANS_URL", "").strip()
    if not url:
        print(
            f"FAR-Trans: missing {missing} and FAR_TRANS_URL is not set. "
            "Set it to a private https URL of a zip containing those files.",
            file=sys.stderr,
        )
        return 1
    if not url.startswith("https://"):
        print("FAR-Trans: FAR_TRANS_URL must be an https:// URL.", file=sys.stderr)
        return 1

    headers = {"Accept": "application/octet-stream", "User-Agent": "wealthpilot-deploy"}
    auth = os.environ.get("FAR_TRANS_AUTH_HEADER", "").strip()
    if auth:
        headers["Authorization"] = auth

    print(f"FAR-Trans: downloading {len(missing)} missing file(s)...")
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 (https enforced above)
            payload = response.read(MAX_BYTES + 1)
    except Exception as exc:  # never echo the URL: it may embed a token
        print(f"FAR-Trans: download failed ({type(exc).__name__}).", file=sys.stderr)
        return 1
    if len(payload) > MAX_BYTES:
        print("FAR-Trans: download exceeds the size limit; aborting.", file=sys.stderr)
        return 1

    expected = os.environ.get("FAR_TRANS_SHA256", "").strip().lower()
    if expected:
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            print("FAR-Trans: SHA-256 mismatch; refusing to use the download.", file=sys.stderr)
            return 1

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            # Extract by base name only, and only the files we expect: no path traversal.
            by_basename = {Path(info.filename).name: info for info in archive.infolist() if not info.is_dir()}
            for name in missing:
                info = by_basename.get(name)
                if info is None:
                    print(f"FAR-Trans: {name} not found inside the zip.", file=sys.stderr)
                    return 1
                (TARGET_DIR / name).write_bytes(archive.read(info))
    except zipfile.BadZipFile:
        print("FAR-Trans: the download is not a valid zip file.", file=sys.stderr)
        return 1

    still_missing = _missing()
    if still_missing:
        print(f"FAR-Trans: still missing {still_missing} after extraction.", file=sys.stderr)
        return 1
    print("FAR-Trans: required files are in place.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
