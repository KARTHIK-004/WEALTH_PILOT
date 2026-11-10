"""Audit regressions for the fictional dry-run package (2026-10-20): the annotator excerpt contains only annotator material, the leak patterns are live, a stale package or excerpt is detected, a rebuild is
deterministic, the new scripts and tests contain no stray control characters, and the shipped language caveat states the real baseline behaviour. Offline; no database; the baseline is not run on the pilot."""

from __future__ import annotations

import importlib.util
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


builder = load("build_dry_run_package")


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """The builder pointed at a temporary copy of the annotator sources and an empty output area (the committed package is never written)."""
    shutil.copytree(PACK / "annotator", tmp_path / "annotator")
    monkeypatch.setattr(builder, "ANNOTATOR", tmp_path / "annotator")
    monkeypatch.setattr(builder, "PACKAGE", tmp_path / "package")
    monkeypatch.setattr(builder, "AUTHOR", tmp_path / "author_only")
    monkeypatch.setattr(builder, "MANIFEST", tmp_path / "author_only" / "DRAFT_MANIFEST.json")
    return tmp_path


# ------------------------------------------------------------------ the excerpt holds annotator material only

def test_the_distributed_excerpt_contains_no_owner_provenance_consent_or_pilot_wording():
    excerpt = (PACK / "package" / "RUBRIC_EXCERPT.md").read_text(encoding="utf-8")
    low = excerpt.lower()
    for word in ("provenance", "consent", "freeze", "manifest", "pilot example", "pack author", "section 5", "section 8", "adr-0", "recommended o2", "source_batch", "real_user_text", "calibration"):
        assert word not in low, word
    assert not re.search(r"\bO[1-4]\b|\bO7\b", excerpt) and "<!--" not in excerpt and "-->" not in excerpt
    assert "## 4. Record format" not in excerpt and "### Flags" in excerpt and "means one thing" in excerpt          # only the flag definitions of section 4 are included
    assert "O5" in excerpt and "O6" in excerpt                                                                      # the proposed labelling policies annotators apply are named as proposals
    assert "PROPOSED" in excerpt


def test_the_leak_patterns_are_live_and_use_real_word_boundaries():
    owner = next((p for p in builder.FORBIDDEN_PATTERNS if "O7" in p.pattern), None)
    assert owner is not None, "the owner-decision leak pattern is missing"
    assert owner.search("the recommended O2 default") and owner.search("O1.") and owner.search("(O4)") and owner.search("O7")
    assert not owner.search("TO4") and not owner.search("O5 and O6") and not owner.search("O10")                  # O5/O6 are allowed; no substring false positives
    assert "\x08" not in owner.pattern                                                                              # a backspace character was once written instead of a word boundary
    assert any(p.search("<!-- annotator-excerpt:start -->") for p in builder.FORBIDDEN_PATTERNS)


def test_verification_reports_leaked_owner_wording_even_if_the_manifest_is_rebuilt_around_it(sandbox):
    builder.build(None)
    assert builder.verify() == []
    leaked = sandbox / "package" / "INSTRUCTIONS.md"
    leaked.write_text(leaked.read_text(encoding="utf-8") + "\nSee the recommended O2 default and the consent record.\n", encoding="utf-8")
    problems = builder.verify()
    assert any("matching" in p and "INSTRUCTIONS.md" in p for p in problems) and any("'consent'" in p for p in problems)


# ------------------------------------------------------------------ marker handling and staleness

def test_missing_nested_or_unbalanced_markers_raise_instead_of_widening_the_excerpt():
    s, e = builder.EXCERPT_START, builder.EXCERPT_END
    for bad in ("no markers at all", f"{s} only a start", f"{s} {s} nested {e} {e}", f"{e} end before start {s}"):
        with pytest.raises(ValueError):
            builder.extract_annotator_rubric(bad)
    only = builder.extract_annotator_rubric(f"private {s} public one {e} private two {s} public two {e} private three")
    assert "public one" in only and "public two" in only and "private" not in only


def test_only_marked_rubric_parts_are_extracted_from_the_real_rubric():
    rubric = (ROOT / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md").read_text(encoding="utf-8")
    assert rubric.count(builder.EXCERPT_START) == rubric.count(builder.EXCERPT_END) == 2
    excerpt = builder.extract_annotator_rubric(rubric)
    for private in ("Author note (not for annotators)", "Real records additionally carry", "## 5. Separation of data", "## 6. Proposed validation protocol", "## 8. Open owner decisions", "freeze manifest"):
        assert private in rubric and private not in excerpt, private
    for public in ("## 1. Scope", "## 2. Label sets", "## 3. Decision rules", "9. **Unsupported language**", "### Flags"):
        assert public in excerpt, public


def test_a_package_copy_that_no_longer_matches_its_source_is_detected(sandbox):
    builder.build(None)
    source = sandbox / "annotator" / "INSTRUCTIONS.md"
    source.write_text(source.read_text(encoding="utf-8") + "\nA late instruction.\n", encoding="utf-8")
    assert any("differs from its source" in p and "INSTRUCTIONS.md" in p for p in builder.verify())
    builder.build(None)                                                                                            # rebuilding restores consistency
    assert builder.verify() == []


def test_an_excerpt_that_no_longer_matches_the_rubric_parts_is_detected(sandbox):
    builder.build(None)
    excerpt = sandbox / "package" / "RUBRIC_EXCERPT.md"
    excerpt.write_text(excerpt.read_text(encoding="utf-8").replace("Use it instead of guessing.", "Guess if you like."), encoding="utf-8")
    manifest = builder.json.loads(builder.MANIFEST.read_text(encoding="utf-8"))
    manifest["package_files"]["RUBRIC_EXCERPT.md"] = builder.sha256_file(excerpt)                                     # even with the manifest hash updated to hide it
    builder.MANIFEST.write_text(builder.json.dumps(manifest), encoding="utf-8")
    assert any("does not match the rubric's annotator-excerpt parts" in p for p in builder.verify())


def test_rebuilding_twice_gives_byte_identical_package_and_manifest(sandbox):
    def snapshot():
        files = {p.name: p.read_bytes() for p in (sandbox / "package").iterdir()}
        return files, builder.MANIFEST.read_bytes()

    builder.build(None)
    first = snapshot()
    builder.build(None)
    assert snapshot() == first
    assert not re.search(rb'"(created|generated|timestamp|date)[a-z_]*"', first[1])


# ------------------------------------------------------------------ hygiene and the shipped caveat

def test_new_scripts_tests_and_docs_contain_no_stray_control_characters():
    paths = [*(ROOT / "scripts").rglob("*.py"), *(ROOT / "scripts").glob("*.ps1"), *(ROOT / "tests" / "backend" / "scripts").glob("*.py"),
             ROOT / "tests/backend/core/test_user_text_pilot_pack.py", ROOT / "tests/backend/core/test_user_text_sentiment.py", ROOT / "tests/backend/core/test_user_text_rubric_examples.py",
             ROOT / "docs/USER_TEXT_ANNOTATION_RUBRIC.md", ROOT / "docs/USER_TEXT_VALIDATION_DECISION_SHEET.md", *PACK.rglob("*.md")]
    for path in paths:
        stray = sorted({b for b in path.read_bytes() if b < 32 and b not in (9, 10, 13)})
        assert not stray, (path.name, stray)               # e.g. a backspace (0x08) written where a regex word boundary was meant


# ------------------------------------------------------------------ cross-document consistency of statuses and claims

DOCS = {
    "rubric": ROOT / "docs" / "USER_TEXT_ANNOTATION_RUBRIC.md",
    "sheet": ROOT / "docs" / "USER_TEXT_VALIDATION_DECISION_SHEET.md",
    "ambiguities": PACK / "author_only" / "pre_annotation_ambiguities.md",
    "readme": PACK / "README.md",
    "annotator": PACK / "annotator" / "INSTRUCTIONS.md",
    "adjudicator": PACK / "adjudicator" / "INSTRUCTIONS.md",
}


def read(name: str) -> str:
    return DOCS[name].read_text(encoding="utf-8")


def test_the_decision_sequence_names_exactly_the_ambiguities_classified_in_the_review():
    summary = read("ambiguities").split("## Review of the proposals")[1].split("| Id |")[1]
    primary = {line.split("|")[1].strip(): line.split("|")[2].strip() for line in summary.splitlines() if line.startswith("| A")}
    steps = {int(line.split("|")[1]): line for line in read("sheet").split("## Next decisions: the smallest useful sequence")[1].splitlines() if line.startswith("| ") and line.split("|")[1].strip().isdigit()}
    named_c = set(re.findall(r"A[0-9]+", steps[2]))
    named_p = set(re.findall(r"A[0-9]+", steps[3]))
    named_t = set(re.findall(r"A[0-9]+", steps[4]))
    assert named_c == {k for k, v in primary.items() if v == "C" and k != "A7"} and named_p == {k for k, v in primary.items() if v == "P"} and named_t == {"A7", "A1"}
    assert "T" == primary["A7"]                                                                                    # the only primary taxonomy item; A1 is T only if the tone list is extended


def test_o1_and_o4_approval_is_limited_to_the_fictional_dry_run_everywhere_it_is_stated():
    manifest = builder.json.loads((PACK / "author_only" / "DRAFT_MANIFEST.json").read_text(encoding="utf-8"))["owner_decisions_in_force"]
    assert "FICTIONAL notes only" in manifest["O1"] and "real participant text collection remains prohibited" in manifest["O1"]
    assert "fictional dry run" in manifest["O4"] and "independent of the rubric author" in manifest["O4"] and "must not be called independent" in manifest["O4"]
    assert "fictional notes only" in read("sheet") and "Real participant text collection remains prohibited" in read("sheet")
    assert "accepted for fictional notes only (real participant text collection remains prohibited)" in read("readme")
    assert "O1 for fictional notes only (real participant text collection remains prohibited)" in read("rubric")


def test_unresolved_and_proposed_decisions_are_stated_the_same_way_in_every_document():
    for name in ("sheet", "readme", "rubric"):
        assert "O2, O3" in read(name) or "O2, O3 and O7" in read(name), name
    manifest = builder.json.loads((PACK / "author_only" / "DRAFT_MANIFEST.json").read_text(encoding="utf-8"))["owner_decisions_in_force"]
    assert [manifest[k] for k in ("O2", "O3", "O7")] == ["unresolved"] * 3
    assert manifest["O5"].startswith("PROPOSED, not accepted") and manifest["O6"].startswith("PROPOSED, not accepted")
    assert "O1 needs a withdrawal route, but O2's default keeps no person-to-text link" in read("sheet")
    assert "Open, owner decision" in read("sheet").replace("**", "")
    assert "blocks any future real-text collection" in builder.FUTURE_BLOCKER
    adr = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8").split("## ADR-044")[1].split("\n## ADR-")[0]
    assert "PROPOSED" in adr and "not accepted" in adr.lower() and "cannot hold for the baseline" in adr


def test_unsupported_language_is_stated_as_annotation_policy_not_as_baseline_behaviour():
    rubric = read("rubric")
    assert "Annotators label such text `uncertain`. The baseline does **not**" in rubric
    sheet = read("sheet")
    assert "the proposal holds for annotators but not for the baseline's own output" in sheet
    assert "language you cannot read" not in rubric and "whether or not you can read it" in rubric


def test_no_document_claims_agreement_annotation_validation_or_readiness_for_real_text():
    claims = (
        r"annotation (is|was|has been) (complete|completed|finished|done)", r"annotators (agreed|have agreed)\b", r"inter-?annotator agreement (was|is|of) [0-9]", r"kappa (was|is|of|=) ?[0-9]",
        r"(rubric|baseline|model) (is|was|has been) validated", r"accuracy (was|is|of) [0-9]", r"ready for real[- ]text", r"real[- ]text collection (is|has been) (approved|authori[sz]ed|ready)",
        r"rubric (is|has been) frozen", r"package (was|has been) distributed",
    )
    for name in DOCS:
        text = read(name)
        for claim in claims:
            assert not re.search(claim, text, re.IGNORECASE), (name, claim)
    assert "annotation has NOT started" in read("readme") and "NOT STARTED" in read("sheet") and "not frozen" in read("rubric")


def test_every_ambiguity_appears_in_the_hypotheses_the_review_and_nowhere_in_the_distributed_package():
    text = read("ambiguities")
    for n in range(1, 12):
        assert text.count(f"| A{n} |") == 3, n                                           # hypotheses table, class summary, detail table
    for p in (PACK / "package").iterdir():
        assert not re.search(r"\bA(1[01]|[1-9])\b", p.read_text(encoding="utf-8")), p.name


def test_no_python_source_in_the_repository_contains_a_stray_control_character():
    """A backslash sequence such as a regex word boundary can be silently written as a control character (0x08) and then never match anything. Two such cases (a package leak check and a
    no-threshold test) and one more in a safety assertion were found in an audit; this keeps the class of defect out of every Python source."""
    checked, offenders = 0, []
    for top in ("tests", "scripts", "backend", "training"):
        for path in (ROOT / top).rglob("*.py"):
            if {".venv", "venv", "site-packages", "node_modules", "__pycache__"} & set(path.parts):
                continue
            checked += 1
            stray = sorted({b for b in path.read_bytes() if b < 32 and b not in (9, 10, 13, 12)})
            if stray:
                offenders.append((path.relative_to(ROOT).as_posix(), stray))
    assert checked > 200
    assert offenders == []
