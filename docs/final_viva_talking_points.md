# WealthPilot AI — Final Viva Talking Points

Concise answers for the final viva. Every answer restates the project's
**documented** architecture and results; the source is in brackets so any
figure can be checked live. Where the honest answer is "modest" or "not
built", it says so — do not upgrade a claim in the room. WealthPilot AI is an
**educational decision-support prototype, not licensed financial advice.**

Source key: ADR-nnn = `docs/DECISIONS.md`; ARCH = `docs/ARCHITECTURE.md`;
PP = `docs/PROJECT_PLAN.md`; PRD = `docs/PRD.md`; `reports/…` = the named
phase report; `models/metrics.json` = trained-model evidence.

## The problem and the architecture

**1. What problem does WealthPilot solve?**
Retail customers rarely get personalised, explainable investment guidance
without a human adviser. WealthPilot explores whether an agentic pipeline —
ML models, deterministic financial maths, a compliance gate, and an LLM that
only explains — can turn a customer's real transaction history and stated
finances into a transparent, auditable recommendation, and stay honest where it
cannot give a confident answer. (`reports/final_viva_facts.md` §1, PRD)

**2. Why agentic AI?**
The task is a chain of different specialist jobs — classify risk, assess
financial health, check goals, read the market, build a portfolio, check
compliance, then recommend and explain. Each is a separate node with its own
inputs and outputs, sharing one typed state, with routing and a veto between
them. "Agentic" here means specialised agents under deterministic
orchestration, not free-form agents deciding on their own. (ADR-011, ARCH §10)

**3. Why LangGraph?**
The routing decisions (risk-confidence gate, emergency-fund gate, compliance
gate) must be reproducible and testable, with no LLM randomness deciding who is
approved. LangGraph gives an explicit, typed state graph; every node wraps
exactly one already-tested function and merges its result through a single
`apply_delta`; no financial logic lives in the graph file. (ADR-011)

**4. Why AutoGen?**
AutoGen provides a bounded three-persona debate (portfolio manager, risk
analyst, compliance analyst) that could critique an already-approved allocation
without altering any number. It is built and tested as a **standalone module**
and is **not invoked by any API route today** — a deliberate scope decision
under a tight Gemini quota. Say this plainly; do not imply it runs on every
request. (ADR-012, `reports/final_viva_facts.md` §17)

**5. Why Gemini?**
An LLM writes clear prose about a decision result, which is what a customer
needs to understand it. Gemini is therefore used for exactly two things: the
explanation of an already-approved recommendation, and general
financial-education Q&A. (ADR-013, `api/services/qa_service.py`)

**6. What does Gemini actually do?**
It receives a fully computed dictionary and returns structured prose, which is
validated against the source data. On any mismatch, failure or timeout the
system falls back to a template restatement of the computed results. In this
environment Gemini's quota is currently exhausted, so the template is what you
see — labelled as such on the "Why This Recommendation" page. (ADR-013)

**7. Does Gemini calculate financial values?**
No — anywhere. Every financial number is computed once, in `core/` or a trained
model; React only formats; Gemini only restates. It is also never called for a
rejected or pending analysis. (ADR-013, ADR-014)

## ML models

**8. How is risk predicted?**
A Random Forest classifier over 20 engineered features built from each
customer's own FAR-Trans transaction history, cut off at that customer's label
date, predicts one of four classes: Conservative, Income, Balanced,
Aggressive. It returns class probabilities; if the top confidence is below 0.50
the system does not guess — it requests more information
(`pending_information`). (`reports/phase4_risk_classification_report.md`,
ARCH §8/§10)

**9. Why Random Forest?**
Four models were compared under identical stratified 5-fold cross-validation
(`random_state=42`) on macro-F1: Random Forest **0.4075 ± 0.0048**, XGBoost
0.3969, MLP 0.3545, Logistic Regression 0.3527. Random Forest scored highest
and is the model served. The plan expected boosting might edge it; the
cross-validated numbers decided, as the plan prescribed. (`models/metrics.json`,
Phase 4 report, PP §2.1)

**10. Why expense segmentation?**
FAR-Trans has no income, expense or savings fields, so it cannot describe
spending behaviour. A separate Kaggle personal-finance dataset (32,424 rows)
is clustered to characterise expense profiles for *that* population. The
result is never applied to a FAR-Trans customer, so the app shows "expense
persona unavailable" with the reason. (ADR-010, Phase 5 expense report)

**11. Why K-Means?**
Methods were compared by silhouette at each method's best k: K-Means k=2 scored
**0.4580**, Ward 0.4065 (on a 5,000-row subsample), GMM 0.0129 (chosen by BIC
at k=10). K-Means k=2 was selected, giving an 88.0% / 12.0% split. (Phase 5
expense report)

**12. How is behaviour detected?**
From a monthly panel (127,924 rows, 29,090 customers) of trading intensity
(monthly trade count), contribution rate (monthly buy value) and asset mix. The
primary detector is a trailing 12-month rolling z-score (alert at |z| > 2.0,
minimum 3 prior months) plus CUSUM (k = 0.5, h = 5.0); a multivariate Isolation
Forest is the secondary detector. The app surfaces two flags: behaviour drift
and anomaly. (`models/metrics.json`, Phase 5 behaviour report)

**13. Why Isolation Forest?**
It needs no labelled anomalies and can score several behaviour features
together, which suits an unlabelled panel. Be candid about one property: its
`contamination` is fixed at 0.05, so about 5% of months are flagged by
construction (6,397 of the panel, 5.0006%). Also, FAR-Trans's multi-dated risk
records showed zero raw risk-category changes, so "no risk drift" is a finding
about that data, not proof the detector is broken. (`models/metrics.json`)

**14. How is the market regime detected?**
Each instrument's rolling 20-day realised volatility and rolling 20-day mean
return are compared with thresholds set at the 66th percentile of each, computed
**only from each window's training slice**; the result is Trending, Range-bound
or Volatile. The market analyst reads the latest regime per instrument from the
pre-computed snapshot in `models/metrics.json` — it never retrains. (Phase 6
report §13, ARCH §8)

**15. Why are market forecasts not used for portfolio expected returns?**
Three reasons, all documented. The plan forbids feeding point forecasts to the
optimiser, because mean-variance optimisation is very sensitive to
expected-return error. The evidence agrees: naive, ARIMA, LSTM and GRU models
were compared per instrument and Diebold-Mariano p-values were all above 0.05,
so no model significantly beat the naive baseline. So expected returns are the
annualised historical mean of daily returns (QQQ +15.06%, AGG −3.36%, GLD
+20.33% over the sample) and are labelled historical estimates, not forecasts.
(PP §2.4/§2.5, Phase 6 report §12, Phase 8 report §6)

## Portfolio construction

**16. Why MVO?**
Mean-variance optimisation (maximise Sharpe, Ledoit-Wolf shrinkage, per-asset
box constraints, risk-free rate 0%) is the brief's required method and the
mapping for Aggressive customers. In the historical backtest MVO scored well for
Aggressive (Sharpe 1.7557) and Conservative (1.7465). The QQQ weight is held
inside the customer's risk band and no asset may exceed 70%. (ADR-017, Phase 8
report)

**17. Why HRP?**
Hierarchical Risk Parity is a return-blind, risk-based allocation that is
robust to expected-return error; it is used for Conservative and Income
customers. Be honest about the backtest: HRP lagged (Sharpe 1.0178) because it
concentrated in AGG (83.8% full-history weight), whose realised return was
negative in this window. (ADR-017, Phase 8 report §13)

**18. Why 1/N?**
Equal weighting is the mandatory benchmark — DeMiguel, Garlappi and Uppal
(2009) showed it often beats optimised portfolios out of sample — and is the
mapping for Balanced customers. In the backtest 1/N (Sharpe 1.6326) beat
MVO-Balanced (1.5291), which the plan said to report rather than hide. (PP §2.5,
ADR-017)

**19. Why QQQ, AGG and GLD?**
The universe is fixed by the project plan: a Nasdaq/tech equity ETF (QQQ), a
bond proxy (AGG) and a gold proxy (GLD). Exactly three strategies and this
three-asset universe exist; nothing else is implemented. It is a deliberate
prototype simplification, evaluated on one ~4.5-year historical window.
(ADR-017, PP §2.4)

## Emergency fund, compliance and recommendation

**20. How does the emergency fund affect recommendations?**
The target is six months of essential expenses. If the fund is sufficient the
normal pipeline continues to portfolio construction. If not — or if it cannot
be determined — the recommendation engine's second layer (savings-first) takes
over. (`core/goals.py::EMERGENCY_FUND_TARGET_MONTHS`, ADR-016)

**21. What happens when the emergency fund is insufficient?**
Portfolio optimisation is skipped, the recommendation status is
`savings_first`, weights are `null`, and compliance passes because a
savings-first proposal legitimately has no weights (ADR-018). Demo 29108: 15,000
required, 4,000 held, shortfall €11,000, "build liquidity before investing".

**22. What happens when the emergency fund is unknown?**
The same savings-first route runs, but compliance is fail-closed: the rule
`emergency_fund_savings_first` triggers ("emergency-fund status was not
provided") and the result is **REJECT**. Demo 29109 — the system refuses to
guess. (ADR-015, ADR-018)

**23. How does compliance work?**
Five rules in `config/compliance_rules.yaml`, each with a unit test: weights sum
to one, no negative weights, QQQ within the risk band, single-asset cap, and
the emergency-fund rule. They are evaluated against the proposal with
`yaml.safe_load` data (never executed code); a rule whose required input is
missing is treated as triggered. All five are REJECT severity. (ADR-015, ARCH
§14)

**24. Can compliance be overridden?**
No. `enforce_gate` raises on REJECT, nothing in the codebase catches it, and the
API layer only runs the recommendation engine and Gemini when the graph's
terminal status is `approved`. The precedence Compliance > Savings-first > Risk
> Goal > Market is fixed. (ADR-015, ADR-016)

**25. What happens after REJECT?**
The analysis ends `rejected`: `recommendation` and `explanation` are `null`, no
allocation exists, Gemini is never called, and the stream ends
`compliance_analyst → rejected → analysis_completed`. The UI shows the
compliance breakdown — which rule triggered and why — and nothing else.
(ADR-013, ADR-015)

## Goals and Monte Carlo

**26. How does Monte Carlo work?**
For each goal, 10,000 simulated paths draw per-period returns **with
replacement** from a historical series (an equal-weighted QQQ/AGG/GLD blend,
compounded to the goal's contribution frequency), accumulate the customer's
contributions, and count the share of paths that reach the inflation-adjusted
target (seed 42). At least 80% is Feasible, 50–79% At Risk, below 50% Not
Feasible. A frequency bug (daily returns applied once per monthly period, which
made every goal 0.0%) was found and fixed in Phase 29 — say so if asked.
(Phase 7 report, ADR-026, ADR-027)

## Data science rigour

**27. How was temporal leakage prevented?**
A leakage audit found that before the fix 76.5% of labelled customers'
behavioural features and 99.95% of market-derived features used information
from after the customer's own label date. It was fixed with point-in-time
filtering (`timestamp <= target_date`) and a backward as-of join for market
features, with an automated regression test. Preprocessors are fitted on
training data only, and market models use walk-forward splits. (Phase 3 leakage
audit, ADR-008)

**28. How were train/test splits performed?**
Risk model: stratified 5-fold cross-validation over one row per customer, with
point-in-time features. Market models: expanding-window walk-forward across 10
windows with a 5-day embargo and a 1-trading-day horizon, targeting returns and
volatility, never price levels. Portfolio backtest: walk-forward on a trailing
lookback. No shuffled splits on time series. (Phase 4 report; Phase 6 report §8–§9;
Phase 8 report §15; ADR-008)

**29. Why does the model have modest macro-F1?**
Macro-F1 is 0.4075 across four imbalanced classes — a genuinely hard problem on
real transactional data, and the project reports it as modest rather than
tuning until it looks better. Per-class recall shows the spread (Conservative
0.64, Balanced 0.44, Aggressive 0.42, Income 0.32). The system compensates by
routing low-confidence customers to `pending_information` instead of
guessing. (`reports/phase19_final_evaluation_report.md` §18, Phase 4 report)

**30. What datasets were used?**
FAR-Trans (real, anonymised, CC-BY 4.0: customer information, asset
information, markets, close and limit prices, transactions, questionnaires;
21,629 customers with a genuine risk label, 21,528 in the trainable
population), a Kaggle synthetic personal-finance dataset (32,424 rows) for
expense segmentation, and `yfinance` market history for QQQ, AGG, GLD, ^IXIC
and ^NDX. (`reports/final_viva_facts.md` §4–5, Phase 2/3 reports)

**31. Why FAR-Trans?**
It is a public, real, anonymised customer dataset with genuine risk labels and
transaction histories from a European institution — what the risk and behaviour
models need. It is research data and does not represent a deployment
population; the disclaimer says so. Predicted and not-available labels are
filtered out before training. (PP data section, disclaimer, ADR-010)

**32. Why the Kaggle synthetic dataset?**
Because FAR-Trans has no income, expense or savings. The Kaggle set supplies
those fields for a separate population, is labelled synthetic in the
disclaimer, and is used only for expense segmentation. (ADR-010)

**33. Why was there no arbitrary linkage between them?**
Pairing a FAR-Trans customer with a Kaggle profile would fabricate a
relationship that does not exist. The plan's synthetic-assembly idea was not
built; the two populations stay separate, and `expense_persona` is reported as
structurally unavailable for FAR-Trans customers. (ADR-010, `models/metrics.json`
expense note)

## Safety, data handling and limits

**34. How is customer isolation handled?**
Every per-customer query is scoped by `customer_id` at the query level, and the
authenticated session resolves to exactly one customer automatically — there is
no customer picker or switcher. This is data scoping, not per-account
authorisation; the prototype has no authorisation layer and does not claim one.
(ADR-021, ADR-024, `docs/SECURITY.md`)

**35. How is NULL handled?**
Unknown, not-yet-provided and structurally unavailable values are `null` plus an
`*_unavailable_reason`, in the database, the API and the UI — never `0`, never
guessed. Each financial input is stored independently nullable, and the screen
shows "Not available" or a "Not provided" placeholder. (CLAUDE.md §12, ADR-025)

**36. What are the major limitations?**
Modest risk-model scores (macro-F1 ≈ 0.41). No market model beat a naive
baseline. One ~4.5-year historical window, three assets, and backtests, not
forward tests. Expense persona is structurally unavailable for FAR-Trans
customers. Prototype authentication only. AutoGen is not wired into the live
pipeline. Gemini's quota is exhausted here, so explanations are the template
fallback. No customer switcher. No browser-based visual testing has been done in
this project; checks were type-checking, build, lint, 763 backend tests and
server-side render checks. (ARCH §23, PRD §39, `reports/final_viva_facts.md`)

**37. What is the current approved demo path?**
Sign in with **Use Individual Demo**, which resolves to "WealthPilot Demo —
Complete": Aggressive, emergency fund sufficient, Retirement Feasible (94.1%),
House Purchase At Risk (50.3%), MVO QQQ 55% / GLD 45%, compliance PASS,
approved. Savings-first and the compliance REJECT are shown through the API
explorer because the app deliberately has no customer switcher. The household
side has its own entry point, **Use Family Demo**, which opens the canonical
"WealthPilot Demo Family" household — household-level context only, with no
household risk score or recommendation (ADR-036).
(`docs/final_demo_script.md`, `docs/demo_runbook.md`)

**38. What does "savings-first" mean?**
"Build liquidity before investing." When the emergency fund is short, the system
defers portfolio optimisation and recommends building the fund; it is a safe,
approved outcome with no allocation, not an error. (ADR-016, ADR-018)

**39. What does "pending information" mean?**
The pipeline could not classify risk with enough confidence — either confidence
is below 0.50 or the customer has no FAR-Trans linkage (a brand-new user) — so it
stops at an information request. Every downstream section is unavailable and
nothing is fabricated. (ARCH §10, demo 29096)

**40. Is this real financial advice?**
No. It is an educational decision-support prototype: it does not execute
trades, move money or connect to a brokerage; market data is historical, not a
forecast; FAR-Trans is research data; the Kaggle data is synthetic; and
production use would need review against advice regulation, suitability
obligations and data-protection law. "Approved" means the deterministic
pipeline completed and compliance passed for a synthetic persona's own inputs.
(ADR-019, the canonical disclaimer)
