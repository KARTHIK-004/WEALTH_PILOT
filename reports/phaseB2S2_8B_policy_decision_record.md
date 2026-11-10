# Research Enhancement Track — Phase B2-S2.8B, Part A: Policy Decision Record

**Status: RECORD OF OWNER DECISIONS. This document records; it does not approve anything further, and it does not turn a provisional
research choice into a validated scientific conclusion.** Date: 2026-10-20 (UTC). Written for: the project owner and any later implementer.

## 0. Source of the decisions, and how gaps are handled

The S2.8B instruction states that the conversation holds 16 owner decisions, answering the 16 numbered questions at the end of
`reports/phaseB2S2_8A_policy_decisions.md`. **No separate message containing 16 answers was present in the conversation available to
this phase.** The decisions below are therefore taken from the owner's S2.8B instruction text (Part A's list of "important distinctions",
Part B's fixes and the "out of scope" paragraph). Where the instruction states a choice, it is recorded as **SELECTED**. Where it does not
address a question, the entry says **NOT STATED** and the question stays open: no answer was assumed. If the original answers differ from
this record, this record is to be corrected, not the code first.

**Status vocabulary**

| Status | Meaning |
| --- | --- |
| SELECTED | stated by the owner; usable as policy direction |
| SELECTED – PROVISIONAL | stated by the owner, explicitly provisional until evidence supports it |
| SELECTED – IMPLEMENTED | stated by the owner and implemented in S2.8B |
| SELECTED – NOT YET IMPLEMENTED | stated by the owner; implementation deferred to a separately bounded phase |
| NOT STATED | not addressed in the instruction; unresolved |

A policy is **usable by downstream code only when the code applies it** (`APPLIED_APPROVED` / `APPLIED_PROVISIONAL` in `policy.py`).
"Selected" is not "applied". Nothing is applied yet, so every required policy still blocks conversion and feature generation.

## 1. The 16 decisions

| # | Topic | Decision as stated | Status | Scope and rationale | Affected components |
| --- | --- | --- | --- | --- | --- |
| 1 | Unknown near-empty indicator | An unknown (NULL) near-empty status is **neither complete evidence nor verified no-news**. The specific mechanism (interval unusable, or the window fails without a baseline) is not named | SELECTED; mechanism NOT STATED | An unknown flag is a missing baseline, not a measurement. It must never be read as "not near-empty" or as "empty" | `manifest_adapter` (passes NULL unchanged), `coverage.interval_count`, `features._assess_day`, `orchestrator` (does not use it yet: F2b open) |
| 2 | Explicit near-empty (flag 1) | **Primary run: uncovered. Sensitivity run: may be treated as covered, with the flag preserved** | SELECTED – PROVISIONAL | Keeps the existing semantics for the primary result and measures how much the choice matters | `coverage.interval_count` (primary already), a later sensitivity switch (not built) |
| 3 | Near-empty detector parameters | The detector's parameters (10% of the median, previous 14 days, at least 7 observations) are **provisional** until evidence supports them. Whether a 14-day lookback must be processed first is NOT STATED | SELECTED – PROVISIONAL; lookback rule NOT STATED | They are proposals labelled PROPOSED in `engine.py`; no contiguous data has measured them | `engine._near_empty` (unchanged), `manifest.baseline_rows` |
| 4 | Source-coverage thresholds | **Primary 0.75; sensitivity 0.50 and 0.90** | SELECTED – PROVISIONAL | In the audit data the three give nearly the same null days (S2.8A §3), but the audit did not cover delays or the causal near-empty rule | `features.SentimentConfig.coverage_threshold`, a later sensitivity runner |
| 5 | Coverage denominator | **The full expected nominal-slot grid.** An absolute limit on consecutive missing slots is NOT STATED | SELECTED (denominator); limit NOT STATED | The denominator must not shrink when slots are missing | `features._assess_day`, `features.nominal_grids` (already so) |
| 6 | Scoring-coverage threshold | NOT STATED. The existing behaviour (report `scoring_coverage`, no threshold) stands | NOT STATED | Nothing was invented | `features._theme_row` |
| 7 | Late and earlier-nominal batches | Delayed batches are **assigned by verified availability time**; **earlier nominal batches arriving inside the requested window must be detected** (F1). The mechanism (detect-and-fail-closed, read earlier files, or a lookback of L days) is NOT STATED | SELECTED – NOT YET IMPLEMENTED (F1 is out of scope for S2.8B) | Preserves point-in-time assignment and stops a false "verified no records" | `orchestrator` (window partition), `adapt_manifest` (would take the extra rows) |
| 8 | Delayed batch with zero rows | NOT STATED. The orchestrator is strict (never evidence of absence) and the aggregator is looser; the disagreement is F2 | NOT STATED | Left open deliberately | `orchestrator`, `features._theme_row` |
| 9 | Repeated content | **Retained.** URL or title similarity is **evidence of a possible relationship, not proof of story identity.** Which relations may be linked, and at what evidence level, is NOT STATED | SELECTED (retention, no identity claim); linking rules NOT STATED | Dropping or merging would assert an identity the data cannot prove | `dayfile_adapter` (retains), `orchestrator.RepeatedContent` (counts only) |
| 10 | Counting unit, first experiment | **Every eligible record, with a repetition sensitivity analysis** | SELECTED – PROVISIONAL (proposed unit, not validated) | The simplest unit; the sensitivity analysis measures the effect of repeats | a later feature step (not built) |
| 11 | Cross-layer vocabulary | NOT STATED. The four-level vocabulary of S2.8A §6 stays a proposal | NOT STATED | Not implemented | `orchestrator`, `features` (F2/F2b open) |
| 12 | Company-item reconciliation (F3) | **Company-item counts must reconcile with the record flags** | SELECTED – IMPLEMENTED | A same-stage count already stored by the engine; a mismatch means the batch is not what the manifest says | `slots.reconcile_slot`, `SlotAccounting.rows_company_item`, `orchestrator` |
| 13 | Version consistency (F4) | **Parser and filter versions must be consistent within a window** | SELECTED – IMPLEMENTED | A mixed window cannot say which version is right, so it fails closed | `orchestrator` (`version_mismatch`, `mixed_versions`) |
| 14 | Policy blocking (F6) | **Unresolved required policies block downstream conversion and feature generation** | SELECTED – IMPLEMENTED | The pipeline must not produce a trusted-looking result while a decision is open | `policy.py`, `features.aggregate_daily` (the only existing downstream boundary), `orchestrator.WindowReport` |
| 15 | Digest (F7) | **Digests must deterministically bind record content, provenance, input files, versions, the window and the relevant configuration** | SELECTED – IMPLEMENTED | A digest that omits content cannot identify a result | `orchestrator.WindowReport.digest` |
| 16 | Order of work | The first corrective phase covers F5, F7, F6, F3 and F4. **F1, F2/F2b, coverage plumbing, near-empty detector changes and repeated-content labelling need a separately bounded follow-up** | SELECTED | Small, decision-light items first; the rest after the contracts are verified | this phase's scope |

## 2. Provisional choices (not validated conclusions)

Provisional until evidence supports them: the coverage thresholds (0.75 / 0.50 / 0.90), the near-empty detector parameters, the choice of
primary near-empty handling, and the record-counting unit with its repetition sensitivity. None of these is a scientific finding. Each
result produced under them must say so (`APPLIED_PROVISIONAL` stays visible in `PolicyState.provisional()`).

## 3. Explicitly unresolved and blocked

- Sentiment model, licence and dependency approval.
- Polarity validation.
- Forecast target and experimental protocol.
- Independent validation of the GDELT relevance/theme filter (the B2 evaluation still lacks independent labels).
- Full-window acquisition.
- Scoring, trusted feature generation, model evaluation and production integration.

Also open and not covered by any recorded decision: questions 6, 8 and 11; the mechanism parts of 1 and 7; the lookback rule of 3; the
absolute missing-slot limit of 5; the linking rules of 9; holiday and early-close calendars; theme-specific cutoffs; the cross-interval
story policy.

## 4. What this record does not change

The approved evaluation criteria (D8), the D12/D12.1 guard, the D13 lock, provider gates, compliance rules, the build lock and the adapter
registry are untouched, and the tests that assert them still pass. No ADR was added: these are research-policy decisions for this track,
not changes to the delivered system's architecture; an ADR can be added on request when a decision becomes architectural.

---

## Supersession note (added in S2.8C)

The S2.8C instruction states that the earlier owner-decision message selected **C-min** for question 7 (detect batches whose nominal
timestamp precedes the window and whose verified availability falls inside it; mark the receiving interval incomplete until the earlier batch
is accounted for; do not extend the requested window). Row 7 above therefore reads "mechanism NOT STATED" only because that message was not
visible to S2.8B; it is superseded by `reports/phaseB2S2_8C_F1_late_arrival_report.md` section 1, which also replaces the label "NOT STATED"
for other items by "UNCONFIRMED (not found in the evidence available; may have been answered)". The original text above is kept unchanged.
