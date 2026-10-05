"""Phase 10 — individual agent nodes.

Each node is a pure function `(AgentState, ...explicit deps) ->
AgentStateDelta` (BUILD_PLAN.md section 9). No node mutates `state`; no
node trains, retrains, or modifies any Phase 4-9 model/artifact/methodology;
no node calls an LLM (Gemini/OpenAI/Claude/anything); no node implements
AutoGen debate or LangGraph routing. This file wires already-approved
Phase 4-9 components together — it invents no new financial or ML logic.

**No feature-engineering entrypoint exists yet for a single live customer**
in Phase 3's `engineer_features()` (it is a batch/population function, per
its own docstring: "kept for potential inference-time feature building").
This file closes that specific, narrow gap the ONLY way that doesn't risk a
subtle correctness bug: by calling `engineer_features()`/`build_monthly_panel()`
completely unmodified, on the SAME raw FAR-Trans tables Phase 3/5 always
used, filtered down to one customer's rows before the call (every feature
in both functions is a `groupby("customerID")` aggregation, so filtering
inputs to one customer first is provably identical to filtering the full
population's output afterward — never a shortcut or approximation).
`Customer.risk_inputs["external_customer_id"]` (set at ingestion,
`data/ingestion.py::ingest_customers`) is required to map a DB `customer_id`
back to the raw FAR-Trans `customerID` these tables are keyed by.

**Node dependency order** (BUILD_PLAN.md section 9's flow diagram, the
deterministic subset only — Information Request/Re-profile are alternate
branches, not sequence positions; AutoGen/Gemini/LangGraph routing are
Phases 11-13, not built here):

    customer_analyzer_node
          |
    risk_analyst_node -------------------- (low confidence) --> information_request_node
          |
    financial_health_node ---------------- (significant drift) --> reprofile_node -> risk_analyst_node
          |
    goal_analyst_node
          |
    market_analyst_node
          |
    portfolio_manager_node --------------- (EF insufficient) --> savings_first_node
          |
    compliance_analyst_node

Phase 10 builds every node above as an independently callable function.
WHICH branch actually runs for a given state (the "low confidence", "EF
insufficient", "significant drift" decisions) is Phase 11's conditional-edge
routing logic, not decided here — see each node's docstring for exactly
what it does and does not decide.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from wealthpilot.agents.state import (
    AgentState,
    AgentStateDelta,
    CustomerProfile,
    EmergencyFundResult,
    FinancialHealthResult,
    GoalAnalysisResult,
    GoalSummary,
    InstrumentRegime,
    MarketAnalysisResult,
    NodeError,
    PortfolioResult,
    RiskAssessmentResult,
)
from wealthpilot.core.compliance import ComplianceProposal, evaluate_compliance
from wealthpilot.core.goals import (
    GoalAssumptions,
    GoalInput,
    analyze_goal_funding,
    assess_emergency_fund,
    classify_feasibility,
    run_goal_monte_carlo,
    savings_first_required,
)
from wealthpilot.core.optimizer import (
    ASSET_UNIVERSE,
    GENERAL_SINGLE_ASSET_CAP,
    RISK_FREE_RATE,
    RISK_LEVEL_QQQ_BANDS,
    covariance_ledoit_wolf,
    effective_bounds,
    equal_weight_portfolio,
    expected_returns_historical,
    hrp_weights,
    mvo_max_sharpe,
    portfolio_return,
    portfolio_volatility,
    sharpe_ratio,
)
from wealthpilot.data.preprocessing import ALL_FEATURES, GENUINE_RISK_LEVELS, engineer_features, load_far_trans_tables

REPO_ROOT = Path(__file__).resolve().parents[3]
RISK_MODELS_DIR = REPO_ROOT / "models" / "risk"
BEHAVIOUR_MODELS_DIR = REPO_ROOT / "models" / "behaviour"
METRICS_PATH = REPO_ROOT / "models" / "metrics.json"

RISK_MODEL_VERSION = "v1"
BEHAVIOUR_MODEL_VERSION = "v1"
PORTFOLIO_CONFIG_VERSION = "v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Customer Analyzer
# ---------------------------------------------------------------------------


def customer_analyzer_node(state: AgentState, session: Session) -> AgentStateDelta:
    """Loads and normalizes the customer profile into state (BUILD_PLAN.md
    section 8's Customer Analyzer row): reads `customers` and
    `financial_goals` rows only — no feature engineering, no model call."""
    from wealthpilot.db.models import Customer

    customer = session.get(Customer, state.customer_id)
    if customer is None:
        return AgentStateDelta(
            new_errors=[
                NodeError(
                    node_name="customer_analyzer",
                    error_type="missing_data",
                    message=f"customer_id {state.customer_id} not found",
                )
            ]
        )

    goals = [
        GoalSummary(
            id=g.id,
            goal_type=g.goal_type,
            target_amount=float(g.target_amount),
            current_savings=float(g.current_savings),
            target_date=g.target_date,
            priority=g.priority,
        )
        for g in customer.financial_goals
    ]
    profile = CustomerProfile(
        customer_id=customer.id,
        name=customer.name,
        age=customer.age,
        income=float(customer.income) if customer.income is not None else None,
        employment_status=customer.employment_status,
        customer_type=customer.customer_type,
        investment_capacity=customer.investment_capacity,
        goals=goals,
        data_source=customer.data_source,
    )
    return AgentStateDelta(customer_profile=profile)


# ---------------------------------------------------------------------------
# Risk Analyst
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _far_trans_tables_cached() -> dict[str, pd.DataFrame]:
    """Loaded once per process (mirrors "load artifacts once" for this
    read-only reference data too) -- never re-downloaded, never modified."""
    return load_far_trans_tables()


@lru_cache(maxsize=1)
def _risk_artifacts_cached() -> tuple:
    preprocessor = joblib.load(RISK_MODELS_DIR / f"preprocessor_{RISK_MODEL_VERSION}.pkl")
    classifier = joblib.load(RISK_MODELS_DIR / f"rf_{RISK_MODEL_VERSION}.pkl")  # random_forest: Phase 4's best_model
    return preprocessor, classifier


def external_customer_id(session: Session, customer_id: int) -> str | None:
    """Maps a DB `customer_id` to the raw FAR-Trans `customerID` (see the
    module docstring) -- public because Phase 11's graph wrappers need it
    too, not just this module's own nodes."""
    from wealthpilot.db.models import Customer

    customer = session.get(Customer, customer_id)
    if customer is None or not customer.risk_inputs:
        return None
    return customer.risk_inputs.get("external_customer_id")


def engineer_features_for_customer(external_customer_id: str) -> dict | None:
    """Calls Phase 3's `engineer_features()` completely unmodified, on the
    raw FAR-Trans tables filtered to this one customer (see module
    docstring for why this is provably equivalent to filtering the full
    population's output afterward). Returns `None` if the customer has no
    row in `customer_information.csv` or produces no feature row (e.g. zero
    transactions on/before their point-in-time cutoff -- Phase 3's own
    documented behaviour, not a bug here)."""
    tables = _far_trans_tables_cached()
    customers = tables["customers"]
    transactions = tables["transactions"]

    customer_rows = customers[customers["customerID"] == external_customer_id]
    if customer_rows.empty:
        return None
    txn_rows = transactions[transactions["customerID"] == external_customer_id]

    features = engineer_features(customer_rows, txn_rows, tables["assets"], tables["close_prices"])
    if external_customer_id not in features.index:
        return None
    row = features.loc[external_customer_id]
    return {col: row[col] for col in ALL_FEATURES}


def risk_analyst_node(state: AgentState, feature_row: dict | None) -> AgentStateDelta:
    """Classifies risk category using the ALREADY-TRAINED Phase 4 model
    (`models/risk/rf_v1.pkl`, Phase 4's selected best model, +
    `preprocessor_v1.pkl`) -- never retrained, never a different model
    selection. `feature_row` (see `engineer_features_for_customer`) is an
    explicit input rather than computed internally, so this node stays a
    thin, testable wrapper around Phase 3/4's own components.

    SHAP values are NOT computed here (known limitation, see the Phase 10
    report) -- Phase 4's SHAP explainability was global/training-population
    -level; live per-customer SHAP would need reloading a TreeExplainer and
    is deferred rather than risk an untested addition here.
    """
    if feature_row is None:
        return AgentStateDelta(
            risk_assessment=RiskAssessmentResult(
                model_version=RISK_MODEL_VERSION,
                data_source="models/risk",
                unavailable_reason="engineered feature row was not provided (no genuine risk label or no "
                "point-in-time-visible transactions for this customer -- see engineer_features_for_customer)",
            )
        )

    missing = [f for f in ALL_FEATURES if f not in feature_row]
    if missing:
        return AgentStateDelta(
            risk_assessment=RiskAssessmentResult(
                model_version=RISK_MODEL_VERSION,
                data_source="models/risk",
                unavailable_reason=f"feature_row is missing required columns: {missing}",
            ),
            new_errors=[NodeError(node_name="risk_analyst", error_type="validation", message=f"missing features: {missing}")],
        )

    preprocessor, classifier = _risk_artifacts_cached()
    X = pd.DataFrame([feature_row])[ALL_FEATURES]
    X_t = preprocessor.transform(X)
    predicted = str(classifier.predict(X_t)[0])
    proba = classifier.predict_proba(X_t)[0]
    class_probabilities = {str(c): float(p) for c, p in zip(classifier.classes_, proba)}
    confidence = float(max(proba))

    if predicted not in GENUINE_RISK_LEVELS:
        return AgentStateDelta(
            risk_assessment=RiskAssessmentResult(
                model_version=RISK_MODEL_VERSION,
                data_source="models/risk",
                unavailable_reason=f"model produced an unrecognized label {predicted!r}",
            ),
            new_errors=[
                NodeError(
                    node_name="risk_analyst", error_type="processing_failure",
                    message=f"classifier returned a non-genuine label {predicted!r}",
                )
            ],
        )

    return AgentStateDelta(
        risk_assessment=RiskAssessmentResult(
            risk_category=predicted,
            confidence=confidence,
            class_probabilities=class_probabilities,
            model_version=RISK_MODEL_VERSION,
            data_source="models/risk",
        )
    )


def reprofile_node(state: AgentState, feature_row: dict | None) -> AgentStateDelta:
    """"Re-run risk assessment when behaviour has materially changed"
    (BUILD_PLAN.md section 8) -- a thin wrapper re-invoking
    `risk_analyst_node` itself, never a second risk-scoring
    implementation. WHETHER drift is "significant enough" to warrant this
    call is Phase 11's routing decision (reads
    `state.financial_health.behaviour_drift_flag`); this node just performs
    the re-assessment once invoked."""
    return risk_analyst_node(state, feature_row)


def information_request_node(state: AgentState) -> AgentStateDelta:
    """"Ask for more data instead of guessing on low-confidence risk"
    (BUILD_PLAN.md section 8) -- produces structured follow-up questions
    from the CURRENT risk assessment. The confidence THRESHOLD that decides
    whether to invoke this node at all is Phase 11's conditional-routing
    constant, not decided here (section 30: do not invent a threshold) --
    this node only defines what to ask given that it has already been
    invoked.
    """
    if state.risk_assessment is None:
        return AgentStateDelta(
            new_errors=[
                NodeError(
                    node_name="information_request", error_type="missing_data",
                    message="no risk_assessment present in state to generate follow-up questions from",
                )
            ]
        )
    questions = [
        "Could you share more detail about your recent trading activity or investment goals?",
        "Are there any recent life changes (income, expenses, employment) relevant to your risk tolerance?",
    ]
    return AgentStateDelta(
        new_errors=[
            NodeError(
                node_name="information_request",
                error_type="missing_data",
                message="risk confidence too low for a guessed classification; structured follow-up requested: "
                + " | ".join(questions),
            )
        ]
    )


# ---------------------------------------------------------------------------
# Financial Health Analyst
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _behaviour_artifacts_cached() -> tuple:
    from training.behaviour.common import PANEL_FEATURES  # pure constant, safe cross-boundary import

    iforest = joblib.load(BEHAVIOUR_MODELS_DIR / f"iforest_{BEHAVIOUR_MODEL_VERSION}.pkl")
    return iforest, PANEL_FEATURES


def financial_health_node(state: AgentState, external_customer_id: str | None) -> AgentStateDelta:
    """Behaviour-change detection only (Isolation Forest + rolling
    z-score/CUSUM, Phase 5's ALREADY-TRAINED artifact -- never refit).
    `expense_persona`/`savings_rate`/`expense_ratio` are ALWAYS explicitly
    unavailable for a FAR-Trans customer (sections 12/13/27): the Kaggle
    expense-clustering model is a different, unlinked population, and
    FAR-Trans has no income/expense fields to compute a real savings rate
    or expense ratio from -- neither is ever fabricated or backfilled.

    `external_customer_id` is the raw FAR-Trans `customerID` (see the
    module docstring) -- `AgentState`/`CustomerProfile` carry only the DB
    `customer_id`, so this is an explicit input rather than something the
    node looks up itself, exactly like `risk_analyst_node`'s `feature_row`.
    """
    from training.behaviour.common import MIN_PRIOR_MONTHS, build_monthly_panel
    from training.behaviour.detection import Z_SCORE_ALERT_THRESHOLD, rolling_zscore

    base_kwargs = dict(
        expense_persona=None,
        expense_persona_unavailable_reason="Kaggle-only expense-clustering model; FAR-Trans customers are a "
        "different, unlinked population (deferred synthetic-assembly decision) -- never applied here",
        savings_rate=None,
        expense_ratio=None,
        model_version=BEHAVIOUR_MODEL_VERSION,
        data_source="models/behaviour",
    )

    if external_customer_id is None:
        return AgentStateDelta(
            financial_health=FinancialHealthResult(**base_kwargs, unavailable_reason="external_customer_id not provided")
        )

    tables = _far_trans_tables_cached()
    transactions = tables["transactions"]
    txn_rows = transactions[transactions["customerID"] == external_customer_id]
    if txn_rows.empty:
        return AgentStateDelta(
            financial_health=FinancialHealthResult(**base_kwargs, unavailable_reason="no transaction history for this customer")
        )

    panel = build_monthly_panel(txn_rows, tables["assets"])
    customer_panel = panel[panel["customerID"] == external_customer_id].sort_values("month")
    if len(customer_panel) < MIN_PRIOR_MONTHS + 1:
        return AgentStateDelta(
            financial_health=FinancialHealthResult(
                **base_kwargs,
                unavailable_reason=f"insufficient trading history ({len(customer_panel)} months, "
                f"{MIN_PRIOR_MONTHS + 1} required) for behaviour-drift detection",
            )
        )

    z = rolling_zscore(customer_panel, "trade_count")
    latest_z = z.iloc[-1]
    drift_flag = bool(pd.notna(latest_z) and abs(latest_z) >= Z_SCORE_ALERT_THRESHOLD)

    iforest, panel_features = _behaviour_artifacts_cached()
    X = customer_panel[panel_features].to_numpy()
    scores = iforest.score_samples(X)
    predictions = iforest.predict(X)
    latest_anomaly = bool(predictions[-1] == -1)

    return AgentStateDelta(
        financial_health=FinancialHealthResult(
            **base_kwargs,
            behaviour_drift_flag=drift_flag,
            isolation_forest_anomaly=latest_anomaly,
            isolation_forest_score=float(scores[-1]),
        )
    )


# ---------------------------------------------------------------------------
# Goal Analyst
# ---------------------------------------------------------------------------


def goal_analyst_node(
    state: AgentState,
    assumptions: GoalAssumptions | None,
    current_date: date,
    historical_returns: np.ndarray | None = None,
    monthly_essential_expenses: float | None = None,
    current_liquid_assets: float | None = None,
) -> AgentStateDelta:
    """Calls Phase 7's Goal Engine only -- no TVM/Monte Carlo/emergency-fund
    math is duplicated here (section 11). `assumptions` (contribution
    amount, expected return, inflation) and `historical_returns`
    (Monte Carlo's bootstrap source) have NO default anywhere in Phase 7 by
    design, and this node does not invent one either -- they are explicit,
    optional inputs; goals/emergency-fund status are reported as
    unavailable, never fabricated, when they are not supplied.
    """
    if state.customer_profile is None:
        return AgentStateDelta(
            new_errors=[NodeError(node_name="goal_analyst", error_type="missing_data", message="customer_profile not yet loaded")]
        )

    goal_results: list[GoalAnalysisResult] = []
    for goal in state.customer_profile.goals:
        if assumptions is None:
            goal_results.append(
                GoalAnalysisResult(
                    goal_id=goal.id, goal_type=goal.goal_type, nominal_target_amount=goal.target_amount,
                    unavailable_reason="no GoalAssumptions (contribution/return/inflation) supplied",
                )
            )
            continue
        try:
            goal_input = GoalInput(
                customer_id=state.customer_id, goal_type=goal.goal_type, target_amount=goal.target_amount,
                current_savings=goal.current_savings, target_date=goal.target_date, priority=goal.priority,
            )
            analysis = analyze_goal_funding(goal_input, assumptions, current_date)
        except ValueError as exc:
            goal_results.append(
                GoalAnalysisResult(goal_id=goal.id, goal_type=goal.goal_type, nominal_target_amount=goal.target_amount, unavailable_reason=str(exc))
            )
            continue

        mc_probability = None
        feasibility = None
        if historical_returns is not None and analysis.periods_remaining > 0:
            mc = run_goal_monte_carlo(
                current_savings=goal.current_savings,
                periodic_contribution=assumptions.contribution_amount,
                n_periods=analysis.periods_remaining,
                target_amount=analysis.inflation_adjusted_target_amount,
                historical_returns=historical_returns,
            )
            mc_probability = mc.success_probability
            feasibility = classify_feasibility(mc_probability)

        goal_results.append(
            GoalAnalysisResult(
                goal_id=goal.id,
                goal_type=goal.goal_type,
                nominal_target_amount=analysis.nominal_target_amount,
                inflation_adjusted_target_amount=analysis.inflation_adjusted_target_amount,
                required_periodic_contribution=analysis.required_periodic_contribution,
                contribution_gap=analysis.contribution_gap,
                already_achieved=analysis.already_achieved,
                monte_carlo_success_probability=mc_probability,
                feasibility=feasibility,
            )
        )

    if monthly_essential_expenses is None or current_liquid_assets is None:
        ef_result = EmergencyFundResult(
            unavailable_reason="monthly_essential_expenses/current_liquid_assets not supplied "
            "(FAR-Trans has no expense/liquid-asset data -- never fabricated)"
        )
    else:
        status = assess_emergency_fund(monthly_essential_expenses, current_liquid_assets)
        ef_result = EmergencyFundResult(
            required_amount=status.required_amount,
            current_amount=status.current_amount,
            shortfall=status.shortfall,
            sufficient=status.sufficient,
            savings_first_required=savings_first_required(status),
        )

    return AgentStateDelta(goal_results=goal_results, emergency_fund=ef_result)


# ---------------------------------------------------------------------------
# Market Analyst
# ---------------------------------------------------------------------------


def market_analyst_node(state: AgentState) -> AgentStateDelta:
    """Reads Phase 6's ALREADY-COMPUTED regime results from
    `models/metrics.json["market"]` -- never re-runs Phase 6's training
    (a full walk-forward run takes ~1 hour and refetches yfinance data;
    doing that per node invocation would violate "train offline, serve
    online" and section 12's "do not introduce new market forecasts").
    Integration/interface layer only, exactly as section 12 specifies."""
    import json

    if not METRICS_PATH.exists():
        return AgentStateDelta(
            market_analysis=MarketAnalysisResult(unavailable_reason="models/metrics.json not found")
        )
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    market = metrics.get("market")
    if market is None:
        return AgentStateDelta(
            market_analysis=MarketAnalysisResult(unavailable_reason="metrics.json has no 'market' section")
        )

    instruments = [
        InstrumentRegime(
            ticker=ticker,
            latest_regime=result.get("latest_regime"),
            date_range=result.get("date_range"),
        )
        for ticker, result in market.get("results_by_instrument", {}).items()
    ]
    return AgentStateDelta(
        market_analysis=MarketAnalysisResult(
            instruments=instruments,
            model_version=market.get("model_version"),
            data_source=market.get("data_source"),
            trained_at=market.get("trained_at"),
        )
    )


# ---------------------------------------------------------------------------
# Portfolio Manager / Savings-first
# ---------------------------------------------------------------------------


def load_portfolio_returns(session: Session) -> pd.DataFrame:
    """Reads the approved 3-asset universe's close prices from
    `market_data` (Phase 6's table, read-only) and builds a return matrix.
    Mirrors `training/portfolio/common.py::build_return_matrix` exactly
    (same fill_method=None fix, same drop-any-missing-row rule) --
    duplicated rather than imported because that module lives under
    `training/`, and an online-serving node should not import from the
    offline-training tree (CLAUDE.md rule 5); the transform itself is a
    handful of lines, not business logic worth a cross-boundary import.

    Public (was `_load_portfolio_returns`) as of Phase 28: a second
    caller, `analysis_service.py`'s `_historical_returns_for_goal_analysis`,
    reuses this SAME function to source Monte Carlo's `historical_returns`
    input -- never a second, parallel implementation of "read market_data
    and compute returns".
    """
    from wealthpilot.db.models import MarketData

    stmt = (
        select(MarketData.ticker, MarketData.date, MarketData.close)
        .where(MarketData.ticker.in_(ASSET_UNIVERSE))
        .order_by(MarketData.ticker, MarketData.date)
    )
    rows = session.execute(stmt).all()
    if not rows:
        raise RuntimeError(f"no market_data rows found for {ASSET_UNIVERSE}")
    df = pd.DataFrame(rows, columns=["ticker", "date", "close"])
    prices = df.pivot(index="date", columns="ticker", values="close").astype(float).sort_index()
    prices = prices[ASSET_UNIVERSE]
    return prices.pct_change(fill_method=None).dropna(how="any")


def portfolio_manager_node(state: AgentState, session: Session, strategy: str = "mvo") -> AgentStateDelta:
    """Calls Phase 8's `core.optimizer` LIVE (cheap, pure, deterministic --
    unlike Market Analyst's heavy walk-forward retrain) on a freshly-read
    `market_data` return matrix, using the customer's OWN risk_level for
    `strategy="mvo"`. Never redesigns MVO/HRP/1-N, never changes the
    approved QQQ bands or the 70% cap (section 29) -- every threshold comes
    directly from `wealthpilot.core.optimizer`'s own constants.

    This node does NOT itself decide "optimize or defer" for an
    insufficient emergency fund -- see `savings_first_node` and the module
    docstring: that branch is Phase 11's conditional routing, based on
    `state.emergency_fund.sufficient`.
    """
    if strategy == "mvo" and (state.risk_assessment is None or state.risk_assessment.risk_category is None):
        return AgentStateDelta(
            portfolio_result=PortfolioResult(
                strategy=strategy, asset_universe=ASSET_UNIVERSE, config_version=PORTFOLIO_CONFIG_VERSION,
                data_source="market_data (PostgreSQL)",
                unavailable_reason="strategy='mvo' requires a known risk_category from risk_assessment",
            )
        )

    try:
        returns = load_portfolio_returns(session)
    except RuntimeError as exc:
        return AgentStateDelta(
            portfolio_result=PortfolioResult(
                strategy=strategy, asset_universe=ASSET_UNIVERSE, config_version=PORTFOLIO_CONFIG_VERSION,
                data_source="market_data (PostgreSQL)", unavailable_reason=str(exc),
            ),
            new_errors=[NodeError(node_name="portfolio_manager", error_type="missing_data", message=str(exc))],
        )

    mu = expected_returns_historical(returns)
    cov, _shrinkage = covariance_ledoit_wolf(returns)

    risk_level = state.risk_assessment.risk_category if state.risk_assessment else None
    if strategy == "equal_weight":
        weights = equal_weight_portfolio(ASSET_UNIVERSE)
        constraints = None
    elif strategy == "hrp":
        weights = hrp_weights(returns)
        constraints = None
    elif strategy == "mvo":
        bounds = effective_bounds(risk_level)
        weights = mvo_max_sharpe(mu, cov, bounds, RISK_FREE_RATE)
        constraints = {"general_single_asset_cap": GENERAL_SINGLE_ASSET_CAP, "risk_level_qqq_band": list(RISK_LEVEL_QQQ_BANDS[risk_level])}
    else:
        return AgentStateDelta(
            new_errors=[NodeError(node_name="portfolio_manager", error_type="validation", message=f"unknown strategy {strategy!r}")]
        )

    ret = portfolio_return(weights, mu)
    vol = portfolio_volatility(weights, cov)
    result = PortfolioResult(
        strategy=strategy,
        risk_level=risk_level,
        weights=weights.to_dict(),
        asset_universe=ASSET_UNIVERSE,
        constraints=constraints,
        expected_return=ret,
        expected_volatility=vol,
        sharpe_ratio=sharpe_ratio(ret, vol, RISK_FREE_RATE),
        config_version=PORTFOLIO_CONFIG_VERSION,
        data_source="market_data (PostgreSQL)",
    )
    return AgentStateDelta(portfolio_result=result)


def savings_first_node(state: AgentState) -> AgentStateDelta:
    """"Produce a liquidity-first recommendation, skip optimization"
    (BUILD_PLAN.md section 8) -- reuses `state.emergency_fund` (Phase 7's
    own output) directly, never recomputes it. Produces no portfolio
    weights at all (section 13/PROJECT_PLAN.md section 2.6: "skipping
    optimization entirely").

    Phase 28 fix: `state.emergency_fund is None` (the node genuinely never
    ran -- e.g. `state.customer_profile` was never loaded) remains a real
    `missing_data` error, since there is nothing to build a recommendation
    from at all. But `emergency_fund.sufficient is None` (the assessment
    DID run, and honestly could not confirm sufficiency because
    `monthly_essential_expenses`/`current_liquid_assets` were not supplied
    -- see `core/goals.py::goal_analyst_node`) is no longer treated as an
    error here: `agents/graph.py::route_after_market`'s own routing already
    treats `sufficient is None` the same, conservative way as `sufficient
    is False` ("do not recommend aggressive investment allocation when
    essential liquidity requirements are not satisfied" -- approved
    2026-09-14), so this node honoring that same reading of `None` is
    aligning with an already-approved decision, not inventing a new one.
    The message is honest about WHICH case occurred -- a known shortfall
    amount is stated only when one is actually known; the unknown case
    says plainly that it is unknown, never a fabricated number."""
    if state.emergency_fund is None:
        return AgentStateDelta(
            new_errors=[
                NodeError(
                    node_name="savings_first", error_type="missing_data",
                    message="no emergency_fund status available to build a savings-first recommendation from",
                )
            ]
        )
    if state.emergency_fund.sufficient is False:
        unavailable_reason = (
            f"normal portfolio optimization deferred: emergency-fund shortfall of "
            f"{state.emergency_fund.shortfall:.2f} -- build liquidity before investing"
        )
    elif state.emergency_fund.sufficient is None:
        unavailable_reason = (
            "normal portfolio optimization deferred: emergency-fund sufficiency could not be "
            "confirmed (required financial inputs not supplied) -- a savings-first recommendation "
            "is given conservatively rather than assuming sufficiency"
        )
    else:
        unavailable_reason = "savings_first_node was invoked but the emergency fund is already sufficient"

    result = PortfolioResult(
        strategy="savings_first",
        asset_universe=[],
        config_version=PORTFOLIO_CONFIG_VERSION,
        data_source="core.goals (Phase 7 emergency-fund assessment)",
        unavailable_reason=unavailable_reason,
    )
    return AgentStateDelta(portfolio_result=result)


# ---------------------------------------------------------------------------
# Compliance Analyst
# ---------------------------------------------------------------------------


def compliance_analyst_node(state: AgentState, is_savings_first_recommendation: bool = False) -> AgentStateDelta:
    """Calls Phase 9's `evaluate_compliance` ONLY -- no rule is
    reimplemented, no threshold is duplicated, no decision is altered
    (section 14/30). Builds a `ComplianceProposal` strictly from
    already-computed state fields; never modifies `state.portfolio_result`.
    `apply_delta` (agents/state.py) derives `blocked`/`block_reason` from
    the returned `compliance_result` automatically -- this node does not
    set them itself.
    """
    proposal = ComplianceProposal(
        risk_level=state.risk_assessment.risk_category if state.risk_assessment else None,
        weights=state.portfolio_result.weights if state.portfolio_result else None,
        emergency_fund_sufficient=state.emergency_fund.sufficient if state.emergency_fund else None,
        is_savings_first_recommendation=is_savings_first_recommendation,
    )
    result = evaluate_compliance(proposal)
    return AgentStateDelta(compliance_result=result)
