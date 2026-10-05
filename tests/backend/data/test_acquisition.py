"""Phase 2 completion criteria: acquisition is idempotent and never touches
raw files that are already present. Runs against the real datasets/raw/ data
(not a fixture) specifically to prove immutability on the actual files —
hashing every byte before and after is the only way to be sure nothing in
datasets/raw/ was moved, renamed, or modified.
"""

import hashlib
from pathlib import Path

from wealthpilot.data.acquisition import (
    FAR_TRANS_DIR,
    KAGGLE_DIR,
    RAW_DIR,
    ensure_far_trans,
    ensure_kaggle,
    far_trans_is_present,
    kaggle_is_present,
)


def _hash_tree(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def test_far_trans_and_kaggle_are_present_on_disk():
    assert far_trans_is_present(), f"expected FAR-Trans files under {FAR_TRANS_DIR}"
    assert kaggle_is_present(), f"expected at least one Kaggle CSV under {KAGGLE_DIR}"


def test_ensure_functions_never_modify_existing_raw_files():
    before = _hash_tree(RAW_DIR)

    ensure_far_trans()
    ensure_kaggle()

    after = _hash_tree(RAW_DIR)
    assert before == after, "datasets/raw/ changed after calling ensure_far_trans()/ensure_kaggle()"


def test_ensure_functions_are_idempotent():
    first_far_trans = ensure_far_trans()
    second_far_trans = ensure_far_trans()
    assert first_far_trans == second_far_trans == FAR_TRANS_DIR

    first_kaggle = ensure_kaggle()
    second_kaggle = ensure_kaggle()
    assert first_kaggle == second_kaggle == KAGGLE_DIR
