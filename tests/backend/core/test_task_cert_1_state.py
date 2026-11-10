"""TASK-CERT-1 guard (GHSA-6q48-6c7w-9gw2): the project environment must carry a `certifi` of 2026.10.19 or later, and so must the copy vendored inside its `pip`. Reads installed metadata and one text file; no network."""
from __future__ import annotations

import importlib.metadata as md
import re
from pathlib import Path

FIXED = (2026, 10, 19)


def parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:3])


def test_the_top_level_certifi_is_the_fixed_release_or_later():
    assert parse(md.version("certifi")) >= FIXED, md.version("certifi")


def test_the_certifi_vendored_inside_pip_is_the_fixed_release_or_later():
    pip_dir = Path(md.distribution("pip")._path).parent / "pip" / "_vendor"
    lines = [l.strip() for l in (pip_dir / "vendor.txt").read_text(encoding="utf-8").splitlines() if l.strip().startswith("certifi")]
    assert len(lines) == 1 and parse(lines[0].split("==", 1)[1]) >= FIXED, lines
    init = (pip_dir / "certifi" / "__init__.py").read_text(encoding="utf-8")
    assert parse(re.search(r'__version__ = "([^"]+)"', init).group(1)) >= FIXED


def test_the_remediation_changed_no_other_pinned_tooling():
    # setuptools 65.5.0 was the TASK-CERT-1 pin; 81.0.0 is the owner-approved correction recorded in docs/sentiment/stage_b/evidence/RECOVERY_RECORD.md (2026-11-04). Anything else is a change nobody approved.
    assert md.version("setuptools") in ("65.5.0", "81.0.0") and md.version("tensorflow") == "2.17.0" and md.version("keras") == "3.15.1" and md.version("numpy") == "1.26.4"
