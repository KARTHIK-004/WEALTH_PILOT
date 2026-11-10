"""Phase 15 — public API request/response schemas.

Every model here is a deliberately separate, PUBLIC Pydantic v2 schema —
never a re-export of an internal `agents/state.py`/`core/*.py` model
(section 5: "the public API schema must NOT simply expose internal
AgentState"). Fields are copied from the internal models field-for-field
where that internal shape is already the correct public shape, so the
public contract can evolve independently of internal refactoring and
never leaks internal-only concepts (DB sessions, model objects, AutoGen
transcripts, Gemini prompts, hidden reasoning, chain-of-thought — none of
which have a field anywhere in this file).

Every section is `Optional` — missing/unavailable backend data is
represented as `None`, never guessed or defaulted (matches every prior
phase's "do not fabricate missing data" rule, now enforced at the API
boundary too).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Questionnaire (GET /api/questionnaire)
# ---------------------------------------------------------------------------


class QuestionOption(BaseModel):
    key: str
    text: str


class Question(BaseModel):
    number: int
    text: str
    options: list[QuestionOption]


class QuestionnaireSection(BaseModel):
    name: str
    questions: list[Question]


class QuestionnaireResponse(BaseModel):
    sections: list[QuestionnaireSection]


# ---------------------------------------------------------------------------
# Profiles (POST /api/profiles, GET /api/profiles/{id})
# ---------------------------------------------------------------------------


class GoalCreate(BaseModel):
    goal_type: str = Field(min_length=1, max_length=100)
    target_amount: float = Field(gt=0)
    target_date: date
    current_savings: float = Field(default=0, ge=0)
    priority: int = Field(default=1, ge=1)


class ProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    age: int | None = Field(default=None, ge=0, le=120)
    income: float | None = Field(default=None, ge=0)
    employment_status: str | None = Field(default=None, max_length=100)
    customer_type: str | None = Field(default=None, max_length=50)
    investment_capacity: str | None = Field(default=None, max_length=50)
    goals: list[GoalCreate] = Field(default_factory=list)


class ProfileCreateResponse(BaseModel):
    customer_id: int


class ProfileLookupResponse(BaseModel):
    """`GET /api/profiles/lookup` (Live Analysis Flow phase) -- an exact,
    case-sensitive name match against `Customer.name`, returning
    `customer_id: None` (never a 404) when nothing matches, since "no
    customer has this name" is a normal, expected outcome for a lookup, not
    an error condition. Reuses the existing `customers.name` column --
    no schema change. Deliberately minimal: no partial/fuzzy matching, no
    listing, no pagination -- a single-purpose lookup for the prototype
    demo-account mechanism (`frontend/src/lib/demo-customer.ts`) to find an
    already-seeded, name-known demo persona without hard-coding its numeric
    id, mirroring the read-only lookup
    `backend/scripts/seed_demo_data.py::_find_existing_customer_id` already
    performs directly against the database for the exact same reason. Not a
    general "search customers" capability -- see
    `reports/live_analysis_flow_fix_report.md` for the full rationale."""

    customer_id: int | None


class GoalOut(BaseModel):
    id: int
    goal_type: str
    target_amount: float
    target_date: date
    current_savings: float
    priority: int


class ProfileResponse(BaseModel):
    customer_id: int
    name: str
    age: int | None
    income: float | None
    employment_status: str | None
    customer_type: str | None
    investment_capacity: str | None
    goals: list[GoalOut]
    data_source: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Financial inputs (Phase 28) — GET/PUT /api/profiles/{id}/financial-inputs
# ---------------------------------------------------------------------------


class FinancialInputsUpdate(BaseModel):
    """Every field is independently optional -- a caller may supply only
    the ones they currently know (section 5: "distinguish KNOWN from
    UNAVAILABLE. Do not silently substitute zero."). Omitting a field on a
    `PUT` leaves it at its current stored value (or `NULL` if never set) --
    this is an upsert/merge, not a full-replace, matching the existing
    questionnaire-answer endpoint's own upsert semantics rather than
    forcing a caller to resend every field just to update one.

    Fields map 1:1 to `core/goals.py`'s own required parameters --
    `monthly_essential_expenses`/`current_liquid_assets`
    (`assess_emergency_fund`) and `contribution_amount`/
    `annual_return_rate`/`annual_inflation_rate`/
    `contribution_periods_per_year` (`GoalAssumptions`) -- no field exists
    here that Phase 7's own engine does not already define and require.
    Bounds (`ge=0` for amounts, `gt=-1.0` for rates) mirror
    `core/goals.py`'s own validators exactly, not a new invented
    constraint.
    """

    monthly_essential_expenses: float | None = Field(default=None, ge=0)
    current_liquid_assets: float | None = Field(default=None, ge=0)
    contribution_amount: float | None = Field(default=None, ge=0)
    annual_return_rate: float | None = Field(default=None, gt=-1.0)
    annual_inflation_rate: float | None = Field(default=None, gt=-1.0)
    contribution_periods_per_year: int | None = Field(default=None, gt=0)


class FinancialInputsResponse(BaseModel):
    customer_id: int
    monthly_essential_expenses: float | None
    current_liquid_assets: float | None
    contribution_amount: float | None
    annual_return_rate: float | None
    annual_inflation_rate: float | None
    contribution_periods_per_year: int | None
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# Questionnaire answers (Phase 23) — POST/GET /api/profiles/{id}/questionnaire
# ---------------------------------------------------------------------------


class QuestionnaireAnswerIn(BaseModel):
    """One submitted answer. `question_number`/`option_key` are the same
    stable identifiers `GET /api/questionnaire` already returns
    (`Question.number`/`QuestionOption.key`) — never question/option text,
    which is never duplicated into the database (see
    `db.models.QuestionnaireAnswer`)."""

    question_number: int = Field(gt=0)
    option_key: str = Field(min_length=1, max_length=1)


class QuestionnaireAnswersSubmitRequest(BaseModel):
    answers: list[QuestionnaireAnswerIn] = Field(min_length=1)


class QuestionnaireAnswerOut(BaseModel):
    question_number: int
    option_key: str
    updated_at: datetime


class QuestionnaireAnswersResponse(BaseModel):
    customer_id: int
    answers: list[QuestionnaireAnswerOut]


# ---------------------------------------------------------------------------
# Goal creation for an existing profile (Phase 23) —
# POST /api/profiles/{id}/goals
# ---------------------------------------------------------------------------
#
# Reuses `GoalCreate` (request body) and `GoalOut` (response), already
# defined above for the embedded-goals path `POST /api/profiles` has used
# since Phase 21 — no second, parallel goal schema.


# ---------------------------------------------------------------------------
# Analysis (POST /api/analysis, GET /api/analysis/{id})
# ---------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    profile_id: int
    # Optional override (BUILD_PLAN.md section 12: "profile_id, optional
    # overrides"). When omitted, Phase 14's risk-conditioned base strategy
    # decides the strategy -- this never forces a DIFFERENT strategy on the
    # recommendation itself, it only affects which strategy the deterministic
    # Phase 11 graph run's OWN `portfolio_result` uses as its first pass
    # (Phase 14 still obtains/recomputes the correct one independently if
    # this override doesn't match the risk-conditioned strategy -- see
    # `agents/recommendation.py::_obtain_portfolio_candidate`).
    portfolio_strategy: Literal["mvo", "hrp", "equal_weight"] | None = None


class RiskSection(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    risk_category: str | None
    confidence: float | None
    class_probabilities: dict[str, float] | None
    model_version: str | None
    data_source: str | None
    unavailable_reason: str | None


class FinancialHealthSection(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    expense_persona: str | None
    expense_persona_unavailable_reason: str | None
    savings_rate: float | None
    behaviour_drift_flag: bool | None
    isolation_forest_anomaly: bool | None
    model_version: str | None
    data_source: str | None
    unavailable_reason: str | None


class GoalSection(BaseModel):
    goal_id: int
    goal_type: str
    nominal_target_amount: float
    inflation_adjusted_target_amount: float | None
    required_periodic_contribution: float | None
    contribution_gap: float | None
    already_achieved: bool | None
    monte_carlo_success_probability: float | None
    feasibility: str | None
    unavailable_reason: str | None


class EmergencyFundSection(BaseModel):
    required_amount: float | None
    current_amount: float | None
    shortfall: float | None
    sufficient: bool | None
    savings_first_required: bool | None
    unavailable_reason: str | None


class InstrumentRegimeSection(BaseModel):
    ticker: str
    latest_regime: str | None
    date_range: list[str] | None


class MarketSection(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    instruments: list[InstrumentRegimeSection]
    model_version: str | None
    data_source: str | None
    unavailable_reason: str | None


class PortfolioSection(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    strategy: str | None
    risk_level: str | None
    weights: dict[str, float] | None
    asset_universe: list[str]
    expected_return: float | None
    expected_volatility: float | None
    sharpe_ratio: float | None
    config_version: str | None
    data_source: str | None
    unavailable_reason: str | None


class RuleResultSection(BaseModel):
    rule_id: str
    description: str
    severity: str
    triggered: bool
    passed: bool
    message: str
    reason: str | None


class ComplianceSection(BaseModel):
    decision: Literal["PASS", "WARN", "REJECT"]
    rules_version: str
    evaluated_at: str
    rule_results: list[RuleResultSection]


class RecommendationRationaleSection(BaseModel):
    risk_based_strategy: str | None
    goal_feasibility_used: str | None
    goal_preference: str | None
    goal_preference_aligned: bool | None
    market_regime_used: str | None
    market_preference: str | None
    market_preference_aligned: bool | None
    reasons: list[str]


class RecommendationProvenanceSection(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    phase14_version: str
    risk_model_version: str | None
    market_model_version: str | None
    portfolio_config_version: str | None
    compliance_rules_version: str | None


class RecommendationSection(BaseModel):
    status: Literal["approved", "savings_first", "blocked_rejected", "failed"]
    selected_strategy: Literal["mvo", "hrp", "equal_weight"] | None
    weights: dict[str, float] | None
    expected_return: float | None
    expected_volatility: float | None
    sharpe_ratio: float | None
    risk_category: str | None
    compliance_decision: Literal["PASS", "WARN", "REJECT"]
    rationale: RecommendationRationaleSection
    blocking_reason: str | None
    provenance: RecommendationProvenanceSection
    data_sources: list[str]
    evaluated_at: str


class ExplanationSection(BaseModel):
    status: Literal["completed", "skipped_rejected", "failed"]
    summary: str | None
    risk_explanation: str | None
    financial_health_explanation: str | None
    goal_explanation: str | None
    portfolio_explanation: str | None
    market_explanation: str | None
    compliance_explanation: str | None
    limitations: str | None
    disclaimer: str | None
    validation_passed: bool
    failure_reason: str | None


class AnalysisResult(BaseModel):
    """The complete, cached analysis result — the single object every
    frontend page reads from (BUILD_PLAN.md section 13). `recommendation`
    and `explanation` are `None` whenever the underlying pipeline did not
    reach that stage (compliance REJECT, low risk confidence, or an
    unexpected processing failure) — never a fabricated placeholder."""

    analysis_id: int
    customer_id: int
    status: Literal["approved", "rejected", "pending_information", "failed"]
    risk: RiskSection | None
    financial_health: FinancialHealthSection | None
    goals: list[GoalSection]
    emergency_fund: EmergencyFundSection | None
    market: MarketSection | None
    portfolio: PortfolioSection | None
    compliance: ComplianceSection | None
    recommendation: RecommendationSection | None
    explanation: ExplanationSection | None
    evaluated_at: str


# ---------------------------------------------------------------------------
# Scenarios (POST /api/scenarios/compare)
# ---------------------------------------------------------------------------


class ScenarioParameters(BaseModel):
    """One side of a what-if comparison — the only parameters this
    prototype allows a client to vary (never a raw override of a
    deterministic output value itself)."""

    profile_id: int
    portfolio_strategy: Literal["mvo", "hrp", "equal_weight"] | None = None


class ScenarioSummary(BaseModel):
    label: str
    risk_category: str | None
    goal_feasibility: list[str]
    portfolio_strategy: str | None
    expected_return: float | None
    expected_volatility: float | None
    sharpe_ratio: float | None
    compliance_decision: Literal["PASS", "WARN", "REJECT"] | None
    recommendation_status: Literal["approved", "savings_first", "blocked_rejected", "failed"] | None


class ScenarioCompareRequest(BaseModel):
    scenario_a: ScenarioParameters
    scenario_b: ScenarioParameters


class ScenarioCompareResponse(BaseModel):
    scenario_a: ScenarioSummary
    scenario_b: ScenarioSummary


# ---------------------------------------------------------------------------
# Q&A (POST /api/qa)
# ---------------------------------------------------------------------------


class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    analysis_id: int | None = None


class QAResponse(BaseModel):
    answer: str
    disclaimer: str


# ---------------------------------------------------------------------------
# Health (GET /api/health)
# ---------------------------------------------------------------------------


class ModelVersions(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    risk: str | None
    behaviour: str | None
    market: str | None
    portfolio: str | None
    compliance_rules: str | None


class HealthResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: str
    app_name: str
    version: str
    environment: str
    model_versions: ModelVersions


# ---------------------------------------------------------------------------
# Households (Phase 32) -- identity and membership ONLY.
#
# Deliberately no financial field anywhere in this section (no income,
# expenses, assets, liabilities, goals, risk, portfolio or recommendation):
# a household is contextual data in Phase 32 and household financial
# aggregation is not implemented (`docs/DECISIONS.md` ADR-031). Request
# models forbid unknown fields, so a client cannot smuggle one in.
# ---------------------------------------------------------------------------

HouseholdRelationship = Literal["self", "spouse", "parent", "child", "sibling", "other"]
HouseholdRole = Literal["primary", "member", "dependent"]


class HouseholdCreateRequest(BaseModel):
    """`POST /api/households` -- the household's name only. The caller (the
    `X-Customer-Id` customer) becomes its `self`/`primary` member."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped


class HouseholdMemberCreateRequest(BaseModel):
    """`POST /api/households/{id}/members`. `relationship`/`role` are
    controlled vocabularies (an unsupported value is a 422). The combination
    rules are the same ones the database CHECK constraints enforce: `self`
    is reserved for the household's primary member, a primary member is
    always `self`, and `self` is never a dependent. `(self, primary)` passes
    this schema on purpose -- it is the "create a second primary" attempt,
    which the service rejects with a 409 because the household already has
    one."""

    model_config = ConfigDict(extra="forbid")

    customer_id: int = Field(gt=0)
    relationship: HouseholdRelationship
    role: HouseholdRole = "member"

    @model_validator(mode="after")
    def _combination_rules(self) -> "HouseholdMemberCreateRequest":
        if self.role == "primary" and self.relationship != "self":
            raise ValueError("a primary member must have relationship 'self'")
        if self.relationship == "self" and self.role != "primary":
            raise ValueError("relationship 'self' is reserved for the household's primary member")
        return self


class HouseholdOut(BaseModel):
    id: int
    name: str
    member_count: int
    created_at: datetime
    updated_at: datetime


class HouseholdMemberOut(BaseModel):
    id: int
    household_id: int
    customer_id: int
    customer_name: str
    relationship: HouseholdRelationship
    role: HouseholdRole
    is_dependent: bool
    created_at: datetime
    updated_at: datetime


class HouseholdMembersResponse(BaseModel):
    household_id: int
    members: list[HouseholdMemberOut]


class ProfileHouseholdResponse(BaseModel):
    """`GET /api/profiles/{id}/household` -- `household`/`membership` are
    both `None` for a customer who has no household yet (a normal state, a
    200 -- never an implicit creation)."""

    customer_id: int
    household: HouseholdOut | None
    membership: HouseholdMemberOut | None


# ---------------------------------------------------------------------------
# Household financial data (Phase 33) -- SOURCE RECORDS ONLY.
#
# Four independent resources owned by a household. Nothing here is computed:
# there is no total, sum, net worth, ratio, cash flow or emergency-fund field
# anywhere in this section, and no response aggregates anything
# (`docs/DECISIONS.md` ADR-032). Every request model forbids unknown fields,
# so a client cannot set `household_id` (ownership is server-controlled, taken
# from the path) or smuggle in a field this phase does not define.
#
# `*Update` models leave every field optional and are applied with
# `exclude_unset`, the same merge-not-replace semantics
# `FinancialInputsUpdate` already uses -- an omitted field keeps its stored
# value, and a nullable field can be cleared by sending `null` explicitly.
# NULL is never a substitute for 0 (CLAUDE.md section 12).
# ---------------------------------------------------------------------------

HouseholdFinanceFrequency = Literal["monthly", "yearly", "one_time"]
HouseholdExpenseCategory = Literal[
    "housing", "food", "utilities", "transportation", "education", "healthcare",
    "insurance", "debt_payment", "childcare", "entertainment", "other",
]
HouseholdAssetType = Literal[
    "cash", "bank_account", "fixed_deposit", "investment", "real_estate", "vehicle", "retirement", "other",
]
HouseholdLiabilityType = Literal[
    "mortgage", "personal_loan", "education_loan", "vehicle_loan", "credit_card", "other",
]


def _require_non_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


# --------------------------------------------------------------------- income


class HouseholdIncomeCreate(BaseModel):
    """`POST /api/households/{id}/income`. `amount` must be strictly positive:
    a household that has no such income omits the record rather than storing
    a zero."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0)
    frequency: HouseholdFinanceFrequency
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("source")
    @classmethod
    def _source_not_blank(cls, value: str) -> str:
        return _require_non_blank(value)


class HouseholdIncomeUpdate(BaseModel):
    """Every field optional; only the fields actually supplied are changed."""

    model_config = ConfigDict(extra="forbid")

    source: str | None = Field(default=None, min_length=1, max_length=100)
    amount: float | None = Field(default=None, gt=0)
    frequency: HouseholdFinanceFrequency | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("source")
    @classmethod
    def _source_not_blank(cls, value: str | None) -> str | None:
        return None if value is None else _require_non_blank(value)


class HouseholdIncomeResponse(BaseModel):
    id: int
    household_id: int
    source: str
    amount: float
    frequency: HouseholdFinanceFrequency
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


# -------------------------------------------------------------------- expense


class HouseholdExpenseCreate(BaseModel):
    """`is_essential` has no default -- whether an expense is essential is the
    household's own judgement, never guessed here."""

    model_config = ConfigDict(extra="forbid")

    category: HouseholdExpenseCategory
    description: str | None = Field(default=None, max_length=200)
    amount: float = Field(gt=0)
    frequency: HouseholdFinanceFrequency
    is_essential: bool
    is_active: bool = True
    notes: str | None = Field(default=None, max_length=500)


class HouseholdExpenseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: HouseholdExpenseCategory | None = None
    description: str | None = Field(default=None, max_length=200)
    amount: float | None = Field(default=None, gt=0)
    frequency: HouseholdFinanceFrequency | None = None
    is_essential: bool | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


class HouseholdExpenseResponse(BaseModel):
    id: int
    household_id: int
    category: HouseholdExpenseCategory
    description: str | None
    amount: float
    frequency: HouseholdFinanceFrequency
    is_essential: bool
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------- asset


class HouseholdAssetCreate(BaseModel):
    """A self-reported holding. `current_value` may be `0` (a stated zero) but
    never negative; it is not a market price and is never priced, revalued or
    optimized by this system."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    asset_type: HouseholdAssetType
    current_value: float = Field(ge=0)
    is_liquid: bool
    description: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        return _require_non_blank(value)


class HouseholdAssetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    asset_type: HouseholdAssetType | None = None
    current_value: float | None = Field(default=None, ge=0)
    is_liquid: bool | None = None
    description: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        return None if value is None else _require_non_blank(value)


class HouseholdAssetResponse(BaseModel):
    id: int
    household_id: int
    name: str
    asset_type: HouseholdAssetType
    current_value: float
    is_liquid: bool
    description: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ liability


class HouseholdLiabilityCreate(BaseModel):
    """`monthly_payment` is optional: omitted stays `null` ("not provided"),
    while `0` means "explicitly no monthly payment" -- two different facts."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    liability_type: HouseholdLiabilityType
    outstanding_amount: float = Field(ge=0)
    monthly_payment: float | None = Field(default=None, ge=0)
    # Recorded for completeness only -- nothing computes with it (ADR-034).
    # Bounded by its Numeric(6, 4) storage limit and finite, so bad input is a
    # 422, never a database 500.
    interest_rate: float | None = Field(default=None, ge=0, le=99.9999, allow_inf_nan=False)
    description: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        return _require_non_blank(value)


class HouseholdLiabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    liability_type: HouseholdLiabilityType | None = None
    outstanding_amount: float | None = Field(default=None, ge=0)
    monthly_payment: float | None = Field(default=None, ge=0)
    interest_rate: float | None = Field(default=None, ge=0, le=99.9999, allow_inf_nan=False)
    description: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        return None if value is None else _require_non_blank(value)


class HouseholdLiabilityResponse(BaseModel):
    id: int
    household_id: int
    name: str
    liability_type: HouseholdLiabilityType
    outstanding_amount: float
    monthly_payment: float | None
    interest_rate: float | None
    description: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Household financial summary (Phase 34) -- GET /api/households/{id}/financial
# -summary. A READ-ONLY, deterministic aggregation of the Phase 33 source
# records. Every number here is computed once, in
# `core/household_finance.py`, and simply carried through: no route, service or
# frontend recomputes any of it, and nothing here feeds the individual analysis
# pipeline (`docs/DECISIONS.md` ADR-033).
#
# NULL is not zero. A monetary field is `None` when nothing is known, and a
# genuine stored 0 is returned as 0 -- the two must stay distinguishable all
# the way to the screen. Each section therefore carries `available` plus the
# project's usual `unavailable_reason` string (CLAUDE.md section 12).
# ---------------------------------------------------------------------------

HouseholdDataAvailability = Literal["available", "unavailable"]
HouseholdEmergencyFundStatus = Literal["sufficient", "insufficient", "unknown"]


class HouseholdIncomeSection(BaseModel):
    """`recurring_monthly` normalizes monthly and yearly (amount / 12) ACTIVE
    records; a one-time income is never turned into recurring income and is
    reported separately."""

    recurring_monthly: float | None
    one_time: float | None
    record_count: int
    active_record_count: int
    available: bool
    unavailable_reason: str | None


class HouseholdExpenseSection(BaseModel):
    """Essential/non-essential come from the household's stored `is_essential`
    judgement -- never inferred from the category."""

    recurring_monthly: float | None
    recurring_essential_monthly: float | None
    recurring_nonessential_monthly: float | None
    one_time: float | None
    record_count: int
    active_record_count: int
    available: bool
    unavailable_reason: str | None


class HouseholdAssetSection(BaseModel):
    """`liquid` sums only records the household marked `is_liquid`; liquidity is
    never inferred from `asset_type`, and values are the stored ones -- no
    market price or revaluation is applied."""

    total: float | None
    liquid: float | None
    record_count: int
    liquid_record_count: int
    available: bool
    unavailable_reason: str | None


class HouseholdLiabilitySection(BaseModel):
    """`monthly_payment` sums only liabilities that actually record one: a
    liability with no recorded payment is "not provided", not a payment of 0."""

    outstanding: float | None
    monthly_payment: float | None
    record_count: int
    available: bool
    unavailable_reason: str | None


class HouseholdCashFlowSection(BaseModel):
    """Recurring monthly income less recurring monthly expenses, available only
    when both are known. One-time records are excluded. This is deliberately
    NOT called savings, and no savings rate is derived from it."""

    recurring_monthly_income: float | None
    recurring_monthly_expenses: float | None
    monthly: float | None
    available: bool
    unavailable_reason: str | None


class HouseholdNetPositionSection(BaseModel):
    """Assets less outstanding liabilities -- income and expenses are not part
    of it. A missing side makes the value unknown, never zero."""

    total_assets: float | None
    total_outstanding_liabilities: float | None
    value: float | None
    available: bool
    unavailable_reason: str | None


class HouseholdEmergencyFundSection(BaseModel):
    """`required` is `target_months` x the household's recurring monthly
    essential expenses, using the same 6-month constant and the same
    `current >= required` comparison as the individual engine
    (`core/goals.py`). Informational only: it produces no recommendation,
    no savings-first verdict and no compliance decision in this phase."""

    required: float | None
    current_liquid_assets: float | None
    shortfall: float | None
    status: HouseholdEmergencyFundStatus
    target_months: int
    available: bool
    unavailable_reason: str | None


class HouseholdDataCompletenessSection(BaseModel):
    """Deterministic "known" vs "not provided" per area -- never a percentage
    or a score."""

    income: HouseholdDataAvailability
    expenses: HouseholdDataAvailability
    assets: HouseholdDataAvailability
    liabilities: HouseholdDataAvailability
    emergency_fund: HouseholdDataAvailability


class HouseholdFinancialSummaryResponse(BaseModel):
    """The whole read-only summary. It carries no customer id, no member
    detail, no risk/portfolio/recommendation field and no score."""

    household_id: int
    income: HouseholdIncomeSection
    expenses: HouseholdExpenseSection
    assets: HouseholdAssetSection
    liabilities: HouseholdLiabilitySection
    cash_flow: HouseholdCashFlowSection
    net_position: HouseholdNetPositionSection
    emergency_fund: HouseholdEmergencyFundSection
    data_completeness: HouseholdDataCompletenessSection


# ---------------------------------------------------------------------------
# Household goals (Phase 36) -- /api/households/{id}/goals
#
# A goal that belongs to a HOUSEHOLD, separate from the individual
# `financial_goals` (neither is ever converted into or merged with the other).
# These schemas carry stored FACTS only. No derived goal figure -- no
# inflation-adjusted target, required contribution, contribution gap,
# probability or feasibility -- appears here, because the inputs
# `core/goals.py` requires for them (return and inflation assumptions, a
# contribution amount, a historical return series) do not exist for a
# household, and inventing them is forbidden (`docs/DECISIONS.md` ADR-035).
# ---------------------------------------------------------------------------

HouseholdGoalType = Literal["emergency_fund", "house", "education", "retirement", "travel", "major_purchase", "other"]

# The largest value each column TYPE can store. These are storage limits, not
# financial rules: without them a non-finite value ("1e400" parses to inf) or an
# over-large one passes `gt=0` and then fails in the database as a 500 instead
# of the 422 a client input error deserves.
_NUMERIC_14_2_MAX = 999_999_999_999.99   # Numeric(14, 2) -- every money column
_NUMERIC_6_4_MAX = 99.9999               # Numeric(6, 4)  -- every rate column


class HouseholdGoalCreate(BaseModel):
    """`target_amount > 0` and a required `target_date`, as for individual
    goals. `current_savings` is OPTIONAL: omitted, it stays "not provided" --
    never 0 (CLAUDE.md section 12)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    goal_type: HouseholdGoalType
    target_amount: float = Field(gt=0, le=_NUMERIC_14_2_MAX, allow_inf_nan=False)
    current_savings: float | None = Field(default=None, ge=0, le=_NUMERIC_14_2_MAX, allow_inf_nan=False)
    target_date: date
    notes: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        return _require_non_blank(value)


class HouseholdGoalUpdate(BaseModel):
    """Every field optional; only the fields actually supplied are changed."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    goal_type: HouseholdGoalType | None = None
    target_amount: float | None = Field(default=None, gt=0, le=_NUMERIC_14_2_MAX, allow_inf_nan=False)
    current_savings: float | None = Field(default=None, ge=0, le=_NUMERIC_14_2_MAX, allow_inf_nan=False)
    target_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        return None if value is None else _require_non_blank(value)

    @model_validator(mode="after")
    def _required_fields_cannot_be_cleared(self) -> "HouseholdGoalUpdate":
        """Every field is optional so a partial update can omit it -- but a field
        that is REQUIRED on the goal cannot be set to an explicit `null`. Without
        this check the null would reach a NOT NULL column and surface as a 500
        instead of the 422 a client error deserves. Only `current_savings` and
        `notes` may be cleared, because only they are genuinely optional."""
        required = ("name", "goal_type", "target_amount", "target_date", "is_active")
        cleared = [field for field in required if field in self.model_fields_set and getattr(self, field) is None]
        if cleared:
            raise ValueError(f"{', '.join(cleared)} cannot be null; omit a field to leave it unchanged")
        return self


class HouseholdGoalResponse(BaseModel):
    id: int
    household_id: int
    name: str
    goal_type: HouseholdGoalType
    target_amount: float
    current_savings: float | None
    target_date: date
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Monthly financial records and behaviour features (Research Enhancement Track
# B1, ADR-042) -- `PUT/GET/DELETE /api/profiles/{id}/monthly-financial-records`
# and `GET /api/profiles/{id}/behaviour-features`.
# ---------------------------------------------------------------------------


def _reject_non_numbers(value: object) -> object:
    """An amount must arrive as a JSON number. Strings (including "1,000" or
    "12e3"), booleans and containers are rejected rather than coerced, so no
    unsupported numeric format is ever guessed at."""
    if value is None:
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("must be a number")
    return value


def _at_most_two_decimals(value: float | None) -> float | None:
    if value is None:
        return value
    exponent = Decimal(repr(value)).as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise ValueError("must have at most 2 decimal places")
    return value


class MonthlyRecordUpdate(BaseModel):
    """Upsert for one calendar month. Every field is optional. A field that is
    OMITTED keeps its stored value; a field sent as an explicit `null` clears
    it back to "not reported". `0` is a value the customer is stating, and is
    never produced from a missing field. Amounts are rupees for the month:
    `income` (on the stated `income_basis`), `expenses` (living costs only,
    excluding money moved to savings or investments), `savings` (newly set
    aside) and `investment_contribution` (newly invested). A transfer from
    savings into an investment is neither new savings nor new income."""

    model_config = ConfigDict(extra="forbid")

    income: float | None = Field(default=None, ge=0, le=_NUMERIC_14_2_MAX, allow_inf_nan=False)
    expenses: float | None = Field(default=None, ge=0, le=_NUMERIC_14_2_MAX, allow_inf_nan=False)
    savings: float | None = Field(default=None, ge=0, le=_NUMERIC_14_2_MAX, allow_inf_nan=False)
    investment_contribution: float | None = Field(default=None, ge=0, le=_NUMERIC_14_2_MAX, allow_inf_nan=False)
    income_basis: Literal["net", "gross"] | None = None

    @field_validator("income", "expenses", "savings", "investment_contribution", mode="before")
    @classmethod
    def _numbers_only(cls, value: object) -> object:
        return _reject_non_numbers(value)

    @field_validator("income", "expenses", "savings", "investment_contribution")
    @classmethod
    def _two_decimals(cls, value: float | None) -> float | None:
        return _at_most_two_decimals(value)


class MonthlyRecordResponse(BaseModel):
    customer_id: int
    period: str  # "YYYY-MM"
    income: float | None
    expenses: float | None
    savings: float | None
    investment_contribution: float | None
    income_basis: Literal["net", "gross"] | None
    updated_at: datetime


class MonthlyRecordListResponse(BaseModel):
    customer_id: int
    records: list[MonthlyRecordResponse]  # newest month first


class FeatureValueOut(BaseModel):
    """A number, or the reason there is none (exactly one is set)."""

    value: float | None
    unavailable_reason: str | None


class RatioFeaturesOut(BaseModel):
    expense_to_income: FeatureValueOut
    savings_to_income: FeatureValueOut
    investment_contribution_to_income: FeatureValueOut


class ChangeFeatureOut(BaseModel):
    absolute_change: FeatureValueOut
    relative_change: FeatureValueOut


class ConsistencyFeatureOut(BaseModel):
    share_with_amount: FeatureValueOut
    known_months: int
    window_months: int


class BehaviourFeaturesResponse(BaseModel):
    """Read-only financial-behaviour features derived from the customer's own
    monthly records. They are ratios and changes of reported amounts -- not a
    score, not sentiment, and not an input to any recommendation."""

    model_config = ConfigDict(protected_namespaces=())

    customer_id: int
    model_version: str
    data_source: str
    currency: str
    observation_count: int
    latest_period: str | None
    latest_income_basis: Literal["net", "gross"] | None
    latest_ratios: RatioFeaturesOut
    income_change: ChangeFeatureOut
    expenses_change: ChangeFeatureOut
    savings_change: ChangeFeatureOut
    investment_contribution_change: ChangeFeatureOut
    savings_consistency: ConsistencyFeatureOut
    investment_contribution_consistency: ConsistencyFeatureOut
    data_quality_notes: list[str]


# ---------------------------------------------------------------------------
# Financial behaviour and user-text sentiment (Research Enhancement Track, ADR-043)
# ---------------------------------------------------------------------------


class PersonalizedInsightRequest(BaseModel):
    """Optional text the user chose to write. It is analysed in memory and is never stored, logged or sent anywhere. The length and content limits are checked by
    the service (not here) so that a rejected text is never echoed back in a validation message."""

    text: str | None = None


class EvidenceOut(BaseModel):
    label: str
    phrase: str  # a short excerpt of the user's own words


class StatedPreferenceOut(BaseModel):
    """A possible preference read from the user's own words. Never an official risk assessment. Only `unconfirmed` is produced today: confirmations are not stored."""

    code: Literal["capital_preservation", "growth_seeking", "liquidity_access", "debt_reduction", "balanced_growth"]
    status: Literal["unconfirmed", "confirmed", "rejected", "not_inferred"]
    requires_confirmation: bool
    evidence: EvidenceOut


class RulesBaselineOut(BaseModel):
    """What the deterministic rules baseline alone concluded, kept beside a trained model's reading so a disagreement is never hidden."""

    model_config = ConfigDict(protected_namespaces=())

    label: Literal["positive", "negative", "neutral", "mixed", "uncertain", "insufficient_evidence"] | None
    method: Literal["rules_baseline"]
    model_version: str


class UserSentimentOut(BaseModel):
    """A suggestion for the user to confirm, never a fact about them. `confidence` is null unless a calibrated model supplied one (the rules baseline never does), and
    `confidence_band` is then `unavailable`. Emotional tone is not risk tolerance. `abstained` means the pipeline declined to interpret the text (see `abstain_reason`)."""

    model_config = ConfigDict(protected_namespaces=())

    status: Literal["analysed", "unavailable"]
    unavailable_reason: str | None
    sentiment: Literal["positive", "negative", "neutral", "mixed", "uncertain", "insufficient_evidence"] | None
    emotional_tone: Literal["concerned", "hopeful", "frustrated", "calm", "neutral", "unknown"] | None
    financial_relevance: Literal["relevant", "unrelated", "ambiguous"] | None
    topics: list[Literal["investment_risk", "saving", "debt", "goals", "liquidity", "market", "retirement", "emergency_fund"]]
    preferences: list[StatedPreferenceOut]
    evidence: list[EvidenceOut]
    confidence: float | None
    confidence_band: Literal["high", "medium", "low", "unavailable"]
    requires_confirmation: bool
    abstained: bool
    abstain_reason: Literal[
        "too_short", "low_quality_text", "unsupported_language", "unrelated_text", "ambiguous_context", "no_usable_evidence", "model_confidence_below_threshold", "model_unavailable"
    ] | None
    interpretation_state: Literal["valid", "weak", "abstained", "unavailable"]
    fallback_used: bool
    fallback_reason: Literal[
        "dependencies_missing", "artifact_missing", "artifact_corrupt", "artifact_incompatible", "path_not_allowed", "not_validated", "version_mismatch", "load_failed",
        "inference_failed", "timeout", "invalid_output", "invalid_configuration", "below_threshold"
    ] | None
    method: Literal["rules_baseline", "trained_model", "hybrid", "unavailable"]
    model_name: str | None
    model_version: str
    validation_status: str
    class_probabilities: dict[str, float] | None
    confidence_calibration_status: Literal["calibrated", "uncalibrated", "not_applicable"]
    sentiment_intensity: float | None
    intensity_available: bool
    rules_baseline: RulesBaselineOut | None
    disagreement: bool
    privacy_status: Literal["in_memory_only"]
    limitations: list[str]


ResearchReason = Literal[
    "disabled", "licence_not_verified", "format_not_allowed", "dependencies_missing", "weights_missing", "manifest_invalid", "revision_mismatch", "artifact_corrupt", "label_unsupported",
    "load_failed", "timeout", "inference_failed", "invalid_output", "invalid_configuration", "input_not_eligible", "loading", "internal_error", "no_candidate_approved", "registration_pending"
]


class ResearchModelResultOut(BaseModel):
    """One research model slot's independent answer (ADR-053, role-keyed by ADR-055). No text, no path. Scores are the model's own and are NOT a confidence: the probabilities are one uncalibrated
    softmax, valid only within this model. A slot with no registered candidate has `model_id` null and says why in `unavailable_reason`."""

    model_config = ConfigDict(protected_namespaces=())

    slot: Literal["financial", "general"]
    display_name: str
    model_id: str | None
    revision: str | None
    availability: Literal["available", "unavailable", "loading"]
    unavailable_reason: ResearchReason | None
    native_label: str | None
    normalized_label: Literal["positive", "negative", "neutral"] | None
    raw_scores: dict[str, float] | None
    probabilities: dict[str, float] | None
    probability_kind: Literal["raw_softmax_uncalibrated"] | None
    processing_ms: float | None


class ModelVsRulesOut(BaseModel):
    """One answering model's label set beside the rules-based reading. `agrees` is agreement of two classifiers, never proof that either is right."""

    model_config = ConfigDict(protected_namespaces=())

    slot: Literal["financial", "general"]
    rules_label: Literal["positive", "negative", "neutral", "mixed", "uncertain", "insufficient_evidence"] | None
    model_label: Literal["positive", "negative", "neutral"] | None
    relation: Literal["agrees", "disagrees", "rules_abstained", "not_compared"]
    explanation: str


class ResearchComparisonOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: Literal["agreement", "disagreement", "single_model", "model_unavailable", "one_model_unavailable", "both_models_unavailable", "no_model_configured", "uncertain"]
    shared_label: Literal["positive", "negative", "neutral"] | None
    explanation: str
    model_vs_rules: list[ModelVsRulesOut]


class TransformerResearchOut(BaseModel):
    """Research output, display only. `production_effect` is always `none`: no risk, goal, portfolio, recommendation or compliance result reads or changes because of it."""

    model_config = ConfigDict(protected_namespaces=())

    enabled: bool
    mode: Literal["research_experimental"]
    validation_status: Literal["not_human_validated"]
    production_effect: Literal["none"]
    rules_baseline: RulesBaselineOut | None
    models: list[ResearchModelResultOut]
    comparison: ResearchComparisonOut
    overall_sentiment: Literal["positive", "negative", "neutral", "mixed", "uncertain", "insufficient_evidence"] | None
    overall_source: Literal["transformer_comparison", "rules_baseline_fallback"]
    rules_relation: Literal["agrees", "disagrees", "rules_abstained", "not_compared"]
    uncertainty_reason: Literal[
        "models_disagree", "rules_disagree", "context_safeguard", "transformers_unavailable", "one_model_unavailable", "input_not_eligible", "model_label_uncertain", "no_model_registered"
    ] | None
    model_versions: dict[str, str]
    model_availability: dict[str, str]
    processing_metadata: dict[str, float | bool | str | None]
    notices: list[str]


class ResearchSlotStatusOut(BaseModel):
    """Which registered candidate, if any, fills a role. `registration_pending` means an owner-approved candidate exists but registering it as runnable has not been approved."""

    role: Literal["financial", "general"]
    state: Literal["registered", "registration_pending", "no_candidate_approved"]
    candidate_key: str | None


class TransformerCandidateStatusOut(BaseModel):
    """Per-candidate status for `GET /api/sentiment-model/status`. No local path, no secret. Built without loading, hashing or verifying anything."""

    model_config = ConfigDict(protected_namespaces=())

    model_key: str
    role: Literal["financial", "general"]
    display_name: str
    repository: str
    revision: str
    weight_licence: str
    licence_status: Literal["license_verified", "license_unverified", "blocked_by_licence"]
    format_status: Literal["safetensors_available", "no_safetensors_published"]
    registration: Literal["registered", "pending_owner_approval", "historical"]
    blocker: str | None
    weights_present: bool
    loaded: bool
    inference_enabled: bool
    availability: Literal["disabled", "blocked", "weights_missing", "not_loaded", "loading", "ready", "unavailable"]
    reason: str | None
    checked_on: str


class CandidateReviewOut(BaseModel):
    """The recorded review of one pretrained candidate (ADR-054). `verdict` is one of the five review values; only `approved_for_research_inference` would allow a download, and none has it."""

    model_config = ConfigDict(protected_namespaces=())

    key: str
    role: Literal["financial", "general"]
    repository: str
    revision: str
    architecture: str
    declared_licence: str
    licence_file: str
    base_model: str
    base_model_licence: str
    training_data: list[str]
    native_labels: list[str]
    label_mapping: dict[str, str]
    languages: str
    safetensors_file: str | None
    safetensors_sha256: str | None
    safetensors_size_bytes: int | None
    verdict: Literal["approved_for_research_inference", "blocked_by_license", "blocked_by_provenance", "blocked_by_approval", "incomplete_review"]
    blockers: list[str]
    active_in_registry: bool
    source_urls: list[str]
    checked_on: str
    owner_decision: str | None = None


class SentimentModelStatusOut(BaseModel):
    """`GET /api/sentiment-model/status`: whether a trained model is in use. No path, no secret, no text. `unavailable` means it is switched on but cannot be used, and says why."""

    model_config = ConfigDict(protected_namespaces=())

    enabled: bool
    state: Literal["disabled", "ready", "unavailable"]
    reason: Literal[
        "dependencies_missing", "artifact_missing", "artifact_corrupt", "artifact_incompatible", "path_not_allowed", "not_validated", "version_mismatch", "load_failed",
        "inference_failed", "timeout", "invalid_output", "invalid_configuration", "below_threshold"
    ] | None
    method_when_used: Literal["rules_baseline", "hybrid"]
    model_name: str | None
    model_version: str | None
    validation_status: str | None
    calibration_status: Literal["calibrated", "uncalibrated"] | None
    intensity_available: bool
    fallback_enabled: bool
    dependencies_available: bool
    data_source: str
    research_models: list[TransformerCandidateStatusOut] = []          # ADR-053: the two pretrained research candidates
    reviewed_candidates: list[CandidateReviewOut] = []                 # ADR-054: every candidate considered, with its verdict
    research_slots: list[ResearchSlotStatusOut] = []                   # ADR-055: which role slot has a registered candidate
    transformers_enabled: bool = False
    production_method: Literal["user_text_rules_v1"] = "user_text_rules_v1"
    production_activation: Literal["not_activated"] = "not_activated"


class BehaviourFindingOut(BaseModel):
    code: str
    category: Literal["trend", "activity", "ratio", "data_quality", "coverage"]
    status: Literal["observed", "unavailable", "not_included"]
    statement: str
    sources: list[str]
    direction: Literal["increased", "decreased", "unchanged"] | None
    values: dict[str, float | None]


class BehaviourFindingsOut(BaseModel):
    version: str
    history: Literal["none", "single_month", "multiple_months"]
    observation_count: int
    latest_period: str | None
    findings: list[BehaviourFindingOut]
    data_quality_notes: list[str]


class RiskProfileOut(BaseModel):
    category: str
    source: str
    assessed_at: datetime | None
    remains_authoritative: Literal[True]   # the stored assessment always outranks a reading of the user's text


class InsightStatementOut(BaseModel):
    text: str
    sources: list[str]
    kind: Literal["behaviour_fact", "stated_by_user", "risk_assessment", "caveat"]


class InsightConflictOut(BaseModel):
    """An inferred preference that disagrees with the stored risk assessment. The stored assessment stays in force; nothing is changed."""

    code: str
    detail: str
    inferred_preference: str
    stored_category: str
    authoritative_source: str
    preference_status: Literal["unconfirmed"]
    action: Literal["confirm_or_correct"]


class PersonalizedInsightResponse(BaseModel):
    """Display-only. No recommendation, risk profile, goal or compliance decision reads or changes because of this response."""

    model_config = ConfigDict(protected_namespaces=())

    customer_id: int
    analysis_timestamp: datetime
    status: Literal["complete", "behaviour_only", "profile_only", "unavailable"]
    model_version: str
    data_source: str
    behaviour: BehaviourFindingsOut
    user_sentiment: UserSentimentOut
    risk_profile: RiskProfileOut | None
    preference_confirmation: str
    statements: list[InsightStatementOut]
    conflicts: list[InsightConflictOut]
    caveats: list[str]
    purpose: str
    transformer_research: TransformerResearchOut | None = None          # ADR-053: research-only, off by default, display only


# ---------------------------------------------------------------------------
# Sensitive-data protection prototype (ADR-047). Protected notes are the ONLY encrypted record type; the older tables
# are unchanged and unprotected. The note text is the user's own words: it is never echoed in a validation error
# (api/errors.py USER_TEXT_ROUTE_MARKERS), never logged and never written to the audit ledger.
# ---------------------------------------------------------------------------

PROTECTED_NOTE_MAX_CHARS = 2000
PROTOTYPE_NOTICE = "Academic prototype \u2014 not a real blockchain."


class ProtectedNoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=PROTECTED_NOTE_MAX_CHARS)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class ProtectionInfoOut(BaseModel):
    """How this record is stored. Facts about the envelope; never key material."""

    encrypted_at_rest: bool
    algorithm: str
    envelope_version: int
    storage: Literal["off_chain_private_database"]


class ProtectedNoteMetadataOut(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    protection: ProtectionInfoOut


class ProtectedNoteOut(ProtectedNoteMetadataOut):
    content: str


class ProtectedNoteListOut(BaseModel):
    """Metadata only: listing never decrypts anything."""

    items: list[ProtectedNoteMetadataOut]


class EncryptionStatusOut(BaseModel):
    status: Literal["operational", "not_configured", "failed"]
    algorithm: str
    # A real encrypt/decrypt round trip with a random probe, run for this request. None when no key is configured.
    self_test_passed: bool | None
    unavailable_reason: str | None


class LedgerStatusOut(BaseModel):
    kind: Literal["local_hash_chain"]
    verification: Literal["valid", "invalid", "empty"]
    events_checked: int
    first_invalid_sequence: int | None
    reason: str | None
    note: str


class ExternalAnchorStatusOut(BaseModel):
    state: Literal["not_configured", "unreachable", "available"]
    detail: str


class LegacyDataStatusOut(BaseModel):
    encrypted: bool
    unprotected_categories: list[str]
    note: str


class SecurityStatusOut(BaseModel):
    """Privacy-safe security status for ONE profile. Everything here is computed by the backend from real checks."""

    prototype_notice: str
    storage: Literal["off_chain_private_database"]
    protected_note_count: int
    encryption: EncryptionStatusOut
    ledger: LedgerStatusOut
    external_anchor: ExternalAnchorStatusOut
    existing_data: LegacyDataStatusOut
    limitations: list[str]


class DemoMonthOut(BaseModel):
    """One FICTIONAL demonstration month. `income`, `expenses` and `savings` are the fixed fixture figures; every ratio and change is calculated by the existing behaviour-feature logic
    (`core/behaviour_features.py`) over the fixture months up to and including this one, so the first month has no change (with the reason) and nothing is invented here."""

    period: str  # "YYYY-MM"
    income: float | None
    expenses: float | None
    savings: float | None
    investment_contribution: float | None = None
    income_basis: Literal["net", "gross"] | None
    expense_to_income: FeatureValueOut
    savings_to_income: FeatureValueOut
    income_change: ChangeFeatureOut
    expenses_change: ChangeFeatureOut
    savings_change: ChangeFeatureOut
    investment_contribution_change: ChangeFeatureOut


class DemoFinancialBehaviourResponse(BaseModel):
    """`POST /api/demo/financial-behaviour` (only when `DEMO_MODE_ENABLED=true`): fictional months, the real behaviour-findings and rules-baseline sentiment code run over them, and the
    model status. Nothing is read from or written to a database; `demo` is always true so a caller can never mistake it for a customer's data."""

    demo: Literal[True] = True
    notice: str
    example_text: str
    currency: str
    months: list[DemoMonthOut]  # oldest first
    insight: PersonalizedInsightResponse
    sentiment_model: SentimentModelStatusOut
    data_source: str


class DemoMemberOut(BaseModel):
    """One FICTIONAL household member in the family demonstration: a stable demo label, a role, the member's fixed months with their calculated ratios and changes, and the records-only (or, for
    the primary member, text-reading) insight produced by the same code as the customer route."""

    label: str
    role: str
    months: list[DemoMonthOut]  # oldest first
    insight: PersonalizedInsightResponse


class DemoFamilyFinancialBehaviourResponse(BaseModel):
    """`POST /api/demo/family-financial-behaviour` (only when `DEMO_MODE_ENABLED=true`): a fictional family. `household_summary` is the real household engine's output over invented household records
    (so its totals, loans and EMIs are calculated, and a loan with no stated payment is reported as not provided). Nothing is read from or written to a database."""

    demo: Literal[True] = True
    scenario: Literal["family"] = "family"
    notice: str
    household_label: str
    example_text: str
    currency: str
    members: list[DemoMemberOut]
    household_summary: HouseholdFinancialSummaryResponse
    sentiment_model: SentimentModelStatusOut
    data_source: str
