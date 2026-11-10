"""Pre-registered sample integrity, stage C gating, review files, logging, and isolation from the app."""

from __future__ import annotations

import ast
import csv
import socket
import sys
from datetime import date
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.config import ApprovalRecord
from wealthpilot.data.gdelt.engine import run_sample
from wealthpilot.data.gdelt.errors import ApprovalRefused
from wealthpilot.data.gdelt.events import EventLog
from wealthpilot.data.gdelt.review import ANNOTATION_COLUMNS, build_review
from wealthpilot.data.gdelt.sample import (
    FRAME_EXCLUDED,
    FRAME_LAST,
    STAGE_C_SHA256,
    STAGE_D_SHA256,
    SampleSlot,
    TriggerRecord,
    derive_stages,
    estimated_bytes,
    known_absent_in_frame,
    list_digest,
    load_confirmation_stage,
    load_development_stage,
    substitute,
)

PKG = Path(__file__).resolve().parents[4] / "backend" / "wealthpilot"
GDELT = PKG / "data" / "gdelt"


# ---------------------------------------------------------------- the pre-registered lists

def test_shipped_development_list_matches_the_committed_hash_and_the_algorithm():
    dev = load_development_stage()
    d, c = derive_stages(known_absent_in_frame())
    assert [s.stamp for s in dev] == d and list_digest(d) == STAGE_D_SHA256 and list_digest(c) == STAGE_C_SHA256
    assert len(set(d) | set(c)) == 384 and not set(d) & set(c)
    assert all(s <= FRAME_LAST for s in d + c) and FRAME_EXCLUDED not in d + c
    assert not (set(d + c) & known_absent_in_frame())
    assert {s.round for s in dev} == set(range(1, 9)) and {s.block for s in dev} == set(range(1, 25))
    assert 1_030_000_000 < estimated_bytes(d) < 1_040_000_000


def test_tampered_list_is_refused(tmp_path):
    from wealthpilot.data.gdelt.errors import SampleIntegrityError
    src = GDELT / "sample_data"
    for name in ("stage_d.txt", "stage_c.txt", "frame_known_absent.txt"):
        (tmp_path / name).write_text((src / name).read_text())
    lines = (tmp_path / "stage_d.txt").read_text().splitlines()
    lines[0], lines[1] = lines[1], lines[0]
    (tmp_path / "stage_d.txt").write_text("\n".join(lines) + "\n")
    with pytest.raises(SampleIntegrityError):
        load_development_stage(tmp_path)


def test_substitution_never_takes_a_confirmation_or_development_batch():
    d = {s.stamp for s in load_development_stage()}
    c = set(derive_stages(known_absent_in_frame())[1])
    sub = substitute(5, set())
    assert sub is not None and sub not in d and sub not in c
    assert substitute(5, {sub}) != sub


APPROVAL_C = ApprovalRecord("TEST", date(2026, 10, 13), "test", 2_000_000_000, STAGE_C_SHA256)


@pytest.mark.parametrize("record,approval,match", [
    (None, APPROVAL_C, "no trigger record"),
    (TriggerRecord({"EQUITY_US": 500, "RATES_US": 400, "GOLD": 150}), APPROVAL_C, "no trigger condition"),
    (TriggerRecord({"EQUITY_US": 500, "RATES_US": 400}), APPROVAL_C, "lacks counts"),
    (TriggerRecord({"EQUITY_US": 500, "RATES_US": 400, "GOLD": 150}, "gdelt_filter_v2", "evidence"), APPROVAL_C,
     "new, registered"),
    (TriggerRecord({"EQUITY_US": 500, "RATES_US": 400, "GOLD": 40}), None, "separate approval"),
    (TriggerRecord({"EQUITY_US": 500, "RATES_US": 400, "GOLD": 40}),
     ApprovalRecord("TEST", date(2026, 10, 13), "test", 2_000_000_000, STAGE_D_SHA256), "stage C list hash"),
])
def test_confirmation_stage_is_inaccessible_without_trigger_and_separate_approval(record, approval, match):
    with pytest.raises(ApprovalRefused, match=match):
        load_confirmation_stage(record, approval, available_specs={"gdelt_filter_v1"})


def test_confirmation_stage_loads_only_when_trigger_fired_and_approved():
    slots = load_confirmation_stage(TriggerRecord({"EQUITY_US": 500, "RATES_US": 400, "GOLD": 40}), APPROVAL_C,
                                    available_specs={"gdelt_filter_v1"})
    assert len(slots) == 192 and {s.round for s in slots} == set(range(9, 17))


# ---------------------------------------------------------------- review files (synthetic sample)

def test_review_files_are_blind_deterministic_and_separate_from_the_key(make_ctx, gkg, fake, tmp_path):
    US = gkg.US_CITY
    stamps = ["20220301120000", "20220302120000"]
    script = {}
    for s in stamps:
        rows = [gkg.row(s, 1, themes=["ECON_GOLDPRICE"]), gkg.row(s, 2, themes=["ECON_CENTRALBANK"], locations=[US]),
                gkg.row(s, 3, title=f"SYNTHETIC TEST ROW {s}: Wall Street"), gkg.row(s, 4, themes=["WB_2936_GOLD"]),
                gkg.row(s, 5, title=f"SYNTHETIC TEST ROW {s}: shares bought by Example LLC (NYSE:EXM)",
                        themes=["ECON_STOCKMARKET"]),
                gkg.row(s, 6, title=f"SYNTHETIC TEST ROW {s}: investors watch"), gkg.row(s, 7)]
        script |= fake.ok_script(s, gkg.zip(s, rows))
    ctx = make_ctx(keep_raw=True)
    run_sample(ctx, fake.Transport(script), [SampleSlot(s, 1, i + 1) for i, s in enumerate(stamps)],
               selection="stage_D", substitute=lambda b, u: None)
    lim = ctx.limits
    out1, out2 = tmp_path / "r1", tmp_path / "r2"
    s1 = build_review(ctx.manifest, ctx.layout.raw_keep, ctx.classifier, out1, max_uncompressed=lim.max_uncompressed_bytes,
                      max_ratio=lim.max_expansion_ratio, max_line_bytes=lim.max_line_bytes)
    s2 = build_review(ctx.manifest, ctx.layout.raw_keep, ctx.classifier, out2, max_uncompressed=lim.max_uncompressed_bytes,
                      max_ratio=lim.max_expansion_ratio, max_line_bytes=lim.max_line_bytes)
    assert s1.files == s2.files and s1.items == 14                       # deterministic; every row placed once
    assert s1.cell_rows == {"C1": 2, "C2": 2, "C3": 2, "C4": 2, "C5": 2, "C6": 2, "C7": 2}
    with open(out1 / "annotation_A.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert tuple(rows[0].keys()) == ANNOTATION_COLUMNS
    assert not {"cell", "weight", "member_gold", "captured", "themes", "tone"} & set(rows[0])
    ids = [r["item_id"] for r in rows]
    assert ids == [f"D{i:04d}" for i in range(1, len(rows) + 1)] and len(set(ids)) == len(ids)
    for r in rows:                                                    # provenance present and consistent
        assert r["gkg_record_id"].startswith(r["batch_ts"] + "-") and r["batch_ts"] in stamps
        assert r["available_at_utc"].endswith("Z") and r["title"].startswith("SYNTHETIC")
        assert r["overlap_subset"] in ("Y", "N") and r["annotator_type"] == "" and r["label_basis"] == ""
    with open(out1 / "annotation_B.csv", newline="", encoding="utf-8") as f:
        b_ids = {r["item_id"] for r in csv.DictReader(f)}
    assert b_ids == {r["item_id"] for r in rows if r["overlap_subset"] == "Y"}
    assert (out1 / "key_sealed.csv").exists()
    text = (out1 / "ANNOTATION_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "Do not open" in text and "never independent human ground truth" in text


# ---------------------------------------------------------------- logging and isolation

def test_event_log_refuses_free_text_keys(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    log.emit("slot_parsed", batch_ts="20220301120000", rows=3)
    with pytest.raises(ValueError):
        log.emit("oops", title="SYNTHETIC title must never reach a log")
    assert "SYNTHETIC" not in (tmp_path / "e.jsonl").read_text()


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_package_imports_only_stdlib_pyyaml_and_itself():
    allowed_stdlib = set(sys.stdlib_module_names)
    for path in GDELT.rglob("*.py"):                       # includes the ai/ subpackage
        for name in _imports(path):
            top = name.split(".")[0]
            ok = (top in allowed_stdlib or top == "yaml" or name.startswith("wealthpilot.data.gdelt")
                  or name == "wealthpilot.data")
            assert ok, f"{path.name} imports {name}"
            assert "sqlalchemy" not in name and "wealthpilot.db" not in name and "wealthpilot.api" not in name


def test_no_application_module_imports_the_tool():
    offenders = []
    for path in PKG.rglob("*.py"):
        if GDELT in path.parents:
            continue
        if any("gdelt" in n for n in _imports(path)):
            offenders.append(str(path))
    assert offenders == []
    assert "gdelt" not in (PKG / "data" / "__init__.py").read_text(encoding="utf-8")


def test_network_guard_is_installed_for_every_test():
    # the autouse fixture replaced these; calling them would raise and fail the test afterwards
    assert socket.create_connection.__name__ == "refuse"
    assert socket.getaddrinfo.__name__ == "refuse"
    assert socket.socket.connect.__name__ == "refuse"
