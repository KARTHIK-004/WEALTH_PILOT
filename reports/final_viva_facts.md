# Final Viva Facts — WealthPilot AI

> **Superseded in part (note added in Phase 31; the body below is a Phase 19
> snapshot and is otherwise unchanged).** Do not repeat these Phase 19 claims:
> §14 "no customer has reached approved" and §15 "the Goal Engine is not wired"
> are no longer true — since Phase 28/29 the seeded "WealthPilot Demo —
> Complete" persona reaches a real `approved` MVO result with real goal
> feasibility (94.1% / 50.3%), "Savings" reaches `savings_first`, and
> "Compliance" is `rejected` on one rule; the "697 tests" figure in §20 is now
> 763 passed, 3 skipped. Use `docs/final_viva_talking_points.md` and
> `docs/final_demo_script.md`, which reflect the current verified state. The
> model scores, dataset counts, leakage-fix figures and design rationale below
> remain accurate.

A ready-reference for presentation/viva. Every figure below is sourced from a
repository artifact (cited inline) and was cross-checked in Phase 19 against
that artifact directly, not from memory of an earlier report alone.

---

## 1. Problem Statement

Retail customers rarely get personalized, explainable investment guidance
without a human advisor. WealthPilot AI is an M.Tech case study exploring
whether an agentic AI pipeline — deterministic ML models plus a compliance
gate plus an LLM that only explains, never decides — can produce a
transparent, auditable investment recommendation from real transactional
data, while remaining honest about where it cannot yet produce a confident
answer.

## 2. What This System Is

An **agentic AI-based decision-support prototype**: a LangGraph pipeline of
specialized nodes (risk classification, financial health, goal analysis,
market read, portfolio optimization, compliance) feeding a four-layer
recommendation engine, with a FastAPI backend and a React frontend. It is
**not** licensed financial advice and does not execute trades.

## 3. What This System Is Not

Not a "robo-advisor" in the commercial sense; not connected to any brokerage
or payment system; not a guarantee of any return; not a system that has been
validated on live/forward market data (all evaluation is historical
backtest); not a system where any real customer has yet received a fully
approved end-to-end recommendation (see §14).

## 4. Data Sources

FAR-Trans (customer_information, asset_information, markets, close_prices,
limit_prices, transactions, questionnaires — no Kaggle-style auth required)
plus a Kaggle personal-finance dataset for expense segmentation, plus
`yfinance`-sourced market price history for the market-prediction models.

## 5. Dataset Scale

Genuine labeled customer count: **21,629**; genuine labeled row count:
**24,850** (`reports/phase2_data_quality_report.md`). Post-leakage-fix
trainable population for the risk model: **21,528** customers (101 excluded
for zero pre-target-date transactions) (`reports/phase3_leakage_audit.md`).

## 6. The Leakage Bug — and Its Fix

A real bug was found and fixed earlier in this project: before the fix,
**76.5%** of labeled customers' behavioral features and **99.95%** of
market-derived features leaked information from after each customer's own
label date. Fixed with point-in-time transaction filtering and an
expanding-window (point-in-time) volatility/drawdown join via
`merge_asof(direction="backward")`, with an automated regression test that
still passes today. This is safe to describe in a viva as an example of
rigorous leakage discipline, not something to hide.

## 7. Risk Classification — Exact Numbers

Macro-F1 (test set), four models compared: **Logistic Regression 0.3527,
Random Forest 0.4075, XGBoost 0.3969, MLP 0.3545** (`models/metrics.json`).
**Random Forest is both the best-scoring model and the one actually served**
in production inference (`agents/nodes.py`). These are modest scores — say
so plainly if asked; do not round up or imply higher confidence than the
number supports.

## 8. Expense Segmentation

K-Means, **k=2**, approximately **88.0% / 12.0%** cluster split
(`reports/phase5_expense_segmentation_report.md`).

## 9. Behaviour Drift Detection

IsolationForest-based. On the evaluated population/window, the finding was
**zero risk-drift** detected — report this as a finding specific to that
data/window, not as proof the detector is non-functional.

## 10. Market Prediction — the Honest Finding

Naive, ARIMA/GARCH, LSTM, and GRU models were all compared per instrument
(QQQ, AGG, GLD) using Diebold-Mariano tests. **Every p-value was above
0.05** — meaning **no tested model significantly beat the naive baseline**.
This is the correct, evidence-backed thing to say if asked "how good are
your market predictions" — do not claim otherwise.

## 11. Portfolio Optimization — Backtest Sharpe Ratios

From `models/portfolio/backtest_v1.json`: equal-weight (1/N) **1.6326**,
HRP **1.0178**, MVO-Conservative **1.7465**, MVO-Income **1.6522**,
MVO-Balanced **1.5291**, MVO-Aggressive **1.7557**. In plain language: MVO
performed strongly for Conservative and Aggressive risk profiles in this
specific historical backtest window; 1/N actually beat MVO for the Balanced
profile; HRP lagged clearly, attributed to its AGG concentration during a
period when AGG had a negative realized return. This is a result about one
historical window, not a universal claim that MVO always wins.

## 12. Compliance Rules

5 REJECT-severity rules, version `v1`, defined in
`config/compliance_rules.yaml`, loaded only via `yaml.safe_load`. No
WARN-severity rule exists — a deliberate design choice, not an omission. A
REJECT verdict is structurally guaranteed to never reach the recommendation
engine, the explanation step, or the API response fields for
recommendation/explanation — enforced by a single `if` gate in the API
service layer, live-verified this phase (17 real customers probed; the 6
that hit REJECT returned `recommendation: null, explanation: null` directly
in the HTTP response, and the same result was independently confirmed over
the live SSE stream).

## 13. The Recommendation Engine's Four Layers

In strict precedence order: **(1) Compliance** — REJECT halts everything.
**(2) Savings-first** — if the emergency fund is insufficient/unknown, a
savings-first recommendation is made and portfolio optimization is skipped.
**(3) Risk-conditioned base strategy** — a total mapping from risk category
to strategy (Conservative/Income → HRP, Balanced → equal-weight, Aggressive
→ MVO); this can never be overridden by layer 4. **(4) Goal/market
preference** — can only annotate the rationale as "aligned" or "overridden"
with the strategy layer 3 already selected, never change it.

## 14. The Honest Limitation: No Customer Has Reached "Approved" Yet

Live-tested this phase against **17 real customer profiles**
(ids 1, 2, 3, 4, 5, 6, 7, 10, 25, 50, 75, 100, 150, 200, 300, 500, 1000):
**11 stopped at "pending_information"** (risk-classification confidence
below the 0.50 routing threshold) and **6 were "rejected"** by compliance.
**Zero reached "approved."** Root cause: FAR-Trans has no expense/liquid-
asset fields, so `emergency_fund.sufficient` is structurally unknown for
this population, which routes every customer to the conservative
savings-first path, which in turn tends to trip a compliance REJECT rule.
This is a genuine, disclosed characteristic of the current data — not a
crash, not fabricated output, and not something this project should claim
does not exist.

## 15. The Other Honest Limitation: Goal Engine Wiring

The Goal Engine (TVM + Monte Carlo, 10,000 simulations, seed 42) is fully
implemented and independently unit-tested, but the live API never supplies
it with a contribution/return/inflation assumption or a historical-return
series — so today, every real customer's goal feasibility shows
"unavailable" rather than a computed number. The system fails safe (it says
"unavailable," it never guesses), but the feature does not yet produce a
live number end-to-end. This is worth stating proactively if asked to
demonstrate the Goals page.

## 16. LangGraph — the Orchestration Layer

A single, acyclic `StateGraph` with 14 nodes. Every conditional edge checks
for an unexpected processing failure first and routes to a `failed` terminal
if one occurred, so a bug in one node cannot silently masquerade as a
different outcome. Confirmed this phase by reading the full source: there is
no loop anywhere in the graph, and no financial calculation lives in the
graph file itself — every node wrapper calls exactly one already-tested
Phase 10 function and applies its result via a single, non-bypassable
`apply_delta` call.

## 17. AutoGen — What It Is, and Its Current Status

`agents/debate.py` implements exactly **three** LLM-backed debating agents —
Portfolio Manager, Risk Analyst, Compliance Analyst — plus a non-LLM
Moderator that only sequences turns. It is fully built and tested but is
**not currently invoked** by the live `/api/analysis` pipeline — a
deliberate decision (not in the required output contract, and invoking it
on every request would multiply an already-tight Gemini quota). Be ready to
say this plainly rather than imply it runs on every request.

## 18. Gemini's Role — and Its Limits

Gemini writes explanation prose for an **already-computed, already-approved**
recommendation, and answers general financial-literacy questions via
`POST /api/qa`. In both cases, Gemini's output is validated or scoped so it
can never compute, restate, or override a number: the explanation path
validates generated text against the source dict and rejects on mismatch;
the Q&A path's system prompt explicitly forbids stating a specific figure
for the asking customer, and nothing in the code parses its response for a
decision.

## 19. Why This Architecture (Design Rationale)

- **LangGraph for the deterministic core**: routing decisions (risk
  confidence gate, emergency-fund gate, compliance gate) are structured,
  reproducible, and testable — no LLM randomness in whether a customer gets
  approved or rejected.
- **AutoGen kept standalone rather than forced into every request**: a
  genuine engineering tradeoff under a real rate limit, disclosed rather
  than hidden, with the module fully built for a future integration
  decision.
- **Gemini restricted to prose, never numbers**: the single most important
  safety property of the whole system — a hallucinated number from an LLM
  could misinform a real financial decision, so the architecture makes that
  structurally impossible rather than relying on prompt discipline alone.
- **Compliance as a hard gate, not a soft signal**: encoded as YAML rules
  with individual unit tests, and enforced by a plain Python `if`, not by an
  LLM's judgment call — auditable and deterministic.
- **Fail-safe over fail-plausible, throughout**: every gap found in this
  project (emergency fund unknown, goal assumptions unset) results in an
  explicit "unavailable" rather than an invented number. This is the
  project's most consistent design principle and the one most worth
  defending in a viva if challenged on the system's incompleteness.

## 20. Facts Safe to State, and Claims Not Safe to Make

**Safe to state:**
- "The backend test suite passes 697 tests with 0 failures."
- "Random Forest was selected as the best risk-classification model, with a
  Macro-F1 of about 0.41."
- "No market-prediction model significantly beat a naive baseline, measured
  via Diebold-Mariano tests — we report this honestly rather than
  overselling predictive power."
- "MVO outperformed 1/N and HRP for Conservative and Aggressive profiles in
  our historical backtest, but 1/N outperformed MVO for the Balanced
  profile in that same window."
- "A REJECT compliance verdict is structurally guaranteed — not just
  conventionally expected — to never reach the recommendation or
  explanation step; this was verified live via the actual HTTP/SSE
  responses, not only by reading the code."
- "No customer in our current test population has received a fully approved
  recommendation yet, because of a known data-availability gap around
  emergency-fund information in the source dataset — we treat this as an
  honest, disclosed limitation."
- "Gemini never computes a financial figure anywhere in this system; it
  only writes explanatory prose for numbers already computed deterministically,
  and its output is validated against the source data."

**Not safe to make:**
- "This system is a licensed financial advisor" or any equivalent — it is
  explicitly an educational decision-support prototype.
- "This system guarantees returns" or "optimizes wealth" in any guaranteed
  sense.
- "Our models are highly accurate" or any unqualified accuracy claim — the
  actual Macro-F1 scores are modest (0.35-0.41) and should be stated as
  such.
- "Our market models predict prices/returns well" — the Diebold-Mariano
  results directly contradict this.
- "Every customer gets a working recommendation" — untrue today; be ready to
  explain the pending_information/rejected/approved split honestly if asked
  to demonstrate the system live.
- "The system has been tested in a real browser for accessibility/visual
  correctness" — it has not; this environment has no headless-browser
  tooling, and that limitation should be stated plainly if asked.
