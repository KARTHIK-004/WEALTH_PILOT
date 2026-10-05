# WealthPilot AI — Project Plan

**Agentic AI-Based Autonomous Financial Advisor for Personalized Wealth Management**

Stack: Python · FastAPI · React + shadcn/ui · PostgreSQL · LangGraph · AutoGen · Gemini · TensorFlow · scikit-learn

---

## Part 0 — Verified Data Sources

Claude Code cannot browse or authenticate to Kaggle. These are verified; treat them as given and do not let the model search for alternatives.

### FAR-Trans (primary — real risk labels)

- **Download:** `https://researchdata.gla.ac.uk/1658/1/FAR-Trans.zip` (~9 MB, direct, no auth)
- **README:** `https://researchdata.gla.ac.uk/1658/2/README.txt`
- **License:** CC-BY 4.0. Copyright holder: National Bank of Greece
- **Citation:** Sanz-Cruzado, J., Droukas, N., McCreadie, R. *FAR-Trans: An Investment Dataset for Financial Asset Recommendation.* IJCAI-2024 Workshop on Recommender Systems in Finance.
- **Coverage:** 2 January 2018 – 29 November 2022

Files: `customer_information.csv`, `asset_information.csv`, `markets.csv`, `close_prices.csv`, `limit_prices.csv`, `transactions.csv`, `questionnaires.csv`.
Unzip these to `datasets/raw/FAR-Trans/` — the single canonical raw-data location (see `CLAUDE.md`'s Layout section).

Notes that change implementation:
- `riskLevel` values are Conservative, Income, Balanced, Aggressive, the eight `Predicted_*` variants, and `Not_Available`. Filter to the four genuine ones.
- `investmentCapacity` bands: `CAP_LT_30K`, `CAP_30K_80K`, `CAP_80K_300K`, `CAP_GT300K`, plus `Predicted_*` and `Not_Available`.
- `customerType`: Mass, Premium, Professional, Legal entity, Inactive.
- `customer_information.csv` has **multiple dated rows per customer** — this is the behaviour agent's ground truth, not a duplicate-row bug. Do not deduplicate blindly.
- `close_prices.csv` is **close only, in euros** — no OHLCV. The `market_data` table's open/high/low/volume columns can only come from yfinance.
- `questionnaires.csv` contains the MiFID II **questions and answer options only — no customer answers.** Questionnaire score cannot be a training feature. Use the questions for the React risk questionnaire, served by the FastAPI API rather than hard-coded in React.
- `transactions.csv` `channel` values: Internet Banking, Phone Banking, Branch.

### Kaggle (secondary — income, expenses, savings)

Requires a Kaggle account and `~/.kaggle/kaggle.json` API token, or a manual download placed in `datasets/raw/kaggle/` (the original downloaded filename may be kept as-is). Claude Code should read from that path and fail with a clear, actionable message naming the expected path if the file is absent — it must not attempt to authenticate.

Primary choice:
- **`miadul/personal-finance-ml-dataset`** — `https://www.kaggle.com/datasets/miadul/personal-finance-ml-dataset`
  32,424 records. Columns include age, gender, education_level, employment_status, monthly_income_usd, monthly_expenses_usd, savings_usd, debt_to_income_ratio, credit_score, savings_to_income_ratio, region. **Synthetic**, generated from statistical distributions — state this in the report.

Alternative if monthly time-series expense data is needed for the behaviour agent:
- **`khushikyad001/personal-finance-tracker-dataset`** — `https://www.kaggle.com/datasets/khushikyad001/personal-finance-tracker-dataset`
  3,000 users, monthly snapshots over multiple years, with spending categories and simulated economic scenarios. Also synthetic.

Verify row counts, null counts and licence terms at acquisition time rather than copying the figures above into the report — dataset versions change.

### Market data (yfinance)

`^IXIC`, `^NDX`, `QQQ`, plus a bond proxy and a gold proxy. Verify ticker availability at runtime; do not assume completeness.

---

## Part 1 — Where ML Is Actually Used

A common weakness in projects like this is claiming ML everywhere. Half this system is deterministic, and that is a design strength, not a gap — financial mathematics and compliance must be reproducible. Be explicit about which is which.

| # | Module | Method | ML? | Why |
|---|---|---|---|---|
| 1 | Risk Classification | Gradient Boosting / Random Forest | **Yes — supervised** | Real labels exist in FAR-Trans |
| 2 | Expense Segmentation | K-Means / GMM | **Yes — unsupervised** | No labels; structure discovery |
| 3 | Behaviour Change Detection | Rolling z-score + Isolation Forest | **Yes — hybrid** | Statistical primary, ML for multivariate |
| 4 | Market Regime / Forecast | LSTM + GARCH | **Yes — sequence** | Time series; heavily caveated |
| 5 | Goal Planning | Time-value-of-money formulas | No | Closed form; must be exact |
| 6 | Monte Carlo Goal Probability | Stochastic simulation | No | Simulation, not learning |
| 7 | Portfolio Optimization | Mean-Variance + shrinkage | No | Convex optimization |
| 8 | Compliance | Rule engine | No | Must be auditable and bypass-proof |
| 9 | Explanation | Gemini (structured output) | LLM, not trained | Language generation only |
| 10 | Orchestration | LangGraph | No | State machine |

**Rule to state in the report and defend in the viva:** no number shown to the user is produced by the LLM. Gemini receives a fully computed dictionary and writes prose about it. Nothing else.

---

## Part 2 — Model Selection and Comparison

### 2.1 Risk Classification Agent

**Task.** Predict risk category from observed investment behaviour.
**Target.** FAR-Trans `riskLevel` — Conservative / Income / Balanced / Aggressive. Genuine labels only; drop every `Predicted_*` and `Not_Available` row.
**Treat as nominal multiclass, not ordinal.** "Income" is an investment objective, not a rung between Conservative and Balanced, so an ordinal model would impose false structure.

**Features (engineered from transactions, not taken raw).**

| Group | Features |
|---|---|
| Asset mix | % value in Stock / Bond / MTF; equity-to-bond ratio |
| Trading intensity | trades per year, buy:sell ratio, active months |
| Position sizing | mean, median, std of `totalValue`; largest trade as % of total |
| Risk exposure | realized volatility of held assets, max drawdown of holdings |
| Concentration | Herfindahl index over ISINs; top-sector share |
| Channel | share via Internet / Phone / Branch |
| Capacity | `customerType`, `investmentCapacity` band |

**Candidate comparison.**

| Model | Expected result | Verdict |
|---|---|---|
| Logistic Regression | Weakest; features interact non-linearly | Keep as baseline — always report a baseline |
| Random Forest | Strong, stable, minimal tuning | Strong contender |
| XGBoost / LightGBM | Usually best macro-F1 on tabular data | Likely winner |
| MLP (TensorFlow) | Underperforms trees at this sample size | Include to show you tested it |

**Why trees rather than deep learning.** On tabular data of a few thousand rows with mixed categorical and numeric features, tree ensembles consistently outperform neural networks — see Grinsztajn, Oyallon & Varoquaux, *Why do tree-based models still outperform deep learning on tabular data?* (NeurIPS 2022). Cite this rather than asserting it. A second practical reason: SHAP's TreeExplainer computes exact Shapley values for tree models in polynomial time, while a neural net needs sampling-based approximation. Explainability is a hard requirement here, so the model family that gives exact attributions wins.

**Why not Random Forest automatically.** RF is the safer default at small n and with less tuning; boosting typically edges it on macro-F1 but overfits faster. Run both, report both, pick on cross-validated macro-F1, and say in the report *why* the winner won.

**Metrics.** Macro-F1 as the headline, plus per-class recall, confusion matrix, and a calibration curve. **Do not lead with accuracy** — the class distribution skews heavily toward intermediate profiles, so a model that never predicts Aggressive can still post high accuracy. Stratified 5-fold cross-validation.

**Validation worth including.** Compare your predicted class distribution against FAR-Trans's real distribution. Over-prediction of Aggressive is a bias finding, and reporting it is stronger than hiding it.

---

### 2.2 Expense Analysis Agent

**Trap to avoid first.** Clustering raw currency amounts clusters income level, not spending behaviour — you will rediscover "rich" and "poor". Convert every expense category to a **share of monthly income** before clustering. That is the single most important preprocessing decision in this module.

| Model | Assessment |
|---|---|
| K-Means | Fast, interpretable centroids that map to named spending personas. Assumes spherical, equal-variance clusters. |
| Gaussian Mixture | Soft assignment with a probability per cluster — lets the agent say "72% discretionary-heavy" rather than a hard label. Handles elongated clusters. |
| Hierarchical (Ward) | Dendrogram is good evidence for choosing *k*, slow above ~10k rows. |
| DBSCAN | Poor fit — spending proportions have no clear density separation, and most points end up labelled noise. |

**Recommendation.** K-Means as the primary model (choose *k* by silhouette score with the elbow curve as supporting evidence), GMM as the documented comparison. Report silhouette and Davies-Bouldin for both, then profile each cluster qualitatively into a persona: essential-heavy, balanced, discretionary-heavy, high-spend/low-save.

Note in the report that cluster count is data-driven, not chosen to match the four personas you wanted.

---

### 2.3 Behaviour Change Agent

| Method | Role |
|---|---|
| Rolling z-score / CUSUM on savings rate, expense ratio, contribution rate | **Primary** — interpretable, produces a directly explainable statement |
| Isolation Forest | Secondary — catches multivariate drift no single metric shows |
| One-Class SVM | Rejected — poor scaling, sensitive kernel tuning, no interpretability gain |

Rationale for putting statistics first: a financial advisor must be able to say *"your expense ratio rose 2.1 standard deviations above your twelve-month norm."* An Isolation Forest anomaly score is not a sentence you can show a customer. Use the ML layer as a second opinion, not the headline.

FAR-Trans supports this genuinely — `customer_information.csv` holds multiple dated rows per customer, so real risk-profile drift is observable rather than simulated.

---

### 2.4 Market Analysis Agent

**This is where projects in this space usually oversell, so handle it carefully.**

**Mandatory baseline: the random walk.** Predicting tomorrow's closing price as today's closing price produces excellent RMSE on price levels. An LSTM trained on price levels typically learns to do exactly that with a one-step lag, then gets reported as a success. Avoid this entirely by **modelling returns and volatility, never price levels.**

| Model | Target | Comparison role |
|---|---|---|
| Naive random walk | Return = 0 | Baseline everything must beat |
| ARIMA | Return | Classical linear benchmark |
| GARCH(1,1) | Volatility | Strong, hard-to-beat volatility benchmark |
| LSTM (TensorFlow) | Return direction / volatility | The brief's required model |
| GRU | Same | Cheaper variant; often matches LSTM |

**Honest expected outcome.** The LSTM will probably not beat the random walk on return prediction. **Report that result rather than hiding it.** It demonstrates you understand market efficiency and is far more defensible than a suspiciously accurate forecast. Where LSTM has a genuine chance is volatility and regime classification, because volatility clusters and is genuinely autocorrelated.

**Metrics.** RMSE and MAE against the naive baseline, directional accuracy against a 50% coin flip, and Diebold-Mariano for whether any difference is statistically real.

**Critical architectural constraint.** Do **not** feed LSTM point forecasts into the optimizer as expected returns. Mean-variance optimization is notoriously sensitive to expected-return error and will convert a small forecast error into an extreme allocation. Instead the LSTM emits a **regime label** — trending / volatile / range-bound — which adjusts constraint bounds, never the return estimates.

---

### 2.5 Portfolio Optimization Agent

Not machine learning. Convex optimization, and it must be deterministic.

| Method | Assessment |
|---|---|
| Naive 1/N (equal weight) | Mandatory benchmark. DeMiguel, Garlappi & Uppal (2009) showed 1/N frequently beats optimized portfolios out of sample. |
| Mean-Variance (Markowitz) | The brief's requirement. Produces extreme corner solutions and is highly sensitive to inputs. |
| MVO + Ledoit-Wolf shrinkage + box constraints | **Recommended.** Shrinkage stabilizes the covariance matrix; constraints prevent absurd allocations. |
| Hierarchical Risk Parity | Needs no matrix inversion, robust to estimation error. Excellent comparison model. |
| Black-Litterman | Elegant for blending views with equilibrium, but adds a prior-specification burden. Mention as future work. |

**Recommendation.** MVO with Ledoit-Wolf shrinkage and per-asset-class box constraints as primary. Benchmark against 1/N and HRP on out-of-sample Sharpe. If 1/N wins, report it — that is a finding, and it justifies the constraints you added.

Constraints to encode: equity share bounded by risk category; single-asset cap; Nasdaq/technology concentration cap; minimum cash floor tied to emergency-fund status.

Deliverables: efficient frontier plot, chosen point marked, Sharpe ratio, and a note that expected returns are historical estimates and not forecasts.

---

### 2.6 Goal Planning

Deterministic. Future value of an existing corpus plus a stream of contributions:

```
FV = PV(1+r)^n + PMT · [((1+r)^n − 1) / r]
```

Solve for `PMT` to get the required monthly investment; the shortfall against current trajectory is the funding gap.

Add **Monte Carlo** for goal-success probability: sample returns from the historical distribution over N paths, report the share reaching the target. This gives "68% probability of reaching your target" instead of a single false-precision number, and is far more honest than a point estimate.

---

## Part 3 — Why LangGraph *and* AutoGen

The brief asks you to justify both. The answer must be a division of labour, not duplication.

| Framework | Responsibility | Why not the other |
|---|---|---|
| **LangGraph** | The workflow spine: typed state, deterministic node order, conditional routing, retry loops, checkpointing | AutoGen has no first-class typed state machine; you would rebuild it badly |
| **AutoGen** | One bounded sub-problem: multi-perspective strategy debate between Portfolio Manager, Risk Analyst and Compliance personas | Expressing genuine back-and-forth argument as LangGraph nodes means hand-coding turn-taking |
| **Gemini** | Language only — explanation, summarization, Q&A | Not a decision-maker |

**Scope AutoGen tightly.** Use it for exactly one node — the strategy debate — that returns a structured verdict into LangGraph state. If AutoGen creeps into orchestration, you have two competing state models and a debugging problem. Say this explicitly in the report; the restraint is the argument.

Conditional edges that make the graph non-trivial:

- Risk confidence below threshold → route to an information-request node instead of proceeding
- Compliance rejection → route back to Recommendation with the violated rule attached, capped at N retries
- Behaviour change flagged as significant → insert a re-profiling pass before optimization
- Emergency fund insufficient → short-circuit to a savings-first recommendation, skipping optimization entirely

---

## Part 4 — Build Approach

**Governing principle: train offline, serve online.** Models are trained in scripts, serialized to `models/`, and loaded by agents at startup. Nothing trains inside the LangGraph run. This keeps agent execution fast and reproducible, and makes model versioning possible.

**Second principle: build bottom-up.** Deterministic maths first, then models, then agents, then UI. The temptation is to build the agent graph early because it is the interesting part; resist it, because debugging a graph whose nodes return garbage is miserable.

### Stage 0 — Foundations
1. Repo structure, `.env` handling, config module, logging
2. PostgreSQL schema with Alembic migrations; add `data_source` and `model_version` columns everywhere for auditability

### Stage 1 — Data
3. Acquire FAR-Trans (CC-BY 4.0, ~9 MB) and the Kaggle personal-finance set; pin versions
4. Data-quality report: nulls, duplicates, outliers, date gaps, currency consistency
5. Preprocessing pipelines as `sklearn` Pipeline objects, serialized with the models — never re-implement preprocessing at inference time
6. Synthetic profile assembly: stratified pairing of FAR-Trans behaviour with Kaggle income/expense, conditioned on `investmentCapacity`; flag every record's provenance
7. yfinance ingestion with retry, gap handling, and adjusted-close treatment

### Stage 2 — Models
8. Risk classifier: feature engineering, four-model comparison, SHAP, serialize
9. Expense clustering: income-normalized, K-Means vs GMM, persona profiling
10. Behaviour detection: rolling statistics plus Isolation Forest
11. Market models: random walk baseline first, then ARIMA, GARCH, LSTM — in that order, so the baseline exists before the LSTM can flatter itself

### Stage 3 — Deterministic Core
12. Goal mathematics with unit tests against known values (the tests matter; an off-by-one in the annuity formula is invisible otherwise)
13. Portfolio optimizer with shrinkage and constraints; 1/N and HRP benchmarks
14. Compliance rule engine loaded from YAML, each rule independently unit-tested

### Stage 4 — Agents
15. Pydantic state model — define this before writing any node
16. Agent nodes wrapping Stage 2 and 3 components; each returns a state delta, never mutates in place
17. LangGraph assembly with conditional edges and retry caps
18. AutoGen debate node, scoped to strategy only
19. Gemini explanation node with structured output and schema validation on the response

### Stage 5 — API and Interface
20. FastAPI layer over the core: profile, analysis run, scenario comparison, Q&A. OpenAPI schema generated from the existing Pydantic models
21. TypeScript types generated from OpenAPI — never hand-written, or the two sides drift
22. Server-sent events endpoint streaming LangGraph node progress
23. React + Vite + shadcn/ui frontend, nine views, TanStack Query for caching
24. Agent Activity view consuming the SSE stream — concise auditable summaries and timings only, never raw chain-of-thought
25. Scenario Simulator comparing two parameter sets against cached runs

### Stage 6 — Evaluation and Report
23. Model comparison tables with all metrics, including the ones where your chosen model lost
24. End-to-end walkthrough on three contrasting personas
25. Limitations section — write this properly, it is the section that most distinguishes a serious project
26. Word-format project report

---

## Part 5 — Risks to Manage Early

| Risk | Mitigation |
|---|---|
| Genuine-label subset too small after filtering `Predicted_*` | Check the count in Stage 1, before designing around it. If it is too small, use the `Predicted_*` rows as a clearly-labelled auxiliary set with the limitation documented. |
| LSTM fails to beat the naive baseline | Expected. Plan to report it as a finding; do not silently switch to price-level RMSE to manufacture a win. |
| Mean-variance produces 100% single-asset allocations | Shrinkage plus box constraints from day one, not as a later patch. |
| Gemini invents a number | Structured output with a strict schema; validate every numeric field against the computed dictionary and reject on mismatch. |
| Every UI interaction re-runs the whole graph | Models loaded once at FastAPI startup; graph results cached server-side on a profile hash; TanStack Query handles client-side caching and deduplication. |
| Frontend and backend types drift apart | Generate TypeScript from the OpenAPI schema in a build step. Never hand-write an interface that mirrors a Pydantic model. |
| Financial logic leaks into React | The frontend displays numbers and never computes them — the same rule that applies to the LLM. No percentage arithmetic in components. |
| Compliance layer becomes advisory rather than binding | Compliance returns a hard verdict that gates output; the explanation node can never run on a rejected recommendation. |

---

## Part 6 — Training Inventory

Every candidate is trained, evaluated and serialized — not described and skipped. The comparison tables in the report must be produced from real runs.

### 6.1 Risk Classification — 4 models trained

| Model | Library | Hyperparameter search | Notes |
|---|---|---|---|
| Logistic Regression | scikit-learn | `C` ∈ {0.01, 0.1, 1, 10}, L2, multinomial | Baseline; report it even though it loses |
| Random Forest | scikit-learn | `n_estimators`, `max_depth`, `min_samples_leaf`, `max_features` | `class_weight='balanced'` |
| XGBoost | xgboost | `learning_rate`, `max_depth`, `subsample`, `colsample_bytree`, `n_estimators` | `sample_weight` for imbalance |
| MLP | TensorFlow | 2 hidden layers, `units`, `dropout`, early stopping on val macro-F1 | Expected to lose; the result is the point |

Shared protocol: stratified 5-fold CV, identical folds across all four, `GridSearchCV` or `RandomizedSearchCV` for the tree models, fixed `random_state`. Record macro-F1, per-class recall, confusion matrix, and fit time for each. Serialize all four, not just the winner — the report needs them, and a reviewer may ask to see the loser's confusion matrix.

Handle imbalance with class weights rather than SMOTE as the default. Synthetic minority samples in a financial-suitability context create customers who do not exist; if you use SMOTE, run it *inside* the CV fold and report both variants.

### 6.2 Expense Segmentation — 3 models trained

| Model | Sweep | Selection criterion |
|---|---|---|
| K-Means | k ∈ 2…10 | Silhouette, with elbow as supporting evidence |
| Gaussian Mixture | k ∈ 2…10 × `covariance_type` ∈ {full, tied, diag, spherical} | BIC |
| Agglomerative (Ward) | k ∈ 2…10 | Silhouette; dendrogram as visual justification for k |

Clustering models are fitted and **serialized**, not refit per request — a new customer must land in the same cluster space every time. Fit the scaler on training data only and pickle it alongside.

### 6.3 Behaviour Detection — 2 models trained

| Model | Fitted parameters |
|---|---|
| Isolation Forest | `n_estimators`, `contamination` ∈ {0.01, 0.05, 0.1}, `max_samples` |
| Rolling z-score / CUSUM | Window length and threshold calibrated on the data, not hard-coded |

The statistical detector has no learned weights but still requires a calibration run. Document the chosen window and threshold with the evidence behind them.

### 6.4 Market Models — 5 models × 5 assets = 25 fits

Assets: `^IXIC`, `^NDX`, `QQQ`, a bond proxy, a gold proxy.

| Model | Library | Fitted on |
|---|---|---|
| Naive random walk | — | Implemented as a model object so it enters the comparison on equal terms |
| ARIMA | statsmodels | Order selected by AIC over a `(p,d,q)` grid |
| GARCH(1,1) | arch | Maximum likelihood on returns |
| LSTM | TensorFlow | Window length ∈ {20, 40, 60}, units, dropout, early stopping |
| GRU | TensorFlow | Same grid as LSTM |

**Non-negotiable: walk-forward validation, never a shuffled split.** A random train/test split on time series leaks the future into the past and will produce results good enough to look fraudulent. Use expanding-window splits with a fixed embargo gap.

Targets are **returns and volatility, not price levels.** Fit the scaler on each training window only and refit it per fold.

### 6.5 Not Trainable — Benchmarked Instead

Three components have no training step. That is their nature, not an omission, and each still gets quantitative evaluation.

| Component | Evaluation method |
|---|---|
| MVO / HRP / 1/N | Rolling out-of-sample backtest: annualized return, volatility, Sharpe, max drawdown, turnover |
| Goal mathematics | Unit tests against hand-computed and spreadsheet-verified values |
| Compliance rules | One unit test per rule, plus adversarial cases where the LLM attempts to bypass a rule |

The portfolio backtest is the closest thing to training here, and it is where 1/N may beat your optimizer. Run it honestly.

### 6.6 Artifacts and Reproducibility

```
models/
  risk/          logreg.pkl  rf.pkl  xgb.pkl  mlp.keras  preprocessor.pkl
  expense/       kmeans.pkl  gmm.pkl  ward.pkl  scaler.pkl
  behaviour/     iforest.pkl  thresholds.json
  market/        {ticker}/  arima.pkl  garch.pkl  lstm.keras  gru.keras
  metrics.json   every metric from every run, keyed by model and version
```

Seed everything. Log library versions. `metrics.json` is what the report tables are generated from, so nothing gets retyped by hand.

**Compute.** All of this runs on CPU. The tree models and clustering finish in seconds; LSTM and GRU take a few minutes per asset. No GPU required, and no Colab dependency.

---

## Disclaimer to Carry Through the System

This is an educational decision-support prototype, not licensed financial advice. Market data is historical and not a forecast. FAR-Trans is research data from a European institution and does not represent the deployment population. Kaggle profile data is synthetic. Production deployment would require review against applicable financial-advice regulation, suitability obligations, data-protection law, and data-provider terms.

---

## Addendum — Extensions Beyond the Original Plan

This document is the original methodology specification and is deliberately
left as written. Work added after it — the household model and its financial
records — is specified by ADRs rather than by edits to the methodology above:
household identity and membership (ADR-031, Phase 32), household financial
source records (ADR-032, Phase 33), the read-only household financial summary
(ADR-033, Phase 34), optional factual metadata on those records (ADR-034,
Phase 35), and household goals as stored facts (ADR-035, Phase 36). None of these changes any methodology in Parts 0-6: no household
figure feeds the risk, expense, behaviour, market or portfolio models, the goal
engine, or compliance.
