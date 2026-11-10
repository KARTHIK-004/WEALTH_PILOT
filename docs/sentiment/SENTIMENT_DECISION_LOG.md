# Sentiment Decision Log — autonomous completion run (2026-11-05)

Written for: the project owner. Each entry is an engineering decision I made without asking, with the evidence that allowed it and the boundary it stayed inside. Anything that needed an approval is under "Deferred to the owner", not decided here. Architecture-level records are in ADR-053/054/055.

## Decisions taken

| # | Decision | Reason / evidence | Boundary respected |
|---|---|---|---|
| 1 | Treated the B2.1 authorisation as covering the TensorFlow/PyTorch coexistence tests once `setuptools==81.0.0` was restored | The B2.1 brief authorised modifying the project `.venv` and running the coexistence tests; the stop was caused by the setuptools defect, which the owner then approved fixing. The coexistence tests need no new package, model placement, registry change or inference through the application. | Recovery limited to setuptools, integrity checks and the TensorBoard regression check; tests loaded the model only from the Stage A directory outside the repository, in throwaway processes |
| 2 | Restored `setuptools==81.0.0` exactly (hash `fdd925d5…10d6`) and changed nothing else | Recorded constraint "setuptools < 82" (tensorboard needs `pkg_resources`); `RECOVERY_RECORD.md` | No unrelated package upgraded; TF 2.17.0, Keras 3.15.1, numpy 1.26.4, protobuf 4.25.9 unchanged |
| 3 | Replaced the rigid FinBERT/RoBERTa slots with role slots `financial` / `general` | ADR-054 already named the generalisation as the bounded change set | Active production method untouched |
| 4 | **Left Horizon `pending_owner_approval`** (not registered) | Registration makes it "runnable in principle"; the owner approved research *consideration*, not registration; the brief forbids registering it as production-runnable | One-line owner decision recorded as the first unblocker |
| 5 | Kept the English-only eligibility gate; Tamil and code-mixed text abstain | No multilingual approval or evidence; Part 5 says "safe abstention otherwise" | The model never sees non-English text |
| 6 | Synchronous first load, guarded by a per-candidate **non-blocking** lock; concurrent callers get `loading` | Avoids a thundering herd without a background thread; warming/lifespan changes were outside B2.1 boundaries | No `api/lifespan.py` change, no startup warming, no thread pool |
| 7 | Status endpoint reads code constants and file existence only | Brief: a status check must not load weights | `candidate_status` never loads, hashes or verifies; tested |
| 8 | Circuit breaker (30 s) after a timeout | A hung model would otherwise stall every request for the full timeout | Fixed reason codes only |
| 9 | Catch-all at the service boundary (`build_transformer_research` never raises) | Research must never turn a valid insight request into a 500 | Falls back to the rules reading; error reason is a fixed code |
| 10 | Optional `SENTIMENT_TRANSFORMERS_THREADS`, applied inside `TransformersBackend` | B2.1 found two OpenMP runtimes; a cap is the cheap mitigation | `import torch` stays in the one guarded module (a static test enforces this); default untouched |
| 11 | Breaking change to the never-enabled `transformer_research` JSON shape | No consumer existed; types and fixtures regenerated | RFC 7807, `model_version` and `data_source` unchanged |
| 12 | The exporter for demo fixtures pins `dependencies_available=False` | The fixture had embedded a machine-dependent value after the install | Fixtures deterministic; production code unchanged |
| 13 | The rules baseline got a regression suite (42 tests, 30 fictional sentences) that **characterises** current behaviour and fixes nothing | "Hardening" without ground truth would mean inventing rules; D20 rejects creating labels | No rule edited; no accuracy claim |
| 14 | No real-weights adapter run; an opt-in smoke test was written and left skipped | It needs the verified files placed under `models/` with a manifest (Stage B) — not authorised | `INFERENCE_VERIFIED` through the adapter is explicitly **not** claimed |
| 15 | DB-backed suites only via `scripts/run_isolated_db_tests.py` | Standing boundary after the dev-DB incident | `neondb` never touched; `agents` directory not run |

## Deferred to the owner (not decided)

Register Horizon; authorise Stage B (file placement, manifest, adapter smoke); production activation (F1/R14); reversing/scoping D20 or resolving D1/D2/D5/E3/D19 for any evaluation; multilingual handling; Stage B2.2.

## Reported separately, not modified

The GDELT scaffold failure in the repo-wide run (a false positive for this work); original DB-error tests in the `agents` directory (not re-run).

---

## R-series decisions (R1, R2, R3 - owner authorisation of 2026-11-07)

| # | Decision | Reason / evidence | Boundary respected |
|---|---|---|---|
| R-1 | Registered Horizon by changing exactly one constant (`registration=REGISTERED`) and wrote ADR-056 | The owner's R1 instruction; ADR-055 had left it as "one constant plus an ADR" | `financial` slot untouched; no flag changed; `user_text_rules_v1` still production |
| R-2 | Updated 14 tests that pinned the "pending" state instead of loosening them; they now assert the registered state, the empty financial slot and "nothing is production" | A pinning test that no longer matches reality must say what is now true | No test was deleted or skipped |
| R-3 | Added an autouse hermetic fixture so unit tests read an EMPTY directory whenever the default (real) model directory would be used | Once the real weights exist locally, a flag-on unit test would otherwise load 560 MB by accident | The real directory is read only by the opt-in smoke file |
| R-4 | Added `models/sentiment_pretrained/` to `.gitignore` | The existing rules covered only `models/sentiment/**`; the new directory was not ignored | Nothing was committed or pushed |
| R-5 | Copied the eight approved files from the Stage A directory instead of downloading again | The files were already hash-verified; a second download adds network use and no information | Exact revision only; hashes re-checked after copying |
| R-6 | Replaced the review `blockers` and appended a dated update to the owner-decision text (the 2026-11-04 text is untouched) | The old blockers ("packages not installed", "not in the registry") had become false and are public via the status endpoint | The public text avoids the local directory name (a test caught the first draft) |
| R-7 | The smoke test uses the Stage A texts and compares the adapter's logits with the Stage A logits | A stronger check than "it returns three numbers": same revision, same tokenizer, same arithmetic | Fictional sentences only; labelled a smoke observation, never accuracy |
| R-8 | R3 comparison environments were built by COPYING the project `.venv` (envA = exact copy; envB = same copy minus the 15 Transformer packages plus `setuptools` 65.5.0) | A byte-level copy reproduces every other native library exactly; envB's `pip freeze` equals the recorded pre-install freeze line for line | The project `.venv` was never modified; both copies live outside the repository |
| R-9 | Refused-by-policy action: enabling Windows Error Reporting local dumps (a registry change under HKLM) was attempted and denied by the permission layer; I did not work around it and used an in-process locator plugin instead | A system-wide setting is not needed for a diagnosis | No registry change was made |
| R-10 | Two overlapping series were discovered and their runs are marked CONTAMINATED rather than silently used | Stopping a task killed the shell but not the loop it had started, so later runs overlapped | Only strictly sequential runs are used as evidence |
