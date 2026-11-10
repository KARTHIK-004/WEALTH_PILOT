# Sentiment Governance Status (as of 2026-11-05)

Written for: the project owner. This is the approval matrix as the repository records it, plus the later scoped decisions. **Silence is never treated as consent; a rejected or unresolved item was not acted on.** Source of the 56-row matrix: `docs/sentiment/stage_b/evidence/governance_statuses_2026-11-04.json` (extracted from `reports/sentiment_consolidated_approval_form.md`).

## 1. Summary counts (56 matrix rows)

| Status | Count | Items |
|---|---|---|
| APPROVE | 44 | A1, A3.1–A3.4, A3.6–A3.13, B1–B10, C1–C5, D3, D4, D6–D13, D15, D17, D18, E1, E2, E4, E5 |
| KEEP UNRESOLVED | 10 | A2, A3.3, D1, D2, D5, D14, D16, D19, E3, F1 |
| REJECT | 2 | **A3.5** (attribution and share-alike), **D20** (permission to generate, collect or label) |

## 2. Later scoped decisions (recorded in ADRs; each narrower than a matrix row)

| Date | Decision | Scope | Record |
|---|---|---|---|
| 2026-11-03 | Replacement candidates reviewed; neither approved (financial DistilBERT blocked by provenance; Horizon blocked by approval) | review only | ADR-054 |
| 2026-11-04 | Horizon `e60eb86f…` may be considered for **research inference only**, accepting web-crawl + LLM-generated text + LLM labels, no human validation | research inference; **no** production, no dataset, no fine-tuning, no multilingual claim | ADR-054 addendum |
| 2026-11-04 | Stage A: download the 8 approved files and run in an isolated environment outside the repository and the project `.venv` | done; rollback backup kept | ADR-054 addendum, `STAGE_A_COMPLETION_REPORT.md` |
| 2026-11-04 | Stage B1: read-only readiness check | done | `STAGE_B1_RUNTIME_READINESS_REPORT.md` |
| 2026-11-04 | Stage B2.1: install the pinned Transformer stack into the project `.venv`; coexistence tests; boundaries: no registry change, no `api/lifespan.py` change, no startup warming | installed; coexistence tests completed after the recovery | `STAGE_B2_1_RUNTIME_COEXISTENCE_REPORT.md` |
| 2026-11-04 | Restore `setuptools==81.0.0` (limited to that correction, integrity verification and TensorBoard regression check) | done, all checks passed | `evidence/RECOVERY_RECORD.md` |
| 2026-11-07 | **R1** register Horizon as the `general` research candidate; **R2** place the exact approved artifacts and run the application-adapter smoke test; **R3** diagnose the intermittent `tests/training` native crash in isolated comparison environments | done within those limits; production activation, financial-domain use, datasets, training, human evaluation and every rejected governance item remain NOT authorised | ADR-056, `R1_…`, `R2_…`, `R3_…` reports |

## 3. Current capability matrix

| Capability | Status | Governing item(s) |
|---|---|---|
| Rules baseline `user_text_rules_v1` in production | **ACTIVE (unchanged)** | ADR-043 |
| Research comparison code, API, UI | **IMPLEMENTED, off by default** | ADR-053/055 |
| Horizon registered as the `general` research candidate | **DONE — owner decision R1, 2026-11-07** (research only; `financial` slot empty) | ADR-056 |
| Horizon artifacts placed in `models/sentiment_pretrained/horizon/` (git-ignored) and manifest written | **DONE — owner decision R2, 2026-11-07** (never committed or pushed) | ADR-056 |
| Real-weights adapter smoke test | **PASSED (9 tests), smoke only — not an accuracy evaluation** | `R2_APPLICATION_ADAPTER_SMOKE_TEST_REPORT.md` |
| Production Transformer activation | **BLOCKED** | F1/R14 unresolved; needs validation evidence that does not exist |
| Multilingual (non-English) handling | **Safe abstention only** | no approval, no evidence |
| FinBERT / RoBERTa / financial DistilBERT | **Not runnable** | A3.3 unresolved, A3.5 rejected; licence/provenance findings |
| Dataset creation, collection, human or AI labelling | **REJECTED** | D20 |
| Fine-tuning / training | **NOT AUTHORISED** | D1, D2, D5, D14, D20 |
| Real frozen evaluation manifest | **UNRESOLVED** | E3 |
| Data retention policy for stored text | **UNRESOLVED** (moot: nothing is stored) | D16 |
| Stage B2.2 | **NOT STARTED — needs approval** | — |

## 4. Owner decisions that would unblock further work (R1 and R2 were granted on 2026-11-07; the rest are not requested here)

1. ~~Register Horizon as the `general` research candidate~~ - DONE (R1, ADR-056).
2. ~~Place the verified files and run the adapter smoke test~~ - DONE (R2, ADR-056).
3. Reverse or scope D20 and resolve D1/D2/D5/E3/D19 if any quality evidence is to be produced.
4. Decide F1/R14 only after such evidence exists.
5. R3 (training-suite native crash) is reported in `R3_TRAINING_NATIVE_CRASH_INVESTIGATION.md`; any follow-up it recommends needs its own decision.

## 5. Hard prohibitions in force

Never access or modify the development `neondb`; never use plain pytest for DB-backed suites; no commit or push; no raw user text to Gemini or any external service; sentiment never affects risk, goals, portfolio, recommendations or compliance; the rollback backup `C:\Users\Administrator\.copilot\wealthpilot-taskcert-rollback` is not deleted; the GDELT scaffold failure is reported separately and not modified.
