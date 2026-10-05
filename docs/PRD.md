# WealthPilot AI — Product Requirements Document

## 1. Document Information

**Product**: WealthPilot AI
**Full title**: Agentic AI-Based Autonomous Financial Advisor for
Personalized Wealth Management
**Type**: M.Tech educational/research prototype
**Purpose**: Define product requirements, capabilities, boundaries, user
experience, and acceptance criteria, using the actual current
implementation as the source of truth for what is live versus planned.
**Documentation status**: Reflects the system as of the completion of
Phase 28 (`reports/phase28_financial_input_savings_first_report.md`).
See `docs/MEMORY.md` for anything more recent.

## 2. Product Overview

WealthPilot AI is a personalized financial decision-support system that
combines a customer's profile, questionnaire responses, financial goals,
and (as of Phase 28) directly-supplied financial inputs with
machine-learning risk classification, behavioural-drift detection,
goal-funding mathematics, market-regime analysis, portfolio construction,
and a binding compliance gate — producing a recommendation that an AI
explanation layer restates in plain language. Deterministic backend
calculation is authoritative throughout: the LLM (Gemini) never computes
a number, and the frontend never recalculates one — both only present
results the backend already produced.

## 3. Product Vision

To provide an intelligent, personalized, explainable financial
decision-support system that combines customer information, financial
behaviour, risk assessment, goals, market conditions, portfolio
strategies, and compliance constraints into a transparent recommendation
workflow. This is not a guarantee of financial outcomes and does not
replace a licensed financial adviser.

## 4. Problem Statement

Financial decisions depend on many interacting factors — risk tolerance,
current financial health, behavioural patterns, concrete goals, and
prevailing market conditions — that are difficult for an individual to
weigh consistently on their own. Generic, one-size-fits-all guidance
ignores this. At the same time, an opaque or "black-box" AI-generated
recommendation reduces trust and cannot be safely acted on: a
recommendation must be traceable to the actual computation behind it, and
must be prevented from reaching a user when required safety/suitability
conditions are not met. WealthPilot AI addresses the combination of these
two problems — personalization and explainable, compliance-gated safety —
in one workflow, rather than as disconnected tools.

## 5. Proposed Solution

```
Customer
  -> Profile
  -> Questionnaire
  -> Financial Goals
  -> Financial Inputs (expenses, liquid assets, contribution/return/inflation assumptions)
  -> Risk Assessment (ML)
  -> Financial Health (behaviour-drift/anomaly detection)
  -> Goal Analysis (funding math + Monte Carlo feasibility)
  -> Market Analysis (regime context)
  -> Savings-First check (emergency-fund adequacy)
  -> Portfolio Construction (MVO / HRP / 1-N) OR Savings-First deferral
  -> Compliance validation (binding)
  -> Recommendation
  -> AI Explanation
```

This is the conceptual product flow. Every stage above is implemented and
live-wired into the running application as of Phase 28 — see
`docs/ARCHITECTURE.md` §10 for the exact routing and
`docs/MEMORY.md` for current verification status.

## 6. Target Users

**Primary**: individuals seeking personalized financial decision support;
users who want to understand their risk profile and financial health;
users who want to evaluate whether their financial goals are on track;
users who want investment guidance they can actually understand the
reasoning behind.

**Secondary**: researchers, students, project reviewers, and academic
evaluators assessing the system as an M.Tech case study.

WealthPilot AI is not intended for regulated professional financial
advisory use, and does not claim to be.

## 7. User Goals

A user should be able to: create or access a customer profile; complete
the risk questionnaire; enter financial goals; enter financial inputs
(expenses, liquid assets, contribution/return/inflation assumptions); view
their risk assessment; understand their financial health (behavioural
signals, where available); evaluate goal feasibility; view market
context; understand the recommended portfolio strategy and why it was
chosen; understand why a recommendation was blocked, if it was; compare
strategies via the Scenario Simulator; and watch analysis progress live
via the Agent Activity view.

## 8. Product Goals

**Goal 1 — Risk Prediction**: Identify a customer's risk category
(Conservative, Income, Balanced, Aggressive) using a trained
machine-learning classifier and the customer's available transaction
history.

**Goal 2 — Financial Analysis**: Analyze financial health (behavioural
drift/anomaly signals), goal funding and feasibility, and emergency-fund
adequacy wherever the required inputs are available.

**Goal 3 — Investment Recommendation**: Select an appropriate strategy
based strictly on the precedence Compliance > Savings-first > Risk > Goal
> Market.

**Goal 4 — Explainability**: Restate every computed result in
understandable prose, always traceable back to the number it explains.

**Goal 5 — Safety**: Prevent invalid, unsupported, non-compliant, or
fabricated financial output from ever reaching the user.

**Goal 6 — Personalization**: Use the specific customer's own supplied
information rather than a generic, one-size-fits-all recommendation.

## 9. Product Principles

1. Deterministic financial calculations are authoritative.
2. Missing data is never fabricated — distinguish unknown/unavailable
   from zero.
3. Compliance is binding; nothing downstream can override a REJECT.
4. Risk, goal, and market logic remain explainable and traceable.
5. AI explains already-computed results; it does not invent them.
6. The frontend displays backend results; it does not recalculate them.
7. Customer data remains isolated per customer.
8. Demo data is synthetic identity paired with real pipeline output.
9. Recommendations are transparent about which layer decided the outcome.
10. The system distinguishes "unavailable" from "zero" everywhere.
11. No trade execution, no fund transfer, no brokerage integration.
12. Human decision-making remains central — this is decision *support*.

## 10. Core Product Capabilities

### 14.1 Customer Profile
Name, age, income, employment status, customer type, investment
capacity. Created via account sign-up or the demo mechanism; viewable and
partially editable (financial inputs) on the Customer Profile page.

### 14.2 Questionnaire
A real, multi-section MiFID-II-style questionnaire (25 questions across 5
sections), sourced from the approved FAR-Trans questionnaire data.
Answers are persisted per customer. The questionnaire does not compute a
risk score itself — see §17.

### 14.3 Financial Health
Behavioural-drift and anomaly signals from a trained Isolation Forest +
rolling z-score model, computed from the customer's linked real
transaction history. Expense persona is a separate, structurally
unavailable concept for this population — see §18/§20.

### 14.4 Risk Assessment
ML-based classification into Conservative / Income / Balanced /
Aggressive, with confidence and full class-probability breakdown.

### 14.5 Expense Segmentation
A Kaggle-population expense-clustering model, entirely separate from the
FAR-Trans risk/behaviour population — never linked to a specific FAR-Trans
customer's result.

### 14.6 Behaviour Detection
Trading-intensity and asset-mix pattern analysis over a monthly panel,
flagging drift and anomalies.

### 14.7 Goal Analysis
Target amount, target date, current savings, priority; required periodic
contribution, inflation-adjusted target, contribution gap, and Monte
Carlo-based feasibility (Feasible / At Risk / Not Feasible), computed once
financial-input assumptions (contribution amount, expected return,
expected inflation) are supplied.

### 14.8 Market Analysis
Regime classification (Trending / Range-bound / Volatile) for a 5
-instrument universe, refreshed by an offline training pipeline, read
live from a pre-computed snapshot.

### 14.9 Portfolio Construction
One of MVO, HRP, or 1/N, selected by risk category, subject to compliance
-validated weight bounds — reached only once the emergency fund is
confirmed sufficient.

### 14.10 Compliance
A binding, fail-closed gate evaluating five rules against the proposed
allocation or savings-first proposal; REJECT blocks all downstream
output.

### 14.11 Recommendation
The final selected outcome — an approved allocation, an approved
savings-first deferral, or a compliance rejection — with a stated
rationale citing which precedence layer decided it.

### 14.12 AI Explanation
Gemini-generated (or templated-fallback) prose explaining the risk,
financial-health, goal, portfolio, market, and compliance results already
computed — never a new calculation.

### 14.13 Agent Activity
A live, streamed view of each analysis stage as it executes, with a
human-readable summary per stage — never internal reasoning or a prompt.

### 14.14 Scenario Comparison
Re-runs the real analysis pipeline for the same customer under a
different portfolio-strategy parameter and summarizes both real results
side by side.

### 14.15 Analytics Graphs
Charts that make the existing results easier to read: the risk-class
probability distribution, required-vs-current emergency fund, a goal's
target vs inflation-adjusted target, the approved portfolio allocation, a
two-scenario return/volatility/Sharpe comparison, and a step-by-step view
of the analysis pipeline as it streams. Every chart plots a value the
backend already computed, sits beside a table or text with the same
values, shows an unavailable state (never zero) when the backend returned
nothing, and none ranks or recommends anything. No efficient-frontier or
risk/return chart exists because the API does not expose frontier data.

### 14.16 Household and Family Members
A first-class **household** that customers can belong to, with family-member
association: a household has a name and members, each member is an existing
customer with a controlled relationship (self, spouse, parent, child, sibling,
other) and role (primary, member, dependent). The customer who creates a
household is its one `self`/`primary` member; only the primary can add or
remove members; the primary can never be removed; a customer belongs to at most
one household. **Phase 32 delivers household identity and membership only** —
and a household never changes any individual analysis. Membership is not
account access.

### 14.17 Household Financial Records
A household can record its own **income, expenses, assets and liabilities**
(Phase 33). Each is an independent, self-reported record owned by the household
rather than by any one member: an income has a free-text source, an amount and a
frequency; an expense adds a category, an optional description and an explicit
essential/non-essential judgement; an asset has a name, a type, a current value
and whether it is liquid; a liability has a name, a type, an outstanding amount
and an optional monthly payment. Any member of the household may read the
records; only the primary member may add, edit or delete them.

**Phase 33 is storage only** — it computes nothing from these records. They do not feed `POST /api/analysis`: every individual
customer's risk classification, goal feasibility, emergency-fund evaluation,
portfolio and compliance result is exactly what it was before any household
financial data existed. "Not provided" is kept distinct from zero throughout
(`docs/DECISIONS.md` ADR-032).

A household can also annotate those records (Phase 35): an optional note on
any record, an optional description on an asset or liability, and an optional
interest rate on a liability. These are recorded for the household's own
reference — the interest rate in particular is never used to compute a
repayment schedule, payoff date, interest amount or debt ratio.

### 14.17a Household Goals
A household can record its own goals (Phase 36) — an emergency fund, a home,
education, retirement, travel, a major purchase or other — each with a name, a
target amount and date, what it has already set aside (optional; unrecorded is
not zero), notes, and whether it is currently active. Household goals are
separate from each member's individual goals and never affect them or any
individual analysis. They are recorded, not evaluated: no projection, required
contribution or feasibility is calculated, because the household's return,
inflation and contribution assumptions are not recorded. Beside the goals, the
household's *calculated* emergency-fund requirement from the financial summary
is shown for reference; an emergency-fund goal's own target never changes it.

### 14.18 Household Financial Summary
A household can see a **factual, read-only summary** of what it has recorded
(Phase 34): its recurring monthly income and expenses (monthly amounts as
recorded, yearly counted as one twelfth per month, one-time amounts kept
separate and never treated as recurring), its essential and non-essential
expenses, its total and liquid assets, its outstanding liabilities and recorded
monthly liability payments, its monthly cash flow, its net position (assets less
liabilities), and its emergency-fund position against the same six-months-of-
essential-expenses rule the individual assessment uses. Each area also states
whether anything is recorded at all.

**It reports; it does not advise.** There is no household savings rate, debt
ratio, score, rating, ranking or percentage-complete metric, no household goal
feasibility or Monte Carlo, no household risk profile, no household portfolio
and no household recommendation — and the summary still does not feed
`POST /api/analysis`, so no individual customer's result changes because of it.
Anything not recorded stays "not provided" rather than becoming zero: a
household that has recorded no liquid assets has an *unknown* emergency-fund
position, while one that has recorded a liquid account worth zero has a known,
insufficient one. Household goals, a household risk view and household-level
advice remain future scope (§40) (`docs/DECISIONS.md` ADR-033).

## 11. User Journey

1. User opens WealthPilot AI and signs in (or uses the demo account).
2. The system resolves the account's associated customer automatically —
   no manual profile-id entry exists.
3. User views their Dashboard, summarizing overall status.
4. User views/edits their Customer Profile, including goals and financial
   inputs.
5. User views Risk Assessment — a real model output, not derived from the
   questionnaire.
6. User starts analysis via Agent Activity and watches it run live.
7. User views Financial Health, Goals (with real feasibility once
   financial inputs are supplied), Market, and Portfolio.
8. User views the Recommendation and its full compliance breakdown.
9. User views Why This Recommendation for a plain-language explanation.
10. User may compare strategies via Scenario Simulator.
11. A new user can create a profile end-to-end (Login → Create Profile →
    Questionnaire → Goals → Dashboard), with every step genuinely
    persisted.

If a step's underlying data is not yet supplied (e.g. financial inputs
never entered), the corresponding page honestly shows an "unavailable"
state with the reason — never a guess.

## 12. Customer Profile

Supported fields: `name`, `age`, `income`, `employment_status`,
`customer_type`, `investment_capacity`. Risk category is never a
user-entered profile field — it is always the ML classifier's own output
(§15). No other profile field exists; none is invented for this document.

## 13. Questionnaire

25 real questions across 5 sections, sourced live from the approved
questionnaire data (never hard-coded). Answers persist per customer and
are re-submittable (upsert, not append). The questionnaire does not
compute or override the ML risk classification — there is no scoring
algorithm that converts questionnaire answers into a risk category or any
other financial number anywhere in this system.

## 14. Financial Health Analysis

Reports: behaviour-drift flag, isolation-forest anomaly flag, and expense
persona (structurally unavailable for every FAR-Trans-linked customer,
with the reason stated). "Unavailable" is shown when the customer's
linked history has too few months of activity or no linkage exists —
never guessed or defaulted.

## 15. Risk Assessment

Classifies into one of four categories: **Conservative, Income, Balanced,
Aggressive** (no other category exists). Reports confidence and, when
available, the full class-probability table. Model evaluation metrics
(from the project's own verified training run) are documented in
`reports/phase4_risk_classification_report.md` — cited there as model
evaluation results, never as a guarantee of future accuracy.

## 16. Expense Segmentation

Based on the approved Kaggle synthetic personal-finance dataset, entirely
separate from FAR-Trans. FAR-Trans itself contains no income, expense, or
savings fields — expense segmentation is never applied to, or inferred
for, a specific FAR-Trans-linked customer's own transaction data. No
linkage between the two datasets exists or is invented.

## 17. Behaviour Detection

Uses the customer's real, linked transaction history to compute a
monthly activity panel (trade counts, asset mix, buy/sell balance),
flagging statistically significant drift (rolling z-score) and
multivariate anomalies (Isolation Forest). This is separate from, and
does not require, income/expense/savings data.

## 18. Goal Analysis

Each goal: target amount, target date, current savings, priority. Once
financial-input assumptions are supplied: required periodic contribution,
inflation-adjusted target, contribution gap, and a Monte Carlo-based
success probability bucketed into **Feasible, At Risk, Not Feasible**.
Emergency-fund adequacy is a related but distinct concept, evaluated
separately (§21). No tax or withdrawal-planning functionality exists.
Goal analysis is fully live-wired into the main analysis pipeline as of
Phase 28 — see `docs/MEMORY.md` for verification.

## 19. Market Analysis

Market universe: NASDAQ Composite (^IXIC) and NASDAQ-100 (^NDX) as regime
-context indices; QQQ, AGG, and GLD as the investable universe. Supported
regimes: **Trending, Range-bound, Volatile**. Market analysis provides
regime context for portfolio construction; it is not, and does not claim
to be, a reliable predictor of future prices.

## 20. Portfolio Construction

Three strategies only: **MVO** (mean-variance optimization,
risk-adjusted, box-constrained — selected for Aggressive risk), **HRP**
(Hierarchical Risk Parity — Conservative/Income), **1/N** (equal-weight
benchmark — Balanced). No other strategy exists or is planned. Subject to
compliance validation (§21) and reached only when the customer's
emergency fund is confirmed sufficient. Past/backtested figures are never
presented as promised future performance.

## 21. Compliance

A deterministic, binding gate evaluating five rules: portfolio weights
sum to one, no negative (short) weights, QQQ weight within its
risk-appropriate band, no single asset exceeds the 70% cap, and emergency
-fund adequacy versus a proposed normal allocation. A rule whose required
data is missing is treated as triggered (fail-closed), not skipped. A
REJECT decision blocks the recommendation and the AI explanation
entirely — no override exists anywhere in the system, for any user,
demo or real.

## 22. Recommendation Engine

Combines the compliance decision, savings-first requirement, risk
category, goal feasibility signal, and market regime into one final
outcome, following the fixed precedence **Compliance > Savings-first >
Risk > Goal > Market**. The result states which strategy was selected (or
that a savings-first deferral applies, or that the proposal was
rejected) and a plain-language rationale citing the deciding factor.

## 23. AI Explanation

Restates the already-computed risk, financial-health, goal, portfolio,
market, and compliance results in prose, plus a standard educational
-prototype disclaimer. Only runs for an approved result. Falls back to a
templated, non-generative restatement (clearly distinguishable via a
`validation_passed` flag) if the generative call fails or its output
cannot be validated against the source numbers — never a fabricated
explanation.

## 24. Agent Activity

A live, streamed trace of each analysis stage — node name, status,
duration, and a short human-readable summary — as the real backend
computation executes. Contains no reasoning trace, prompt, or transcript
of any kind; the underlying data shape has no field for one.

## 25. Scenario Comparison

Lets a user compare two portfolio-strategy parameters for the same
customer side by side. Each side is a real, independently-computed
analysis result (not a client-side "what-if" calculation) — both sides
honestly show "unavailable" together when the underlying data does not
support a comparison, never a fabricated difference.

## 26. Authentication and Customer Association

Prototype authentication only: a client-side credential check with one
supported demo credential and a local Create-User flow, no backend
session or token. Every successful authentication deterministically
resolves exactly one associated customer before the user reaches any
page — never a manual "enter a customer id" step. No in-app control lets
an authenticated user switch to a different customer's data. This is a
disclosed prototype limitation, not production-grade authentication — see
`docs/SECURITY.md`.

## 27. Demo Experience

The demo account resolves to the most complete real demonstration
available in the current environment — a synthetic identity whose risk
-relevant history is linked to one real, anonymized FAR-Trans customer,
so risk, behaviour, and (as of Phase 28) approved-recommendation results
are all genuine, live-computed outputs. Other preserved demo personas
illustrate the savings-first, compliance-rejected, and
information-required states; each is reachable via the backend's own API
explorer when not the one currently resolved. No demo result is ever
hand-inserted into the database.

## 28. System Statuses

An analysis run's overall status is one of: **approved** (compliance
PASS/WARN; may include a normal allocation or a savings-first
deferral), **rejected** (compliance REJECT — no recommendation, no
explanation), **pending_information** (risk confidence too low or
unavailable — nothing downstream runs), **failed** (an unexpected
processing error — a structural safety fallback, not a normal outcome).

## 29. Data Sources

**FAR-Trans**: real, anonymized European investment-platform data —
customer information, asset information, market/price history,
transactions, and MiFID-II-style questionnaires. Used for risk
classification and behaviour-drift detection. Contains no income,
expense, or savings fields, and no personally identifying information in
its transactional data.
**Kaggle personal-finance dataset**: synthetic data used for expense
-persona clustering, entirely separate from the FAR-Trans population.
**Market data**: OHLCV history via yfinance for the investable universe
and regime-context indices.
All raw data is immutable and read-only to the application — see
`docs/DECISIONS.md` ADR-023.

## 30. Functional Requirements

- The system MUST classify a linked customer's risk category using the
  trained model and report confidence.
- The system MUST NOT compute a risk category, portfolio weight,
  compliance decision, or goal feasibility figure in the frontend or in
  Gemini.
- The system MUST evaluate compliance on every analysis run that reaches
  the compliance stage, with no bypass.
- The system MUST persist customer-entered goals, questionnaire answers,
  and financial inputs, scoped to that customer only.
- The system MUST distinguish "not yet provided" from "zero" for every
  optional financial input.
- The system MUST stream analysis progress without exposing reasoning
  content.
- The system MUST resolve an authenticated session's customer
  automatically, without a manual selection step.
- The system MUST NOT expose one customer's data through a request scoped
  to a different customer's id.

## 31. Non-Functional Requirements

- **Reproducibility**: identical inputs produce identical outputs
  (`random_state=42` throughout).
- **Auditability**: every computed value carries its model version and
  data source.
- **Traceability**: every AI explanation sentence is traceable to an
  already-computed value.
- **Fail-safety**: missing data or an unexpected error degrades to an
  honest "unavailable"/"failed" state, never a guessed result.
- **Type safety**: no `any` in TypeScript; full type hints in Python;
  frontend API types are generated, never hand-written.
- **No production-grade availability/scaling claims**: this is a
  prototype, evaluated for correctness and demonstrability, not load.

## 32. User Interface Requirements

Every API-dependent page/section handles loading, empty, unavailable
(with a stated reason), error, and success states. The frontend uses
shadcn/ui components exclusively as its primitive layer. No page computes
a financial figure; every number shown is read directly from an API
response. Provenance (model version, data source) is visible wherever a
model-derived figure is shown. See `docs/DESIGN.md` for the full visual
system.

## 33. Security Requirements

No secret (API key, database credential, token) is ever committed,
logged, or returned in an API response. No chain-of-thought, prompt, or
LLM/agent transcript is ever exposed to the frontend. Customer data is
isolated per customer id at the query level. Prototype authentication
limitations are disclosed, not hidden. See `docs/SECURITY.md` for the
complete treatment.

## 34. Data and Privacy Requirements

No real personally identifying information is used or displayed — demo
personas are synthetic identities; FAR-Trans transactional data used for
linkage carries no PII (verified in `reports/phase2_data_quality_report.md`).
Raw datasets are immutable and never modified by the running application.

## 35. AI/LLM Requirements

Gemini receives only a fully-computed result dict and a structured
-output schema; it must never be asked to calculate a number, select a
strategy, or override compliance. Every structured response is validated
against the source dict; any deviation triggers the templated fallback,
never a silently-accepted fabrication. AutoGen debate personas critique
an already-computed, already-compliant proposal and are validated the
same way.

## 36. Financial Safety Requirements

No trade execution, no fund transfer, no brokerage integration exists or
is planned. Compliance REJECT unconditionally blocks the recommendation
and explanation. No portfolio strategy outside MVO/HRP/1-N exists. Every
disclaimer states plainly that this is an educational prototype, not
licensed financial advice.

## 37. Out of Scope

Production-grade authentication (JWT/OAuth, server sessions, password
hashing, role/admin management); trade execution or brokerage
integration; tax or estate planning; multi-currency support; a
customer-switching UI for an authenticated user (household membership, added in
Phase 32, is not account switching); household financial **advice** — Phase 34
reports a household's aggregates, cash flow, net position and emergency-fund
position, but there is no household savings rate, debt ratio, score, goal
feasibility, risk profile, portfolio or recommendation, and no household figure
affects any individual analysis; real-time market data
streaming; mobile native apps. None of these exist in the current
implementation and none is planned within this project's stated scope.

## 38. Current Implementation Status

Implemented and live-wired: customer profile, questionnaire persistence,
goal persistence, financial-input persistence (Phase 28), risk
classification, financial-health/behaviour detection, goal funding math
and feasibility, market regime context, savings-first mechanism,
portfolio construction (MVO/HRP/1-N), compliance gate, recommendation
engine, AI explanation (with fallback), Agent Activity SSE stream,
Scenario Simulator, household identity and family-member association
(Phase 32), the household's own financial records (Phase 33) and their
read-only factual summary including a household emergency-fund position
(Phase 34 — reporting only, feeding no advice and no individual analysis),
prototype
authentication with automatic customer association, and a verified
synthetic demo population covering all four
terminal analysis states. See `docs/MEMORY.md` for the authoritative,
continuously-updated current-state record and any item that has changed
since this PRD was last verified against source.

## 39. Known Limitations

Expense persona is permanently unavailable for FAR-Trans-linked
customers (structural, by dataset design, not a defect). Prototype
authentication has no server session and is devtools-editable client
state (disclosed). No customer-switching UI exists by design — a
non-default demo persona is reachable only via the backend's API
explorer. No browser-based visual/interactive testing has been performed
in this project's development environment to date; verification has
relied on type-checking, build, lint, and backend test suites plus
source-level review. Goal feasibility is a real Monte Carlo result at the
supplied assumptions and can legitimately be "At Risk" or "Not
Feasible" (for example a short deadline against a much larger required
contribution). Goal feasibility is bootstrapped from a blended
historical-return series compounded to the goal's contribution
frequency; the choice of that series is a documented judgment call
(`docs/DECISIONS.md` ADR-026/ADR-027), not a directly-specified
requirement.

## 40. Future Scope

Possible, not committed: household financial **advice** — household goal
feasibility and Monte Carlo, a household risk profile, a household portfolio, a
household recommendation and compliance over it, plus derived ratios such as a
savings rate or debt-to-income. Phases 32-34 deliberately stop short of all of
it: Phase 34 reports the household's own figures and feeds none of them into
any advice path, and each of those additions would first need its methodology
specified and then implemented as deterministic `core/` logic with its own ADR;
membership invitation/consent and primary-ownership transfer; per-record
visibility control within a household; a genuine production authentication system;
richer scenario-comparison parameters (varying financial inputs, not just
portfolio strategy); a customer-facing way to inspect other demo personas
without the API explorer; additional compliance rules if a later
methodology review calls for them. None of this is scheduled or
implied to be imminent.

## 41. Success Criteria

The system correctly classifies risk for a linked customer with a
documented, verified confidence level; correctly computes goal funding
math and feasibility once inputs are supplied; correctly enforces
compliance with no bypass under any tested condition; correctly restricts
every financial calculation to the backend; correctly isolates customer
data; and correctly reaches all four terminal analysis states
(approved, savings-first-approved, rejected, pending-information) via
real, unmodified pipeline execution for at least one real or
synthetic customer each — verified live, not assumed
(`reports/phase28_financial_input_savings_first_report.md` §14).

## 42. Product Acceptance Criteria

- [ ] Every financial number displayed anywhere in the frontend is
  traceable to a specific backend API field.
- [ ] No compliance REJECT ever reaches a recommendation or explanation.
- [ ] No customer's data is readable or writable through another
  customer's request.
- [ ] Every analysis result state (approved / rejected /
  pending_information / failed) is reachable through the real,
  unmodified pipeline for at least one verified customer.
- [ ] The demo population's results are all read from real API
  responses, never hand-inserted.
- [ ] `npx tsc -b`, `npm run build`, `npx oxlint`, and the backend
  `pytest` suite all pass at the time this PRD is read as "current."
- [ ] `docs/MEMORY.md` reflects the same implementation status this PRD
  claims; any drift is called out, not hidden.
