"""Validation-sample drawing, the annotation export and per-theme evidence, plus the stage-blocker map. SYNTHETIC fixtures only: no label or prediction here is real, and nothing reads a label store or key."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment import pipeline as pl
from wealthpilot.data.gdelt.sentiment import polarity_validation as pv
from wealthpilot.data.gdelt.sentiment.policy import APPLIED_APPROVED, REQUIRED_POLICIES, PolicyState

_spec = importlib.util.spec_from_file_location("_wp_world_val", Path(__file__).with_name("test_sentiment_orchestrator.py"))
W = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = W
_spec.loader.exec_module(W)
UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def row(i, **over):
    title = f"Synthetic headline number {i:03d} about nothing real"
    return {"page_title": title, "title_hash": hashlib.sha256(title.encode()).hexdigest(), **over}


def cands(n=40):
    specs = [row(i, member_rates_us="1" if i % 2 else "0", member_gold="1" if i % 5 == 0 else "0") for i in range(n)]
    specs += [row(900, member_equity_us="0"), row(901, page_title="x", title_hash=hashlib.sha256(b"x").hexdigest())]      # no theme; too-short text
    return [x for i in W.World({W.IN_D2: specs}).run().intervals for x in i.records]


# ================================================================ sample drawing

def test_the_sample_is_deterministic_seeded_and_drawn_only_from_scorable_theme_candidates():
    cs = cands()
    a = pv.draw_validation_sample(cs, excluded_ids=frozenset(), per_theme=5, seed=42, min_chars=20)
    assert a == pv.draw_validation_sample(list(reversed(cs)), excluded_ids=frozenset(), per_theme=5, seed=42, min_chars=20)       # input order is irrelevant
    assert a.by_theme != pv.draw_validation_sample(cs, excluded_ids=frozenset(), per_theme=5, seed=43, min_chars=20).by_theme       # the seed changes the draw
    assert all(len(v) == 5 for v in a.by_theme.values()) and a.shortfall == {"equity_us": 0, "rates_us": 0, "gold": 0}
    by_id = {c.article_id: c for c in cs}
    for theme, ids in a.by_theme.items():
        assert all(by_id[i].theme_flags[theme] and by_id[i].text_status == "ok" for i in ids) and len(set(ids)) == 5
    assert a.pool_sizes["equity_us"] == 40 and a.pool_sizes["rates_us"] == 20 and a.pool_sizes["gold"] == 8        # the no-theme and short-text rows never enter a pool


def test_the_overlap_exclusion_set_is_honoured_and_a_shortfall_is_reported_not_filled():
    cs = cands()
    first = pv.draw_validation_sample(cs, excluded_ids=frozenset(), per_theme=5, seed=7, min_chars=20)
    banned = frozenset(first.by_theme["gold"][:3]) | frozenset(first.by_theme["equity_us"])
    b = pv.draw_validation_sample(cs, excluded_ids=banned, per_theme=8, seed=7, min_chars=20)
    assert not (set(sum(b.by_theme.values(), ())) & banned) and b.n_excluded_in_pool > 0
    assert b.shortfall["gold"] == 8 - len(b.by_theme["gold"]) and b.shortfall["gold"] > 0
    with pytest.raises(pv.PolarityEvidenceError):
        pv.draw_validation_sample(cs, excluded_ids={"x"}, per_theme=5, seed=1, min_chars=20)            # type: ignore[arg-type]
    for bad in (dict(per_theme=0), dict(per_theme=True), dict(seed=1.5), dict(seed=None)):
        with pytest.raises(pv.PolarityEvidenceError):
            pv.draw_validation_sample(cs, **{"excluded_ids": frozenset(), "per_theme": 5, "seed": 1, "min_chars": 20, **bad})


def test_the_annotation_export_carries_only_id_theme_and_title():
    cs = cands()
    s = pv.draw_validation_sample(cs, excluded_ids=frozenset(), per_theme=3, seed=42, min_chars=20)
    rows = pv.annotation_rows(s, cs)
    assert len(rows) == 9 and all(set(r) == {"article_id", "theme", "title"} for r in rows)
    assert not any(k in r for r in rows for k in ("tone", "positive", "negative", "polarity", "label", "pred_label", "p_positive", "model_id"))
    text = (Path(__file__).resolve().parents[4] / "backend/wealthpilot/data/gdelt/sentiment/polarity_validation.py").read_text(encoding="utf-8")
    assert "open(" not in text.split('"""', 2)[2] and "read_text" not in text.split('"""', 2)[2]


# ================================================================ per-theme evidence

def labels_for(theme, pairs, frozen=T0, kind=pv.HUMAN_INDEPENDENT):
    return [pv.ReferenceLabel(f"{theme}-{i}", r, kind, frozen, theme) for i, (r, _) in enumerate(pairs)]


def preds_for(theme, pairs):
    return [pv.Prediction(f"{theme}-{i}", p, None if p == "unavailable" else T0 + timedelta(days=1), "m", "r1") for i, (_, p) in enumerate(pairs)]


def test_evidence_is_computed_per_theme_and_themes_never_pool():
    eq = [("positive", "positive")] * 5 + [("negative", "positive")] * 2
    ra = [("negative", "negative")] * 4
    labs = labels_for("equity_us", eq) + labels_for("rates_us", ra)
    preds = preds_for("equity_us", eq) + preds_for("rates_us", ra)
    out = pv.validate_polarity_by_theme(labs, preds, excluded_ids=frozenset(), min_labelled=4)
    assert set(out) == {"equity_us", "rates_us"} and out["equity_us"].n_scored == 7 and out["rates_us"].n_scored == 4
    assert out["equity_us"].accuracy.point == pytest.approx(5 / 7) and out["rates_us"].accuracy.point == 1.0
    assert all(e.verdict == pv.VERDICT for e in out.values())
    thin = pv.validate_polarity_by_theme(labs, preds, excluded_ids=frozenset(), min_labelled=5)
    assert thin["equity_us"].status == "COMPUTED_DESCRIPTIVE" and thin["rates_us"].status == "INSUFFICIENT_EVIDENCE"


def test_a_label_without_a_theme_or_with_ai_provenance_is_rejected_in_the_per_theme_check():
    base = labels_for("gold", [("positive", "positive")] * 4)
    with pytest.raises(pv.PolarityEvidenceError, match="theme"):
        pv.validate_polarity_by_theme([pv.ReferenceLabel("a", "positive", pv.HUMAN_INDEPENDENT, T0)] + base, [], excluded_ids=frozenset(), min_labelled=1)
    with pytest.raises(pv.PolarityEvidenceError, match="human-independent"):
        pv.validate_polarity_by_theme(labels_for("gold", [("positive", "positive")] * 4, kind="ai_suggestion"), [], excluded_ids=frozenset(), min_labelled=1)


# ================================================================ which gate blocks which stage

LIVE = PolicyState.from_mapping(orc.POLICY_STATUS)
ALL = PolicyState.from_mapping({n: APPLIED_APPROVED for n in REQUIRED_POLICIES})


def test_each_downstream_stage_names_its_current_blockers():
    g = pl.blocking_gates(LIVE)
    assert g["tone_derived"] == ("scorer_approval_and_polarity_validation=UNRESOLVED_NOT_APPLIED",)           # derived tone keeps the all-eight gate; seven are applied
    assert g["scoring"] == ("scorer_approval_and_polarity_validation=UNRESOLVED_NOT_APPLIED", "no approved, installed scorer or weights (E1)")
    assert set(g["tone_derived"]) <= set(g["features"]) and "daily features not authorised (E4)" in g["features"] and "no approved, installed scorer or weights (E1)" in g["features"]
    assert set(g["features"]) <= set(g["evaluation"]) and any("E5" in x for x in g["evaluation"])


def test_with_every_policy_applied_only_the_non_policy_blockers_remain():
    g = pl.blocking_gates(ALL)
    assert g["tone_derived"] == () and g["scoring"] == ("no approved, installed scorer or weights (E1)",)
    assert g["features"] == ("no approved, installed scorer or weights (E1)", "daily features not authorised (E4)")
    assert len(g["evaluation"]) == 3


def test_the_pipeline_reports_the_same_blockers_as_the_map():
    r = pl.run_pipeline(W.World({W.IN_D2: [row(1)]}).inputs())
    g = pl.blocking_gates(r.window.policy_state())
    assert {x for x in r.stage("features").reasons if "=" in x} == {x for x in g["features"] if "=" in x}
    assert {x for x in r.stage("tone_derived").reasons if "=" in x} == set(g["tone_derived"])
