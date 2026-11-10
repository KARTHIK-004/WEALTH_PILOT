# Sentiment Test Report (2026-11-05)

Written for: the project owner and reviewers. Every figure below comes from a command run during this work; nothing is estimated. DB-free suites ran under a socket-guard pytest plugin (any external connection or DNS lookup would be counted and refused; count was **0** in every run). DB-backed suites ran **only** through `scripts/run_isolated_db_tests.py` (host `…neon.tech`, database **`neondb_test`**, never `neondb`). The `agents` directory was **not** run (it uses the development database and live Gemini). Nothing was committed or pushed.

## 1. Results

| Suite | Command (abridged) | Result |
|---|---|---|
| Sentiment set (new slots, API, reviews, rules regression, personalized insights x3, preflight, manifest writer, `tests/training/sentiment`) | `pytest -p netguard tests/backend/core/test_sentiment_research_slots.py tests/backend/api/test_sentiment_research_api.py tests/backend/core/test_user_text_rules_regression.py tests/backend/api/test_personalized_insights*.py tests/backend/core/test_sentiment_candidate_reviews.py tests/backend/scripts/test_sentiment_preflight.py tests/backend/scripts/test_write_pretrained_manifest.py tests/training/sentiment` | **861 passed, 3 skipped** (netguard attempts: 0) |
| `tests/backend/core` | `pytest -p netguard tests/backend/core` | 1197 passed, 4 skipped, **1 failed** -> fixed (see 2a) -> `test_task_cert_1_state.py` 3 passed |
| `tests/backend/data` | same | 1508 passed, **1 failed** (GDELT, see 2b), **4 errors** (DB needed, see 2c) |
| `tests/backend/scripts` | same | 263 passed, 1 skipped |
| `tests/backend/pipeline` | same | 31 passed |
| `tests/backend/security` | same | 147 passed |
| `tests/training/sentiment` (alone, 3 runs) | same | 675 passed, 1 skipped (and 33/33 for `test_evaluate_frozen_mode.py`, twice) |
| `tests/training/{behaviour,expense,market,portfolio}` | same | 13, 10, 51, 12 passed |
| `tests/training/risk` | same | completed (13 passed) in 4 of 6 runs; **2 of 6 runs aborted with a native access violation** (see 2d) |
| DB-backed: ingestion (4 tests that errored under the guard) | `run_isolated_db_tests.py --suite ingestion -- -k <4 tests>` | **4 passed** |
| DB-backed: API sentiment/insight subset | `run_isolated_db_tests.py --suite api -- -k "sentiment or personalized or insight"` | **89 passed**, 552 deselected |
| Frontend unit + Vite SSR component cases | `npm test` | **279 / 279 passed** |
| Frontend mutation harness | `npm run test:mutations` | **200 of 200 mutations detected** (TR1-TR18 cover the research panel) |
| Frontend type check / lint / build | `npx tsc -b`, `npx oxlint`, `npm run build` | all exit 0 (oxlint: 8 pre-existing warnings, 0 errors) |

Not run: `tests/backend/agents` (development DB + live Gemini; forbidden by the standing boundary); the remaining DB-backed API/DB suites in full (hours; only the relevant subset was run); the opt-in real-weights smoke test (`test_horizon_real_weights_smoke.py`, skipped by design, needs Stage B placement).

## 2. Non-green items, classified from their own tracebacks

a. **`test_task_cert_1_state.py::test_the_remediation_changed_no_other_pinned_tooling`** asserted `setuptools == 65.5.0`. The owner-approved `setuptools==81.0.0` correction made it stale. I changed the assertion to accept `65.5.0` or `81.0.0` with a comment pointing to `RECOVERY_RECORD.md`; the TensorFlow, Keras and NumPy pins in the same assertion are unchanged. Disclosed here because it edits a test from an earlier phase.

b. **`tests/backend/data/gdelt/test_sentiment_scaffold.py::test_no_production_entry_point_or_helper_imports_the_sentiment_scaffold`** fails for an unrelated reason (the GDELT scaffold guard). It is a false positive for this work, was reported earlier, and was not modified.

c. **`tests/backend/data/test_ingestion.py` (4 errors)** are expected under the socket guard because they need the database; they passed (4/4) through the isolated runner on `neondb_test`.

d. **Native access violation (UNRESOLVED, not caused by sentiment code).** A combined run of the DB-free backend directories plus `tests/training`, and two full `pytest tests/training` runs, aborted (at about 82%, 9% and 21% of the run), always with `Windows fatal exception: access violation`, once in TensorFlow graph-op creation, otherwise in pure-Python code (`_jaccard`) with joblib loky threads alive. Findings: each sub-directory passes alone; `tests/training/sentiment` passed in three separate runs; `tests/training/risk` aborted in 2 of 6 runs even though `torch` was **not imported** in that process (`'torch' in sys.modules` was False; TensorFlow was); an earlier full `tests/training` run at 21:07 on 2026-11-04, before the Transformer packages were installed, passed (735 passed, 3 skipped). So a connection to the B2.1 installation is **neither shown nor excluded**: a flaky TensorFlow/xgboost/joblib interaction on this machine is equally consistent. I did not change any code or environment in response (out of scope; CLAUDE.md section 4). **Consequence:** I cannot claim a single clean full-directory `tests/training` run in the current environment; I can claim every sub-directory passed in isolation. **Suggested follow-up for the owner:** re-run `tests/training` several times, and once with the Transformer packages hidden (for example in a copy of the environment) to separate cause from coincidence.

## 3. What the new tests establish (and what they do not)

- **Registry/gates:** an unregistered candidate cannot run; Horizon constant is `pending_owner_approval`; licence, format and registration gates fail closed in order.
- **Normalisation/comparison:** one softmax; label order read from the model's own config; unknown or mixed vocabularies refused; every comparison status and every combined-reading rule (agree, differ, rules abstained, weak-rules safeguard, fallback).
- **Lifecycle:** artifact defects (missing, corrupt, wrong revision, forbidden file types), timeout then immediate breaker response, back-off, cache, config parsing incl. threads, unexpected exceptions mapped to fixed reasons, status never loads, concurrent callers get `loading`, `build_transformer_research` never raises.
- **Privacy/isolation:** text appears in no log, error or response (capture-based); no network call; `torch.load` never used; non-English and code-mixed text (Tamil, mixed scripts) never reaches a model; sentiment output cannot reach risk, goals, portfolio, recommendation or compliance modules; flags default off; `user_text_rules_v1` unchanged.
- **API:** 400 and 422 as `application/problem+json` without echoing text; the status endpoint's new fields; every analysis response keeps `model_version` and `data_source`.
- **Frontend:** 15 component cases, one card per slot, empty slot is not a failure, unknown label never rendered as neutral, no confidence shown, no browser-side computation; 18 research-panel mutants all detected.
- **Mocks:** the real adapter path is exercised with a fake backend factory and fault injection. **These tests do not show that the model is accurate, and the adapter has not loaded the real weights.**

---

# R-series (R1 registration, R2 real-weights smoke, R3 training-crash investigation) - 2026-11-07/09

Same rules as above: DB-free suites ran under the network guard (external attempts 0 except the four ingestion tests that need a database and are rerun through the isolated runner); DB-backed suites ran only through `scripts/run_isolated_db_tests.py` on `neondb_test`; `agents` was not run; nothing was committed or pushed.

| Suite | Result |
|---|---|
| Sentiment set (slots, API, rules regression, personalized insights x3, reviews, preflight, manifest tool, real-weights smoke file) | **186 passed, 11 skipped** (the 9 smoke tests skip by default; run opt-in below) |
| Opt-in real-weights smoke (`WEALTHPILOT_REAL_WEIGHTS_SMOKE=1`) | **9 passed** (31 s) - `R2_APPLICATION_ADAPTER_SMOKE_TEST_REPORT.md` |
| `tests/backend/core` | **1198 passed**, 12 skipped (one guard test updated, see below) |
| `tests/backend/data` | 1508 passed; 1 failed = the known GDELT scaffold guard (unrelated, unchanged); 4 errors = DB needed, **4 passed** via the isolated runner |
| `tests/backend/scripts` / `pipeline` / `security` | 263 passed (1 skipped) / 31 passed / 147 passed |
| `tests/training`, by sub-directory | behaviour 13, expense 10, portfolio 12, market 51, risk 13, sentiment 675 passed (1 skipped); **no run aborted** |
| `tests/training`, whole directory in one process | **not reliably runnable**: aborts with the NVIDIA-driver/XGBoost fault in most runs (R3: 14 of 16 unprotected runs, 0 of 8 with the intervention) |
| DB-backed API subset via the isolated runner (`-k "sentiment or personalized or insight or demo"`) | 144 passed; 11 errors in `test_seed_demo_data.py` (family seeding, unrelated to sentiment) from `getaddrinfo failed` / `connection timeout expired`; re-run in isolation: 3 passed, 6 errors again from the same network messages. **Not verified; classified as network, not as assertion failures.** |
| Frontend `npm test` | **279 / 279** |
| Frontend mutation harness | **200 of 200 detected** |
| `npx tsc -b` / `npx oxlint` / `npm run build` | exit 0 / 0 errors (8 pre-existing warnings) / exit 0 |
| Generated types | regenerated to a scratch file: **identical** to `src/types/api.ts`; insight and demo fixtures regenerated (22 + 9) and `--check` passes |

## Tests changed because the registered state is now the truth

14 tests that pinned "Horizon is pending, nothing is registered" were rewritten to assert the registered state (5 files); `test_sentiment_final_state.py` now allows exactly one untracked weight file, `models/sentiment_pretrained/horizon/model.safetensors`, and requires the `.gitignore` rule; two frontend cases were split so that the real saved response (Horizon registered, research off) and a hand-built "nothing registered" response are both covered. An autouse fixture makes the unit tests read an empty directory instead of the real model directory. No test was deleted or skipped to get green.

## Findings that are not green

- **GDELT scaffold guard** (unchanged, reported separately).
- **`test_seed_demo_data.py` network errors** above: unresolved because the hosted database was intermittently unreachable (DNS and timeouts), not because of an assertion.
- **XGBoost/NVIDIA fault** in whole-directory `tests/training` runs: root cause and evidence in `R3_TRAINING_NATIVE_CRASH_INVESTIGATION.md`.
