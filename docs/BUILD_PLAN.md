# WealthPilot AI — Build Plan

This is the project's implementation contract. It reconciles three source
documents into one authoritative plan:

- `CLAUDE.md` — stack, non-negotiable rules, backend/frontend layout
- `docs/PROJECT_PLAN.md` — data sources, model selection and comparison,
  training inventory, risks
- `docs/MASTER_PROMPT.md` — exhaustive feature checklist, database table
  list, page-by-page UI spec, testing scope, responsible-AI copy

**Document provenance and conflict resolution.** `CLAUDE.md`/`PROJECT_PLAN.md`
and `MASTER_PROMPT.md` specify two different backend architectures for the
same system (package layout, dependency file, API route style, phase count).
On 2026-09-13 this was raised explicitly and resolved by the user:
**`CLAUDE.md`/`PROJECT_PLAN.md` win on architecture.** `MASTER_PROMPT.md` is
used here only for _what_ must exist (pages, database tables, test
categories, responsible-AI copy) and has been adapted to fit the winning
architecture — never taken as the literal file layout or endpoint list.
Every place this plan departs from a literal reading of `MASTER_PROMPT.md` is
called out inline.

No implementation has started. This plan does not create backend or frontend
code, dependencies, or database migrations — that begins at Phase 0, and only
after this plan is approved.

---

## 1. Project Overview

WealthPilot AI is an educational decision-support prototype: a simulated
autonomous financial advisor that takes a customer's income, expenses,
savings, goals and existing holdings, and produces a portfolio recommendation
it can explain and defend. It is built as an M.Tech case-study project, not a
production financial product.

**Main problem being solved.** Retail investors get either generic robo-advisor
allocations with no reasoning shown, or expensive human advice. WealthPilot AI
demonstrates a middle path: deterministic financial engines (goal math,
portfolio optimization, compliance rules) do the actual computation, ML models
classify risk and detect behavioural change from real transaction data, and an
LLM (Gemini) is used strictly as a language layer to explain — never compute —
the result. The project's core methodological claim, defended throughout, is
that no number the user sees was produced by the LLM or by the frontend.

**Expected system output.** For a given customer profile, the system produces:
a risk category with confidence and SHAP explanation, a financial-health
summary, a goal funding gap and Monte-Carlo success probability, a market
regime read, a recommended portfolio allocation with a compliance verdict, and
a Gemini-generated explanation of that allocation validated against the
underlying numbers before it ever reaches the browser.

**User interaction flow.** A user creates a customer profile (including the
real MiFID II risk questionnaire, served from FAR-Trans data rather than
hard-coded), triggers an analysis run, watches the LangGraph agent pipeline
execute live over Server-Sent Events on the Agent Activity page, then reviews
the recommendation, its explanation, and can explore "what if" changes in the
Scenario Simulator — all recalculated server-side.

**Responsible-AI limitations, carried through every page and the final
report:** WealthPilot AI is an educational decision-support prototype and is
not a substitute for advice from a licensed financial professional. It does
not guarantee returns and does not execute trades, transfer funds, or perform
any autonomous financial transaction. Market data is historical, not a
forecast. FAR-Trans is European research data and does not represent the
deployment population. The Kaggle income/expense data is synthetic.

---

## 2. Complete System Architecture

```text
React + shadcn/ui  (nine views, TanStack Query, typed API client)
        ↓  HTTPS/JSON + SSE
FastAPI  (backend/wealthpilot/api — routers, schemas, dependencies, sse)
        ↓
LangGraph  (backend/wealthpilot/agents — typed state, nodes, conditional routing)
        ↓
   ┌────────────┬───────────────┬───────────────┬─────────────────┐
   ▼            ▼               ▼               ▼                 ▼
Risk Engine  Expense/       Market Engine   Goal Engine      Portfolio
(ML,         Behaviour      (ARIMA/GARCH/   (TVM formulas,   Optimizer
served)      Engine (ML)    LSTM/GRU,       Monte Carlo)     (MVO+shrinkage,
                            regime label)                     1/N, HRP)
   └────────────┴───────────────┴───────────────┴─────────────────┘
                                 ▼
                    AutoGen Strategy Debate (bounded, one node)
                                 ▼
                        Compliance Engine (YAML rules, PASS/WARN/REJECT)
                                 ▼
                    Gemini Explanation + Validation (REJECT ⇒ no explanation)
                                 ▼
                              PostgreSQL  (persistence, audit trail)
                                 ▼
                        FastAPI response / SSE event
                                 ▼
                        React (displays only; computes nothing)
```

**Layer responsibilities.**

- **React + shadcn/ui** — presentation only. Every figure shown is a field in
  an API response. No percentage, ratio or allocation arithmetic in a
  component (CLAUDE.md rule 2).
- **FastAPI** — the only thing the browser talks to. Validates requests with
  Pydantic, loads all ML/statistical artifacts once at startup, runs or
  streams the LangGraph workflow, caches results by profile hash, and is the
  single source of generated OpenAPI schema → TypeScript types.
- **LangGraph** — the workflow spine. Typed `AgentState`, deterministic node
  order, conditional edges for low-confidence risk, compliance rejection,
  emergency-fund shortfall, and significant behavioural drift.
- **Risk / Expense-Behaviour / Market engines** — trained offline in
  `training/`, serialized to `models/`, loaded once, never retrained inside a
  request.
- **Goal Engine / Portfolio Optimizer** — deterministic, not ML. Closed-form
  time-value-of-money formulas, Monte Carlo simulation, and convex
  optimization (MVO + Ledoit-Wolf shrinkage, benchmarked against 1/N and HRP).
- **AutoGen Strategy Debate** — exactly one bounded node: Portfolio Manager,
  Risk Analyst and Compliance personas debate the proposed allocation and
  return a structured verdict into LangGraph state. AutoGen is never the
  orchestrator.
- **Compliance Engine** — deterministic YAML rules producing PASS / WARN /
  REJECT. A REJECT is a hard gate: LangGraph routes around the Gemini
  explanation node entirely, and no explanation field is ever attached to a
  rejected recommendation.
- **Gemini** — language only. Receives the fully computed dictionary,
  produces prose, and every numeric claim in that prose is validated against
  the source dictionary before the response is allowed through.
- **PostgreSQL** — persistence and audit trail (`data_source` and
  `model_version` on every table that needs one), and the cache backing
  server-side result reuse by profile hash.

---

## 3. Technology Map

| Technology                      | Where Used                                                    | Purpose                                                                                              |
| ------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Python 3.11                     | `backend/`                                                    | All financial/ML/agent processing                                                                    |
| FastAPI + uvicorn               | `backend/wealthpilot/api/`                                    | REST + SSE boundary between React and the graph                                                      |
| Pydantic v2 / pydantic-settings | Backend-wide                                                  | Request/response validation, typed config                                                            |
| SQLAlchemy + Alembic            | `backend/wealthpilot/db/`                                     | ORM models, versioned migrations                                                                     |
| PostgreSQL                      | Persistence                                                   | Customers, goals, transactions, portfolios, market data, recommendations, agent logs, analysis cache |
| LangGraph                       | `backend/wealthpilot/agents/graph.py`                         | Workflow spine: state, node order, conditional routing, retry caps                                   |
| AutoGen                         | `backend/wealthpilot/agents/debate.py`                        | One bounded multi-persona strategy debate node                                                       |
| google-genai (Gemini)           | `backend/wealthpilot/agents/explanation.py`                   | Structured-output explanation and Q&A, language only                                                 |
| scikit-learn                    | `training/`, `backend/wealthpilot/core` inference             | Risk (LogReg, RF), clustering (K-Means, GMM, Ward), Isolation Forest, preprocessing pipelines        |
| XGBoost                         | `training/risk/`                                              | Risk classification, usual macro-F1 winner                                                           |
| TensorFlow                      | `training/risk/`, `training/market/`                          | MLP baseline for risk, LSTM/GRU for market returns & volatility                                      |
| statsmodels                     | `training/market/`                                            | ARIMA return benchmark                                                                               |
| arch                            | `training/market/`                                            | GARCH(1,1) volatility benchmark                                                                      |
| yfinance                        | `backend/wealthpilot/data/acquisition.py`, `training/market/` | `^IXIC`, `^NDX`, `QQQ`, bond proxy, gold proxy — OHLCV market data                                   |
| SHAP                            | `training/risk/`, served via API                              | TreeExplainer attributions for the winning risk model                                                |
| scipy                           | `backend/wealthpilot/core/optimizer.py`                       | Constrained numerical optimization (`scipy.optimize`) for box-constrained MVO; added 2026-09-13      |
| React 19 + Vite + TypeScript    | `frontend/`                                                   | Nine-view dashboard UI                                                                               |
| Tailwind CSS + shadcn/ui        | `frontend/src/components/ui`                                  | Styling and accessible UI primitives, added via CLI                                                  |
| TanStack Query                  | `frontend/src/lib/api.ts`, hooks                              | Server-state caching/dedup against the typed client                                                  |
| React Router                    | `frontend/src/App.tsx`                                        | Nine routes + persistent sidebar                                                                     |
| Recharts                        | `frontend/src/components/charts`                              | Efficient frontier, allocation donuts, SHAP waterfall, goal progress                                 |
| lucide-react                    | Frontend-wide                                                 | Iconography                                                                                          |
| openapi-typescript              | npm script                                                    | Generates `frontend/src/types/api.ts` from the live FastAPI schema — never hand-written              |

Only technologies listed in `CLAUDE.md`'s Stack section are approved. Nothing
outside this list is added without asking first.

---

## 4. Data Source Map

### FAR-Trans (primary — real risk labels)

- **Location:** `datasets/raw/FAR-Trans/` — the zip is unzipped there; this is
  the single canonical raw-data directory (top-level, sibling of `backend/`).
- **Contains:** `customer_information.csv` (multiple dated rows per customer —
  the behaviour agent's ground truth), `asset_information.csv`,
  `markets.csv`, `close_prices.csv` (close-only, EUR, no OHLCV),
  `limit_prices.csv`, `transactions.csv` (channel: Internet Banking / Phone
  Banking / Branch), `questionnaires.csv` (MiFID II **questions and answer
  options only** — no customer answers, so questionnaire score can never be a
  training feature).
- **Why used:** the only genuine, real-world supervised risk labels in the
  project. Coverage 2 Jan 2018 – 29 Nov 2022. CC-BY 4.0, National Bank of
  Greece via University of Glasgow.
- **Genuine labels kept:** `riskLevel` ∈ {Conservative, Income, Balanced,
  Aggressive}. **Labels dropped before any training:** every `Predicted_*`
  variant and `Not_Available` — they are another model's output, not ground
  truth (CLAUDE.md rule 7). Same filtering applies to `investmentCapacity`
  bands.
- **Where used:** risk classifier training (Phase 4), behaviour-change
  detection ground truth (Phase 5), and the React risk questionnaire is
  populated from `questionnaires.csv` via `GET /api/questionnaire` rather
  than hard-coded (Phase 15/17).

### Kaggle Personal Finance Dataset (secondary — income, expenses, savings)

- **Provides:** age, gender, education level, employment status, monthly
  income (USD), monthly expenses (USD), savings, debt-to-income ratio, credit
  score, savings-to-income ratio, region. Primary choice:
  `miadul/personal-finance-ml-dataset` (~32k records). Alternative if
  monthly time-series is needed for the behaviour agent:
  `khushikyad001/personal-finance-tracker-dataset`.
- **Synthetic-data limitation:** both are generated from statistical
  distributions, not real customers — this is stated in the report and in
  the UI where this data backs a figure.
- **Location:** `datasets/raw/kaggle/` — the original downloaded filename is
  kept as-is.
- **Access:** the acquisition script reads from `datasets/raw/kaggle/`; if the
  expected file is absent, it fails with a clear, actionable message naming
  that path. Never attempt to authenticate to Kaggle.
- **Where used:** synthetic profile assembly (Phase 3) — stratified pairing
  with FAR-Trans behaviour, conditioned on `investmentCapacity`, with every
  record's provenance flagged via `data_source`.

### Yahoo Finance (yfinance)

```text
Yahoo Finance
     ↓  yfinance.download()
^IXIC (NASDAQ Composite) / ^NDX (NASDAQ-100) / QQQ ETF
     + bond proxy + gold proxy (ticker availability verified at runtime)
     ↓
market_data table (OHLCV — the only source of open/high/low/volume,
since FAR-Trans close_prices.csv is close-only)
     ↓
Market Analysis Agent — ARIMA / GARCH / LSTM / GRU, walk-forward validated,
targets returns & volatility, never price levels
     ↓
Regime label (Trending / Volatile / Range-bound) → adjusts portfolio
optimizer constraint bounds, never expected returns
```

Yahoo Finance is a market-data source only; its own analyst-style figures (if
any) are never treated as model predictions.

**Not a manually supplied dataset.** Unlike FAR-Trans and Kaggle, yfinance
data is never placed in `datasets/raw/` — it is fetched live by
`backend/wealthpilot/data/acquisition.py` and its authoritative store is the
`market_data` table in PostgreSQL. The acquisition layer may keep a local
cache of raw pulls for reproducibility (e.g. under a build/cache directory
excluded from `datasets/raw/`), but that cache is never confused with, or
substituted for, PostgreSQL as the application's source of truth for market
records.

---

## 5. Database Design

PostgreSQL via SQLAlchemy models in `backend/wealthpilot/db/models.py`,
versioned with Alembic. Every table below carries `id`, `created_at`, and
`data_source` where the row's provenance can vary (FAR-Trans / Kaggle /
yfinance / user-entered / computed); tables holding a model-derived figure
also carry `model_version` (CLAUDE.md: "add `data_source` and `model_version`
columns everywhere for auditability").

| Table              | Purpose                                                      | Key columns                                                                                     | Data source                                        | Written by                         | Read by                                                                               |
| ------------------ | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- | -------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------- |
| `customers`        | Customer profile core                                        | name, age, income, employment, risk-input fields, `data_source`                                 | User-entered / Kaggle-seeded demo profiles         | `POST /api/profiles`               | Every agent node, every page                                                          |
| `financial_goals`  | One or more goals per customer                               | goal_type, target_amount, target_date, current_savings, priority                                | User-entered                                       | Profile creation/update            | Goal Analyst, Financial Health / Portfolio pages                                      |
| `transactions`     | Investment transaction history                               | transaction_date, category, amount, transaction_type, `data_source`                             | FAR-Trans `transactions.csv` (seed) / user-entered | Data ingestion (Phase 3)           | Risk Analyst (feature engineering), Financial Health page                             |
| `portfolios`       | Current and recommended holdings                             | asset, allocation, value                                                                        | Computed / user-entered current holdings           | Portfolio Manager node             | Portfolio Analysis page                                                               |
| `market_data`      | OHLCV history per ticker                                     | ticker, date, open, high, low, close, volume, `source`                                          | yfinance                                           | Market data ingestion (Phase 3)    | Market Analyst                                                                        |
| `recommendations`  | Final recommendation snapshot                                | recommendation, risk_category, portfolio_allocation, confidence, `model_version`, `data_source` | Computed                                           | Recommendation engine (Phase 14)   | AI Recommendation, Why This Recommendation pages                                      |
| `agent_logs`       | Auditable per-node execution record                          | agent_name, action, result summary, `model_version`                                             | Computed                                           | Every LangGraph node on completion | Agent Activity page (backs the SSE replay), audit                                     |
| `risk_assessments` | Risk model output per run                                    | risk_category, risk_score, confidence, class_probabilities, shap_values, `model_version`        | Computed                                           | Risk Analyst node                  | Risk Assessment page                                                                  |
| `analysis_runs`    | Server-side cache of a full graph run, keyed by profile hash | profile_hash, status, result (jsonb), started_at, completed_at                                  | Computed                                           | LangGraph run orchestrator         | `POST /api/analysis`, `GET /api/analysis/{id}`, SSE stream replay, Scenario Simulator |

`analysis_runs` is the mechanism behind CLAUDE.md's "cache graph results
server-side on a profile hash" requirement — it is not in `MASTER_PROMPT.md`'s
literal table list but is required by the winning architecture's API
conventions, so it is added here explicitly rather than invented silently
later.

---

## 6. ML Model Map

| Module    | Model                   | Type                         | Input                                                    | Output                                              | Used Where                                                              |
| --------- | ----------------------- | ---------------------------- | -------------------------------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------- |
| Risk      | Logistic Regression     | Supervised, baseline         | Engineered transaction/behaviour features                | Risk class                                          | Risk Analyst node                                                       |
| Risk      | Random Forest           | Supervised                   | Same                                                     | Risk class                                          | Risk Analyst node                                                       |
| Risk      | XGBoost                 | Supervised                   | Same                                                     | Risk class                                          | Risk Analyst node (expected winner on macro-F1)                         |
| Risk      | TensorFlow MLP          | Neural network               | Same                                                     | Risk class                                          | Risk Analyst node (expected to lose to trees — reported, not hidden)    |
| Expense   | K-Means                 | Unsupervised, primary        | Income-normalized expense shares                         | Cluster / persona                                   | Expense Analyst                                                         |
| Expense   | Gaussian Mixture        | Unsupervised, comparison     | Same                                                     | Soft cluster probability                            | Expense Analyst                                                         |
| Expense   | Agglomerative (Ward)    | Unsupervised, comparison     | Same                                                     | Cluster, dendrogram-justified k                     | Expense Analyst (report only)                                           |
| Behaviour | Rolling z-score / CUSUM | Statistical, primary         | Savings rate, expense ratio, contribution rate over time | Explainable drift statement                         | Behaviour Change Agent                                                  |
| Behaviour | Isolation Forest        | Anomaly detection, secondary | Multivariate behaviour metrics                           | Anomaly flag                                        | Behaviour Change Agent                                                  |
| Market    | Naive random walk       | Baseline                     | Returns                                                  | Return = 0 forecast                                 | Market Analyst — the bar everything else must beat                      |
| Market    | ARIMA                   | Classical linear             | Returns                                                  | Return forecast                                     | Market Analyst                                                          |
| Market    | GARCH(1,1)              | Volatility                   | Returns                                                  | Volatility forecast                                 | Market Analyst                                                          |
| Market    | LSTM                    | Deep learning                | Windowed return/volatility sequences                     | Return-direction / volatility signal → regime label | Market Analyst (LSTM point forecasts never feed the optimizer directly) |
| Market    | GRU                     | Deep learning                | Same                                                     | Same                                                | Market Analyst (cheaper LSTM comparison)                                |

No model is used for a purpose outside this table. SHAP (TreeExplainer) is
computed for the winning tree-based risk model only, since it gives exact
attributions in polynomial time — the practical reason the model family, not
just accuracy, drove model selection.

---

## 7. Deterministic Financial Engine

These calculations are **NOT performed by Gemini and NOT performed by
React.** They live in `backend/wealthpilot/core/`, are covered by unit tests
against hand-computed values, and are the only source of the numbers agents
and pages display.

- **Time-value-of-money:** `FV = PV(1+r)^n + PMT · [((1+r)^n − 1) / r]`,
  solved for `PMT` to get the required periodic contribution; the shortfall
  against current trajectory is the funding gap.
- **Inflation adjustment** applied to goal targets before solving.
- **Monte Carlo goal-success probability:** sample returns from the
  historical distribution over N paths, report the share reaching the
  target — never a single false-precision point estimate.
- **Portfolio optimization:** Mean-Variance Optimization with Ledoit-Wolf
  covariance shrinkage and per-asset-class box constraints (equity share
  bounded by risk category, single-asset cap, Nasdaq/tech concentration cap,
  minimum cash floor tied to emergency-fund status), benchmarked against 1/N
  and Hierarchical Risk Parity on out-of-sample Sharpe. If a benchmark wins,
  that is reported, not hidden.
- **Emergency-fund logic:** adequacy check gates optimization — insufficient
  liquidity short-circuits to a savings-first recommendation and defers
  normal portfolio optimization entirely.
- **Compliance rules:** YAML-defined, each with its own unit test, producing
  a hard PASS / WARN / REJECT gate.

---

## 8. Agent Map

All agents are LangGraph nodes in `backend/wealthpilot/agents/nodes.py` unless
noted. Each returns a state delta; none mutate state in place.

| Agent                    | Responsibility                                               | Input                                         | Output                                                  | Technology                            | Next node                                                                                                      |
| ------------------------ | ------------------------------------------------------------ | --------------------------------------------- | ------------------------------------------------------- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Customer Analyzer        | Load and normalize the customer profile into agent state     | `customers`, `financial_goals` rows           | Populated `AgentState`                                  | Deterministic                         | Risk Analyst                                                                                                   |
| Risk Analyst             | Classify risk category from behaviour features               | Engineered transaction features               | risk_category, risk_score, confidence, SHAP values      | Trained ML (Section 6)                | Financial Health Analyst, or Information Request if confidence below threshold                                 |
| Information Request      | Ask for more data instead of guessing on low-confidence risk | Risk Analyst output                           | Structured follow-up questions                          | Deterministic                         | Halts run pending more input                                                                                   |
| Financial Health Analyst | Expense clustering + behaviour-change detection              | Transactions, income/expenses                 | Persona, drift statement, anomaly flag                  | Trained ML (Section 6)                | Goal Analyst, or Re-profile if significant drift flagged                                                       |
| Re-profile               | Re-run risk assessment when behaviour has materially changed | Flagged drift                                 | Updated risk state                                      | Deterministic routing to Risk Analyst | Goal Analyst                                                                                                   |
| Goal Analyst             | Funding gap and success probability per goal                 | Goals, savings trajectory                     | Required contribution, funding gap, success probability | Deterministic (Section 7)             | Market Analyst                                                                                                 |
| Market Analyst           | Regime read                                                  | `market_data` history                         | Regime label (Trending/Volatile/Range-bound)            | Trained ML (Section 6)                | Portfolio Manager                                                                                              |
| Portfolio Manager        | Emergency-fund check, then optimize or defer                 | Risk category, regime, goals                  | Recommended allocation, or savings-first recommendation | Deterministic (Section 7)             | Savings-first (if EF insufficient) or Compliance Analyst                                                       |
| Savings-first            | Produce a liquidity-first recommendation, skip optimization  | Emergency-fund shortfall                      | Savings-first recommendation                            | Deterministic                         | Compliance Analyst                                                                                             |
| AutoGen Strategy Debate  | Bounded multi-persona critique of the proposed allocation    | Proposed allocation, risk, compliance context | Structured debate verdict                               | AutoGen (one node only)               | Compliance Analyst                                                                                             |
| Compliance Analyst       | Hard PASS/WARN/REJECT gate                                   | Recommendation + debate verdict               | Compliance verdict                                      | Deterministic rule engine             | Gemini Explanation if PASS/WARN; back to Recommendation with violated rule attached (capped retries) if REJECT |
| Gemini Explanation       | Natural-language explanation of a validated result           | Fully computed dict                           | Validated prose explanation                             | Gemini + schema validation            | API response                                                                                                   |

---

## 9. LangGraph Architecture

**State.** One typed `AgentState` Pydantic model (defined before any node is
written, per `PROJECT_PLAN.md` Stage 4 step 15), carrying the customer
profile, every engine's output as it accumulates, the compliance verdict, the
explanation, and retry counters.

**Nodes.** As listed in Section 8, each a pure function
`AgentState -> AgentStateDelta` wrapping a Section 6/7 component; no node
trains a model or mutates state in place.

**Conditional routing:**

- Risk confidence below threshold → **Information Request** instead of
  proceeding.
- Compliance verdict is REJECT → route back to the recommendation step with
  the violated rule attached, **capped at N retries**, never straight to
  Gemini.
- Behaviour-change agent flags significant drift → insert **Re-profile**
  before optimization.
- Emergency fund insufficient → short-circuit to **Savings-first**, skipping
  optimization entirely.

```text
Customer Analyzer
      ↓
Risk Analyst ──(low confidence)──▶ Information Request (halt, ask)
      ↓
Financial Health Analyst ──(significant drift)──▶ Re-profile ──▶ Risk Analyst
      ↓
Goal Analyst
      ↓
Market Analyst
      ↓
Portfolio Manager ──(EF insufficient)──▶ Savings-first ──┐
      ↓ (EF sufficient)                                   │
AutoGen Strategy Debate                                    │
      ↓                                                    │
Compliance Analyst ◀───────────────────────────────────────┘
      │
      ├──(REJECT, retries < N)──▶ back to Portfolio Manager with rule attached
      ├──(REJECT, retries = N)──▶ API returns REJECT verdict, no explanation
      └──(PASS/WARN)──▶ Gemini Explanation ──▶ API response
```

**Retry limits** are a fixed `N` (finalized during Phase 11) so a
persistently non-compliant recommendation terminates with a REJECT response
rather than looping.

---

## 10. AutoGen Architecture

Scoped to exactly one bounded sub-problem, per `PROJECT_PLAN.md` Part 3 —
AutoGen is not the orchestrator and never touches state outside this one node.

- **Participants:** Portfolio Manager, Risk Analyst and Compliance personas
  (AutoGen agents, distinct from the LangGraph nodes of the same name).
- **What they debate:** whether the Portfolio Manager's proposed allocation
  is defensible given the customer's risk category, market regime, and
  compliance constraints — genuine multi-perspective back-and-forth that
  would be awkward to hand-code as LangGraph nodes.
- **What they receive:** the proposed allocation, risk category, market
  regime, and the relevant compliance rules.
- **Structured result returned to LangGraph:** a verdict object (e.g.
  supported / flagged concerns with rationale / recommended adjustment
  within bounds), which becomes part of `AgentState` and feeds the
  Compliance Analyst node.
- **Why not fold this into LangGraph nodes:** expressing genuine argument
  and rebuttal as a fixed node sequence means hand-coding turn-taking that
  AutoGen already provides; why not let AutoGen orchestrate everything:
  it has no first-class typed state machine, checkpointing, or conditional
  routing, which LangGraph provides natively.

---

## 11. Gemini Architecture

**Gemini CAN:** explain validated financial results, summarize
recommendations, answer educational financial questions, explain risk,
portfolio allocation, and goals — grounded in financial terminology,
risk-profile definitions, portfolio concepts, goal-planning concepts,
project policies and compliance rules provided as context, plus the
validated model outputs for the current run.

**Gemini CANNOT:** calculate financial values, change a portfolio
allocation, override compliance, invent market data, guarantee returns,
execute trades, or transfer money.

```text
Fully computed dict (risk_category, risk_score, allocations, goal figures,
compliance verdict — already PASS/WARN, never REJECT)
      ↓
Gemini structured-output call (financial-domain grounding + policies)
      ↓
Response validated: every numeric field checked against the source dict
      ↓
   ┌── match ─────────────────────▶ explanation attached to API response
   └── mismatch / invented number / guaranteed-return claim / compliance
       violation ─▶ FAIL ─▶ reject / regenerate / fallback to a templated
       explanation — never an invalid recommendation reaches the user
```

A REJECT compliance verdict never reaches this node at all — the LangGraph
routing in Section 9 removes that path structurally, not just by convention.

---

## 12. FastAPI API Map

Workflow/SSE-oriented, per `CLAUDE.md`'s API conventions — synchronous
endpoints return complete computed results rather than requiring the client
to assemble partial payloads from many small per-resource endpoints. This
supersedes `MASTER_PROMPT.md` §20's REST-nested-per-customer endpoint list,
which the architecture decision placed as subordinate to `CLAUDE.md`.

| Method | URL                           | Purpose                                                                            | Input                                                       | Output                                                                                      | Backend module                                | DB interaction                                                                                    | Auth                   |
| ------ | ----------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---------------------- |
| GET    | `/api/health`                 | Liveness/readiness                                                                 | —                                                           | status, loaded model versions                                                               | `api/routers/health.py`                       | None                                                                                              | None (local prototype) |
| GET    | `/api/questionnaire`          | MiFID II risk questions for the React form                                         | —                                                           | Questions + answer options (from `questionnaires.csv`)                                      | `api/routers/profiles.py`                     | Read-only, seeded at startup                                                                      | None                   |
| POST   | `/api/profiles`               | Create and persist a customer profile                                              | Demographics, income/expenses, goals, questionnaire answers | Created `customer_id`                                                                       | `api/routers/profiles.py`                     | Writes `customers`, `financial_goals`                                                             | None                   |
| GET    | `/api/profiles/{profile_id}`  | Fetch a profile                                                                    | —                                                           | Profile detail                                                                              | `api/routers/profiles.py`                     | Reads `customers`, `financial_goals`                                                              | None                   |
| POST   | `/api/analysis`               | Run the full LangGraph workflow; returns cached result if the profile hash matches | `profile_id`, optional overrides                            | Complete `AnalysisResult` (risk, health, goals, market, portfolio, compliance, explanation) | `api/routers/analysis.py` → `agents/graph.py` | Reads profile tables, writes `risk_assessments`, `recommendations`, `agent_logs`, `analysis_runs` | None                   |
| GET    | `/api/analysis/{analysis_id}` | Fetch a previously computed result                                                 | —                                                           | Same `AnalysisResult` shape                                                                 | `api/routers/analysis.py`                     | Reads `analysis_runs`                                                                             | None                   |
| GET    | `/api/analysis/stream`        | SSE progress while a run executes                                                  | `profile_id` (query)                                        | Stream of `{node, status, duration, summary, model_version}` events, never chain-of-thought | `api/sse.py`                                  | Reads `agent_logs` as nodes complete                                                              | None                   |
| POST   | `/api/scenarios/compare`      | Recompute two parameter sets and diff them                                         | Two parameter-set payloads                                  | Two `AnalysisResult`-shaped summaries, cached                                               | `api/routers/scenarios.py`                    | Reads/writes `analysis_runs`                                                                      | None                   |
| POST   | `/api/qa`                     | Gemini educational Q&A through the approved knowledge layer                        | Question, optional `analysis_id` for context                | Answer text                                                                                 | `api/routers/qa.py` → `agents/explanation.py` | Read-only                                                                                         | None                   |

Every response carries `model_version` and `data_source` per `CLAUDE.md`.
Errors return RFC 7807 problem details, never a bare 500. No endpoint accepts
credentials or performs authentication in this prototype — this is stated
explicitly in Section 20.

---

## 13. React Frontend Map

All nine pages read from the same `AnalysisResult` object cached by TanStack
Query under the current `analysis_id`, plus their own narrow endpoints where
listed. No page performs financial arithmetic — if a figure isn't in the
payload, the API gains a field rather than the component computing one.

| Page                       | Purpose                                 | API endpoint(s)                                | Data displayed                                                                                                                                                          | Charts/components                      | shadcn/ui                       |
| -------------------------- | --------------------------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ------------------------------- |
| 1. Home / Dashboard        | At-a-glance financial health            | `GET /api/analysis/{id}`                       | Net financial health, risk category, savings rate, emergency-fund status, goal progress, portfolio allocation, market regime, recommendation summary, compliance status | Recharts donut + progress bars         | Card, Badge, Progress, Alert    |
| 2. Customer Profile        | Create/edit profile, take questionnaire | `POST /api/profiles`, `GET /api/questionnaire` | Form fields, MiFID II questions                                                                                                                                         | —                                      | Form, Input, Select, Tabs       |
| 3. Financial Health        | Expense persona, behaviour drift        | `GET /api/analysis/{id}`                       | Cluster persona, drift statement, anomaly flag                                                                                                                          | Recharts bar/line                      | Card, Badge, Tooltip            |
| 4. Risk Assessment         | Risk model output                       | `GET /api/analysis/{id}`                       | Risk category, score, confidence, class probabilities, SHAP waterfall, confusion matrix, model performance                                                              | Recharts SHAP waterfall                | Card, Table, Tabs               |
| 5. Portfolio Analysis      | Allocation detail                       | `GET /api/analysis/{id}`                       | Current vs recommended allocation, efficient frontier, Sharpe, drawdown, turnover, 1/N & HRP benchmark comparison                                                       | Recharts pie/donut + frontier scatter  | Card, Table, Tabs               |
| 6. AI Recommendation       | The recommendation itself               | `GET /api/analysis/{id}`                       | Recommendation, risk considerations, goal impact, market context, compliance status, disclaimer                                                                         | —                                      | Card, Alert, Badge              |
| 7. Why This Recommendation | Explainability                          | `GET /api/analysis/{id}`                       | SHAP factors, expense behaviour, goal probability, optimization factors, regime, compliance checks                                                                      | Recharts SHAP + goal probability gauge | Card, Accordion, Tooltip        |
| 8. Agent Activity          | Live pipeline transparency              | `GET /api/analysis/stream` (SSE)               | Node name, status, timestamp, duration, concise result summary per LangGraph node                                                                                       | Timeline component                     | Card, Badge, Progress, Skeleton |
| 9. Scenario Simulator      | What-if comparison                      | `POST /api/scenarios/compare`                  | Two parameter sets side by side: goal probability, funding gap, portfolio metrics                                                                                       | Recharts comparison bars               | Card, Tabs, Slider, Input       |

A persistent sidebar (React Router) shows phase/section progress and links
all nine views.

---

## 14. shadcn/ui Component Map

Added via `npx shadcn@latest add <name>` — never hand-written:

Card, Button, Input, Select, Dialog, Tabs, Table, Badge, Alert, Progress,
Sidebar, Tooltip, Dropdown Menu, Sheet, Form, Skeleton, Accordion, Slider.

No custom replacement is built for anything the CLI already provides.

---

## 15. Frontend/Backend Data Flow

```text
React component
      ↓  useQuery / useMutation
TanStack Query  (caching, dedup, keyed by analysis_id / profile_id)
      ↓  typed client (src/lib/api.ts, built on generated types)
FastAPI  (Pydantic request validation)
      ↓
LangGraph run (or PostgreSQL read on cache hit)
      ↓
Financial/ML Engines (Sections 6–7)
      ↓
PostgreSQL  (persist + cache by profile hash)
      ↓
FastAPI response  (Pydantic response model)
      ↓
TanStack Query cache update
      ↓
React renders the returned fields — computes nothing
```

`src/types/api.ts` is generated from the live OpenAPI schema by an
`openapi-typescript` npm script; a hand-written interface mirroring a
Pydantic model is treated as a bug, per `CLAUDE.md` rule 3.

---

## 16. Agent Activity SSE Flow

```text
LangGraph node completes
      ↓
Progress event: {node, status, duration, summary, model_version}
      ↓
FastAPI SSE endpoint — GET /api/analysis/stream
      ↓
React SSE hook (frontend/src/hooks/useAgentStream.ts)
      ↓
Agent Activity page — renders nodes live, in order, as they complete
```

Node name, status, duration, a concise human-readable summary, and model
version are sent for every node. Chain-of-thought is **never** sent — this is
enforced at the point the event is constructed in the backend, not filtered
client-side.

---

## 17. Complete Project File Structure

```text
wealthpilot/                         [repo root — this directory]
├── CLAUDE.md                        Phase 0 (already created)
├── README.md                        Phase 0
├── .env.example                     Phase 0
├── .gitignore                       Phase 0
├── Makefile                         Phase 0 — install/dev/migrate/test/typegen
├── docs/
│   ├── PROJECT_PLAN.md              already created
│   ├── MASTER_PROMPT.md             already created
│   └── BUILD_PLAN.md                this file
├── reports/                          Phase 19 — evaluation & case study
├── backend/
│   ├── pyproject.toml                Phase 0
│   └── wealthpilot/
│       ├── __init__.py               Phase 0
│       ├── config/                   Phase 0 — settings, logging
│       ├── db/                       Phase 1 — models, session, Alembic env
│       ├── data/                     Phase 2–3 — acquisition, quality, preprocessing CODE only, no data files
│       ├── core/                     Phase 7–9 — goal math, optimizer, compliance
│       ├── agents/                   Phase 10–14 — state, nodes, graph, debate, explanation, recommendation engine
│       └── api/                      Phase 15 — routers, schemas, dependencies, sse
├── training/                         Phase 4–6 — one script per model family, top-level, NOT under backend/
│   ├── risk/
│   ├── expense/
│   ├── behaviour/
│   └── market/
├── models/                           Phase 4–6 output — top-level, NOT under backend/ or datasets/
│   ├── risk/                         serialized artifacts (.pkl / .keras) — gitignored
│   ├── expense/
│   ├── behaviour/
│   ├── market/
│   └── metrics.json                  every metric from every run — VERSIONED, not gitignored
├── datasets/                         Phase 2 — top-level, the single canonical raw-data location
│   └── raw/                          downloaded/original data, gitignored (.gitkeep tracked)
│       ├── FAR-Trans/                customer_information.csv, asset_information.csv, markets.csv,
│       │                             close_prices.csv, limit_prices.csv, transactions.csv, questionnaires.csv
│       └── kaggle/                   personal-finance-ml-dataset — original filename kept as-is
├── config/
│   └── compliance_rules.yaml         Phase 9
├── tests/                            Every phase — top-level, mirrors backend/wealthpilot/ + training/ structure
└── frontend/
    ├── package.json                  Phase 0
    ├── vite.config.ts                Phase 0
    ├── tailwind.config.ts            Phase 0
    └── src/
        ├── components/
        │   ├── ui/                   Phase 0/16 — shadcn primitives, CLI-added
        │   ├── charts/                Phase 17–18
        │   ├── dashboard/             Phase 17
        │   ├── portfolio/             Phase 17
        │   ├── risk/                  Phase 17
        │   └── agents/                Phase 18
        ├── pages/                     Phase 17–18 — nine views
        ├── lib/api.ts                 Phase 16 — typed client
        ├── types/api.ts               GENERATED — Phase 15 script, never hand-edited
        ├── hooks/                     Phase 16–18 (incl. useAgentStream.ts)
        ├── routes/                    Phase 16
        └── App.tsx                    Phase 16
```

---

## 18. Phase-by-Phase Implementation Plan

Phase map per `CLAUDE.md`'s revised phase table (this supersedes
`MASTER_PROMPT.md` §34's 17-phase list, per the architecture decision).

### Phase 0 — Foundation, both workspaces

- **Objective:** scaffolding only, no business logic.
- **Builds:** backend/frontend layout with `__init__.py`s, `backend/pyproject.toml`
  pinned to the approved stack (including `scipy`), the top-level
  `training/{risk,expense,behaviour,market}/`, `models/{risk,expense,
behaviour,market}/`, `datasets/raw/{FAR-Trans,kaggle}/` (empty, `.gitkeep`
  tracked), `config/compliance_rules.yaml` placeholder, and `tests/`
  directories exactly as laid out in Section 17 — none of these nested under
  `backend/` — Vite React-TS frontend with Tailwind + shadcn/ui initialised
  and 3–4 base primitives added via CLI, `pydantic-settings` config +
  structured logging, FastAPI app exposing only `GET /api/health` with CORS
  for the Vite dev origin, `openapi-typescript` npm script wired against the
  running backend, `.env.example`, `.gitignore` (covering `datasets/raw/*`
  but keeping `.gitkeep`, and `models/**/*.pkl` / `.keras` but keeping
  `models/metrics.json`), Makefile/scripts (install, dev backend, dev
  frontend, migrate, test, generate types), README stub.
- **Depends on:** nothing (this BUILD_PLAN).
- **Tests:** health endpoint returns 200; type-gen script produces valid TS
  against the stub schema.
- **Manual verification:** `uvicorn` boots, `vite dev` boots, CORS allows the
  frontend origin.
- **Completion criteria:** both dev servers run; no page content, no models,
  no agents exist yet.

### Phase 1 — PostgreSQL and persistence

- **Objective:** schema for Section 5's tables via SQLAlchemy + Alembic.
- **Builds:** `db/models.py`, initial Alembic migration, session dependency.
- **Depends on:** Phase 0 config module.
- **Tests:** migration applies cleanly to an empty `TEST_DATABASE_URL`; model
  round-trip tests per table.
- **Manual verification:** `alembic upgrade head` succeeds locally.
- **Completion criteria:** all Section 5 tables exist with `data_source`/
  `model_version` columns where specified.

### Phase 2 — Data acquisition and quality

- **Objective:** acquire FAR-Trans and Kaggle data, produce a data-quality
  report.
- **Builds:** `data/acquisition.py` (FAR-Trans download+unzip, Kaggle local-path
  read with a clear failure if absent), a nulls/duplicates/outliers/date-gap/
  currency-consistency report. Yahoo Finance / yfinance acquisition and all
  market-data handling are **not** part of Phase 2 — that is Phase 6's
  responsibility in full (clarified 2026-09-13; Phase 2 was implemented and
  approved without it).
- **Depends on:** Phase 1 (raw data lands independent of DB, but ingestion
  targets it).
- **Tests:** acquisition script is idempotent; quality report generation is
  covered by a test on a fixture subset.
- **Manual verification:** row counts and null counts checked against
  `PROJECT_PLAN.md` Part 0 and logged, not copied verbatim.
- **Completion criteria:** `datasets/raw/` populated (gitignored) and quality
  report produced.

### Phase 3 — Preprocessing, features, synthetic assembly, plus DB ingestion

- **Objective:** sklearn `Pipeline` preprocessing, feature engineering per
  `PROJECT_PLAN.md` §2.1, synthetic profile assembly (FAR-Trans × Kaggle,
  stratified on `investmentCapacity`), and ingestion into PostgreSQL.
- **Builds:** `data/preprocessing.py`, `data/synthetic.py`, ingestion scripts
  writing `customers`, `transactions`, `financial_goals`, `market_data`.
- **Depends on:** Phases 1–2.
- **Tests:** pipeline fit/transform round-trip; synthetic assembly provenance
  flag present on every synthetic row.
- **Manual verification:** genuine-label count after filtering `Predicted_*`/
  `Not_Available` checked — flagged as a risk in Section 21 if too small.
- **Completion criteria:** DB populated from real data; no model trained yet.

### Phase 4 — Risk classification, four models

- **Objective:** train and compare Logistic Regression, Random Forest,
  XGBoost, MLP per `PROJECT_PLAN.md` §2.1 / §6.1.
- **Builds:** `training/risk/*.py`, `models/risk/*.pkl|.keras`,
  `models/metrics.json` risk section, SHAP TreeExplainer on the winner.
- **Depends on:** Phase 3 features.
- **Tests:** stratified 5-fold CV reproducibility with fixed seed; metrics
  recorded for all four models, not just the winner.
- **Manual verification:** macro-F1 led reporting, confusion matrix reviewed
  per class, predicted-vs-real class distribution compared.
- **Completion criteria:** all four models serialized; metrics.json updated.

### Phase 5 — Expense segmentation and behaviour detection

- **Objective:** K-Means/GMM/Ward clustering on income-normalized expense
  shares; rolling z-score/CUSUM + Isolation Forest behaviour detection.
- **Builds:** `training/expense/*.py`, `training/behaviour/*.py`,
  `models/expense/*.pkl`, `models/behaviour/iforest.pkl` + `thresholds.json`.
- **Depends on:** Phase 3.
- **Tests:** silhouette/BIC selection logic tested on fixture data; threshold
  calibration documented with evidence.
- **Manual verification:** cluster personas profiled qualitatively; cluster
  count confirmed data-driven, not forced to four.
- **Completion criteria:** models serialized; metrics.json updated.

### Phase 6 — Market models and regime classifier

- **Objective:** naive/ARIMA/GARCH/LSTM/GRU across the five assets, walk-forward
  validated, targeting returns and volatility only.
- **Builds:** `training/market/*.py`, `models/market/{ticker}/*`.
- **Depends on:** Phase 2 yfinance ingestion.
- **Tests:** no shuffled split — walk-forward split logic itself unit tested;
  RMSE/MAE/directional accuracy/Diebold-Mariano computed against the naive
  baseline.
- **Manual verification:** LSTM result reported honestly even if it loses to
  the random walk.
- **Completion criteria:** 25 fits complete and serialized; regime label
  derivation defined.

### Phase 7 — Goal mathematics and Monte Carlo

- **Objective:** deterministic TVM formulas and Monte Carlo goal-success
  probability.
- **Builds:** `core/goals.py`.
- **Depends on:** Phase 1 schema (goal fields).
- **Tests:** unit tests against hand-computed/spreadsheet-verified values —
  this is the phase where an off-by-one is otherwise invisible.
- **Manual verification:** none beyond tests; this module is exact by
  construction.
- **Completion criteria:** goal engine covered by passing unit tests.

### Phase 8 — Portfolio optimization and backtest

- **Objective:** MVO + Ledoit-Wolf shrinkage + box constraints; 1/N and HRP
  benchmarks; rolling out-of-sample backtest.
- **Builds:** `core/optimizer.py`, `core/backtest.py`.
- **Depends on:** Phase 6 (regime bounds), Phase 7 (goal-linked constraints).
- **Tests:** constraint satisfaction tests (equity bound by risk category,
  single-asset cap, concentration cap, cash floor); backtest metrics
  (annualized return, volatility, Sharpe, max drawdown, turnover).
- **Manual verification:** if 1/N or HRP wins out-of-sample, reported as a
  finding, not suppressed.
- **Completion criteria:** efficient frontier generation works end to end.

### Phase 9 — Compliance engine

- **Objective:** deterministic YAML-driven PASS/WARN/REJECT gate.
- **Builds:** `config/compliance_rules.yaml`, `core/compliance.py`.
- **Depends on:** Phase 8 (what it evaluates).
- **Tests:** one unit test per rule, plus adversarial/bypass-attempt cases.
- **Manual verification:** confirmed a REJECT cannot be bypassed by any
  input combination tried.
- **Completion criteria:** every rule independently tested and passing.

### Phase 10 — Agent state and nodes

- **Objective:** typed `AgentState`, then nodes wrapping Phases 4–9,
  including Information Request, Re-profile, Savings-first.
- **Builds:** `agents/state.py`, `agents/nodes.py`.
- **Depends on:** Phases 4–9 (wraps all of them).
- **Tests:** each node tested as a pure function returning a state delta.
- **Manual verification:** no node mutates state in place.
- **Completion criteria:** all Section 8 nodes implemented and unit tested in
  isolation (no graph wiring yet).

### Phase 11 — LangGraph assembly and conditional routing

- **Objective:** wire Section 9's graph, including retry caps.
- **Builds:** `agents/graph.py`.
- **Depends on:** Phase 10.
- **Tests:** each conditional edge exercised (low confidence, REJECT retry
  loop terminating at N, drift-triggered re-profile, EF-insufficient
  short-circuit).
- **Manual verification:** full graph run on a synthetic profile completes.
- **Completion criteria:** graph runs end to end without the debate/Gemini
  nodes (stubbed) since those are later phases.

### Phase 12 — AutoGen strategy debate

- **Objective:** the one bounded debate node from Section 10.
- **Builds:** `agents/debate.py`.
- **Depends on:** Phase 11 (slots into the graph).
- **Tests:** structured verdict schema validated; debate scope confirmed not
  to leak into orchestration.
- **Manual verification:** debate transcript reviewed for genuineness, not
  just a rubber stamp.
- **Completion criteria:** debate node returns a structured verdict consumed
  by the Compliance Analyst node.

### Phase 13 — Gemini explanation and validation

- **Objective:** Section 11's explanation node with strict schema validation.
- **Builds:** `agents/explanation.py`.
- **Depends on:** Phase 12 (post-compliance in the graph).
- **Tests:** every numeric field in a Gemini response validated against the
  source dict; REJECT-path test confirms this node is never reached on
  REJECT; adversarial prompt tests (Gemini asked to invent/guarantee/override
  a number) confirm FAIL → fallback.
- **Manual verification:** explanation reads naturally and matches the
  numbers exactly.
- **Completion criteria:** no invalid explanation can reach the API response.

### Phase 14 — Recommendation engine (four-layer hybrid), as its own phase

- **Objective:** assemble the final recommendation from the deterministic
  layers already built — risk-conditioned strategic allocation (Phase 4/8),
  goal-driven tactical adjustment (Phase 7), market-regime bound adjustment
  (Phase 6/8), and the compliance-gated final output (Phase 9) — into one
  coherent `Recommendation` object.
- **Open item — resolve before starting this phase:** neither source
  document specifies the exact combination rule for how these four layers
  interact numerically (e.g. precedence when goal-driven and regime-driven
  adjustments disagree). Per `CLAUDE.md` ("if the spec is silent... ask;
  never invent financial logic"), this must be confirmed with the user at
  the start of Phase 14 rather than decided here.
- **Depends on:** Phases 4, 6, 7, 8, 9.
- **Tests:** recommendation composition tested against known inputs once the
  combination rule above is confirmed.
- **Manual verification:** recommendation traceable back to which layer
  produced which part of the allocation.
- **Completion criteria:** `Recommendation` object populated correctly for
  representative personas, pending the open item above.

### Phase 15 — FastAPI layer, OpenAPI schema, SSE streaming, generated TS types

- **Objective:** Section 12's full API map.
- **Builds:** `api/routers/*`, `api/sse.py`, `api/schemas.py` (reusing
  existing Pydantic state models — no parallel schema set), lifespan handler
  loading all serialized models once, npm script regenerating
  `frontend/src/types/api.ts`.
- **Depends on:** Phase 14 (what it exposes), Phase 1 (persistence).
- **Tests:** every endpoint tested; explicit test that a REJECT verdict never
  returns an `explanation` field.
- **Manual verification:** type-gen script produces valid types against the
  live schema.
- **Completion criteria:** API map fully implemented and tested; no React
  work in this phase.

### Phase 16 — React shell

- **Objective:** routing, layout, shadcn theme, typed API client — no page
  content beyond placeholders.
- **Builds:** React Router with nine routes, persistent sidebar with phase
  progress, shadcn theme (a considered palette, not default slate),
  `lib/api.ts` on generated types, `useAgentStream` SSE hook, loading
  skeletons, error boundary.
- **Depends on:** Phase 15 (generated types must exist).
- **Tests:** each page's placeholder proves its data hook resolves against
  the live backend.
- **Manual verification:** navigating all nine routes works with real data
  flowing to at least a placeholder.
- **Completion criteria:** shell complete; no page has real content yet.

### Phase 17 — Views 1–5: Home, Profile, Financial Health, Risk, Portfolio

- **Objective:** Section 13's first five pages.
- **Builds:** page components, `components/charts`, `components/dashboard`,
  `components/portfolio`, `components/risk`. Risk questionnaire served from
  `GET /api/questionnaire`, not hard-coded. SHAP waterfall computed
  server-side, sent as data.
- **Depends on:** Phase 16.
- **Tests:** component rendering against mocked API responses; no
  computation found in any component (grep-level check as part of review).
- **Manual verification:** every displayed figure traced to an API field.
- **Completion criteria:** five pages fully functional against the live
  backend.

### Phase 18 — Views 6–9: Recommendation, Why This, Agent Activity, Scenario Simulator

- **Objective:** Section 13's remaining four pages.
- **Builds:** page components, `components/agents` (Agent Activity timeline
  consuming SSE live). Recommendation view renders nothing from Gemini
  unless compliance is PASS. Scenario Simulator compares two parameter sets
  via `POST /api/scenarios/compare`.
- **Depends on:** Phase 17 shared components, Phase 15 SSE endpoint.
- **Tests:** REJECT-path UI test (no explanation rendered); SSE hook
  reconnect/error handling tested.
- **Manual verification:** run three contrasting personas plus an
  insufficient-emergency-fund case end to end; report what is observed.
- **Completion criteria:** all nine pages complete and demoable end to end.

### Phase 19 — Evaluation and final case study

- **Objective:** model comparison tables (including losers), end-to-end
  persona walkthroughs, limitations section, Word-format report.
- **Builds:** `reports/`.
- **Depends on:** everything above.
- **Tests:** N/A — this phase documents results, it does not add code.
- **Manual verification:** every report table traced back to
  `models/metrics.json`, nothing retyped by hand.
- **Completion criteria:** report complete and defensible in the viva.

---

## 19. Testing Strategy

- **Unit tests:** goal engine (against hand-computed values), portfolio
  optimizer (constraint satisfaction), compliance rules (one per rule plus
  adversarial cases), risk/market preprocessing pipelines, feature
  engineering functions.
- **ML evaluation:** stratified CV for risk models (macro-F1, per-class
  recall, confusion matrix, calibration, fit time); silhouette/BIC for
  clustering; walk-forward RMSE/MAE/directional accuracy/Diebold-Mariano for
  market models — all four model families trained and evaluated, not just
  the winner.
- **Integration tests:** database round-trips, FastAPI endpoint contracts,
  full LangGraph run on fixture profiles, Gemini validation (including
  adversarial "invent a number" prompts), the full recommendation pipeline
  end to end.
- **API tests:** every endpoint in Section 12; explicit REJECT ⇒ no
  explanation test.
- **Frontend tests:** page rendering against mocked API responses, form
  validation, chart rendering, recommendation display gated on compliance
  status, loading/error/empty states, SSE hook behaviour.
- **End-to-end:** three contrasting personas plus an insufficient-
  emergency-fund case, run through the full stack (Phase 18 completion
  criterion).

---

## 20. Security and Responsible AI

- **Secrets:** `GEMINI_API_KEY`, `DATABASE_URL`, `TEST_DATABASE_URL` live in
  `.env`, never in Git (`.gitignore` covers `.env` from Phase 0). No secrets
  are ever placed in React — the frontend talks only to FastAPI, and FastAPI
  alone talks to Gemini.
- **Authentication:** none in this prototype — this is stated explicitly in
  the API map (Section 12) rather than left implicit, since it is a
  deliberate scope decision for an educational local prototype, not an
  oversight.
- **No trade execution, no fund transfer, no brokerage integration** — ever
  (`CLAUDE.md` rule 10).
- **No guaranteed returns, fake performance claims, autonomous trading, or
  unsupported financial claims** anywhere in generated prose — enforced by
  the Gemini validation step (Section 11).
- **Disclaimer**, shown consistently across the UI and the report: _"WealthPilot
  AI is an educational decision-support prototype and is not a substitute for
  advice from a licensed financial professional. The system does not
  guarantee returns and does not execute trades, transfer funds, or provide
  autonomous financial transactions."_
- **Dataset limitations** stated wherever the figure they back is shown:
  FAR-Trans is European research data not representative of the deployment
  population; Kaggle income/expense data is synthetic.

---

## 21. Known Risks and Mitigations

| Risk                                                                                 | Mitigation                                                                                                                                                 |
| ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Genuine-label subset too small after filtering `Predicted_*`/`Not_Available`         | Checked in Phase 2/3 before designing around it; if too small, `Predicted_*` rows used as a clearly-labelled auxiliary set with the limitation documented. |
| LSTM/GRU fail to beat the naive random-walk baseline                                 | Expected; reported as a finding in Phase 6/19, not hidden by silently switching to price-level RMSE.                                                       |
| Mean-variance produces extreme/single-asset allocations                              | Ledoit-Wolf shrinkage plus box constraints built in from Phase 8 day one, not patched later.                                                               |
| Gemini invents or alters a number                                                    | Structured output plus per-field validation against the computed dict (Phase 13); FAIL path rejects/regenerates/falls back.                                |
| Every UI interaction re-runs the whole graph                                         | Models loaded once at FastAPI startup; results cached server-side by profile hash (`analysis_runs`, Phase 15); TanStack Query caches/dedupes client-side.  |
| Frontend and backend types drift                                                     | TypeScript generated from the live OpenAPI schema (Phase 15/16 npm script); hand-written interfaces are treated as a bug.                                  |
| Financial logic leaks into React                                                     | Rule enforced by review at Phase 17/18 completion — every displayed figure must trace to an API field.                                                     |
| Compliance becomes advisory rather than binding                                      | REJECT is a structural LangGraph routing decision (Section 9), not a flag checked by convention — the explanation node is unreachable on REJECT.           |
| **The four-layer recommendation combination rule is undefined (new, this document)** | Flagged explicitly in Phase 14; must be confirmed with the user before that phase starts rather than invented.                                             |
| Class imbalance in risk labels                                                       | Class weights as the default; if SMOTE is used, it runs inside the CV fold and both variants are reported (Phase 4).                                       |
| Time-series leakage                                                                  | Walk-forward expanding-window splits with a fixed embargo gap, never a shuffled split (Phase 6).                                                           |
| SSE connection failures                                                              | `useAgentStream` hook includes reconnect/error handling, tested in Phase 18.                                                                               |
| Long-running analysis requests                                                       | SSE for the live view; synchronous `POST /api/analysis` still returns a complete result once done, backed by the same cache.                               |

---

## 22. Final End-to-End Flow

```text
Customer Input  (profile + MiFID II questionnaire, Phase 17)
      ↓
Financial Profile  (Customer Analyzer, Phase 10)
      ↓
Risk Classification  (Risk Analyst — 4-model comparison, Phase 4/10)
      ↓
Expense Analysis  (Financial Health Analyst — clustering, Phase 5/10)
      ↓
Behaviour Detection  (same node — z-score/CUSUM + Isolation Forest, Phase 5/10)
      ↓
Financial Goals  (Goal Analyst — TVM + Monte Carlo, Phase 7/10)
      ↓
Market Analysis  (Market Analyst — ARIMA/GARCH/LSTM/GRU → regime, Phase 6/10)
      ↓
Portfolio Optimization  (Portfolio Manager — MVO+shrinkage vs 1/N/HRP,
                         emergency-fund gate, Phase 8/10)
      ↓
AutoGen Strategy Debate  (bounded critique, Phase 12)
      ↓
Compliance  (PASS/WARN/REJECT hard gate, Phase 9)
      ↓
Gemini Explanation  (language only, validated, Phase 13)
      ↓
Validation  (every numeric field checked against the source dict, Phase 13)
      ↓
FastAPI  (complete AnalysisResult, cached by profile hash, Phase 15)
      ↓
React + shadcn/ui  (nine views, computes nothing, Phase 16–18)
      ↓
Final Recommendation, shown with its explanation, compliance status,
and disclaimer — or, on REJECT, shown with the compliance verdict and
no explanation at all.
```

---

## Step 4 — Plan Validation

Checked against `CLAUDE.md`, `docs/PROJECT_PLAN.md`, and `docs/MASTER_PROMPT.md`:

- **Contradictions:** the one substantive contradiction (backend layout, API
  style, phase count) was resolved by explicit user decision on 2026-09-13
  and is documented at the top of this file and wherever it affects a
  section (Sections 12, 17, 18).
- **Missing components:** none found against `MASTER_PROMPT.md`'s checklist —
  every page (§4), database table (§5, plus `analysis_runs` and
  `risk_assessments` added for reasons stated in Section 5), ML model (§8–11),
  and testing category (§31) has a home in this plan.
- **Incorrect technology placement:** none found; Section 3 matches
  `CLAUDE.md`'s approved stack exactly, with no additions.
- **Missing APIs:** `MASTER_PROMPT.md` §20's per-customer REST list is fully
  covered by the workflow-oriented endpoints in Section 12 — every piece of
  data those endpoints would have served is present in `AnalysisResult` or a
  narrow supporting endpoint (`/api/questionnaire`, `/api/scenarios/compare`,
  `/api/qa`).
- **Missing datasets:** FAR-Trans, Kaggle, and yfinance all mapped in
  Section 4 with their exact files/tickers and filtering rules.
- **Missing ML models:** all eleven models across risk/expense/behaviour/
  market are in Section 6, matching `PROJECT_PLAN.md` §6 exactly (4 + 3 + 2 +
  5-per-asset).
- **Missing frontend pages / shadcn components:** all nine pages (Section 13)
  and the full shadcn component list (Section 14) are present.
- **Missing testing:** Section 19 covers unit, ML evaluation, integration,
  API, frontend, and end-to-end — matching `MASTER_PROMPT.md` §31 categories.
- **Missing security requirements:** Section 20 covers secrets, no-auth
  scope statement, the ten `CLAUDE.md` non-negotiable rules, and the
  responsible-AI disclaimer.
- **One open item remains by design, not oversight:** the exact numeric
  combination rule for Phase 14's "four-layer hybrid" recommendation engine
  is not specified in any source document. It is flagged in Sections 18 and
  21 to be resolved with the user immediately before Phase 14 begins, per
  `CLAUDE.md`'s instruction to ask rather than invent financial logic.

No further changes identified. This plan is ready for review.
