# Phase 9 — Compliance Report

## 1. Status

**COMPLETE.**

## 2. Compliance architecture

`backend/wealthpilot/core/compliance.py` — pure, DB-free (same design as `core/goals.py` and `core/optimizer.py`): `evaluate_compliance(proposal, rules_config)` takes a plain `ComplianceProposal` built from already-computed Phase 4/7/8 outputs and returns a plain `ComplianceResult`. No FastAPI, LangGraph, AutoGen, or Gemini code exists here or is imported here (all explicitly out of scope for this phase). `enforce_gate(result)` is the binding gate: it raises `ComplianceRejectedError` on `REJECT` rather than returning a boolean a caller could forget to check.

## 3. Rule source

`config/compliance_rules.yaml` is the single source of truth for rule identity/severity/description/message. It existed only as an empty Phase-0 placeholder (`rules: []`) before this phase — no rule logic was added ahead of this phase's spec review, exactly as its own placeholder comment required.

**No document specifies a concrete rule list or WARN threshold** — every prior document only names constraint *categories* (equity/risk-category bounds, concentration caps, minimum cash floor). Two decisions were confirmed via `AskUserQuestion` before writing any rule logic (2026-09-14):

1. **The 5-rule set below**, every threshold reusing an *already-approved* Phase 7/8 number — nothing new invented.
2. **REJECT-only for now** — no WARN-severity rule exists, since no WARN threshold is specified anywhere. The engine's severity/aggregation logic fully supports WARN; a future rule can be added to the YAML with zero code changes.
3. **Fail-closed** on missing required data (also confirmed 2026-09-14) — see §14.

## 4. Rule schema

```yaml
- id: <stable identifier>
  description: <human-readable, for audit/reporting>
  severity: REJECT | WARN
  condition: <controlled identifier naming one function in _RULE_REGISTRY>
  message: <concise, customer-facing-safe summary>
```

`condition` is **never** an expression that gets evaluated — it is a lookup key into `_RULE_REGISTRY`, a Python dict mapping known identifiers to hand-written check functions. `RuleDefinition`'s Pydantic validator rejects any `condition` not already in that registry at load time; there is no code path from YAML content to `eval`/`exec`/dynamic import anywhere in this module. See §15 for the security tests proving this.

## 5. Rule version

`version: "v1"` (top-level field in the YAML). Every `ComplianceResult.rules_version` records exactly which version produced it, satisfying the "identify which rules/version produced the result" requirement. A future rule change requires bumping this string — enforced by convention/documentation, not by code, matching how Phases 4-8 version their own artifacts (`_v1` suffix).

## 6. Decision states

`PASS`, `WARN`, `REJECT` — the exact three states MASTER_PROMPT.md section 15 specifies, no others.

## 7. Rule aggregation

Strict escalation, never a downgrade: the loop starts at `PASS`; any triggered `REJECT`-severity rule sets the decision to `REJECT` unconditionally; a triggered `WARN`-severity rule escalates `PASS`→`WARN` but is guarded (`elif decision != "REJECT"`) from ever overriding an existing `REJECT`. **REJECT dominance holds regardless of rule evaluation order** — verified by two tests running the identical rule set with REJECT and WARN rules in opposite orders.

## 8. Binding REJECT gate

```
proposal → evaluate_compliance() → ComplianceResult
                                          ↓
                                    enforce_gate()
                                    /            \
                          PASS/WARN            REJECT
                          (returns              (raises
                           result)               ComplianceRejectedError)
```

`enforce_gate` is the **only** sanctioned way to move from "a result exists" to "downstream processing may proceed." Nothing in this codebase catches `ComplianceRejectedError`. A minimal, test-only stand-in for a future explanation step (`_simulate_downstream_explanation`, defined *inside* the test file — no Phase 10 LangGraph/agent code was written) proves the end-to-end contract directly: calling it with a REJECTing proposal raises before the "explanation" line ever executes; calling it with a PASSing proposal reaches that line normally. This is the "MOST IMPORTANT TEST" the phase instructions called for.

## 9. Risk suitability

The `qqq_within_risk_band` rule imports `RISK_LEVEL_QQQ_BANDS` and `GENERAL_SINGLE_ASSET_CAP` **directly from `wealthpilot.core.optimizer`** (Phase 8) — no second, independently-defined allocation system exists. The same intersection Phase 8's `effective_bounds()` applies (tighter of the risk-category band vs. the general cap wins) is reproduced exactly, verified by a dedicated test using Aggressive's case (nominal 80% ceiling, actually enforced at 70%). Phase 4's risk model is neither retrained nor modified — the rule takes a plain `risk_level: str` and does not call into any Phase 4 code.

## 10. Portfolio validation

Four rules validate a proposed portfolio: weights sum to 1 (`weights_sum_to_one`), no negative/short weights (`no_negative_weights`), QQQ within its risk-category band (`qqq_within_risk_band`), no asset above the general single-asset cap (`single_asset_cap`). **Compliance never modifies a weight** — verified directly (`test_evaluate_compliance_never_mutates_the_proposal_weights`): a REJECTing proposal's weights are byte-identical before and after evaluation. No MVO/HRP/efficient-frontier/rebalancing code is imported or called anywhere in `core/compliance.py`.

## 11. Emergency-fund interaction

The `emergency_fund_savings_first` rule takes two plain booleans (`emergency_fund_sufficient`, `is_savings_first_recommendation`) — it does **not** import or call Phase 7's `assess_emergency_fund()`/`savings_first_required()` itself; whichever later phase builds the proposal is responsible for computing those booleans via Phase 7's own functions and passing the results in. This keeps the emergency-fund *calculation* entirely in Phase 7 (never duplicated) while letting Phase 9 enforce the *consequence* PROJECT_PLAN.md/MASTER_PROMPT.md already specify: an insufficient emergency fund paired with anything other than a savings-first recommendation is a binding REJECT.

## 12. Behaviour interaction

**None** — no Phase 5 behaviour flag (Isolation Forest anomaly, CUSUM alarm, trading-intensity signal) is read, referenced, or reinterpreted anywhere in this module. Per this phase's own instruction, an anomaly is not financial misconduct or a regulatory violation unless explicitly specified, and nothing specifies it, so nothing was invented.

## 13. Data-source limitations

**Kaggle/FAR-Trans separation preserved structurally, not just by convention**: `ComplianceProposal` has exactly four fields (`risk_level, weights, emergency_fund_sufficient, is_savings_first_recommendation`) — verified by a test asserting the exact field set and that no field name contains `expense`, `cluster`, `persona`, `kaggle`, or `savings_rate`. There is no code path by which a Kaggle-only expense-persona cluster could reach a FAR-Trans customer's compliance evaluation, because there is no field to carry it. No savings-rate or expense-ratio value is fabricated anywhere (Phase 5 already established these are unavailable in FAR-Trans; nothing here contradicts that).

## 14. Error handling

Three distinct failure modes, kept distinguishable:

1. **Invalid rule configuration** (bad severity, unknown condition, duplicate id, blank id) → `pydantic.ValidationError` at `load_rules()`/`RulesConfig` construction time — a system/config error, never silently ignored or defaulted.
2. **A genuine rule violation** (e.g. QQQ weight outside its band) → a valid `REJECT` (or `WARN`) `ComplianceResult`, with a `reason` describing exactly what failed.
3. **Missing required data** (approved 2026-09-14: **fail-closed**) → the affected rule is marked `triggered=True` at its own configured severity, with a `reason` naming the missing input (e.g. `"required data unavailable: portfolio weights were not provided"`) — for every rule in the current YAML (all REJECT), missing data always REJECTs. This is deliberately indistinguishable in *blocking effect* from a genuine violation while remaining distinguishable in the result's `reason` text, so an internal data-availability problem can never present as a silent PASS. Verified directly: a completely empty `ComplianceProposal()` REJECTs (`test_missing_data_never_silently_passes`).
4. **Internal engine failure** (e.g. a YAML file that fails to parse at all) → an exception propagates (`yaml.YAMLError`, `ValueError`) — never silently converted into a PASS.

## 15. Security considerations

`load_rules()` uses `yaml.safe_load` **exclusively** — never `yaml.load`/`yaml.unsafe_load`. Verified directly: a YAML file using the `!!python/object/apply:os.system` tag (which `yaml.load` would execute) is refused with `yaml.YAMLError`, not silently run. `condition` values are looked up in a fixed Python dict (`_RULE_REGISTRY`) built entirely from hand-written functions in this module — configuration data is never passed to `eval()`, `exec()`, or any dynamic-import mechanism; an attempted expression-injection string (`"__import__('os').system(...)"` as a `condition` value) is rejected by Pydantic validation before it could ever be looked up. The actual repository `compliance_rules.yaml` was also checked directly for the absence of any `!!python` tag.

## 16. Tests

**51 new Phase 9 tests**, all passing (`tests/backend/core/test_compliance.py`):

| Category | Tests |
|---|---|
| YAML loading / schema validation | 10 |
| Rule version | 1 |
| Individual rules — PASS | 6 |
| Individual rules — REJECT (incl. all 4 risk levels, general-cap intersection) | 9 |
| WARN + aggregation (incl. REJECT dominance both rule orders) | 5 |
| Fail-closed missing-data | 4 |
| Invalid input handling | 1 |
| No weight mutation | 1 |
| Determinism | 1 |
| Serialization | 1 |
| Binding gate | 4 |
| End-to-end safety contract (incl. the "most important test") | 3 |
| Security (no eval/exec via YAML) | 3 |
| Kaggle/FAR-Trans separation | 1 |
| metrics summary | 1 |

**Full project test suite: 339 tests, all passing** (`pytest tests/ --collect-only -q` confirms 339 collected, 0 skipped; 339 passed in 276s). No regressions in Phases 0-8.

## 17. Database changes

**None.** `Recommendation` (the table that would eventually store a compliance-gated recommendation) is explicitly documented in `backend/wealthpilot/db/models.py` as "Written by the recommendation engine (**Phase 14**)" — not this phase. Per this phase's own instruction ("If persistence is not specified: keep the core compliance evaluation DB-independent"), no table was added and none of Phases 1-8's tables were touched. `db/models.py`'s modification time (2026-09-13 23:39) predates this phase entirely; the 3 existing Alembic migrations are unchanged.

## 18. Files created/modified

- **Modified**: `config/compliance_rules.yaml` (from an empty Phase-0 placeholder to 5 real, tested rules + `version: "v1"`).
- **Created**: `backend/wealthpilot/core/compliance.py`.
- **Created**: `tests/backend/core/test_compliance.py`.
- **Created**: this report.
- **Modified**: `models/metrics.json` — merged a `"compliance"` key (rules version + a static rule-set summary: id/severity/condition per rule, no fabricated ML-style statistic like an "accuracy" or "pass rate," since none exists to report). All five prior keys (`risk, behaviour, expense, market, portfolio`) are unchanged.
- **Untouched**: `models/risk/`, `models/expense/`, `models/behaviour/`, `models/market/`, `models/portfolio/`, `backend/wealthpilot/db/models.py`, all Alembic migrations, all raw datasets.

## 19. Manual verification

- [x] Authoritative documents inspected (CLAUDE.md, PROJECT_PLAN.md, MASTER_PROMPT.md, BUILD_PLAN.md).
- [x] Existing `compliance_rules.yaml` inspected (found as an empty Phase-0 placeholder).
- [x] Rules are configuration-driven — thresholds for the two portfolio rules are read live from Phase 8's approved constants, not duplicated in YAML.
- [x] Rule schema validated (Pydantic, tested against every invalid-shape case: unknown condition, invalid severity, blank id, duplicate id).
- [x] Rule version identified (`v1`, recorded on every result).
- [x] PASS implemented and tested for every rule.
- [x] WARN implemented (aggregation-level) and tested, though no WARN rule ships yet (approved).
- [x] REJECT implemented and tested for every rule.
- [x] REJECT dominates aggregation — tested in both rule orders.
- [x] Invalid/missing input cannot become PASS — fail-closed, tested directly including the empty-proposal case.
- [x] Compliance does not modify portfolio weights — tested directly (byte-identical before/after).
- [x] Risk suitability follows the approved Phase 8 rules exactly (same constants, same intersection logic).
- [x] Emergency-fund logic does not duplicate Phase 7 — the rule takes booleans, never imports Phase 7's calculation functions.
- [x] Kaggle expense model is not incorrectly applied to FAR-Trans — structurally impossible (no such field exists on `ComplianceProposal`).
- [x] No fabricated savings/expense values anywhere.
- [x] No market forecasting added.
- [x] No portfolio optimization added — no MVO/HRP/frontier/rebalancing code imported.
- [x] No LLM calculations, no Gemini, no AutoGen, no LangGraph anywhere in this phase.
- [x] No Phase 10 code started.
- [x] No unsafe eval/exec — `yaml.safe_load` only, verified directly against a malicious payload.
- [x] Full test suite passes (339/339, 0 regressions).
- [x] Previous Phase 0-8 tests remain passing.
- [x] Raw datasets unchanged (no file touched since Phase 7).
- [x] Database integrity verified (no table added or modified).
- [x] Previous artifacts preserved (`models/{risk,expense,behaviour,market,portfolio}/` untouched; `metrics.json`'s 5 prior keys unchanged).

## 20. Known limitations

1. **No WARN rule exists yet** — by design (§3), since no WARN threshold is specified anywhere in the project's authoritative documents. The engine is ready for one; none was invented.
2. **The emergency-fund and risk-level inputs are plain booleans/strings the caller must supply correctly** — this phase does not call into Phase 4/7 itself to compute them (deliberately, to avoid duplicating those phases' logic), so a future integration phase is responsible for wiring the real computed values in.
3. **This is an educational decision-support prototype** — nothing here claims or implies regulatory certification, licensed financial-advice compliance, or legal suitability determination; no such claim was invented (per this phase's own explicit instruction not to invent legal/regulatory requirements).

## 21. Next phase

**Phase 10 — Agent State / Nodes.**

**Do not begin Phase 10.** Awaiting explicit approval of this report.
