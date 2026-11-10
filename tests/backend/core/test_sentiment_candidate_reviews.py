"""The candidate REVIEW records and the replacement candidates (ADR-054).

The two proposed replacements were reviewed on 2026-11-03 and BOTH are blocked, so the active comparison pair is unchanged. These tests pin the verdicts, the recorded revisions and hashes, the
label vocabularies (Bullish / Bearish for the financial model), and that nothing new can run. Every model output here is a stand-in (TESTED_WITH_MOCKS); no weight was downloaded and no
package installed.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import re
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from wealthpilot.api.dependencies import get_session
from wealthpilot.api.main import app
from wealthpilot.config import get_settings
from wealthpilot.core import sentiment_model as sm
from wealthpilot.core.sentiment import adapter, comparison, normalization, registry, reviews

ROOT = Path(__file__).resolve().parents[3]
FIN, GEN = reviews.FINANCIAL_DISTILBERT_REVIEW, reviews.GENERAL_MULTILINGUAL_REVIEW
TEXT = "My investments are growing but I am worried about my loan EMI"


class NoDb:
    def __getattr__(self, name):                                                                  # pragma: no cover
        raise AssertionError(f"the route used the database session ({name})")


def test_only_horizon_is_approved_and_only_for_research_inference_and_the_other_verdicts_are_unchanged():
    assert [r.key for r in reviews.REVIEWS if r.verdict == reviews.APPROVED] == ["horizon_multilingual_sentiment_small"]
    assert {r.key: r.verdict for r in reviews.REVIEWS} == {
        "finbert": reviews.BLOCKED_LICENCE, "roberta": reviews.BLOCKED_PROVENANCE,
        "tooshlegacy_distilbert_financial_tweet": reviews.BLOCKED_PROVENANCE, "horizon_multilingual_sentiment_small": reviews.APPROVED}
    assert all(r.verdict in reviews.VERDICTS and r.blockers for r in reviews.REVIEWS)                # every candidate still lists what stands in the way (for Horizon: the remaining gates)
    assert [r.key for r in reviews.REVIEWS if r.owner_decision] == ["horizon_multilingual_sentiment_small"]       # no other candidate carries an owner decision
    assert reviews.CHECKED_ON == "2026-11-03" and all(r.checked_on == reviews.CHECKED_ON and r.source_urls for r in reviews.REVIEWS)


def test_recorded_revisions_and_hashes_are_well_formed_and_the_replacements_have_safetensors():
    for r in reviews.REVIEWS:
        assert re.fullmatch(r"[0-9a-f]{40}", r.revision), r.key
        assert (r.safetensors_sha256 is None) == (r.safetensors_size_bytes is None), r.key
        if r.safetensors_sha256:
            assert re.fullmatch(r"[0-9a-f]{64}", r.safetensors_sha256) and r.safetensors_file == "model.safetensors", r.key
    assert (FIN.repository, FIN.revision) == ("tooshlegacy/distilbert-financial-tweet-sentiment", "ba66b6a858cc775dc9e78d773c437b7e984fd5fc")
    assert (GEN.repository, GEN.revision) == ("Horizon-Labs/multilingual-sentiment-small", "e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac")
    assert FIN.safetensors_sha256 == "97fcaa54879f7cfd07af3cdcdb73aaa011dc89ced9b4ca479038148b957c6ac0" and GEN.safetensors_sha256 == "f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1"
    assert reviews.ROBERTA_REVIEW.safetensors_file is None                                             # the original general candidate has no safetensors file


def test_the_findings_that_decide_the_verdicts_are_recorded():
    assert "no LICENSE" in FIN.licence_file.upper().replace("NONE: THE REPOSITORY CONTAINS NO", "no") or "NONE" in FIN.licence_file
    assert any("Twitter API" in d for d in FIN.training_data) and any("ABSENT" in d for d in FIN.training_data)
    assert not any("PhraseBank" in d and "no Financial PhraseBank" not in d for d in FIN.training_data)    # no share-alike corpus is named in its data
    assert any("NO human annotation" in d for d in GEN.training_data) and any("Qwen" in d for d in GEN.training_data) and any("FineWeb" in d for d in GEN.training_data)
    assert "transformers" in " ".join(GEN.blockers) and "A3.3" in " ".join(FIN.blockers)
    assert GEN.base_model_licence.startswith("mit") and FIN.base_model_licence.startswith("apache-2.0")


def test_only_horizon_is_registered_as_a_research_candidate_and_the_other_replacement_is_not_in_the_registry_at_all():
    assert {c.key: c.registration for c in registry.CANDIDATES} == {"horizon": registry.REGISTERED, "finbert": registry.HISTORICAL, "roberta": registry.HISTORICAL}          # R1, ADR-056
    assert [c.key for c in registry.CANDIDATES if c.registered] == ["horizon"] and [c.key for c in registry.CANDIDATES if c.runnable_in_principle] == ["horizon"]
    assert "tooshlegacy/distilbert-financial-tweet-sentiment" not in {c.repository for c in registry.CANDIDATES}                  # the blocked financial replacement was never registered
    assert {r.key for r in reviews.REVIEWS if r.active_in_registry} == {"horizon_multilingual_sentiment_small"}                  # registered candidates only: Horizon
    assert not FIN.active_in_registry and GEN.active_in_registry
    assert registry.HORIZON.repository == GEN.repository and registry.HORIZON.revision == GEN.revision                           # the registry constant and the review describe the same artifact


def test_a_candidate_built_from_a_review_with_no_registration_still_cannot_load_or_run(tmp_path):
    for review in (FIN, GEN):
        cand = registry.Candidate(key=review.key, role=review.role, display_name=review.key, repository=review.repository, revision=review.revision, weight_licence=review.declared_licence,
                                  licence_status=registry.LICENCE_UNVERIFIED, licence_note="not approved", format_status=registry.FORMAT_SAFETENSORS, format_note="",
                                  registration=registry.PENDING, registration_note="not registered", source_urls=())
        config = adapter.ResearchConfig(enabled=True, max_tokens=128, timeout_seconds=2.0, device="cpu")
        result = adapter.classify_with(cand, config, TEXT, root=tmp_path)
        assert (result.available, result.unavailable_reason) == (False, "licence_not_verified")


# ------------------------------------------------------------------------------------------------------------------------ label vocabularies
def test_the_financial_models_bullish_bearish_labels_map_to_positive_negative_and_keep_their_spelling():
    assert [normalization.normalise_native_label(v) for v in ("Bearish", "Bullish", "Neutral", "BULLISH")] == ["negative", "positive", "neutral", "positive"]
    order = normalization.label_order_from_id2label({"0": "Bearish", "1": "Bullish", "2": "Neutral"})
    assert order == ("Bearish", "Bullish", "Neutral")                                                  # native spelling preserved, in index order
    assert normalization.label_order_from_id2label({"0": "negative", "1": "neutral", "2": "positive"}) == ("negative", "neutral", "positive")
    for review in reviews.REVIEWS:
        assert [normalization.normalise_native_label(n) for n, _ in review.label_mapping] == [m for _, m in review.label_mapping], review.key
        assert tuple(n for n, _ in review.label_mapping) == review.native_labels


def test_ambiguous_or_unsupported_label_sets_are_refused_not_guessed():
    for bad in ({"0": "bullish", "1": "positive", "2": "neutral"}, {"0": "bearish", "1": "negative", "2": "neutral"}, {"0": "Bearish", "1": "Bullish", "2": "Sideways"},
                {"0": "LABEL_0", "1": "LABEL_1", "2": "LABEL_2"}, {"0": "uncertain", "1": "mixed", "2": "neutral"}):
        assert normalization.label_order_from_id2label(bad) is None
    assert all(normalization.normalise_native_label(v) is None for v in ("sideways", "mixed", "uncertain", "", None))


def mock_result(model_key, labels, logits):
    return normalization.result_from_logits(model_key, "repo", "rev", labels, logits, 1.0)


def test_mocked_logits_give_native_and_normalized_labels_and_the_comparison_works_across_vocabularies():
    fin = mock_result("financial", ("Bearish", "Bullish", "Neutral"), [0.1, 4.0, 0.2])
    gen = mock_result("general", ("negative", "neutral", "positive"), [0.1, 0.2, 3.0])
    assert (fin.native_label, fin.normalized_label, gen.native_label, gen.normalized_label) == ("Bullish", "positive", "positive", "positive")
    agree = comparison.compare_models(fin, gen)
    assert (agree.status, agree.shared_label) == ("agreement", "positive") and "not a human-validated finding" in agree.explanation
    split = comparison.compare_models(fin, mock_result("general", ("negative", "neutral", "positive"), [3.0, 0.2, 0.1]))
    assert split.status == "disagreement" and split.shared_label is None
    overall = comparison.decide_overall(split, "mixed", "valid")
    assert (overall.sentiment, overall.uncertainty_reason) == ("uncertain", "models_disagree")        # never silently picks the financial or the general model
    assert fin.raw_scores == (("Bearish", 0.1), ("Bullish", 4.0), ("Neutral", 0.2))                    # raw scores keep the native labels
    assert all(r.normalized_label in ("positive", "negative", "neutral") for r in (fin, gen))          # a model never emits `uncertain` itself


def test_both_models_can_agree_while_the_rules_baseline_disagrees_and_all_three_readings_survive():
    fin = mock_result("financial", ("Bearish", "Bullish", "Neutral"), [4.0, 0.1, 0.2])
    gen = mock_result("general", ("negative", "neutral", "positive"), [3.0, 0.2, 0.1])
    agree = comparison.compare_models(fin, gen)
    out = comparison.decide_overall(agree, "positive", "valid")
    assert (agree.shared_label, out.sentiment, out.rules_relation, out.uncertainty_reason) == ("negative", "uncertain", "disagrees", "rules_disagree")


# ------------------------------------------------------------------------------------------------------------------------ status endpoint
@pytest.fixture()
def client():
    app.dependency_overrides[get_session] = lambda: NoDb()
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


def test_the_status_endpoint_lists_every_reviewed_candidate_with_its_verdict_and_no_path(client):
    body = client.get("/api/sentiment-model/status").json()
    listed = {c["key"]: c for c in body["reviewed_candidates"]}
    assert set(listed) == {r.key for r in reviews.REVIEWS}
    assert listed["tooshlegacy_distilbert_financial_tweet"]["verdict"] == "blocked_by_provenance" and listed["horizon_multilingual_sentiment_small"]["verdict"] == "approved_for_research_inference"
    assert listed["horizon_multilingual_sentiment_small"]["owner_decision"] == reviews.HORIZON_OWNER_DECISION_CURRENT and listed["horizon_multilingual_sentiment_small"]["owner_decision"].startswith(reviews.HORIZON_OWNER_DECISION)
    assert listed["finbert"]["owner_decision"] is None
    assert listed["tooshlegacy_distilbert_financial_tweet"]["label_mapping"] == {"Bearish": "negative", "Bullish": "positive", "Neutral": "neutral"}
    assert listed["horizon_multilingual_sentiment_small"]["safetensors_sha256"] == GEN.safetensors_sha256 and listed["horizon_multilingual_sentiment_small"]["role"] == "general"
    assert [k for k, c in listed.items() if c["verdict"] == "approved_for_research_inference"] == ["horizon_multilingual_sentiment_small"] and all(c["blockers"] for c in listed.values())
    assert {k for k, c in listed.items() if c["active_in_registry"]} == {"horizon_multilingual_sentiment_small"}                       # registered by the owner's R1 decision, research only
    assert body["production_method"] == "user_text_rules_v1" and body["production_activation"] == "not_activated" and body["transformers_enabled"] is False
    raw = client.get("/api/sentiment-model/status").text
    assert "C:\\\\" not in raw and "Administrator" not in raw and "sentiment_pretrained" not in raw


# ------------------------------------------------------------------------------------------------------------------------ state of this phase
def test_no_weights_are_in_the_repository_and_production_is_unchanged_whatever_packages_this_machine_has():
    assert "models/sentiment_pretrained/" in (ROOT / ".gitignore").read_text(encoding="utf-8")        # R2: placed weights can never be tracked by accident
    assert get_settings().sentiment_transformers_enabled is False and get_settings().sentiment_model_enabled is False
    # `dependencies_available()` only says whether the packages import: the owner-authorised B2.1 installation made it True in the project environment (it was False in earlier phases). It must
    # never be what switches anything on, so with the packages present every candidate is still unavailable and production is unchanged.
    from wealthpilot.api.services import personalized_insight_service as service
    status = service.sentiment_model_status()
    assert status.enabled is False and status.state == "disabled" and status.method_when_used == "rules_baseline" and status.transformers_enabled is False
    assert status.production_method == "user_text_rules_v1" and status.production_activation == "not_activated" and [c.key for c in registry.CANDIDATES if c.runnable_in_principle] == ["horizon"]


def test_the_original_findings_are_still_in_the_decision_record_and_the_replacement_has_its_own_entry():
    decisions = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    assert "## ADR-053" in decisions and "## ADR-054" in decisions
    assert decisions.index("## ADR-053") < decisions.index("## ADR-054")
    assert "blocked_by_licence" in (ROOT / "backend" / "wealthpilot" / "core" / "sentiment" / "registry.py").read_text(encoding="utf-8")        # the historical registry entry is preserved


# ------------------------------------------------------------------------------------------------------------------------ the owner's scoped decision (2026-11-04)
def test_the_owner_decision_names_the_exact_revision_scope_and_what_is_not_authorised():
    decision = GEN.owner_decision or ""
    assert reviews.OWNER_DECISION_DATE == "2026-11-04" and GEN.revision in decision and "RESEARCH INFERENCE ONLY" in decision
    assert "web-crawl and LLM-generated training data" in decision and "absence of human-validated labels" in decision
    for not_authorised in ("production activation", "dataset creation", "fine-tuning", "automatic model downloads", "redistribution", "commercial use", "financial-decision impact", "accuracy or calibration claim"):
        assert not_authorised in decision, not_authorised
    assert "each still need their own approval" in decision                                           # install, download, inference and the registry change are separate approvals


def test_the_financial_slot_is_empty_no_financial_candidate_is_approved_and_the_tooshlegacy_model_stays_blocked():
    assert [r.key for r in reviews.REVIEWS if r.role == "financial" and r.verdict == reviews.APPROVED] == []
    assert FIN.verdict == reviews.BLOCKED_PROVENANCE and FIN.owner_decision is None and not FIN.active_in_registry
    assert [r.key for r in reviews.REVIEWS if r.role == "general" and r.verdict == reviews.APPROVED] == ["horizon_multilingual_sentiment_small"]
    assert [c.key for c in registry.CANDIDATES if c.runnable_in_principle] == ["horizon"]               # only the owner-registered general research candidate is runnable in principle; the financial slot has none


def test_the_remaining_gates_for_horizon_are_recorded_including_the_transformers_incompatibility():
    text = " ".join(GEN.blockers)
    for needed in ("4.57.1 is NOT compatible", "rope_parameters", "5.17.0", "NOT production", "F1/R14", "smoke test"):
        assert needed in text, needed
    assert GEN.native_labels == ("negative", "neutral", "positive")                                  # native labels retained
    assert [n for n, _ in GEN.label_mapping] == ["negative", "neutral", "positive"]


def test_approval_of_the_review_does_not_make_horizon_loadable_or_change_production(tmp_path):
    from wealthpilot.api.services import personalized_insight_service as service
    config = adapter.ResearchConfig(enabled=True, max_tokens=512, timeout_seconds=5.0, device="cpu")
    for cand in registry.CANDIDATES:
        assert adapter.classify_with(cand, config, TEXT, root=tmp_path).available is False
    status = service.sentiment_model_status()
    assert status.production_method == "user_text_rules_v1" and status.production_activation == "not_activated" and status.transformers_enabled is False
    assert get_settings().sentiment_transformers_enabled is False and get_settings().sentiment_model_enabled is False
    example = [l.strip() for l in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines() if l.startswith("SENTIMENT_TRANSFORMERS_ENABLED")]
    assert example == ["SENTIMENT_TRANSFORMERS_ENABLED=false"]


def test_the_governance_documents_record_the_scoped_decision_without_resolving_other_gates():
    decisions = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    addendum = decisions[decisions.index("Addendum to ADR-054"):]
    assert "RESEARCH INFERENCE ONLY" in addendum and "A3.3" in addendum and "D20" in addendum and "F1" in addendum
    form = (ROOT / "reports" / "sentiment_consolidated_approval_form.md").read_text(encoding="utf-8")
    assert "| A3.3 |" in form and "| D20 |" in form                                                      # the consolidated form is untouched; its statuses are asserted by test_consolidated_approval_form
