# Stage A report — Horizon multilingual sentiment, real local CPU inference (ADR-054 addendum)

Written for: the project owner. Dates: 2026-11-04. Scope: **research inference only**, in an isolated environment. Statuses use the requested words: IMPLEMENTED, TESTED_WITH_MOCKS, INFERENCE_VERIFIED, BLOCKED, DEFERRED, NOT_IMPLEMENTED.

**Headline.** The approved model (`Horizon-Labs/multilingual-sentiment-small` @ `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac`) loaded from its checksum-verified safetensors file and produced real predictions on CPU in the isolated environment: **INFERENCE_VERIFIED for the reference implementation (transformers 5.17.0 + torch 2.15.0+cpu), in the isolated environment only.** This is a smoke test: no accuracy, precision, recall, F1, calibration, human-agreement or superiority claim is made or possible. The application is unchanged: `.venv` untouched, registry unchanged, `SENTIMENT_TRANSFORMERS_ENABLED=false`, production `user_text_rules_v1`. Stage B is not authorised and was not started.

## 1. Test classification

### 1.1 The stopped full-suite run (preserved)

The full run was stopped after the owner approved the change of approach. Counts: **796 completed: 792 passed, 2 errors, 2 failures, 0 skipped** (an earlier snapshot of the same run read 681 completed with 2 errors; the run continued while the plan was being agreed, so 796 is the figure at the moment it was stopped). Logs: `...\scratchpad\archive_partial_run\full_suite_partial_*.txt`. The log holds no tracebacks, because pytest prints them only at the end of a run; **the original tracebacks of the two errors were therefore lost with the stopped run and are not recoverable.**

### 1.2 The two original errors (errors at setup or teardown, not test-body failures)

| Test | Result when reproduced |
| --- | --- |
| `test_household_goals.py::test_a_required_field_cannot_be_cleared_with_null[goal_type]` | passed alone; passed again inside a full run of its file |
| `test_monthly_records.py::test_malformed_values_are_rejected_with_422_and_nothing_is_stored[payload8]` | passed alone; passed again inside a full run of its file (53 passed) |

Neither error reproduced, so **their individual root causes cannot be proven**. What the reproduction did show: re-running the household-goals file produced a *different* error, `ERROR at setup of test_invalid_input_is_422[overrides22]` — `sqlalchemy.exc.OperationalError: (psycopg.OperationalError) consuming input failed: server closed the connection unexpectedly`, raised at an `INSERT INTO customers` in `tests/backend/api/conftest.py:138` (the test body never ran). That test passed when re-run alone (12 s). Classification: **transient infrastructure fault — the hosted PostgreSQL test database closed the connection during fixture setup; the failing test moves between runs and passes on re-run; no code defect.** For the two original errors this is the best-supported explanation (same error class, setup-time, non-deterministic), not a proven one. The documented project guidance (`docs/TEST_PLAN.md`, transient failures) describes the same pattern.

### 1.3 The two failures — genuine defects in my own earlier change, fixed

Both were caused by the additive `transformer_research` response field introduced in ADR-053; I had run only sentiment-focused subsets then and never these files.

| Test | Cause | Fix |
| --- | --- | --- |
| `test_personalized_insights_hardening.py::test_the_frontend_test_fixtures_are_exactly_what_the_backend_returns_today` | the saved frontend fixtures predated the field (`fixture records-only drifted from the backend`) | regenerated with `scripts/export_insight_fixtures.py` from the real current backend: 22 fixtures changed; **in every one the only difference is the added `transformer_research` object; everything else is identical** (checked programmatically); it shows the real disabled state (`enabled: false`, models `disabled`, `total_ms: null`) |
| `test_personalized_insights_interpretation.py::test_every_field_of_the_previous_response_is_still_present` | exact key-set equality (`Extra items in the right set: 'transformer_research'`) | the assertion now requires every previous field to remain, allows **exactly one** documented addition (`set(j) - previous == {"transformer_research"}`, so any other new key is still rejected), checks the object is display-only (`enabled false`, `production_effect none`, `not_human_validated`), and checks the submitted text is not echoed into it |

After the fixes: hardening 33 passed; interpretation 24 passed.

### 1.4 Two further tests that the owner-approved Stage A changed legitimately

- `tests/backend/scripts/test_sentiment_preflight.py::test_the_command_exits_1_and_says_blocked_while_any_gate_is_open` asserted "no artifact on this machine". The approved download makes preflight gate 5 pass (it only reports whether a `model.safetensors` exists; it verifies nothing). The test now asserts what is true: exit 1, gates 1/3/4/6 blocked with blockers, gate 5 mirrors the file system, gate 7 passes. **The preflight still reports BLOCKED.**
- `frontend/tests/transformer-research.cases.tsx` used a saved fixture as its "older response without the research object"; the regenerated fixture now carries it, so the test builds the old shape explicitly by removing the field.

## 2. Sequential backend suites

Final results are in `docs/sentiment/stage_a/STAGE_A_COMPLETION_REPORT.md`, section 8 (nine directory runs: **4,294 passed, 1 failed, 9 skipped, 0 errors**; the failure is the unrelated GDELT scaffold heuristic; about 546 API tests before `test_profiles.py` were not re-run in the final chain). That report is the final record; where the two differ, it governs.

## 3. Isolated environment (outside the repository)

`C:\Users\Administrator\.copilot\wealthpilot-stageA\venv` — Python 3.11.9 (64-bit), pip 24.0; a separate virtual environment created from the base interpreter, **not** the project `.venv`.
Resolver dry-run first (`pip install --dry-run --report`): exit 0, 35 packages, 0 source distributions; `torch 2.15.0+cpu` only from the PyTorch CPU index (`download-r2.pytorch.org`), every other package from `files.pythonhosted.org`; `numpy` held at **1.26.4** (the application's version) so a clean run is evidence for a later integration.
Installed from the hash-pinned lock `docs/sentiment/stage_a/requirements-stage-a.lock.txt` with `pip install --require-hashes --no-deps --only-binary=:all:`; `pip check`: no broken requirements.

| Package | Version |
| --- | --- |
| transformers | 5.17.0 |
| tokenizers | 0.23.3 |
| safetensors | 0.8.0 |
| huggingface-hub | 1.33.0 |
| torch (CPU build) | 2.15.0+cpu (CUDA available: no) |
| numpy | 1.26.4 |

Others in the lock (all hashed): annotated-doc 0.0.5, anyio 4.16.0, certifi 2026.10.23, click 8.5.0, colorama 0.4.6, filelock 4.2.8, fsspec 2026.9.0, h11 0.16.0, hf-xet 1.8.0, httpcore 1.0.9, httpx 0.28.1, idna 3.20, jinja2 3.1.6, markdown-it-py 4.2.0, markupsafe 3.0.4, mdurl 0.1.2, mpmath 1.3.0, networkx 3.6.1, packaging 26.3, pygments 2.21.0, pyyaml 6.0.3, regex 2026.9.29, rich 15.0.0, setuptools 84.2.1, shellingham 1.5.4, sympy 1.14.0, tqdm 4.70.1, typer 0.27.3, typing-extensions 4.16.0. Disk: 937 MB.

**The application `.venv` was not touched:** its `site-packages` timestamp is unchanged (2026-10-29 21:31:18) and it still has TensorFlow 2.17.0, Keras 3.15.1, numpy 1.26.4, protobuf 4.25.9 and none of the new packages.

## 4. Download and integrity

Only the eight approved files, at the exact revision, via `hf download` (telemetry off), into `C:\Users\Administrator\.copilot\wealthpilot-approved-models\horizon-multilingual-sentiment-small` (outside the repository): `model.safetensors` (562,584,932 bytes), `config.json`, `tokenizer.json` (34,363,286), `tokenizer_config.json`, `special_tokens_map.json`, `SHA256SUMS`, `LICENSE`, `NOTICE`. The downloader's own metadata records commit `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac`. No `onnx/`, no pickle-capable file.
Every file matches the repository's `SHA256SUMS` **and** the values I had recorded earlier from a summarising fetch (so those recordings are now confirmed first-hand); `model.safetensors` = `f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1`, recomputed independently with `Get-FileHash`. Files were re-hashed once more by the smoke script itself before anything was loaded.

## 5. Actual inference — INFERENCE_VERIFIED (reference stack, isolated environment, CPU)

Script: `...\wealthpilot-stageA\scripts\stage_a_smoke.py`; raw results: `...\results\stage_a_inference_results.json` (outside the repository). Status `COMPLETED`, errors none.

**Verified:** model class `ModernBertForSequenceClassification`, 140,642,691 parameters, float32, CPU; config read with `rope_parameters` for both layer types at `rope_theta` 160000 and 22 `layer_types` (the setting that, from reading its source, transformers 4.57.1 would likely have got wrong; that version was not run); tokenizer `TokenizersBackend` over `tokenizer.json`, `len(tokenizer)` 256000 = vocab 256000; sequence is wrapped as `<bos> … <eos>` (ids 2 … 1); inputs `input_ids` and `attention_mask`, int64, shape `[1, n]`, ids within the vocabulary, attention mask all ones; maximum length used 512 (the tokenizer's own limit is 8192; an 8,039-character input of 1,682 tokens truncated to exactly 512 and ran, 321.9 ms); output logits shape `[1, 3]`; **native labels `0 negative, 1 neutral, 2 positive`** (as expected); no NaN or infinity anywhere.

**Probability handling:** the raw output is logits (for the negative-intent sentence `[4.7016, 0.6210, -2.8954]`, sum 2.43, not a probability vector). **One** softmax gives `[0.9829, 0.0166, 0.0005]`, which equals the library's own `text-classification` pipeline scores to 1.9e-9. A second softmax would have flattened this to `[0.570, 0.217, 0.213]` and was not applied. These probabilities are uncalibrated.

**Stability:** five repeats of an identical input, default threads and a single thread: maximum difference 0.0 (bitwise identical), same label under both thread settings; batch versus single-sentence inference differ by 2.4e-6 at most.

### Predictions (fictional functional smoke-test inputs; "intent" is only what the sentence was written to express, NOT ground truth)

| Input (fictional) | Intent | Native label | Softmax (negative / neutral / positive) | Logits | Tokens | ms |
| --- | --- | --- | --- | --- | --- | --- |
| I feel happy because my savings have increased this month. | positive | **positive** | 0.0002 / 0.0002 / 0.9996 | -2.03, -1.75, 6.60 | 13 | 22.5 |
| I am worried because my monthly loan payments are becoming difficult to manage. | negative | **negative** | 0.9829 / 0.0166 / 0.0005 | 4.70, 0.62, -2.90 | 16 | 18.3 |
| I deposited five thousand rupees into my savings account this month. | neutral | **neutral** | 0.0030 / 0.9591 / 0.0379 | -2.37, 3.41, 0.18 | 14 | 22.9 |
| My investments are growing, but I am worried about future expenses. | mixed | **neutral** | 0.0857 / 0.8839 / 0.0303 | 0.21, 2.54, -0.83 | 15 | 18.8 |
| I reviewed my account statement yesterday. | ambiguous | **neutral** | 0.0020 / 0.9927 / 0.0053 | -1.79, 4.42, -0.81 | 9 | 18.6 |
| I am not worried about my savings at all. | negation | **positive** | 0.0323 / 0.2371 / 0.7306 | -1.14, 0.85, 1.98 | 12 | 21.0 |
| If I lost my job I would panic about my savings. | hypothetical | **negative** | 0.8254 / 0.1338 / 0.0408 | 2.49, 0.67, -0.51 | 14 | 20.4 |
| Estoy muy contento porque por fin pude ahorrar para mis vacaciones. | other language | **positive** | 0.0004 / 0.0004 / 0.9991 | -1.98, -1.96, 5.77 | 14 | 16.4 |

These are the model's actual outputs on eight invented sentences. They are **not an evaluation**: eight hand-written inputs say nothing about accuracy, calibration or behaviour on real personal-finance language. Observations only: the model has three classes, so the "mixed" sentence came back as neutral; the hypothetical sentence read as negative although it describes no current feeling; these are the cases WealthPilot's rules safeguards and the comparison layer exist for.

**CPU runtime:** model load 0.82 s (warm file cache); per-sentence 16.4 to 22.9 ms (median 20.4 ms, 9 to 16 tokens); 512-token input 321.9 ms; whole script 4.05 s. **Memory (measured with correctly typed Windows API calls in a separate run; the first helper returned a bogus 0.0 and was discarded):** peak working set 305 MB after the Python imports, **1,139.7 MB** after loading the model, unchanged after one inference.

## 6. Privacy, network and safety checks (all from the run itself)

- Interpreter and prefix are the isolated environment's.
- Offline variables set (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `HF_HUB_DISABLE_TELEMETRY`); every socket entry point wrapped to refuse and count: **0 attempts**.
- `torch.load` (the pickle-capable loader) was replaced by a function that raises: **0 calls**; model loaded with `use_safetensors=True`; no pickle-capable file in the model directory.
- `trust_remote_code=False`, no `auto_map`, no module imported from the model directory.
- Only fictional sentences were used; no real customer text; no dataset created (the eight sentences are inline in the smoke script, outside the repository, with no ground-truth labels); no fine-tuning; no external API; no database touched by the inference.

## 7. Production and application boundaries (unchanged)

Active registry unchanged (FinBERT and Twitter-RoBERTa, both gated off; Horizon not added); `SENTIMENT_TRANSFORMERS_ENABLED=false`; `SENTIMENT_MODEL_ENABLED=false`; production `user_text_rules_v1`; no change to risk, goals, portfolio, recommendations or compliance; `.venv`, TensorFlow and application dependencies untouched; **CORRECTION (2026-11-04): the development database `neondb` WAS accessed** by the `tests/backend/agents` directory (and by `test_analysis.py` in the stopped run), which I ran with plain `pytest` instead of `scripts/run_isolated_db_tests.py`: access CONFIRMED, read-only by test design, direct test-level writes in the inspected files none identified, application-level writes not fully verified, actual database state not verified, **modification UNKNOWN**. The earlier sentence in this report claiming `neondb` was not accessed was wrong and is withdrawn. Full account: `docs/sentiment/stage_a/STAGE_A_COMPLETION_REPORT.md`, section 10.3. Nothing was committed or pushed; `docs/sentiment/stage_a/requirements-stage-a.lock.txt` is the only new repository artifact of the environment work.

## 8. Remaining backend suites (sequential, one process at a time, nothing deselected)

See the completion report, section 8 (nine final runs, the coverage gap, and the `agents` directory's database-boundary label).

## 9. Remaining blockers and recommended Stage B

Stage B is not authorised. Open decisions: the in-application runtime (the verified reference stack, with the lock above, installed into the main environment only after a resolver dry-run shows no change to the TensorFlow stack — the Stage A environment already used numpy 1.26.4 successfully — or ONNX Runtime, which needs an artifact-policy extension and a parity check against these Stage A outputs); the registry change with an ADR (generalising the `finbert` / `roberta` keys to role keys, as ADR-054 describes); an in-application smoke test; and, separately and later, any production activation, which this work does not authorise. **Recommended:** the reference stack, because it is now proven on this machine with the exact approved artifact; keep the first in-app load outside the inference timeout with an explicit operator warm-up (about 1.1 GB resident); keep research mode off by default.
