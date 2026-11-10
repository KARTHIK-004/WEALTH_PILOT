# WealthPilot AI — Viva Demonstration Runbook

> **Phase 31**: the click-by-click script with every verified number is now
> `docs/final_demo_script.md`, and concise viva answers are in
> `docs/final_viva_talking_points.md`. This runbook remains the longer
> narrative and its "What NOT to say" list still applies.

This runbook sequences a live walkthrough of WealthPilot AI using the
real, unmodified application and the demo customer population documented
in `reports/demo_dataset_catalog.md`. Every screen and result named below
was directly, live-verified against the real backend while writing this
runbook — nothing here is aspirational.

**Read this first — the state of this system changed with Phase 28**:
earlier versions of this runbook said no customer could ever reach an
"approved" recommendation, a genuine, structural, disclosed limitation at
the time. Phase 28 closed the two gaps that caused that
(`reports/phase28_financial_input_savings_first_report.md`): a real
financial-input data contract now lets emergency-fund and goal
assumptions be supplied, and a compliance-rule fix correctly recognizes a
legitimate savings-first proposal as compliant rather than invalid. The
default demo customer now reaches a REAL `approved` result with a REAL
optimized portfolio. **Say so plainly — do not undersell it, and do not
claim more than what is shown**: every number on screen is still read
directly from a live API response, nothing is fabricated, and compliance
is exactly as binding as before (see "Why compliance cannot be bypassed"
below) — the fail-closed REJECT path still exists and is still
demonstrable (see step 12).

## The full-pipeline demo (added 2026-10-23)

Every page shows real results for one persona: **WealthPilot Demo — Full Pipeline** (`WPDEMO-E`).
Sign in with **Use Full Pipeline Demo** (a third demo entry beside Individual and Family). It finds the
persona by its exact name and never creates it; if it has not been seeded you get a message naming the
command (`seed_demo_data.py setup`). What it shows, as computed by the application: a Balanced risk
profile, three goals with feasibility results, twelve reported months of behaviour findings, an
equal-weight recommendation that passed all compliance rules, and the plain-language explanation
(the written Gemini explanation appears only where a Gemini key is configured). Data and the local
set-up order are in `demo_data/README.md` sections 4 and 7.

A page that says "not available yet" for another profile is the designed pending state, not a fault:
the risk model reads a FAR-Trans history that only personas A, B, C and E are linked to.

**Household, debts and spending for this account (ADR-051).** `seed_demo_data.py setup` also builds E's household ("WealthPilot Demo — Full Pipeline Household": E and its partner F):
open **Customer Profile → Household** for the members, the financial summary (recurring income 155,000, spending 96,000, cash flow 59,000, net position 1,720,000, a sufficient
emergency fund) and the Income / Expenses / Assets / Liabilities / Goals tabs, where the loans and EMIs live (car loan, education loan, a credit card at a stated 0). **Financial Health**
shows the twelve months' spending findings under "Spending and expenses", and its "Debt & Commitments" card says an individual has no recorded loans (the household's liabilities are
on the profile page). A spending *pattern* (the expense-persona model) is never available for a FAR-Trans customer, by design.

**"0 reported months", no household, or "Spending pattern not available" on the Full Pipeline demo.** Check, in this order: (1) the header names "WealthPilot Demo — Full Pipeline" — "Sign In"
and "Use Individual Demo" open persona A, which has no months and no household by design; (2) `python scripts/seed_demo_data.py verify` against the SAME database the backend uses prints, for
persona E, "monthly records match the dataset (12 months)" and a passing household section — if not, run `setup` there (it only adds what is missing and never overwrites an edit);
(3) a second customer with the exact same name makes the lowest id win in both the seed and the sign-in lookup — `verify` prints a NOTE when it finds one.

**A local SQLite demo with two-member households.** `scripts/local_synthetic_backend.py` now gives SQLite the same partial unique index PostgreSQL has ("one PRIMARY member per household"); a
`.db` file made by an older launcher is repaired when the launcher starts. Before that fix SQLite allowed only one member per household, so `setup-family` failed on a local database.

## Reaching each demo customer

**Three things changed since this runbook was first written, each
documented in full in its own report — read this section fresh, do not
rely on memory of an earlier version:**

1. **The post-login profile-selection UX fix**
   (`reports/post_login_profile_flow_report.md`) removed the manual
   "enter a numeric profile id" header control entirely. There is no
   customer-switching UI anywhere in the authenticated app — by design,
   not an oversight. Every authenticated session shows exactly ONE
   customer, resolved automatically at login.
2. **The Live Analysis Flow phase**
   (`reports/live_analysis_flow_fix_report.md`) changed WHICH customer
   the individual demo (the button now labelled "Use Individual Demo")
   resolves to: it now prefers the real,
   FAR-Trans-linked **"WealthPilot Demo — Complete"** persona over Phase
   24's original, linkage-less **"WealthPilot Demo Customer"** — falling
   back to the original customer only if "Complete" has not been seeded.
3. **Phase 28** gave "WealthPilot Demo — Complete" (and a second persona,
   "WealthPilot Demo — Savings") real financial inputs, so the pipeline
   now runs all the way through to a genuine `approved` result for the
   default demo account.

- **Demo Account** (`demo@wealthpilot.ai` / `WealthPilotDemo@2026`,
  unchanged since Phase 20): in an environment where
  `scripts/seed_demo_data.sh setup` has already been run (see below),
  automatically resolves to **"WealthPilot Demo — Complete"** — in every
  browser, including one that had earlier remembered the blank fallback
  customer (Phase 31 fix: the seeded persona now wins over a remembered
  fallback id, which previously kept such a browser on the blank customer
  forever) — a real
  Aggressive risk classification (91% confidence), a real behaviour-model
  result, real goal-funding numbers, and a real, `approved`,
  MVO-optimized portfolio with a full compliance PASS. In a fresh,
  unseeded environment it falls back to Phase 24's original
  **"WealthPilot Demo Customer"** (the "Information Required" case) —
  both are legitimate, honestly-labeled demonstrations, never a
  fabricated substitute for one another.
- **"WealthPilot Demo — Savings"** (29111, real `approved` + real
  savings-first recommendation), **"WealthPilot Demo — Compliance"**
  (29112, real `rejected` — the fail-closed demonstration), and —
  whenever "Complete" is the one the login flow resolves to —
  **"WealthPilot Demo Customer"** (29113, `pending_information`) remain
  fully preserved in the database (never deleted, never renamed) but are
  **not reachable through the authenticated UI**, since that UI
  deliberately shows only the one customer associated with the logged-in
  session (point 1 above). To show a presenter one of these, use the
  backend directly: the interactive API docs at `/docs` (`GET
  /api/profiles/lookup?name=...` to find the id, then `GET
  /api/analysis/{analysis_id}` for its last recorded result), or `python
  scripts/seed_demo_data.py verify` (prints every persona's id, linkage,
  and financial-input status). This is a real, disclosed limitation of
  the current single-session-single-customer UI design, not something
  this runbook is hiding.

(If seeding a fresh environment, run `scripts/seed_demo_data.sh setup`
first — it now also submits each relevant persona's financial inputs via
the real `PUT /api/profiles/{id}/financial-inputs` endpoint. Customer ids
are environment-specific — the frontend never hard-codes one;
`scripts/seed_demo_data.py verify` shows this environment's actual ids.)

All demo data comes from `demo_data/` (ADR-038; see its README). Before a demo:

```bash
python backend/scripts/validate_demo_data.py              # static, no database
cd backend
python scripts/seed_demo_data.py setup --in-process        # idempotent: creates only what is missing
python scripts/seed_demo_data.py setup-family --in-process
python scripts/seed_demo_data.py verify --in-process       # stored values + expected outcomes
python scripts/seed_demo_data.py verify-family --in-process
```

`setup` also creates the pending-information persona ("WealthPilot Demo
Customer") when it is missing. `--in-process` runs the real app without a
server.

### Two demo scenarios: individual and family

The login page now offers two demo entries with the same credential (ADR-036):

| Entry | Resolves to | Demonstrates |
|---|---|---|
| **Use Individual Demo** | "WealthPilot Demo — Complete" (29110) | one customer's own analysis — risk, financial health, goals, portfolio, recommendation, explanation, agent activity, scenarios |
| **Use Family Demo** | "WealthPilot Demo — Savings" (29111), primary of "WealthPilot Demo Family" (household 9 in this environment) | household-level context — members, income, expenses, assets, liabilities, the financial summary and household goals |

Individual analysis is individual-level decision support; the household is
household-level financial context. They are separate on purpose: household
figures never feed any individual analysis, and there is no household risk
score, portfolio or recommendation. The family demo is seeded with
`python scripts/seed_demo_data.py setup-family --in-process` (from `backend/`,
after `setup`); see `reports/family_demo_report.md` and section 17 of
`docs/final_demo_script.md`.

## Sequence

1. **Open Login** (`/login`). Point out: prototype authentication only —
   a client-side credential check, no backend session, explicitly labeled
   as such on the page itself. No forgot-password, no social login (by
   design).
2. **Explain prototype authentication** briefly, then click **Use Demo
   Account**. This resolves the account's associated customer
   automatically — no profile-selection screen of any kind — and lands
   directly on the Dashboard. In a seeded environment this is "WealthPilot
   Demo — Complete"; say so, and name the fallback ("WealthPilot Demo
   Customer") only if that is what actually resolved (check the Profile
   page, next step).
3. **Show Dashboard** (`/dashboard`; `/` is now the public Home page). Point out the "Demo Account" badge in the
   header (never a real customer's data, never a raw numeric id) and the
   "Next step" guidance sentence, which now reads "A recommendation is
   ready for this profile" for the default seeded customer.
4. **Show Profile** (`/profile`). "WealthPilot Demo — Complete" — a real
   customer_type/investment capacity, two real persisted goals, the
   **Financial Inputs** card (Phase 28): monthly essential expenses,
   liquid assets, and goal-planning assumptions, editable here at any
   time (an empty field shows "Not provided", never 0), and — Phase 31 — a
   **Questionnaire** card whose button opens the saved answers for review
   or update. Point out these are the raw numbers the analysis below is
   computed from — never something the frontend itself calculates.
5. **Show Risk Assessment** (`/risk-assessment`): a real, high-confidence
   (91%) model classification (`Aggressive`), with the full
   class-probability table — the page's own text notes this is the
   model's own output, not derived from the questionnaire or the
   financial inputs (risk classification is unaffected by Phase 28).
6. **Start Analysis** via **Agent Activity** (`/agent-activity`) — click
   "Start analysis" and watch the real SSE node sequence run live:
   `customer_analyzer → risk_analyst → financial_health_analyst →
   goal_analyst → market_analyst → portfolio_manager → compliance_analyst
   → approved → recommendation → explanation → analysis_completed`
   (verified live in Phase 29: 12 events; recommendation and explanation
   appear only AFTER the compliance-approved terminal node, never for a
   rejected run — that one ends `compliance_analyst → rejected →
   analysis_completed`). Narrate each node — this is genuine backend
   execution, including a real MVO optimization, not a scripted
   animation. Each event carries only node/status/duration/summary/model
   version — there is no field for reasoning or a prompt.
7. **Show Financial Health** (`/financial-health`): the profile's own stored
   income, monthly essential expenses and quickly accessible savings (shown
   exactly as recorded), a real "no significant change / no unusual
   activity" behaviour-model result, the emergency-savings result, and an
   honest "unavailable" state for the spending pattern. Say why plainly: the
   spending-pattern model was trained on the separate Kaggle population and,
   by design (ADR-010), is never applied to a FAR-Trans-linked profile —
   even one whose own income/expense inputs are stored. The page also says
   that individual debts, cash flow and net position are not recorded or
   calculated; those exist only for a household (Family Demo).
8. **Show Goals** (`/goals`): all three goals show a real required monthly
   contribution, contribution gap, Monte Carlo success probability, and
   feasibility label — for this persona, Home Down Payment and Child Higher
   Education are **Feasible** (~99% and ~100%, and their contribution gaps are
   negative: the ₹30,000/month plan is ahead of the ~₹19,292 and ~₹12,648
   required) while Retirement Corpus is **At Risk**
   (~68%, and its gap is positive: ~₹30,565 required vs ₹30,000 supplied) —
   the probability and the deterministic gap agree in direction, which is
   a good thing to point out. Point out the numbers come from
   `core/goals.py`'s unmodified Phase 7 engine, fed by the financial inputs
   entered on the Profile page. (Until Phase 29 every goal here showed a
   spurious 0.0% / "Not Feasible" — a daily-vs-monthly return-frequency
   bug in the wiring, since fixed; if asked, say so plainly.)
9. **Show Portfolio** (`/portfolio`): a real, `approved` MVO allocation —
   QQQ/AGG/GLD weights, expected return, expected volatility, Sharpe
   ratio — genuine Phase 8 `core.optimizer` output, unmodified, reached
   live for the first time this project. Say plainly that this was
   previously never reachable through the live API, and explain why in
   one sentence if asked (a missing financial-input contract, now closed).
10. **Show Recommendation** (`/recommendation`): the real compliance
    outcome — `PASS`, zero rules triggered — alongside the real selected
    strategy and rationale. This is the single best screen to show the
    full, honest chain from risk → goals → market → portfolio →
    compliance → recommendation.
11. **Show Why This Recommendation** (`/why-this-recommendation`): a real
    explanation is now shown (Gemini's own generative call may itself
    fall back to Phase 13's existing templated restatement if its quota
    is unavailable at demo time — say so plainly if it happens; both
    paths are real, pre-existing, approved behavior, never a fabricated
    explanation either way).
12. **Show the fail-closed REJECT path, via the API, not the UI**: the
    authenticated app deliberately shows only one customer per session
    (no switcher exists), so open `/docs` and call `GET
    /api/profiles/lookup?name=WealthPilot Demo — Compliance`, then `GET
    /api/analysis/{analysis_id}` for its last result — a real `REJECT`
    with exactly one triggered rule (`emergency_fund_savings_first`,
    "emergency-fund status was not provided"), demonstrating the gate is
    just as binding as ever for a customer whose financial inputs were
    deliberately never supplied. Frame this as "the same backend,
    inspected directly" — not a second, hidden UI.
13. **Show Scenario Simulator** (`/scenarios`): run a comparison for the
    current profile across portfolio strategies; every value shown is
    still read directly from a real `POST /api/analysis` response for
    each strategy, never computed in React. For the Aggressive default
    persona the risk-conditioned default already IS MVO, so compare it with
    **HRP** (or 1/N): both are **REJECTed by compliance** for this
    customer (their QQQ weight is below the Aggressive band), which is a
    good demonstration of the gate acting on a what-if. Phase 30 added the
    return/volatility and Sharpe charts to this page.
14. **Explain compliance/fail-safe behavior**: summarize the "Viva Talking
    Points" below.
15. **Log out**, then **create a brand-new user** end to end: Login →
    "Create your profile" → fill the form → Questionnaire (answers are
    saved — Phase 23) → Goals (saved) → Dashboard. This new user has NO
    financial inputs on file yet, so their own analysis will honestly
    show `pending_information`/`rejected` until they visit their Profile
    page and enter some — a good, honest illustration of exactly what
    Phase 28 actually changed (a real user-provided input, not a demo
    -only shortcut).

## Viva Talking Points

- **Why demo data is synthetic**: every demo customer's *identity* (name,
  profile fields, questionnaire answers, goals, and now financial inputs)
  is fabricated specifically for this demonstration and clearly labeled
  as such ("WealthPilot Demo — …"). It is never presented as, and never
  contains, a real customer's personal information.
- **Why outputs are generated by the real pipeline, not fabricated**:
  every risk category, confidence score, behaviour flag, market regime,
  portfolio weight, and compliance decision shown above was read directly
  from a live `POST /api/analysis` response — none was hand-entered into
  the database. The one thing NOT possible to fabricate from scratch is a
  real, model-recognizable transaction history, so each demo persona's
  risk-relevant data source is an existing, real (anonymized) FAR-Trans
  customer, linked via the exact mechanism the system already uses for
  its whole real population — disclosed here explicitly, not hidden. The
  financial inputs (expenses, liquid assets, contribution/return/
  inflation assumptions), by contrast, are plausible, directly-entered
  synthetic numbers — exactly the kind of thing a real user would type
  into the same Profile-page form.
- **Why the frontend does not calculate financial numbers**: every page
  reads figures directly from the API response and only formats them
  (currency symbols, percentage signs, date formatting) — never computes
  a new value, including the new Financial Inputs form, which only
  validates (non-negative, sensible ranges) and submits raw numbers
  verbatim.
- **Why compliance cannot be bypassed**: `enforce_gate` raises an
  exception on REJECT that nothing in the codebase catches; the API
  service layer only calls the recommendation engine and Gemini
  explanation when the graph's own terminal status is `approved` — a
  structural gate, not a convention. Nothing about Phase 28 changed this
  mechanism; it only supplied real data for the SAME gate to evaluate.
- **Why Gemini does not calculate numbers**: Gemini only ever writes
  prose explaining numbers the deterministic pipeline already computed;
  its output is validated against the source data and rejected on
  mismatch.
- **Why AutoGen reasoning is not exposed**: the Agent Activity page and
  its SSE stream carry only `node`/`status`/`duration_ms`/`summary`/
  `model_version` fields — there is no field anywhere in that data shape
  for a prompt, reasoning trace, or transcript.
- **Why unavailable information produces a safe terminal state**: this
  system is built to say "unavailable" rather than guess. A brand-new
  user with no financial inputs yet still gets an honest
  `pending_information`/`rejected` result, never a guessed one.
- **How the portfolio strategy is selected**: risk category
  deterministically maps to exactly one strategy (Conservative/Income →
  HRP, Balanced → 1/N, Aggressive → MVO) — a fixed, auditable rule, now
  demonstrably reachable live for a real customer.
- **How provenance is preserved**: every result carries its model version
  and data source (e.g. `models/risk`, `v1`), visible on the
  Recommendation and Risk Assessment pages.
- **How a savings-first recommendation differs from a normal one**
  ("WealthPilot Demo — Savings", reachable via `/docs` per step 12's
  pattern): a customer with a genuinely insufficient emergency fund gets
  `recommendation.status == "savings_first"` and `portfolio: null` — by
  design, "build liquidity before investing," not an error and not a
  lesser/broken result.
- **Why the Compliance persona's REJECT now cites one rule instead of
  five**: earlier, all 5 compliance rules triggered for a
  savings-first-shaped proposal, 4 of them for the misleading reason
  "portfolio weights were not provided." Phase 28 fixed this: the 4
  weight-validation rules now correctly recognize a legitimate
  savings-first proposal's absent weights as expected. The Compliance
  persona still REJECTs — for the one rule that is actually true for it
  (no financial inputs were ever supplied) — a more accurate explanation
  of the exact same binding gate, not a weaker one.

## What NOT to say

- Do not say "approved" means the same thing as "recommended by a
  licensed financial adviser" — it means the deterministic pipeline
  completed and a real compliance PASS was reached for this synthetic
  demo persona's own supplied numbers.
- Do not claim this is licensed financial advice, a guaranteed-return
  system, or a production-authenticated application.
- Do not claim browser-based visual testing was performed in this
  environment if a headless browser tool was not actually available when
  this was written.
- Do not say a customer picker/switcher exists in the app — it does not,
  by deliberate design; the other preserved personas are shown via the
  API explorer, never a hidden in-app control.
- Do not claim a goal result is "wrong" or "tuned": "At Risk" / "Not
  Feasible" at a given contribution/return/inflation assumption and
  deadline is a real Monte Carlo result (e.g. the Complete persona's
  Retirement Corpus goal, due 2051, needs ~₹30,565/month against ₹30,000 supplied),
  and changing the assumptions on the Profile page changes it, live,
  because the math is real. Do not present the pre-Phase-29 all-0.0%
  results as legitimate — they were a frequency-mismatch bug (see
  `docs/DECISIONS.md` ADR-027).
- Do not describe the Recommendation page's compliance list as showing
  "the compliance engine's full internal state" — it shows each rule's
  description, whether it triggered, and (if triggered) the engine's own
  reason string, verbatim; nothing more.

## Demo Completeness Audit (2026-10-01)

Audited against the live API for this environment; no demo record was changed.

| Demo | Income | Expenses | Spending pattern | Behaviour | Emergency savings | Assets | Liabilities / net position |
|---|---|---|---|---|---|---|---|
| Complete (29110) | stored (annual) | stored (monthly essential) | unavailable — ADR-010 | computed (FAR-Trans) | computed — sufficient | liquid savings only | not recorded for individuals |
| Savings (29111) | stored | stored | unavailable — ADR-010 | computed | computed — below target (savings first) | liquid savings only | not recorded for individuals |
| Compliance (29112) | stored | not provided (by design) | unavailable — ADR-010 | computed | not checked (inputs absent) | not provided (liquid savings) | not recorded; analysis stays **rejected** |
| Pending (29113) | stored | stored (monthly essential) | not reached | not reached | not reached | liquid savings stored | analysis stays **pending information** |
| Family (household 9) | 5 records (4 active) | 10 records, essential / non-essential split | household spending summary (not an ML result) | — | household summary — below target | 6 records, total + liquid | 2 records; cash flow and net position from the household summary |

- **Spending pattern (expense persona)** stays unavailable for every demo
  persona. All individual personas with an analysis are FAR-Trans-linked, and
  ADR-010 / `.claude/rules/ml.md` forbid applying the Kaggle-trained expense
  model to a FAR-Trans customer's data. The model's features (expense-,
  savings-, debt- and EMI-to-income ratios) also need debt and EMI figures
  that no individual record stores. Making it available would need a new,
  explicitly approved decision (e.g. a non-FAR-Trans synthetic demo persona),
  not a data fix.
- **Household spending** is the backend's own summary of the household's
  expense records (recurring essential / non-essential / one-time) — never an
  individual expense cluster.
- **Provenance**: every demo record and `demo_data/wealthpilot_complete_demo_dataset.csv`
  row is `data_source = synthetic_demo`, `dataset_purpose =
  demo_testing_presentation`, `training_eligible = false`.
- **Resolved (ADR-040, 2026-10-04)**: an earlier environment had a stray
  "TEST" household and a duplicate "WealthPilot Demo Customer" row (ADR-030);
  both were removed in the 2026-10-04 demo reset and the full demo population
  was reseeded under new ids (see above). `seed_demo_data.py verify-family`'s
  "individual-demo persona is in no household" check now passes.

## Financial Behaviour & Sentiment demonstration mode (development only)

`/financial-behaviour?demo=true` shows a walk-through with six clearly **fictional** months (March to August 2026), their calculated ratios and month-over-month changes, a chart and table, and a fictional sentence read by the rules baseline `user_text_rules_v1`.

1. Backend `.env`: `DEMO_MODE_ENABLED=true` (the default is `false`; `.env.example` says so). Start the backend as usual (`PYTHONPATH=..` from `backend/`, see the README).
2. Frontend: `npm run dev` (the query is honoured only by the Vite dev server, or a build made with `VITE_DEMO_MODE=true`; a production build ignores it).
3. Sign in with the existing demo account (the page is still behind the prototype sign-in), then open `http://localhost:5173/financial-behaviour?demo=true`. The `?demo=true` survives the sign-in redirect.

What is real and what is not: every figure beside the months is calculated by the existing behaviour-feature code and the sentence by the existing rules baseline; the months and the sentence are fixed fiction served by `POST /api/demo/financial-behaviour`, which takes no database session, writes nothing, logs no text, touches no ledger, and answers `404 Demo mode is not enabled` when the flag is off. A backend that is down shows "Service unavailable", never demo data. Without `?demo=true` the page is unchanged (no profile, no records, real records). `SENTIMENT_MODEL_ENABLED` stays false, the method stays `user_text_rules_v1`, confidence and intensity stay unavailable.

### Family demonstration (`?demo=family`) and the real Financial Behaviour page (2026-11-02)

`http://localhost:5173/financial-behaviour?demo=family` shows a **fictional family** ("Demo data — fictional family example"): a primary member, a partner and a dependent, each with their own months, trends, month-over-month changes, savings rate, investment behaviour, spending-pattern state and the "Not recorded for an individual" loan / EMI wording, plus the household's own totals (income, spending, assets, loans and EMIs) from the real household engine over invented household records. The optional note is the primary member's and is read by the rules baseline. It uses the same `DEMO_MODE_ENABLED=true` backend flag, the same dev-server-only front end rule and the same sign-in as `?demo=true`; both routes answer 404 when the flag is off and neither touches a database.

**Real records (no `?demo`).** `/financial-behaviour` shows, for the signed-in profile: the overview (reported months, date range, income / spending / savings trends, savings rate, month-over-month changes, and why any value is missing), the profile's own months as a chart and table, investment behaviour (consistent, increasing, decreasing, unusual, or "Not enough investment history to compare."), the spending pattern ("Not available" unless the spending model returned one), the individual loan / EMI wording, and the optional note in simple English with the technical reading inside an optional "Detailed reading" disclosure. Months are added, corrected or deleted on **Customer Profile → Monthly records** (a month is stored once; amounts cannot be negative or have more than two decimals; a blank amount is "not provided", never zero). With no records the page shows "No monthly records yet" and a link there. Demo data is never used for a real profile or for an error.

### If the page says "No monthly records yet" (diagnosed 2026-11-03)

That sentence is the NORMAL page for a profile with no monthly records, so it appears whenever the demonstration was not reached. The demonstration itself works (verified in headless Chrome at `http://localhost:5173/financial-behaviour?demo=family`). The ways it was being lost, and what changed:

1. **"Use Family Demo" on the sign-in page** always opened `/profile?household=open`, discarding the `?demo=family` you asked for; every sign-in button now returns to the address you were sent from.
2. **The sidebar "Behaviour & Sentiment" link** is the plain path; inside a demonstration it now keeps the `demo` query.
3. **A build or value that does not honour the parameter** (a production build, `?demo=Family`, `?demo=`) silently showed the normal page; it now says "Demonstration mode is not active" and why. No demo data is ever shown for a real profile.
4. **A 404 from the demonstration route** is now explained as the flag or an older backend ("set `DEMO_MODE_ENABLED=true` and restart the backend": the setting is read once, at start-up), not "may not have been created yet".
5. **The real empty page** now points developers (development builds only) at `?demo=family` and `?demo=true`.

Checking it yourself: `frontend/tests/route-probe.mjs` drives headless Chrome against a LOCAL dev server and prints what rendered (`node frontend/tests/route-probe.mjs "http://localhost:5173/financial-behaviour?demo=family" --auth --expect="Demo data — fictional family example" --forbid="No monthly records yet"`); see its header for the mock and click options (it needs Chrome at the usual Windows path and never talks to anything but localhost).
