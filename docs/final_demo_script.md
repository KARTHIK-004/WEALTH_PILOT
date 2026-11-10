# WealthPilot AI — Final Demo Script

A practical, click-by-click script for the live demonstration, viva or guide
review. Every number below was read from a real API response for the seeded
demo persona **"WealthPilot Demo — Complete"** (id 29110 in this
environment; ids are environment-specific, the frontend never hard-codes
one). Nothing here is aspirational. If a number on screen differs, the screen
is right and this script is out of date — say so plainly rather than
reconciling it aloud.

WealthPilot AI is an **educational decision-support prototype, not licensed
financial advice**. It does not execute trades, move money or connect to a
brokerage.

## 0. Before you start (5 minutes, off-stage)

- Backend running (`uvicorn wealthpilot.api.main:app --app-dir .` from
  `backend/`) and frontend running (`npm run dev` from `frontend/`, opens
  `http://localhost:5173`). Check `http://localhost:8000/api/health`.
- The demo personas seeded: `scripts/seed_demo_data.sh verify` prints each
  persona's id, FAR-Trans linkage and financial-input status. (Only run
  `setup` on a fresh environment.)
- Use a normal browser window. If it was used before, it does not matter what
  it remembers: **Use Individual Demo resolves to "Complete" whenever that
  persona is seeded** (Phase 31 fix — earlier, a browser that had once landed on the
  blank fallback customer stayed there).
- Gemini's free quota may be exhausted. That is fine and expected — see
  section 12 for what to say. Do not try to work around it.
- Have `http://localhost:8000/docs` open in a second tab for sections 15–16.
- The family demo seeded (for section 17): from `backend/`,
  `python scripts/seed_demo_data.py verify-family --in-process` must end
  `VERIFY-FAMILY PASSED`. (Only run `setup-family` on a fresh environment; it is
  idempotent, so re-running it changes nothing.)

## 1. Login

**Click:** open `/login`. Point at the "Prototype authentication — for
demonstration only" line. Point at the two demo entries — **Individual** and
**Family** — then click **Use Individual Demo**.

**Say:** "This is prototype authentication — a client-side credential check,
no server session. It is disclosed as such on the page and in the security
notes; I have not built production auth on purpose. Signing in resolves the
account's customer automatically — there is no customer picker anywhere in
the app, by design."

**Verify on screen:** you land on the Dashboard; the header shows a **Demo
Account** badge (never a raw customer id).

## 2. Dashboard

**Point at:** the "Next step" alert ("A recommendation is ready for this
profile"); the Profile / Risk / Financial health / Goals / Compliance /
Recommendation cards; the **Portfolio allocation** donut at the bottom.

**Say:** "The dashboard is a summary. Every value comes from one analysis
result the backend computed; the frontend only formats. The donut is drawn
from the backend's own weights."

**Numbers:** Risk **Aggressive**, emergency fund **sufficient**, 2 goals
evaluated, compliance **PASS**, recommendation **approved**.

## 3. Profile

**Click:** Customer Profile in the sidebar.

**Point at:** the two separate cards — *Customer information* (name, age,
income, customer type, investment capacity, goals) and **Financial Inputs**.

**Say:** "Financial inputs are what the user tells us: monthly essential
expenses (₹45,000), current liquid assets (₹3,60,000), monthly contribution
(₹30,000), expected annual return (0.09) and inflation (0.04), contributions
per year (12). They feed the emergency-fund and goal calculations. A blank
field means *not provided* — it is stored as unknown, never as zero, and the
analysis then honestly reports that result as unavailable."

**Optional:** do not clear anything on the demo account. To show the honest
"not provided" state, point at the placeholder text on any empty field and
mention that the Compliance persona has not provided two of these six values, its monthly essential expenses and liquid assets (section 16).

## 4. Questionnaire

**Click:** on the Profile page, the **Questionnaire** card → **Review or update
answers**.

**Say:** "The questionnaire (5 sections, 25 questions, from the FAR-Trans
MiFID-style questionnaire file) is saved with the profile and can be updated.
**Answering it does not change the ML risk category** — the page says so. The
risk category comes from the risk model, which reads transaction history, not
these answers."

**Click:** **Back** returns to the Profile page; or **Save & Continue** to
step through to Goals and the Dashboard.

## 5. Goals

**Click:** Goals in the sidebar.

**Explain one card at a time (Home Down Payment, Child Higher Education, then Retirement Corpus):**

| | Home Down Payment | Child Higher Education | Retirement Corpus |
|---|---|---|---|
| Target amount | ₹15,00,000 | ₹20,00,000 | ₹1,50,00,000 |
| Inflation-adjusted target | ₹17,53,846 | ₹29,20,546 | ₹3,88,10,445 |
| Required contribution | ₹19,292 / month | ₹12,648 / month | ₹30,565 / month |
| Contribution gap | −₹10,708 | −₹17,352 | +₹565 |
| Simulated success probability | **98.8%** | **100.0%** | **67.7%** |
| Feasibility (from the backend) | **Feasible** | **Feasible** | **At Risk** |

**Say:** "Inflation-adjusted target is the target grown at the assumed 4% to
the deadline. Required contribution is the deterministic monthly amount that
reaches it at the assumed 9% return. The **gap** is required minus what the plan contributes: negative means the
₹30,000 plan is *ahead* — the page says 'Contribution exceeds the calculated
requirement' — positive means it falls short. The probability is a Monte Carlo
result: 10,000 simulated paths bootstrapped from historical returns. Feasible
is 80% and above, At Risk 50–79%, Not Feasible below 50%; the label is the
backend's, never inferred in the browser."

**If asked about earlier versions:** goals once all showed 0.0% because daily
returns were applied once per monthly period — a wiring bug found and fixed in
Phase 29 (ADR-027). Say so plainly.

## 6. Analysis

**Say (no click needed):** "One analysis run is a LangGraph pipeline: customer
analyzer → risk analyst → financial-health analyst → goal analyst → market
analyst → portfolio manager (or savings-first) → compliance analyst → and only
if approved, recommendation and explanation. Each step is a deterministic
function or a trained model; nothing in the routing is decided by an LLM."

## 7. Risk Assessment

**Click:** Risk Assessment.

**Point at:** the category badge **Aggressive**, model confidence **91%**, the
probability chart and table.

**Numbers:** Aggressive 91.3%, Balanced 7.2%, Income 1.5%, Conservative 0.1%
(shown in the API's own order, one decimal).

**Say:** "A Random Forest trained on FAR-Trans transaction history, 20
engineered features, four classes. Its cross-validated macro-F1 is about
0.41 — a modest score on a hard problem, and I do not oversell it. When
confidence is below 0.50 the system does not guess: it asks for more
information (that is the pending-information state)."

## 8. Financial Health

**Click:** Financial Health.

**Point at:** the emergency-fund chart — Required **₹2,70,000** vs Current
**₹3,60,000**, shortfall **₹0**, **sufficient**; the behaviour cards (no drift, no
anomaly); the *expense persona* shown as unavailable with its reason.

**Say:** "Emergency fund = six months of essential expenses. ₹45,000 × 6 =
₹2,70,000 required; the customer holds ₹3,60,000, so the normal path continues.
The shortfall is the backend's number, printed as text — the chart never
computes it. Expense persona is unavailable on purpose: that model was trained
on a separate Kaggle population and is never applied to a FAR-Trans customer
(no invented linkage)."

## 9. Portfolio

**Click:** Portfolio Analysis.

**Point at:** strategy **MVO**; the allocation donut and table; expected
return / volatility / Sharpe.

**Numbers:** **QQQ 55%**, **AGG ≈ 0%**, **GLD 45%**; expected return 17.4%,
volatility 16.4%, Sharpe 1.06.

**Say:** "Aggressive maps to mean-variance optimisation — maximise Sharpe with
Ledoit-Wolf shrinkage, with box constraints: QQQ is held to the band for the
customer's risk level and no asset may exceed 70%. The three assets are QQQ
(Nasdaq equity), AGG (bonds) and GLD (gold). Expected returns are historical
averages, **not forecasts** — my market models did not beat a naive baseline,
so I refuse to feed them into the optimiser. AGG is about zero — bonds had a
negative average return in this historical window (it includes 2022's rate
selloff), and a Sharpe-maximising optimiser gives such an asset no weight."

## 10. Compliance

**Click:** Recommendation → the **Compliance** card.

**Point at:** **PASS**, rules v1, five rules each marked *passed* — weights sum
to one, no short positions, QQQ within the risk band, single-asset cap,
emergency-fund rule.

**Say:** "Compliance is a binding gate, not advice. Five YAML rules,
fail-closed: if a required input is missing the rule triggers. A REJECT raises
an exception that nothing catches, so no recommendation or explanation can
exist for a rejected profile. I will show that shortly."

## 11. Recommendation

**Point at:** status **Approved**, strategy **MVO**, and the *Structured
rationale*: "Risk category 'Aggressive' selects MVO", "Goal feasibility 'At
Risk' prefers MVO, which matches", "Market regime 'Volatile' prefers HRP, but
risk suitability overrides it".

**Say:** "The engine has a fixed precedence: **Compliance > Savings-first >
Risk > Goal > Market.** Compliance can veto everything; an insufficient
emergency fund forces savings-first regardless of anything else; otherwise the
risk category picks the base strategy, and goals and markets may only be
*noted as aligned or overridden* — they can never change it. That last line
shows it in action: the market preferred HRP, risk suitability won. There is no
score and no 'best strategy' — the reasons are the recommendation."

## 12. Why This Recommendation

**Click:** Why This Recommendation?

**Point at:** the two clearly separated cards — **Explanation (wording only)**
and **Deterministic factors**.

**Say:** "Gemini writes wording; it never calculates or decides. Everything in
the second card — risk, compliance, goal feasibility, market regimes, selected
strategy — is computed by the backend's models and rules. Gemini receives that
already-computed data and its prose is validated against the numbers; if it
fails or the service is unavailable, a template restates the computed results
directly."

**If the quota is exhausted (expected):** the badge reads **Template
restatement of the computed results** and an alert says an AI-written
explanation was not used. Say: "Gemini's free quota is exhausted right now, so
you are seeing the designed fallback. That is the safety net working: no
number here was produced by AI either way."

## 13. Agent Activity

**Click:** Agent Activity → **Start analysis**.

**Point at:** the step list filling in live, each with status, duration, a
short summary and model version.

**Expect (12 steps):** analysis started → customer analyzer → risk analyst →
financial-health analyst → goal analyst → market analyst → **portfolio
manager** → compliance analyst → analysis outcome (Approved) → recommendation →
explanation → analysis completed.

**Say:** "This is the real LangGraph run, streamed. Each event carries only
node, status, duration, a summary and a model version — there is no field for a
prompt, reasoning or transcript, so none can appear. The view draws only steps
that actually arrived. Recommendation and explanation come after the compliance
outcome, never before, and never at all for a rejected run."

## 14. Scenario Simulator

**Click:** Scenario Simulator → set **Scenario A** to *Risk-conditioned
(default)* and **Scenario B** to **HRP** → **Compare scenarios**. (For this
Aggressive customer the default *is* MVO, so comparing default with MVO would
show two identical sides.) The first run of a new strategy is a real pipeline
run and takes a few seconds; it is then cached.

**Point at:** the return/volatility chart, the separate Sharpe chart, and the
comparison table.

**Numbers (verified against the real API):** Scenario A (MVO): return 17.4%,
volatility 16.4%, Sharpe 1.06, compliance **PASS**, recommendation
*approved*. Scenario B (HRP): return 0.1%, volatility 6.9%, Sharpe 0.01,
compliance **REJECT**, no recommendation. Choosing *1/N* for B gives return
10.7%, volatility 11.6%, Sharpe 0.92 and also **REJECT**.

**Say:** "Each side is a real analysis run under a different portfolio-strategy
parameter. It is a comparison, not a contest: nothing is ranked or called
best. Look at the compliance row — for an Aggressive customer, HRP and 1/N put
far less than the required minimum in QQQ, so compliance rejects them and no
recommendation exists for those scenarios. That is the binding gate working on
a what-if, not a defect. A missing metric is shown as unavailable, never zero."

## 15. Savings-first demo (API explorer)

The authenticated app shows exactly one customer per session — there is no
switcher, by design. **"WealthPilot Demo — Savings" (29111) is therefore
verifiable through the API but not reachable through the authenticated UI.**

**Do:** in `http://localhost:8000/docs` call `GET
/api/profiles/lookup?name=WealthPilot Demo — Savings` (em dash), then `POST
/api/analysis` with `{"profile_id": <that id>}` (a cached result — nothing is
recomputed).

**Show:** `status: approved`, `recommendation.status: savings_first`,
`emergency_fund`: required 2,28,000, current 90,000, **shortfall 1,38,000**,
`portfolio.weights: null`, `recommendation.selected_strategy: null`,
compliance PASS.

**Say:** "Same backend, inspected directly. The emergency fund is ₹1,38,000
short, so the system does *not* optimise a portfolio — it says 'build
liquidity before investing'. It is a safe, approved outcome, not an error, and
no allocation exists to show. In the app this would appear as 'Savings-first:
portfolio allocation deferred' with the emergency-fund chart."

## 16. Compliance demo (API explorer)

Same rule as section 15 — reachable through the API, not the authenticated UI.

**Do:** look up `WealthPilot Demo — Compliance` (29112), then `POST
/api/analysis`.

**Show:** `status: rejected`; `compliance.decision: REJECT` with **exactly one
triggered rule, `emergency_fund_savings_first`**, reason "required data
unavailable: emergency-fund status was not provided"; `recommendation: null`;
`explanation: null`; portfolio `savings_first` with no weights.

**Say:** "This customer supplied an income and a savings plan, and the goals were
computed, but never supplied monthly essential expenses or liquid assets. The system
will not guess — the fail-closed rule triggers and the gate rejects. Nothing
downstream ran: no recommendation, no Gemini call. The four weight rules
correctly do not trigger, because a savings-first proposal has no weights by
design."

**Optional (one line):** "WealthPilot Demo Customer" (29113) has no FAR-Trans
linkage, so risk cannot be classified → `pending_information` and every
downstream section is unavailable — the honest 'need more information' state.
A brand-new user created through **Create your profile** behaves the same way.

## 17. Family demo (household, 3 minutes)

**Click:** sign out, then on `/login` click **Use Family Demo**. You land on
the Customer Profile page with the **Household** section already open; the
header badge now reads **Family Demo**.

**Say:** "Everything so far was one customer's own analysis. This is the other
half of the product: a household. The family is a real persisted household —
seeded through the same public API the app uses — with a primary member and a
spouse. The figures here are household-level context. They are not an input to
anyone's individual analysis, and there is no household risk score or
recommendation."

**Walk through, in order:**

1. **Household identity:** "WealthPilot Demo Family", *Your role* Primary,
   *Members* 2. The Members tab shows the spouse by name, relationship and role
   only. "Membership is not account access — I cannot see the spouse's own
   profile, analysis or finances from here."
2. **Financial summary:** recurring monthly income **₹1,60,000**, recurring
   monthly expenses **₹99,200** (essential ₹86,000, other ₹13,200), monthly cash
   flow **₹60,800**, net position **₹18,20,000**.
3. **Income tab:** the yearly interest income (₹36,000) counts as ₹3,000 a month;
   the ₹1,20,000 bonus is one-time and shown separately; the ended part-time job
   is stored but inactive, so it is not counted.
4. **Liabilities tab:** the credit card is recorded at **₹0** outstanding with
   its monthly payment **Not provided** — "a known zero next to an unknown; the
   system never turns one into the other."
5. **Emergency fund:** required **₹5,16,000** (6 months of ₹86,000 essential
   expenses), current liquid assets **₹3,60,000**, shortfall **₹1,56,000**,
   **Insufficient** — the same rule as the individual engine.
6. **Goals tab:** five household goals. The emergency-fund goal's own ₹5,50,000
   target is the family's stated target; the line above the table restates the
   *calculated* ₹5,16,000 requirement — "one calculated figure, never two".

**Verify on screen:** badge **Family Demo**; the Household section open on
arrival; the figures above.

## 18. Final closing (30 seconds)

"WealthPilot AI takes a customer's real transaction history and their own
financial inputs and runs them through a fixed pipeline: an ML risk
classifier, behaviour and market analysis, deterministic goal and emergency-
fund maths, a portfolio optimiser, and a binding compliance gate — then, only
if approved, a recommendation with a fixed precedence and an explanation. The
LLM only writes wording. Every number is computed once, in the backend, and
every unavailable value is shown as unavailable, never guessed. It is an
educational prototype: modest model scores, one historical window, prototype
authentication, and it is not financial advice."

## What NOT to say

- That "approved" means recommended by a licensed adviser — it means the
  deterministic pipeline completed and compliance passed for this synthetic
  persona's own inputs.
- That it guarantees returns, or that the models are highly accurate.
- That a customer switcher exists, or that browser-based visual testing was
  performed — this project has been verified by type-checking, build, lint,
  the backend test suite and source-level review plus server-side render
  checks, not in a browser.
- That AutoGen runs during analysis — the debate module is built and tested but
  is not invoked by any API route.
- That Gemini "made" or "checked" any number.

## Numbers cheat-sheet (demo 29110)

| Item | Value |
|---|---|
| Risk | Aggressive, 91.3% (Balanced 7.2%, Income 1.5%, Conservative 0.1%) |
| Emergency fund | required ₹2,70,000 (6 × ₹45,000), current ₹3,60,000, shortfall ₹0 |
| Home Down Payment | ₹15,00,000 → ₹17,53,846; ₹19,292/mo required; gap −₹10,708; 98.8%, Feasible |
| Child Higher Education | ₹20,00,000 → ₹29,20,546; ₹12,648/mo required; gap −₹17,352; 100.0%, Feasible |
| Retirement Corpus | ₹1,50,00,000 → ₹3,88,10,445; ₹30,565/mo required; gap +₹565; 67.7%, At Risk |
| Market regimes | ^IXIC Range-bound, ^NDX Volatile, QQQ Volatile, AGG Range-bound, GLD Volatile |
| Portfolio | MVO — QQQ 55%, AGG ≈ 0%, GLD 45%; return 17.4%, volatility 16.4%, Sharpe 1.06 |
| Compliance | PASS, rules v1, 0 of 5 triggered |
| Recommendation | approved, MVO (risk-conditioned) |
