"""The integrated sentiment pipeline entry point: one call runs every stage that is currently permitted and reports every other stage as an explicit, typed blocked state.

Stages: ``accounting`` (manifest → day files → reconciliation → late arrivals → completeness/coverage/near-empty, i.e. ``orchestrate_window``) always runs; ``scoring`` runs only when an
approved ``ScorerPort`` is supplied AND the scorer policy is applied (it never is today), and scores only the candidates ``scored_records.scoring_inputs`` selects; ``conversion`` then builds
``ArticleRecord`` objects (``scored_records.convert``); ``features`` and ``evaluation`` are blocked by named, current reasons. Nothing is inferred: a
stage is ``COMPLETED`` only when it ran, and a blocked stage carries the reasons read from the live policy table. No model inference, training, network or file access happens here beyond
what ``orchestrate_window`` already does through the caller's ``day_source``.

Not run on purpose (owner approvals missing): daily features (the remaining policy gates and E4) and any evaluation (E5). Both are reported as blocked. ``scored_at`` is supplied by the caller:
the core path reads no clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from datetime import datetime

from wealthpilot.data.gdelt.errors import GdeltToolError
from wealthpilot.data.gdelt.sentiment.orchestrator import WindowInputs, WindowReport, orchestrate_window
from wealthpilot.data.gdelt.sentiment.policy import PolicyBlockedError, PolicyState, REQUIRED_POLICIES
from wealthpilot.data.gdelt.sentiment.schema import THEMES, ArticleRecord
from wealthpilot.data.gdelt.sentiment.scored_records import ConversionResult, convert, scoring_inputs
from wealthpilot.data.gdelt.sentiment.scorer_port import SCORER_POLICY, ScoreOutcome, ScorerPort, score_candidates
from wealthpilot.data.gdelt.sentiment.tone_baseline import (
    APPROVED_MAPPING, ToneDerived, ToneIntervalSummary, count_tone, derive_interval_tone, observe_tone,
)

# No evaluation target, instruments, calendar, split or acceptance criteria are approved (worksheet E5a-e). Change only on a recorded owner decision.
EVALUATION_APPROVED = False
CONVERSION_CONTRACT_APPROVED = True           # owner decisions E3a/E3b/E3c and OD-11a/b/c (see scored_records.py); it removes no policy gate
FEATURES_AUTHORISED = False                   # E4: daily features need an explicit owner go-ahead after E1-E3 and every policy applied


class PipelineError(GdeltToolError):
    code = "sentiment_pipeline_error"


class StageStatus(str, Enum):
    COMPLETED = "completed"
    BLOCKED_BY_POLICY = "blocked_by_policy"
    BLOCKED_NO_SCORER = "blocked_no_scorer"
    BLOCKED_NOT_APPROVED = "blocked_not_approved"


@dataclass(frozen=True)
class StageReport:
    name: str
    status: StageStatus
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PipelineResult:
    window: WindowReport
    stages: tuple[StageReport, ...]
    scores: tuple[ScoreOutcome, ...] = ()        # empty unless the scoring stage COMPLETED
    conversion: ConversionResult | None = None   # None unless the conversion stage COMPLETED
    tone: tuple[ToneIntervalSummary, ...] = ()   # the local GDELT tone baseline: validation counts
    tone_derived: tuple[ToneDerived, ...] = ()   # the descriptive document-tone mean; empty while any required policy is unapplied

    def stage(self, name: str) -> StageReport:
        return next(s for s in self.stages if s.name == name)

    @property
    def digest(self) -> str:
        return self.window.digest()


def blocking_gates(state: PolicyState) -> dict[str, tuple[str, ...]]:
    """What currently blocks each downstream stage, read from the live policy state and the owner-approval constants. An empty tuple means nothing blocks it."""
    pending = tuple(f"{n}={s}" for n, s in state.unresolved(REQUIRED_POLICIES))
    scorer = tuple(f"{n}={s}" for n, s in state.unresolved((SCORER_POLICY,))) + ("no approved, installed scorer or weights (E1)",)
    features = pending + scorer[len(scorer) - 1:] + (() if FEATURES_AUTHORISED else ("daily features not authorised (E4)",))
    return {"tone_derived": pending, "scoring": scorer, "features": features,
            "evaluation": features + (() if EVALUATION_APPROVED else ("no approved target, instruments, split, baselines or acceptance criteria (E5)",))}


def run_pipeline(inputs: WindowInputs, *, scorer: ScorerPort | None = None, policy: PolicyState | None = None,
                 scored_at: datetime | None = None) -> PipelineResult:
    """Run accounting, then scoring and conversion only if permitted. ``policy`` defaults to the window's own (live) policy status."""
    window = orchestrate_window(inputs)
    state = policy if policy is not None else window.policy_state()
    stages = [StageReport("accounting", StageStatus.COMPLETED,
                          (f"{len(window.issues)} issue(s) reported", f"{sum(len(i.records) for i in window.intervals)} candidate record(s) placed",
                           *(f"limitation: {x}" for x in window.residual_limitations())))]
    tone = tuple(ToneIntervalSummary(i.origin_date, count_tone([observe_tone(r) for r in i.records])) for i in window.intervals)
    stages.append(StageReport("tone_baseline", StageStatus.COMPLETED,
                              ("raw GDELT tone fields validated and counted per theme (document-level lexicon tone; no title scorer involved)",)))
    pending = tuple(f"{n}={st}" for n, st in state.unresolved(REQUIRED_POLICIES))
    tone_derived: tuple[ToneDerived, ...] = ()
    if pending:
        stages.append(StageReport("tone_derived", StageStatus.BLOCKED_BY_POLICY,
                                  (f"mapping {APPROVED_MAPPING.version} is {APPROVED_MAPPING.status} (descriptive document tone only), but required policies are unapplied", *pending)))
    else:
        tone_derived = tuple(derive_interval_tone([observe_tone(r) for r in i.records], i.origin_date, t, APPROVED_MAPPING, i.assessment, policy=state)
                             for i in window.intervals for t in THEMES)
        stages.append(StageReport("tone_derived", StageStatus.COMPLETED, (f"{len(tone_derived)} theme-interval value(s): descriptive document tone, not sentiment or direction",)))
    scores: tuple[ScoreOutcome, ...] = ()
    conversion: ConversionResult | None = None
    if scorer is None:
        stages.append(StageReport("scoring", StageStatus.BLOCKED_NO_SCORER, ("no approved scorer was supplied",)))
        stages.append(StageReport("conversion", StageStatus.BLOCKED_NO_SCORER, ("nothing was scored",)))
    else:
        if scored_at is None:
            raise PipelineError("scored_at is required when a scorer is supplied (the core path reads no clock)")
        candidates = [r for i in window.intervals for r in i.records]
        try:
            to_score = scoring_inputs(candidates, min_chars=inputs.min_chars)
            scores = score_candidates(to_score, scorer, policy=state, min_chars=inputs.min_chars)
        except PolicyBlockedError as exc:
            stages.append(StageReport("scoring", StageStatus.BLOCKED_BY_POLICY, (str(exc),)))
            stages.append(StageReport("conversion", StageStatus.BLOCKED_BY_POLICY, ("nothing was scored",)))
        else:
            stages.append(StageReport("scoring", StageStatus.COMPLETED, (f"{len(scores)} outcome(s) for {len(candidates)} candidate(s)",)))
            conversion = convert(candidates, scores, scorer.identity, scored_at=scored_at, min_chars=inputs.min_chars)
            stages.append(StageReport("conversion", StageStatus.COMPLETED, (f"{len(conversion.records)} record(s) converted",
                                                                          f"{len(conversion.not_converted)} candidate(s) not converted (not theme relevant)")))
    unresolved = tuple(f"{n}={s}" for n, s in state.unresolved(REQUIRED_POLICIES))
    reasons = list(unresolved)
    if not CONVERSION_CONTRACT_APPROVED:
        reasons.append("candidate-to-scored-record contract not approved (E3, OD-11)")
    if not FEATURES_AUTHORISED:
        reasons.append("daily features not authorised (E4)")
    stages.append(StageReport("features", StageStatus.BLOCKED_BY_POLICY if reasons else StageStatus.COMPLETED, tuple(reasons)))
    stages.append(StageReport("evaluation", StageStatus.COMPLETED if EVALUATION_APPROVED else StageStatus.BLOCKED_NOT_APPROVED,
                              () if EVALUATION_APPROVED else ("no approved target, instruments, split, baselines or acceptance criteria (E5)",)))
    return PipelineResult(window, tuple(stages), scores, conversion, tone, tone_derived)
