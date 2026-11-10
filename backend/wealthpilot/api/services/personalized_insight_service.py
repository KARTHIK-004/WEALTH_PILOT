"""Personalised insight orchestration (Research Enhancement Track, ADR-043): reads the customer's own monthly features and stored risk assessment, reads the optional text the
caller sends, and composes a display-only insight with `core/`. The route layer is thin; the rules live in `core/behaviour_findings.py`, `core/user_text_sentiment.py` and
`core/personalized_insight.py`.

Privacy and scope (docs/SECURITY.md): the text is analysed in memory and is never stored, logged, sent to a ledger, an LLM or any external service; this module has no logger.
Everything is scoped by `customer_id` (ADR-024: data scoping, not authorisation). Nothing here writes to the database, and nothing in the analysis, recommendation, compliance
or risk path reads this module's output.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from wealthpilot.api.errors import InvalidRequestError
from wealthpilot.api.schemas import (
    BehaviourFindingOut,
    BehaviourFindingsOut,
    EvidenceOut,
    InsightConflictOut,
    InsightStatementOut,
    PersonalizedInsightResponse,
    RiskProfileOut,
    RulesBaselineOut,
    SentimentModelStatusOut,
    CandidateReviewOut,
    StatedPreferenceOut,
    ModelVsRulesOut,
    ResearchComparisonOut,
    ResearchModelResultOut,
    ResearchSlotStatusOut,
    TransformerCandidateStatusOut,
    TransformerResearchOut,
    UserSentimentOut,
)
from wealthpilot.api.services import monthly_records_service
from wealthpilot.core.behaviour_findings import derive_findings
from wealthpilot.core.personalized_insight import COMPOSER_VERSION, PersonalizedInsight, RiskProfileView, compose_insight
from wealthpilot.config import get_settings
from wealthpilot.core import sentiment_model as trained
from wealthpilot.core.sentiment import adapter as research_adapter
from wealthpilot.core.sentiment import inference_service as research_inference
from wealthpilot.core.sentiment import registry as research_registry
from wealthpilot.core.sentiment.normalization import ModelResult, unavailable
from wealthpilot.core.sentiment.reviews import REVIEWS
from wealthpilot.core.sentiment.comparison import compare_slots, decide_overall
from wealthpilot.core.user_text_sentiment import METHOD_VERSION, SentimentModel, UserTextAnalysis, UserTextError, analyse_user_text
from wealthpilot.db.models import AnalysisRun, RiskAssessment

DATA_SOURCE = "monthly_financial_records+risk_assessments+user_text"
CONFIRMATION_NOTE = ("Confirming a preference is not available yet: confirmed preferences are not stored (storing them needs a reviewed schema change). "
                     "Until then an inferred preference is a suggestion only, and your risk assessment and questionnaire answers stay in force.")


SOURCE_STORED_ASSESSMENT = "stored risk assessment of the latest analysis"


def _config() -> tuple[trained.SentimentModelConfig, bool]:
    """The model settings, parsed. Returns (config, valid): an unparsable number makes the configuration invalid (reason `invalid_configuration`), never a guessed value."""
    settings = get_settings()

    def number(raw: str, kind: type, default):  # noqa: ANN001, ANN202
        if not raw.strip():
            return default, True
        try:
            value = kind(raw.strip())
        except ValueError:
            return default, False
        return value, True

    min_confidence, ok1 = number(settings.sentiment_model_min_confidence, float, None)
    max_tokens, ok2 = number(settings.sentiment_model_max_tokens, int, None)
    timeout, ok3 = number(settings.sentiment_model_timeout_seconds, float, 5.0)
    config = trained.SentimentModelConfig(
        enabled=settings.sentiment_model_enabled, name=settings.sentiment_model_name, path=settings.sentiment_model_path, version=settings.sentiment_model_version,
        min_confidence=min_confidence, allow_fallback=settings.sentiment_model_allow_fallback, max_tokens=max_tokens, device=settings.sentiment_model_device, timeout_seconds=timeout)
    return config, ok1 and ok2 and ok3 and (min_confidence is None or 0.0 < min_confidence <= 1.0)


RESEARCH_NOTICES = (
    "Experimental pretrained model output \u2014 not human validated.",
    "Model predictions are not financial advice.",
    "Sentiment does not modify your financial risk profile or investment recommendations.",
)
SLOT_LABEL = {"financial": "Financial sentiment model", "general": "General sentiment model"}


def _research_config() -> research_adapter.ResearchConfig:
    """The research settings, parsed. An enabled switch with a missing or unparsable limit is an INVALID configuration (the models then report `invalid_configuration`), never a guessed number.
    The thread cap is optional: blank leaves torch's own default untouched; anything unparsable is invalid."""
    settings = get_settings()

    def number(raw: str, kind: type):  # noqa: ANN001, ANN202
        try:
            return kind(raw.strip()) if raw.strip() else None
        except ValueError:
            return None

    threads = None if not settings.sentiment_transformers_threads.strip() else (number(settings.sentiment_transformers_threads, int) or 0)
    return research_adapter.ResearchConfig(enabled=settings.sentiment_transformers_enabled, max_tokens=number(settings.sentiment_transformers_max_tokens, int),
                                           timeout_seconds=number(settings.sentiment_transformers_timeout_seconds, float) or 0.0, device=settings.sentiment_transformers_device, threads=threads)


def _model_out(result: ModelResult) -> ResearchModelResultOut:
    reason = result.unavailable_reason
    return ResearchModelResultOut(
        slot=result.role, display_name=SLOT_LABEL[result.role], model_id=result.repository or None, revision=result.revision or None,  # type: ignore[arg-type]
        availability="available" if result.available else ("loading" if reason == "loading" else "unavailable"), unavailable_reason=reason,  # type: ignore[arg-type]
        native_label=result.native_label, normalized_label=result.normalized_label,  # type: ignore[arg-type]
        raw_scores=None if result.raw_scores is None else {k: round(v, 4) for k, v in result.raw_scores},
        probabilities=None if result.probabilities is None else {k: round(v, 4) for k, v in result.probabilities},
        probability_kind="raw_softmax_uncalibrated" if result.probabilities is not None else None, processing_ms=result.processing_ms)


def _failed_outcome(rules_label: str | None, interpretation_state: str | None) -> research_inference.ResearchOutcome:
    """What the research path reports if it raised something nothing anticipated: every slot `internal_error`, the rules reading stands. The exception is discarded (it could carry the text)."""
    results = tuple(unavailable("", "", "", "internal_error", role=role) for role in research_registry.ROLES)
    comparison = compare_slots(results)
    return research_inference.ResearchOutcome(results, comparison, decide_overall(comparison, rules_label, interpretation_state, eligible=True), (), False, False, 0.0)


def build_transformer_research(text: str | None, analysis: UserTextAnalysis, *, config: research_adapter.ResearchConfig | None = None,
                               backend_factory: research_adapter.BackendFactory | None = None, root=None, slots=None) -> TransformerResearchOut:  # noqa: ANN001
    """The research-only panel for one already-analysed text. NEVER raises: any failure of the research path becomes `internal_error` slots and the rules reading stands. Holds no text."""
    cfg = config or _research_config()
    rules_label = analysis.rules_label if analysis.rules_label is not None else analysis.sentiment
    kwargs: dict = {} if root is None else {"root": root}
    try:
        outcome = research_inference.run_research(text, rules_label=rules_label, interpretation_state=analysis.interpretation_state, config=cfg, backend_factory=backend_factory, slots=slots, **kwargs)
    except Exception:  # noqa: BLE001 -- the production endpoint must never fail because of the research path
        outcome = _failed_outcome(rules_label, analysis.interpretation_state)
    models = [_model_out(r) for r in outcome.results]
    comparison = ResearchComparisonOut(
        status=outcome.comparison.status, shared_label=outcome.comparison.shared_label, explanation=outcome.comparison.explanation,  # type: ignore[arg-type]
        model_vs_rules=[ModelVsRulesOut(slot=m.role, rules_label=m.rules_label, model_label=m.model_label, relation=m.relation, explanation=m.explanation) for m in outcome.model_vs_rules])  # type: ignore[arg-type]
    slot_map = slots if slots is not None else research_inference.current_slots()
    return TransformerResearchOut(
        enabled=cfg.enabled, mode="research_experimental", validation_status="not_human_validated", production_effect="none",
        rules_baseline=None if rules_label is None else RulesBaselineOut(label=rules_label, method="rules_baseline", model_version=METHOD_VERSION),  # type: ignore[arg-type]
        models=models, comparison=comparison, overall_sentiment=outcome.overall.sentiment, overall_source=outcome.overall.source, rules_relation=outcome.overall.rules_relation,  # type: ignore[arg-type]
        uncertainty_reason=outcome.overall.uncertainty_reason,  # type: ignore[arg-type]
        model_versions={role: cand.revision for role, (cand, _reason) in slot_map.items() if cand is not None},
        model_availability={m.slot: m.availability for m in models},
        processing_metadata={"total_ms": outcome.total_ms if outcome.ran else None, "input_eligible": outcome.eligible, "device": cfg.device}, notices=list(RESEARCH_NOTICES))


def candidate_reviews() -> list[CandidateReviewOut]:
    return [CandidateReviewOut(
        key=r.key, role=r.role, repository=r.repository, revision=r.revision, architecture=r.architecture, declared_licence=r.declared_licence, licence_file=r.licence_file,  # type: ignore[arg-type]
        base_model=r.base_model, base_model_licence=r.base_model_licence, training_data=list(r.training_data), native_labels=list(r.native_labels), label_mapping=dict(r.label_mapping),
        languages=r.languages, safetensors_file=r.safetensors_file, safetensors_sha256=r.safetensors_sha256, safetensors_size_bytes=r.safetensors_size_bytes, verdict=r.verdict,  # type: ignore[arg-type]
        blockers=list(r.blockers), active_in_registry=r.active_in_registry, source_urls=list(r.source_urls), checked_on=r.checked_on, owner_decision=r.owner_decision) for r in REVIEWS]


def research_candidate_statuses() -> list[TransformerCandidateStatusOut]:
    """Per known candidate. Reads only the cache, the locks, the failure memory and whether the weight file exists: it NEVER loads, hashes or verifies a model."""
    cfg = _research_config()
    out = []
    for c in research_registry.CANDIDATES:
        s = research_adapter.candidate_status(c, cfg)
        out.append(TransformerCandidateStatusOut(
            model_key=c.key, role=c.role, display_name=c.display_name, repository=c.repository, revision=c.revision, weight_licence=c.weight_licence,  # type: ignore[arg-type]
            licence_status=c.licence_status, format_status=c.format_status, registration=c.registration, blocker=c.blocker, weights_present=s.weights_present, loaded=s.loaded,  # type: ignore[arg-type]
            inference_enabled=cfg.enabled and c.runnable_in_principle, availability=s.availability, reason=s.reason, checked_on=research_registry.CHECKED_ON))  # type: ignore[arg-type]
    return out


def research_slot_statuses() -> list[ResearchSlotStatusOut]:
    out = []
    for role in research_registry.ROLES:
        candidate, reason = research_registry.slot_state(role)
        out.append(ResearchSlotStatusOut(role=role, state="registered" if candidate is not None else reason, candidate_key=None if candidate is None else candidate.key))  # type: ignore[arg-type]
    return out


def _resolve_model() -> tuple[SentimentModel | None, str | None]:
    """(model, None) when a validated model is usable; (None, reason) when one is switched on but cannot be used; (None, None) when it is switched off (the rules baseline is then
    simply the method, not a fallback)."""
    config, valid = _config()
    if not config.enabled:
        return None, None
    if not valid:
        return None, "invalid_configuration"
    try:
        return trained.load_model(config), None
    except trained.ModelUnavailable as exc:
        return None, exc.reason


def get_sentiment_model() -> SentimentModel | None:
    """The validated trained sentiment model, or None. NONE EXISTS in this repository (ADR-052): the feature is off and every reading comes from the rules baseline. A test replaces
    this function (and `sentiment_unavailable_reason`) to exercise the model, fallback and abstention paths with a fake backend."""
    return _resolve_model()[0]


def sentiment_unavailable_reason() -> str | None:
    """Why a SWITCHED-ON model cannot be used (a fixed code), or None (switched off, or usable)."""
    return _resolve_model()[1]


def sentiment_model_status() -> SentimentModelStatusOut:
    config, valid = _config()
    status = trained.model_status(config) if valid else trained.ModelStatus(config.enabled, "unavailable" if config.enabled else "disabled", "invalid_configuration" if config.enabled else None,
                                                                             None, None, None, None, False, config.allow_fallback, trained.dependencies_available())
    return SentimentModelStatusOut(
        enabled=status.enabled, state=status.state, reason=status.reason, method_when_used="hybrid" if status.state == "ready" else "rules_baseline",  # type: ignore[arg-type]
        model_name=status.model_name, model_version=status.model_version, validation_status=status.validation_status, calibration_status=status.calibration_status,  # type: ignore[arg-type]
        intensity_available=status.intensity_available, fallback_enabled=status.fallback_enabled,
        dependencies_available=status.dependencies_available, data_source="models/sentiment",
        research_models=research_candidate_statuses(), reviewed_candidates=candidate_reviews(), research_slots=research_slot_statuses(), transformers_enabled=get_settings().sentiment_transformers_enabled)


def _risk_profile(session: Session, customer_id: int) -> RiskProfileView | None:
    """The customer's STORED risk assessment, never the text's. A `risk_assessments` row is used when one exists. The analysis pipeline does not write that table (its
    `risk_score` column is NOT NULL and no ordinal score exists, so persistence is skipped rather than fabricated: `analysis_service._persist_risk_assessment`), so the
    stored assessment is otherwise the risk result kept in the customer's latest analysis run. Without either, nothing is assumed: the caller gets None."""
    row = session.scalars(
        select(RiskAssessment).where(RiskAssessment.customer_id == customer_id).order_by(RiskAssessment.created_at.desc(), RiskAssessment.id.desc()).limit(1)
    ).first()
    if row is not None:
        return RiskProfileView(row.risk_category, SOURCE_STORED_ASSESSMENT, None if row.created_at is None else row.created_at.isoformat())
    run = session.scalars(
        select(AnalysisRun).where(AnalysisRun.customer_id == customer_id, AnalysisRun.result.is_not(None)).order_by(AnalysisRun.id.desc()).limit(1)
    ).first()
    category = ((run.result or {}).get("risk") or {}).get("risk_category") if run is not None else None
    if not isinstance(category, str) or not category:
        return None  # the latest analysis produced no risk result (for example it is waiting for information)
    stamp = run.completed_at or run.created_at
    return RiskProfileView(category, SOURCE_STORED_ASSESSMENT, None if stamp is None else stamp.isoformat())


def _sentiment_out(a: UserTextAnalysis) -> UserSentimentOut:
    return UserSentimentOut(
        status=a.status, unavailable_reason=a.unavailable_reason, sentiment=a.sentiment, emotional_tone=a.emotional_tone,  # type: ignore[arg-type]
        financial_relevance=a.financial_relevance,  # type: ignore[arg-type]
        topics=list(a.topics),  # type: ignore[arg-type]
        preferences=[StatedPreferenceOut(code=p.code, status=p.status, requires_confirmation=p.requires_confirmation,  # type: ignore[arg-type]
                                         evidence=EvidenceOut(label=p.evidence.label, phrase=p.evidence.phrase)) for p in a.preferences],
        evidence=[EvidenceOut(label=e.label, phrase=e.phrase) for e in a.evidence], confidence=None if a.confidence is None else round(a.confidence, 4),
        confidence_band=a.confidence_band,  # type: ignore[arg-type]
        requires_confirmation=a.requires_confirmation, abstained=a.abstained, abstain_reason=a.abstain_reason,  # type: ignore[arg-type]
        interpretation_state=a.interpretation_state, fallback_used=a.fallback_used, fallback_reason=a.fallback_reason, method=a.method, model_name=a.model_name,  # type: ignore[arg-type]
        model_version=a.model_version, validation_status=a.validation_status, class_probabilities=None if a.class_probabilities is None else {k: round(v, 4) for k, v in a.class_probabilities.items()},
        confidence_calibration_status=a.confidence_calibration_status,  # type: ignore[arg-type]
        sentiment_intensity=None if a.sentiment_intensity is None else round(a.sentiment_intensity, 4),
        intensity_available=a.sentiment_intensity is not None,
        rules_baseline=None if a.rules_label is None else RulesBaselineOut(label=a.rules_label, method="rules_baseline", model_version=METHOD_VERSION),  # type: ignore[arg-type]
        disagreement=a.disagreement, privacy_status=a.privacy_status, limitations=list(a.limitations))  # type: ignore[arg-type]


def _response(customer_id: int, findings, text: UserTextAnalysis, risk: RiskProfileView | None, insight: PersonalizedInsight) -> PersonalizedInsightResponse:   # noqa: ANN001
    assessed = None if risk is None or risk.assessed_at is None else datetime.fromisoformat(risk.assessed_at)
    return PersonalizedInsightResponse(
        customer_id=customer_id, analysis_timestamp=datetime.now(timezone.utc), status=insight.status,  # type: ignore[arg-type]
        model_version=f"{COMPOSER_VERSION}|{findings.version}|{text.model_version}", data_source=DATA_SOURCE,
        behaviour=BehaviourFindingsOut(
            version=findings.version, history=findings.history, observation_count=findings.observation_count, latest_period=findings.latest_period,  # type: ignore[arg-type]
            findings=[BehaviourFindingOut(code=f.code, category=f.category, status=f.status, statement=f.statement, sources=list(f.sources),  # type: ignore[arg-type]
                                          direction=f.direction, values=dict(f.values)) for f in findings.findings],  # type: ignore[arg-type]
            data_quality_notes=list(findings.data_quality_notes)),
        user_sentiment=_sentiment_out(text),
        risk_profile=None if risk is None else RiskProfileOut(category=risk.category, source=risk.source, assessed_at=assessed, remains_authoritative=True),
        preference_confirmation=CONFIRMATION_NOTE,
        statements=[InsightStatementOut(text=s.text, sources=list(s.sources), kind=s.kind) for s in insight.statements],  # type: ignore[arg-type]
        conflicts=[InsightConflictOut(code=c.code, detail=c.detail, inferred_preference=c.inferred_preference, stored_category=c.stored_category,  # type: ignore[arg-type]
                                      authoritative_source=c.authoritative_source, preference_status=c.preference_status, action=c.action) for c in insight.conflicts],
        caveats=list(insight.caveats), purpose=insight.purpose)


def build_insight_from_features(customer_id: int, features, text: str | None, risk_loader: Callable[[], RiskProfileView | None]) -> PersonalizedInsightResponse:   # noqa: ANN001
    """The display-only insight for ALREADY COMPUTED behaviour features: the rules-baseline reading of the optional text, the findings and the composition. The stored risk assessment is
    fetched only AFTER the text has been accepted (`risk_loader`), so a rejected text never causes a read. Shared by the customer route and the fictional demo route."""
    try:
        model = get_sentiment_model()
        analysis = analyse_user_text(text, model, model_unavailable_reason=None if model is not None else sentiment_unavailable_reason(), allow_fallback=_config()[0].allow_fallback)
    except UserTextError as exc:
        raise InvalidRequestError(f"The text cannot be analysed: {exc}.") from None   # from None: the message never carries the text
    findings = derive_findings(features)
    risk = risk_loader()
    response = _response(customer_id, findings, analysis, risk, compose_insight(findings, analysis, risk))
    response.transformer_research = build_transformer_research(text, analysis)          # research-only and display-only: composed AFTER, and never read by, the insight above
    return response


def build_insight(session: Session, customer_id: int, text: str | None) -> PersonalizedInsightResponse:
    """The display-only insight for this customer. Raises `CustomerNotFoundError` for an unknown customer and `InvalidRequestError` (without echoing the text) for unusable text."""
    features = monthly_records_service.core_features(session, customer_id)   # also verifies the customer exists
    return build_insight_from_features(customer_id, features, text, lambda: _risk_profile(session, customer_id))
