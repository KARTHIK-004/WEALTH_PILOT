# Stage A Completion Report — Horizon multilingual sentiment, isolated real CPU inference

Written for: the project owner. Date: 2026-11-04. Model: `Horizon-Labs/multilingual-sentiment-small` @ `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac`. Scope: **research inference only, isolated environment only.**
Evidence labels: **VERIFIED** (recorded command output or reproducible check), **OBSERVED** (seen, not established as a general property), **UNRESOLVED** (insufficient evidence), **NOT AUTHORIZED** (outside the approved scope).
This report supersedes nothing in `reports/sentiment_transformer_stage_a_report.md` (the working report); where they differ, this one is the final record.


## 1. Executive Summary

**Verdict in one line:** Stage A achieved its technical goal (real, checksum-verified, isolated CPU inference), but the test evidence is not fully green and two isolation boundaries were crossed by how I ran the test suites. Both are disclosed below and neither is hidden by the numbers.

- **VERIFIED:** the approved model loaded from its checksum-verified safetensors file and ran real CPU inference in the isolated environment: `INFERENCE_VERIFIED`, reference stack only (transformers 5.17.0 + torch 2.15.0+cpu), isolated environment only.
- **VERIFIED:** nine directory runs finished: **4,294 passed, 1 failed, 9 skipped, 0 errors** (4,304 tests executed). The one failure is the unrelated GDELT scaffold test, a substring-heuristic false positive, left unmodified and visible (section 9).
- **VERIFIED:** about 546 API tests (the API files before `test_profiles.py`) were **not** re-run in the final nine runs; their evidence is the earlier stopped run plus targeted reruns (section 8). This is a coverage gap, stated openly.
- **DATABASE-BOUNDARY INCIDENT (section 10.3):** development database access: **CONFIRMED**; intended mode: **READ-ONLY BY TEST DESIGN**; direct test-level writes in the inspected files: **NONE IDENTIFIED**; application-level writes through supplied sessions: **NOT FULLY VERIFIED**; actual database state: **NOT VERIFIED**; database modification: **UNKNOWN**. It happened because I ran `tests/backend/agents` with plain `pytest` instead of the project's isolated runner (a **test-execution process failure**). The same run also made three rate-limited live Gemini calls.
- **UNRESOLVED:** the causes of the two original database errors (their tracebacks were lost with the stopped run).
- **VERIFIED:** the application is unchanged: the project `.venv`, TensorFlow, the model registry, the settings and production (`user_text_rules_v1`) were not touched.
- **NOT AUTHORIZED / NOT STARTED:** Stage B.
- The eight fictional sentences are smoke-test observations. They are not a dataset, benchmark, evaluation, human validation or accuracy claim.

## 2. Scope and Explicit Non-Goals

**Approved scope (owner, 2026-11-04): Stage A only**, research inference only: an isolated environment outside the repository, a hash-pinned dependency stack, a checksum-verified download of one model at one revision, compatibility verification, and a real CPU inference smoke test on fictional sentences; plus running the backend suites and fixing test failures caused by the earlier ADR-053 change.

**Not done, not authorized:** Stage B; integrating Horizon into the application; runtime selection; any registry change; production activation or any feature-flag change; automatic downloads from application code; fine-tuning or training; dataset collection or creation; human annotation or validation; accuracy, calibration or performance claims beyond the smoke-test measurements; any use of sentiment in risk, portfolio, goals, recommendations, compliance or financial decisions; installing anything into the project `.venv`; modifying `neondb`; changing unresolved licensing or dataset governance decisions (A3.3, A3.5, D20, F1); commercial use or redistribution; commits or pushes. None of these was done.

## 3. Environment and Dependency Verification

- **VERIFIED** Isolated virtual environment `C:\Users\Administrator\.copilot\wealthpilot-stageA\venv` (outside the repository), base interpreter Python 3.11.9 (64-bit, Windows 11), pip 24.0.
- **VERIFIED** Resolver dry-run before installing (`pip install --dry-run --report`): exit 0; 35 packages; no source distributions; `torch 2.15.0+cpu` only from the PyTorch CPU index, every other package from `files.pythonhosted.org`.
- **VERIFIED** `numpy` held at 1.26.4 (the application's version).
- **VERIFIED** Installed with `pip install --require-hashes --no-deps --only-binary=:all:` from `docs/sentiment/stage_a/requirements-stage-a.lock.txt` (35 hash-pinned entries); installed set equals the lock (`setuptools` is hidden by `pip freeze` and was confirmed with `pip list`); `pip check`: no broken requirements.
- **VERIFIED** Versions: transformers 5.17.0, tokenizers 0.23.3, safetensors 0.8.0, huggingface-hub 1.33.0, torch 2.15.0+cpu (CUDA available: no), numpy 1.26.4, plus the packages in the lock. Disk: 937 MB.
- **VERIFIED** The application `.venv` is untouched: its `site-packages` timestamp is unchanged (2026-10-29 21:31:18) and it still has TensorFlow 2.17.0, Keras 3.15.1, numpy 1.26.4, protobuf 4.25.9 and none of the new packages.


## 4. Model Provenance, Revision, and Checksum Verification

- **VERIFIED** Only the eight approved files were downloaded (`hf download`, telemetry off) at the exact revision: `model.safetensors` (562,584,932 bytes), `config.json`, `tokenizer.json` (34,363,286), `tokenizer_config.json`, `special_tokens_map.json`, `SHA256SUMS`, `LICENSE`, `NOTICE`; none of `onnx/`, `code/`, `eval/`, `training/`. Directory: `C:\Users\Administrator\.copilot\wealthpilot-approved-models\horizon-multilingual-sentiment-small` (outside the repository).
- **VERIFIED** The downloader's own metadata records commit `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac`.
- **VERIFIED** Every file matches the repository's `SHA256SUMS` and the values recorded earlier from a summarising fetch (so those recordings are confirmed first-hand): `model.safetensors` `f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1`; `tokenizer.json` `f34b44a6dc8a0eef651bfa10e8325057530152606a69d9c3b6ae02efb1558f0a`; `config.json` `516d8046cca3238145113bbe8b5e2b5b34b2f0c04b0ca093d7761c5f0a504eb9`; `tokenizer_config.json` `ea349495764b24570b4560fe2e4a557e5c0a47e6bce782c2409b1d6445cf8633`; `special_tokens_map.json` `baec30ea10906f16adb8c18af7a34023002c1746542612b8b41c9f09e1351351`.
- **VERIFIED** `model.safetensors` was also recomputed independently (`Get-FileHash`) and re-hashed by the smoke script before loading. No pickle-capable file is present.
- **OBSERVED** Training data and labelling as stated by the repository (not independently verified): FineWeb / FineWeb-2 web-crawl snippets, LLM-written synthetic text, soft labels from an LLM teacher, no human annotation. Accepted by the owner for research inference only (ADR-054 addendum, 2026-11-04).


## 5. Architecture Compatibility Findings

- **VERIFIED (executed)** transformers 5.17.0 reads the model's configuration correctly: `ModernBertForSequenceClassification`, `rope_parameters` for both layer types at `rope_theta` 160000, 22 `layer_types`, `classifier_pooling: mean`, vocabulary 256,000, 8,192 positions, no `auto_map`.
- **OBSERVED (source reading, not executed)** transformers 4.57.1 has no `rope_parameters` and defaults `local_rope_theta` to 10000; this model needs 160000 for its sliding-attention layers, so 4.57.1 would likely load it and silently give wrong numbers. That version was **not run**; the conclusion rests on reading its source.
- **VERIFIED (executed)** The ADR-052 pins (`tokenizers 0.22.1`, `safetensors 0.6.2`) were not used; transformers 5.17.0 requires `tokenizers>=0.23.1` and `safetensors>=0.8.0`, and the resolver accepted the pins in the lock.
- **VERIFIED** The earlier note that transformers 5 "reportedly drops TensorFlow" was withdrawn: 5.17.0 declares no TensorFlow dependency, and it ran alongside numpy 1.26.4. **UNRESOLVED:** coexistence with TensorFlow 2.17 inside one environment was not tested (TensorFlow was deliberately kept out of the isolated environment); that is a Stage B question.
- **UNRESOLVED** ONNX Runtime was not evaluated in Stage A; it needs an artifact-policy extension and a parity check (NOT AUTHORIZED here).


## 6. Real Inference Smoke-Test Results

Script `...\wealthpilot-stageA\scripts\stage_a_smoke.py`; raw results `...\results\stage_a_inference_results.json` (outside the repository). Status `COMPLETED`, no errors. All inputs fictional; the "intent" column is only what each sentence was written to express and is **not ground truth**.

| Input (fictional) | Intent | Native label | Softmax neg / neu / pos | Logits | Tokens | ms |
| --- | --- | --- | --- | --- | --- | --- |
| I feel happy because my savings have increased this month. | positive | positive | 0.0002 / 0.0002 / 0.9996 | -2.03, -1.75, 6.60 | 13 | 22.5 |
| I am worried because my monthly loan payments are becoming difficult to manage. | negative | negative | 0.9829 / 0.0166 / 0.0005 | 4.70, 0.62, -2.90 | 16 | 18.3 |
| I deposited five thousand rupees into my savings account this month. | neutral | neutral | 0.0030 / 0.9591 / 0.0379 | -2.37, 3.41, 0.18 | 14 | 22.9 |
| My investments are growing, but I am worried about future expenses. | mixed | neutral | 0.0857 / 0.8839 / 0.0303 | 0.21, 2.54, -0.83 | 15 | 18.8 |
| I reviewed my account statement yesterday. | ambiguous | neutral | 0.0020 / 0.9927 / 0.0053 | -1.79, 4.42, -0.81 | 9 | 18.6 |
| I am not worried about my savings at all. | negation | positive | 0.0323 / 0.2371 / 0.7306 | -1.14, 0.85, 1.98 | 12 | 21.0 |
| If I lost my job I would panic about my savings. | hypothetical | negative | 0.8254 / 0.1338 / 0.0408 | 2.49, 0.67, -0.51 | 14 | 20.4 |
| Estoy muy contento porque por fin pude ahorrar para mis vacaciones. | other language | positive | 0.0004 / 0.0004 / 0.9991 | -1.98, -1.96, 5.77 | 14 | 16.4 |

- **VERIFIED** native labels `0 negative, 1 neutral, 2 positive`; input ids and attention masks `int64` of shape `[1, n]`, ids within the vocabulary, attention mask all ones; sequences are wrapped `<bos> ... <eos>`; output logits shape `[1, 3]`; no NaN or infinity; maximum length 512 (an 8,039-character, 1,682-token input truncated to exactly 512 and ran in 321.9 ms).
- **VERIFIED** CPU only; model load 0.82 s (warm file cache); 16.4 to 22.9 ms per sentence (median 20.4 ms); whole script 4.05 s.
- **VERIFIED** memory (separate run, correctly typed Windows API calls; an earlier helper returned a bogus 0.0 and was discarded): peak working set 305 MB after imports, 1,139.7 MB after loading the model, unchanged after one inference.
- **OBSERVED** (eight inputs; not a general property): the "mixed" sentence came back neutral, the hypothetical job-loss sentence read as negative, and the negated "not worried" sentence read as positive. These are the cases the existing rules safeguards and the comparison layer exist for. They are **not** accuracy measurements.


## 7. Probability and Numerical Verification

- **VERIFIED** The raw model output is logits, not probabilities (for the negative-intent sentence `[4.7016, 0.6210, -2.8954]`, sum 2.43).
- **VERIFIED** Exactly one softmax gives `[0.9829, 0.0166, 0.0005]` and equals the library's own `text-classification` pipeline scores to 1.9e-9.
- **VERIFIED** A second softmax would have flattened this to `[0.570, 0.217, 0.213]`; it was not applied.
- **VERIFIED** Five repeats of an identical input at the default thread count and at one thread: maximum difference 0.0 (bitwise identical); the label is the same at both thread settings; batch versus single-sentence inference differ by at most 2.4e-6.
- **OBSERVED** The softmax values are uncalibrated and valid within this one model only; no confidence is claimed.


## 8. Test Execution Results

Every directory ran with its own command, sequentially (one process at a time, never in parallel), with `-p no:cacheprovider --tb=long -q -rfEs`, **no deselection, no retries**, from the repository root with `PYTHONPATH=.` and the project `.venv` interpreter. Logs and exit codes: `...\scratchpad\remaining_suites\*.txt` and `status.txt` (outside the repository). Command shape: `python -u -m pytest <target> -p no:cacheprovider --tb=long -q -rfEs`.

### 8.1 The nine final directory runs (VERIFIED from the recorded output)

| # | Target | Passed | Failed | Skipped | Errors | Exit | Time | Notes |
| --- | --- | ---: | ---: | ---: | ---: | :---: | --- | --- |
| 1 | `tests/backend/core` | 1,138 | 0 | 2 | 0 | 0 | 17 s | 2 skips: symbolic links need a privilege this account lacks |
| 2 | `tests/backend/data` | 1,512 | **1** | 0 | 0 | **1** | 2 m 01 s | the GDELT scaffold heuristic (section 9) |
| 3 | `tests/backend/scripts` | 263 | 0 | 1 | 0 | 0 | 1 m 02 s | 1 skip: symbolic links |
| 4 | `tests/training` | 735 | 0 | 3 | 0 | 0 | 2 m 40 s | 2 skips: `torch` is not installed in the project `.venv` (by design); 1 skip: symbolic links |
| 5 | `tests/backend/api` **from `test_profiles.py` onward only** (8 files) | 107 | 0 | 0 | 0 | 0 | 21 m 24 s | partial directory, see 8.3 |
| 6 | `tests/backend/agents` | 229 | 0 | 3 | 0 | 0 | 2 m 48 s | 3 skips: live Gemini calls rate-limited (HTTP 429); **crossed the development-database boundary: six of its files opened `neondb` sessions (access CONFIRMED, modification UNKNOWN), see section 10.3** |
| 7 | `tests/backend/pipeline` | 31 | 0 | 0 | 0 | 0 | 10 s | |
| 8 | `tests/backend/security` | 147 | 0 | 0 | 0 | 0 | 4 s | |
| 9 | `tests/backend/db` | 132 | 0 | 0 | 0 | 0 | 13 m 19 s | |
| | **Aggregate of the nine runs** | **4,294** | **1** | **9** | **0** | | | **4,304 tests executed** |

Aggregates are summed from these nine final runs only. The earlier 1,529-pass gate and the stopped run's counts are **not** added in. No test was deselected; the only exclusion is the file selection in row 5.

All 9 skips are documented environment skips: 4 symbolic-link privilege (core 2, scripts 1, training 1), 2 `torch` absent from the project environment, 3 Gemini quota (HTTP 429). None was added to hide a failure.

### 8.2 Earlier runs, kept separate (they are NOT part of the table above)

| Run | Result | Status |
| --- | --- | --- |
| Stopped full run (sequential from the top, plain `pytest tests/`) | 796 completed: 792 passed, 2 errors, 2 failures, 0 skipped (an earlier snapshot of the same run read 681 completed, 2 errors) | stopped by agreement; no tracebacks survive, because pytest prints them only at the end |
| Re-run of `test_household_goals.py` (whole file) | 83 passed, **1 error** (a different test, a database connection drop at fixture setup) | the errored test then passed alone |
| Re-run of `test_monthly_records.py` (whole file) | 53 passed | |
| After the two ADR-053 fixes: `..._hardening.py` / `..._interpretation.py` | 33 passed / 24 passed | superseded the two failures of the stopped run |
| Relevant sentiment gate under a socket guard (before inference) | **1,529 passed, 6 skipped, 0 failed, 0 network attempts**; frontend 276 of 276 | a separate, offline, database-free subset: not a full-suite figure |

### 8.3 Coverage gap (stated, not hidden)

`tests/backend/api` has 653 tests; the final chain ran 107 of them (from `test_profiles.py`). **About 546 API tests in the 17 files before `test_profiles.py` were not re-run in the final nine runs.** Their evidence: the stopped run passed them except the 2 errors and 2 failures above (all four since classified or fixed), plus the targeted file-level reruns in 8.2 and the sentiment-related API files inside the 1,529-pass gate. That is real evidence, but it is **pre-fix, partly partial, and not one clean run**; I did not re-run them because it takes hours and the owner asked not to repeat the long suite. **UNRESOLVED** whether any unrelated regression exists there. A tally difference of 2 tests (738 executed in `training` against 736 counted at an earlier collection) is a bookkeeping discrepancy in my own count, not in the results.

## 9. Failure Classification and Fixes

### 9.1 The GDELT failure (data directory) — VERIFIED evidence, no change made

`tests/backend/data/gdelt/test_sentiment_scaffold.py::test_no_production_entry_point_or_helper_imports_the_sentiment_scaffold` fails on the assertion `'import sentiment' not in <source of personalized_insight_service.py>` (the first offender found).
- **Cause (VERIFIED):** the test scans the code base for four forbidden substrings. `import sentiment` also occurs inside the legitimate ADR-052 line `from wealthpilot.core import sentiment_model`, so every importer of that module trips it.
- **No genuine scaffold import (VERIFIED):** the other three needles (`gdelt.sentiment`, `sentiment.fake_scorer`, `FakeScorerTestOnly`) appear nowhere. One flagged file (`tests/training/sentiment/test_sentiment_training_pipeline.py`) matched only because it contains the string `"from training import sentiment"` inside an assertion that bans that import.
- **Scope (VERIFIED):** 14 files are flagged. Eight carry modification times between 2026-10-27 and 2026-10-30; four were written by the ADR-053/054 work (`core/sentiment/adapter.py`, `scripts/write_pretrained_manifest.py`, `test_sentiment_candidate_reviews.py`, `test_sentiment_research_pair.py`; they import the ADR-052 module, not the scaffold) and add to the same false positive; two (`personalized_insight_service.py`, `test_personalized_insights_model.py`) were edited by me but already contained the ADR-052 import.
- **Timeline (OBSERVED, not provable from Git):** the test was last written 2026-10-20; the earliest flagged file is dated 2026-10-27 (ADR-052). The claim that it predates ADR-053 rests on those file timestamps and the test's own logic. **There is no Git history** (a single "Initial project upload" commit), so it cannot be independently proven.
- **Classification: test-heuristic defect / false positive.** It stays visible as a failure. **I did not modify the test.**
- **Proposed future correction (NOT applied):** replace the substring scan with an AST-based inspection of real `import` and `from ... import` statements. A plain word-boundary regex would not reliably fix it: `\bimport sentiment\b(?!_)` still matches the text `"from training import sentiment"` inside a string literal, and it would be fooled by comments and docstrings; only parsing the syntax tree separates real imports from text.

### 9.2 The two original errors — UNRESOLVED

`test_household_goals.py::test_a_required_field_cannot_be_cleared_with_null[goal_type]` and `test_monthly_records.py::test_malformed_values_are_rejected_with_422_and_nothing_is_stored[payload8]`: **their original tracebacks were lost when the long-running suite was stopped, so their causes remain unproven.** Both passed alone and inside a full run of their files, so the errors did not reproduce.

### 9.3 A different error seen on re-run — classified as infrastructure, diagnosis not overstated

`ERROR at setup of test_invalid_input_is_422[overrides22]`: `psycopg.OperationalError: consuming input failed: server closed the connection unexpectedly` at an `INSERT INTO customers` in `tests/backend/api/conftest.py:138`; the test body never ran; it passed when re-run alone. **VERIFIED** as a connection drop during fixture setup against the hosted test database; whether it is Neon, the network or the client is **UNRESOLVED**. The best-supported (not proven) explanation for the two original errors is the same class of fault.

### 9.4 The two ADR-053 failures — genuine defects, fixed (VERIFIED)

Both came from the additive `transformer_research` field, in files I had not run when I made that change. (1) 22 insight fixtures were regenerated from the real backend; a programmatic comparison confirmed the only difference in each is the added `transformer_research` object. (2) The exact key-set assertion now requires every previous field, allows exactly the one documented addition and rejects any other. Both files pass (33 and 24 tests).

### 9.5 Two tests updated because the approved Stage A changed their state (VERIFIED)

The preflight gate-5 assertion now mirrors the file system (gate 5 only reports that a `model.safetensors` exists; **the preflight still exits 1, BLOCKED**), and one frontend case now builds its "older response" explicitly. Nothing else was altered to improve a count.

## 10. Security and Network Isolation

### 10.1 During inference (VERIFIED from the run's own record)

Offline variables set; every socket entry point wrapped to refuse and count: **0 attempts**. `torch.load` replaced by a function that raises: **0 calls**. `use_safetensors=True`, `trust_remote_code=False`, no `auto_map`, no module imported from the model directory, no external inference API, no database used. The relevant offline test gate ran under a socket guard with **0 external connection or lookup attempts**.

### 10.2 Network use that did occur (VERIFIED or OBSERVED)

- Approved: package installation (PyPI, the PyTorch CPU index) and the model download (Hugging Face). The `hf` tool also printed "a new version of huggingface_hub is available", which shows its built-in update check contacted a package index (metadata only; no user text; OBSERVED). `~/.cache/huggingface` was created by it (an index file and update markers; no token, no other model).
- The database-backed suites used the hosted test database (`TEST_DATABASE_URL`, `neondb_test`).

### 10.3 DATABASE-BOUNDARY INCIDENT: the development database `neondb` was accessed

| Question | Status |
| --- | --- |
| Development database access | **CONFIRMED** |
| Intended access mode | **READ-ONLY BY TEST DESIGN** (the tests' own docstrings: "READ-ONLY … never writing"; the `real_client` fixture wraps the development database in a transaction that is rolled back) |
| Direct test-level writes in the inspected files | **NONE IDENTIFIED** |
| Application-level writes through the supplied sessions | **NOT FULLY VERIFIED** |
| Actual state of the development database | **NOT VERIFIED** |
| Database modification | **UNKNOWN. This report does not claim that no modification occurred, and the access is not described as harmless or proven read-only.** |

**What happened.** I ran the remaining suites with plain `pytest`. The project already provides `scripts/run_isolated_db_tests.py`, which sets **both** `TEST_DATABASE_URL` and `DATABASE_URL` to `neondb_test` for the child process and **deselects every test that uses the development database (`real_*` fixtures)**. I did not use it for the affected execution. I had confirmed that the shared `tests/backend/conftest.py` uses the test database, but I did not check every test module. **This is recorded as a test-execution process failure.**

**What opened development-database sessions.** Six files in `tests/backend/agents/` (`test_compliance_gate_safety.py`, `test_financial_inputs_integration.py`, `test_graph_execution.py`, `test_graph_safety_contracts.py`, `test_nodes.py`, `test_recommendation_node.py`) call `get_engine(settings.database_url)`. The `agents` directory completed twice: inside the stopped full run, and in the final chain (229 passed, 3 skipped). Separately, `tests/backend/api/test_analysis.py` used the rollback-wrapped `real_client` fixture in the stopped run (that file is among the API files that were not re-run in the final chain).

**What the inspection covered, and its limits.** I read the six agents files and `test_analysis.py` and searched them for INSERT, UPDATE, DELETE, `add`, `add_all`, `flush`, `commit` and similar. None was found against a development session; the single `db_session.add` (in `test_recommendation_node.py`) uses the test-database fixture. **The inspection did not cover** the application code those tests call with the supplied sessions (`run_analysis_graph`, the graph nodes and any services they reach), which was not fully audited for writes; it did not cover other test files outside this list; and it could not establish the database's real state, because that would require accessing `neondb` again, which I did not and will not do. No query, cleanup, rollback or corrective operation was attempted.

**Decision on `agents`: it is not re-run.** The existing result is a valid execution record but is **labelled as having crossed the development-database boundary**. The isolated runner would deselect the real-data tests, and the remaining agents tests depend on FAR-Trans data held only in the development database, so a re-run would not reproduce equivalent coverage.

**Therefore the test suite as run is not fully isolated**, and the `db`, `pipeline` and `security` results do not need this caveat only because their files do not use the development URL (the migration-history test reads Alembic script files and opens no connection). The Stage A scripts contain no database code.

**Future requirement.** Database-backed suites must be run through `python scripts/run_isolated_db_tests.py` (for example `--suite api --suite db`). `tests/backend/agents` and any `real_*` test must be treated as an explicit, owner-approved development-database read and not run by default; `docs/TEST_PLAN.md` section 33 records this.

### 10.4 DISCLOSURE: live Gemini API calls

Three `agents` tests (`test_debate_gemini_client.py`, `test_explanation_gemini_client.py`) call the Gemini API with the project's key; all received `429 RESOURCE_EXHAUSTED` and were skipped. They are documented project behaviour (live-Gemini tests skip when unavailable) and send fixed test prompts, not user text, but they are outbound calls to an external service that I did not flag beforehand.


## 11. Production Isolation Verification (final checks run 2026-11-04)

| Check | Evidence | Result |
| --- | --- | --- |
| Production sentiment method | `METHOD_VERSION` read from the code: `user_text_rules_v1` | VERIFIED |
| Transformer flags | defaults in code and the ACTIVE settings with `.env` applied: `sentiment_model_enabled=False`, `sentiment_transformers_enabled=False`; `.env.example`: both `=false`; `.env` has no `SENTIMENT_*` keys (its only related key is the earlier, unrelated development flag `DEMO_MODE_ENABLED=true`, fictional data, no model) | VERIFIED |
| Registry | active registry: FinBERT and Twitter-RoBERTa, `any runnable: False`; Horizon not in the registry (`active_in_registry False`, review verdict `approved_for_research_inference`); `registry.py` last written 2026-11-03 02:05, before Stage A | VERIFIED |
| No application integration or production inference | the research panel and API object are display-only and disabled; the Stage A inference ran only from standalone scripts in the isolated environment | VERIFIED |
| No migration | no migration file written since 2026-11-03; no Alembic command was run | VERIFIED |
| Project `.venv` | `site-packages` last written 2026-10-29 21:31:18; TensorFlow 2.17.0, Keras 3.15.1, numpy 1.26.4, protobuf 4.25.9; none of torch, transformers, tokenizers, safetensors, huggingface-hub, onnxruntime; `pip check` clean | VERIFIED |
| Isolated environment vs lock | 35 of 35 pinned packages installed at the locked versions, nothing extra; `pip check` clean; no TensorFlow in it (by design) | VERIFIED |
| Model files | all eight files re-verified against `SHA256SUMS` and the recorded hashes on 2026-11-04 (final check); `model.safetensors` `f0d0b6d2...2dd1`; no pickle-capable file; only that folder under `wealthpilot-approved-models` | VERIFIED |
| Weights in the repository | none added: the 29 weight-like files in the repository are the project's existing trained models dated 2026-09-14; none is a sentiment model or newer than 2026-11-03; `models/sentiment_pretrained` does not exist | VERIFIED |
| `neondb` | access **CONFIRMED** (read-only by test design); direct test-level writes in the inspected files: none identified; application-level writes: not fully verified; actual state: not verified; **modification: UNKNOWN** (section 10.3) | **NOT claimed untouched** |
| Network / model downloads / `torch.load` / remote code | inference: 0, 0, none (section 10.1); the only downloads were the approved ones (10.2) | VERIFIED |
| Preflight | `scripts/sentiment_preflight.py` exits 1 (BLOCKED: A3.3, A3.5, D20, E3, F1 open; gate 5 passes only because the approved weights now exist) | VERIFIED |

## 12. Limitations and Observations

- Eight fictional sentences cannot support any accuracy, calibration, generalisation, human-agreement or superiority claim, and none is made.
- The model's labels were produced by an LLM, and its training data is web-crawl plus LLM-written text (owner-accepted for research inference only). It has three classes and cannot express mixed or uncertain.
- Multilingual ability is not used by WealthPilot (only English text would reach a model).
- Stage A ran the reference stack in an isolated environment without TensorFlow; coexistence in the application environment, the first-load time inside a request path (about 1.1 GB resident), and in-application behaviour are untested (Stage B questions).
- The unrelated GDELT scaffold test (section 9.1) is a false positive of an over-broad substring heuristic that I believe predates ADR-053 on the evidence of file timestamps (no Git history exists); it was left unmodified and remains a visible failure.
- The test evidence is not one clean run: about 546 API tests were not re-run in the final chain (section 8.3), the original two database errors are unresolved (9.2), and the `agents` directory ran across the `neondb` and live-Gemini boundaries (10.3).


## 13. Changed Files and Git Status

**Git state (VERIFIED):** the repository has a single commit (`71b363f` "Initial project upload"); `git status` shows **294 entries (78 modified, 216 untracked)** because most of the project's work since that commit is uncommitted. Git therefore cannot separate this work from earlier uncommitted user and phase work; the lists below are from my session records (cross-checked against files written since 2026-11-03). Nothing was reverted, cleaned, overwritten, committed or pushed.

**Created for Stage A (2026-11-04):** `docs/sentiment/stage_a/requirements-stage-a.lock.txt`; `docs/sentiment/stage_a/STAGE_A_COMPLETION_REPORT.md`; `reports/sentiment_transformer_stage_a_report.md`.

**Modified for Stage A (tests and fixtures):** `tests/backend/api/test_personalized_insights_interpretation.py` (additive key-set assertion); `tests/backend/scripts/test_sentiment_preflight.py` (gate 5 mirrors the file system); `frontend/tests/transformer-research.cases.tsx` (explicit older-response shape); `frontend/tests/fixtures/*.json` (22 insight fixtures regenerated; only the added `transformer_research` object differs).

**Modified for Stage A (documentation):** `docs/DECISIONS.md` (ADR-054 Stage A addendum), `docs/MEMORY.md`, `docs/TEST_PLAN.md` (section 33).

**From the preceding ADR-053 / ADR-054 work (same uncommitted tree):** `backend/wealthpilot/core/sentiment/` (`__init__`, `registry`, `normalization`, `adapter`, `comparison`, `inference_service`, `reviews`); additive edits to `backend/wealthpilot/api/schemas.py`, `api/services/personalized_insight_service.py`, `config/settings.py`, `.env.example`; `scripts/write_pretrained_manifest.py`; `frontend/src/lib/transformer-research.ts`, `frontend/src/components/financial-health/transformer-research-panel.tsx`, `behaviour-sentiment-view.tsx`, `frontend/src/types/api.ts` (regenerated, additive only), `frontend/tests/component.test.mjs`, `mutation-check.mjs`; `tests/backend/core/test_sentiment_research_pair.py`, `test_sentiment_candidate_reviews.py`, `tests/backend/api/test_sentiment_research_api.py`, `tests/backend/scripts/test_write_pretrained_manifest.py`, `tests/backend/api/test_personalized_insights_model.py` (status assertion made additive); `docs/sentiment/*`, `docs/SECURITY.md`, `docs/THREAT_MODEL.md`, `docs/ARCHITECTURE.md`, `training/sentiment/README.md`, `reports/sentiment_*`. Pre-existing earlier-phase files that were also written on or after 2026-11-03 and are not Stage A work include `scripts/sentiment_preflight.py`, `scripts/export_demo_fixtures.py`, `frontend/tests/route-probe.mjs` and `docs/demo_runbook.md`.

**Outside the repository (not in Git):** `C:\Users\Administrator\.copilot\wealthpilot-stageA\` (isolated `venv`, `scripts`, `resolve`, `results`) and `C:\Users\Administrator\.copilot\wealthpilot-approved-models\horizon-multilingual-sentiment-small\` (8 files, 570 MB). The rollback backup `wealthpilot-taskcert-rollback` is untouched.

## 14. Final Stage A Verdict

**Technical objectives: ACHIEVED (VERIFIED).** The approved model, at its exact revision, was downloaded, checksum-verified against the repository's own manifest, loaded from safetensors in an isolated, hash-locked environment and ran real CPU inference; its configuration, tokenizer, native labels, output shape and probability handling (exactly one softmax) were verified; results were bitwise stable; the run made no network call, no `torch.load` call and executed no remote code. Status: `INFERENCE_VERIFIED` for the reference implementation in the isolated environment, **nothing more**. It is a smoke test on eight invented sentences: it supports no accuracy, calibration, generalisation, human-agreement or production-readiness claim, and the observations (a "mixed" sentence read as neutral, a hypothetical read as negative, a negated "not worried" read as positive) show why the rules safeguards remain necessary.

**Test evidence: NOT fully green.** Nine runs: 4,294 passed, 1 failed, 9 skipped, 0 errors. The single failure is a false positive in an unrelated GDELT test, left unmodified. About 546 API tests were not re-run in the final chain; the two original database errors are unresolved; one further transient database connection error was observed.

**Process: a test-execution failure with two boundary crossings, disclosed.** Because I used plain `pytest` instead of the project's isolated runner, the `agents` directory connected to the development database `neondb` (access confirmed; read-only by test design; direct test-level writes none identified; application-level writes not fully verified; actual state not verified; **modification unknown**) and made three rate-limited live Gemini calls. I do not claim that `neondb` was untouched or proven unmodified, and the suite as run was not fully isolated.

**Production and the application: unchanged (VERIFIED).** Stage A can be regarded as complete for its inference and integrity goals, with the caveats above. It is **not** a clean bill of health for the whole suite, and it is not production readiness.

## 15. Stage B Readiness — Not Authorized

**NOT AUTHORIZED.** Stage B (in-application runtime selection, registry change, in-application smoke test, any production activation) was not started and is not permitted by this report. A successful Stage A is not permission to proceed. Open decisions for the owner: the in-application runtime (the verified reference stack after a resolver dry-run against the TensorFlow environment, or ONNX Runtime after an artifact-policy extension and a parity check), the registry change with an ADR, an in-application smoke test, and, separately and later, any production activation.

