"""SQLAlchemy ORM models for the nine tables in docs/BUILD_PLAN.md section 5.

Every table carries `id` and `created_at`. `data_source` is added wherever a
row's provenance can genuinely vary (FAR-Trans / Kaggle / yfinance /
user-entered / computed); `model_version` is added wherever a row is the
direct output of a trained model or the recommendation engine. This mirrors
CLAUDE.md's "add data_source and model_version columns everywhere for
auditability" rule, applied per-table rather than blindly on every table
(financial_goals and analysis_runs have a single, fixed provenance and do not
need `data_source`).

No business logic lives here — this is schema only. Table and column
docstrings intentionally repeat what's in BUILD_PLAN.md section 5 so the
model file is self-explanatory without cross-referencing the doc.
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wealthpilot.db.base import Base


class Customer(Base):
    """Customer profile core. Written by POST /api/profiles.

    Read by every agent node and every page.
    """

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    age: Mapped[int | None] = mapped_column(nullable=True)
    income: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    employment_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    investment_capacity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_inputs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    financial_goals: Mapped[list["FinancialGoal"]] = relationship(back_populates="customer")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="customer")
    portfolios: Mapped[list["Portfolio"]] = relationship(back_populates="customer")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="customer")
    agent_logs: Mapped[list["AgentLog"]] = relationship(back_populates="customer")
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(back_populates="customer")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="customer")
    risk_snapshots: Mapped[list["CustomerRiskSnapshot"]] = relationship(back_populates="customer")
    questionnaire_answers: Mapped[list["QuestionnaireAnswer"]] = relationship(back_populates="customer")
    financial_inputs: Mapped["FinancialInputs | None"] = relationship(back_populates="customer", uselist=False)


class CustomerRiskSnapshot(Base):
    """Full history of a customer's FAR-Trans dated profile records.

    Added in Phase 3 (not part of the original Phase 1 schema) because
    `customers` holds only current state, but FAR-Trans's
    `customer_information.csv` has multiple dated rows for ~3,378 real
    customers — genuine risk-profile drift over time, which is exactly what
    Phase 5's Behaviour Change Agent needs (PROJECT_PLAN.md section 2.3;
    BUILD_PLAN.md section 8). This table preserves every dated record
    unfiltered — including `Predicted_*`/`Not_Available` risk_level values —
    since it exists to preserve history, not to serve as a training-label
    source; genuine-label filtering (CLAUDE.md rule 7) happens at
    feature-engineering time, reading from here, not at ingestion time.
    Mirrors the `transactions` table's own append-only-log design rather
    than introducing a new pattern.
    """

    __tablename__ = "customer_risk_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    snapshot_date: Mapped[date] = mapped_column(Date)
    customer_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    investment_capacity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data_source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="risk_snapshots")


class FinancialGoal(Base):
    """One or more goals per customer. Always user-entered — no data_source."""

    __tablename__ = "financial_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    goal_type: Mapped[str] = mapped_column(String(100))
    target_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    target_date: Mapped[date] = mapped_column(Date)
    current_savings: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    priority: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="financial_goals")


class FinancialInputs(Base):
    """The Phase 28 financial-input data contract -- one row per customer,
    holding exactly the raw numbers `core/goals.py`'s already-approved
    Phase 7 engine requires and no field it does not: `monthly_
    essential_expenses`/`current_liquid_assets` for
    `assess_emergency_fund`, and `contribution_amount`/
    `annual_return_rate`/`annual_inflation_rate`/
    `contribution_periods_per_year` for `GoalAssumptions`. Every column is
    independently nullable -- `NULL` means "not yet provided", never `0`
    (CLAUDE.md: never substitute a default for missing data). A separate
    table, not new columns on `customers`, matching the existing
    `financial_goals`/`questionnaire_answers` pattern of one dedicated
    table per Phase-23-style persistence concern rather than widening the
    core profile table. `UniqueConstraint` on `customer_id` enforces the
    1:1 relationship a `PUT /api/profiles/{id}/financial-inputs`
    (upsert) endpoint expects.
    """

    __tablename__ = "financial_inputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), unique=True)
    monthly_essential_expenses: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    current_liquid_assets: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    contribution_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    annual_return_rate: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    annual_inflation_rate: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    contribution_periods_per_year: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="financial_inputs")


class QuestionnaireAnswer(Base):
    """One row per (customer, question): the customer's current selected
    option for that MiFID-II questionnaire question (Phase 23).

    Stores stable identifiers only -- `question_number` (matches
    `Question.number` from `GET /api/questionnaire`'s parsed response) and
    `selected_option_key` (matches that question's `QuestionOption.key`,
    always a single letter a-e per
    `api/services/questionnaire_service.py`'s `_OPTION_RE`) -- never the
    question/option text itself, which always comes fresh from
    `GET /api/questionnaire` (parsed from
    `datasets/raw/FAR-Trans/questionnaires.csv`) rather than being
    duplicated into this table.

    `uq_questionnaire_answers_customer_question` enforces at most one row
    per (customer, question), the same per-natural-key uniqueness pattern
    `Transaction`/`MarketData` already use elsewhere in this file --
    re-submitting an answer updates this row (see
    `api/routers/profiles.py::submit_questionnaire_answers`) rather than
    inserting a duplicate.

    Data storage only: no risk score, risk category, confidence, ML
    prediction, portfolio allocation, or recommendation is derived or
    stored here. The Phase 4 FAR-Trans risk model and every other approved
    ML/agent component are entirely unchanged by this table's existence.
    """

    __tablename__ = "questionnaire_answers"
    __table_args__ = (
        UniqueConstraint("customer_id", "question_number", name="uq_questionnaire_answers_customer_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    question_number: Mapped[int] = mapped_column()
    selected_option_key: Mapped[str] = mapped_column(String(1))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="questionnaire_answers")


class Transaction(Base):
    """Investment transaction history.

    Seeded from FAR-Trans transactions.csv or user-entered.

    `external_transaction_id` and `isin` added in Phase 3 (not part of the
    original Phase 1 schema): Phase 2 found that FAR-Trans's `transactionID`
    is not globally unique — it repeats across different customerIDs for
    what looks like joint-account co-ownership — so the real identity of a
    FAR-Trans-seeded row is (customerID, transactionID), not transactionID
    alone. Both columns are nullable because future user-entered
    transactions won't have a FAR-Trans ID or ISIN at all.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "external_transaction_id",
            name="uq_transactions_customer_external_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    external_transaction_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    transaction_type: Mapped[str] = mapped_column(String(20))
    data_source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="transactions")


class Portfolio(Base):
    """Current and recommended holdings. Written by the Portfolio Manager node."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    asset: Mapped[str] = mapped_column(String(100))
    allocation: Mapped[float] = mapped_column(Numeric(6, 3))
    value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    data_source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="portfolios")


class MarketData(Base):
    """OHLCV history per ticker, from yfinance.

    The only source of open/high/low/volume — FAR-Trans close_prices.csv is
    close-only. `source` (not `data_source`) matches the column name given in
    docs/MASTER_PROMPT.md section 5 and docs/BUILD_PLAN.md section 5.
    """

    __tablename__ = "market_data"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_market_data_ticker_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    date: Mapped[date] = mapped_column(Date)
    open: Mapped[float] = mapped_column(Numeric(14, 4))
    high: Mapped[float] = mapped_column(Numeric(14, 4))
    low: Mapped[float] = mapped_column(Numeric(14, 4))
    close: Mapped[float] = mapped_column(Numeric(14, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Recommendation(Base):
    """Final recommendation snapshot. Written by the recommendation engine (Phase 14)."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    recommendation: Mapped[str] = mapped_column(Text)
    risk_category: Mapped[str] = mapped_column(String(50))
    portfolio_allocation: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    model_version: Mapped[str] = mapped_column(String(50))
    data_source: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="recommendations")


class AgentLog(Base):
    """Auditable per-node execution record.

    Written by every LangGraph node on completion; backs the Agent Activity
    page's SSE replay (docs/BUILD_PLAN.md section 16), which is why `status`
    and `duration_ms` exist here even though the section 5 table's compact
    column list only named agent_name/action/result/model_version — the SSE
    flow in section 16 requires status and duration per event.
    """

    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    agent_name: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="agent_logs")


class RiskAssessment(Base):
    """Risk model output per run. Written by the Risk Analyst node."""

    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    risk_category: Mapped[str] = mapped_column(String(50))
    risk_score: Mapped[int] = mapped_column()
    confidence: Mapped[float] = mapped_column(Numeric(5, 4))
    class_probabilities: Mapped[dict] = mapped_column(JSON)
    shap_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="risk_assessments")


class AnalysisRun(Base):
    """Server-side cache of a full LangGraph run, keyed by profile hash.

    Backs CLAUDE.md's "cache graph results server-side on a profile hash"
    API convention. Not in MASTER_PROMPT.md's literal table list — added
    deliberately per docs/BUILD_PLAN.md section 5's note, not invented here.
    """

    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    profile_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20))
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="analysis_runs")


# ---------------------------------------------------------------------------
# Phase 32 -- Household foundation (identity and membership only).
# ---------------------------------------------------------------------------

# The controlled vocabularies. Stored as plain strings guarded by CHECK
# constraints (not a PostgreSQL enum type) so a later phase can extend a
# vocabulary with an ordinary migration. `api/schemas.py` declares the same
# values as `Literal` types; `tests/backend/db/test_household_models.py`
# asserts the two never drift apart.
HOUSEHOLD_RELATIONSHIPS: tuple[str, ...] = ("self", "spouse", "parent", "child", "sibling", "other")
HOUSEHOLD_ROLES: tuple[str, ...] = ("primary", "member", "dependent")


class Household(Base):
    """A family unit that customers can belong to (Phase 32).

    Identity only: deliberately NO financial column (income, expenses,
    assets, liabilities, risk, portfolio, recommendation ...). Those belong
    to later phases; a household is contextual data and changes nothing in
    the individual analysis pipeline (`docs/DECISIONS.md` ADR-031).
    """

    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    members: Mapped[list["HouseholdMember"]] = relationship(back_populates="household")


class HouseholdMember(Base):
    """One customer's membership in one household (Phase 32).

    Rules enforced by the database itself, so no code path can bypass them:
    a customer belongs to at most one household (`uq_household_members_
    customer` -- there is no soft delete, removal deletes the row, so every
    row is an active membership, and this also makes a customer appearing
    twice in the same household impossible); a household has at most one
    primary member (partial unique index); a primary member is always the
    `self` relationship and `self` is never a dependent; `is_dependent` is
    always exactly `role = 'dependent'`. "A household has AT LEAST one
    primary" cannot be expressed as a plain PostgreSQL constraint, so it is
    guaranteed transactionally instead: the primary membership is created in
    the same transaction as its household, and no API path can remove it
    (`api/services/household_service.py`).

    The Python attribute is `relationship_type` because `relationship` would
    shadow SQLAlchemy's own `relationship()` inside this class body; the
    column and the API field are both named `relationship`.

    Both foreign keys cascade: a membership is meaningless without its
    customer or its household (there is no API to delete either, so this
    only matters to the demo `reset` script deleting a persona).
    """

    __tablename__ = "household_members"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_household_members_customer"),
        Index("uq_household_members_one_primary", "household_id", unique=True, postgresql_where=text("role = 'primary'")),
        CheckConstraint(
            "relationship IN ('self', 'spouse', 'parent', 'child', 'sibling', 'other')",
            name="ck_household_members_relationship",
        ),
        CheckConstraint("role IN ('primary', 'member', 'dependent')", name="ck_household_members_role"),
        CheckConstraint("role <> 'primary' OR relationship = 'self'", name="ck_household_members_primary_is_self"),
        CheckConstraint("relationship <> 'self' OR role <> 'dependent'", name="ck_household_members_self_not_dependent"),
        CheckConstraint("is_dependent = (role = 'dependent')", name="ck_household_members_is_dependent_matches_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    relationship_type: Mapped[str] = mapped_column("relationship", String(20))
    role: Mapped[str] = mapped_column(String(20))
    is_dependent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    household: Mapped["Household"] = relationship(back_populates="members")
    customer: Mapped["Customer"] = relationship()


# ---------------------------------------------------------------------------
# Phase 33 -- Household financial DATA (source records only).
#
# Four independently addressable tables, owned by a household (never by a
# customer directly). Phase 33 stores what the household reports and computes
# NOTHING from it: no total, no net worth, no cash flow, no ratio, no
# emergency fund -- and none of it reaches the individual analysis pipeline
# (`docs/DECISIONS.md` ADR-032). Aggregation belongs to a later phase.
#
# Money is `Numeric(14, 2)`, the same convention `financial_inputs`,
# `financial_goals` and `transactions` already use. An optional field left out
# stays NULL: NULL means "not provided", never `0` (CLAUDE.md section 12).
# ---------------------------------------------------------------------------

# Controlled vocabularies, guarded by CHECK constraints and mirrored as
# `Literal` types in `api/schemas.py` (a test asserts they never drift apart),
# exactly as Phase 32's relationship/role vocabularies are. Each classification
# list ends in "other" so a household is never forced into a wrong category,
# and the free-text fields (`household_incomes.source`,
# `household_expenses.description`, `household_assets.name`,
# `household_liabilities.name`) carry the specifics.
HOUSEHOLD_FINANCE_FREQUENCIES: tuple[str, ...] = ("monthly", "yearly", "one_time")
HOUSEHOLD_EXPENSE_CATEGORIES: tuple[str, ...] = (
    "housing", "food", "utilities", "transportation", "education", "healthcare",
    "insurance", "debt_payment", "childcare", "entertainment", "other",
)
HOUSEHOLD_ASSET_TYPES: tuple[str, ...] = (
    "cash", "bank_account", "fixed_deposit", "investment", "real_estate", "vehicle", "retirement", "other",
)
HOUSEHOLD_LIABILITY_TYPES: tuple[str, ...] = (
    "mortgage", "personal_loan", "education_loan", "vehicle_loan", "credit_card", "other",
)


def _in_list_sql(column: str, values: tuple[str, ...]) -> str:
    """`column IN ('a', 'b', ...)` for a CHECK constraint."""
    return column + " IN (" + ", ".join("'" + value + "'" for value in values) + ")"


class HouseholdIncome(Base):
    """One income stream a household reports (Phase 33).

    `source` is deliberately free text (a human-readable label such as
    "Salary -- employer A"), while `frequency` is a controlled vocabulary,
    because a stated amount is meaningless without knowing its period. The
    amount must be strictly positive: a household with no income omits the
    record rather than storing a zero.
    """

    __tablename__ = "household_incomes"
    __table_args__ = (
        CheckConstraint(_in_list_sql("frequency", HOUSEHOLD_FINANCE_FREQUENCIES), name="ck_household_incomes_frequency"),
        CheckConstraint("amount > 0", name="ck_household_incomes_amount_positive"),
        CheckConstraint("length(btrim(source)) > 0", name="ck_household_incomes_source_not_blank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    frequency: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # Phase 35 -- free-text context the household chooses to record. Factual
    # metadata only: nothing reads it, and no calculation depends on it.
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    household: Mapped["Household"] = relationship()


class HouseholdExpense(Base):
    """One expense a household reports (Phase 33).

    `category` is a controlled vocabulary (ending in "other"); `description`
    is optional free text and stays NULL when not supplied. `is_essential` has
    no default -- whether an expense is essential is the household's own
    judgement, never something this system guesses.
    """

    __tablename__ = "household_expenses"
    __table_args__ = (
        CheckConstraint(_in_list_sql("category", HOUSEHOLD_EXPENSE_CATEGORIES), name="ck_household_expenses_category"),
        CheckConstraint(_in_list_sql("frequency", HOUSEHOLD_FINANCE_FREQUENCIES), name="ck_household_expenses_frequency"),
        CheckConstraint("amount > 0", name="ck_household_expenses_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    frequency: Mapped[str] = mapped_column(String(20))
    is_essential: Mapped[bool] = mapped_column(Boolean)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    household: Mapped["Household"] = relationship()


class HouseholdAsset(Base):
    """One asset a household reports (Phase 33).

    A manually entered, self-reported value -- NOT a market price, NOT a
    brokerage holding, and never fed to the portfolio optimizer.
    `current_value` may be `0` (a real, stated zero) but never negative.
    """

    __tablename__ = "household_assets"
    __table_args__ = (
        CheckConstraint(_in_list_sql("asset_type", HOUSEHOLD_ASSET_TYPES), name="ck_household_assets_type"),
        CheckConstraint("current_value >= 0", name="ck_household_assets_value_non_negative"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_household_assets_name_not_blank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    asset_type: Mapped[str] = mapped_column(String(30))
    current_value: Mapped[float] = mapped_column(Numeric(14, 2))
    is_liquid: Mapped[bool] = mapped_column(Boolean)
    # Phase 35 -- `name` stays the short label; `description` is optional
    # detail, matching `household_expenses.description`.
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    household: Mapped["Household"] = relationship()


class HouseholdLiability(Base):
    """One liability a household reports (Phase 33).

    `monthly_payment` is nullable on purpose: NULL means "not provided" and
    `0` means "explicitly no monthly payment" -- two different facts, kept
    apart (CLAUDE.md section 12). No debt ratio, amortization schedule or
    interest calculation exists in this phase.
    """

    __tablename__ = "household_liabilities"
    __table_args__ = (
        CheckConstraint(_in_list_sql("liability_type", HOUSEHOLD_LIABILITY_TYPES), name="ck_household_liabilities_type"),
        CheckConstraint("outstanding_amount >= 0", name="ck_household_liabilities_outstanding_non_negative"),
        CheckConstraint("monthly_payment IS NULL OR monthly_payment >= 0", name="ck_household_liabilities_payment_non_negative"),
        CheckConstraint("interest_rate IS NULL OR interest_rate >= 0", name="ck_household_liabilities_interest_non_negative"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_household_liabilities_name_not_blank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    liability_type: Mapped[str] = mapped_column(String(30))
    outstanding_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    monthly_payment: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    # Phase 35 -- recorded for completeness only. NOTHING computes with it:
    # no debt ratio, amortization schedule, payoff date or interest figure
    # exists in this project (ADR-034). `Numeric(6, 4)` matches the rate
    # convention already used by `financial_inputs`.
    interest_rate: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    household: Mapped["Household"] = relationship()


HOUSEHOLD_GOAL_TYPES: tuple[str, ...] = (
    "emergency_fund", "house", "education", "retirement", "travel", "major_purchase", "other",
)


class HouseholdGoal(Base):
    """Phase 36 -- a financial goal that belongs to a HOUSEHOLD, owned through
    `household_id` alone (no `customer_id`, exactly like the Phase 33 records).

    Deliberately separate from the individual `financial_goals` table: neither
    is ever converted into, merged with or allowed to modify the other.

    Stored FACTS only -- the household's own statement of what it is aiming for.
    Nothing derived is stored here: no inflation-adjusted target, no required
    contribution, no contribution gap, no feasibility, no probability and no
    emergency-fund requirement (ADR-035).

    Field choices mirror the existing individual goal where one exists, and
    diverge only where the project's own rules require it:

    - `target_amount > 0` and `target_date` required, as for individual goals.
    - `current_savings` reuses the individual goal's NAME, but is NULLABLE:
      the individual column defaults to 0, which predates CLAUDE.md section 12;
      here "not provided" must stay distinct from a recorded 0.
    - `goal_type` is a controlled vocabulary (individual goal types are free
      text and no canonical vocabulary exists to reuse); `name` carries the
      household's own free-text label, as Phase 33's income `source` does.
    - No `inflation_adjusted` flag and no `priority`: see ADR-035.
    """

    __tablename__ = "household_goals"
    __table_args__ = (
        CheckConstraint(_in_list_sql("goal_type", HOUSEHOLD_GOAL_TYPES), name="ck_household_goals_goal_type"),
        CheckConstraint("target_amount > 0", name="ck_household_goals_target_positive"),
        CheckConstraint("current_savings IS NULL OR current_savings >= 0", name="ck_household_goals_current_non_negative"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_household_goals_name_not_blank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    goal_type: Mapped[str] = mapped_column(String(30))
    target_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    current_savings: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    target_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    household: Mapped["Household"] = relationship()
