"""Annotation utilities: double-annotation assignment, agreement, adjudication, MIX/UNC handling and the freeze manifest.

Every label below is a SYNTHETIC test fixture. None is a human annotation, and nothing here says anything about any model. The real-sample test only builds the sample and its files in a temporary folder
(read-only on the dataset; it reads one id column of the overlap manifest, never a label)."""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import annotation_tools as at
from wealthpilot.data.gdelt.sentiment import polarity_validation as pv

ROOT = Path(__file__).resolve().parents[4]
UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def load(path, alias):
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


W = load(Path(__file__).with_name("test_sentiment_orchestrator.py"), "_wp_world_ann")


def cands(n=40):
    specs = []
    for i in range(n):
        title = f"Synthetic headline number {i:03d} about nothing real"
        specs.append({"page_title": title, "title_hash": hashlib.sha256(title.encode()).hexdigest(), "member_rates_us": "1" if i % 2 else "0", "member_gold": "1" if i % 5 == 0 else "0"})
    return [x for iv in W.World({W.IN_D2: specs}).run().intervals for x in iv.records]


CS = cands()
SAMPLE = pv.draw_validation_sample(CS, excluded_ids=frozenset(), per_theme=10, seed=42, min_chars=20)
ROWS = pv.annotation_rows(SAMPLE, CS)
TARGET = "market_direction"
EXPORT = at.target_export_sha256(TARGET, ROWS)
INSTR = "i" * 64
PROTO = "p" * 64
ASSIGN = at.assign_double_annotation(SAMPLE, fraction=0.2, seed=42)
ITEMS = [(i, t) for t in at.THEMES for i in SAMPLE.by_theme[t]]


def ann(items, who, code_of, **over):
    base = dict(target=TARGET, annotator_type="human", label_basis="own", instruction_sha256=INSTR, export_sha256=EXPORT, labelled_at_utc=T0)
    return [at.AnnotationRecord(i, t, annotator_id=who, code=code_of(i, t), **{**base, **over}) for i, t in items]


def doubles():
    return [(i, t) for t in at.THEMES for i in ASSIGN.double[t]]


def freeze(primary=None, secondary=None, adjud=(), **over):
    primary = primary if primary is not None else ann(ITEMS, "AA", lambda i, t: "POS")
    secondary = secondary if secondary is not None else ann(doubles(), "BB", lambda i, t: "POS")
    kw = dict(target=TARGET, sample=SAMPLE, export_sha256=EXPORT, instruction_sha256=INSTR, assignment=ASSIGN, annotations=primary + secondary, adjudications=list(adjud),
              primary_annotator="AA", secondary_annotator="BB", protocol_sha256=PROTO, frozen_at_utc=T0 + timedelta(days=1))
    return at.build_freeze_manifest(**{**kw, **over})


def adj(item, theme, code, **over):
    return at.AdjudicationRecord(item, theme, TARGET, "CC", code, True, T0 + timedelta(hours=1), **over) if not over else at.AdjudicationRecord(item, theme, TARGET, **over)


# ================================================================ assignment

def test_double_assignment_is_deterministic_per_theme_and_ceil_of_the_fraction():
    a = at.assign_double_annotation(SAMPLE, fraction=0.2, seed=42)
    assert a == at.assign_double_annotation(SAMPLE, fraction=0.2, seed=42) and a != at.assign_double_annotation(SAMPLE, fraction=0.2, seed=43)
    assert dict(a.n_double) == {"equity_us": 2, "rates_us": 2, "gold": 2} and a.not_feasible == ()          # ceil(0.2 * 10) = 2; gold has 8 items: ceil(1.6) = 2
    assert all(set(a.double[t]) <= set(SAMPLE.by_theme[t]) for t in at.THEMES)
    rebound = at.assign_double_annotation(dataclasses.replace(SAMPLE, manifest_sha256="x" * 64), fraction=0.2, seed=42)
    assert rebound.double == a.double and rebound.sha256 != a.sha256                                           # the assignment hash binds the sample manifest
    thin = dataclasses.replace(SAMPLE, by_theme={**SAMPLE.by_theme, "gold": SAMPLE.by_theme["gold"][:3]})
    t = at.assign_double_annotation(thin, fraction=0.2, seed=42)
    assert t.double["gold"] == () and t.not_feasible == ("gold",)                                              # reported, never padded
    for bad in (dict(fraction=0.0), dict(fraction=1), dict(seed=1.5)):
        with pytest.raises(at.AnnotationError):
            at.assign_double_annotation(SAMPLE, **{"fraction": 0.2, "seed": 42, **bad})


# ================================================================ agreement

def test_cohen_kappa_known_values_and_undefined_cases():
    perfect = at.cohen_kappa([("POS", "POS"), ("NEG", "NEG"), ("NEU", "NEU"), ("POS", "POS")], at.CODES)
    assert (perfect.n, perfect.observed, perfect.kappa) == (4, 1.0, 1.0)
    k = at.cohen_kappa([("POS", "POS")] * 20 + [("POS", "NEG")] * 5 + [("NEG", "POS")] * 10 + [("NEG", "NEG")] * 15, ("POS", "NEG"))      # textbook example
    assert k.kappa == pytest.approx(0.4) and k.observed == pytest.approx(0.7)
    assert at.cohen_kappa([("POS", "POS")] * 5, at.CODES).kappa is None                                       # chance agreement is 1: undefined, not 1.0
    assert at.cohen_kappa([], at.CODES).kappa is None and at.cohen_kappa([], at.CODES).n == 0
    assert at.cohen_kappa([("MIX", "UNC")] * 3 + [("POS", "POS")] * 3, at.CODES).observed == 0.5            # MIX and UNC are different answers


# ================================================================ freeze: the success path

def test_a_complete_valid_set_freezes_and_the_hash_is_deterministic_and_ignores_the_timestamp():
    d = doubles()
    secondary = ann(d, "BB", lambda i, t: "NEG" if (i, t) == d[0] else "POS")                                 # one disagreement ...
    m = freeze(secondary=secondary, adjud=[adj(d[0][0], d[0][1], "UNC")])                                     # ... adjudicated to UNC
    assert m.protocol_status == "PROPOSAL_NOT_APPROVED" and m.treatment == at.NOT_COMPARABLE_TREATMENT
    assert m.final_codes[d[0]] == "UNC" and sum(sum(v.values()) for v in m.counts.values()) == len(ITEMS)
    again = freeze(secondary=secondary, adjud=[adj(d[0][0], d[0][1], "UNC")], frozen_at_utc=T0 + timedelta(days=9))
    assert again.sha256 == m.sha256 and again.frozen_at_utc != m.frozen_at_utc                                 # timestamps are recorded, never relied on
    changed = freeze(secondary=secondary, adjud=[adj(d[0][0], d[0][1], "NEG")])
    assert changed.sha256 != m.sha256
    other = freeze(primary=ann(ITEMS, "AA", lambda i, t: "NEU"), secondary=ann(d, "BB", lambda i, t: "NEU"))
    assert other.sha256 != m.sha256 and other.agreement["equity_us"]["all_codes"].kappa is None             # all NEU: chance agreement 1: kappa undefined


def test_agreement_is_reported_on_the_double_labelled_items_with_mix_and_unc_distinct():
    d = doubles()
    p = ann(ITEMS, "AA", lambda i, t: "MIX" if (i, t) in d[:2] else "POS")
    s = ann(d, "BB", lambda i, t: "UNC" if (i, t) == d[0] else ("MIX" if (i, t) == d[1] else "POS"))
    m = freeze(primary=p, secondary=s, adjud=[adj(d[0][0], d[0][1], at.UNRESOLVED)])
    eq = m.agreement["equity_us"]
    assert eq["all_codes"].n == 2 and eq["all_codes"].observed == 0.5 and eq["comparable"].n == 0                  # (MIX, UNC) differ, (MIX, MIX) agree; neither is comparable
    assert m.counts["equity_us"]["UNRESOLVED"] == 1 and m.n_unresolved["equity_us"] == 1 and d[0] not in m.final_codes     # unresolved: excluded and counted
    assert m.final_codes[d[1]] == "MIX"                                                                         # MIX stays MIX; it is not NEU, not UNC


def test_comparable_labels_exclude_mix_and_unc_and_feed_the_target_evidence_with_the_counts_beside_them():
    codes = {}
    for k, (i, t) in enumerate(ITEMS):
        codes[(i, t)] = ("MIX", "UNC", "POS", "NEG", "NEU")[k % 5]
    p = ann(ITEMS, "AA", lambda i, t: codes[(i, t)])
    s = ann(doubles(), "BB", lambda i, t: codes[(i, t)])
    m = freeze(primary=p, secondary=s)
    labs = at.comparable_reference_labels(m)
    assert {lab.label for lab in labs} == {"positive", "negative", "neutral"} and len(labs) == sum(1 for c in codes.values() if c in at.COMPARABLE)
    assert all(lab.labeller_kind == pv.HUMAN_INDEPENDENT and lab.target == TARGET and lab.export_sha256 == EXPORT and lab.frozen_at_utc == m.frozen_at_utc for lab in labs)
    nc = at.not_comparable_counts(m)
    assert sum(nc[t]["MIX"] for t in at.THEMES) == sum(1 for c in codes.values() if c == "MIX") and sum(nc[t]["UNC"] for t in at.THEMES) == sum(1 for c in codes.values() if c == "UNC")
    preds = [pv.Prediction(i, "positive", T0 + timedelta(days=2), "m", "r1", TARGET) for i in {i for i, _ in ITEMS}]
    ev = pv.validate_target_evidence(labs, preds, target=TARGET, sample=SAMPLE, export_sha256=EXPORT, excluded_ids=frozenset(), min_labelled=2)
    assert ev.by_theme["equity_us"].n_labelled == sum(1 for (i, t), c in codes.items() if t == "equity_us" and c in at.COMPARABLE)       # MIX/UNC never enter
    bd = at.not_comparable_prediction_breakdown(m, preds)
    assert sum(sum(c.values()) for t in bd.values() for c in t.values()) == sum(1 for c in codes.values() if c in at.NOT_COMPARABLE)
    assert at.not_comparable_prediction_breakdown(m, [])["equity_us"]["MIX"]["no_prediction"] >= 0


# ================================================================ freeze refusals

@pytest.mark.parametrize("name", ["missing_primary", "extra_annotator", "secondary_missing", "secondary_extra", "ai_basis", "ai_type", "email", "wrong_export", "wrong_instruction",
                                  "off_sample", "bad_code", "wrong_target", "duplicate", "naive_time", "empty"])
def test_the_freeze_refuses_every_malformed_unbound_or_incomplete_label_set(name):
    d = doubles()
    full, sec = ann(ITEMS, "AA", lambda i, t: "POS"), ann(d, "BB", lambda i, t: "POS")
    cases = {
        "missing_primary": dict(primary=full[:-1]),
        "extra_annotator": dict(secondary=sec + ann(d[:1], "ZZ", lambda i, t: "POS")),
        "secondary_missing": dict(secondary=sec[:-1]),
        "secondary_extra": dict(secondary=sec + ann([ITEMS[0]] if ITEMS[0] not in d else [ITEMS[1]], "BB", lambda i, t: "POS")),
        "ai_basis": dict(primary=ann(ITEMS, "AA", lambda i, t: "POS", label_basis="accepted_ai")),
        "ai_type": dict(primary=ann(ITEMS, "AA", lambda i, t: "POS", annotator_type="ai")),
        "email": dict(primary=ann(ITEMS, "a@b.c", lambda i, t: "POS"), primary_annotator="a@b.c"),
        "wrong_export": dict(primary=ann(ITEMS, "AA", lambda i, t: "POS", export_sha256="0" * 64)),
        "wrong_instruction": dict(primary=ann(ITEMS, "AA", lambda i, t: "POS", instruction_sha256="0" * 64)),
        "off_sample": dict(primary=full + ann([("SYN-not-sampled", "equity_us")], "AA", lambda i, t: "POS")),
        "bad_code": dict(primary=ann(ITEMS, "AA", lambda i, t: "MAYBE")),
        "wrong_target": dict(primary=ann(ITEMS, "AA", lambda i, t: "POS", target="wording_tone")),
        "duplicate": dict(primary=full + full[:1]),
        "naive_time": dict(primary=ann(ITEMS, "AA", lambda i, t: "POS", labelled_at_utc=datetime(2026, 1, 1))),
        "empty": dict(primary=[], secondary=[]),
    }
    kw = cases[name]
    if "primary" in kw and "secondary" not in kw:
        kw["secondary"] = sec
    with pytest.raises(at.FreezeRefused):
        freeze(**kw)


def test_the_freeze_refuses_undecided_or_unattested_disagreements_and_foreign_assignments():
    d = doubles()
    disagree = ann(d, "BB", lambda i, t: "NEG" if (i, t) == d[0] else "POS")
    with pytest.raises(at.FreezeRefused, match="cover exactly the disagreements"):
        freeze(secondary=disagree)                                                                             # no adjudication
    with pytest.raises(at.FreezeRefused, match="cover exactly the disagreements"):
        freeze(adjud=[adj(d[1][0], d[1][1], "POS")])                                                           # adjudicating an agreement
    with pytest.raises(at.FreezeRefused, match="attestation"):
        freeze(secondary=disagree, adjud=[at.AdjudicationRecord(d[0][0], d[0][1], TARGET, "CC", "POS", False, T0)])
    with pytest.raises(at.FreezeRefused, match="not valid"):
        freeze(secondary=disagree, adjud=[adj(d[0][0], d[0][1], "MAYBE")])
    with pytest.raises(at.FreezeRefused, match="repeated|wrong target"):
        freeze(secondary=disagree, adjud=[adj(d[0][0], d[0][1], "POS"), adj(d[0][0], d[0][1], "NEG")])
    other_sample = pv.draw_validation_sample(CS, excluded_ids=frozenset(), per_theme=5, seed=7, min_chars=20)
    with pytest.raises(at.FreezeRefused, match="does not belong"):
        freeze(assignment=at.assign_double_annotation(other_sample, fraction=0.2, seed=42))                    # an assignment made for a different sample
    with pytest.raises(at.FreezeRefused, match="target must be"):
        freeze(target="sentiment")


def test_there_is_no_second_annotator_when_none_is_declared_and_no_double_subset_is_assigned():
    solo_assign = at.DoubleAssignment(0.2, 42, {t: () for t in at.THEMES}, {t: 0 for t in at.THEMES}, (), at.assign_double_annotation(SAMPLE, fraction=0.2, seed=42).sha256)
    with pytest.raises(at.FreezeRefused, match="does not belong"):
        freeze(secondary=[], secondary_annotator=None, assignment=solo_assign)                                 # a tampered assignment (no double subset) is refused whole


def test_target_export_hashes_are_target_bound_and_order_independent():
    a, b = at.target_export_sha256("wording_tone", ROWS), at.target_export_sha256("market_direction", ROWS)
    assert a != b and a == at.target_export_sha256("wording_tone", list(reversed(ROWS)))
    with pytest.raises(at.AnnotationError):
        at.target_export_sha256("sentiment", ROWS)


# ================================================================ the real sample (read-only; builds files in a temp folder)

SAMPLE_DIR = ROOT / "datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1"


@pytest.mark.skipif(not (SAMPLE_DIR / "review_files" / "annotation_B.csv").exists(), reason="the local development sample is not present")
def test_the_build_script_is_deterministic_private_and_reports_actual_pools(tmp_path, monkeypatch):
    script = load(ROOT / "scripts" / "build_sentiment_validation_sample.py", "_wp_build_script")
    runs = []
    for k in range(2):
        out = tmp_path / f"run{k}"
        monkeypatch.setattr(script, "OUT", out)
        assert script.main() == 0
        runs.append(out)
    assert script.main() == 1                                                                                   # an existing output folder is never overwritten
    names = sorted(p.name for p in runs[0].iterdir())
    assert names == sorted(p.name for p in runs[1].iterdir())
    for n in names:
        assert (runs[0] / n).read_bytes() == (runs[1] / n).read_bytes(), n                                      # byte-identical across runs
    m = json.loads((runs[0] / "sample_manifest.json").read_text(encoding="utf-8"))
    assert m["seed"] == 42 and m["per_theme_requested"] == 200 and m["sampled"]["equity_us"] == 200 and m["sampled"]["rates_us"] == 200
    assert m["sampled"]["gold"] == m["pool_sizes_after_exclusions"]["gold"] < 200 and m["shortfall"]["gold"] == 200 - m["sampled"]["gold"]
    assert m["shortfall"]["equity_us"] == m["shortfall"]["rates_us"] == 0 and m["metrics_protocol_status"] == "PROPOSAL_NOT_APPROVED"
    assert m["exclusion_control"]["columns_read"] == ["gkg_record_id"] and m["exclusion_control"]["n_ids"] == 312
    for name, digest in m["output_file_sha256"].items():
        assert hashlib.sha256((runs[0] / name).read_bytes()).hexdigest() == digest, name                       # hash integrity
    sampled = {i for ids in m["sample_ids"].values() for i in ids}
    with (SAMPLE_DIR / "review_files" / "annotation_B.csv").open(encoding="utf-8", newline="") as fh:
        overlap = {row["gkg_record_id"] for row in csv.DictReader(fh)}
    assert not (sampled & overlap)                                                                              # the D13 overlap items are excluded
    for target in at.TARGETS:
        with (runs[0] / f"annotation_{target}_primary.csv").open(encoding="utf-8", newline="") as fh:
            rd = csv.DictReader(fh)
            assert rd.fieldnames == ["item_id", "theme", "title", "code", "note"]                               # nothing else is exported
            rows = list(rd)
        assert len(rows) == sum(m["sampled"].values()) and all(r["code"] == "" and r["note"] == "" for r in rows)
        with (runs[0] / f"annotation_{target}_secondary.csv").open(encoding="utf-8", newline="") as fh:
            sec = list(csv.DictReader(fh))
        assert len(sec) == sum(m["double_annotation"]["n_double"].values())
    text = "".join((runs[0] / n).read_text(encoding="utf-8") for n in names if n.endswith(".csv"))
    assert "tone" not in text.split("\n", 1)[0] and "p_positive" not in text
    assert (SAMPLE_DIR / "review_files" / "key_sealed.csv").exists()                                           # untouched (existence only)
