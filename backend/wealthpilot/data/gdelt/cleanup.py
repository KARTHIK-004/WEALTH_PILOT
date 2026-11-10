"""Path-guarded deletion (B2-I section 8.5). Never recursive; never outside the allowed folders."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path

from wealthpilot.data.gdelt.errors import UnsafePathError

ALLOWED_NAMES = (
    re.compile(r"^\d{14}\.gkg\.csv\.zip$"),
    re.compile(r"^\d{14}\.tsv\.gz$"),
    re.compile(r"^.+\.partial$"),
)


def safe_delete(path: Path, allowed_dirs: Sequence[Path]) -> None:
    """Delete one regular file if, and only if, every guard passes."""
    path = Path(path)
    if os.path.islink(path):
        raise UnsafePathError(f"refusing to delete a symbolic link: {path}")
    if not any(p.match(path.name) for p in ALLOWED_NAMES):
        raise UnsafePathError(f"refusing to delete an unexpected name: {path.name}")
    real = Path(os.path.realpath(path))
    roots = [Path(os.path.realpath(d)) for d in allowed_dirs]
    if not any(os.path.commonpath([str(real), str(r)]) == str(r) and real != r for r in roots):
        raise UnsafePathError(f"refusing to delete outside the allowed folders: {path}")
    if real.is_dir():
        raise UnsafePathError(f"refusing to delete a directory: {path}")
    if real.exists():
        real.unlink()


def sweep_tmp(tmp_dir: Path, keep: set[Path] | None = None) -> tuple[list[Path], list[Path]]:
    """Delete leftover files in ``tmp_dir`` (except ``keep``); return (deleted, refused)."""
    deleted: list[Path] = []
    refused: list[Path] = []
    if not tmp_dir.exists():
        return deleted, refused
    keep_real = {Path(os.path.realpath(k)) for k in (keep or set())}
    for root, _dirs, files in os.walk(tmp_dir):
        for name in sorted(files):
            p = Path(root) / name
            if Path(os.path.realpath(p)) in keep_real:
                continue
            try:
                safe_delete(p, [tmp_dir])
                deleted.append(p)
            except UnsafePathError:
                refused.append(p)
    # remove now-empty day folders (non-recursive, one level)
    for child in sorted(tmp_dir.iterdir()) if tmp_dir.exists() else []:
        if child.is_dir() and not os.path.islink(child) and not any(child.iterdir()):
            child.rmdir()
    return deleted, refused
