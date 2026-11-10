"""Adversarial tests for the fictional dry-run package builder (scripts/build_dry_run_package.py): hostile or careless inputs must be rejected or handled by a documented rule.

Every verify-style case follows the same pattern so no test can pass vacuously: a CONTROL (the unmodified sandbox verifies clean) and then ONE mutation that must produce the named problem.
Offline, deterministic, standard library only; the committed package is never written (the builder is pointed at a temporary copy). No labels, annotators or agreement are simulated.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "datasets" / "rubric_examples" / "pilot_pack_v0"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b = load("build_dry_run_package")
S, E = b.EXCERPT_START, b.EXCERPT_END


@pytest.fixture()
def sb(tmp_path, monkeypatch):
    """A sandbox: temporary annotator sources, rubric, package and manifest. Returns the root; the builder's module paths point inside it."""
    shutil.copytree(PACK / "annotator", tmp_path / "annotator")
    (tmp_path / "docs").mkdir()
    shutil.copyfile(ROOT / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md", tmp_path / "docs" / "RUBRIC.md")
    monkeypatch.setattr(b, "ANNOTATOR", tmp_path / "annotator")
    monkeypatch.setattr(b, "RUBRIC", tmp_path / "docs" / "RUBRIC.md")
    monkeypatch.setattr(b, "PACKAGE", tmp_path / "package")
    monkeypatch.setattr(b, "AUTHOR", tmp_path / "author_only")
    monkeypatch.setattr(b, "MANIFEST", tmp_path / "author_only" / "DRAFT_MANIFEST.json")
    return tmp_path


def built(sb):
    b.build(None)
    assert b.verify() == []                                   # CONTROL: the untouched sandbox is clean
    return sb


def manifest_of(sb) -> dict:
    return json.loads((sb / "author_only" / "DRAFT_MANIFEST.json").read_text(encoding="utf-8"))


def rewrite_manifest_hash(sb, name: str) -> None:
    """The attacker also fixes the manifest so the plain hash comparison cannot catch the change."""
    data = manifest_of(sb)
    data["package_files"][name] = b.sha256_file(sb / "package" / name)
    if name == "RUBRIC_EXCERPT.md":
        data["rubric_excerpt_sha256"] = data["package_files"][name]
    (sb / "author_only" / "DRAFT_MANIFEST.json").write_text(json.dumps(data), encoding="utf-8")


# ------------------------------------------------------------------ excerpt markers

@pytest.mark.parametrize("text, why", [
    ("no markers at all", "missing"),
    (f"{S} only a start", "unbalanced"),
    (f"only an end {E}", "unbalanced"),
    (f"{E} reversed {S}", "reversed"),
    (f"{S} a {E} {E} b {S}", "reversed"),
    (f"{S} outer {S} inner {E} {E}", "nested"),
    (f"{S} {S} {E} {E}", "nested"),
    (f"{S} same {E} gap {S} same {E}", "duplicate"),
    (f"{S}   {E}", "empty"),
    (f"{S} fine {E}\n<!--annotator-excerpt:start--> sneaky {E}", "not an exact marker"),
    (f"{S} fine {E}\n<!-- Annotator-Excerpt:START --> hidden", "not an exact marker"),
    (f"{S} fine {E}\n<!-- annotator-excerpt:start -->   <!-- annotator-excerpt:end -->", "duplicate|empty"),
])
def test_bad_marker_layouts_are_rejected_with_a_reason(text, why):
    with pytest.raises(ValueError) as info:
        b.extract_annotator_rubric(text)
    assert re.search(why, str(info.value)), (why, str(info.value))
    # CONTROL: a well-formed layout of the same material is accepted
    assert "fine" in b.extract_annotator_rubric(f"{S} fine {E} private {S} other {E}")


def test_marker_like_prose_that_is_not_an_html_comment_is_allowed():
    ok = b.extract_annotator_rubric(f"Use `annotator-excerpt` markers. {S} public {E} annotator-excerpt prose")
    assert ok.endswith("public\n") and "markers" not in ok


def test_a_misspelled_marker_can_no_longer_silently_shrink_the_real_rubric_excerpt(sb):
    rubric = sb / "docs" / "RUBRIC.md"
    original = rubric.read_text(encoding="utf-8")
    assert len(b.extract_annotator_rubric(original)) > 2000                                   # CONTROL
    rubric.write_text(original.replace(f"{S}\n\n### Flags", "<!--annotator-excerpt:start-->\n\n### Flags", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="not an exact marker"):
        b.extract_annotator_rubric(rubric.read_text(encoding="utf-8"))
    with pytest.raises(ValueError):
        b.build(None)                                                                           # the builder refuses instead of writing a shorter excerpt
    assert not (sb / "package").exists() or not any((sb / "package").iterdir())


def test_a_leaking_rubric_part_makes_the_builder_refuse_before_writing(sb):
    rubric = sb / "docs" / "RUBRIC.md"
    rubric.write_text(rubric.read_text(encoding="utf-8").replace("## 1. Scope", "## 1. Scope\n\nSee the recommended O2 default and the consent record (author note).", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="leak"):
        b.build(None)
    assert not (sb / "package" / "RUBRIC_EXCERPT.md").exists()


# ------------------------------------------------------------------ altered files, even with the manifest rewritten

@pytest.mark.parametrize("name, mutation", [
    ("RUBRIC_EXCERPT.md", lambda t: t.replace("Use it instead of guessing.", "Guess if you like.")),
    ("INSTRUCTIONS.md", lambda t: t + "\nAlso label the third text positive.\n"),
    ("annotation_template.csv", lambda t: t.replace("pilot-001,,,", "pilot-001,,positive,", 1)),
    ("pilot_texts.jsonl", lambda t: t.replace("I track my spending", "I never track my spending", 1)),
])
def test_an_altered_package_file_is_detected_even_when_the_manifest_hash_is_rewritten(sb, name, mutation):
    built(sb)
    path = sb / "package" / name
    changed = mutation(path.read_text(encoding="utf-8"))
    assert changed != path.read_text(encoding="utf-8")                                          # the mutation really changed something
    path.write_text(changed, encoding="utf-8", newline="")
    rewrite_manifest_hash(sb, name)
    problems = b.verify()
    assert problems and not any("differs from the manifest hash" in p for p in problems)        # the hash trick worked, so something else must catch it
    assert any(name in p for p in problems), problems


def test_a_manifest_that_lies_about_counts_ids_or_the_excerpt_hash_is_detected(sb):
    built(sb)
    for key, value in (("text_count", 29), ("ids_sha256", "0" * 64), ("rubric_excerpt_sha256", "1" * 64)):
        data = manifest_of(sb)
        original = data[key]
        data[key] = value
        (sb / "author_only" / "DRAFT_MANIFEST.json").write_text(json.dumps(data), encoding="utf-8")
        assert any(key in p for p in b.verify()), key
        data[key] = original
        (sb / "author_only" / "DRAFT_MANIFEST.json").write_text(json.dumps(data), encoding="utf-8")
        assert b.verify() == [], key                                                              # CONTROL after restoring


def test_malformed_or_incomplete_manifests_are_reported_not_crashed_on(sb):
    built(sb)
    path = sb / "author_only" / "DRAFT_MANIFEST.json"
    path.write_text("{ not json", encoding="utf-8")
    assert any("not valid JSON" in p for p in b.verify())
    path.write_text(json.dumps({"manifest_status": "DRAFT", "frozen": False}), encoding="utf-8")
    assert any("missing" in p for p in b.verify())


def test_manifest_listing_extra_or_path_like_package_entries_is_rejected(sb):
    built(sb)
    data = manifest_of(sb)
    data["package_files"]["../author_only/author_challenge_map.json"] = "0" * 64
    (sb / "author_only" / "DRAFT_MANIFEST.json").write_text(json.dumps(data), encoding="utf-8")
    assert any("package_files" in p and "exactly" in p for p in b.verify())


# ------------------------------------------------------------------ stale, extra, missing and traversal

def test_extra_hidden_nested_and_missing_package_entries_are_detected(sb):
    built(sb)
    (sb / "package" / ".hidden").write_text("x", encoding="utf-8")
    (sb / "package" / "sub").mkdir()
    assert any("package files are" in p and ".hidden" in p and "sub" in p for p in b.verify())
    (sb / "package" / ".hidden").unlink()
    (sb / "package" / "sub").rmdir()
    assert b.verify() == []
    (sb / "package" / "INSTRUCTIONS.md").unlink()
    problems = b.verify()
    assert any("package files are" in p for p in problems)


def test_the_builder_refuses_a_package_folder_with_unexpected_entries_and_never_deletes_them(sb):
    built(sb)
    stray = sb / "package" / "challenge_notes.txt"
    stray.write_text("author hypotheses", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected entries.*never deletes"):
        b.build(None)
    assert stray.exists()                                                                          # preserved, as the project rules require
    stray.unlink()
    b.build(None)
    assert b.verify() == []


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_a_symlink_inside_the_package_or_as_a_source_is_rejected(sb):
    built(sb)
    secret = sb / "secret.md"
    secret.write_text("# Annotation rules\n" + (sb / "package" / "RUBRIC_EXCERPT.md").read_text(encoding="utf-8"), encoding="utf-8")
    target = sb / "package" / "INSTRUCTIONS.md"
    original = target.read_bytes()
    target.unlink()
    try:
        os.symlink(secret, target)
    except (OSError, NotImplementedError):
        pytest.skip("creating symlinks needs a privilege on this machine")
    assert any("not a regular file" in p and "INSTRUCTIONS.md" in p for p in b.verify())
    target.unlink()
    target.write_bytes(original)
    assert b.verify() == []
    source = sb / "annotator" / "INSTRUCTIONS.md"
    source.unlink()
    os.symlink(secret, source)
    with pytest.raises(ValueError, match="regular file"):
        b.build(None)


def test_path_like_names_cannot_become_package_members(sb):
    assert all(Path(n).name == n and n not in ("", ".", "..") for n in b.PACKAGE_FILES)
    built(sb)
    outside = sb / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    (sb / "package" / "..outside").write_text("x", encoding="utf-8")
    assert any("package files are" in p for p in b.verify())


# ------------------------------------------------------------------ leakage through headings, comments, metadata and instructions

@pytest.mark.parametrize("name, addition, expect", [
    ("INSTRUCTIONS.md", "\n## Pre-annotation ambiguities\n", "pre_annotation|ambigu"),
    ("INSTRUCTIONS.md", "\n<!-- written by the pack author -->\n", "matching|pack author"),
    ("RUBRIC_EXCERPT.md", "\n### Author note (not for annotators)\n", "author note|not for annotators"),
    ("RUBRIC_EXCERPT.md", "\nProbe A5 checks the negation rule.\n", "A\\(\\?:1"),
    ("RUBRIC_EXCERPT.md", "\nThe recommended O2 default applies.\n", "O\\[1-4\\]"),
    ("INSTRUCTIONS.md", "\nSee author_only/author_challenge_map.json\n", "author_only"),
    ("INSTRUCTIONS.md", "\nThe freeze manifest lists the hashes.\n", "freeze|manifest"),
    ("INSTRUCTIONS.md", "\nYour consent form is separate.\n", "consent"),
])
def test_author_only_information_in_headings_comments_and_instructions_is_flagged(sb, name, addition, expect):
    built(sb)
    path = sb / "package" / name
    path.write_text(path.read_text(encoding="utf-8") + addition, encoding="utf-8")
    rewrite_manifest_hash(sb, name)
    problems = [p for p in b.verify() if name in p and ("author-only wording" in p or "non-annotator content" in p)]
    assert problems and any(re.search(expect, p, re.IGNORECASE) for p in problems), (expect, problems)


def test_label_leaking_metadata_in_the_texts_and_template_is_rejected(sb):
    built(sb)
    texts = sb / "package" / "pilot_texts.jsonl"
    original = texts.read_text(encoding="utf-8")
    first = json.loads(original.splitlines()[0])
    for extra in ({"expected_sentiment": "neutral"}, {"labels": {"sentiment": "neutral"}}, {"tags": ["neutral"]}, {"annotator_id": "x"}):
        rows = original.splitlines()
        rows[0] = json.dumps({**first, **extra}, ensure_ascii=False)
        texts.write_text("\n".join(rows) + "\n", encoding="utf-8")
        rewrite_manifest_hash(sb, "pilot_texts.jsonl")
        assert any("pilot_texts.jsonl" in p and "keys" in p for p in b.verify()), extra
    texts.write_text(original, encoding="utf-8")
    rewrite_manifest_hash(sb, "pilot_texts.jsonl")
    assert b.verify() == []
    template = sb / "package" / "annotation_template.csv"
    saved = template.read_text(encoding="utf-8")
    template.write_text(saved.replace("pilot-002,,,", "pilot-002,,,mixed,", 1), encoding="utf-8", newline="")
    rewrite_manifest_hash(sb, "annotation_template.csv")
    assert any("annotation_template.csv" in p for p in b.verify())


def test_a_template_with_an_extra_column_missing_rows_or_reordered_ids_is_rejected(sb):
    for label, mutate in (("extra column", lambda t: t.replace("note", "note,expected", 1)), ("dropped row", lambda t: "\n".join(t.splitlines()[:-1]) + "\n"),
                          ("swapped ids", lambda t: t.replace("pilot-001", "pilot-TMP", 1).replace("pilot-002", "pilot-001", 1).replace("pilot-TMP", "pilot-002", 1))):
        with pytest.raises(ValueError):
            (sb / "annotator" / "annotation_template.csv").write_bytes(mutate((PACK / "annotator" / "annotation_template.csv").read_text(encoding="utf-8")).encode("utf-8"))
            b.build(None)


# ------------------------------------------------------------------ determinism, including line endings

def snapshot(sb):
    return {p.name: p.read_bytes() for p in sorted((sb / "package").iterdir())}, (sb / "author_only" / "DRAFT_MANIFEST.json").read_bytes()


def test_repeated_builds_are_byte_identical_and_independent_of_the_working_directory(sb, monkeypatch, tmp_path_factory):
    b.build(None)
    first = snapshot(sb)
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))
    b.build(None)
    assert snapshot(sb) == first
    assert not re.search(rb'"[a-z_]*(time|date|created|generated|host|user|path)[a-z_]*"', first[1], re.IGNORECASE)


def test_windows_and_unix_line_endings_give_the_same_package_and_manifest(sb):
    b.build(None)
    lf = snapshot(sb)
    for path in [*(sb / "annotator").iterdir(), sb / "docs" / "RUBRIC.md"]:
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))        # every source and the rubric checked out with CRLF
    assert b.verify() == []                                                                          # the existing package still verifies against CRLF sources
    shutil.rmtree(sb / "package")
    b.build(None)
    assert snapshot(sb) == lf


# ------------------------------------------------------------------ the participant register

def reg(tmp_path, rows, header=b.REGISTER_COLUMNS, encoding="utf-8"):
    path = tmp_path / "register.csv"
    with path.open("w", encoding=encoding, newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


OK = [("A-01", "annotator", "yes", "2026-10-21"), ("A-02", "annotator", "yes", "2026-10-21"), ("J-01", "adjudicator", "yes", "2026-10-21")]


def test_a_complete_register_passes_and_a_utf8_bom_from_a_spreadsheet_is_tolerated(tmp_path):
    assert b.check_register(reg(tmp_path, OK)) == []                                                 # CONTROL
    assert b.check_register(reg(tmp_path, OK, encoding="utf-8-sig")) == []


@pytest.mark.parametrize("rows, expected", [
    ([OK[0], OK[1], ("J-01", "adjudicator", "yes", "")], "attestation date"),
    ([OK[0], OK[1], ("J-01", "adjudicator", "yes", "21/10/2026")], "attestation date"),
    ([OK[0], OK[1], ("J-01", "adjudicator", "yes", "not a date")], "attestation date"),
    ([OK[0], OK[1], ("J-01", "adjudicator", "", "2026-10-21")], "not attested independent"),
    ([OK[0], OK[1], ("J-01", "adjudicator", "y", "2026-10-21")], "not attested independent"),
    ([OK[0], OK[1], ("J-01", "adjudicator", "no", "2026-10-21")], "not attested independent"),
    ([OK[0], ("A-01", "annotator", "yes", "2026-10-21"), OK[2]], "unique"),
    ([OK[0], ("a-01 ", "annotator", "yes", "2026-10-21"), OK[2]], "unique"),
    ([OK[0], OK[1], ("A-02", "adjudicator", "yes", "2026-10-21")], "unique"),
    ([OK[0], OK[1], ("", "adjudicator", "yes", "2026-10-21")], "unique"),
    ([OK[0], OK[2]], "need 2 independent annotators, register has 1"),
    ([OK[0], OK[1]], "need 1 independent adjudicator, register has 0"),
    ([], "need 2 independent annotators, register has 0"),
    ([OK[0], OK[1], ("J-01", "reviewer", "yes", "2026-10-21")], "must be annotator or adjudicator"),
])
def test_a_register_missing_an_attestation_or_failing_independence_blocks_distribution(tmp_path, rows, expected):
    blockers = b.check_register(reg(tmp_path, rows))
    assert blockers and any(expected in x for x in blockers), blockers


def test_role_and_independence_matching_ignores_case_and_surrounding_whitespace_only(tmp_path):
    assert b.check_register(reg(tmp_path, [(" A-01 ", " Annotator ", " YES ", " 2026-10-21 "), OK[1], OK[2]])) == []
    assert b.check_register(reg(tmp_path, [(" A-01 ", " Annotator ", " yep ", "2026-10-21"), OK[1], OK[2]]))


def test_register_files_that_are_missing_wrongly_shaped_or_not_files_are_blocked(tmp_path):
    assert any("not found" in x for x in b.check_register(tmp_path / "nope.csv"))
    assert any("not found" in x for x in b.check_register(tmp_path))                                  # a directory is not a register
    assert any("exactly the columns" in x for x in b.check_register(reg(tmp_path, [], header=("annotator_code", "role"))))
    assert any("exactly the columns" in x for x in b.check_register(reg(tmp_path, [], header=(*b.REGISTER_COLUMNS, "name"))))
    assert any("exactly the columns" in x for x in b.check_register(reg(tmp_path, [], header=tuple(reversed(b.REGISTER_COLUMNS)))))
    assert b.check_register(None) and "not yet identified" in b.check_register(None)[0]


def test_a_blocked_register_never_sets_distribution_ready_and_a_complete_one_never_freezes(sb, tmp_path):
    blocked = b.build(reg(tmp_path, OK[:2]))
    assert blocked["distribution_ready"] is False and blocked["distribution_blockers"]
    ready = b.build(reg(tmp_path, OK))
    assert ready["distribution_ready"] is True and ready["frozen"] is False and ready["annotation_status"] == "NOT STARTED"
    assert "cannot verify independence" in ready["independence_attestation_note"] and "A-01" not in json.dumps(ready)      # self-attested; codes are not copied into the manifest
    assert b.verify() == []


def test_the_cli_refuses_cleanly_instead_of_crashing(sb, tmp_path, capsys):
    (sb / "docs" / "RUBRIC.md").write_text("no markers here", encoding="utf-8")
    assert b.main([]) == 2
    out = capsys.readouterr().out
    assert "BUILD REFUSED" in out and "Traceback" not in out
    (sb / "docs" / "RUBRIC.md").write_text(f"{S} fine {E}", encoding="utf-8")
    assert b.main(["--verify"]) == 1 and "package or manifest is missing" in capsys.readouterr().out


def test_symlink_handling_is_exercised_without_needing_the_privilege_to_create_one(sb, monkeypatch):
    """Creating a real symlink needs a privilege on Windows (the test above is skipped there), so the filesystem is made to REPORT one instead; the builder's decision logic is the same."""
    built(sb)
    real_is_symlink = Path.is_symlink
    package_file, source_file = sb / "package" / "INSTRUCTIONS.md", sb / "annotator" / "INSTRUCTIONS.md"

    monkeypatch.setattr(Path, "is_symlink", lambda self: True if self == package_file else real_is_symlink(self))
    problems = b.verify()
    assert any("INSTRUCTIONS.md is not a regular file" in p for p in problems)
    assert not any("contains author-only" in p and "INSTRUCTIONS.md" in p for p in problems)           # it is not even read through the link
    monkeypatch.setattr(Path, "is_symlink", real_is_symlink)
    assert b.verify() == []                                                                          # CONTROL

    monkeypatch.setattr(Path, "is_symlink", lambda self: True if self == source_file else real_is_symlink(self))
    with pytest.raises(ValueError, match="regular file"):
        b.build(None)
    monkeypatch.setattr(Path, "is_symlink", real_is_symlink)
    b.build(None)
    assert b.verify() == []
