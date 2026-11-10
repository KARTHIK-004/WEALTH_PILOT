"""The local GDELT tone baseline: raw-value validation, provenance, counts, and the BLOCKED derived-polarity layer.

Document-level lexicon tone is not title sentiment and not market direction. Synthetic fixtures are tests, never findings; the one real-sample test is read-only and checks only data validity.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import math
import sqlite3
import sys
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.filters import load_spec
from wealthpilot.data.gdelt.sentiment import dayfile_adapter as da
from wealthpilot.data.gdelt.sentiment import manifest_adapter as ma
from wealthpilot.data.gdelt.sentiment import pipeline as pl
from wealthpilot.data.gdelt.sentiment import tone_baseline as tb
from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment.completeness import IntervalUsability
from wealthpilot.data.gdelt.sentiment.policy import APPLIED_APPROVED, REQUIRED_POLICIES, PolicyBlockedError, PolicyState

_spec = importlib.util.spec_from_file_location("_wp_world_tone", Path(__file__).with_name("test_sentiment_orchestrator.py"))
W = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = W
_spec.loader.exec_module(W)

PKG = Path(__file__).resolve().parents[4] / "backend/wealthpilot/data/gdelt/sentiment"
SAMPLE = Path(__file__).resolve().parents[4] / "datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1"


def tone(t, p, n, pol=None):
    """Four tone columns for a synthetic row: tone = p - n and polarity = p + n unless overridden."""
    return {"tone": repr(float(t)), "positive": repr(float(p)), "negative": repr(float(n)), "polarity": repr(float(p + n if pol is None else pol))}


def world(specs, **kw):
    return W.World({W.IN_D2: specs}, **kw)


def observations(specs):
    r = world(specs).run()
    return r, [tb.observe_tone(x) for i in r.intervals for x in i.records]


# ================================================================ validation of the raw values

@pytest.mark.parametrize("raw,status", [
    (("-1.5", "2.0", "3.5", "5.5"), "valid"), (("0", "0", "0", "0"), "valid"), (("0.0", "0.0", "0.0", "0.0"), "valid"),
    (("", "", "", ""), "missing"), (("  ", "", " ", ""), "missing"),
    (("1", "", "", ""), "invalid"), (("", "2", "1", "3"), "invalid"),
    (("a", "2", "1", "3"), "invalid"), (("1", "nan", "0", "1"), "invalid"), (("inf", "2", "1", "3"), "invalid"),
    (("nan", "0", "0", "0"), "invalid"), (("0", "0", "0", "nan"), "invalid"),
    (("-1", "-1", "0", "-1"), "invalid"), (("101", "101", "0", "101"), "invalid"), (("0", "200", "200", "400"), "invalid"),
    (("1.0", "2.0", "3.5", "5.5"), "invalid"), (("-1.5", "2.0", "3.5", "6.0"), "invalid"),
    (("1", "2", "3"), "invalid"), (("1", "2", "3", "4", "5"), "invalid"),
])
def test_each_raw_pattern_has_exactly_one_status_and_only_valid_ones_have_values(raw, status):
    got, reasons, values = tb.validate_raw(raw)
    assert got == status and (values is not None) == (status == "valid") and bool(reasons) == (status == "invalid")


def test_the_relations_hold_within_the_documented_tolerance_and_no_further():
    assert tb.validate_raw(("-1.5000000000001", "2.0", "3.5", "5.5"))[0] == "valid"         # ~1e-13, like the sample
    assert tb.validate_raw(("-1.4999", "2.0", "3.5", "5.5"))[0] == "invalid"


def test_missing_and_invalid_are_never_zero_or_neutral():
    for raw in (("", "", "", ""), ("x", "1", "1", "2")):
        _, _, values = tb.validate_raw(raw)
        assert values is None
    zero = tb.validate_raw(("0", "0", "0", "0"))
    assert zero[0] == "valid" and zero[2] == (0.0, 0.0, 0.0, 0.0)                              # a real zero is valid, and is flagged separately below


# ================================================================ provenance through the adapter and the window

def test_the_adapter_keeps_the_raw_strings_unchanged_and_the_fingerprint_binds_them():
    specs = [{**tone(-1.5, 2.0, 3.5)}, {"tone": "", "positive": "", "negative": "", "polarity": ""}, {**tone(0, 0, 0)}]
    r, obs = observations(specs)
    recs = [x for i in r.intervals for x in i.records]
    assert [x.tone_raw for x in recs] == [("-1.5", "2.0", "3.5", "5.5"), ("", "", "", ""), ("0.0", "0.0", "0.0", "0.0")]
    assert [o.status for o in obs] == ["valid", "missing", "valid"] and obs[2].all_zero and not obs[0].all_zero
    assert all(o.contract_version == tb.CONTRACT_VERSION and o.scope == tb.SCOPE for o in obs)
    assert [o.raw for o in obs] == [x.tone_raw for x in recs]                                   # raw is preserved on the observation
    changed = world([{**tone(-1.5, 2.0, 3.5)}, {"tone": "", "positive": "", "negative": "", "polarity": ""}, {**tone(0, 0, 1)}]).run()
    assert changed.record_fingerprint != r.record_fingerprint and changed.digest() != r.digest()


def test_a_default_world_row_with_a_partly_empty_tone_is_invalid_not_zero():
    _, obs = observations([{}])
    assert obs[0].status == "invalid" and obs[0].values is None and "partly empty" in obs[0].reasons[0]


# ================================================================ counts

def test_counts_per_theme_separate_valid_missing_invalid_and_all_zero_and_count_every_record():
    specs = [{**tone(-1.5, 2.0, 3.5)}, {**tone(0, 0, 0)}, {"tone": "", "positive": "", "negative": "", "polarity": ""},
             {"tone": "x", "positive": "1", "negative": "1", "polarity": "2"}, {**tone(1, 2, 1), "mech_dup": "DUP_SAME_BATCH"},
             {**tone(1, 2, 1), "member_equity_us": "0", "member_gold": "1"}]
    _, obs = observations(specs)
    eq, ra, go = tb.count_tone(obs)
    assert (eq.theme, eq.n_records, eq.n_valid, eq.n_missing, eq.n_invalid, eq.n_valid_all_zero) == ("equity_us", 5, 3, 1, 1, 1)      # the duplicate counts: primary unit
    assert eq.valid_share == pytest.approx(3 / 5)
    assert (ra.n_records, ra.valid_share) == (0, None) and (go.n_records, go.n_valid) == (1, 1)         # no records: no share, never 0 or 1


# ================================================================ derived polarity is blocked

ALL_APPLIED = PolicyState.from_mapping({n: APPLIED_APPROVED for n in REQUIRED_POLICIES})          # a TEST FIXTURE: nothing in production builds this
APPROVED_FOR_TESTS = tb.APPROVED_MAPPING
UNAPPROVED = dataclasses.replace(tb.APPROVED_MAPPING, version="some_other_mapping", approved=False, status="PROPOSED_NOT_APPROVED")


def test_only_the_owner_approved_mapping_derives_and_any_other_mapping_is_blocked():
    r, obs = observations([{**tone(1, 2, 1)}])
    assert tb.APPROVED_MAPPING.approved is True and tb.APPROVED_MAPPING.version == "gdelt_tone_mean_v0" and tb.APPROVED_MAPPING.status == "OWNER_APPROVED_DESCRIPTIVE_BASELINE"
    assert tb.MAPPING_LABEL == "descriptive_document_tone_baseline"
    with pytest.raises(tb.ToneMappingBlockedError):
        tb.derive_interval_tone(obs, W.D2, "equity_us", UNAPPROVED, r.interval(W.D2).assessment, policy=ALL_APPLIED)


def test_with_a_test_fixture_mapping_the_mean_uses_valid_records_only_and_fails_closed_otherwise():
    specs = [{**tone(2, 3, 1)}, {**tone(-4, 0, 4)}, {"tone": "", "positive": "", "negative": "", "polarity": ""}, {"tone": "x", "positive": "1", "negative": "1", "polarity": "2"}]
    r, obs = observations(specs)
    a = r.interval(W.D2).assessment
    d = tb.derive_interval_tone(obs, W.D2, "equity_us", APPROVED_FOR_TESTS, a, policy=ALL_APPLIED)
    assert (d.status, d.mean_tone, d.n_valid, d.n_records) == ("computed", pytest.approx(-1.0), 2, 4) and d.scope == tb.SCOPE
    none = tb.derive_interval_tone(obs, W.D2, "gold", APPROVED_FOR_TESTS, a, policy=ALL_APPLIED)                          # no gold records: no value, and not zero
    assert (none.status, none.mean_tone, none.n_valid) == ("no_valid_observations", None, 0)
    all_bad = tb.derive_interval_tone([o for o in obs if o.status != "valid"], W.D2, "equity_us", APPROVED_FOR_TESTS, a, policy=ALL_APPLIED)
    assert all_bad.mean_tone is None and all_bad.status == "no_valid_observations" and all_bad.n_records == 2
    inc = world(specs, drop_slots={W.IN_D2_B}).run().interval(W.D2).assessment
    assert inc.usability is IntervalUsability.UNUSABLE_INCOMPLETE
    blocked = tb.derive_interval_tone(obs, W.D2, "equity_us", APPROVED_FOR_TESTS, inc, policy=ALL_APPLIED)
    assert (blocked.status, blocked.mean_tone) == ("unavailable_incomplete_interval", None)
    with pytest.raises(tb.ToneBaselineError):
        tb.derive_interval_tone(obs, W.D2, "bonds", APPROVED_FOR_TESTS, a, policy=ALL_APPLIED)
    with pytest.raises(tb.ToneBaselineError):
        tb.derive_interval_tone(obs, W.D2, "equity_us", dataclasses.replace(APPROVED_FOR_TESTS, aggregate="median"), a, policy=ALL_APPLIED)


# ================================================================ pipeline integration and separation

def test_the_pipeline_runs_the_tone_baseline_locally_and_the_derived_tone_stays_blocked_by_the_policy_gates():
    inputs = world([{**tone(-1.5, 2.0, 3.5)}, {**tone(0, 0, 0), "member_rates_us": "1"}]).inputs()
    r = pl.run_pipeline(inputs)
    assert r.stage("tone_baseline").status is pl.StageStatus.COMPLETED and r.stage("tone_derived").status is pl.StageStatus.BLOCKED_BY_POLICY
    assert r.stage("scoring").status is pl.StageStatus.BLOCKED_NO_SCORER and r.scores == () and r.conversion is None      # independent of any title scorer
    d2 = next(s for s in r.tone if s.origin_date == W.D2)
    eq, ra, go = d2.counts
    assert (eq.n_records, eq.n_valid, ra.n_records, ra.n_valid_all_zero, go.n_records) == (2, 2, 1, 1, 0)
    assert d2.scope == tb.SCOPE and len(r.tone) == len(r.window.intervals)
    assert r.tone_derived == () and sum(1 for x in r.stage("tone_derived").reasons if "=" in x) == 1 and "OWNER_APPROVED_DESCRIPTIVE_BASELINE" in r.stage("tone_derived").reasons[0]
    assert r.digest == pl.run_pipeline(inputs).digest and r == pl.run_pipeline(inputs)


def test_the_tone_baseline_is_separate_from_the_title_scorer_and_the_schema():
    text = (PKG / "tone_baseline.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in text.splitlines() if l.startswith(("import ", "from ")))
    assert "scorer_port" not in code and "polarity_validation" not in code and "ArticleRecord" not in code and "fake_scorer" not in code
    assert not any(m in code for m in ("torch", "transformers", "tensorflow", "requests", "socket", "urllib"))
    assert pl.FEATURES_AUTHORISED is False


@pytest.mark.skipif(not (SAMPLE / "manifest" / "manifest.sqlite").exists(), reason="the local B2-M sample is not present")
def test_real_sample_tone_fields_are_all_valid_and_raw_strings_are_preserved_read_only():
    db = sqlite3.connect(f"file:{(SAMPLE / 'manifest' / 'manifest.sqlite').as_posix()}?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    slot_rows = [dict(r) for r in db.execute("SELECT * FROM slot")]
    series = [dict(r) for r in db.execute("SELECT * FROM slot_series_count")]
    commits = [dict(r) for r in db.execute("SELECT * FROM day_commit ORDER BY utc_day LIMIT 6")]
    db.close()
    slots = ma.adapt_manifest(slot_rows, series, filter_version="gdelt_filter_v1", expected_batches=sorted(r["batch_ts"] for r in slot_rows)).by_batch()
    recs = [x for c in commits for x in da.adapt_day_file((SAMPLE / c["file_relpath"]).read_bytes(), utc_day=c["utc_day"], slots=slots,
                                                         min_chars=int(load_spec().raw["title_hash_min_chars"]), source_name=c["file_relpath"], day_commit=c).records]
    assert len(recs) > 100
    obs = [tb.observe_tone(x) for x in recs]
    assert {o.status for o in obs} == {"valid"} and all(all(isinstance(s, str) and s != "" for s in o.raw) for o in obs)
    assert any(o.all_zero for o in obs) and any(not o.all_zero for o in obs)                    # exact zeros exist: they are not evidence of neutrality
    assert all(math.isfinite(v) for o in obs for v in o.values)


def test_an_approved_mapping_alone_never_unblocks_a_derived_number():
    r, obs = observations([{**tone(1, 2, 1)}])
    a = r.interval(W.D2).assessment
    assert a.usability is IntervalUsability.USABLE
    live = PolicyState.from_mapping(orc.POLICY_STATUS)
    with pytest.raises(PolicyBlockedError):
        tb.derive_interval_tone(obs, W.D2, "equity_us", APPROVED_FOR_TESTS, a, policy=live)              # mapping approved, policies unresolved
    with pytest.raises(PolicyBlockedError):
        tb.derive_interval_tone(obs, W.D2, "equity_us", APPROVED_FOR_TESTS, a, policy={n: APPLIED_APPROVED for n in REQUIRED_POLICIES})   # type: ignore[arg-type]
    undecided = world([{**tone(1, 2, 1)}], row_over={W.IN_D2: {"near_empty_flag": None}}).run().interval(W.D2).assessment
    assert undecided.usability is IntervalUsability.UNDECIDED_POLICY
    d = tb.derive_interval_tone(obs, W.D2, "equity_us", APPROVED_FOR_TESTS, undecided, policy=ALL_APPLIED)
    assert (d.status, d.mean_tone) == ("unavailable_policy_undecided", None)
    assert tb.derive_interval_tone(obs, W.D2, "equity_us", APPROVED_FOR_TESTS, a, policy=ALL_APPLIED).status == "computed"


def test_the_derived_tone_is_reported_with_its_counts_and_the_all_zero_excluded_sensitivity():
    specs = [{**tone(2, 3, 1)}, {**tone(-4, 0, 4)}, {**tone(0, 0, 0)}, {**tone(0, 0, 0)}, {"tone": "", "positive": "", "negative": "", "polarity": ""}]
    r, obs = observations(specs)
    d = tb.derive_interval_tone(obs, W.D2, "equity_us", tb.APPROVED_MAPPING, r.interval(W.D2).assessment, policy=ALL_APPLIED)
    assert d.status == "computed" and d.mean_tone == pytest.approx(-0.5)                          # (2 - 4 + 0 + 0) / 4: the exact zeros are valid observations
    assert (d.n_valid, d.n_records, d.n_valid_all_zero) == (4, 5, 2)                                # reported alongside the mean
    assert d.mean_tone_excluding_all_zero == pytest.approx(-1.0)                                    # the sensitivity variant, reported separately
    assert d.label == "descriptive_document_tone_baseline" and d.scope == tb.SCOPE and d.mapping_version == "gdelt_tone_mean_v0"
    only_zero, obs0 = observations([{**tone(0, 0, 0)}])
    z = tb.derive_interval_tone(obs0, W.D2, "equity_us", tb.APPROVED_MAPPING, only_zero.interval(W.D2).assessment, policy=ALL_APPLIED)
    assert (z.mean_tone, z.mean_tone_excluding_all_zero, z.n_valid_all_zero) == (0.0, None, 1)       # a real zero mean, but no non-zero sensitivity value (never 0)


def test_with_every_policy_applied_in_a_test_the_pipeline_derives_tone_and_otherwise_it_does_not():
    inputs = world([{**tone(2, 3, 1)}, {**tone(0, 0, 0), "member_rates_us": "1"}]).inputs()
    r = pl.run_pipeline(inputs, policy=ALL_APPLIED)
    assert r.stage("tone_derived").status is pl.StageStatus.COMPLETED and len(r.tone_derived) == 6      # 2 intervals x 3 themes
    eq = next(x for x in r.tone_derived if x.origin_date == W.D2 and x.theme == "equity_us")
    assert (eq.status, eq.mean_tone, eq.n_valid) == ("computed", pytest.approx(1.0), 2) and eq.n_valid_all_zero == 1
    gold = next(x for x in r.tone_derived if x.origin_date == W.D2 and x.theme == "gold")
    assert (gold.status, gold.mean_tone) == ("no_valid_observations", None)
    assert pl.run_pipeline(inputs).tone_derived == ()                                                 # the live policy table still blocks it
    assert r.stage("features").status is pl.StageStatus.BLOCKED_BY_POLICY                             # E4 is still not authorised: tone is not the daily features
