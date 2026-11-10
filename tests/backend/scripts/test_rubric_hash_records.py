"""The pilot-pack manifest records the CURRENT hashes of `docs/USER_TEXT_ANNOTATION_RUBRIC.md` after the owner-approved edit of 2026-10-28 (rules 11 and 12), and the pack is still a DRAFT: not frozen,
not distributed, annotation not started. The hashes are rebuilt with `python scripts/build_dry_run_package.py` (the repository's own process), never written by hand. No label, text or baseline
output is involved here."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUBRIC = ROOT / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md"
MANIFEST = ROOT / "datasets" / "rubric_examples" / "pilot_pack_v0" / "author_only" / "DRAFT_MANIFEST.json"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_dry_run_package_for_hash_records", ROOT / "scripts" / "build_dry_run_package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_manifest_records_the_current_hashes_and_still_says_draft_not_frozen_not_started():
    builder = load_builder()
    rubric_text = RUBRIC.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["rubric_sha256"] == hashlib.sha256(rubric_text.encode("utf-8")).hexdigest()
    assert manifest["rubric_excerpt_sha256"] == hashlib.sha256(builder.extract_annotator_rubric(rubric_text).encode("utf-8")).hexdigest()
    assert manifest["package_files"]["RUBRIC_EXCERPT.md"] == manifest["rubric_excerpt_sha256"]
    assert (manifest["manifest_status"], manifest["frozen"], manifest["freeze_process_completed"], manifest["rubric_version"]) == ("DRAFT", False, False, "v0-draft")
    assert manifest["annotation_status"] == "NOT STARTED" and manifest["distribution_ready"] is False
    assert manifest["data_kind"].startswith("FICTIONAL") and "not validation data" in manifest["data_kind"]
    assert builder.verify() == []


def test_the_rubric_edit_left_the_other_package_hashes_untouched():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["package_files"]["pilot_texts.jsonl"] == "b37568933e59f1630a4e740dc886ba64c653275727d77a014c5d73d90db09b48"          # the 30 fictional texts, unchanged
    assert manifest["package_files"]["annotation_template.csv"] == "3d72b2a76f23a50c69242f80d2a427528f0431041a5d79d6fff4e8767fcd1569"
    assert manifest["package_files"]["INSTRUCTIONS.md"] == "291049daf44f9f6e6e8872144b2bc3fa5154a2d07e586db2a95fe9663536878e"
    assert manifest["text_count"] == 30 and manifest["ids_sha256"] == "e7ba4f18fdff78092011611299bd5e6beffd66af1d91ee38731f65a8a8ba25fe"
