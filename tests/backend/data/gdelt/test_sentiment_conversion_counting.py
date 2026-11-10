"""Owner decisions E3a/E3b/E3c, OD-11a/b/c: the candidate → scored-record contract and the primary-versus-sensitivity counting.

Synthetic only. The stub scorer is not a model; no model, file, key or network is touched. The conversion and counting rules are the owner's; nothing here applies a policy gate.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import features as ft
from wealthpilot.data.gdelt.sentiment import scored_records as sr
from wealthpilot.data.gdelt.sentiment import scorer_port as sp
from wealthpilot.data.gdelt.sentiment.policy import APPLIED_APPROVED, PolicyBlockedError, PolicyState
from wealthpilot.data.gdelt.sentiment.schema import ArticleRecord, validate


def load(name, alias):
    spec = importlib.util.spec_from_file_location(alias, Path(__file__).with_name(name))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


W = load("test_sentiment_orchestrator.py", "_wp_world_conv")
S = load("test_sentiment_scaffold.py", "_wp_scaffold_conv")
UTC = timezone.utc
SHA = "b" * 64
IDENT = sp.ScorerIdentity("UNIT_TEST_STUB_NOT_A_MODEL", "stub-0", SHA, SHA, {"LABEL_0": "positive", "LABEL_1": "negative", "LABEL_2": "neutral"})
SCORER_APPLIED = PolicyState.from_mapping({sp.SCORER_POLICY: APPLIED_APPROVED})          # a TEST FIXTURE: nothing in production builds this
SCORED_AT = datetime(2026, 1, 1, tzinfo=UTC)


class Stub:
    identity = IDENT

    def __init__(self):
        self.texts = []

    def score_batch(self, texts):
        self.texts += list(texts)
        return [{"LABEL_0": 0.1, "LABEL_1": 0.2, "LABEL_2": 0.7}] * len(texts)


def row(title="SYNTHETIC headline about nothing real", **over):
    """A synthetic day-file row whose recorded hash is the hash of its title, as in the real files."""
    return {"page_title": title, "title_hash": hashlib.sha256(title.encode()).hexdigest(), **over}


def candidates(specs):
    r = W.World({W.IN_D2: specs}).run()
    return [x for i in r.intervals for x in i.records]


def mixed():
    """theme+ok, theme+ok duplicate, theme+ok syndicated, theme+short, theme+empty, no-theme+ok, no-theme+short."""
    return candidates([
        row("Alpha headline long enough here"),
        row("Alpha headline long enough here two", mech_dup="DUP_SAME_BATCH"),
        row("Alpha headline long enough here three", mech_dup="SYNDICATED_SAME_BATCH"),
        row("tiny"),
        row(""),
        row("A non theme headline long enough", member_equity_us="0"),
        row("tiny", member_equity_us="0"),
    ])


# ================================================================ E3a / E3b: what is scored and what is converted

def test_only_ok_text_with_a_theme_flag_is_scored_and_duplicates_are_included():
    cs = mixed()
    chosen = sr.scoring_inputs(cs, min_chars=20)
    assert [c.same_batch_status for c in chosen] == ["ORIGINAL", "DUP_SAME_BATCH", "SYNDICATED_SAME_BATCH"]
    assert all(c.text_status == "ok" and sr.has_theme(c) for c in chosen)
    assert len(cs) == 7


def test_conversion_covers_every_theme_candidate_and_reports_the_rest_without_converting_them():
    cs, stub = mixed(), Stub()
    chosen = sr.scoring_inputs(cs, min_chars=20)
    outcomes = sp.score_candidates(chosen, stub, policy=SCORER_APPLIED, min_chars=20)
    res = sr.convert(cs, outcomes, IDENT, scored_at=SCORED_AT, min_chars=20)
    assert len(stub.texts) == 3                                                           # the short, empty and non-theme texts never reached the scorer
    assert [r.pred_label for r in res.records] == ["neutral", "neutral", "neutral", "unavailable", "unavailable"]
    assert [r.unavailable_reason for r in res.records][3:] == ["text_short", "text_empty"]       # existing text_* reasons
    assert [(n.reason) for n in res.not_converted] == [sr.NOT_THEME_RELEVANT] * 2 and len(res.not_converted) == 2
    assert {n.article_id for n in res.not_converted}.isdisjoint({r.article_id for r in res.records})
    assert all(isinstance(r, ArticleRecord) and validate(r) is r for r in res.records)


def test_field_mapping_is_exact_and_carries_no_story_claim():
    cs = mixed()
    outcomes = sp.score_candidates(sr.scoring_inputs(cs, min_chars=20), Stub(), policy=SCORER_APPLIED, min_chars=20)
    res = sr.convert(cs, outcomes, IDENT, scored_at=SCORED_AT, min_chars=20)
    for rec, c in zip(res.records, [x for x in cs if sr.has_theme(x)]):
        assert rec.story_id == f"UNLINKED:{c.article_id}" == sr.unlinked_story_id(c.article_id)        # record-specific, not a story identity
        assert rec.dup_status == c.same_batch_status                                                  # the only relation the day files carry
        assert (rec.article_id, rec.batch_ts, rec.available_at_utc, rec.availability_status, rec.source_domain) == (
            c.article_id, c.batch_ts, c.available_at_utc, "verified", c.source_domain)
        assert rec.title_sha256 == c.title_sha256_raw == hashlib.sha256(c.title.encode()).hexdigest()
        assert dict(rec.theme_flags) == dict(c.theme_flags) and (rec.model_id, rec.model_revision) == (IDENT.model_id, IDENT.model_revision)
    assert len({r.story_id for r in res.records}) == len(res.records)
    assert not hasattr(res.records[0], "page_publication") and not any("pub" in f.name for f in dataclasses.fields(ArticleRecord))


def test_scored_records_carry_the_given_time_and_unavailable_ones_carry_none():
    cs = mixed()
    outcomes = sp.score_candidates(sr.scoring_inputs(cs, min_chars=20), Stub(), policy=SCORER_APPLIED, min_chars=20)
    res = sr.convert(cs, outcomes, IDENT, scored_at=SCORED_AT, min_chars=20)
    assert [r.scored_at_utc for r in res.records] == [SCORED_AT] * 3 + [None, None]
    with pytest.raises(Exception, match="scored_at"):
        sr.convert(cs, outcomes, IDENT, scored_at=datetime(2026, 1, 1), min_chars=20)               # naive time
    with pytest.raises(Exception, match="before|earlier"):
        sr.convert(cs, outcomes, IDENT, scored_at=cs[0].available_at_utc - timedelta(seconds=1), min_chars=20)


def test_a_scorer_failure_stays_unavailable_and_is_never_neutral():
    cs = candidates([row("Alpha headline long enough here")])
    failed = (sp.ScoreOutcome(cs[0].article_id, "unavailable", None, "scorer_failure"),)
    rec = sr.convert(cs, failed, IDENT, scored_at=SCORED_AT, min_chars=20).records[0]
    assert (rec.pred_label, rec.unavailable_reason, rec.p_positive, rec.p_negative, rec.p_neutral, rec.scored_at_utc) == ("unavailable", "scorer_failure", None, None, None, None)


def test_conversion_fails_closed_on_inconsistent_inputs():
    cs = candidates([row("Alpha headline long enough here"), row("Beta headline long enough here too")])
    outs = list(sp.score_candidates(sr.scoring_inputs(cs, min_chars=20), Stub(), policy=SCORER_APPLIED, min_chars=20))
    for bad_outs in (outs[:1], outs + [sp.ScoreOutcome("SYN-extra", "unavailable", None, "scorer_failure")], outs + outs[:1]):
        with pytest.raises(sr.ConversionError):
            sr.convert(cs, bad_outs, IDENT, scored_at=SCORED_AT, min_chars=20)
    wrong_status = [dataclasses.replace(cs[0], text_status="short")] + cs[1:]
    with pytest.raises(sr.ConversionError, match="contradicts"):
        sr.convert(wrong_status, outs, IDENT, scored_at=SCORED_AT, min_chars=20)
    wrong_hash = [dataclasses.replace(cs[0], title_sha256_raw="0" * 64)] + cs[1:]
    with pytest.raises(sr.ConversionError, match="hash"):
        sr.convert(wrong_hash, outs, IDENT, scored_at=SCORED_AT, min_chars=20)
    with pytest.raises(sr.ConversionError, match="unique"):
        sr.convert(cs + cs[:1], outs, IDENT, scored_at=SCORED_AT, min_chars=20)


def test_conversion_is_deterministic():
    cs = mixed()
    outs = sp.score_candidates(sr.scoring_inputs(cs, min_chars=20), Stub(), policy=SCORER_APPLIED, min_chars=20)
    assert sr.convert(cs, outs, IDENT, scored_at=SCORED_AT, min_chars=20) == sr.convert(cs, outs, IDENT, scored_at=SCORED_AT, min_chars=20)


# ================================================================ OD-11c: primary unit versus sensitivity comparison

def comparison(arts):
    return ft.aggregate_daily_with_sensitivity(arts, S.DAYS, S.slots_for(arts), config=S.CFG, earlier=S.EXAMINED_NONE)


def test_the_primary_unit_counts_every_eligible_record_and_the_sensitivity_removes_repeats():
    arts = [S.art(1, S.IN_D2), S.art(2, S.IN_D2, dup="DUP_SAME_BATCH"), S.art(3, S.IN_D2, dup="SYNDICATED_SAME_BATCH"), S.art(4, S.IN_D2)]
    c = comparison(arts)
    p, q = S.row(c.primary, S.D2), S.row(c.sensitivity, S.D2)
    assert (p.n_eligible, p.n_duplicates_removed) == (4, 0) and (q.n_eligible, q.n_duplicates_removed) == (2, 2)
    assert p.n_scored == 4 and q.n_scored == 2 and p.coverage_status == q.coverage_status == "ok"
    d = next(x for x in c.differences() if x.origin_date == S.D2 and x.theme == "equity_us")
    assert (d.n_eligible_primary, d.n_eligible_sensitivity, d.n_removed_in_sensitivity) == (4, 2, 2)
    assert (c.primary_unit, c.sensitivity_unit) == ("every_eligible_record", "proposed_dedup_policy")


def test_each_run_equals_a_plain_aggregation_with_the_same_policy_and_the_sensitivity_is_the_current_policy():
    arts = [S.art(1, S.IN_D2), S.art(2, S.IN_D2, dup="DUP_SAME_BATCH")]
    c = comparison(arts)
    assert c.primary == tuple(S.aggregate(arts, S.DAYS, S.slots_for(arts), config=dataclasses.replace(S.CFG, dedup=ft.PRIMARY_DEDUP_POLICY)))
    assert c.sensitivity == tuple(S.aggregate(arts, S.DAYS, S.slots_for(arts), config=dataclasses.replace(S.CFG, dedup=ft.PROPOSED_DEDUP_POLICY)))
    assert ft.PRIMARY_DEDUP_POLICY.duplicate_statuses == frozenset() and ft.PRIMARY_DEDUP_POLICY.status == "PROVISIONAL_OWNER_SELECTED"
    assert ft.PROPOSED_DEDUP_POLICY.duplicate_statuses == {"DUP_SAME_BATCH", "SYNDICATED_SAME_BATCH", "REOBSERVATION", "SYNDICATED"}   # unchanged


def test_unlinked_records_make_no_story_level_claim_and_each_counts_in_its_own_interval():
    arts = [dataclasses.replace(S.art(1, S.IN_D2), story_id="UNLINKED:SYN-0001"), dataclasses.replace(S.art(2, S.IN_D3), story_id="UNLINKED:SYN-0002")]
    c = comparison(arts)
    d2, d3 = S.row(c.primary, S.D2), S.row(c.primary, S.D3)
    assert (d2.n_eligible, d2.n_distinct_stories, d3.n_eligible, d3.n_distinct_stories) == (1, 1, 1, 1)        # ALLOWED across intervals: once per availability interval
    assert d2.dedup_status == "none_found"


def test_the_comparison_changes_no_gate_and_the_policy_guard_still_applies():
    arts = [S.art(1, S.IN_D2), S.art(2, S.IN_D2, dup="DUP_SAME_BATCH")]
    empty = comparison([])
    assert S.row(empty.primary, S.D2).no_news is True and S.row(empty.sensitivity, S.D2).no_news is True
    live = dataclasses.replace(S.CFG, policy=PolicyState.from_mapping({n: "UNRESOLVED_NOT_APPLIED" for n in S.pol.REQUIRED_POLICIES}))
    with pytest.raises(PolicyBlockedError):
        ft.aggregate_daily_with_sensitivity(arts, S.DAYS, S.slots_for(arts), config=live, earlier=S.EXAMINED_NONE)
