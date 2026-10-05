> **Note (2026-09-13):** This document was supplied as a second, independent
> specification alongside `CLAUDE.md` and `docs/PROJECT_PLAN.md`. It conflicts
> with those two on backend package layout (`backend/app/` vs
> `backend/wealthpilot/`), dependency file (`requirements.txt` vs
> `pyproject.toml`), API route style (REST-nested per-customer vs
> workflow/SSE-oriented), and phase numbering (17 phases vs 20). The user
> resolved this explicitly: **CLAUDE.md and PROJECT_PLAN.md are authoritative
> on architecture.** This file is kept as the exhaustive feature/requirements
> checklist, page-by-page UI spec, and phase-completion-report template — use
> it for *what* must exist and be tested, not for *how the code is laid out*.
> The reconciled, authoritative phase plan is `docs/BUILD_PLAN.md`.
>
> **Dataset location (added 2026-09-13):** the canonical raw-data directory is
> `datasets/raw/`, split into `datasets/raw/FAR-Trans/` and
> `datasets/raw/kaggle/`, as a top-level sibling of `backend/` — not
> `backend/data/`, not inside `backend/wealthpilot/`, and not the bare
> `data/` folder shown in this document's own §30 structure below. `training/`
> and `models/` (§7, §30) are likewise top-level siblings of `backend/`, per
> `CLAUDE.md`.

# WEALTHPILOT AI — MASTER IMPLEMENTATION PROMPT

## Project Title

**WealthPilot AI: Agentic AI-Based Autonomous Financial Advisor for Personalized Wealth Management**

---

# 1. PROJECT OBJECTIVE

Build a complete full-stack AI-powered financial advisory prototype that:

* Analyzes customer income, expenses, savings, investments and financial goals.
* Classifies the customer's risk profile.
* Segments spending behaviour.
* Detects unusual changes in financial behaviour.
* Analyzes market conditions.
* Uses statistical and ML models for market forecasting.
* Calculates financial-goal success probabilities.
* Generates optimized portfolio allocations.
* Applies deterministic compliance and suitability rules.
* Uses Agentic AI to coordinate financial analysis.
* Uses Gemini as a **financial-domain explanation and interaction layer**.
* Provides explainable recommendations through a modern React web application.

### Critical architecture rule

**LLM/Gemini must NEVER calculate, modify, invent or override financial numbers.**

All financial values must come from:

* Deterministic Python calculations
* ML models
* Statistical models
* Portfolio optimization
* Monte Carlo simulation
* Database values
* Verified market data

Gemini can only explain validated outputs and communicate them naturally to the user.

---

# 2. TECHNOLOGY STACK

## Backend

* Python 3.11
* FastAPI
* LangGraph
* AutoGen
* Gemini API
* Pydantic
* SQLAlchemy
* Alembic
* PostgreSQL

## Machine Learning

* scikit-learn
* XGBoost
* TensorFlow
* SHAP
* pandas
* numpy

## Financial / Statistical Models

* statsmodels
* arch
* yfinance
* scipy
* Monte Carlo simulation
* Mean-Variance Optimization
* Ledoit-Wolf covariance shrinkage

## Market Data

Use:

**Yahoo Finance through `yfinance`**

Primary market instruments:

* NASDAQ Composite — `^IXIC`
* NASDAQ-100 — `^NDX`
* QQQ ETF — `QQQ`
* Appropriate bond proxy
* Appropriate gold proxy

Yahoo Finance is a **market-data source only**.

Do not treat Yahoo Finance predictions as model predictions.

---

# 3. FRONTEND TECHNOLOGY

The frontend MUST NOT use Streamlit.

Use:

* React
* TypeScript
* Vite
* Tailwind CSS
* shadcn/ui
* React Router
* TanStack Query
* Recharts
* Lucide React icons

### Frontend architecture

```text
React + TypeScript
        ↓
React Router
        ↓
TanStack Query
        ↓
FastAPI REST API
        ↓
LangGraph Agent Workflow
        ↓
ML / Financial Engines
        ↓
PostgreSQL
```

### UI requirements

Use shadcn/ui components for:

* Cards
* Buttons
* Tables
* Dialogs
* Tabs
* Selects
* Forms
* Alerts
* Progress indicators
* Badges
* Tooltips
* Dropdown menus
* Sidebars
* Navigation
* Sheets
* Charts where appropriate

The UI should look like a **professional financial analytics dashboard**, not a basic student CRUD application.

Use:

* Responsive layout
* Sidebar navigation
* Dashboard cards
* Data tables
* Interactive charts
* Risk indicators
* Portfolio allocation charts
* Goal progress indicators
* Explainability panels
* Agent activity timeline
* Loading states
* Error states
* Empty states

Avoid excessive boxes and unnecessary decoration.

---

# 4. APPLICATION PAGES

Create the following React pages:

1. Home / Dashboard
2. Customer Profile
3. Financial Health
4. Risk Assessment
5. Portfolio Analysis
6. AI Recommendation
7. Why This Recommendation?
8. Agent Activity
9. Scenario Simulator

---

# 5. DATABASE

Use PostgreSQL with SQLAlchemy and Alembic.

Required tables:

### customers

* id
* name
* age
* income
* employment information
* risk-related inputs
* data_source
* created_at

### financial_goals

* id
* customer_id
* goal_type
* target_amount
* target_date
* current_savings
* priority
* created_at

### transactions

* id
* customer_id
* transaction_date
* category
* amount
* transaction_type
* data_source
* created_at

### portfolios

* id
* customer_id
* asset
* allocation
* value
* created_at

### market_data

* id
* ticker
* date
* open
* high
* low
* close
* volume
* source
* created_at

### recommendations

* id
* customer_id
* recommendation
* risk_category
* portfolio_allocation
* confidence
* model_version
* data_source
* created_at

### agent_logs

* id
* customer_id
* agent_name
* action
* result
* model_version
* created_at

---

# 6. DATA SOURCES

Use:

### Financial behaviour data

FAR-Trans research dataset for risk classification.

Genuine risk labels:

* Conservative
* Income
* Balanced
* Aggressive

Do NOT use:

* Predicted_*
* Not_Available

as genuine supervised training labels.

### Personal finance data

Use a suitable Kaggle dataset containing:

* Income
* Expenses
* Savings
* Financial goals
* Spending information

### Market data

Use Yahoo Finance via `yfinance`.

At minimum include:

```text
^IXIC
^NDX
QQQ
```

plus suitable bond and gold proxies.

---

# 7. TRAINING ARCHITECTURE

All ML training must follow:

```text
Raw Data
   ↓
Data Quality
   ↓
Preprocessing
   ↓
Feature Engineering
   ↓
Train
   ↓
Validate
   ↓
Evaluate
   ↓
Serialize
   ↓
Inference
```

Training code belongs inside:

```text
training/
```

Serialized models belong inside:

```text
models/
```

The production application MUST NOT retrain models.

---

# 8. RISK CLASSIFICATION

Train and compare:

* Logistic Regression
* Random Forest
* XGBoost
* TensorFlow MLP

Use:

* Stratified 5-fold cross-validation
* Class weighting where appropriate
* Macro-F1
* Per-class recall
* Confusion matrix
* Calibration
* Training/fit time

Use SHAP for the best tree-based model.

The final system should output:

```json
{
  "risk_category": "Balanced",
  "risk_score": 62,
  "confidence": 0.87
}
```

---

# 9. EXPENSE SEGMENTATION

Primary model:

**K-Means**

Compare against:

* Gaussian Mixture Model
* Ward Hierarchical Clustering

Cluster based on:

* Income-normalized expense proportions
* Savings behaviour
* Investment contribution behaviour

Do not cluster solely using raw expense amounts.

Use:

* Silhouette score
* Elbow method
* BIC where applicable
* Dendrogram for hierarchical clustering

---

# 10. BEHAVIOUR CHANGE DETECTION

Monitor:

* Savings rate
* Expense ratio
* Investment contribution rate

Primary:

* Rolling z-score
* CUSUM

Secondary:

* Isolation Forest

Detect:

* Increasing expenses
* Falling savings
* Reduced investment contributions
* Unusual financial behaviour

---

# 11. MARKET ANALYSIS

Market data comes from:

**Yahoo Finance → `yfinance`**

Example:

```python
import yfinance as yf

nasdaq = yf.download("^IXIC")
nasdaq100 = yf.download("^NDX")
qqq = yf.download("QQQ")
```

Analyze:

* Historical returns
* Volatility
* Volume
* Trends
* Market regimes

Models:

* Naive return baseline
* ARIMA
* GARCH(1,1)
* LSTM
* GRU

### Evaluation

Use:

* Walk-forward expanding-window validation
* Embargo
* RMSE
* MAE
* Directional accuracy
* Diebold-Mariano test

Do NOT randomly shuffle time-series data.

The final market output should be a regime:

```text
Trending
Volatile
Range-bound
```

Do not directly feed an LSTM price prediction into the portfolio optimizer.

---

# 12. FINANCIAL GOAL ENGINE

Use deterministic financial formulas.

Calculate:

* Future value
* Present value
* Required periodic contribution
* Inflation-adjusted target
* Goal funding gap
* Goal success probability

Use Monte Carlo simulation for goal probability.

Example output:

```json
{
  "goal": "House Purchase",
  "target_amount": 5000000,
  "current_savings": 1000000,
  "required_monthly_saving": 35000,
  "success_probability": 0.78
}
```

Gemini must not calculate these values.

---

# 13. PORTFOLIO OPTIMIZATION

Implement:

### Primary

Mean-Variance Optimization

with:

* Ledoit-Wolf covariance shrinkage
* Asset allocation constraints
* Box constraints

Compare against:

* 1/N portfolio
* Hierarchical Risk Parity

Evaluate using:

* Annualized return
* Volatility
* Sharpe ratio
* Maximum drawdown
* Turnover

Generate efficient frontier.

If the benchmark performs better, report it honestly.

---

# 14. EMERGENCY FUND LOGIC

Before portfolio optimization:

Check emergency-fund adequacy.

If insufficient:

```text
Emergency Fund Insufficient
        ↓
Savings-First Recommendation
        ↓
Normal Portfolio Optimization Deferred
```

Do not recommend aggressive investment allocation when essential liquidity requirements are not satisfied.

---

# 15. COMPLIANCE ENGINE

Create:

```text
config/compliance_rules.yaml
```

Implement deterministic:

```text
PASS
WARN
REJECT
```

Compliance must be a hard gate.

```text
Recommendation
      ↓
Compliance Check
      ↓
PASS / WARN / REJECT
      ↓
If REJECT → No Gemini explanation
```

Test:

* Every compliance rule
* Edge cases
* Adversarial inputs
* Attempts to bypass restrictions

---

# 16. AGENT ARCHITECTURE

Use **LangGraph as the main workflow/state spine.**

Agents/components:

```text
Customer Analyzer
        ↓
Risk Analyst
        ↓
Financial Health Analyst
        ↓
Goal Analyst
        ↓
Market Analyst
        ↓
Portfolio Manager
        ↓
Compliance Analyst
        ↓
Gemini Financial Advisor
```

Use AutoGen for one bounded strategy debate between:

* Portfolio Manager
* Risk Analyst
* Compliance Analyst

Do not create unnecessary autonomous loops.

---

# 17. GEMINI FINANCIAL ADVISOR

Gemini should be specialized through **financial-domain grounding**, not uncontrolled numerical reasoning.

Provide Gemini with:

* Financial terminology
* Investment concepts
* Risk-profile definitions
* Portfolio concepts
* Goal-planning concepts
* Financial-literacy material
* Project policies
* Compliance rules
* Validated model outputs

Example structured input:

```json
{
  "risk_category": "Balanced",
  "risk_score": 62,
  "current_equity": 78,
  "recommended_equity": 60,
  "recommended_bonds": 25,
  "recommended_gold": 10,
  "recommended_cash": 5
}
```

Gemini can explain:

> "Your equity allocation was reduced because your current risk profile and financial goals indicate a need for greater stability."

Gemini MUST NOT change:

* 60% equity
* 25% bonds
* 10% gold
* 5% cash

or calculate them independently.

---

# 18. GEMINI VALIDATION

Every Gemini response containing financial numbers must be validated against the deterministic result.

If Gemini:

* Changes a number
* Invents a number
* Gives unsupported financial claims
* Violates compliance
* Provides a guaranteed-return statement

then:

```text
Gemini Response
      ↓
Validation
      ↓
FAIL
      ↓
Reject / regenerate / fallback
```

No invalid recommendation reaches the user.

---

# 19. REACT FRONTEND

Create:

```text
frontend/
├── src/
│   ├── components/
│   │   ├── ui/
│   │   ├── charts/
│   │   ├── dashboard/
│   │   ├── portfolio/
│   │   ├── risk/
│   │   └── agents/
│   │
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── CustomerProfile.tsx
│   │   ├── FinancialHealth.tsx
│   │   ├── RiskAssessment.tsx
│   │   ├── PortfolioAnalysis.tsx
│   │   ├── AIRecommendation.tsx
│   │   ├── RecommendationExplanation.tsx
│   │   ├── AgentActivity.tsx
│   │   └── ScenarioSimulator.tsx
│   │
│   ├── api/
│   ├── hooks/
│   ├── types/
│   ├── lib/
│   ├── routes/
│   └── App.tsx
│
├── package.json
├── vite.config.ts
└── tailwind.config.ts
```

Use reusable components.

Do not duplicate UI code across pages.

---

# 20. FASTAPI BACKEND

Create REST endpoints for:

```text
/api/customers
/api/customers/{id}/financial-health
/api/customers/{id}/risk
/api/customers/{id}/goals
/api/customers/{id}/portfolio
/api/customers/{id}/recommendation
/api/customers/{id}/explanation
/api/customers/{id}/agents
/api/customers/{id}/scenario
/api/market
/api/health
```

Use Pydantic schemas for request/response validation.

---

# 21. DASHBOARD

The React dashboard should show:

* Net financial health
* Risk category
* Risk score
* Savings rate
* Emergency fund status
* Goal progress
* Portfolio allocation
* Market regime
* AI recommendation
* Compliance status

Use interactive charts with Recharts.

---

# 22. RISK ASSESSMENT PAGE

Show:

* Risk category
* Risk score
* Confidence
* Class probabilities
* Important features
* SHAP explanation
* Confusion matrix
* Model performance

Use clear financial-language explanations.

---

# 23. PORTFOLIO PAGE

Show:

* Current allocation
* Recommended allocation
* Asset-level weights
* Efficient frontier
* Risk/return metrics
* Benchmark comparison
* Drawdown
* Turnover

Use pie/donut charts and appropriate financial visualizations.

---

# 24. AI RECOMMENDATION PAGE

Show:

### Recommendation

### Why?

### Supporting evidence

### Risk considerations

### Goal impact

### Market context

### Compliance status

### Disclaimer

Never display hidden chain-of-thought.

Show only concise decision explanations and validated evidence.

---

# 25. WHY THIS RECOMMENDATION PAGE

Show explainability:

* Risk model factors
* SHAP feature importance
* Expense behaviour
* Goal probability
* Portfolio optimization factors
* Market regime
* Compliance checks

The goal is to answer:

> **"Why did WealthPilot recommend this?"**

without exposing private chain-of-thought.

---

# 26. AGENT ACTIVITY PAGE

Show a transparent activity timeline:

```text
Customer Data Loaded
        ↓
Risk Assessment Completed
        ↓
Financial Health Analyzed
        ↓
Goals Evaluated
        ↓
Market Regime Identified
        ↓
Portfolio Optimized
        ↓
Compliance Checked
        ↓
Recommendation Generated
```

Display:

* Agent
* Action
* Status
* Timestamp
* Result summary

Do not expose hidden reasoning.

---

# 27. SCENARIO SIMULATOR

Allow the user to modify deterministic inputs such as:

* Monthly savings
* Investment contribution
* Retirement age
* Goal target
* Investment horizon
* Inflation assumption
* Risk profile where appropriate

Recalculate:

* Goal probability
* Funding gap
* Portfolio metrics
* Financial outcomes

Use backend calculations.

Never perform financial calculations only in JavaScript.

---

# 28. SECURITY

Use:

```text
.env
```

for:

```text
GEMINI_API_KEY=
DATABASE_URL=
```

Never expose API keys in React.

Never place secrets in Git.

Backend communicates with Gemini.

Frontend communicates only with FastAPI.

---

# 29. PERFORMANCE

Backend:

* Cache models
* Avoid retraining during requests
* Reuse database connections

Frontend:

* TanStack Query caching
* Lazy-loaded routes where useful
* Loading skeletons
* Optimized API requests
* Avoid unnecessary re-renders

---

# 30. PROJECT STRUCTURE

Recommended structure:

```text
wealthpilot-ai/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── models/
│   │   ├── services/
│   │   ├── schemas/
│   │   ├── db/
│   │   └── core/
│   │
│   ├── training/
│   ├── tests/
│   ├── config/
│   ├── models/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
│
├── data/
├── docs/
├── scripts/
├── .env.example
├── .gitignore
├── CLAUDE.md
└── README.md
```

---

# 31. TESTING

Implement:

### Unit tests

* Financial calculations
* Risk preprocessing
* Goal engine
* Portfolio optimizer
* Compliance rules
* Market preprocessing

### Integration tests

* Database
* FastAPI
* LangGraph
* Gemini validation
* Recommendation pipeline

### Frontend tests

Test:

* Page rendering
* API states
* Forms
* Charts
* Recommendation display
* Error handling

---

# 32. REPRODUCIBILITY

Use:

```text
random_state = 42
```

where applicable.

Record:

* Python version
* Library versions
* Dataset version
* Model version
* Timestamp
* Hyperparameters
* Evaluation metrics

Store model metrics in:

```text
models/metrics.json
```

This file should be the source for report/paper performance tables.

---

# 33. RESPONSIBLE AI

Display:

> WealthPilot AI is an educational decision-support prototype and is not a substitute for advice from a licensed financial professional. The system does not guarantee returns and does not execute trades, transfer funds, or provide autonomous financial transactions.

No:

* Guaranteed returns
* Fake performance claims
* Autonomous trading
* Fund transfers
* Unsupported financial claims

---

# 34. DEVELOPMENT PHASES

Implement sequentially.

### Phase 0

Foundation and repository setup

### Phase 1

PostgreSQL database

### Phase 2

Data acquisition and quality

### Phase 3

Preprocessing and feature engineering

### Phase 4

Risk classification

### Phase 5

Expense segmentation and behaviour detection

### Phase 6

Market analysis

**This is where Yahoo Finance / `yfinance` and NASDAQ data are used.**

### Phase 7

Financial goal engine

### Phase 8

Portfolio optimization

### Phase 9

Compliance engine

### Phase 10

Agent state and nodes

### Phase 11

LangGraph workflow

### Phase 12

AutoGen strategy debate

### Phase 13

Gemini financial-domain advisor

### Phase 14

React frontend — Dashboard, Customer Profile, Financial Health, Risk Assessment, Portfolio Analysis

### Phase 15

React frontend — AI Recommendation, Why Recommendation, Agent Activity, Scenario Simulator

### Phase 16

Final integration, testing, evaluation, documentation and case study

---

# 35. STRICT PHASE EXECUTION RULE

For every phase:

1. Read `CLAUDE.md`.
2. Read `docs/PROJECT_PLAN.md`.
3. Identify the current phase.
4. Implement ONLY that phase.
5. Do not implement later phases.
6. Run relevant tests.
7. Fix errors belonging to the current phase.
8. Verify the implementation.
9. Produce a Phase Completion Report.

---

# 36. PHASE COMPLETION REPORT

At the end of every phase provide:

```text
PHASE COMPLETION REPORT

Phase:
Status:

Completed:
- ...

Files Created:
- ...

Files Modified:
- ...

Tests:
- ...

Actual Test Results:
- ...

Manual Verification:
- [ ] ...
- [ ] ...

Known Issues:
- ...

Next Phase:
- ...
```

Do not claim a feature works unless it has actually been tested.

---

# 37. CONTEXT / OUTPUT LIMIT RULE

If your context or output limit is reached during a phase, DO NOT restart the phase.

Stop and output:

```text
PHASE X PAUSED

Last completed step:
...

Files completed:
...

Files remaining:
...

Next step:
...

WAITING FOR CONTINUE
```

When the user sends:

```text
CONTINUE
```

resume exactly from the next incomplete step.

Do not repeat completed work.

Do not recreate existing files unnecessarily.

---

# 38. FINAL SYSTEM

The completed system should follow:

```text
                    React + shadcn/ui
                           │
                           ▼
                    FastAPI REST API
                           │
                           ▼
                      LangGraph
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     Risk Engine      Goal Engine      Market Engine
          │                │                │
          │                │          Yahoo Finance
          │                │             ↓
          │                │      NASDAQ / QQQ /
          │                │      Bond / Gold
          └────────────────┼────────────────┘
                           ▼
                  Portfolio Optimizer
                           │
                           ▼
                  Compliance Engine
                           │
                    PASS / WARN / REJECT
                           │
                           ▼
                  Gemini Financial Advisor
                           │
                           ▼
                Validated Explanation
                           │
                           ▼
                    React Dashboard
```

**Core principle:**

> **Python computes → Agents coordinate → Compliance validates → Gemini explains → React presents.**

Never allow the LLM to become the financial calculation engine.
