"""Phase 9 — deterministic, YAML-driven compliance/suitability gate.

Pure, DB-free (same design as `core/goals.py` and `core/optimizer.py`):
`evaluate_compliance` takes a plain `ComplianceProposal` built from
already-computed Phase 4/7/8 outputs — it never recomputes a risk category,
a TVM/Monte Carlo figure, an emergency-fund amount, or a portfolio weight
itself (CLAUDE.md rule 1 in spirit: this module never invents a number
either, it only checks numbers computed elsewhere). No FastAPI, LangGraph,
AutoGen, or Gemini code exists here or is imported here.

**Rule source**: `config/compliance_rules.yaml`, loaded with
`yaml.safe_load` only (never `yaml.load`/`unsafe_load`, which can execute
arbitrary Python via `!!python/object` tags). Each rule's `condition` is a
controlled string identifier naming one specific, hand-written Python
function in `_RULE_REGISTRY` below — configuration NEVER supplies a Python
expression that gets evaluated or executed; an unrecognized `condition`
fails `RulesConfig` validation at load time rather than being silently
ignored.

**Decision states**: `PASS`, `WARN`, `REJECT` (MASTER_PROMPT.md section
15). Aggregation is a strict escalation, never a downgrade: any triggered
REJECT-severity rule sets the overall decision to REJECT and nothing can
change it back; a triggered WARN-severity rule escalates PASS to WARN but
never overrides an existing REJECT. There is currently no WARN-severity
rule in `compliance_rules.yaml` (approved 2026-09-14 — no WARN threshold is
specified anywhere in the project's authoritative documents, and inventing
one would violate this phase's own "do not invent arbitrary thresholds"
rule); the aggregation logic fully supports one being added later without
any code change here.

**Missing required data is fail-closed** (approved 2026-09-14): a rule
whose inputs are unavailable is marked `triggered=True` with a message
naming the missing data, at that rule's own configured severity — for
every rule in the current YAML that is REJECT, so missing data currently
always REJECTs. This is deliberately indistinguishable in *effect* from a
genuine rule violation (both block downstream processing) while remaining
distinguishable in the result's `reason` text, so an internal data-
availability problem can never present as a silent PASS.

**One deliberate exception (Phase 28)**: the four weight-validation rules
(`weights_sum_to_one`, `no_negative_weights`, `qqq_within_risk_band`,
`single_asset_cap`) do NOT fail-closed when `weights is None` AND
`is_savings_first_recommendation is True` — see `_missing_weights_outcome`.
A savings-first proposal legitimately has no weights, by
`agents/nodes.py::savings_first_node`'s own design ("skip optimization
entirely"); treating that as an invalid portfolio was a real, documented
bug (`reports/live_analysis_flow_fix_report.md` §2), not fail-closed
safety. This exemption applies ONLY to that exact combination — a
NORMAL-path proposal with no weights still fails closed exactly as
before, and a savings-first proposal that inconsistently DOES supply
weights is still fully validated against every rule. No rule was removed,
no severity changed, no threshold changed, and `emergency_fund_savings_first`
(the rule that actually detects an insufficient emergency fund) is
completely untouched by this exception.

**The binding gate** (`enforce_gate`): raises `ComplianceRejectedError`
when `decision == "REJECT"`, rather than returning a boolean a caller could
forget to check. This is the structural mechanism — required by
PROJECT_PLAN.md's "compliance returns a hard verdict that gates output; the
explanation node can never run on a rejected recommendation" and this
phase's own non-negotiable end-to-end contract — that makes bypassing a
REJECT require a caller to deliberately not call `enforce_gate` (or to
catch `ComplianceRejectedError` and ignore it, which nothing in this
codebase does), not merely forget an `if` check.

No LangGraph/AutoGen/Gemini node exists yet (deliberately out of Phase 9's
scope) — `enforce_gate` is the interface later phases call before running
an explanation/Gemini/API-response step.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml
from pydantic import BaseModel, field_validator

from wealthpilot.core.optimizer import GENERAL_SINGLE_ASSET_CAP, RISK_LEVEL_QQQ_BANDS

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RULES_PATH = REPO_ROOT / "config" / "compliance_rules.yaml"

DECISION_STATES = ("PASS", "WARN", "REJECT")
SEVERITIES = ("WARN", "REJECT")


# ---------------------------------------------------------------------------
# Proposal input
# ---------------------------------------------------------------------------


class ComplianceProposal(BaseModel):
    """Everything compliance needs, gathered from already-computed Phase
    4/7/8 outputs. `None` means "not provided" and is handled fail-closed
    by whichever rule needs it — this model itself does not require any
    field, since not every evaluation context has every signal available."""

    risk_level: str | None = None
    weights: dict[str, float] | None = None
    emergency_fund_sufficient: bool | None = None
    is_savings_first_recommendation: bool = False


# ---------------------------------------------------------------------------
# Rule check functions (the ONLY code that ever runs for a `condition`)
# ---------------------------------------------------------------------------


@dataclass
class _CheckOutcome:
    triggered: bool
    reason: str


def _missing_weights_outcome(p: ComplianceProposal) -> _CheckOutcome:
    """Shared "no weights" handling for every weight-validation rule below
    (Phase 28 fix -- see `reports/live_analysis_flow_fix_report.md` §2 for
    the finding this addresses): a savings-first proposal legitimately has
    no weights, by design (`agents/nodes.py::savings_first_node` -- "skip
    optimization entirely"), so `is_savings_first_recommendation=True`
    together with `weights=None` is a genuine PASS for these rules, not a
    REJECT -- a savings-first state must not be interpreted as an invalid
    portfolio. Any OTHER "no weights" case (a normal-path proposal with
    none at all) remains fail-closed REJECT, completely unchanged. This
    does not weaken these rules for an actually invalid portfolio: the
    moment `weights` is non-`None`, every rule below still validates it in
    full regardless of `is_savings_first_recommendation` -- the exemption
    applies ONLY to the missing-weights case itself, nowhere else."""
    if p.is_savings_first_recommendation:
        return _CheckOutcome(False, "")
    return _CheckOutcome(True, "required data unavailable: portfolio weights were not provided")


def _check_weights_sum_to_one(p: ComplianceProposal) -> _CheckOutcome:
    if p.weights is None:
        return _missing_weights_outcome(p)
    total = sum(p.weights.values())
    if abs(total - 1.0) > 1e-6:
        return _CheckOutcome(True, f"portfolio weights sum to {total:.6f}, not 1.0")
    return _CheckOutcome(False, "")


def _check_no_negative_weights(p: ComplianceProposal) -> _CheckOutcome:
    if p.weights is None:
        return _missing_weights_outcome(p)
    negative = {a: w for a, w in p.weights.items() if w < -1e-9}
    if negative:
        return _CheckOutcome(True, f"negative (short) weights present: {negative}")
    return _CheckOutcome(False, "")


def _check_qqq_within_risk_band(p: ComplianceProposal) -> _CheckOutcome:
    if p.weights is None:
        return _missing_weights_outcome(p)
    if p.risk_level is None:
        return _CheckOutcome(True, "required data unavailable: portfolio weights or risk_level were not provided")
    if "QQQ" not in p.weights:
        return _CheckOutcome(True, "required data unavailable: proposal has no QQQ weight to evaluate")
    if p.risk_level not in RISK_LEVEL_QQQ_BANDS:
        return _CheckOutcome(True, f"unrecognized risk_level {p.risk_level!r}")
    lower, upper = RISK_LEVEL_QQQ_BANDS[p.risk_level]
    upper = min(upper, GENERAL_SINGLE_ASSET_CAP)  # same intersection Phase 8's effective_bounds() applies
    qqq = p.weights["QQQ"]
    if not (lower - 1e-9 <= qqq <= upper + 1e-9):
        return _CheckOutcome(
            True, f"QQQ weight {qqq:.4f} is outside the approved [{lower:.2f}, {upper:.2f}] band for {p.risk_level}"
        )
    return _CheckOutcome(False, "")


def _check_single_asset_cap(p: ComplianceProposal) -> _CheckOutcome:
    if p.weights is None:
        return _missing_weights_outcome(p)
    violators = {a: w for a, w in p.weights.items() if w > GENERAL_SINGLE_ASSET_CAP + 1e-9}
    if violators:
        return _CheckOutcome(
            True, f"asset(s) exceed the {GENERAL_SINGLE_ASSET_CAP:.0%} single-asset cap: {violators}"
        )
    return _CheckOutcome(False, "")


def _check_emergency_fund_savings_first(p: ComplianceProposal) -> _CheckOutcome:
    if p.emergency_fund_sufficient is None:
        return _CheckOutcome(True, "required data unavailable: emergency-fund status was not provided")
    if p.emergency_fund_sufficient:
        return _CheckOutcome(False, "")
    if p.is_savings_first_recommendation:
        return _CheckOutcome(False, "")
    return _CheckOutcome(
        True,
        "emergency fund is insufficient but a normal investment allocation was proposed "
        "instead of a savings-first recommendation",
    )


_RULE_REGISTRY: dict[str, Callable[[ComplianceProposal], _CheckOutcome]] = {
    "weights_sum_to_one": _check_weights_sum_to_one,
    "no_negative_weights": _check_no_negative_weights,
    "qqq_within_risk_band": _check_qqq_within_risk_band,
    "single_asset_cap": _check_single_asset_cap,
    "emergency_fund_savings_first": _check_emergency_fund_savings_first,
}


# ---------------------------------------------------------------------------
# YAML rule configuration + validation
# ---------------------------------------------------------------------------


class RuleDefinition(BaseModel):
    id: str
    description: str
    severity: str
    condition: str
    message: str

    @field_validator("severity")
    @classmethod
    def _valid_severity(cls, v: str) -> str:
        if v not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}, got {v!r}")
        return v

    @field_validator("condition")
    @classmethod
    def _known_condition(cls, v: str) -> str:
        if v not in _RULE_REGISTRY:
            raise ValueError(f"unrecognized condition {v!r}; no registered rule-check function for it")
        return v

    @field_validator("id")
    @classmethod
    def _non_blank_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("rule id must not be blank")
        return v


class RulesConfig(BaseModel):
    version: str
    rules: list[RuleDefinition]

    @field_validator("rules")
    @classmethod
    def _unique_ids(cls, v: list[RuleDefinition]) -> list[RuleDefinition]:
        ids = [r.id for r in v]
        if len(ids) != len(set(ids)):
            duplicates = {i for i in ids if ids.count(i) > 1}
            raise ValueError(f"duplicate rule id(s) in compliance_rules.yaml: {duplicates}")
        return v


def load_rules(path: Path = DEFAULT_RULES_PATH) -> RulesConfig:
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text)  # safe_load ONLY -- never yaml.load/unsafe_load
    if raw is None:
        raise ValueError(f"{path} is empty or not valid YAML")
    return RulesConfig.model_validate(raw)


def rules_summary(rules_config: RulesConfig) -> dict:
    """A `models/metrics.json`-safe summary of the loaded ruleset — no
    ML-style metric is fabricated (there is nothing trained here); this is
    purely an auditability record of which rules/version are active."""
    return {
        "version": rules_config.version,
        "n_rules": len(rules_config.rules),
        "rules": [
            {"id": r.id, "severity": r.severity, "condition": r.condition}
            for r in rules_config.rules
        ],
    }


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class RuleResult(BaseModel):
    rule_id: str
    description: str
    severity: str
    triggered: bool
    passed: bool
    message: str
    reason: str | None = None


class ComplianceResult(BaseModel):
    decision: str
    rules_version: str
    evaluated_at: str
    rule_results: list[RuleResult]

    @property
    def is_rejected(self) -> bool:
        return self.decision == "REJECT"


def evaluate_compliance(proposal: ComplianceProposal, rules_config: RulesConfig | None = None) -> ComplianceResult:
    """Deterministic: identical `proposal` + `rules_config` always produce
    an identical `ComplianceResult` (no randomness, no I/O beyond the
    already-loaded `rules_config`)."""
    if rules_config is None:
        rules_config = load_rules()

    rule_results: list[RuleResult] = []
    decision = "PASS"

    for rule in rules_config.rules:
        outcome = _RULE_REGISTRY[rule.condition](proposal)
        rule_results.append(
            RuleResult(
                rule_id=rule.id,
                description=rule.description,
                severity=rule.severity,
                triggered=outcome.triggered,
                passed=not outcome.triggered,
                message=rule.message,
                reason=outcome.reason or None,
            )
        )
        if outcome.triggered:
            if rule.severity == "REJECT":
                decision = "REJECT"
            elif rule.severity == "WARN" and decision != "REJECT":
                decision = "WARN"

    return ComplianceResult(
        decision=decision,
        rules_version=rules_config.version,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        rule_results=rule_results,
    )


# ---------------------------------------------------------------------------
# Binding gate
# ---------------------------------------------------------------------------


class ComplianceRejectedError(Exception):
    """Raised by `enforce_gate` on a REJECT decision. Nothing in this
    codebase catches this exception — it is meant to propagate all the way
    out of whatever later phase's explanation/Gemini/API step would
    otherwise have run next."""

    def __init__(self, result: ComplianceResult):
        self.result = result
        violated = [r.message for r in result.rule_results if r.triggered and r.severity == "REJECT"]
        super().__init__(f"compliance REJECTed ({len(violated)} rule(s)): {violated}")


def enforce_gate(result: ComplianceResult) -> ComplianceResult:
    """The ONLY sanctioned way to move from 'a compliance result exists' to
    'downstream processing (explanation, Gemini, API response) may
    proceed.' Raises on REJECT; returns `result` unchanged on PASS/WARN."""
    if result.decision == "REJECT":
        raise ComplianceRejectedError(result)
    return result
