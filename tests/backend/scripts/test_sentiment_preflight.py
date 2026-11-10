"""`scripts/sentiment_preflight.py`: the read-only pre-flight for enabling the Transformer. On the REAL repository it must report the model blocked, with the owner's recorded blockers named; on INVENTED state
it must pass only when every approval, package, artifact, manifest and the owner's R14 decision are present, and it must never treat a missing item as approved. Nothing here reads a model, a dataset or user text."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("sentiment_preflight", ROOT / "scripts" / "sentiment_preflight.py")
pf = importlib.util.module_from_spec(SPEC)
sys.modules["sentiment_preflight"] = pf
SPEC.loader.exec_module(pf)                                                                      # type: ignore[union-attr]

ALL = pf.LEGAL + pf.DEPENDENCIES + pf.DATASET + pf.EVALUATION + pf.ACTIVATION
INSTALLED = {p: True for p in pf.PACKAGES}


def approved_everything() -> dict[str, str]:
    return {i: "APPROVE" for i in ALL}


def gates(answers, installed=INSTALLED, files=("model.safetensors",), manifest=True, flag=False):
    return {g["gate"].split()[0]: g for g in pf.evaluate(answers, installed, list(files), manifest, flag)}


def test_on_the_real_repository_the_transformer_is_blocked_and_the_recorded_owner_blockers_are_named():
    answers = pf.recorded_answers((ROOT / "reports" / "sentiment_consolidated_approval_form.md").read_text(encoding="utf-8"))
    result = gates(answers, {p: importlib.util.find_spec(p) is not None for p in pf.PACKAGES}, pf._model_files(), pf._frozen_manifest_exists(), False)
    assert not all(g["passed"] for k, g in result.items() if k != "7")
    legal = " ".join(result["1"]["blockers"])
    assert "A3.3: KEEP UNRESOLVED" in legal and "A3.5: REJECT" in legal                         # training-data terms unresolved, share-alike rejected
    dataset = " ".join(result["3"]["blockers"])
    assert "D20: REJECT" in dataset and "D1: KEEP UNRESOLVED" in dataset and "D5: KEEP UNRESOLVED" in dataset and "no frozen manifest exists" in dataset
    assert "F1: KEEP UNRESOLVED" in " ".join(result["6"]["blockers"])                           # R14
    assert result["7"]["passed"] is True                                                         # the safe state: the model is off


def test_the_command_exits_1_and_says_blocked_while_any_gate_is_open():
    done = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "sentiment_preflight.py"), "--json"], capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert done.returncode == 1
    report = json.loads(done.stdout)
    assert report["transformer_may_be_enabled"] is False and "enables nothing" in report["note"]
    by_number = {g["gate"].split()[0]: g for g in report["gates"]}
    for blocked in ("1", "3", "4", "6"):                                                                # legal (A3.3, A3.5), dataset (D20 ...), evaluation (E3), activation (F1) stay open
        assert not by_number[blocked]["passed"] and by_number[blocked]["blockers"], blocked
    assert by_number["5"]["passed"] is bool(pf._model_files())                                         # gate 5 only reports whether a model.safetensors exists on this machine (it verifies nothing);
    #                                                                                                    the owner-approved Stage A download (2026-11-04) put one outside the repository, so it mirrors the file system
    assert by_number["7"]["passed"] is True                                                             # production is still the rules baseline


def test_every_gate_passes_only_when_everything_is_present():
    result = gates(approved_everything())
    assert all(g["passed"] for g in result.values()) and all(not g["blockers"] for g in result.values())


def test_one_missing_item_blocks_exactly_its_gate_and_nothing_is_approved_by_omission():
    for item, gate in (("A3.3", "1"), ("C4", "2"), ("D20", "3"), ("E3", "4"), ("F1", "6")):
        for status in ("KEEP UNRESOLVED", "REJECT", "BLOCKED"):
            result = gates({**approved_everything(), item: status})
            assert [k for k, g in result.items() if not g["passed"]] == [gate], (item, status)
        missing = approved_everything()
        del missing[item]
        assert f"{item}: not recorded" in gates(missing)[gate]["blockers"]                       # an unrecorded decision is a blocker, never an approval


def test_missing_packages_artifact_manifest_and_a_switched_on_flag_each_block():
    assert [k for k, g in gates(approved_everything(), {**INSTALLED, "torch": False}).items() if not g["passed"]] == ["2"]
    assert [k for k, g in gates(approved_everything(), files=()).items() if not g["passed"]] == ["5"]
    assert [k for k, g in gates(approved_everything(), manifest=False).items() if not g["passed"]] == ["3", "4"]
    assert [k for k, g in gates(approved_everything(), flag=True).items() if not g["passed"]] == ["7"]
    assert [k for k, g in gates(approved_everything(), flag=None).items() if not g["passed"]] == ["7"]


def test_the_form_parser_reads_the_recorded_statuses_and_ignores_prose_tables():
    answers = pf.recorded_answers((ROOT / "reports" / "sentiment_consolidated_approval_form.md").read_text(encoding="utf-8"))
    assert answers["A1"] == "APPROVE" and answers["A3.2"] == "APPROVE" and answers["A3.3"] == "KEEP UNRESOLVED" and answers["A3.5"] == "REJECT" and answers["D20"] == "REJECT"
    assert set(pf.LEGAL + pf.DEPENDENCIES + pf.DATASET + pf.EVALUATION + pf.ACTIVATION) <= set(answers)


def test_the_script_reads_files_only():
    source = (ROOT / "scripts" / "sentiment_preflight.py").read_text(encoding="utf-8")
    for forbidden in ("import socket", "urllib", "requests", "httpx", "from_pretrained", "import torch", "import transformers", "subprocess", "os.system", "pickle", "write_text", "open("):
        assert forbidden not in source, forbidden
