"""Mutation checks on the regression tests themselves (2026-10-20): a test that only ever passes proves nothing. For each repaired regex and each control-character test, the REAL test code is run
against (a) a clean fixture, which must pass, and (b) a deliberately constructed bad fixture or mutation, which must make it FAIL. This is how the original defect (a backspace character where a regex
word boundary was meant, silently making three checks inert) would have been caught.

Local, deterministic, standard library only; the bad fixtures live in temporary directories and in monkeypatched module attributes, never in the repository.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BS = chr(92)
BACKSPACE = chr(8)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def regex_literals(source_path: Path, function: str) -> list[str]:
    """The string literals passed as the first argument of re.search/re.match/re.compile inside one test function, taken from the test's own source."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function)
    found = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("search", "match", "compile") and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.append(first.value)
    return found


def mutate_boundaries(pattern: str) -> str:
    """The original defect: every regex word boundary replaced by a backspace character."""
    return pattern.replace(BS + "b", BACKSPACE)


def hits(pattern: str, samples: list[str]) -> list[bool]:
    compiled = re.compile(pattern, re.IGNORECASE)
    return [bool(compiled.search(s)) for s in samples]


# ------------------------------------------------------------------ the builder's leak patterns

def test_the_leak_pattern_test_fails_on_a_backspace_mutant_and_passes_on_the_real_patterns():
    audit = load_module("audit_mod_leak", ROOT / "tests" / "backend" / "scripts" / "test_dry_run_package_audit.py")
    audit.test_the_leak_patterns_are_live_and_use_real_word_boundaries()                                  # CONTROL: passes on the real patterns
    real = audit.builder.FORBIDDEN_PATTERNS
    mutant = tuple(re.compile(mutate_boundaries(p.pattern)) for p in real)
    assert any(BACKSPACE in p.pattern for p in mutant)
    audit.builder.FORBIDDEN_PATTERNS = mutant
    try:
        with pytest.raises(AssertionError):
            audit.test_the_leak_patterns_are_live_and_use_real_word_boundaries()                          # the mutant must be caught
    finally:
        audit.builder.FORBIDDEN_PATTERNS = real
    audit.builder.FORBIDDEN_PATTERNS = (re.compile("never matches anything"),)
    try:
        with pytest.raises(AssertionError):
            audit.test_the_leak_patterns_are_live_and_use_real_word_boundaries()                          # a pattern that matches nothing is caught too
    finally:
        audit.builder.FORBIDDEN_PATTERNS = real


def test_the_verification_leak_test_fails_when_the_leak_rules_are_weakened(tmp_path):
    """The package-level leak checks are behavioural: with the real rules a planted owner/consent sentence is flagged; with emptied rules it is not, so the test that asserts the flag would fail."""
    builder = load_module("builder_mut", ROOT / "scripts" / "build_dry_run_package.py")
    text = "See the recommended O2 default and the consent record. Probe A5. <!-- c -->"
    assert len(builder.leak_problems("x.md", text)) >= 4                                                  # CONTROL
    builder.FORBIDDEN_IN_PACKAGE, builder.FORBIDDEN_PATTERNS = (), ()
    assert builder.leak_problems("x.md", text) == []                                                      # weakened rules flag nothing, which the adversarial tests would notice


# ------------------------------------------------------------------ the numeric-threshold regex in the pilot test

THRESHOLD_BAD = ["at least 3 annotators are needed", "a minimum of two raters", "no fewer than ten texts", "kappa >= 0.7 is required", "precision of 70%", "agreement 0.8", "accuracy < 0.5", "95 %"]
THRESHOLD_GOOD = ["Pick the sample size from the stated assumptions.", "The owner supplies every threshold.", "Cohen's kappa per field, and its minimum chosen by the owner.", "two independent annotators and one adjudicator"]


PILOT_TEST = ROOT / "tests" / "backend" / "core" / "test_user_text_pilot_pack.py"
ADAPTER_TEST = ROOT / "tests" / "backend" / "data" / "gdelt" / "test_anthropic_adapter.py"


def check_threshold_regex(source: Path) -> None:
    literals = [lit for lit in regex_literals(source, "test_the_packet_invents_no_numeric_threshold") if "%" in lit]
    assert len(literals) == 1, literals
    pattern = literals[0]
    assert BACKSPACE not in pattern and (BS + "b") in pattern                                              # the repaired source has real word boundaries
    assert all(hits(pattern, THRESHOLD_BAD)), [s for s, h in zip(THRESHOLD_BAD, hits(pattern, THRESHOLD_BAD)) if not h]
    assert not any(hits(pattern, THRESHOLD_GOOD)), [s for s, h in zip(THRESHOLD_GOOD, hits(pattern, THRESHOLD_GOOD)) if h]
    mutant = mutate_boundaries(pattern)
    caught = hits(mutant, THRESHOLD_BAD)
    assert not all(caught)                                                                                  # the backspace mutant misses invented thresholds: this sample set detects the defect
    assert [s for s, h in zip(THRESHOLD_BAD, caught) if not h]                                              # and names which ones it would have missed


def test_the_real_pilot_test_threshold_regex_passes_the_effectiveness_check():
    check_threshold_regex(PILOT_TEST)


def test_a_copy_of_the_pilot_test_with_backspaces_for_boundaries_or_a_weakened_regex_fails_the_check(tmp_path):
    original = PILOT_TEST.read_text(encoding="utf-8")
    assert BS + "b" in original
    broken = tmp_path / "backspace_copy.py"
    broken.write_text(original.replace(BS + "b", BACKSPACE), encoding="utf-8")                          # the original defect, reproduced
    with pytest.raises(AssertionError):
        check_threshold_regex(broken)
    weakened = tmp_path / "weakened_copy.py"
    assert "at least" in original
    weakened.write_text(original.replace("at least|", "", 1).replace("(at least|", "(", 1), encoding="utf-8")       # the regex no longer catches "at least N"
    with pytest.raises(AssertionError):
        check_threshold_regex(weakened)


# ------------------------------------------------------------------ the GDELT adapter's `.env` assertion

def check_adapter_regex(source: Path) -> None:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    patterns = [n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "search" and n.args
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str) and "env" in n.args[0].value]
    assert len(patterns) == 1, patterns
    pattern = patterns[0]
    assert BACKSPACE not in pattern
    must_match = ["open('.env')", "load_dotenv('/repo/.env')", 'path = ".env"', "p / '.env'"]
    must_not_match = ["os.environ['KEY']", "os.environ.get('KEY')", "environment variable", "the .environment folder"]
    assert all(hits(pattern, must_match)), [s for s, h in zip(must_match, hits(pattern, must_match)) if not h]
    assert not any(hits(pattern, must_not_match)), [s for s, h in zip(must_not_match, hits(pattern, must_not_match)) if h]
    mutant = mutate_boundaries(pattern)
    assert BACKSPACE in mutant and not any(hits(mutant, must_match))                                      # the mutant could never fail, so a test using it proves nothing


def test_the_real_adapter_test_dotenv_regex_passes_the_effectiveness_check():
    check_adapter_regex(ADAPTER_TEST)


def test_a_copy_of_the_adapter_test_with_a_backspace_or_a_never_matching_regex_fails_the_check(tmp_path):
    original = ADAPTER_TEST.read_text(encoding="utf-8")
    needle = BS + ".env" + BS + "b"
    assert original.count(needle) == 1
    for label, replacement in (("backspace", BS + ".env" + BACKSPACE), ("never matches", BS + ".envNEVER" + BS + "b"), ("wrong anchor", BS + ".env$")):
        copy = tmp_path / f"{label.replace(' ', '_')}.py"
        copy.write_text(original.replace(needle, replacement), encoding="utf-8")
        with pytest.raises(AssertionError):
            check_adapter_regex(copy)


# ------------------------------------------------------------------ the control-character tests

def make_clean_tree(root: Path) -> None:
    """A tree with the shape the two control-character tests walk, every file clean."""
    for top in ("tests", "scripts", "backend", "training"):
        (root / top).mkdir(parents=True, exist_ok=True)
    for i in range(205):
        (root / "tests" / f"test_{i}.py").write_text("x = 1\n", encoding="utf-8")
    for rel in ("scripts/a.py", "scripts/b.ps1", "tests/backend/scripts/t.py", "tests/backend/core/test_user_text_pilot_pack.py", "tests/backend/core/test_user_text_sentiment.py",
                "tests/backend/core/test_user_text_rubric_examples.py", "docs/USER_TEXT_ANNOTATION_RUBRIC.md", "docs/USER_TEXT_VALIDATION_DECISION_SHEET.md",
                "datasets/rubric_examples/pilot_pack_v0/README.md"):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("clean\ttext\nsecond line\r\n", encoding="utf-8", newline="")


@pytest.fixture()
def audit_module(tmp_path):
    module = load_module("audit_mod_ctrl", ROOT / "tests" / "backend" / "scripts" / "test_dry_run_package_audit.py")
    make_clean_tree(tmp_path)
    module.ROOT = tmp_path
    module.PACK = tmp_path / "datasets" / "rubric_examples" / "pilot_pack_v0"
    return module, tmp_path


def plant(path: Path, byte: int) -> None:
    path.write_bytes(path.read_bytes() + bytes([byte]) + b"\n")


@pytest.mark.parametrize("byte", [8, 0, 27, 7, 11])
def test_the_repo_wide_control_character_test_fails_on_a_planted_control_byte_and_passes_when_clean(audit_module, byte):
    module, root = audit_module
    module.test_no_python_source_in_the_repository_contains_a_stray_control_character()                    # CONTROL: clean tree passes (tab, LF, CR allowed)
    for victim in ("tests/test_17.py", "scripts/a.py", "tests/backend/scripts/t.py"):
        path = root / victim
        original = path.read_bytes()
        plant(path, byte)
        with pytest.raises(AssertionError):
            module.test_no_python_source_in_the_repository_contains_a_stray_control_character()
        path.write_bytes(original)
    module.test_no_python_source_in_the_repository_contains_a_stray_control_character()                    # restored: passes again


def test_the_repo_wide_control_character_test_allows_form_feeds_and_refuses_a_too_small_tree(audit_module):
    module, root = audit_module
    (root / "tests" / "test_ff.py").write_bytes(b"x = 1\n\x0c\ny = 2\n")                                  # a form feed is legitimate in Python source
    module.test_no_python_source_in_the_repository_contains_a_stray_control_character()
    for extra in range(0, 205):
        (root / "tests" / f"test_{extra}.py").unlink(missing_ok=True)
    with pytest.raises(AssertionError):
        module.test_no_python_source_in_the_repository_contains_a_stray_control_character()                # an empty walk must not count as a pass


@pytest.mark.parametrize("victim", ["scripts/a.py", "scripts/b.ps1", "tests/backend/scripts/t.py", "tests/backend/core/test_user_text_pilot_pack.py", "tests/backend/core/test_user_text_sentiment.py",
                                    "tests/backend/core/test_user_text_rubric_examples.py", "docs/USER_TEXT_ANNOTATION_RUBRIC.md", "docs/USER_TEXT_VALIDATION_DECISION_SHEET.md",
                                    "datasets/rubric_examples/pilot_pack_v0/README.md"])
def test_the_document_and_script_control_character_test_fails_on_a_planted_backspace_in_any_listed_file(audit_module, victim):
    module, root = audit_module
    module.test_new_scripts_tests_and_docs_contain_no_stray_control_characters()                           # CONTROL
    plant(root / victim, 8)
    with pytest.raises(AssertionError):
        module.test_new_scripts_tests_and_docs_contain_no_stray_control_characters()


# ------------------------------------------------------------------ the control-character scan really covers the files that were once damaged

def test_the_originally_damaged_files_are_clean_and_inside_the_scanned_trees():
    damaged = ["tests/backend/core/test_user_text_pilot_pack.py", "tests/backend/data/gdelt/test_anthropic_adapter.py", "scripts/build_dry_run_package.py", "docs/TEST_PLAN.md"]
    for rel in damaged:
        data = (ROOT / rel).read_bytes()
        assert bytes([8]) not in data, rel
    scanned_roots = {"tests", "scripts", "backend", "training"}
    assert all(rel.split("/")[0] in scanned_roots for rel in damaged if rel.endswith(".py"))
