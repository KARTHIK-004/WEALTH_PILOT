"""Scorer port, polarity-validation infrastructure and the integrated pipeline entry point.

Everything here is SYNTHETIC. The stub scorer below is not a model and its outputs are not sentiment; the synthetic reference labels are test fixtures, not ground truth.
No real model exists or is loaded; no file, key, label store or network is touched.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from wealthpilot.data.gdelt.sentiment import orchestrator as orc
from wealthpilot.data.gdelt.sentiment import pipeline as pl
from wealthpilot.data.gdelt.sentiment import polarity_validation as pv
from wealthpilot.data.gdelt.sentiment import scorer_port as sp
from wealthpilot.data.gdelt.sentiment.policy import APPLIED_APPROVED, PolicyBlockedError, PolicyState
from wealthpilot.data.gdelt.sentiment.schema import LABELS, TEST_ONLY_MODEL_ID

_spec = importlib.util.spec_from_file_location("_wp_orchestrator_world2", Path(__file__).with_name("test_sentiment_orchestrator.py"))
W = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = W
_spec.loader.exec_module(W)

PKG = Path(__file__).resolve().parents[4] / "backend/wealthpilot/data/gdelt/sentiment"
UTC = timezone.utc
SHA = "a" * 64
MAP = {"LABEL_0": "positive", "LABEL_1": "negative", "LABEL_2": "neutral"}
IDENT = sp.ScorerIdentity("UNIT_TEST_STUB_NOT_A_MODEL", "stub-0", SHA, SHA, MAP)
SCORER_APPLIED = PolicyState.from_mapping({sp.SCORER_POLICY: APPLIED_APPROVED})            # a TEST FIXTURE: nothing in production builds this
GOOD = {"LABEL_0": 0.2, "LABEL_1": 0.3, "LABEL_2": 0.5}


class Stub:
    """Not a model: returns whatever the test tells it to, and counts calls."""

    def __init__(self, outputs=GOOD, *, boom=False, short=False):
        self.identity, self.outputs, self.boom, self.short, self.calls, self.texts = IDENT, outputs, boom, short, 0, []

    def score_batch(self, texts):
        self.calls += 1
        self.texts += list(texts)
        if self.boom:
            raise RuntimeError("model crashed")
        out = [self.outputs(t) if callable(self.outputs) else self.outputs for t in texts]
        return out[:-1] if self.short else out


def cands(*titles_over):
    """Real CandidateRecords from the synthetic world; the first records of D2 with titles overridden where given."""
    recs = [r for i in W.World({W.IN_D2: [{} for _ in titles_over or [0, 0, 0]]}).run().intervals for r in i.records]
    return [dataclasses.replace(r, title=t) if t is not None else r for r, t in zip(recs, titles_over or [None] * len(recs))]


# ================================================================ scorer port

def test_scoring_is_blocked_while_the_scorer_policy_is_unresolved_and_the_scorer_is_never_called():
    stub = Stub()
    live = PolicyState.from_mapping(orc.POLICY_STATUS)
    with pytest.raises(PolicyBlockedError):
        sp.score_candidates(cands(None, None), stub, policy=live, min_chars=20)
    assert stub.calls == 0


def test_the_test_only_identity_and_a_bad_identity_are_refused():
    for bad in (dict(model_id=TEST_ONLY_MODEL_ID), dict(model_id=" "), dict(weights_sha256="xyz"), dict(scorer_code_sha256=""),
                dict(label_map={"a": "positive", "b": "negative"}), dict(label_map={"a": "positive", "b": "positive", "c": "neutral"}),
                dict(label_map={"a": "positive", "b": "negative", "c": "bullish"})):
        with pytest.raises(sp.ScorerPortError):
            dataclasses.replace(IDENT, **bad)


def test_valid_output_is_mapped_to_schema_labels_with_an_argmax_label_and_traceable_order():
    cs = cands(None, None, None)
    out = sp.score_candidates(cs, Stub(), policy=SCORER_APPLIED, min_chars=20)
    assert [o.candidate_id for o in out] == [c.article_id for c in cs]
    assert all(o.label == "neutral" and o.probabilities == (0.2, 0.3, 0.5) and o.unavailable_reason is None for o in out)
    tie = sp.score_candidates(cs[:1], Stub({"LABEL_0": 0.4, "LABEL_1": 0.4, "LABEL_2": 0.2}), policy=SCORER_APPLIED, min_chars=20)[0]
    assert tie.label == "positive"                                                           # the schema's rule: the first label wins a tie
    swapped = sp.ScorerIdentity("UNIT_TEST_STUB_NOT_A_MODEL", "stub-0", SHA, SHA, {"N": "negative", "P": "positive", "U": "neutral"})
    stub = Stub({"N": 0.7, "P": 0.2, "U": 0.1})
    stub.identity = swapped
    o = sp.score_candidates(cs[:1], stub, policy=SCORER_APPLIED, min_chars=20)[0]
    assert o.label == "negative" and o.probabilities == (0.2, 0.7, 0.1)                       # always (positive, negative, neutral)


@pytest.mark.parametrize("bad", [None, [], "positive", {"LABEL_0": 1.0}, {**GOOD, "EXTRA": 0.0}, {**GOOD, "LABEL_2": float("nan")},
                                 {**GOOD, "LABEL_2": float("inf")}, {"LABEL_0": -0.1, "LABEL_1": 0.6, "LABEL_2": 0.5},
                                 {"LABEL_0": 0.5, "LABEL_1": 0.5, "LABEL_2": 0.5}, {"LABEL_0": True, "LABEL_1": 0.0, "LABEL_2": 0.0},
                                 {"LABEL_0": "0.2", "LABEL_1": 0.3, "LABEL_2": 0.5}])
def test_malformed_scorer_output_is_an_explicit_failure_never_neutral_or_zero(bad):
    o = sp.score_candidates(cands(None), Stub(bad), policy=SCORER_APPLIED, min_chars=20)[0]
    assert (o.label, o.probabilities, o.unavailable_reason) == ("unavailable", None, "scorer_failure")


def test_a_crashing_or_misaligned_scorer_fails_every_text_without_a_fallback():
    cs = cands(None, None, None)
    for stub in (Stub(boom=True), Stub(short=True)):
        out = sp.score_candidates(cs, stub, policy=SCORER_APPLIED, min_chars=20)
        assert [(o.label, o.probabilities, o.unavailable_reason) for o in out] == [("unavailable", None, "scorer_failure")] * 3


def test_unscorable_text_never_reaches_the_scorer():
    stub = Stub()
    out = sp.score_candidates(cands("", "short", "x" * 30 + "​" * 3, "A perfectly ordinary long enough headline"), stub, policy=SCORER_APPLIED, min_chars=20)
    assert [o.unavailable_reason for o in out][:2] == ["text_empty", "text_short"]
    assert out[3].label == "neutral" and len(stub.texts) == len([o for o in out if o.unavailable_reason is None])
    assert all(o.probabilities is None for o in out if o.label == "unavailable")


def test_batches_are_respected_order_is_stable_and_arguments_are_checked():
    cs = cands(*["A perfectly ordinary long enough headline %d" % i for i in range(5)])
    stub = Stub()
    out = sp.score_candidates(cs, stub, policy=SCORER_APPLIED, min_chars=20, batch_size=2)
    assert stub.calls == 3 and [o.candidate_id for o in out] == [c.article_id for c in cs]
    assert out == sp.score_candidates(cs, Stub(), policy=SCORER_APPLIED, min_chars=20, batch_size=5)
    for kw in (dict(batch_size=0), dict(min_chars=0)):
        with pytest.raises(sp.ScorerPortError):
            sp.score_candidates(cs, Stub(), policy=SCORER_APPLIED, **{"min_chars": 20, **kw})
    with pytest.raises(sp.ScorerPortError):
        sp.score_candidates([cs[0], cs[0]], Stub(), policy=SCORER_APPLIED, min_chars=20)
    with pytest.raises(sp.ScorerPortError):
        sp.score_candidates(cs, object(), policy=SCORER_APPLIED, min_chars=20)               # type: ignore[arg-type]
    with pytest.raises(PolicyBlockedError):
        sp.score_candidates(cs, Stub(), policy={sp.SCORER_POLICY: APPLIED_APPROVED}, min_chars=20)   # type: ignore[arg-type]


def test_the_port_imports_no_ml_library_and_returns_no_article_record():
    text = (PKG / "scorer_port.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in text.splitlines() if l.startswith(("import ", "from ")))
    assert not any(m in code for m in ("torch", "transformers", "tensorflow", "requests", "urllib", "socket", "httpx", "onnx", "openai"))
    assert "ArticleRecord(" not in text


# ================================================================ polarity-validation infrastructure (synthetic fixtures, not ground truth)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def fixtures(pairs, *, kind=pv.HUMAN_INDEPENDENT, frozen=T0, scored=T0 + timedelta(days=1), model=("m", "r1")):
    labs = [pv.ReferenceLabel(f"A{i}", r, kind, frozen) for i, (r, _) in enumerate(pairs)]
    preds = [pv.Prediction(f"A{i}", p, None if p == "unavailable" else scored, *model) for i, (_, p) in enumerate(pairs)]
    return labs, preds


def run(labs, preds, **kw):
    return pv.validate_polarity(labs, preds, **{"excluded_ids": frozenset(), "min_labelled": 4, **kw})


def test_descriptive_statistics_are_computed_from_independent_labels_and_never_called_validated():
    pairs = [("positive", "positive")] * 6 + [("positive", "negative")] * 2 + [("negative", "negative")] * 5 + [("neutral", "neutral")] * 3 + [("neutral", "positive")]
    ev = run(*fixtures(pairs))
    assert ev.status == "COMPUTED_DESCRIPTIVE" and ev.verdict == pv.VERDICT == "NO_ACCEPTANCE_CRITERIA_APPROVED"
    assert ev.n_labelled == ev.n_scored == 17 and ev.model == ("m", "r1")
    assert ev.confusion == ((6, 2, 0), (0, 5, 0), (1, 0, 3))
    assert ev.accuracy.point == pytest.approx(14 / 17) and ev.accuracy.low < ev.accuracy.point < ev.accuracy.high and ev.accuracy.n == 17
    pos = ev.classes[0]
    assert (pos.support, pos.recall.point, pos.precision.point) == (8, 6 / 8, 6 / 7)
    assert 0.0 < ev.macro_f1 < 1.0


def test_insufficient_evidence_computes_no_metrics():
    ev = run(*fixtures([("positive", "positive")] * 3), min_labelled=4)
    assert ev.status == "INSUFFICIENT_EVIDENCE" and ev.accuracy is None and ev.confusion is None and ev.macro_f1 is None and ev.verdict == pv.VERDICT


def test_unavailable_and_missing_predictions_are_counted_apart_and_never_scored():
    pairs = [("positive", "positive")] * 4 + [("negative", "unavailable")] * 3
    labs, preds = fixtures(pairs)
    ev = run(labs + [pv.ReferenceLabel("X", "neutral", pv.HUMAN_INDEPENDENT, T0)], preds)
    assert (ev.n_labelled, ev.n_scored, ev.n_unavailable, ev.n_unpredicted) == (8, 4, 3, 1) and ev.accuracy.point == 1.0


def test_invalid_evidence_is_rejected():
    labs, preds = fixtures([("positive", "positive")] * 5)
    with pytest.raises(pv.PolarityEvidenceError, match="human-independent"):
        run(*fixtures([("positive", "positive")] * 5, kind="ai_suggestion"))
    with pytest.raises(pv.PolarityEvidenceError, match="overlap"):
        run(labs, preds, excluded_ids=frozenset({"A2"}))
    with pytest.raises(pv.PolarityEvidenceError, match="frozen strictly before"):
        run(*fixtures([("positive", "positive")] * 5, frozen=T0 + timedelta(days=1)))                 # equal times are not "before"
    with pytest.raises(pv.PolarityEvidenceError, match="duplicate reference"):
        run(labs + [labs[0]], preds)
    with pytest.raises(pv.PolarityEvidenceError, match="duplicate prediction"):
        run(labs, preds + [preds[0]])
    mixed = preds[:-1] + [dataclasses.replace(preds[-1], model_revision="r2")]
    with pytest.raises(pv.PolarityEvidenceError, match="model identities"):
        run(labs, mixed)
    with pytest.raises(pv.PolarityEvidenceError, match="malformed"):
        run(labs, preds[:-1] + [dataclasses.replace(preds[-1], label="bullish")])
    with pytest.raises(pv.PolarityEvidenceError, match="not one of"):
        run([dataclasses.replace(labs[0], label="bullish")] + labs[1:], preds)
    with pytest.raises(pv.PolarityEvidenceError, match="scoring time"):
        run(labs, preds[:-1] + [dataclasses.replace(preds[-1], scored_at_utc=None)])
    for bad in (0, True, None):
        with pytest.raises(pv.PolarityEvidenceError, match="min_labelled"):
            run(labs, preds, min_labelled=bad)
    with pytest.raises(pv.PolarityEvidenceError, match="frozenset"):
        run(labs, preds, excluded_ids={"A1"})


def test_the_wilson_interval_matches_known_values_and_is_none_for_no_data():
    w = pv.wilson(8, 10)
    assert w.point == 0.8 and w.low == pytest.approx(0.4902, abs=1e-3) and w.high == pytest.approx(0.9433, abs=1e-3)
    assert pv.wilson(0, 0) is None and pv.wilson(10, 10).high == pytest.approx(1.0) and math.isclose(pv.wilson(0, 10).low, 0.0, abs_tol=1e-12)


def test_the_module_opens_no_file_and_names_no_key_or_label_store():
    text = (PKG / "polarity_validation.py").read_text(encoding="utf-8")
    assert "open(" not in text.split('"""', 2)[2] and "read_text" not in text.split('"""', 2)[2]


# ================================================================ the integrated pipeline

def good(**over):
    """A synthetic row whose recorded title hash is the hash of its title (as in the real day files)."""
    title = over.pop("page_title", "SYNTHETIC headline about nothing real")
    return {"page_title": title, "title_hash": hashlib.sha256(title.encode()).hexdigest(), **over}


def inputs(**over):
    return W.World({W.IN_D2: [good(), good(page_title="SYNTHETIC second headline about nothing", member_rates_us="1")]}).inputs(**over)


def test_the_pipeline_runs_accounting_and_reports_every_other_stage_as_blocked_with_current_reasons():
    r = pl.run_pipeline(inputs())
    assert [s.name for s in r.stages] == ["accounting", "tone_baseline", "tone_derived", "scoring", "conversion", "features", "evaluation"]
    assert r.stage("accounting").status is pl.StageStatus.COMPLETED and r.scores == ()
    assert r.stage("scoring").status is pl.StageStatus.BLOCKED_NO_SCORER and r.stage("conversion").status is pl.StageStatus.BLOCKED_NO_SCORER
    f = r.stage("features")
    assert f.status is pl.StageStatus.BLOCKED_BY_POLICY and sum(1 for x in f.reasons if "=" in x) == 1 and any("E4" in x for x in f.reasons)
    assert r.stage("evaluation").status is pl.StageStatus.BLOCKED_NOT_APPROVED
    assert r.window.interval(W.D2).n_records_by_theme == {"equity_us": 2, "rates_us": 1, "gold": 0} and len(r.digest) == 64


def test_a_scorer_under_the_live_policy_is_blocked_and_never_called():
    stub = Stub()
    r = pl.run_pipeline(inputs(), scorer=stub, scored_at=T0)
    assert r.stage("scoring").status is pl.StageStatus.BLOCKED_BY_POLICY and stub.calls == 0 and r.scores == ()
    assert "scorer_approval_and_polarity_validation" in r.stage("scoring").reasons[0]


def test_with_an_applied_scorer_policy_in_a_test_the_scoring_stage_runs_but_features_stay_blocked():
    stub = Stub()
    r = pl.run_pipeline(inputs(), scorer=stub, policy=SCORER_APPLIED, scored_at=T0)
    assert r.stage("scoring").status is pl.StageStatus.COMPLETED and len(r.scores) == 2 and stub.calls == 1
    assert r.stage("features").status is pl.StageStatus.BLOCKED_BY_POLICY                       # 7 other policies and the conversion contract remain
    assert sum(1 for x in r.stage("features").reasons if "=" in x) == 7
    assert r.stage('conversion').status is pl.StageStatus.COMPLETED and len(r.conversion.records) == 2 and r.conversion.not_converted == ()
    assert pl.CONVERSION_CONTRACT_APPROVED is True and pl.FEATURES_AUTHORISED is False and pl.EVALUATION_APPROVED is False
    with pytest.raises(pl.PipelineError):
        pl.run_pipeline(inputs(), scorer=Stub(), policy=SCORER_APPLIED)                   # scored_at is required: the core path reads no clock


def test_the_pipeline_is_deterministic_and_does_not_change_the_accounting():
    a, b = pl.run_pipeline(inputs()), pl.run_pipeline(inputs())
    assert a == b and a.digest == b.digest == orc.orchestrate_window(inputs()).digest()
