# WealthPilot AI — Sentiment Subsystem: Final Completion Report

Date: 2026-11-05. Written for: the project owner (decision-maker) and examiners. Evidence labels: **VERIFIED** (command output recorded), **OBSERVED** (seen, not generalised), **NOT VERIFIED**, **BLOCKED** (needs an approval that has not been given), **NOT AVAILABLE** (the evidence cannot exist under current approvals). Nothing was committed or pushed.

## 1. Executive summary and separate statuses

| Status line | Value |
|---|---|
| Research implementation (code, API, UI, lifecycle guards, tests, docs) | **COMPLETE** |
| Rules production baseline (`user_text_rules_v1`) | **VERIFIED** (unchanged; behaviour pinned by 42 characterization tests — this is regression protection, not an accuracy result) |
| Transformer research inference | **VERIFIED** by direct loading (Stage A, B2.1) **and, since 2026-11-07 (R2), through the application's adapter and service on the real weights** (9-test opt-in smoke; see section 23) |
| Production Transformer activation | **BLOCKED** (F1/R14 unresolved; no validation evidence exists; Horizon not registered; flag off) |
| Human evaluation | **NOT AVAILABLE** (D20 rejected; D1/D2/D5/E3/D19 unresolved) |
| Accuracy / calibration / superiority claims | **NOT SUPPORTED** (none made) |

In one paragraph: the sentiment subsystem is now a complete, tested, privacy-conscious, off-by-default research comparison built around role slots (`financial`, `general`). Both slots are empty today because Horizon is approved only for research consideration and its registration needs an explicit owner decision, which I did not take. The production reading is still the rules baseline and nothing about sentiment reaches risk, goals, portfolio, recommendations or compliance.

## 2. Scope and authority

Brief: the 22-part master autonomous completion prompt. Binding limits honoured: no access to `neondb`; DB-backed suites only through `scripts/run_isolated_db_tests.py` (`neondb_test`); no commit/push; existing modified and untracked files preserved; no new dependency beyond the already-authorised B2.1 set; no Horizon production inference, flag change or registration; `user_text_rules_v1` not replaced; no raw user text to Gemini or any external service; no downloads, datasets or fine-tuning; D20 rejected, A3.3 unresolved, A3.5 rejected, E3/F1 unresolved, none acted on; B2.2 not started; the rollback backup `C:\Users\Administrator\.copilot\wealthpilot-taskcert-rollback` untouched; the GDELT scaffold failure reported separately, not modified.

## 3. Repository and governance audit (Phase 0)

Baseline: branch `master`, one commit (`71b363f`), 294 changed/untracked entries before the B2.1 work (now 296: the real-weights smoke test and the rules regression test are new; the slots test replaced the pair test). The approval matrix and later scoped decisions are in `SENTIMENT_GOVERNANCE_STATUS.md`.

## 4. Approval matrix summary

56 rows: 44 APPROVE, 10 KEEP UNRESOLVED (A2, A3.3, D1, D2, D5, D14, D16, D19, E3, F1), 2 REJECT (A3.5, D20). Later scoped decisions: Horizon for research inference only (2026-11-04); Stage A; B1; B2.1; `setuptools==81.0.0`.

## 5. Runtime recovery (Phase 1) — VERIFIED

Only `setuptools` 84.2.1 -> 81.0.0 (hash `fdd925d5…10d6`). `pip check` clean; `pkg_resources` and the three TensorBoard modules import; TensorFlow 2.17.0, Keras 3.15.1, NumPy 1.26.4, protobuf 4.25.9 unchanged. No inference or model loading was done as part of the recovery. Evidence: `docs/sentiment/stage_b/evidence/`.

## 6. Coexistence (B2.1 continuation) — VERIFIED

Decision: the original B2.1 authorisation covers the coexistence tests (no new package, no repository model placement, no registry/lifespan change, no application inference), so they were run; the reading is stated in `SENTIMENT_DECISION_LOG.md` item 1 and the owner can disregard the evidence if they disagree. Results (one machine, CPU): both import orders pass; the TensorFlow market model loads and predicts; Horizon loads offline (3.3-3.6 s) and gives logits identical to Stage A; 31 sequential rounds bitwise identical; peak 1332-1573 MB; medians 24 ms (Horizon) and 75-79 ms (market model); zero network attempts; two OpenMP runtimes coexist; the backend does not import TensorFlow at runtime. Recommendation: in-process is viable behind the guards; out-of-process remains the fallback. See the addendum (section 16) of `STAGE_B2_1_RUNTIME_COEXISTENCE_REPORT.md`.

## 7. Architecture (Phase 2) — COMPLETE

Role slots with `Candidate.registration`; shared adapter interface; closed reason vocabulary; comparison/overall rules; abstention; lifecycle guards (non-loading status, per-candidate non-blocking load lock, 30 s breaker, fixed error mapping, never-raise boundary, optional thread cap); ADR-055. Detail: `SENTIMENT_ARCHITECTURE.md`.

## 8. Rules baseline (Phase 3) — VERIFIED (characterization)

No rule was edited: improving rules without ground truth would invent behaviour. 42 tests over 30 fictional sentences pin gating, abstention, safeguards and determinism. Notable observed behaviours are recorded, not "fixed": negation and hypotheticals read as `uncertain`/weak; a neutral sentence reads as neutral/weak; a mixed sentence can read as negative.

## 9. Transformer research implementation (Phase 4) — implemented; adapter run NOT VERIFIED

Exact 40-character revision; safetensors only; manifest with SHA-256; `trust_remote_code=False`; offline; one softmax; label order from the model's own config; every failure is a fixed reason. The model card is `SENTIMENT_MODEL_CARD.md`. To obtain `INFERENCE_VERIFIED` through the adapter the owner must authorise Stage B (see section 21, request R2).

## 10. Multilingual (Phase 5)

Not approved, no evidence: safe abstention only. Tamil, mixed-script and code-mixed text are tested to never reach a model. The model's multilingual capability is unused and unvalidated.

## 11. API (Phase 6) — COMPLETE

`POST /api/profiles/{id}/personalized-insights` and `GET /api/sentiment-model/status`; RFC 7807 400 (over 1000 chars / control characters) and 422 (non-string); every analysis response keeps `model_version` and `data_source`; the status endpoint loads nothing. Breaking change to the never-enabled `transformer_research` shape (ADR-055). Reference: `SENTIMENT_API_REFERENCE.md`.

## 12. Frontend (Phase 7) — COMPLETE

One card per role slot; an empty slot is a plain "No model registered" card, not a failure; per-model "Rules-based reading" line; no confidence shown; unknown labels never rendered as neutral; no browser-side computation. `npm test` 279/279, mutation harness 200/200, `tsc -b`, `oxlint` (0 errors) and `npm run build` pass. Browser-based visual testing was **not** performed in this window.

## 13. Privacy and security (Phase 8) — audit complete

Data stays in process memory; nothing stored, logged, echoed or sent externally; supply-chain and path controls; residual risks listed. `SENTIMENT_PRIVACY_AND_SECURITY.md` has the data-flow diagram and control-to-test map.

## 14. Testing (Phase 9)

See `SENTIMENT_TEST_REPORT.md`. Highlights: 861 passed / 3 skipped in the sentiment set; core 1197 passed plus one stale-pin test fixed and re-run (3/3; the full core directory was not re-run afterwards); data 1508 passed (+1 known GDELT false positive, +4 DB tests that pass via the isolated runner); scripts 263; pipeline 31; security 147; training sub-directories all pass individually; isolated-DB subsets 4 + 89 passed; netguard external attempts 0 throughout.

## 15. Evaluation (Phase 10) — NOT AVAILABLE

No accuracy, calibration, fairness or human-agreement metric exists or is claimed. The Stage A eight-sentence smoke comparison is explicitly not evidence. Evidence required before any claim is listed in `SENTIMENT_EVALUATION_REPORT.md` section 4.

## 16. Documentation delivered (Phase 11)

`docs/sentiment/`: `SENTIMENT_ARCHITECTURE`, `SENTIMENT_IMPLEMENTATION_REPORT`, `SENTIMENT_PRIVACY_AND_SECURITY`, `SENTIMENT_MODEL_CARD`, `SENTIMENT_EVALUATION_REPORT`, `SENTIMENT_API_REFERENCE`, `SENTIMENT_GOVERNANCE_STATUS`, `SENTIMENT_TEST_REPORT`, `SENTIMENT_DECISION_LOG`, and this report. Updated: `docs/DECISIONS.md` (ADR-055), `docs/MEMORY.md`, `docs/TEST_PLAN.md` (section 34), `docs/SECURITY.md`, `docs/THREAT_MODEL.md`, and the B2.1 report addendum.

## 17. Files changed

Listed in `SENTIMENT_IMPLEMENTATION_REPORT.md` section 2.

## 18. Git status

Not committed, not pushed, tree not cleaned. 296 entries versus a 294-entry baseline; the difference is new test files only.

## 19. Defects found and fixed during this run

(1) setuptools 84.2.1 removed `pkg_resources` (my B1 miss; fixed by the approved 81.0.0). (2) Demo fixtures embedded a machine-dependent `dependencies_available` (exporter now pins it). (3) A static guard caught `import torch` in the adapter (thread cap moved into the one guarded module). (4) Two stale ADR-053 expectations (fixtures, exact key set). (5) A secret-scan test matched the word "tokenizer" (now token-shaped regex). (6) A stale stand-in test (missing sixth argument). (7) Mutation-harness syntax error from an escape-collapsed `\n`. (8) The setuptools pin in `test_task_cert_1_state.py` (accepts 65.5.0 or the approved 81.0.0). (9) Pydantic protected-namespace warnings on two new response models. (10) Earlier disclosed incident: a plain-pytest run of the `agents` directory had touched the development database read-only by design; not repeated.

## 20. Unresolved issues and risks

1. **Intermittent native access violation in full `tests/training` runs** (TensorFlow/xgboost/joblib; torch not imported in at least one crashing process; sub-directories pass; one clean run before the install). Cause unknown; connection to the B2.1 installation neither shown nor excluded. I cannot claim a clean full-directory `tests/training` run now.
2. The real-weights adapter path is unexercised.
3. Training data of the model are web crawl plus LLM text with LLM labels (accepted for research only).
4. Synchronous first load and 1.3-1.6 GB peak memory when both frameworks are present.
5. GDELT scaffold guard test fails (unrelated, reported separately); original `agents`/dev-DB items unresolved by design.

## 21. Blocked items and precise approval requests (nothing was acted on)

- **R1 — Register Horizon as the `general` research candidate.** Change: `registration = REGISTERED` for `HORIZON` in `core/sentiment/registry.py` (plus the tests that pin the constant). Effect: the general slot becomes runnable in principle when the flag is on and files exist; flag stays off; still display-only. Needs: owner decision.
- **R2 — Authorise Stage B placement and the adapter smoke test.** Copy the 8 verified files from `C:\Users\Administrator\.copilot\wealthpilot-approved-models\horizon-multilingual-sentiment-small` to `models/sentiment_pretrained/horizon/`, run `scripts/write_pretrained_manifest.py --candidate horizon --tokenizer-length <n>` (only possible after R1), and run `WEALTHPILOT_REAL_WEIGHTS_SMOKE=1 pytest tests/backend/core/test_horizon_real_weights_smoke.py`. Needed to claim `INFERENCE_VERIFIED` through the adapter.
- **R3 — Investigate the `tests/training` crash.** Approve re-running the directory several times, and once in a copy of the environment without the Transformer packages, to establish whether it pre-dates the install.
- **R4 — Evaluation evidence.** Requires reversing or scoping D20 and resolving D1, D2, D5, E3, D19; then a labelled, consented, frozen set and independent annotation. Not requested until the owner wants quality claims.
- **R5 — Production activation (F1/R14).** Not to be asked until R4 evidence exists.
- Also unchanged and not requested: A3.3, A3.5, B2.2, multilingual handling, any change to the rollback backup.

## 22. Confirmations and next step

Confirmed: no commit, no push; no access to `neondb`; no plain-pytest run of any DB-backed suite; `agents` not run; no Gemini call; no download; no dataset or label created; no fine-tuning; no model registered, no flag changed, `api/lifespan.py` untouched; no human-validation, accuracy or calibration claim; no browser-based visual test was performed. Recommended next step: decide R1 and R2 together (they unlock the one missing verification), and R3 in parallel.

## 23. Addendum (2026-11-09): owner-approved R1, R2 and R3

Written for: the project owner. Sections 1-22 above describe the state of 2026-11-05; where they say Horizon is unregistered or that the adapter was not run, this section supersedes them. Detail: `R1_HORIZON_RESEARCH_REGISTRATION_REPORT.md`, `R2_APPLICATION_ADAPTER_SMOKE_TEST_REPORT.md`, `R3_TRAINING_NATIVE_CRASH_INVESTIGATION.md`, ADR-056, `SENTIMENT_TEST_REPORT.md` (R-series section). Evidence: `docs/sentiment/r_series/evidence/`.

| Item | Status |
|---|---|
| Horizon general registration | **VERIFIED** (`registration=REGISTERED`, role `general`, ADR-056) |
| Financial slot | **VERIFIED empty** (`no_candidate_approved`) |
| Production flags disabled | **VERIFIED** (`SENTIMENT_TRANSFORMERS_ENABLED=false`, `SENTIMENT_MODEL_ENABLED=false`, `production_activation: not_activated`, method `user_text_rules_v1`) |
| Exact model revision | **VERIFIED** `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` |
| Artifact SHA-256 | **VERIFIED** (model.safetensors `f0d0b6d2…02dd1`; all eight files re-hashed after copying; matches Stage A and the repository `SHA256SUMS`) |
| Application adapter loading | **VERIFIED** (first call including hashing 10.2 s) |
| Real-weight inference | **VERIFIED** (warm median 24.9 ms; adapter logits equal the Stage A logits to rounding) |
| Output normalisation / single softmax | **VERIFIED** |
| Research comparison | **VERIFIED** (general model vs rules; safeguards keep neutral-weak, negation and mixed-vs-rules readings `uncertain`) |
| No raw-text leakage | **VERIFIED** (marker token absent from responses and DEBUG logs; 0 network attempts; no `torch.load`) |
| Financial isolation | **VERIFIED** (structural guards unchanged and passing; research object has `production_effect: none`) |
| Runtime integrity | **VERIFIED** (project `.venv` untouched in R3; no dependency change in R1-R3) |
| Training crash investigation | **RESOLVED (cause established)**: XGBoost's CUDA probe loads then unloads the NVIDIA driver DLL `nvdxgdmal64.dll` 21 ms later; a late driver callback executes the unmapped code (`0xC0000005`). Not caused by the Transformer install (it also crashes in the pre-install reconstruction: 9 of 11). Pinning the DLL removed it (0 of 8 vs 14 of 16). **No mitigation applied; options in the R3 report** |
| Regression tests | exact results in `SENTIMENT_TEST_REPORT.md` (R-series): sentiment 186 passed / 11 skipped, smoke 9 passed, core 1198, data 1508 (+ the known GDELT failure), scripts 263, pipeline 31, security 147, training sub-directories 13 / 10 / 12 / 51 / 13 / 675, frontend 279/279, mutations 200/200; isolated-DB: ingestion 4 passed, API subset 144 passed with 6 network-classified errors in unrelated seed-demo tests (not verified) |
| Documentation | **COMPLETE** |
| Production activation | **BLOCKED** (F1/R14; no validation evidence; D20 rejected) |

Dependency changes in R1-R3: **none** (one temporary download of the recorded `setuptools==65.5.0` wheel into a scratch folder for the comparison environment). The comparison environments (about 3.2 GB each) remain at `C:/Users/Administrator/.copilot/wealthpilot-r3/`. A request to enable Windows Error Reporting dumps (a machine-wide registry change) was refused by the permission layer and was not worked around. Nothing was committed or pushed; the Git status listing is identical before and after (296 entries, `r_series/evidence/git_status_*.txt`).

Remaining blockers: production activation (F1/R14); any quality, accuracy, calibration or human-validation claim (D20 rejected; D1/D2/D5/E3/D19 unresolved); multilingual use; Stage B2.2; a decision on the XGBoost/NVIDIA mitigation; the unverified network-affected seed-demo DB tests.

## 24. Addendum (2026-11-09): R3 mitigation - test-only DLL lifetime guard (owner option 4)

Written for: the project owner. Full detail: `R3_TRAINING_NATIVE_CRASH_INVESTIGATION.md` section 10.

- **Implemented (tests only):** `tests/training/nvidia_dll_guard.py` (holds one reference to the validated driver DLL for the life of the test process), `tests/training/conftest.py` (activates it for the training suite on Windows), `tests/training/test_nvidia_dll_guard.py` (22 passed, 1 skipped for symbolic-link privilege). Switch-off: `WEALTHPILOT_NVIDIA_DLL_GUARD=0`.
- **Result, project `.venv`, whole `tests/training`, sequential:** guard off 4 of 5 runs crashed (`0xC0000005`); guard on **0 of 5** crashed, each 796 passed / 2 skipped, exit code 0. All training sub-directories pass individually (13 / 10 / 12 / 51 / 13 / 675).
- **Isolation:** no dependency change (XGBoost 2.1.2), no change under `backend/`, `scripts/`, `training/`, `config/` or `models/`, no import of the guard outside `tests/training/conftest.py` (enforced by a test), Transformer flags `false`, production sentiment `user_text_rules_v1`, Horizon research-only. Nothing committed or pushed; 3 new untracked files.
- **Limitations:** a workaround for a driver defect, not a fix; protects only pytest runs that collect `tests/training/`; inactive when several NVIDIA driver packages are installed unless the path is named; no in-code signature check; modest sample (5 + 5 runs, in addition to the R3 series).

## 25. Addendum (2026-11-10): R4 baseline verified; backend XGBoost exposure is an unresolved item (U1)

Written for: the project owner. Full detail: `R3_TRAINING_NATIVE_CRASH_INVESTIGATION.md` section 11.

- **R4 baseline re-verified against the repository (read-only):** the three guard files and the R4 evidence exist; `r4_results.jsonl` holds 10 rows (guard off: 4 crashed with `0xC0000005`, 1 passed; guard on: 5 of 5 exit 0, 796 passed / 2 skipped); XGBoost is 2.1.2; the guard is imported only by `tests/training/conftest.py`. Nothing was recreated, redesigned, removed or expanded. It is a machine-specific mitigation, not proof that the driver defect is fixed.
- **Correction:** the R3 note said the application risk model uses XGBoost. The served model is the random forest (`models/metrics.json` `best_model`; `agents/nodes.py` loads `rf_v1.pkl`); no backend module imports `xgboost`.
- **U1 (unresolved):** backend XGBoost exposure is neither shown nor ruled out. Static evidence suggests the serving path does not load XGBoost; dynamic confirmation (`sys.modules` after a served request), transitive imports, and whether `import xgboost` alone triggers the DLL load were not checked. No production change was made.

## 26. Addendum (2026-11-10): U1 backend XGBoost exposure investigation (read-only)

Written for: the project owner. Full detail: `r_series/U1_BACKEND_XGBOOST_RUNTIME_EXPOSURE_REPORT.md`.

- **Result:** 37 fresh-subprocess import runs, all exit 0, no native crash. The backend served import closure does not import `xgboost`; no NVIDIA module was mapped in any run, including nine where `xgboost.dll` was loaded. A poller control (a harmless system DLL mapped for 21 ms and for 5 ms) was seen in 40 of 40 runs.
- **Latent path:** `import autogen` / `import flaml` imports `xgboost` (`autogen/oai/client.py:9` -> `flaml/__init__.py:5`); reachable only via `agents/debate.py::run_strategy_debate`, which nothing in `backend/wealthpilot` calls today.
- **Classification:** no exposure observed in tested imports. Not a safety claim: XGBoost use, `warm_model_caches`, served requests, the debate execution path and `api.main` were NOT RUN. The driver defect is not fixed; R4 was not touched.
- **Safety:** no database or `.env` access, no sockets (blocked at the Python level; only a local IPv6 bind probe and a Windows-version subprocess probe were seen), no server, no repository or dependency change (`git status` outside the evidence folder identical; `pip freeze` identical).
