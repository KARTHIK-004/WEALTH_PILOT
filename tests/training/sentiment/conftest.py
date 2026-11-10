"""Fixtures for the sentiment training tests (ADR-052). The helpers live in `sentiment_fixtures.py`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# the project's pytest runs in importlib mode, which does not put a test directory on sys.path: the shared helpers are imported from here
sys.path.insert(0, str(Path(__file__).parent))

from sentiment_fixtures import make_rows, manifest_dict, write_jsonl, write_manifest


@pytest.fixture()
def dev_data(tmp_path: Path):
    """(data file, manifest file): 120 invented sentences, 40 per class, grouped by four, in a manifest that says it is a development fixture."""
    return write_jsonl(tmp_path / "dev.jsonl", make_rows(40, group_every=4)), write_manifest(tmp_path / "manifest.json", manifest_dict())
