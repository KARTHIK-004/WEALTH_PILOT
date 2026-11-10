"""The recorded S1 package set (documentation guard; no network, no package, no environment). `reports/sentiment_transformer_dependency_request.md` holds TWO tables that disagree on `setuptools`:
the early candidate table of section "Hash table for S1" (setuptools 84.2.1, certifi 2026.7.22: the first proposal) and the EXECUTED hash-pinned list of section L (35 wheels, setuptools 81.0.0 accepted by the
owner on 2026-10-27, certifi 2026.10.23, installed twice with identical pins, 19 of 19 stand-in checks and 381 tests). The executed list is the authoritative one; these tests pin both facts so the discrepancy
cannot silently change, and so a later `--require-hashes` file can be checked against the record."""
from __future__ import annotations

import re
from pathlib import Path

REPORT = (Path(__file__).resolve().parents[3] / "reports" / "sentiment_transformer_dependency_request.md").read_text(encoding="utf-8")
ROW = re.compile(r"^\| ([A-Za-z0-9_.-]+) \| ([0-9][^|]*?) \| (direct|transitive|requested) \| `([^`]+)` \| [^|]+ \| `([0-9a-f]{64})` \|", re.M)
DIRECT = re.compile(r"^\| `([a-z]+)==([0-9.]+)` \| `([^`]+)` \| [^|]+ \| `([0-9a-f]{64})` \|", re.M)


def section(start: str, end: str) -> str:
    a = REPORT.index(start)
    return REPORT[a:REPORT.index(end, a)]


def norm(name: str) -> str:
    return name.lower().replace("_", "-")


def executed_list() -> dict[str, tuple[str, str]]:
    l_table = section("### L.3 Resolution, hashes and installation", "### L.4 Licence findings")
    rows = {norm(m.group(1)): (m.group(2).strip(), m.group(5)) for m in ROW.finditer(l_table)}
    direct = {norm(m.group(1)): (m.group(2), m.group(4)) for m in DIRECT.finditer(section("### M.1 Environment and wheel set", "### M.2 What the test is"))}
    return {**rows, **direct}


def early_list() -> dict[str, tuple[str, str]]:
    table = section("**Hash table for S1**", "### ")
    return {norm(m.group(1)): (m.group(2).strip(), m.group(5)) for m in ROW.finditer(table)}


def test_the_executed_list_has_35_wheels_each_with_a_sha256_and_the_owner_accepted_versions():
    pins = executed_list()
    assert len(pins) == 35, sorted(pins)
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for _, digest in pins.values())
    assert {k: v[0] for k, v in pins.items() if k in ("torch", "transformers", "tokenizers", "safetensors", "setuptools", "numpy")} == {
        "torch": "2.13.0", "transformers": "5.12.1", "tokenizers": "0.22.1", "safetensors": "0.6.2", "setuptools": "81.0.0", "numpy": "1.26.4"}
    assert pins["setuptools"][1] == "fdd925d5c5d9f62e4b74b30d6dd7828ce236fd6ed998a08d81de62ce5a6310d6"
    assert pins["certifi"][0] == "2026.10.23"                       # outside the affected range of GHSA-6q48-6c7w-9gw2 (fixed in 2026.10.19)
    assert "huggingface-hub" in pins and "hf-xet" in pins          # the dependencies the six direct packages need under --require-hashes


def test_the_early_candidate_table_is_the_source_of_the_84_2_1_discrepancy_and_it_still_names_the_affected_certifi():
    early = early_list()
    assert early["setuptools"][0] == "84.2.1" and early["certifi"][0] == "2026.7.22"
    assert 34 <= len(early) <= 36
    executed = executed_list()
    differing = sorted(k for k in set(early) & set(executed) if early[k] != executed[k])
    assert "setuptools" in differing and "certifi" in differing
    assert executed["setuptools"][0] == "81.0.0" and executed["setuptools"] != early["setuptools"]


def test_the_report_marks_the_early_table_as_superseded_and_names_the_authoritative_list():
    flat = " ".join(REPORT.split())
    for phrase in ("SUPERSEDED (2026-10-29)", "the early candidate table", "The executed 35-wheel list of section L.3 is authoritative", "setuptools==81.0.0",
                   "the owner accepted `setuptools==81.0.0` on 2026-10-27", "no version was substituted"):
        assert phrase in flat, phrase


def test_the_six_direct_packages_are_not_a_sufficient_require_hashes_set():
    pins = executed_list()
    assert len(pins) - 6 == 29                                     # 29 further wheels must be pinned for --require-hashes to succeed


def test_the_execution_section_records_all_35_wheels_with_the_authoritative_names_versions_and_hashes():
    execution = REPORT[REPORT.index("### S. Execution of the approved S1 retrieval"):]
    rows = re.findall(r"^\| ([A-Za-z0-9_.-]+) \| ([0-9][^|]*?) \| `([^`]+\.whl)` \| `([0-9a-f]{64})` \| MATCH \|", execution, re.M)
    recorded = {norm(name): (version.strip(), digest) for name, version, _, digest in rows}
    assert len(rows) == 35 and recorded == executed_list()
    flat = " ".join(execution.split())
    for phrase in ("expected 35, present 35, problems 0", "`pypi.org` and `files.pythonhosted.org`", "no source distribution", "1124 passed, 2 skipped", "the temporary Hugging Face cache path was never created",
                   "**Nothing was changed in the project environment**"):
        assert phrase in flat, phrase
