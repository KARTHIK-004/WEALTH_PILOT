# Phase B2-U10: B2 completion plan

Date: 2026-10-19. Status: **a plan only. Nothing here is scheduled as approved, and no task below has started.** B2 is incomplete.

Written for: you, the project owner. Part of the [U10 readiness report](phaseB2U10_readiness_report.md); decision IDs (D1 to D14) are defined there.

**How to read it.** Work is split into three tracks by what it needs. A task never appears as ready if a decision it depends on is open. Each task states what it may touch, what it must not, how it is accepted, how to undo it, and whether it needs you.

**Standing prohibitions for every task:** no provider or network call; no real AI output; no real labels or suggestions; no freeze or approval record; the sealed key stays closed; nothing under `datasets/` changes; `NETWORK` and `DEV_SAMPLE` stay as they are; the build lock stays `False` and the adapter list empty; no weakening of any gate or check; no threshold change; no commit unless you ask.

## Track 1: decision-dependent (blocked until you decide)

| ID | Task | Depends on | Output |
| --- | --- | --- | --- |
| T1.1 | Choose the methodology (D1) and exclusion setting (D2) | nothing | a written choice; it decides which of the other tasks exist |
| T1.2 | Decide reweighting (D3), recall gate and target (D5), bootstrap generator (D6) and interpretation (D7b) | T1.1 helps but is not required | a written decision for each |
| T1.3 | Freeze the criteria (D4) | **T1.2 first** (they change what the criteria mean) | an approval reference and a reviewed `decision.py` change |
| T1.4 | Map the two unmapped review origins (D10, D11) | T1.1 (matters only for M2 and M3) | a chosen mapping |
| T1.5 | Choose polarity (D7a), provider (D8) and data-handling principle (D9) | T1.1 (M2 or M3 only) | decisions; Gate B and C inputs |
| T1.6 | Approve or reject the retention design and set the period (D14) | T1.1, T1.5 | an approval or a revision request |
| T1.7 | Write the real experiment config and the gate A to D records | T1.1 to T1.6, **and** the adapter (T3.2) | approval records bound to the dry run's hashes (created by you) |

Approval needed for every Track 1 task: **yes, from you, in writing.** If you choose **M1**, T1.4 to T1.7 and all of Track 3 except T3.5 and T3.6 do not apply.

## Track 2: safe offline work (no decision needed unless noted)

| ID | Task | Prerequisites | Allowed files and changes | Forbidden | Acceptance | Tests | Rollback | Your approval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T2.1 | Correct the U9 capture-recall statement | none | a superseded-by note inside `reports/phaseB2U9_…md`; `docs/MEMORY.md` | rewriting the old report | note present and links to U10 section 3.3 | none | revert the note | no (done in this phase) |
| T2.2 | Bridge hardening F1 to F3: verify the review chain, compare the manifest's chain heads with the current chains, tie each `review_record_sha256` to the review record, block when a named chain is missing | none, but it is a code change | `ai_bridge.py`, `ai_origin.py`, `test_label_bridge.py` | any write path; relaxing a check; touching `annotate.py` | the three probes in section 2.3 of the readiness report each become refusals; all 794 tests still pass | probe tests (chain edited, non-terminal append, forged review hash, chain deleted), regression | `git`-level revert of those files; no data depends on them | **yes (D12)** |
| T2.3 | Label capture recall in the independent-reference scope as invalid under parent weights (F4) | none, a code change | `evaluate.py` (scope metadata), its test | changing any weight, denominator or target | the field carries an explicit "not valid under parent weights" note; no number changes | a test on the scope output | revert | **yes (D13)** |
| T2.4 | Reproducible statistics script and fixture | none | a new script under `scripts/` or the tests, reading only `selection_log.json` and `annotation_A.csv` public columns | opening the key; reading labels | reproduces section 3 of the readiness report byte for byte | a test comparing its output with the documented values | delete the file | no |
| T2.5 | Retention design test specification as skipped or xfail tests | none | `tests/backend/data/gdelt/` only, marked not-implemented | implementing the design | the matrix rows 1 to 20 exist as named, documented, skipped tests | collection passes; skipped counts reported | delete | no |
| T2.6 | Non-mutating integrity audit script (provenance, fingerprint, overlap rule, gate state in one command) | none | a read-only command or script | writing records | one command prints the section 1 table of the readiness report | a test that it writes nothing | delete | no |
| T2.7 | Regression planning | none | this document | n/a | the commands below are used unchanged | n/a | n/a | no |

**Test commands (unchanged until a task needs more):** `pytest tests/backend/data/gdelt -q -p no:cacheprovider` (expected: 794 passed now). Suites that were **not run and must not be reported as passing:** the hosted-database backend suite, `npx tsc -b`, `npm run build`, `npx oxlint`, and the full-project `pytest tests/`.

## Track 3: needs explicit authorisation (do not start)

| ID | Task | Prerequisites | Allowed changes | Forbidden | Acceptance | Tests | Rollback | Approval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T3.1 | Retention implementation (payload files, expiry) | T1.6; design approved | per the design's sequence 1 to 3 | migrating or rewriting any existing chain; touching the runner before step 4 | the 20 matrix tests pass | the matrix | revert; discard any v2 folder | **yes** |
| T3.2 | A provider adapter | T1.1, T1.5; possibly a library approval | one adapter file, registered only with the lock change | enabling the lock in the same change as writing the adapter | adapter unit tests with a fake transport only | adapter tests | revert | **yes** |
| T3.3 | Create gate A to D records | T1.7 | the real experiment config | creating a record for you | each `binds_sha256` equals the dry run's hash | `blockers` shows none unmet except the lock | delete the config | **yes, you create them** |
| T3.4 | Lift the build lock and register the adapter; run | all of T3.1 to T3.3 and a matching dry run | the lock and registry | any other change in the same edit | explicit execution authorisation recorded | a full regression | revert the lock | **yes, explicit** |
| T3.5 | Labelling (M1) or review (M2, M3), then freeze and evaluation | T1.1, T1.3 | working copy via the existing workflow; freeze record | opening the key before the freeze | freeze created by you; evaluation after the checks | existing suite | none after the freeze; before it, corrections are logged | **yes** |
| T3.6 | Full-window acquisition | its own authorisation; the driver does not exist | none now | any acquisition | n/a | n/a | n/a | **separate, yes** |
| T3.7 | Lock the `NETWORK` and `DEV_SAMPLE` switches | your decision | the two constants and one test that asserts the current state | any other switch | switches `False`; the dependent test updated | gdelt suite | revert | **yes** |

## Dependency order

```
T1.1 methodology ─┬─► T1.2 ─► T1.3 freeze criteria ─────────────► T3.5 label/review, freeze, evaluate ─► B2 evaluation
                  ├─► T1.4 origin mapping ┐
                  └─► T1.5 provider/data ─┼─► T1.6 retention ─► T3.1 ─┐
                                          └─► T3.2 adapter ──────────┼─► T1.7 ─► T3.3 ─► T3.4 (M2 or M3 only)
T2.2, T2.3 (after D12, D13) and T2.4 to T2.6 are independent of the above.      T3.6 acquisition is separate throughout.
```

## Stop conditions

Stop and report, do not work around, if: a baseline differs from section 1 of the readiness report; a safety invariant stops holding; a task needs the key, a provider, the network or real data; a check would have to be weakened to pass; a decision it depends on is open; or a test needs hosted services that are unavailable.

## What "B2 complete" would require

An approved methodology; frozen criteria; labels made under it; a valid evaluation (verified provenance, adequate evidence, a freeze before the key); the filter decision applied; the ADR written; and, separately authorised, full-window ingestion. **None of these exists; this plan does not claim any.**

## Recommended single next step

Decide **D1** (M1, M2 or M3). It costs nothing, needs no code, and decides which half of Tracks 1 and 3 exists at all. If you also authorise **D12 and D13**, T2.2 and T2.3 can run safely in the same pass, since they only tighten verification and a reported field.
