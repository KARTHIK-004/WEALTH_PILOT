"""S2 / S2.2 / S2.3: the offline sentiment scaffold. SYNTHETIC data and a deterministic TEST-ONLY fake scorer only.

No model, weights, network, API, key, annotation label or AI-only suggestion is used (the ``_no_network`` fixture in conftest
blocks sockets). Nothing here says anything about real sentiment. One test reads the local B2-M development sample's manifest and
day files **read-only** (counts and flags only; it is skipped when the sample is absent).

S2.2 regression tests are in the sections headed "S2.2"; S2.3 (source reconciliation and late batches) in the sections headed
"S2.3".
"""

from __future__ import annotations

import csv
import dataclasses
import gzip
import inspect
import io
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

from wealthpilot.data.gdelt import availability
from wealthpilot.data.gdelt.manifest import slot_state
from wealthpilot.data.gdelt.sentiment import features as ft
from wealthpilot.data.gdelt.sentiment.completeness import EarlierEvidence
from wealthpilot.data.gdelt.sentiment import fake_scorer as fs
from wealthpilot.data.gdelt.sentiment import policy as pol
from wealthpilot.data.gdelt.sentiment import schema as sc
from wealthpilot.data.gdelt.sentiment import slots as sl
from wealthpilot.data.gdelt.session_calendar import PROPOSED_EARLY_CLOSES, cutoff_utc, origin_for
from wealthpilot.data.gdelt.timeutil import SLOT, format_batch_stamp, slot_grid

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / "backend/wealthpilot/data/gdelt/sentiment"
SAMPLE = ROOT / "datasets/raw/gdelt/english_gkg_v1/review/b2i_review_v1"
UTC = timezone.utc
D1, D2, D3 = date(2022, 3, 1), date(2022, 3, 2), date(2022, 3, 3)          # Tue, Wed, Thu (New York is on EST in early March)
DAYS = [D1, D2, D3]
FLAGS = {"equity_us": True, "rates_us": False, "gold": False}
SCORER = fs.FakeScorerTestOnly(min_chars=20)
CODE_SHA = fs.scorer_code_sha256()
APPROVED_FOR_TESTS = pol.PolicyState.from_mapping({n: pol.APPLIED_APPROVED for n in pol.REQUIRED_POLICIES})   # a TEST FIXTURE: nothing in production builds this
CFG = ft.SentimentConfig(coverage_threshold=ft.PROPOSED_COVERAGE_THRESHOLD, early_closes=frozenset(), market_holidays=frozenset(),
                         dedup=ft.PROPOSED_DEDUP_POLICY, expected_model_id=sc.TEST_ONLY_MODEL_ID,
                         expected_model_revision=fs.MODEL_REVISION, expected_scorer_code_sha256=CODE_SHA,
                         policy=APPROVED_FOR_TESTS, allow_test_only=True)
SCORED_AT = datetime(2026, 1, 1, tzinfo=UTC)

EXAMINED_NONE = EarlierEvidence.none_found()      # the lookback was examined and no earlier batch is in play (a test assertion)


def aggregate(*args, **kwargs):
    """features.aggregate_daily with the C-min evidence stated explicitly (it has no default in production code)."""
    kwargs.setdefault("earlier", EXAMINED_NONE)
    return ft.aggregate_daily(*args, **kwargs)

FV, PV = "gdelt_filter_v1", "gkg_parser_v1"


@lru_cache(maxsize=None)
def verified(batch_ts: str) -> datetime:
    """The availability time through the EXISTING rule (a synthetic server clock, no network)."""
    nominal = datetime.strptime(batch_ts, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    lm = nominal + timedelta(minutes=-9)                                     # GDELT writes files shortly before the nominal time
    res = availability.compute_availability(batch_ts, format_datetime(lm, usegmt=True), format_datetime(nominal + SLOT, usegmt=True))
    assert res.verified
    return res.available_at


def art(n: int, batch_ts: str, *, title="SYNTHETIC headline number %d about nothing real", flags=FLAGS, story=None,
        dup="ORIGINAL", status="verified", at="auto", scorer=SCORER) -> sc.ArticleRecord:
    available = verified(batch_ts) if (at == "auto" and status == "verified") else (None if status != "verified" else at)
    a = fs.SyntheticArticle(f"SYN-{n:04d}", batch_ts, available, status, "example.invalid",
                            title % n if "%d" in title else title, flags, story or f"SYN-{n:04d}", dup)
    return scorer.score(a, scored_at=SCORED_AT)


def unscored(rec: sc.ArticleRecord) -> sc.ArticleRecord:
    """The same record as a scorer failure: an explicit reason, no vector, no scored time."""
    return dataclasses.replace(rec, p_positive=None, p_negative=None, p_neutral=None, pred_label="unavailable",
                               unavailable_reason="scorer_failure", scored_at_utc=None)


def row(rows, d, theme="equity_us"):
    return next(r for r in rows if r.origin_date == d and r.theme == theme)


def grid(prev: date, d: date, cfg=CFG) -> list[str]:
    lower, upper = cutoff_utc(prev, cfg.early_closes), cutoff_utc(d, cfg.early_closes)
    return slot_grid(format_batch_stamp(lower), format_batch_stamp(upper - SLOT))


def processed(t: str, recs=(), *, at=None, near=False, rows=None, theme_rows=None) -> sl.SlotAccounting:
    """A processed slot whose counts are exactly those of ``recs`` (overridable to build a wrong one)."""
    recs = list(recs)
    counts = {th: sum(1 for r in recs if r.theme_flags[th]) for th in sc.THEMES}
    return sl.SlotAccounting(t, "processed", at or verified(t), len(recs) if rows is None else rows,
                             counts if theme_rows is None else theme_rows, near, FV, PV)


def absent(t: str) -> sl.SlotAccounting:
    return sl.SlotAccounting(t, "confirmed_absent")


def slots_for(arts, days=DAYS, cfg=CFG, *, near=False) -> dict:
    """Every interval's full nominal grid, all processed, with counts and availability exactly those of the supplied records."""
    by = defaultdict(list)
    for a in arts:
        by[a.batch_ts].append(a)
    out = {}
    for p, d in zip(days, days[1:]):
        out[d] = [processed(t, by.get(t, ()), near=near,
                            at=by[t][0].available_at_utc if by.get(t) and by[t][0].available_at_utc else None)
                  for t in grid(p, d, cfg)]
    return out


def agg(arts, days=DAYS, cfg=CFG, slots=None, **kw):
    return aggregate(arts, days, slots if slots is not None else slots_for(arts, days, cfg), config=cfg, **kw)


def set_slots(slots, d, indexes, make):
    out = list(slots[d])
    for i in indexes:
        out[i] = make(out[i].batch_ts)
    return {**slots, d: out}


# Wednesday 2022-03-02: the interval is (2022-03-01 21:00Z, 2022-03-02 21:00Z]
IN_D2 = "20220302150000"           # available 15:15Z
IN_D3 = "20220303150000"
LAST_D2 = "20220302204500"         # the last nominal slot of D2: available 21:00Z exactly (the cutoff)
UNAVAILABLE_FEATURES = ("n_eligible", "n_scored", "n_duplicates_removed", "n_invalid_text", "n_update_versions",
                        "n_distinct_stories", "n_late_carried_in", "n_delayed_theme_rows", "mean_p_pos", "mean_p_neg", "mean_net",
                        "disp_net", "no_news")


def all_unavailable(r):
    for name in UNAVAILABLE_FEATURES:
        assert getattr(r, name) is None, name                                                      # never 0, never False, never neutral


# ================================================================ 1-3. schema, probabilities, labels, fields

def test_a_valid_record_validates_and_round_trips():
    r = art(1, IN_D2)
    assert sc.problems(r, allow_test_only=True) == [] and r.schema_version == "s2_article_v2"
    back = sc.from_dict(sc.to_dict(r), allow_test_only=True)
    assert back == r and sc.to_dict(r)["available_at_utc"].endswith("Z")


@pytest.mark.parametrize("probs,part", [
    ((float("nan"), 0.5, 0.5), "finite"), ((float("inf"), 0.0, 0.0), "finite"), ((-0.1, 0.6, 0.5), "[0, 1]"),
    ((1.1, 0.0, -0.1), "[0, 1]"), ((0.3, 0.3, 0.3), "sum to 1"), ((0.5, 0.5, 0.5), "sum to 1"),
    ((1, 0, 0), "finite floats"), ((True, 0.0, 0.0), "finite floats"), ((None, 0.5, 0.5), "finite floats")])
def test_invalid_probabilities_are_reported(probs, part):
    r = dataclasses.replace(art(1, IN_D2), p_positive=probs[0], p_negative=probs[1], p_neutral=probs[2])
    assert any(part in p for p in sc.problems(r, allow_test_only=True))


def test_the_probability_sum_tolerance_is_documented_and_small():
    r = art(1, IN_D2)
    assert sc.PROB_SUM_TOLERANCE == 1e-6
    near = dataclasses.replace(r, p_positive=r.p_positive + 5e-7)
    assert all("sum" not in p for p in sc.problems(near, allow_test_only=True))             # within the rounding allowance
    far = dataclasses.replace(r, p_positive=r.p_positive + 1e-3)
    assert any("sum to 1" in p for p in sc.problems(far, allow_test_only=True))


def test_the_label_must_be_an_argmax_of_the_vector():
    r = art(1, IN_D2)
    other = next(l for l in sc.LABELS if l != r.pred_label and getattr(r, f"p_{l}") < max(r.p_positive, r.p_negative, r.p_neutral))
    assert any("argmax" in p for p in sc.problems(dataclasses.replace(r, pred_label=other), allow_test_only=True))


@pytest.mark.parametrize("label", ["bullish", "", "POSITIVE", None, 1])
def test_invalid_labels_are_rejected(label):
    assert any("pred_label" in p for p in sc.problems(dataclasses.replace(art(1, IN_D2), pred_label=label), allow_test_only=True))


def test_an_unavailable_prediction_has_no_probabilities_and_is_never_a_neutral_vector():
    bad = dataclasses.replace(unscored(art(1, IN_D2)), p_positive=0.2, p_negative=0.3, p_neutral=0.5)
    assert any("no probabilities" in p for p in sc.problems(bad, allow_test_only=True))
    bad2 = dataclasses.replace(unscored(art(1, IN_D2)), p_positive=0.0, p_negative=0.0, p_neutral=1.0)
    assert any("no probabilities" in p for p in sc.problems(bad2, allow_test_only=True))


def test_missing_required_fields_and_extra_fields_are_rejected():
    d = sc.to_dict(art(1, IN_D2))
    for name in sc.FIELD_NAMES:
        broken = {k: v for k, v in d.items() if k != name}
        with pytest.raises(sc.SentimentSchemaError, match="missing"):
            sc.from_dict(broken, allow_test_only=True)
    with pytest.raises(sc.SentimentSchemaError, match="page publication time"):
        sc.from_dict({**d, "page_pub_ts_utc": "2022-03-02T10:00:00Z"}, allow_test_only=True)
    for name in ("article_id", "source_domain", "story_id", "model_id", "model_revision"):
        assert any("required" in p for p in sc.problems(dataclasses.replace(art(1, IN_D2), **{name: ""}), allow_test_only=True))


@pytest.mark.parametrize("over,part", [
    ({"batch_ts": "2022-03-02"}, "batch_ts"), ({"batch_ts": "20220302150700"}, "15-minute"),
    ({"availability_status": "maybe"}, "availability_status"), ({"title_sha256": "xyz"}, "SHA-256"),
    ({"scorer_code_sha256": "ab"}, "SHA-256"), ({"text_status": "great"}, "text_status"), ({"dup_status": "COPY"}, "dup_status"),
    ({"theme_flags": {"equity_us": True}}, "theme_flags"), ({"theme_flags": {**FLAGS, "gold": 1}}, "theme_flags"),
    ({"schema_version": "v0"}, "schema_version"), ({"scored_at_utc": datetime(2026, 1, 1)}, "scored_at_utc"),
    ({"available_at_utc": datetime(2022, 3, 2, 15, 15)}, "available_at_utc")])
def test_other_invalid_fields_are_reported(over, part):
    assert any(part in p for p in sc.problems(dataclasses.replace(art(1, IN_D2), **over), allow_test_only=True)), over


def test_the_availability_time_must_follow_the_verified_rule_not_a_page_time():
    r = art(1, IN_D2)
    too_early = dataclasses.replace(r, available_at_utc=datetime(2022, 3, 2, 14, 59, tzinfo=UTC))   # before nominal + one slot
    assert any("verified availability rule" in p for p in sc.problems(too_early, allow_test_only=True))
    unverified_with_time = dataclasses.replace(r, availability_status="unverified")
    assert any("must not carry an availability time" in p for p in sc.problems(unverified_with_time, allow_test_only=True))
    verified_without = dataclasses.replace(r, available_at_utc=None)
    assert any("needs available_at_utc" in p for p in sc.problems(verified_without, allow_test_only=True))


# ================================================================ 4. the test-only fake scorer

def test_the_fake_scorer_is_deterministic_and_marked_test_only():
    a = fs.SyntheticArticle("SYN-0001", IN_D2, verified(IN_D2), "verified", "example.invalid", "SYNTHETIC headline one about nothing",
                            FLAGS, "SYN-0001")
    r1, r2 = SCORER.score(a, scored_at=SCORED_AT), SCORER.score(a, scored_at=SCORED_AT)
    assert r1 == r2 and r1.model_id == "TEST_ONLY_FAKE_SCORER" and fs.FakeScorerTestOnly.TEST_ONLY is True
    assert abs(r1.p_positive + r1.p_negative + r1.p_neutral - 1.0) <= sc.PROB_SUM_TOLERANCE
    other = dataclasses.replace(a, title="SYNTHETIC headline two about nothing")
    assert SCORER.score(other, scored_at=SCORED_AT).p_positive != r1.p_positive
    assert r1.title_sha256 == sc.title_sha256(a.title) and r1.scorer_code_sha256 == CODE_SHA


@pytest.mark.parametrize("article_id,domain", [("D0001", "example.invalid"), ("SYN-1", "reuters.com"), ("20220302-1", "example.test"),
                                               ("SYN-1", "example.com")])
def test_the_fake_scorer_refuses_anything_that_is_not_marked_synthetic(article_id, domain):
    a = fs.SyntheticArticle(article_id, IN_D2, verified(IN_D2), "verified", domain, "SYNTHETIC headline about nothing real",
                            FLAGS, "s")
    with pytest.raises(fs.NotSyntheticError):
        SCORER.score(a, scored_at=SCORED_AT)
    with pytest.raises(fs.NotSyntheticError):
        SCORER.score({"title": "x"}, scored_at=SCORED_AT)


def test_the_fake_scorer_is_not_exported_and_its_records_need_an_explicit_test_flag():
    import wealthpilot.data.gdelt.sentiment as pkg
    assert not hasattr(pkg, "FakeScorerTestOnly") and "FakeScorer" not in (PKG / "__init__.py").read_text(encoding="utf-8").split('"""')[2]
    r = art(1, IN_D2)
    assert any("test-only" in p for p in sc.problems(r))                                  # the default refuses it
    with pytest.raises(sc.SentimentSchemaError):
        sc.validate(r)


def test_unscorable_text_gets_no_vector_no_scored_time_and_an_explicit_reason():
    for title, status in (("", "empty"), ("   ", "empty"), ("short", "short"), ("bad\x00title that is long enough", "malformed")):
        r = art(1, IN_D2, title=title)
        assert r.text_status == status and r.pred_label == "unavailable" and r.unavailable_reason == f"text_{status}"
        assert (r.p_positive, r.p_negative, r.p_neutral, r.scored_at_utc) == (None, None, None, None)


def test_classify_title_cases():
    assert sc.classify_title("A reasonably long title here", min_chars=20) == "ok"
    assert sc.classify_title(None, min_chars=20) == "malformed" and sc.classify_title(5, min_chars=20) == "malformed"
    assert sc.classify_title("tab\tseparated title is fine here", min_chars=20) == "ok"
    assert sc.classify_title("lone \ud800 surrogate in a long title", min_chars=20) == "malformed"
    assert sc.classify_title("zero​width format char in a long title", min_chars=20) == "malformed"      # a zero-width space (category Cf)
    with pytest.raises(sc.SentimentSchemaError):
        sc.classify_title("x", min_chars=0)


# ================================================================ duplicates and story updates (proposed policy, unchanged)

def test_duplicates_are_excluded_without_modifying_the_source_records():
    originals = [art(1, IN_D2, dup="ORIGINAL"), art(2, IN_D2, dup="DUP_SAME_BATCH"), art(3, IN_D2, dup="SYNDICATED_SAME_BATCH"),
                 art(4, IN_D2, dup="REOBSERVATION"), art(5, IN_D2, dup="SYNDICATED")]
    snapshot = [sc.to_dict(a) for a in originals]
    r = row(agg(originals), D2)
    assert (r.n_eligible, r.n_scored, r.n_duplicates_removed) == (1, 1, 4)
    assert r.dedup_status == "duplicates_removed_proposed" and r.n_distinct_stories == 1
    assert [sc.to_dict(a) for a in originals] == snapshot                                      # records unchanged (and frozen)
    with pytest.raises(dataclasses.FrozenInstanceError):
        originals[0].dup_status = "ORIGINAL"                                                   # type: ignore[misc]


def test_unapproved_update_handling_and_bad_duplicate_sets_are_refused():
    for bad in (ft.DedupPolicy(frozenset({"REOBSERVATION"}), "latest_version_only"),
                ft.DedupPolicy(frozenset({"UPDATE"})), ft.DedupPolicy(frozenset({"ORIGINAL"})), ft.DedupPolicy(frozenset({"COPY"}))):
        with pytest.raises(ft.SentimentFeatureError):
            dataclasses.replace(CFG, dedup=bad)
    for t in (0.0, 1.5, 1, "0.75", None, True):
        with pytest.raises(ft.SentimentFeatureError):
            dataclasses.replace(CFG, coverage_threshold=t)


def test_the_proposed_rules_are_explicit_inputs_and_every_row_says_they_are_not_approved():
    with pytest.raises(TypeError):
        ft.SentimentConfig(coverage_threshold=0.75, early_closes=frozenset())               # type: ignore[call-arg]
    assert ft.PROPOSED_DEDUP_POLICY.status == "PROPOSED_NOT_APPROVED"
    rows = agg([art(1, IN_D2)])
    assert {r.rules_status for r in rows} == {"PROPOSED_NOT_APPROVED"} and ft.RULES_STATUS == "PROPOSED_NOT_APPROVED"


# ================================================================ availability, cutoffs and leakage (S2 regression)

def test_availability_before_at_and_after_the_cutoff():
    cut2 = cutoff_utc(D2)
    assert cut2.hour == 21 and cut2.tzinfo is not None                                          # 16:00 EST
    before, at_cutoff, after = art(1, "20220302203000"), art(2, LAST_D2), art(3, "20220302210000")
    assert verified(LAST_D2) == cut2 and verified("20220302210000") > cut2
    rows = agg([before, at_cutoff, after])
    assert row(rows, D2).n_eligible == 2 and row(rows, D3).n_eligible == 1                      # "at" is inside, "after" is next day
    assert row(rows, D2).n_slots_delayed == 0 and row(rows, D3).n_late_carried_in == 0           # none of them is delayed
    assert origin_for(cut2, DAYS) == D2 and origin_for(cut2 + timedelta(seconds=1), DAYS) == D3  # the existing convention


def test_the_lower_bound_is_exclusive_so_an_article_belongs_to_exactly_one_day():
    exactly_prev_cutoff = art(1, "20220301204500")                                              # available exactly at cutoff(D1)
    assert verified("20220301204500") == cutoff_utc(D1)
    rows = agg([exactly_prev_cutoff], slots=slots_for([]))                                      # its slot is before the window
    assert row(rows, D2).n_eligible == 0 and row(rows, D3).n_eligible == 0                      # it belongs to D1, which has no row


def test_a_future_article_cannot_change_an_earlier_daily_feature():
    base = [art(1, IN_D2), art(2, "20220302160000")]
    later = base + [art(3, IN_D3), art(4, "20220304120000")]
    assert row(agg(base), D2) == row(agg(later), D2)
    changed = base + [dataclasses.replace(art(3, IN_D3), p_positive=0.98, p_negative=0.01, p_neutral=0.01, pred_label="positive")]
    assert row(agg(base), D2) == row(agg(changed), D2)


def test_the_page_publication_time_is_not_part_of_the_record_or_the_rule():
    assert not any("pub" in f for f in sc.FIELD_NAMES)
    text = "".join((PKG / n).read_text(encoding="utf-8") for n in ("features.py", "schema.py", "slots.py"))
    assert "page_pub" not in text.replace("a page publication time is never an input", "").replace("page publication time", "")


def test_an_article_without_verified_availability_inside_a_processed_slot_fails_closed():
    u = art(1, IN_D2, status="unverified")
    assert u.available_at_utc is None
    r = row(agg([u]), D2)                                                                       # its slot says processed with 1 row
    assert r.coverage_status == "slot_article_mismatch" and "no verified availability" in r.reason
    all_unavailable(r)
    assert row(agg([u, art(2, IN_D2)]), D2).coverage_status == "slot_article_mismatch"


# ================================================================ missing data, coverage and no-news (S2 regression)

def test_missing_batches_are_not_zero_sentiment():
    slots = set_slots(slots_for([]), D2, range(96), absent)
    r = row(agg([], slots=slots), D2)
    assert r.coverage_status == "missing_source_batches" and r.coverage == 0.0 and r.n_slots_expected == 96
    all_unavailable(r)


def test_low_coverage_alone_is_informational_and_never_creates_availability_or_no_news():
    a = art(1, IN_D2)
    low = set_slots(slots_for([a]), D2, range(60), absent)                                           # 36 of 96 = 0.375
    r = row(agg([a], slots=low), D2)
    assert r.coverage_status == "ok" and r.coverage == pytest.approx(0.375) and (r.coverage_threshold, r.coverage_threshold_met) == (0.75, False)
    assert r.n_eligible == 1 and r.mean_net is not None                                              # features are computed from the evidence that exists
    assert (r.source_completeness, r.interval_usability, r.result_availability) == ("final_gaps", "undecided_policy", "unavailable")   # but the gaps keep it unavailable
    empty = row(agg([], slots=set_slots(slots_for([]), D2, range(60), absent)), D2, "gold")
    assert empty.no_news is None and empty.theme_evidence == "unverified_empty" and empty.mean_net is None      # missing evidence is never no-news or neutral
    at_threshold = set_slots(slots_for([a]), D2, range(24), absent)                                 # 72 of 96 = 0.75 meets it
    just_below = set_slots(slots_for([a]), D2, range(25), absent)                                   # 71 of 96 does not
    met = row(agg([a], slots=at_threshold), D2)
    below = row(agg([a], slots=just_below), D2)
    assert (met.coverage_status, met.coverage_threshold_met) == ("ok", True) and (below.coverage_status, below.coverage_threshold_met) == ("ok", False)
    assert met.interval_usability == below.interval_usability == "undecided_policy"                  # the ratio decides nothing about usability


def test_a_processed_slot_with_unknown_emptiness_is_not_counted_as_covered():
    slots = set_slots(slots_for([]), D2, range(96), lambda t: processed(t, near=None))
    r = row(agg([], slots=slots), D2)
    assert (r.coverage_status, r.coverage, r.coverage_threshold_met, r.no_news, r.theme_evidence) == ("ok", 0.0, False, None, "unverified_empty")


def test_no_slot_information_is_its_own_status_not_a_zero():
    slots = slots_for([])
    del slots[D2]
    r = row(agg([art(1, IN_D2)], slots=slots), D2)
    assert r.coverage_status == "no_expected_slots" and r.coverage is None
    all_unavailable(r)


def test_a_verified_no_news_day_is_not_a_neutral_day():
    nothing = row(agg([]), D2)
    assert nothing.coverage_status == "ok" and nothing.no_news is True and nothing.reason == "verified_no_news"
    assert nothing.n_eligible == 0 and nothing.mean_net is None and nothing.mean_p_pos is None   # no mean at all: not 0, not neutral
    neutral = dataclasses.replace(art(1, IN_D2), p_positive=0.1, p_negative=0.1, p_neutral=0.8, pred_label="neutral")
    scored = row(agg([neutral]), D2)
    assert scored.no_news is False and scored.n_scored == 1 and scored.mean_net == pytest.approx(0.0)
    assert scored.mean_net is not None and nothing.mean_net is None                               # the two cases never collide


def test_other_themes_news_does_not_count_for_this_theme():
    rows = agg([art(1, IN_D2)])                                                                    # an equity_us article only
    assert row(rows, D2, "equity_us").n_eligible == 1
    assert row(rows, D2, "gold").no_news is True and row(rows, D2, "gold").n_eligible == 0


def test_invalid_titles_are_counted_and_all_invalid_is_not_no_news():
    arts = [art(1, IN_D2, title=""), art(2, IN_D2, title="short"), art(3, IN_D2, title="bad\x07title that is long enough to pass")]
    r = row(agg(arts), D2)
    assert (r.n_invalid_text, r.n_eligible, r.no_news) == (3, 0, False) and r.reason == "all_candidate_articles_have_invalid_text"
    r2 = row(agg(arts + [art(4, IN_D2)]), D2)
    assert (r2.n_invalid_text, r2.n_eligible, r2.n_scored) == (3, 1, 1) and r2.no_news is False


def test_eligible_articles_that_could_not_be_scored_do_not_become_neutral():
    r = row(agg([unscored(art(1, IN_D2))]), D2)
    assert r.n_eligible == 1 and r.n_scored == 0 and r.mean_net is None and r.reason == "no_scored_articles" and r.no_news is False
    assert r.scoring_status == "none_scored" and r.scoring_coverage == 0.0


# ================================================================ aggregates and reproducibility (S2 regression)

def test_the_aggregates_are_the_documented_arithmetic():
    vec = [(0.7, 0.2, 0.1, "positive"), (0.1, 0.6, 0.3, "negative"), (0.2, 0.2, 0.6, "neutral")]
    arts = [dataclasses.replace(art(i, IN_D2), p_positive=p, p_negative=n, p_neutral=u, pred_label=lab)
            for i, (p, n, u, lab) in enumerate(vec, start=1)]
    r = row(agg(arts), D2)
    nets = [0.5, -0.5, 0.0]
    assert r.mean_p_pos == pytest.approx(1.0 / 3) and r.mean_p_neg == pytest.approx(1.0 / 3) and r.mean_net == pytest.approx(0.0)
    assert r.disp_net == pytest.approx(math.sqrt(sum(x * x for x in nets) / 2))                    # sample std, ddof = 1
    assert row(agg(arts[:1]), D2).disp_net is None and row(agg(arts[:1]), D2).reason == "single_article_dispersion_undefined"
    assert r.feature_cutoff_utc == cutoff_utc(D2) and r.model_revision == "fake-v1" and r.schema_version == "s2_daily_v4"
    assert r.scoring_status == "complete" and r.scoring_coverage == 1.0 and r.reason is None


def test_the_daily_aggregates_are_reproducible_and_independent_of_input_order():
    arts = [art(i, f"202203021{i % 6}0000", flags=FLAGS) for i in range(1, 9)]
    first = agg(arts)
    assert first == agg(arts) == agg(list(reversed(arts))) == agg(tuple(arts))
    slots = slots_for(arts)
    reversed_slots = {d: list(reversed(v)) for d, v in slots.items()}
    assert aggregate(arts, DAYS, reversed_slots, config=CFG) == first                       # slot order does not matter either
    assert [r.origin_date for r in first][:3] == [D2, D2, D2] and len(first) == 6                   # 2 origin days x 3 themes


# ================================================================ S2.2 C1: one-shot and unordered iterables

def test_a_generator_or_set_is_refused_and_never_read_as_no_news():
    arts = [art(i, IN_D2) for i in range(1, 4)]
    slots = slots_for(arts)
    with pytest.raises(ft.SentimentFeatureError, match="list or tuple"):
        aggregate((a for a in arts), DAYS, slots, config=CFG)                              # was: n_eligible=0, no_news=True
    with pytest.raises(ft.SentimentFeatureError, match="list or tuple"):
        aggregate({a.article_id for a in arts}, DAYS, slots, config=CFG)
    with pytest.raises(ft.SentimentFeatureError, match="list or tuple"):
        aggregate(iter(arts), DAYS, slots, config=CFG)
    with pytest.raises(ft.SentimentFeatureError, match="list or tuple"):
        aggregate(arts, (d for d in DAYS), slots, config=CFG)
    with pytest.raises(ft.SentimentFeatureError, match="list or tuple"):
        aggregate(arts, set(DAYS), slots, config=CFG)
    with pytest.raises(ft.SentimentFeatureError, match="list or tuple"):
        aggregate(arts, DAYS, slots, config=CFG, themes={"equity_us"})
    with pytest.raises(ft.SentimentFeatureError, match="mapping"):
        aggregate(arts, DAYS, list(slots.values()), config=CFG)                            # type: ignore[arg-type]
    assert row(aggregate(tuple(arts), tuple(DAYS), slots, config=CFG), D2).n_eligible == 3   # tuples are supported


# ================================================================ S2.2 C2: whole-second timestamps and serialisation

def test_a_sub_second_availability_is_rejected_and_never_truncated():
    cut = cutoff_utc(D2)
    with pytest.raises(sc.SentimentSchemaError, match="whole seconds"):
        art(1, LAST_D2, at=cut + timedelta(milliseconds=400))                                       # 21:00:00.4: after the cutoff
    ok = art(1, LAST_D2)
    sub = dataclasses.replace(ok, available_at_utc=cut + timedelta(milliseconds=400))
    assert any("whole seconds" in p for p in sc.problems(sub, allow_test_only=True))
    with pytest.raises(sc.SentimentSchemaError, match="whole seconds"):
        sc.to_dict(sub)                                                                             # serialising refuses, never rounds
    sub_scored = dataclasses.replace(ok, scored_at_utc=SCORED_AT + timedelta(microseconds=1))
    assert any("whole seconds" in p for p in sc.problems(sub_scored, allow_test_only=True))


def test_serialisation_preserves_every_cutoff_inclusion_decision():
    arts = [art(1, "20220302203000"), art(2, LAST_D2), art(3, "20220302210000")]
    back = [sc.from_dict(sc.to_dict(a), allow_test_only=True) for a in arts]
    assert back == arts
    before, after = agg(arts), agg(back)
    assert before == after and row(before, D2).n_eligible == 2 and row(before, D3).n_eligible == 1
    assert [a.available_at_utc for a in back] == [a.available_at_utc for a in arts]


# ================================================================ S2.3: the slot accounting input

def test_a_slot_accounting_validates_its_counts_and_availability():
    t = IN_D2
    good = processed(t, [art(1, t)])
    assert good.processed and good.rows_captured == 1 and good.theme_rows == {"equity_us": 1, "rates_us": 0, "gold": 0}
    bad = [
        dict(batch_ts="2022-03-02", state="processed"),                                              # malformed stamp
        dict(batch_ts=t, state="maybe"),                                                             # unknown state
        dict(batch_ts=t, state="confirmed_absent", rows_captured=0),                                 # counts on an absent slot
        dict(batch_ts=t, state="in_progress", available_at_utc=verified(t)),
        dict(batch_ts=t, state="processed"),                                                         # nothing at all
        dict(batch_ts=t, state="processed", available_at_utc=verified(t), rows_captured=1, theme_rows={"equity_us": 1},
             filter_version=FV, parser_version=PV),                                                  # a theme is missing
        dict(batch_ts=t, state="processed", available_at_utc=verified(t), rows_captured=-1,
             theme_rows={"equity_us": 0, "rates_us": 0, "gold": 0}, filter_version=FV, parser_version=PV),
        dict(batch_ts=t, state="processed", available_at_utc=verified(t), rows_captured=True,
             theme_rows={"equity_us": 0, "rates_us": 0, "gold": 0}, filter_version=FV, parser_version=PV),
        dict(batch_ts=t, state="processed", available_at_utc=datetime(2022, 3, 2, 15, 0, tzinfo=UTC), rows_captured=0,
             theme_rows={"equity_us": 0, "rates_us": 0, "gold": 0}, filter_version=FV, parser_version=PV),   # before nominal + one slot
        dict(batch_ts=t, state="processed", available_at_utc=datetime(2022, 3, 2, 15, 15), rows_captured=0,
             theme_rows={"equity_us": 0, "rates_us": 0, "gold": 0}, filter_version=FV, parser_version=PV),   # naive
        dict(batch_ts=t, state="processed", available_at_utc=verified(t) + timedelta(milliseconds=5), rows_captured=0,
             theme_rows={"equity_us": 0, "rates_us": 0, "gold": 0}, filter_version=FV, parser_version=PV),   # sub-second
        dict(batch_ts=t, state="processed", available_at_utc=verified(t), rows_captured=0,
             theme_rows={"equity_us": 0, "rates_us": 0, "gold": 0}, near_empty="no", filter_version=FV, parser_version=PV),
        dict(batch_ts=t, state="processed", available_at_utc=verified(t), rows_captured=0,
             theme_rows={"equity_us": 0, "rates_us": 0, "gold": 0}, filter_version="", parser_version=PV),
    ]
    for kw in bad:
        with pytest.raises(sl.SentimentSlotError):
            sl.SlotAccounting(**kw)


def test_the_slot_states_are_exactly_those_the_manifest_can_report():
    rows = {
        "confirmed_absent": dict(existence="absent_confirmed", fetch_status="pending", parse_status="pending", commit_status="pending"),
        "absent_inconclusive": dict(existence="absent_inconclusive", fetch_status="pending", parse_status="pending", commit_status="pending"),
        "request_failed": dict(existence="request_failed", fetch_status="pending", parse_status="pending", commit_status="pending"),
        "inaccessible": dict(existence="inaccessible", fetch_status="pending", parse_status="pending", commit_status="pending"),
        "downloaded_invalid": dict(existence="present_invalid", fetch_status="fetched", parse_status="not_applicable", commit_status="not_applicable"),
        "processed": dict(existence="present_verified", fetch_status="fetched", parse_status="parsed_validated", commit_status="committed"),
        "parsed_validated": dict(existence="present_verified", fetch_status="fetched", parse_status="parsed_validated", commit_status="pending"),
        "in_progress": dict(existence="available", fetch_status="in_progress", parse_status="pending", commit_status="pending"),
        "verified_available": dict(existence="available", fetch_status="pending", parse_status="pending", commit_status="pending"),
        "unverified": dict(existence="unverified", fetch_status="pending", parse_status="pending", commit_status="pending"),
    }
    assert {name: slot_state(r) for name, r in rows.items()} == {name: name for name in rows}
    assert set(rows) == set(sl.ALL_STATES)                                                          # no state is unmapped or invented
    assert sl.SERIES_TO_THEME == {"EQUITY_US": "equity_us", "RATES_US": "rates_us", "GOLD": "gold"}
    assert tuple(sl.SERIES_TO_THEME.values()) == sc.THEMES


def manifest_row(**over):
    base = dict(batch_ts=IN_D2, existence="present_verified", fetch_status="fetched", parse_status="parsed_validated",
                commit_status="committed", availability_status="verified", available_at_utc="2022-03-02T15:15:00Z",
                rows_captured=12, near_empty_flag=None, filter_version=FV, parser_version=PV)
    return {**base, **over}


SERIES_ROWS = {"EQUITY_US": 5, "RATES_US": 4, "GOLD": 1}


def test_the_manifest_adapter_maps_real_counts_and_fails_closed_on_anything_missing():
    s = sl.slot_from_manifest(manifest_row(), SERIES_ROWS)
    assert s.state == "processed" and s.rows_captured == 12 and s.theme_rows == {"equity_us": 5, "rates_us": 4, "gold": 1}
    assert s.available_at_utc == verified(IN_D2) and s.near_empty is None and (s.filter_version, s.parser_version) == (FV, PV)
    assert sl.slot_from_manifest(manifest_row(near_empty_flag=1), SERIES_ROWS).near_empty is True
    assert sl.slot_from_manifest(manifest_row(near_empty_flag=0), SERIES_ROWS).near_empty is False
    absent_row = manifest_row(existence="absent_confirmed", available_at_utc=None, rows_captured=None, availability_status="not_applicable")
    assert sl.slot_from_manifest(absent_row, None).state == "confirmed_absent"                      # no counts needed or allowed
    for row_over, series in (({}, None), ({}, {"EQUITY_US": 5, "RATES_US": 4}), ({}, {**SERIES_ROWS, "OTHER": 1}),
                             ({}, {"EQUITY_US": 5, "RATES_US": 4, "GOLD": None}), ({}, {"EQUITY_US": 5, "RATES_US": 4, "GOLD": -1}),
                             ({"availability_status": "unverified"}, SERIES_ROWS), ({"available_at_utc": None}, SERIES_ROWS),
                             ({"available_at_utc": "2022-03-02 15:15"}, SERIES_ROWS), ({"rows_captured": None}, SERIES_ROWS),
                             ({"near_empty_flag": 2}, SERIES_ROWS), ({"filter_version": None}, SERIES_ROWS),
                             ({"available_at_utc": "2022-03-02T15:00:00Z"}, SERIES_ROWS)):
        with pytest.raises(sl.SentimentSlotError):
            sl.slot_from_manifest(manifest_row(**row_over), series)


def test_reconcile_slot_compares_the_same_stage_and_explains_every_difference():
    t = IN_D2
    recs = [art(1, t), art(2, t, flags={"equity_us": True, "rates_us": True, "gold": False}), art(3, t, flags={"equity_us": False, "rates_us": False, "gold": True})]
    ok = processed(t, recs)                                                                         # 3 captured; equity 2, rates 1, gold 1
    assert ok.theme_rows == {"equity_us": 2, "rates_us": 1, "gold": 1} and sl.reconcile_slot(ok, recs) == []
    assert sum(ok.theme_rows.values()) > ok.rows_captured                                           # a row can be in several themes
    assert any("rows_captured 3 but 2" in p for p in sl.reconcile_slot(ok, recs[:2]))               # a record missing
    assert any("rows_captured 3 but 4" in p for p in sl.reconcile_slot(ok, recs + [art(4, t)]))     # a record too many
    assert any("rates_us series rows 1 but 0" in p for p in sl.reconcile_slot(processed(t, recs, theme_rows={"equity_us": 2, "rates_us": 1, "gold": 1}), [recs[0], recs[0], recs[2]]))
    english_valid = processed(t, recs, rows=1121)                                                   # a count from an EARLIER stage
    assert any("rows_captured 1121 but 3" in p for p in sl.reconcile_slot(english_valid, recs))
    all_themes_equal_captured = processed(t, recs, theme_rows={"equity_us": 3, "rates_us": 3, "gold": 3})   # the S2.2 reading
    problems = sl.reconcile_slot(all_themes_equal_captured, recs)
    assert any("equity_us" in p for p in problems) and any("rates_us" in p for p in problems) and any("gold" in p for p in problems)
    assert any("inconsistent" in p for p in sl.reconcile_slot(processed(t, recs, rows=1, theme_rows={"equity_us": 2, "rates_us": 1, "gold": 1}), recs[:1]))
    assert any("differs from the batch availability" in p for p in sl.reconcile_slot(processed(t, recs, at=verified(t) + timedelta(hours=1)), recs))
    assert any("slot is confirmed_absent but 3" in p for p in sl.reconcile_slot(absent(t), recs))
    assert sl.reconcile_slot(absent(t), []) == []


@pytest.mark.skipif(not (SAMPLE / "manifest" / "manifest.sqlite").exists(), reason="the local B2-M sample is not present")
def test_the_contract_holds_on_every_batch_of_the_real_local_sample_read_only():
    """Counts and flags only (no titles are used); the manifest is opened read-only and immutable, nothing is written."""
    db = sqlite3.connect(f"file:{(SAMPLE / 'manifest' / 'manifest.sqlite').as_posix()}?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    slot_rows = [dict(r) for r in db.execute("SELECT * FROM slot WHERE existence = 'present_verified'")]
    series: dict[str, dict[str, int]] = defaultdict(dict)
    for r in db.execute("SELECT batch_ts, series, rows FROM slot_series_count"):
        series[r["batch_ts"]][r["series"]] = r["rows"]
    db.close()
    kept: dict[str, list] = defaultdict(list)
    for f in sorted((SAMPLE / "filtered" / "gdelt_filter_v1").rglob("*.tsv.gz")):
        text = gzip.decompress(f.read_bytes()).decode("utf-8")
        for r in csv.DictReader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\"):
            at = datetime.strptime(r["available_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            kept[r["batch_ts"]].append(SimpleNamespace(
                article_id=r["gkg_record_id"], availability_status="verified", available_at_utc=at,
                theme_flags={t: r[f"member_{t}"] == "1" for t in sc.THEMES}))
    assert len(slot_rows) == 192
    old_rule_holds = 0
    for r in slot_rows:
        s = sl.slot_from_manifest(r, series[r["batch_ts"]])
        assert s.state == "processed"
        assert sl.reconcile_slot(s, kept[r["batch_ts"]]) == [], r["batch_ts"]                      # the corrected contract: 192 / 192
        old_rule_holds += all(s.theme_rows[t] == len(kept[r["batch_ts"]]) for t in sc.THEMES)      # the S2.2 reading
    assert old_rule_holds == 0                                                                      # ... which held in 0 of 192


# ================================================================ S2.3 H1: slot / article reconciliation in the aggregator

def test_rows_the_slots_report_that_no_article_accounts_for_are_not_no_news():
    base = slots_for([])
    wrong = set_slots(base, D2, range(8), lambda t: processed(t, rows=10, theme_rows={"equity_us": 10, "rates_us": 0, "gold": 0}))
    r = row(agg([], slots=wrong), D2)
    assert r.coverage_status == "slot_article_mismatch" and "rows_captured 10 but 0" in r.reason
    all_unavailable(r)
    assert row(agg([], slots=wrong), D3).no_news is True                                           # the other day still reconciles


def test_a_count_mismatch_in_either_direction_or_stage_is_not_trusted():
    a = art(1, IN_D2)
    i = grid(D1, D2).index(IN_D2)
    for make, part in ((lambda t: processed(t, [a, a], rows=2, theme_rows={"equity_us": 2, "rates_us": 0, "gold": 0}), "rows_captured 2 but 1"),
                       (lambda t: absent(t), "slot is confirmed_absent but 1"),
                       (lambda t: processed(t, [a], rows=1000), "rows_captured 1000 but 1"),            # an earlier stage's count
                       (lambda t: processed(t, [a], theme_rows={"equity_us": 1, "rates_us": 1, "gold": 1}), "rates_us series rows 1 but 0")):
        r = row(agg([a], slots=set_slots(slots_for([a]), D2, [i], make)), D2)
        assert r.coverage_status == "slot_article_mismatch" and part in r.reason, part
        all_unavailable(r)
    assert row(agg([a]), D2).coverage_status == "ok"


def test_every_article_status_counts_toward_the_slot_whatever_its_theme_text_or_duplicate_label():
    arts = [art(1, IN_D2, dup="DUP_SAME_BATCH"), art(2, IN_D2, title=""), art(3, IN_D2, flags={**FLAGS, "equity_us": False}),
            art(4, IN_D2)]
    assert row(agg(arts), D2).coverage_status == "ok"                                              # 4 captured, equity 3, none else
    short = slots_for(arts[:3])                                                                     # slots that miss one record
    assert row(agg(arts, slots=short), D2).coverage_status == "slot_article_mismatch"


def test_a_record_availability_that_differs_from_its_batch_is_a_mismatch():
    a = art(1, IN_D2)
    i = grid(D1, D2).index(IN_D2)
    r = row(agg([a], slots=set_slots(slots_for([a]), D2, [i], lambda t: processed(t, [a], at=verified(t) + timedelta(minutes=30)))), D2)
    assert r.coverage_status == "slot_article_mismatch" and "differs from the batch availability" in r.reason


def test_mixed_filter_or_parser_versions_across_slots_are_refused():
    base = slots_for([])
    old = sl.SlotAccounting(base[D2][0].batch_ts, "processed", verified(base[D2][0].batch_ts), 0,
                            {"equity_us": 0, "rates_us": 0, "gold": 0}, False, "gdelt_filter_v0", PV)
    with pytest.raises(ft.SentimentFeatureError, match="different filter/parser versions"):
        agg([], slots=set_slots(base, D2, [0], lambda t: old))


# ================================================================ S2.3 H2: the late-batch interval contract

CUT2 = cutoff_utc(D2)                                                                               # 2022-03-02 21:00Z
LATE = datetime(2022, 3, 2, 21, 45, tzinfo=UTC)                                                     # the last D2 slot, one hour late


def test_a_batch_available_before_the_cutoff_is_in_its_own_interval():
    a = art(1, "20220302203000")                                                                    # nominal 20:30Z, available 20:45Z
    rows = agg([a])
    d2 = row(rows, D2)
    assert d2.n_eligible == 1 and d2.n_slots_delayed == 0 and d2.n_delayed_theme_rows == 0 and d2.n_late_carried_in == 0
    assert row(rows, D3).n_eligible == 0 and d2.no_news is False


def test_a_batch_available_exactly_at_the_cutoff_is_not_delayed():
    a = art(1, LAST_D2)                                                                             # available 21:00:00 = cutoff(D2)
    assert a.available_at_utc == CUT2
    rows = agg([a])
    d2 = row(rows, D2)
    assert (d2.n_eligible, d2.n_slots_delayed, d2.n_slots_covered, d2.coverage) == (1, 0, 96, 1.0)
    assert row(rows, D3).n_eligible == 0 and row(rows, D3).n_late_carried_in == 0


def test_a_batch_available_one_second_after_the_cutoff_is_delayed_into_the_next_interval():
    a = art(1, LAST_D2, at=CUT2 + timedelta(seconds=1))
    rows = agg([a])
    d2, d3 = row(rows, D2), row(rows, D3)
    assert (d2.n_eligible, d2.n_slots_delayed, d2.n_slots_covered) == (0, 1, 95)                   # not covered at D2's cutoff
    assert (d3.n_eligible, d3.n_late_carried_in, d3.coverage_status) == (1, 1, "ok")               # counted exactly once, in D3
    assert d3.n_slots_expected == 96 and d3.n_slots_covered == 96                                   # D3's own grid is unchanged


def test_a_delayed_batch_is_not_verified_no_news_in_its_nominal_interval():
    a = art(1, LAST_D2, at=LATE)                                                                    # the reported S3 case
    rows = agg([a])
    d2, d3 = row(rows, D2), row(rows, D3)
    assert d2.coverage_status == "ok" and d2.n_slots_delayed == 1 and d2.n_delayed_theme_rows == 1
    assert d2.n_eligible == 0 and d2.no_news is None and "delayed_availability" in d2.reason and d2.mean_net is None
    assert (d3.n_eligible, d3.n_late_carried_in, d3.no_news) == (1, 1, False)
    other = row(rows, D2, "gold")                                                                   # a theme the late batch does not carry
    assert other.n_delayed_theme_rows == 0 and other.no_news is None                                # F2: a delayed batch is in play, so zero is not verified
    assert other.theme_evidence == "unverified_empty" and "complete_with_delayed" in other.theme_evidence_reasons
    assert other.source_completeness == "complete_with_delayed" and other.interval_usability == "undecided_policy"


def test_a_delayed_batch_adds_a_note_when_other_news_exists_and_never_enters_the_earlier_features():
    inside = art(1, IN_D2)
    late = art(2, LAST_D2, at=LATE)
    with_late, without = agg([inside, late]), agg([inside])
    a, b = row(with_late, D2), row(without, D2)
    assert (a.n_eligible, a.mean_net, a.mean_p_pos, a.disp_net) == (b.n_eligible, b.mean_net, b.mean_p_pos, b.disp_net)
    assert "delayed_rows_not_available_at_cutoff_1" in a.reason and a.n_delayed_theme_rows == 1 and b.n_delayed_theme_rows == 0
    assert row(with_late, D3).n_eligible == 1 and row(without, D3).n_eligible == 0


def test_no_article_is_used_before_its_verified_availability_time():
    inside = art(1, IN_D2)
    for when in (CUT2 + timedelta(seconds=1), LATE, datetime(2022, 3, 3, 10, 0, tzinfo=UTC), datetime(2022, 3, 3, 21, 0, tzinfo=UTC)):
        rows = agg([inside, art(2, LAST_D2, at=when)])
        d2 = row(rows, D2)
        assert d2.n_eligible == 1                                                                   # never counted before it existed
        expected_day = D3 if when <= cutoff_utc(D3) else None
        assert row(rows, D3).n_late_carried_in == (1 if expected_day else 0)
        assert all(r.origin_date == origin_for(when, DAYS) or r.origin_date != D3 or when > cutoff_utc(D3) for r in rows if r.n_late_carried_in)


def test_a_late_batch_beyond_the_last_cutoff_is_reported_not_silently_used():
    a = art(1, "20220303204500", at=cutoff_utc(D3) + timedelta(hours=3))                           # nominal slot of D3, available after D3
    rows = agg([a])
    d3 = row(rows, D3)
    assert d3.n_slots_delayed == 1 and d3.n_delayed_theme_rows == 1 and d3.n_eligible == 0 and d3.no_news is None
    assert not any(r.n_eligible for r in rows)                                                      # it has no interval in this window


def test_a_weekend_delay_lands_in_the_next_trading_day_with_its_accounting():
    thu, fri, mon = date(2022, 3, 3), date(2022, 3, 4), date(2022, 3, 7)
    days = [thu, fri, mon]
    a = art(1, "20220304204500", at=datetime(2022, 3, 5, 6, 0, tzinfo=UTC))                         # Friday's last slot, available Saturday
    rows = agg([a], days=days)
    assert (row(rows, fri).n_slots_delayed, row(rows, fri).no_news) == (1, None)
    assert (row(rows, mon).n_eligible, row(rows, mon).n_late_carried_in, row(rows, mon).coverage_status) == (1, 1, "ok")


def test_a_late_article_without_a_reconciled_source_slot_is_never_used():
    a = art(1, LAST_D2, at=LATE)
    no_source = slots_for([a])
    del no_source[D2]                                                                               # the source interval has no slot information
    rows = agg([a], slots=no_source)
    assert row(rows, D2).coverage_status == "no_expected_slots"
    d3 = row(rows, D3)
    assert d3.coverage_status == "slot_article_mismatch" and "without a reconciled source slot" in d3.reason and LAST_D2 in d3.reason
    all_unavailable(d3)
    missing_slot = slots_for([a])
    missing_slot[D2] = missing_slot[D2][:-1]                                                        # the source grid is broken
    broken = agg([a], slots=missing_slot)
    assert row(broken, D2).coverage_status == "slot_grid_mismatch" and row(broken, D3).coverage_status == "slot_article_mismatch"
    wrong_counts = set_slots(slots_for([a]), D2, [95], lambda t: processed(t, [a], rows=3))         # the source slot disagrees
    mismatched = agg([a], slots=wrong_counts)
    assert row(mismatched, D2).coverage_status == "slot_article_mismatch" and row(mismatched, D3).coverage_status == "slot_article_mismatch"


def test_an_article_from_before_the_window_with_no_source_slot_cannot_enter_an_interval():
    a = art(1, "20220301203000", at=datetime(2022, 3, 2, 9, 0, tzinfo=UTC))                         # a D1-interval batch that arrived late
    r = row(agg([a], slots=slots_for([])), D2)
    assert r.coverage_status == "slot_article_mismatch" and "without a reconciled source slot" in r.reason


def test_incomplete_source_accounting_is_its_own_status_and_never_no_news():
    for state in ("in_progress", "verified_available", "unverified", "parsed_validated"):
        slots = set_slots(slots_for([]), D2, [10], lambda t, s=state: sl.SlotAccounting(t, s))
        r = row(agg([], slots=slots), D2)
        assert r.coverage_status == "incomplete_source_accounting" and state in r.reason and r.n_slots_expected == 96
        all_unavailable(r)
        assert row(agg([], slots=slots), D3).no_news is True                                       # only the affected interval is unavailable
    terminal = set_slots(slots_for([]), D2, [10], lambda t: sl.SlotAccounting(t, "downloaded_invalid"))
    assert row(agg([], slots=terminal), D2).coverage_status == "ok"                                 # a final failed slot is missing, not incomplete


def test_delay_accounting_is_deterministic_across_repeated_runs_and_orderings():
    arts = [art(1, IN_D2), art(2, LAST_D2, at=LATE), art(3, "20220302203000"), art(4, IN_D3)]
    slots = slots_for(arts)
    first = aggregate(arts, DAYS, slots, config=CFG)
    assert first == aggregate(arts, DAYS, slots, config=CFG) == aggregate(list(reversed(arts)), DAYS, slots, config=CFG)
    assert first == aggregate(arts, DAYS, {d: list(reversed(v)) for d, v in slots.items()}, config=CFG)


def test_a_far_future_batch_cannot_change_an_earlier_row_even_with_delay_accounting():
    base = [art(1, IN_D2), art(2, LAST_D2, at=LATE)]
    later = base + [art(3, IN_D3, ), art(4, "20220303204500", at=datetime(2022, 3, 5, 0, 0, tzinfo=UTC))]
    assert row(agg(base), D2) == row(agg(later), D2)


# ================================================================ S2.2 H2: the expected slot grid (nominal)

def test_the_expected_grid_sizes_follow_the_cutoffs():
    assert len(grid(D1, D2)) == 96 and grid(D1, D2)[0] == "20220301210000" and grid(D1, D2)[-1] == LAST_D2
    assert len(grid(date(2022, 3, 4), date(2022, 3, 7))) == 288                                     # Friday close to Monday close (EST)


def test_a_single_slot_never_implies_a_covered_24_hour_interval():
    slots = {**slots_for([]), D2: [processed(grid(D1, D2)[0])]}
    r = row(agg([], slots=slots), D2)
    assert r.coverage_status == "slot_grid_mismatch" and "96 expected" in r.reason and r.n_slots_expected == 96
    assert r.coverage is None
    all_unavailable(r)


def test_missing_duplicate_unexpected_and_mismatched_slots_are_detected():
    base = slots_for([])
    missing = {**base, D2: base[D2][1:]}
    duplicate = {**base, D2: base[D2] + [base[D2][0]]}
    unexpected = {**base, D2: base[D2] + [processed("20220302210000")]}                              # first slot of the NEXT day
    wrong_day = {**base, D2: slots_for([])[D3]}                                                      # D3's grid under D2
    renamed = {**base, D2: [processed("20220301150000")] + base[D2][1:]}                              # a valid stamp, but not this interval's
    with pytest.raises(sl.SentimentSlotError):
        sl.SlotAccounting("20220302152000", "confirmed_absent")                                      # an off-grid stamp cannot even be built
    for bad in (missing, duplicate, unexpected, wrong_day, renamed):
        r = row(agg([], slots=bad), D2)
        assert r.coverage_status == "slot_grid_mismatch", bad
        all_unavailable(r)
    assert "missing 1" in row(agg([], slots=missing), D2).reason and "duplicate 1" in row(agg([], slots=duplicate), D2).reason


def test_malformed_slot_objects_and_unknown_origin_days_are_refused():
    base = slots_for([])
    with pytest.raises(ft.SentimentFeatureError, match="SlotAccounting"):
        agg([], slots={**base, D2: [object()] * 96})                                                 # type: ignore[list-item]
    with pytest.raises(ft.SentimentFeatureError, match="SlotAccounting"):
        agg([], slots={**base, D2: iter(base[D2])})                                                  # type: ignore[dict-item]
    with pytest.raises(ft.SentimentFeatureError, match="origin day"):
        agg([], slots={**base, D1: base[D2]})                                                        # D1 has no row: it is the lower bound only
    with pytest.raises(ft.SentimentFeatureError, match="origin day"):
        agg([], slots={**base, date(2022, 3, 9): base[D2]})


# ================================================================ S2.2 H3: the trading calendar

def test_malformed_trading_calendars_fail_closed():
    base = slots_for([])
    for days, part in (([D2, D1], "sorted"), ([D1, D1], "sorted"), ([D1], "at least two"), ([], "at least two"),
                       ([date(2022, 3, 4), date(2022, 3, 5)], "weekend"),                           # Saturday
                       ([datetime(2022, 3, 1), datetime(2022, 3, 2)], "plain date"),
                       ([D1, D3], "missing expected trading days")):                                # Wednesday skipped
        with pytest.raises(ft.SentimentFeatureError, match=part):
            aggregate([], days, base, config=CFG)
    with pytest.raises(ft.SentimentFeatureError, match="themes"):
        aggregate([], DAYS, base, config=CFG, themes=("crypto",))
    with pytest.raises(ft.SentimentFeatureError, match="themes"):
        aggregate([], DAYS, base, config=CFG, themes=("gold", "gold"))


def test_a_skipped_day_cannot_merge_two_intervals():
    a = art(1, "20220301150000")                                                                    # Tuesday
    with pytest.raises(ft.SentimentFeatureError, match="missing expected trading days"):
        aggregate([a], [date(2022, 2, 28), D2], {D2: []}, config=CFG)                      # Tuesday absent from the calendar


def test_weekends_and_holidays_are_explicit_inputs():
    fri, mon = date(2022, 3, 4), date(2022, 3, 7)
    a = art(1, "20220305120000")                                                                    # Saturday
    rows = agg([a], days=[fri, mon])
    assert row(rows, mon).n_eligible == 1 and row(rows, mon).n_slots_expected == 288                # a weekend gap is implicit
    wed, fri_ = date(2022, 11, 23), date(2022, 11, 25)
    with pytest.raises(ft.SentimentFeatureError, match="missing expected trading days"):
        aggregate([], [wed, fri_], {}, config=CFG)                                         # Thanksgiving not declared a holiday
    cfg = dataclasses.replace(CFG, market_holidays=frozenset({date(2022, 11, 24)}))
    assert len(agg([], days=[wed, fri_], cfg=cfg)) == 3                                             # declared: accepted
    with pytest.raises(ft.SentimentFeatureError, match="market holiday"):
        aggregate([], [wed, date(2022, 11, 24), fri_], {}, config=cfg)


def test_calendar_config_inputs_are_validated():
    for kw in ({"early_closes": frozenset({date(2022, 3, 5)})}, {"early_closes": {date(2022, 3, 1)}},
               {"early_closes": frozenset({datetime(2022, 3, 1)})}, {"market_holidays": frozenset({"2022-03-01"})},
               {"market_holidays": frozenset({date(2022, 3, 1)}), "early_closes": frozenset({date(2022, 3, 1)})}):
        with pytest.raises(ft.SentimentFeatureError):
            dataclasses.replace(CFG, **kw)


def test_dst_transitions_change_the_cutoff_and_the_grid():
    fri, mon = date(2022, 3, 11), date(2022, 3, 14)                                                 # DST began Sunday 2022-03-13
    assert cutoff_utc(fri).hour == 21 and cutoff_utc(mon).hour == 20
    assert len(grid(fri, mon)) == 284                                                               # 71 hours, not 72
    inside, outside = art(1, "20220314194500"), art(2, "20220314200000")                            # available 20:00Z (cutoff) and 20:15Z
    rows = agg([inside, outside], days=[fri, mon])
    assert row(rows, mon).n_eligible == 1 and row(rows, mon).n_slots_expected == 284
    assert row(rows, mon).feature_cutoff_utc == datetime(2022, 3, 14, 20, 0, tzinfo=UTC)
    fri2, mon2 = date(2022, 11, 4), date(2022, 11, 7)                                               # DST ended Sunday 2022-11-06
    assert cutoff_utc(fri2).hour == 20 and cutoff_utc(mon2).hour == 21 and len(grid(fri2, mon2)) == 292
    a, b = art(3, "20221107204500"), art(4, "20221107210000")                                       # 21:00Z (cutoff) and 21:15Z
    assert row(agg([a, b], days=[fri2, mon2]), mon2).n_eligible == 1                                # 21:15Z is after the EST cutoff


def test_the_early_close_calendar_is_an_explicit_input():
    day = date(2022, 11, 25)                                                                         # PROPOSED early close (13:00 ET)
    days = [date(2022, 11, 23), day]
    base = dataclasses.replace(CFG, market_holidays=frozenset({date(2022, 11, 24)}))
    with_early = dataclasses.replace(base, early_closes=PROPOSED_EARLY_CLOSES)
    a = art(1, "20221125180000")                                                                     # 18:15Z = 13:15 EST: after the early close
    early, regular = agg([a], days=days, cfg=with_early), agg([a], days=days, cfg=base)
    assert row(early, day).n_eligible == 0 and row(regular, day).n_eligible == 1
    assert row(early, day).n_slots_expected == 180 and row(regular, day).n_slots_expected == 192     # 45 h versus 48 h
    assert row(early, day).feature_cutoff_utc.hour == 18


# ================================================================ S2.2 H4/H5: duplicates, story versions, duplicates-only days

def test_two_original_records_for_one_story_are_unresolved_not_silently_counted():
    r = row(agg([art(1, IN_D2, story="S-1"), art(2, IN_D2, story="S-1")]), D2)
    assert r.dedup_status == "unresolved_story_ids" and (r.n_eligible, r.n_distinct_stories) == (2, 1)
    assert r.mean_net is None and r.mean_p_pos is None and r.disp_net is None and r.no_news is None
    assert "unapproved" in r.reason
    distinct = row(agg([art(1, IN_D2, story="S-1"), art(2, IN_D2, story="S-2")]), D2)
    assert distinct.dedup_status == "none_found" and distinct.n_distinct_stories == 2 and distinct.mean_net is not None


def test_an_update_chain_is_kept_under_the_proposed_policy_and_labelled():
    chain = [art(1, IN_D2, story="S-1"), art(2, "20220302160000", dup="UPDATE", story="S-1"),
             art(3, "20220302170000", dup="UPDATE", story="S-1")]
    r = row(agg(chain), D2)
    assert (r.n_eligible, r.n_distinct_stories, r.n_update_versions, r.n_duplicates_removed) == (3, 1, 2, 0)
    assert r.dedup_status == "versions_kept_proposed" and "update_versions_kept" in r.reason and r.mean_net is not None
    assert r.rules_status == "PROPOSED_NOT_APPROVED"
    update_only = row(agg(chain[1:]), D2)                                                            # the original was on an earlier day
    assert update_only.dedup_status == "versions_kept_proposed" and update_only.n_eligible == 2


def test_a_duplicates_only_day_is_not_verified_no_news():
    r = row(agg([art(1, IN_D2, dup="REOBSERVATION"), art(2, IN_D2, dup="SYNDICATED")]), D2)
    assert r.n_eligible == 0 and r.n_duplicates_removed == 2
    assert r.no_news is None and r.dedup_status == "duplicates_only_unresolved" and "only_duplicate" in r.reason
    assert r.mean_net is None
    assert row(agg([]), D2).no_news is True                                                          # a day with nothing is still no news
    mixed = row(agg([art(1, IN_D2, dup="REOBSERVATION"), art(2, IN_D2, title="")]), D2)              # invalid text exists: news existed
    assert mixed.no_news is False and mixed.dedup_status == "duplicates_removed_proposed"


# ================================================================ S2.2 H6: scoring coverage is separate from source coverage

def test_partial_scoring_is_exposed_and_never_presented_as_complete():
    arts = [art(i, IN_D2) for i in range(1, 5)]
    partial = row(agg([unscored(arts[0])] + arts[1:]), D2)
    assert (partial.n_eligible, partial.n_scored) == (4, 3) and partial.scoring_status == "partial"
    assert partial.scoring_coverage == pytest.approx(0.75) and "partially_scored_3_of_4" in partial.reason
    assert partial.coverage == 1.0 and partial.coverage_status == "ok"                                # source coverage is separate
    heavy = [unscored(a) for a in [art(i, IN_D2) for i in range(1, 51)]] + [art(99, IN_D2)]
    r = row(agg(heavy), D2)
    assert r.scoring_status == "partial" and r.scoring_coverage == pytest.approx(1 / 51) and r.mean_net is not None
    assert row(agg(arts), D2).scoring_status == "complete" and row(agg([]), D2).scoring_status == "not_applicable"
    assert "min_scoring" not in inspect.signature(ft.SentimentConfig).parameters                       # no threshold is invented


# ================================================================ S2.2 M1/M2: provenance and temporal consistency

def test_scorer_provenance_is_never_mixed_including_unavailable_records():
    good = art(1, IN_D2)
    for over in ({"model_id": "OTHER_MODEL"}, {"model_revision": "fake-v2"}, {"scorer_code_sha256": "0" * 64}):
        for other in (dataclasses.replace(art(2, IN_D2), **over),                                    # a scored record
                      dataclasses.replace(unscored(art(3, IN_D2)), **over),                          # a scorer-failure record
                      dataclasses.replace(art(4, IN_D2, title=""), **over)):                         # an unscorable-text record
            with pytest.raises(ft.SentimentFeatureError, match="different model, revision or scorer code"):
                agg([good, other])
    assert row(agg([good, art(2, IN_D2)]), D2).n_eligible == 2                                      # identical provenance is fine


def test_duplicate_article_ids_and_invalid_records_fail_closed():
    with pytest.raises(ft.SentimentFeatureError, match="duplicate article_id"):
        agg([art(1, IN_D2), art(1, "20220302160000")])
    with pytest.raises(sc.SentimentSchemaError):
        agg([dataclasses.replace(art(1, IN_D2), p_positive=float("nan"))])
    with pytest.raises(sc.SentimentSchemaError):
        agg([{"article_id": "x"}], slots=slots_for([]))                                             # type: ignore[list-item]


def test_a_record_cannot_be_scored_before_it_was_available():
    r = art(1, IN_D2)
    early = dataclasses.replace(r, scored_at_utc=r.available_at_utc - timedelta(seconds=1))
    assert any("before it was available" in p for p in sc.problems(early, allow_test_only=True))
    on_time = dataclasses.replace(r, scored_at_utc=r.available_at_utc)
    assert sc.problems(on_time, allow_test_only=True) == []
    with pytest.raises(sc.SentimentSchemaError):
        fs.FakeScorerTestOnly(min_chars=20).score(fs.SyntheticArticle("SYN-1", IN_D2, r.available_at_utc, "verified", "x.invalid",
                                                                      "SYNTHETIC headline about nothing real", FLAGS, "s"),
                                                  scored_at=r.available_at_utc - SLOT)


def test_unavailable_records_are_consistent_with_the_schema():
    base = unscored(art(1, IN_D2))
    assert sc.problems(base, allow_test_only=True) == []
    cases = {
        "scored_at": dataclasses.replace(base, scored_at_utc=SCORED_AT),
        "no reason": dataclasses.replace(base, unavailable_reason=None),
        "unknown reason": dataclasses.replace(base, unavailable_reason="because"),
        "text ok but text reason": dataclasses.replace(base, unavailable_reason="text_short"),
        "vector": dataclasses.replace(base, p_neutral=1.0),
    }
    for name, rec in cases.items():
        assert sc.problems(rec, allow_test_only=True), name
    bad_text = art(2, IN_D2, title="short")
    assert any("contradicts" in p for p in sc.problems(dataclasses.replace(bad_text, unavailable_reason="scorer_failure"), allow_test_only=True))
    assert any("must not carry" in p for p in sc.problems(dataclasses.replace(art(3, IN_D2), unavailable_reason="scorer_failure"), allow_test_only=True))
    assert unscored(art(1, IN_D2)).unavailable_reason == "scorer_failure" and art(1, IN_D2, title="").unavailable_reason == "text_empty"


# ================================================================ S2.2 M3: near-empty slots

def test_near_empty_but_processed_slots_are_not_counted_as_covered_and_are_visible():
    thirty = set_slots(slots_for([]), D2, range(30), lambda t: processed(t, near=True))              # 66 of 96 covered = 0.6875
    r = row(agg([], slots=thirty), D2)
    assert r.coverage_status == "ok" and (r.n_slots_covered, r.n_slots_near_empty) == (66, 30) and r.coverage_threshold_met is False
    assert "near_empty_slots" in r.reason and r.no_news is None                                      # visible, and never a verified quiet day
    twenty = set_slots(slots_for([]), D2, range(20), lambda t: processed(t, near=True))              # 76 of 96 covered
    ok = row(agg([], slots=twenty), D2)
    assert ok.coverage_status == "ok" and ok.n_slots_near_empty == 20 and ok.coverage == pytest.approx(76 / 96)
    assert ok.no_news is None and ok.theme_evidence == "unverified_empty" and "near_empty_slots" in ok.theme_evidence_reasons   # F2: not verified zero
    every = set_slots(slots_for([]), D2, range(96), lambda t: processed(t, near=True))
    full = row(agg([], slots=every), D2)
    assert full.coverage_status == "ok" and full.coverage == 0.0 and full.coverage_threshold_met is False      # processed, so not "missing_source_batches"


# ================================================================ S2.2 M4: the test-only guard fails closed

def test_the_test_only_scorer_and_the_config_cannot_be_paired_by_accident():
    with pytest.raises(ft.SentimentFeatureError, match="test-only"):
        dataclasses.replace(CFG, allow_test_only=False)                                              # fake model expected, flag off
    with pytest.raises(ft.SentimentFeatureError, match="test-only"):
        dataclasses.replace(CFG, expected_model_id="REAL_MODEL")                                     # real model, flag still on
    production = dataclasses.replace(CFG, expected_model_id="REAL_MODEL", allow_test_only=False)
    with pytest.raises(sc.SentimentSchemaError, match="test-only"):
        agg([art(1, IN_D2)], cfg=production)                                                         # a fake record is refused outright
    with pytest.raises(ft.SentimentFeatureError, match="SHA-256"):
        dataclasses.replace(CFG, expected_scorer_code_sha256="abc")
    with pytest.raises(ft.SentimentFeatureError, match="bool"):
        dataclasses.replace(CFG, allow_test_only=1)


def test_the_fake_scorer_refuses_to_run_outside_a_test_session(monkeypatch):
    monkeypatch.delitem(sys.modules, "pytest")
    with pytest.raises(fs.FakeScorerUseError, match="test-only"):
        fs.FakeScorerTestOnly(min_chars=20)
    monkeypatch.undo()
    assert fs.FakeScorerTestOnly(min_chars=20).TEST_ONLY is True


# ================================================================ S2.2 M7: theme-specific calendars stay blocked

def test_theme_specific_calendars_are_not_implemented():
    params = inspect.signature(ft.aggregate_daily).parameters
    assert not any("calendar" in p or "cutoff" in p for p in params)
    rows = agg([art(1, IN_D2)])
    assert len({r.feature_cutoff_utc for r in rows if r.origin_date == D2}) == 1                      # one equity-session cutoff for all themes


# ================================================================ isolation

def test_the_scaffold_touches_no_key_label_suggestion_store_or_network():
    forbidden = ("key_sealed", "annotation_A", "annotate", "ai_only", "ai_bridge", "ai_origin", "evaluate", "overlap_lock", "labeller",
                 "working", "Paths(", "urllib", "socket", "requests", "transformers", "torch", "huggingface", "anthropic",
                 "open(", "read_text", "write_text", "os.environ", "subprocess")
    for f in PKG.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        imports = "\n".join(ln for ln in text.splitlines() if ln.startswith(("import ", "from ")))
        for word in forbidden:
            assert word not in imports, (f.name, word)
        for word in ("key_sealed", "annotation_A", "ai_only", "urllib", "socket", "transformers", "torch", "huggingface", "subprocess",
                     "os.environ", "sqlite3"):
            assert word not in text, (f.name, word)                                                  # the package never opens a database


# The ONE explicit exception (owner milestone 2026-10-20): a local, offline, human-run research preparation tool that builds the annotation sample. It is not a production entry point. It is checked
# by its own test below (no network, model, scoring, sealed-key or label access). No other script, helper or backend module may import the scaffold.
ALLOWED_RESEARCH_TOOLS = frozenset({"scripts/build_sentiment_validation_sample.py"})


def test_the_only_allowed_research_tool_touches_no_network_model_scoring_key_or_label():
    text = (ROOT / "scripts/build_sentiment_validation_sample.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in text.splitlines() if l.startswith(("import ", "from ")))
    for word in ("urllib", "socket", "requests", "transformers", "torch", "huggingface", "anthropic", "subprocess", "fake_scorer", "scorer_port", "aggregate_daily", "features", "orchestrator"):
        assert word not in code, word
    for word in ("key_sealed", "ai_only", "ai_bridge", "labeller", "working/", "os.environ", "http://", "https://"):
        assert word not in text, word
    assert 'columns_read": ["gkg_record_id"]' in text and "mode=ro&immutable=1" in text and "refusing to overwrite" in text


def test_no_production_entry_point_or_helper_imports_the_sentiment_scaffold():
    this = Path(__file__).resolve()
    checked = 0
    for top in ("backend", "training", "scripts", "tests"):
        base = ROOT / top
        if not base.exists():
            continue
        for f in base.rglob("*.py"):
            parts = set(f.parts)
            if f.resolve() == this or PKG in f.parents or parts & {".venv", "venv", "site-packages", "node_modules", "__pycache__"} \
                    or (f.parent == this.parent and f.name.startswith("test_sentiment_")) \
                    or f.relative_to(ROOT).as_posix() in ALLOWED_RESEARCH_TOOLS:                           # the scaffold's own test files; the one allowed research tool
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            for needle in ("gdelt.sentiment", "import sentiment", "sentiment.fake_scorer", "FakeScorerTestOnly"):
                assert needle not in text, (str(f.relative_to(ROOT)), needle)
            checked += 1
    assert checked > 50                                                                              # the scan really walked the tree
    for name in ("agents", "core", "api"):
        assert (ROOT / "backend" / "wealthpilot" / name).exists()


def test_the_scaffold_does_not_change_the_gates_or_the_criteria():
    import wealthpilot.data.gdelt as pkg
    from wealthpilot.data.gdelt import decision
    from wealthpilot.data.gdelt.ai import provider
    assert pkg.AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD is False and dict(provider.ADAPTERS) == {}
    assert decision.CRITERIA == {"precision_min": 0.70, "precision_lower_bound_min": 0.60, "pooled_recall_min": 0.90,
                                 "reporting_floor_non_ambiguous": 100}
    assert decision.APPROVED_CRITERIA_SHA256 == decision.criteria_sha256()


def test_the_required_schema_and_feature_fields_exist():
    assert sc.FIELD_NAMES == ("article_id", "batch_ts", "available_at_utc", "availability_status", "source_domain", "title_sha256",
                              "text_status", "theme_flags", "story_id", "dup_status", "model_id", "model_revision", "p_positive",
                              "p_negative", "p_neutral", "pred_label", "unavailable_reason", "scored_at_utc", "scorer_code_sha256",
                              "schema_version")
    names = {f.name for f in dataclasses.fields(ft.DailyFeatures)}
    assert {"n_eligible", "n_scored", "n_duplicates_removed", "coverage", "coverage_status", "mean_p_pos", "mean_p_neg", "mean_net",
            "disp_net", "no_news", "feature_cutoff_utc", "model_revision", "schema_version", "scoring_coverage", "scoring_status",
            "dedup_status", "n_distinct_stories", "n_update_versions", "n_slots_expected", "n_slots_covered",
            "n_slots_near_empty", "n_slots_delayed", "n_delayed_theme_rows", "n_late_carried_in"} <= names
    assert "n_unavailable" not in names                                                              # an always-zero field would hide missingness
    assert {"source_completeness", "interval_usability", "theme_evidence", "theme_evidence_reasons", "result_availability",
            "result_reason", "n_slots_near_empty_unknown"} <= names                                    # the shared vocabulary (S2.8D)


# ================================================================ S2.8D: the shared completeness vocabulary in the feature rows

def test_s28d_rows_carry_four_distinct_states_and_verified_zero_needs_full_evidence():
    arts = [art(1, IN_D2)]
    equity, gold = row(agg(arts), D2), row(agg(arts), D2, "gold")
    assert (equity.source_completeness, equity.interval_usability, equity.theme_evidence) == ("complete", "usable", "has_records")
    assert equity.result_availability == "available_test_only"                                      # the test-only scorer can never give a research result
    assert (gold.theme_evidence, gold.no_news, gold.result_availability) == ("verified_zero_records", True, "unavailable")   # nothing to score: no value
    unknown = set_slots(slots_for([]), D2, range(96), lambda t: processed(t, near=None))
    r = row(agg([], slots=unknown), D2)
    assert r.n_slots_near_empty_unknown == 96 and r.n_slots_near_empty == 0 and r.no_news is None   # unknown is not near-empty, not false, not empty
    assert r.source_completeness == "complete" and r.interval_usability == "undecided_policy" and r.theme_evidence == "unverified_empty"


def test_s28d_missing_or_incomplete_evidence_never_becomes_a_value_or_no_news():
    arts = [art(1, IN_D2)]
    cases = {
        "missing slot": {**slots_for(arts), D2: slots_for(arts)[D2][1:]},
        "non-final": set_slots(slots_for(arts), D2, [3], lambda t: sl.SlotAccounting(t, "in_progress")),
        "rejected": set_slots(slots_for(arts), D2, [grid(D1, D2).index(IN_D2)], lambda t: processed(t, arts, rows=5)),
    }
    for label, slots in cases.items():
        r = row(agg(arts, slots=slots), D2)
        assert r.interval_usability == "unusable_incomplete" and r.source_completeness == "incomplete", label
        assert r.no_news is None and r.mean_net is None and r.mean_p_pos is None and r.n_eligible is None, label
        assert r.theme_evidence == "not_evaluated" and r.result_availability == "unavailable", label


def test_s28d_scoring_not_performed_is_its_own_result_state():
    r = row(agg([unscored(art(1, IN_D2))]), D2)
    assert r.result_availability == "scoring_not_performed" and r.mean_net is None and r.scoring_status == "none_scored"
    assert row(agg([art(1, IN_D2, title="")]), D2).result_availability == "scoring_not_performed"       # unscorable text: still no value


def test_s28d_c_min_evidence_marks_the_interval_incomplete_and_is_required():
    unresolved = aggregate([], DAYS, slots_for([]), config=CFG, earlier=EarlierEvidence(True, ("20220301100000",)))
    assert {r.coverage_status for r in unresolved} == {"incomplete_source_accounting"} and {r.no_news for r in unresolved} == {None}
    by_interval = aggregate([], DAYS, slots_for([]), config=CFG, earlier=EarlierEvidence(True, (), ((D2, ("20220301100000",)),)))
    assert row(by_interval, D2).source_completeness == "incomplete" and row(by_interval, D3).source_completeness == "complete"
    reconciled = aggregate([], DAYS, slots_for([]), config=CFG, earlier=EarlierEvidence(True, (), (), ((D2, 1),)))
    assert row(reconciled, D2).source_completeness == "complete_with_delayed" and row(reconciled, D2).no_news is None
    with pytest.raises(TypeError):
        ft.aggregate_daily([], DAYS, slots_for([]), config=CFG)                                     # type: ignore[call-arg]


def test_s28d_an_unreconciled_late_batch_makes_the_interval_it_lands_in_incomplete_even_without_its_records():
    late = datetime(2022, 3, 2, 21, 45, tzinfo=UTC)
    a = art(1, LAST_D2, at=late)
    bad = set_slots(slots_for([a]), D2, [95], lambda t: processed(t, [a], at=late, rows=3))        # counts do not reconcile; available in D3
    rows = agg([], slots=bad)                                                                         # ...and its record is not even supplied
    assert row(rows, D2).source_completeness == "incomplete" and row(rows, D3).source_completeness == "incomplete"
    assert row(rows, D3).coverage_status == "incomplete_source_accounting" and row(rows, D3).no_news is None
