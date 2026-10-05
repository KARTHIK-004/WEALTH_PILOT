# WealthPilot AI — Demo Dataset

> **This dataset is NOT a replacement for FAR-Trans or the Kaggle training
> dataset and MUST NOT be used as additional ML training data.**

The demo data comes in two forms:

- **`wealthpilot_complete_demo_dataset.csv`**: the whole demo population in a
  single flat table, one row per demo customer. It is for reading, presenting
  and testing, and opens in Excel, Google Sheets, pandas or VS Code. See
  [section 13](#13-the-single-file-csv).
- **The JSON files below**: the seed input that `seed_demo_data.py` sends
  through the API. See sections 1–12.

## 1. What it is

This folder holds the complete synthetic demo population for WealthPilot AI:

- four individual personas, each with a profile, questionnaire answers,
  financial inputs and goals;
- one family household with members, income, expenses, assets, liabilities
  and goals;
- scenario inputs for the Scenario Simulator;
- the high-level outcome each persona and the household is expected to show.

It is the single source of this data. The seed script reads it from here, and
it is no longer written inline in Python.

## 2. Why it exists

The dataset lets the whole application be demonstrated, tested, presented and
defended in a viva, from login through the final explanation. It is the same
every time and can be re-created on any environment:

- **Individual:** approved, savings first, compliance rejected, and pending
  information.
- **Family:** a two-member household with its financial summary and goals.

## 3. Synthetic, demo-only

Every file is labelled `"source": "synthetic_demo"`.

- **Invented, clearly-labelled values:** names, ages, incomes, goals, inputs
  and household records. They contain no real email, phone number, government
  ID or account number.
- **Links to FAR-Trans rows:** personas A–C are linked to an existing,
  anonymised FAR-Trans customer through `risk_data_link`. That is the only way
  the approved architecture can give a new identity a genuine model-computed
  risk result. The link reuses that customer's already-present trading
  history. It invents none, and it copies no personal data.
- **Currency:** amounts are EUR, the project's single currency.
- **Nothing computed is stored.** The dataset holds no risk category,
  Monte Carlo probability, emergency-fund status, portfolio weight, compliance
  decision, recommendation or household summary. The application computes
  every one of them when the data is seeded and analysed.

## 4. Individual personas

| Key | Customer name | Shows | Financial inputs | Risk link |
| --- | --- | --- | --- | --- |
| `WPDEMO-A` | WealthPilot Demo — Complete | approved: portfolio, recommendation, compliance PASS, explanation | provided (sufficient emergency fund) | FAR-Trans |
| `WPDEMO-B` | WealthPilot Demo — Savings | savings first: insufficient emergency fund, no portfolio weights | provided (insufficient emergency fund) | FAR-Trans |
| `WPDEMO-C` | WealthPilot Demo — Compliance | compliance REJECT (`emergency_fund_savings_first`, fail-closed), no recommendation, no explanation | **not provided** (`null` + reason) | FAR-Trans |
| `WPDEMO-D` | WealthPilot Demo Customer | pending information: no risk label, so nothing downstream | **not provided** (`null` + reason) | none (`null` + reason) |

A, B and C are owned by the seed (`owned_by_seed: true`).

D is Phase 24's canonical demo customer. The seed creates it only if it is
missing. The frontend fallback (`lib/demo-customer.ts`) may also create it,
with the same values. `reset` never deletes it.

In the current development database these personas are customers 29107,
29108, 29109 and 29096. The dataset stores **no numeric id**: every persona
is found by its exact name.

## 5. Family persona

`WPDEMO-FAM` is "WealthPilot Demo Family":

- **Members:** the primary is persona B (`self`/`primary`) and the spouse is
  persona C (`spouse`/`member`).
- **Records:** 5 income, 8 expenses, 4 assets, 2 liabilities and 3 goals.

The records are chosen to show the household summary's rules:

- yearly amounts count as amount / 12 per month;
- one-time amounts stay out of the recurring view;
- an inactive record is stored but not counted;
- essential expenses are the emergency-fund basis;
- liquid assets are the emergency-fund balance;
- a liability recorded at 0 sits beside a monthly payment that was never
  recorded, and the two are never conflated.

Household records are stored source data, and household goals are stored facts
with no goal math. Household membership is identity only: no household figure
reaches any individual analysis, and no member sees another member's
individual data. Personas A and D belong to no household.

## 6. Structure

```text
demo_data/
├── README.md               this file
├── wealthpilot_complete_demo_dataset.csv
│                           the single flat table (section 13)
├── manifest.json           version, counts, per-file SHA-256, expected outcomes,
│                           raw-training-data guard (generated -- do not hand-edit)
├── profiles/               one file per persona: identity, purpose, risk_data_link,
│                           and `profile` -- the exact POST /api/profiles body
├── questionnaire/          one file per persona: ANSWERS only (question_number,
│                           option_key) + the position rule that chose them
├── financial_inputs/       one file per persona: the PUT .../financial-inputs body,
│                           or null + financial_inputs_unavailable_reason
├── individual_goals/       one file per persona: POST .../goals bodies
├── household/
│   ├── households/         the household name and its primary persona
│   ├── members/            membership (relationship / role) by persona key
│   ├── income/ expenses/ assets/ liabilities/ goals/
│   │                       the exact POST /api/households/{id}/<resource> bodies,
│   │                       plus the field that identifies each record
├── scenarios/              Scenario Simulator inputs (POST /api/scenarios/compare)
├── expected_results/       expected contract-level states per persona / household
└── seed/seed_plan.json     which file feeds which API call, in order
```

In each file, the API payload is a nested object: `profile`, `answers`,
`financial_inputs`, `goals` or `records`. It is sent to the API unchanged and
uses only fields that API schema defines. Everything outside it is dataset
metadata (`demo_key`, `purpose`, `source` and so on) and is never stored.

**Questionnaire definition vs answers.** The questions and options are the
application's own questionnaire. `GET /api/questionnaire` serves them from
`datasets/raw/FAR-Trans/questionnaires.csv`, and they are never copied here.
This folder holds only each persona's answers.

**Scenarios.** The simulator lets a client vary one thing: the portfolio
strategy (default, `mvo`, `hrp` or `equal_weight`). The five scenarios use
exactly that. The application computes each side's result.

Four other what-ifs cannot be expressed through the existing contract:

- a lower monthly contribution;
- a higher monthly contribution;
- increased expenses;
- a changed goal date.

They are listed under `not_supported_by_the_contract` with the reason.
Contribution, expenses and goal dates are stored inputs, not simulator
parameters.

**Transactions: none.** The application cannot consume synthetic
transactions. Risk and behaviour features are read only from the immutable
FAR-Trans CSVs, never from the database `transactions` table, so synthetic
rows would change nothing. They are left out rather than added for
appearance.

## 7. How to seed it

All commands run from `backend/` with the virtualenv active. Add
`--in-process` to drive the real app in-process through FastAPI's TestClient
against `DATABASE_URL`, so no server needs to be running. Without it, the
script talks to a running backend (`--base-url`, default
`http://127.0.0.1:8000`).

```bash
python scripts/seed_demo_data.py setup          # personas A–D (+ their analyses)
python scripts/seed_demo_data.py setup-family   # the family household
```

Seeding is **idempotent**. Each step reads what exists and writes only what
is missing, so it never overwrites a stored value. A second run creates
nothing. See `seed/seed_plan.json`.

It uses the real public API throughout. The one exception is
`risk_inputs.external_customer_id`: no API exposes that field, so it is set by
a single direct write, only for a persona the seed has just created.

## 8. How to validate it

```bash
python backend/scripts/validate_demo_data.py          # static; exits 1 on any failure
python scripts/seed_demo_data.py verify               # live: stored data + expected states
python scripts/seed_demo_data.py verify-family        # live: household + authorization
```

The static validator needs no database. It checks:

- the files, their format and the `synthetic_demo` label;
- unique keys, names and links, and that every reference resolves;
- every payload against the real API request schemas, rejecting any field
  those schemas do not define;
- that a missing value is `null` with a reason, never zero;
- the answers against the live questionnaire and each persona's own rule;
- the household rules: exactly one primary, who is `self`; nobody else is
  `self`; no persona is in two households;
- the scenario payloads against the simulator contract;
- that no training or application code reads this folder;
- the manifest's counts and hashes, and the current Alembic head;
- that the raw training files still have the SHA-256 hashes recorded in the
  manifest.

After editing any data file, regenerate the manifest:

```bash
python backend/scripts/validate_demo_data.py --write-manifest
```

The validator refuses to write a manifest for data that fails any check.

## 9. How to reset only demo data

```bash
python scripts/seed_demo_data.py reset-family   # only the household matched by its exact
                                                # name AND its primary persona
python scripts/seed_demo_data.py reset          # the household first, then personas A, B, C
                                                # (exact names) and their own rows
```

Nothing else is ever deleted:

- persona D;
- any other customer, household or record;
- the raw datasets;
- the trained models.

There is no global reset.

## 10. Expected demo flows

The expected states are in `expected_results/`. `verify` checks them against
each persona's live, default analysis.

| Persona | `analysis_status` | Recommendation | Compliance | Explanation |
| --- | --- | --- | --- | --- |
| A | `approved` | `approved`, portfolio weights present | `PASS` | yes |
| B | `approved` | `savings_first`, no portfolio weights | `PASS` | yes |
| C | `rejected` | none | `REJECT`, rule `emergency_fund_savings_first` | none |
| D | `pending_information` | none | not evaluated (`null`) | none |
| Family | household summary and household goals available; 2 members; non-members get 403 | | | |

For B, the overall status is `approved`. Savings first is the
**recommendation's** status, not a separate overall status.

The expected results state only outcomes, available sections and rule
identities. They hold no financial number that could drift from the
application's own calculation.

Demo flows:

- **Individual demo login:** persona A. It runs from the dashboard through
  risk, goals, portfolio and recommendation to the explanation, the scenario
  simulator and agent activity.
- **Family demo login:** persona B, on the profile page with the household
  view open.
- **Personas B, C and D:** shown through the API or by the presenter, as
  documented in `docs/final_demo_script.md`.

## 11. Never use it for ML training

Nothing under `training/` may read this folder, and the validator fails if
any file does. None of it is ground truth:

- the personas are invented;
- A–C's risk inputs are existing FAR-Trans rows, already part of that
  dataset;
- no label here came from a real outcome.

Training on it would leak synthetic values into the models and double-count
FAR-Trans rows.

## 12. Relationship to FAR-Trans and Kaggle

- **FAR-Trans** (`datasets/raw/FAR-Trans/`) and **Kaggle**
  (`datasets/raw/kaggle/`) are the immutable raw training datasets. Nothing
  here modifies them.
- The manifest's `training_data_guard` records their SHA-256 hashes, and the
  validator fails if any raw file changes.
- The only link to FAR-Trans is by reference, for A–C: `risk_data_link` names
  an existing customer so the risk and behaviour models have genuine input.
- The questionnaire definition is read from FAR-Trans's questionnaire file.
- The Kaggle dataset is not linked to this data at all. It is a separate,
  unlinked population used only for expense-segmentation training.

## 13. The single-file CSV

**File:** `demo_data/wealthpilot_complete_demo_dataset.csv`, 4 rows × 88
columns.

### What it is

The CSV has one row per demo customer, exported from the live application on
2026-09-30. It shows the demo population and the results the application
computed for each persona in one table, for demonstration, testing and the
viva.

It is **synthetic demo data**. Every row carries:

- `data_source = synthetic_demo`
- `training_eligible = false`
- `dataset_purpose = demo_testing_presentation`

It is not a second financial system. Every value is copied from an API
response of the running application:

- profiles, questionnaire answers, financial inputs and goals;
- household membership and the household financial summary;
- each persona's stored analysis.

Nothing in it was typed by hand or calculated for the file. The application
remains the only calculation engine, and it does not read this CSV.

### Rows

| `demo_customer_id` | `demo_persona` | Customer | Household |
| --- | --- | --- | --- |
| 29107 | `APPROVED` | WealthPilot Demo — Complete | none |
| 29108 | `SAVINGS_FIRST` | WealthPilot Demo — Savings | 8, `primary` / `self` |
| 29109 | `COMPLIANCE_REJECTED` | WealthPilot Demo — Compliance | 8, `member` / `spouse` |
| 29096 | `PENDING_INFORMATION` | WealthPilot Demo Customer | none |

The ids are this environment's customer ids. Every row has
`demo_type = INDIVIDUAL`: each is one customer's own record.

The **family** (household 8, "WealthPilot Demo Family") appears on its two
members' rows:

- The household columns describe the **household**. They are repeated
  unchanged on each member row, never added together or split.
- They are not the member's own figures, and they never enter any individual
  analysis.
- For a customer in no household, every household column is empty.

### Column groups

Columns use the application's own field names and meanings.

| Group | Columns |
| --- | --- |
| Identity | `demo_customer_id`, `demo_persona`, `demo_user_name`, `demo_type`, `household_id`, `household_name`, `household_role`, `household_relationship`, `is_dependent` |
| Profile | `customer_type`, `age`, `employment_status`, `annual_income`, `investment_capacity` |
| Questionnaire | `questionnaire_completed`, `questionnaire_answers_recorded`, `questionnaire_questions_total` |
| Financial inputs | `currency`, `monthly_essential_expenses`, `current_liquid_assets`, `contribution_amount`, `annual_return_rate`, `annual_inflation_rate`, `contribution_periods_per_year`, `financial_inputs_unavailable_reason` |
| Emergency fund (individual analysis) | `emergency_fund_sufficient`, `emergency_fund_required_amount`, `emergency_fund_current_amount`, `emergency_fund_shortfall`, `emergency_fund_unavailable_reason` |
| Goals 1–3 | `goal_N_type`, `goal_N_target_amount`, `goal_N_target_date`, `goal_N_current_savings`, `goal_N_priority`, `goal_N_feasibility`, `goal_N_monte_carlo_success_probability`, `goal_N_unavailable_reason` |
| Risk | `risk_category`, `risk_confidence`, `risk_unavailable_reason` |
| Portfolio | `portfolio_weights_available`, `portfolio_strategy`, `qqq_weight`, `agg_weight`, `gld_weight`, `portfolio_expected_return`, `portfolio_expected_volatility`, `portfolio_sharpe_ratio` |
| Recommendation and compliance | `recommendation_status`, `recommendation_selected_strategy`, `compliance_decision`, `compliance_triggered_rules` |
| Analysis | `analysis_id`, `analysis_status`, `explanation_available` |
| Household summary | `household_recurring_monthly_income`, `household_recurring_monthly_expenses`, `household_monthly_cash_flow`, `household_total_assets`, `household_liquid_assets`, `household_outstanding_liabilities`, `household_net_position`, `household_emergency_fund_required`, `household_emergency_fund_shortfall`, `household_emergency_fund_status` |
| Demo purpose | `demo_description`, `expected_demo_flow`, `notes` |
| Dataset | `data_source`, `training_eligible`, `dataset_purpose` |

Goals are ordered by priority. No persona has a third goal, so the `goal_3_*`
columns are empty.

#### Where a column follows the application's name

Some column names differ from the ones first requested, so that no column
claims a meaning the application does not have:

| Requested | In the CSV | Why |
| --- | --- | --- |
| `monthly_income` | `annual_income` | The profile stores one income, which the app labels "Annual income". There is no monthly income field, and the value is not divided. |
| `risk_questionnaire_status` | `questionnaire_answers_recorded`, `questionnaire_questions_total` | No questionnaire status field exists. These are the counts `questionnaire_completed` is read from. |
| `emergency_fund_status`, `_required`, `_current` | `emergency_fund_sufficient`, `_required_amount`, `_current_amount` | The individual analysis's own fields. `sufficient` is true, false or empty (unknown). |
| `goal_N_name`, `_status`, `_probability` | `goal_N_type`, `_feasibility`, `_monte_carlo_success_probability` | Individual goals have a type, not a name. The status is the backend's feasibility label. |
| `risk_level` | `risk_category` | The risk model's output field. |
| `portfolio_available` | `portfolio_weights_available` | True only when the portfolio has weights. |
| `recommendation_type` | `recommendation_selected_strategy` | The recommendation's own field (`mvo`, or empty for savings first). |
| `compliance_status` | `compliance_decision`, `compliance_triggered_rules` | `PASS` / `WARN` / `REJECT`, plus the ids of the rules that triggered. |
| `household_monthly_income`, `_expenses` | `household_recurring_monthly_income`, `_expenses` | The summary counts recurring amounts only. One-time amounts are separate, and yearly amounts count as amount / 12. |
| `household_cash_flow` | `household_monthly_cash_flow` | The summary's `cash_flow.monthly`. |
| `household_total_liabilities` | `household_outstanding_liabilities` | The summary's `liabilities.outstanding`. |
| `household_emergency_required`, `_status` | `household_emergency_fund_required`, `_status` | The summary's `emergency_fund.required` / `.status`. |

### Missing values and zeros

- **Empty cell:** the application has no value. It is unknown, not provided,
  not evaluated, or not applicable (a non-member's household columns, a third
  goal).
- **Reason columns:** where the application gives a reason for a missing
  value, the paired `*_unavailable_reason` column carries it verbatim.
- **Not evaluated:** persona D's emergency fund, goal results, compliance,
  portfolio and recommendation were never evaluated. The analysis stops at
  `pending_information`, so those cells are empty. Its `notes` says so.
- **`0`** is always a genuine, recorded zero. Examples: 29107's
  emergency-fund `shortfall` of 0, and 29108's Emergency Fund goal
  probability of 0. A missing value is never written as 0.
- **Never used as a missing marker:** `null`, `None`, `NaN`, `N/A` and `-`.
- **Booleans** are `true` / `false`.

### Numbers and currency

- **Currency:** all amounts are **EUR**, the project's single currency. The
  application formats every amount as €. No schema stores a currency, so the
  `currency` column states that convention. There is no conversion, and no
  INR anywhere.
- **Numbers are exactly as stored, unrounded.** Rates, probabilities,
  confidences and weights are fractions: `0.07` means 7%, and a goal
  probability of `0.9411` is shown as 94.1%.
- **One stored value looks odd.** The approved portfolio's AGG weight is
  stored as `1.6653345369377348e-16`, a floating-point value the app displays
  as 0%. It is copied as stored.

### Format

- UTF-8 with a byte-order mark, so Excel shows the em dashes in the names
  correctly.
- Commas as delimiters, a quote only where a field needs one, CRLF line
  endings.
- One header row, no line breaks inside cells, no formulas.

In pandas, read the file with `pd.read_csv(path)`; empty cells become `NaN`.
Add `keep_default_na=False` to keep them as empty strings.

### Validate it, or regenerate it

```bash
python scripts/validate_demo_dataset.py               # no database; exit 0 valid, 1 invalid
python scripts/validate_demo_dataset.py --regenerate  # re-export from the live app, then validate
```

The validator checks the following:

- **File and format:** the header and column order, no duplicate columns,
  consistent field counts, UTF-8 with a BOM, and no line breaks, formulas,
  null-like tokens or credentials.
- **Rows:** the four personas, each exactly once with its canonical id, and
  no duplicate ids.
- **Household 8:** 29108 is `primary` / `self` and 29109 is `member` /
  `spouse`, with identical household values on both rows.
- **Dataset labels:** the three columns on every row.
- **Missing values:** a value is empty wherever its reason column is filled
  or the JSON package records it as not provided.
- **Agreement with the JSON package:** profiles, financial inputs, goals and
  the expected analysis states.
- **Training data:** the raw files still match the hashes in `manifest.json`.

`--regenerate` reads the application in-process against `DATABASE_URL`, with
no server needed. It uses only read requests plus `POST /api/analysis`, which
returns each persona's stored analysis while the profile is unchanged.

### Never for ML training

This file must never be used to train, tune or evaluate any model:

- **The identities are invented.**
- **Its results are the application's own model outputs.** Training on them
  would teach a model its own predictions, a form of data leakage.
- **Personas A–C's risk inputs are existing FAR-Trans rows.** Adding them again
  would count those customers twice.

`training_eligible = false` marks every row. Nothing under `training/` reads
`demo_data/`, and the demo-package validator fails if anything does.
