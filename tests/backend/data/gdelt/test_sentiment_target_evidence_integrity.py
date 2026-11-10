"""Target-bound polarity evidence, policy provenance and approval-guard integrity. SYNTHETIC fixtures only: the labels below are test inputs, never real annotations, and prove nothing about any model."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment import polarity_validation as pv
from wealthpilot.data.gdelt.sentiment import tone_baseline as tb
from wealthpilot.data.gdelt.sentiment.policy import REQUIRED_POLICIES

_spec = importlib.util.spec_from_file_location("_wp_world_tgt", Path(__file__).with_name("test_sentiment_orchestrator.py"))
W = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = W
_spec.loader.exec_module(W)
UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def cands(n=30):
    specs = []
    for i in range(n):
        title = f"Synthetic headline number {i:03d} about nothing real"
        specs.append({"page_title": title, "title_hash": hashlib.sha256(title.encode()).hexdigest(), "member_rates_us": "1" if i % 2 else "0"})
    return [x for iv in W.World({W.IN_D2: specs}).run().intervals for x in iv.records]


CS = cands()
SAMPLE = pv.draw_validation_sample(CS, excluded_ids=frozenset(), per_theme=6, seed=42, min_chars=20)
ROWS = pv.annotation_rows(SAMPLE, CS)
EXPORT = pv.annotation_export_sha256(ROWS)


def labels(target="market_direction", themes=("equity_us", "rates_us"), label="positive", **over):
    return [pv.ReferenceLabel(a, label, pv.HUMAN_INDEPENDENT, T0, t, over.get("target", target), over.get("export", EXPORT))
            for t in themes for a in SAMPLE.by_theme[t]]


def preds(labs, label="positive", construct="market_direction"):
    seen, out = set(), []
    for lab in labs:
        if lab.article_id not in seen:
            seen.add(lab.article_id)
            out.append(pv.Prediction(lab.article_id, label, T0 + timedelta(days=1), "m", "r1", construct))
    return out


def run(labs, ps=None, **kw):
    return pv.validate_target_evidence(labs, preds(labs) if ps is None else ps, **{"target": "market_direction", "sample": SAMPLE, "export_sha256": EXPORT,
                                                                                 "excluded_ids": frozenset(), "min_labelled": 4, **kw})


# ================================================================ target-bound evidence

def test_evidence_is_per_theme_bound_to_the_sample_and_export_and_names_its_target():
    ev = run(labels(themes=("equity_us",)))
    assert ev.target == "market_direction" and ev.sample_sha256 == SAMPLE.manifest_sha256 and ev.export_sha256 == EXPORT and ev.verdict == pv.VERDICT
    assert set(ev.by_theme) == {t for t in SAMPLE.by_theme if SAMPLE.by_theme[t]}
    assert ev.by_theme["equity_us"].status == "COMPUTED_DESCRIPTIVE" and ev.by_theme["rates_us"].status == "INSUFFICIENT_EVIDENCE" and ev.by_theme["rates_us"].n_labelled == 0
    assert ev.by_theme["rates_us"].accuracy is None and ev.by_theme["rates_us"].macro_f1 is None            # an unlabelled theme gets no score, not a zero


def test_missing_absent_or_unbound_evidence_is_refused():
    with pytest.raises(pv.PolarityEvidenceError, match="no reference labels"):
        run([])
    with pytest.raises(pv.PolarityEvidenceError, match="target must be"):
        run(labels(), target="sentiment")
    with pytest.raises(pv.PolarityEvidenceError, match="constructs are never pooled"):
        run(labels() + labels(target="wording_tone", themes=("rates_us",)))
    with pytest.raises(pv.PolarityEvidenceError, match="annotation export"):
        run(labels(export="0" * 64))
    with pytest.raises(pv.PolarityEvidenceError, match="annotation export"):
        run([dataclasses.replace(lab, export_sha256=None) for lab in labels()])
    stray = [pv.ReferenceLabel("SYN-not-sampled", "positive", pv.HUMAN_INDEPENDENT, T0, "equity_us", "market_direction", EXPORT)]
    with pytest.raises(pv.PolarityEvidenceError, match="frozen validation sample"):
        run(labels() + stray)
    wrong_theme = [dataclasses.replace(lab, theme="gold") for lab in labels(themes=("equity_us",))[:1]]
    with pytest.raises(pv.PolarityEvidenceError, match="frozen validation sample"):
        run(labels() + wrong_theme)


def test_independence_freezing_and_overlap_checks_still_apply():
    with pytest.raises(pv.PolarityEvidenceError, match="human-independent"):
        run([dataclasses.replace(lab, labeller_kind="ai_suggestion") for lab in labels()])
    late = [dataclasses.replace(lab, frozen_at_utc=T0 + timedelta(days=2)) for lab in labels()]
    with pytest.raises(pv.PolarityEvidenceError, match="frozen strictly before"):
        run(late)
    with pytest.raises(pv.PolarityEvidenceError, match="overlap"):
        run(labels(), excluded_ids=frozenset({SAMPLE.by_theme["equity_us"][0]}))


def test_wording_and_market_direction_are_never_compared_without_an_approved_mapping():
    labs = labels()
    mismatched = preds(labs, construct="wording_tone")
    with pytest.raises(pv.PolarityEvidenceError, match="no approved mapping"):
        run(labs, mismatched)
    with pytest.raises(pv.PolarityEvidenceError, match="no approved mapping"):
        run(labs, mismatched, construct_mapping="invented_mapping_v1")
    assert pv.APPROVED_CONSTRUCT_MAPPINGS == frozenset() and pv.TARGETS == ("wording_tone", "market_direction")
    ok = run(labels(target="wording_tone"), preds(labels(target="wording_tone"), construct="wording_tone"), target="wording_tone")
    assert ok.target == "wording_tone"


def test_the_export_hash_binds_the_exact_content_and_ignores_row_order():
    assert pv.annotation_export_sha256(list(reversed(ROWS))) == EXPORT
    changed = [dict(ROWS[0], title=ROWS[0]["title"] + " ")] + ROWS[1:]
    assert pv.annotation_export_sha256(changed) != EXPORT
    assert pv.annotation_export_sha256(ROWS[1:]) != EXPORT


# ================================================================ policy provenance and approval guards

def test_every_required_policy_has_a_provenance_and_none_is_applied():
    assert set(REQUIRED_POLICIES) <= set(orc.POLICY_PROVENANCE) and all(orc.POLICY_PROVENANCE[n].strip() for n in REQUIRED_POLICIES)
    applied = [n for n in REQUIRED_POLICIES if orc.POLICY_STATUS[n].startswith("APPLIED")]
    assert len(applied) == 7 and orc.POLICY_STATUS["scorer_approval_and_polarity_validation"] == "UNRESOLVED_NOT_APPLIED"
    assert {n for n in REQUIRED_POLICIES if orc.POLICY_STATUS[n] == "APPLIED_APPROVED"} == {"cross_interval_story_uniqueness", "scoring_coverage_threshold"}   # the rest are provisional
    assert all(orc.POLICY_PROVENANCE[n].startswith("worksheet: owner") for n in REQUIRED_POLICIES)
    with pytest.raises(TypeError):
        orc.POLICY_STATUS["late_batch_strictness"] = "APPLIED_APPROVED"                 # type: ignore[index]
    with pytest.raises(TypeError):
        orc.POLICY_PROVENANCE["late_batch_strictness"] = "x"                            # type: ignore[index]


def test_the_tone_mapping_approval_cannot_change_by_accident():
    with pytest.raises(dataclasses.FrozenInstanceError):
        tb.APPROVED_MAPPING.approved = False                                            # type: ignore[misc]
    with pytest.raises(TypeError):
        tb.ToneMapping("gdelt_tone_mean_v0", "mean_tone_of_valid_records")              # type: ignore[call-arg]   # no default: approval is always stated explicitly
    assert tb.ToneMapping.__dataclass_fields__["approved"].default is dataclasses.MISSING
    assert tb.APPROVED_MAPPING.status == "OWNER_APPROVED_DESCRIPTIVE_BASELINE" and tb.APPROVED_MAPPING.aggregate == "mean_tone_of_valid_records"
