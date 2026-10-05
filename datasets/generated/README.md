# WealthPilot AI — Synthetic ML Training Dataset

> **This dataset is synthetic and must not be represented as empirical customer
> financial data.** It is not real customer data. No row describes a real person.

- **Generator:** `scripts/generate_wealthpilot_synthetic_dataset.py`
- **Validator:** `scripts/validate_synthetic_training_dataset.py`
- **Decision record:** `docs/DECISIONS.md` ADR-039
- **Seed:** 42
- **Metadata:** `wealthpilot_training_metadata.json`, with counts, missing-value
  rates, label distributions, method, leakage controls, validation result and
  per-file SHA-256

## Why it exists

It gives WealthPilot's ML components a large, fully known dataset for training
experiments, evaluation and research:

- risk classification;
- expense segmentation;
- behaviour-anomaly detection;
- goal feasibility.

The real sources are small, and the two unsupervised components have no ground
truth at all. Here every target, and how it was produced, is known.

It is **not wired into any existing training script**. Training a production
model on it would be a new, separate decision.

## Separate from everything else

| Source | Where | Relationship |
| --- | --- | --- |
| FAR-Trans (real, anonymised) | `datasets/raw/FAR-Trans/` | Not used, copied or modified. Only its file *format* and column vocabularies are mirrored. The validator confirms no ID overlap and unchanged raw files. |
| Kaggle personal finance | `datasets/raw/kaggle/` | Not used, copied or modified. Only its file format and ratio definitions are mirrored. |
| Demo data | `demo_data/` | Not used, not merged. The demo personas are never training data. |

The three shapes below are views of **one synthetic population**. That is not a
linkage of the real FAR-Trans and Kaggle datasets, which stay separate
(ADR-010).

## Files

The CSVs are git-ignored. Regenerate them, byte-identically, with
`python scripts/generate_wealthpilot_synthetic_dataset.py`.

| File | Rows | Columns |
| --- | ---: | ---: |
| `wealthpilot_customer_training.csv` | 100,000 | 76 |
| `wealthpilot_transactions_training.csv` | 2,642,361 | 13 |
| `wealthpilot_goals_training.csv` | 325,290 | 23 |
| `far_trans_format/customer_information.csv` | 100,000 | 6 |
| `far_trans_format/asset_information.csv` | 300 | 9 |
| `far_trans_format/transactions.csv` | 2,642,361 | 9 |
| `far_trans_format/close_prices.csv` | 469,800 | 3 |
| `kaggle_format/synthetic_personal_finance_dataset.csv` | 100,000 | 20 |

About 619 MB in total. All files are UTF-8, comma-delimited, with one header row
and empty cells for missing values.

**Format copies.** The existing loaders read these through their existing
data-directory argument, so no training code changes:

- `load_far_trans_tables(dir)` → `engineer_features`, then `build_monthly_panel`;
- `load_kaggle_primary(dir)` → `engineer_expense_features`.

The validator runs all of them.

- **FAR-Trans copy:** one genuine-labelled row per customer, dated at
  `feature_cutoff_date`. `markets.csv` and `limit_prices.csv` are not produced,
  because no loader reads them.
- **Kaggle copy:**
  - It keeps Kaggle's own ratio definitions: `debt_to_income_ratio` is monthly
    EMI ÷ monthly income, and `savings_to_income_ratio` is savings ÷ annual
    income.
  - It keeps the format's fixed `_usd` column names, but the amounts are this
    population's **EUR** amounts; no exchange conversion is applied.
  - `gender`, `job_title`, `credit_score`, `region`, `loan_term_months` and
    `loan_interest_rate_pct` are left empty, because this population does not
    have them.

## Customer file: feature groups

IDs run `SYN000001`–`SYN100000`. They never overlap FAR-Trans or demo IDs.

| Group | Columns |
| --- | --- |
| Identity / time | `customer_id`, `data_source` (`synthetic_generated`), `onboarding_date`, `feature_cutoff_date` |
| Existing risk-model attributes | `customer_type` (Mass / Premium / Professional), `investment_capacity` (FAR-Trans bands CAP_LT30K … CAP_GT300K) |
| A. Demographics | `age`, `dependents`, `employment_status` (Kaggle vocabulary), `employment_years`, `marital_status`, `education_level` (Kaggle vocabulary) |
| B. Income | `annual_income`, `monthly_income` (= annual ÷ 12, 2 dp), `income_growth_rate`, `income_stability_score`, `income_source_count` |
| C. Expenses | `monthly_expenses` = the sum of housing, food, transport, healthcare, education, utilities, insurance, discretionary and other; `monthly_essential_expenses` = the first seven |
| D. Debt | `total_debt` = credit card + personal + home + auto; `monthly_emi`; `credit_card_limit`; `debt_to_income_ratio` (total debt ÷ annual income); `emi_to_income_ratio`; `credit_utilization` (card debt ÷ limit, empty with no card) |
| E. Savings | `cash_savings`, `monthly_savings` (= income − expenses − EMI; negative means a deficit), `savings_rate`, `liquid_assets` (= cash + the cash share of the portfolio), `investment_contribution` (≤ positive savings), `savings_stability`, `investment_portfolio_value` |
| F. Emergency fund | `emergency_fund_required`, from the **production** `assess_emergency_fund` (6 × essential expenses); `emergency_fund_target_months` (6); `emergency_fund_months` (liquid ÷ essential); `emergency_fund_status` (sufficient / insufficient) |
| G. Financial health | `expense_to_income_ratio`, `savings_to_income_ratio` (cash ÷ annual income), `liquidity_ratio` (liquid ÷ monthly expenses), `discretionary_expense_ratio`, `investment_ratio` |
| H. Risk | `risk_tolerance_score`, `risk_capacity_score`, `investment_horizon_years`, `financial_stability_score`, `investment_experience`, `loss_tolerance` |
| I. Allocation | `equity_pct`, `bond_pct`, `gold_pct`, `cash_pct`, `other_pct` (sum exactly 100.00) |
| J. Behaviour (point-in-time) | `trade_count`, `buy_value`, `sell_value`, `portfolio_turnover` (sell ÷ buy value), `average_transaction_value`, `investment_frequency` (trades per observed month), `behaviour_volatility` (coefficient of variation of monthly trade counts) |
| Targets | `risk_label`, `expense_segment`, `behavior_anomaly`, `behavior_anomaly_month` |

Every sum and ratio is computed from the stored, rounded values, so the
validator can recompute it exactly.

## Transactions and goals

**Transactions.** Columns: `transaction_id`, `customer_id`, `transaction_date`,
`transaction_type` (Buy / Sell), `buy_sell_indicator` (+1 / −1), `asset_type`
(Stock / Bond / Fund), `asset_subtype`, `asset_id`, `quantity`, `price`,
`transaction_value`, `portfolio_weight`, `channel`.

- Rows are in date order.
- `transaction_value` = quantity × price, where price is that day's synthetic
  market close.
- Every sell closes part or all of an earlier buy lot, so holdings are never
  negative.
- `portfolio_weight` is the asset's share of the customer's cumulative purchase
  value up to and including that transaction. It looks backward only.
- Activity: 10% of customers have 4 or fewer trades, the median is 14, 10%
  have 73 or more, and the maximum is a few hundred.

**Goals.** 1–6 goals per customer, each goal type at most once:

- Emergency Fund, Retirement, Education, Home, Vehicle, Travel, Wealth
  Creation, Other.

Columns:

- identity: `goal_id`, `customer_id`, `goal_type`, `priority`;
- timing: `analysis_date` (the customer's cutoff), `target_date`,
  `target_year`, `years_remaining`, `periods_remaining`;
- amounts: `target_amount`, `current_amount`, `monthly_contribution`;
- assumptions: `annual_return_rate`, `annual_inflation_rate`,
  `contribution_periods_per_year`;
- engine outputs: `inflation_adjusted_target_amount`,
  `required_monthly_contribution`, `contribution_gap`, `goal_status`;
- simulation: `monte_carlo_simulations`, `monte_carlo_success_probability`,
  `goal_feasibility`.

Rules:

- `goal_status` is Achieved when `current_amount` is at least the
  inflation-adjusted target, and only then may it exceed `target_amount`.
- Paused means not achieved and no monthly contribution.
- Otherwise the status is Active.
- A customer's contributions never total more than their positive monthly
  savings.

## Targets and how they were generated

Hidden (latent) variables are drawn first for each customer: wealth, prudence,
risk appetite, leverage propensity, trading activity, stability and
impulsivity. Every observed column is then derived from them with its own
noise. No target is ever computed from an observed column.

| Target | Supports | Generation | Distribution |
| --- | --- | --- | --- |
| `risk_label` | risk classification (the existing 4 classes) | Ordinal thresholds on 0.60 × risk appetite + 0.25 × capacity + 0.15 × horizon + N(0, 0.55). Shares follow FAR-Trans's genuine distribution. | Income 42,000 · Balanced 33,000 · Conservative 13,000 · Aggressive 12,000 |
| `expense_segment` | evaluating the existing (unsupervised) expense clustering | Drawn from prudence and leverage *before* the expense, debt and savings columns it shapes. Labels describe ratio profiles, in the existing model's labelling style. | moderate-expense-low-leverage-moderate-savings 35,457 · low-expense-low-leverage-higher-savings 30,546 · high-expense-low-leverage-lower-savings 21,900 · moderate-expense-high-leverage-lower-savings 12,097 |
| `behavior_anomaly` | evaluating the existing (unsupervised) behaviour detector | The top 2.5% by impulsivity + noise. Each gets one month-long burst of 10–30 unusually large buys in its least-used asset class, inside its observation window and after at least 4 months of history. `behavior_anomaly_month` gives the month. | 0: 97,500 · 1: 2,500 |
| `goal_feasibility` | goal analysis | The **production goal engine** (`core/goals.py`): `analyze_goal_funding` → `run_goal_monte_carlo` → `classify_feasibility`. It uses 500 paths per goal instead of the app's 10,000, and a return series built the way the app builds its own. | Not Feasible 174,931 · Feasible 123,067 · At Risk 27,292 |

**Two realism devices keep bursts from giving the anomalies away:**

- 6% of normal customers get an ordinary busy month;
- high-activity customers trade in clusters.

**Goal targets** are the customer's funding capacity times a log-normal
"ambition" factor, kept inside type-plausible bounds. The Emergency Fund goal
instead targets the production requirement itself. Whether a goal is feasible
is then decided by the engine alone.

**No train/test files are produced.** If you split:

- split customers **by `customer_id`**, grouped, so a customer never appears on
  both sides;
- split transactions **by date**, time-ordered, never by random shuffling.

## Leakage controls

- **Targets come from hidden variables.** Every observed feature carries
  independent noise.
- **No single feature gives a target away.** In the final dataset:
  - No single customer feature predicts `risk_label` above 70%. The strongest is
    `equity_pct` at 49.0%, against a 42% majority baseline.
  - No single feature separates `behavior_anomaly` with an AUC above 0.995. The
    strongest is `investment_frequency` at 0.950.
- **Behaviour features are point-in-time.** They use only transactions on or
  before `feature_cutoff_date`, the same rule the risk pipeline applies to
  FAR-Trans. 92,475 customers have later activity that is deliberately excluded.
  The validator recomputes every feature and checks this.
- **Some columns must never be features:**
  - the targets: `risk_label`, `expense_segment`, `behavior_anomaly`,
    `behavior_anomaly_month`, `goal_feasibility`,
    `monte_carlo_success_probability`;
  - the goal engine's own outputs: inflation-adjusted target, required
    contribution, contribution gap and `goal_status`.
- **Expense segments are defined by design on the income ratios** (a
  segmentation target), so those ratios are expected to separate them.

## Missing values

Missing values are empty cells, never 0.

- **Random missingness** is used only in leaf columns that nothing else is
  computed from. Rates:

  | Column | Missing |
  | --- | ---: |
  | `income_growth_rate` | 6.0% |
  | `investment_experience` | 5.0% |
  | `savings_stability` | 4.1% |
  | `employment_years` | 4.0% |
  | `income_stability_score` | 3.0% |
  | `loss_tolerance` | 3.0% |
  | `education_level` | 3.0% |
  | `income_source_count` | 2.0% |
  | `marital_status` | 1.9% |

- **Structurally empty values:**
  - `credit_utilization` for customers with no credit card (16.5%);
  - `behavior_anomaly_month` where `behavior_anomaly` is 0.
- **Never missing:** identifiers, dates, targets, transactions and goals.

## Validation

Run `python scripts/validate_synthetic_training_dataset.py`. It exits 0 on
success and 1 on any failure; the generator also runs it automatically. It
checks:

- **Format:** UTF-8, a single header, no duplicate columns, no embedded
  newlines, no NaN/Infinity/null strings, no formulas.
- **Counts and uniqueness:** row and column counts, duplicate rows, null rates,
  and unique IDs.
- **Consistency:** 26 customer consistency rules.
- **Transactions:** value = quantity × price = the day's close, holdings never
  negative, date order, and trading after onboarding only.
- **Point-in-time features.**
- **Goals:** goal rules and the production thresholds, plus a 300-goal re-run
  through the production engine.
- **Referential integrity** across all files.
- **Leakage limits.**
- **Existing pipelines** run on the format copies.
- **Raw training data** matches the recorded SHA-256 hashes.

## Limitations

- **Synthetic realism is designed, not observed.** Distributions,
  correlations and the market are modelling choices documented here and in the
  generator. Nothing is calibrated to real customers beyond FAR-Trans's label
  shares and the vocabularies.
- **The market is synthetic.** 300 assets follow three factors, with a 2020
  crash and a 2022 bear market and rate shock. It is not real price history.
- **Goal feasibility uses 500 paths, not 10,000.** Probabilities are coarser
  than the application's, though the method and thresholds are identical.
  "At Risk" (probability 0.50–0.79) is a narrow band, hence its 8.4% share.
- **Planted labels are only as meaningful as their construction.** Evaluating
  the unsupervised models against them measures agreement with *this*
  generator's definitions.
- **One currency.** EUR throughout, including the Kaggle copy's `_usd` columns.
