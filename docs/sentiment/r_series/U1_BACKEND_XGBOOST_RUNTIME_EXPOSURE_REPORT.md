# U1 - Backend XGBoost / NVIDIA DLL runtime exposure: read-only investigation

Date: 2026-11-10. Written for: the project owner. Scope: read-only. No application code, dependency, `.venv`, model artifact, environment file, database, driver, GPU setting or the R4 DLL guard was changed; nothing was committed or pushed; no server was started and no request was served.

## 1. Executive summary

- **Question:** can the R3/R4 NVIDIA DLL lifetime fault (`nvdxgdmal64.dll+0x8080`, triggered by XGBoost on this hybrid-graphics machine) affect the backend at runtime?
- **Result for the backend's own import closure (OBSERVED):** across 37 fresh-subprocess experiment runs (all PASS, all exit 0) the backend modules that make up the served application imported **without ever importing `xgboost`**, and no experiment - including three that did import XGBoost - mapped `nvdxgdmal64.dll` or any other NVIDIA module. No native crash occurred.
- **Latent path found (OBSERVED, not currently wired):** `import autogen` (and `import flaml`) imports `xgboost` as a side effect (`autogen/oai/client.py:9` -> `flaml/__init__.py:5` -> `flaml/automl/__init__.py:4` -> `automl.py:22` -> `ml.py:12` -> `xgboost`). The backend imports `autogen` only inside `agents/debate.py::run_strategy_debate` (line 458, inside a function), and nothing in `backend/wealthpilot` calls that function today (only tests do). So the path exists in the code base but is not on the served path as written.
- **Important limit:** `import xgboost` alone did not map any NVIDIA DLL in any run. R3 showed the DLL loads when XGBoost is used (fit + predict), not on import. So this investigation shows *whether XGBoost can be loaded by the backend*, and the answer is "not by the tested imports"; it does not, and cannot (by the stage rules), show what happens when a loaded XGBoost is used.
- **Classification (section 12): "No exposure observed in tested imports"**, with a named latent path and several things explicitly NOT RUN. This is not a claim that the backend is safe, and not a claim that the driver defect is fixed.

## 2. Static import graph (Stage 1, read-only)

Method: read the entry points, `lifespan`, every router's import lines, `agents/nodes.py`, `agents/graph.py`, `db/session.py`, `config/settings.py`; searched all of `backend/wealthpilot` (excluding the GDELT tooling, which is not imported by any served module) for module-level calls that open files, read the environment, create engines or clients, or touch the network; read `training/` modules the backend imports; scanned `site-packages` for importers of `xgboost`; scanned the served pickle artifacts' opcode streams (never unpickled).

```
api/main.py            -- calls get_settings() AT IMPORT (line 38): reads the repo-root .env (real credentials). NOT imported by any experiment (BLOCKED).
  api/lifespan.py      -- imports agents.nodes; model warming runs only inside the async lifespan, not at import
  api/routers/*        -- 13 routers; import api.dependencies / api.schemas / api.services.* / db.models / security.*; no module-level I/O found
  api/dependencies.py  -- imports get_settings / get_engine as FUNCTIONS; create_engine only inside get_engine(), called per request
  api/services/analysis_service.py -> agents.graph (langgraph, langchain_core), agents.recommendation, agents.explanation, db.models
agents/nodes.py        -- joblib, numpy, pandas, sqlalchemy, core.*, data.preprocessing (-> data.acquisition: imports urllib.request, no call)
  lazy (inside functions): training.behaviour.common / .detection (sklearn IsolationForest), db.models
agents/explanation.py, qa_service.py  -- google.genai imported inside functions (lines 518, 61)
agents/debate.py       -- `import autogen` inside run_strategy_debate (line 458); google.genai inside functions
core/sentiment_model.py -- torch/transformers inside a function (flag off)
```

| Item requested | Finding |
|---|---|
| Direct `xgboost` imports | none under `backend/**/*.py`; present only in `training/risk/common.py:26`, `training/risk/xgboost_model.py:30`, `training/market/common.py:164` (inside a function) |
| `shap` imports | none in `backend/`; only `training/risk/explain.py:22` |
| Indirect importers in installed packages | `shap` (lazy, inside functions), `sklearn/ensemble/_hist_gradient_boosting/utils.py` (lazy test helper), **`flaml` (top-level: `flaml/automl/model.py:27`, `ml.py:12`)** |
| Who pulls `flaml` | `pyautogen 0.2.35` requires `flaml`; `autogen/oai/client.py:9`, `cohere.py:33`, `completion.py:10-12` import it at module level |
| Modules that load model artifacts | `agents/nodes.py` only: `_risk_artifacts_cached` (`preprocessor_v1.pkl`, `rf_v1.pkl`), `_behaviour_artifacts_cached` (`iforest_v1.pkl`), `_far_trans_tables_cached` (CSV); triggered by `lifespan.warm_model_caches` or first use, never at import |
| Served risk model | `models/metrics.json` `risk.best_model = "random_forest"`; `xgb_v1.pkl` and `mlp_v1.keras` exist but nothing in `backend/` loads them |
| Artifact opcode scan (not executed) | `preprocessor_v1.pkl`, `rf_v1.pkl`: only `sklearn.*`, `numpy`, `joblib.numpy_pickle`. `iforest_v1.pkl`: `sklearn.ensemble._iforest`, `sklearn.tree.*`; the opcode scan stopped at the embedded array data, so that list is partial (sklearn/numpy only up to that point) |
| DB engines created at import | none found; `create_engine` only inside `db/session.py::get_engine` |
| External API clients at import | none found; Gemini/AutoGen clients are built inside functions |
| Network at import | none found in project code; two library-level probes were observed (section 8) |
| Declared dependencies | `wealthpilot` lists `xgboost==2.1.2` and `shap==0.46.0` as dependencies; declared is not imported |

## 3. Direct and transitive XGBoost import findings

| Experiment (3 runs each) | Imported | `xgboost` in `sys.modules` | Evidence |
|---|---|---|---|
| S2A / S2B `xgboost` | `xgboost` | yes (control) | `xgboost.dll` loaded via `ctypes` |
| S3 `shap` | `shap` | **no** | |
| S3b `flaml` | `flaml` | **yes** | chain via `flaml/__init__.py:5` -> `automl/__init__.py:4` -> `automl.py:22` -> `ml.py:12` |
| S3c `autogen` | `autogen` | **yes** | `autogen/oai/client.py:9` -> the flaml chain above |
| S3d `wealthpilot.agents.debate` | the module only | no (autogen is imported lazily) | |
| S4a `wealthpilot.agents.nodes` | | no | |
| S4b `wealthpilot.agents.graph` | | no | |
| S4c `wealthpilot.api.services.analysis_service` | | no | |
| S4d `wealthpilot.api.lifespan` + `api.dependencies` | | no | |
| S4e `api.errors`, `api.sse`, `api.lifespan` + all 13 routers | | no | the import closure of `main.py` minus `main.py` |
| S4f `training.behaviour.common` + `.detection` | | no | |

## 4. SHAP findings

`import shap` (3 runs): imports `numba` and `sklearn` but **not** `xgboost`; shap's references to XGBoost are inside functions (`_tree.py:221,288`, `pytree.py:170`, `utils/_clustering.py:99`). The backend does not import `shap`; only `training/risk/explain.py` does. SHAP is therefore not a path to XGBoost for the backend, and not a trigger by import.

## 5. Standalone XGBoost import results (Stage 2)

- `S2A` (instrumented: audit hook + continuous module poller), 3 runs, and `S2B` (minimal: no hook, no poller, one final module snapshot after a 2 s linger), 3 runs - all exit 0, no exception, no native crash.
- `xgboost.dll` is loaded through `ctypes.dlopen` at about 1.5 s into the import. **No NVIDIA module (`nvcuda`, `nvapi64`, `nvdxgdmal64`, `cuda*`, ...) appeared in any of the six runs.** In the instrumented runs the poller made about 2,300 polls per run (about 1.8 ms apart over the whole run).
- The `S2B` result rests on a single end-of-run snapshot, so by itself it could not see a module that had already been unmapped; it is a control for the instrumentation (same exit code, same `sys.modules`), not independent evidence about DLL loading.
- No fit, predict, `DMatrix` or `Booster` was created (Stage 2 rule).

## 6. Backend module import results (Stage 4)

All of S4a-S4f: 18 runs, exit 0, every import `ok`, `xgboost` never in `sys.modules`, no NVIDIA module seen, no artifact file (`.pkl`, `.joblib`, `.keras`, ...) opened during import, no `.env` read attempted. TensorFlow, PyTorch and Keras were not imported by any backend module (the heavy-library lists are in `u1_results.jsonl`, `heavy_loaded`).

**Not imported (BLOCKED):** `wealthpilot.api.main`. Its line 38 calls `get_settings()` at import, which reads the repo-root `.env` (database URL, Gemini key, protected-data keys) and builds the application. That fails the Stage 4 precondition, so it was not run. Its import closure was covered by S4e (all routers + lifespan + errors + sse), which is everything `main.py` imports except `main.py` itself and the already-covered `config`.

## 7. NVIDIA DLL loading observations

- **Observed:** no NVIDIA module in any of the 37 runs (baseline at interpreter start: none). That includes the nine instrumented runs where `xgboost` was imported and `xgboost.dll` was mapped (`S2A` x3, `S3b` x3, `S3c` x3).
- **Poller sensitivity control** (`u1_control.py`, 40 runs): a harmless non-NVIDIA system DLL (`mscms.dll`) was loaded and unloaded in a fresh instrumented process. Mapped for 21 ms (the R3 lifetime of `nvdxgdmal64.dll`) it was seen by the poller in **20 of 20** runs; mapped for 5 ms, **20 of 20**. This shows the poller can see a short-lived module in an otherwise idle interpreter. It was not measured under heavy import load; the real runs' average poll spacing (about 1.8 ms) is the best available bound.
- **Interpretation (INFERENCE consistent with R3):** XGBoost's CUDA/driver probe happens when XGBoost is first used, not when it is imported. Therefore a process that merely imports XGBoost, as `autogen`/`flaml` do, is not shown to touch the NVIDIA driver; a process that then *uses* XGBoost would. Use was not tested (rule), and the crash cannot be produced on demand (R3), so "no crash observed here" carries no information about the fault itself.

## 8. Database and network safety verification

| Check | Result |
|---|---|
| `neondb` / `neondb_test` accessed | **No.** No database URL was supplied; the runner passes `DATABASE_URL`, `TEST_DATABASE_URL`, `GEMINI_API_KEY`, `PROTECTED_DATA_KEYS` as **empty strings** and nothing else from the environment except the Windows/interpreter allow-list (`u1_run.py::ALLOW`) |
| `.env` read | **No.** The audit hook blocks any `open()` of a file named `.env*` and records the attempt; zero attempts in 37 runs |
| Sockets / DNS | The audit hook blocks `socket.connect`, `getaddrinfo`, `gethostbyname`, `sendto`, `bind` and records the attempt. Observed attempts: only `bind(('::1', 0))` from `urllib3/util/connection.py:137` (its import-time IPv6 capability check; local only, reached through langchain/langgraph), once per run in S4b, S4c, S4e. Zero `connect`/DNS attempts |
| Subprocess | Blocked and recorded: 3 per run, all `cmd.exe /c ver` from `platform.win32_ver` called by `sklearn/utils/fixes.py:33` (`platform.machine()`); `platform` falls back, every import still succeeded. No other process start was attempted |
| Server / request | none |
| Repository changes | `git status --porcelain` outside the evidence folder is byte-identical before and after (same hash); `PYTHONDONTWRITEBYTECODE=1` and `-B` kept `__pycache__` untouched |
| Dependencies | `pip freeze` identical to the R3/R4 reference; `xgboost==2.1.2` |
| Limits of the net | The hook sees Python-level events only; a native library opening its own socket would not be seen. None of the imported libraries is known to do that at import, and nothing connected to anything |

All blocked events were labelled benign only when they matched one of the two exact patterns above; any other would have produced a `BLOCKED` classification. None did. (The first full pass, kept as `u1_results_pass1_superseded.jsonl`, marked those same events as BLOCKED because the benign labelling was incomplete; the underlying outcomes were identical - every import succeeded - and the suite was rerun once with the corrected labels. Only the rerun is cited here.)

## 9. Exact commands and subprocess results

Interpreter for all runs: `C:\Users\Administrator\Desktop\Project\TEST\.venv\Scripts\python.exe`, Python 3.11.9; working directory: repository root; flags `-I -B`; `CUDA_VISIBLE_DEVICES` not set (the backend would not set it); timeout 240 s per run.

```
python -I -B docs/sentiment/r_series/evidence/scripts/u1_run.py                      # 28 runs, all PASS
python -I -B docs/sentiment/r_series/evidence/scripts/u1_run.py --only S3b_flaml --only S3c_autogen --only S3d_agents_debate_module   # 9 runs, all PASS
python -I -B docs/sentiment/r_series/evidence/scripts/u1_control.py                  # poller sensitivity, 40 runs
```

Each run is `python -I -B u1_probe.py --repo <repo> --out <json> --mode instrumented|minimal --linger 2.0 --import <module> ...`. Per-run JSON: `evidence/u1_runs/`; one summary line per run: `evidence/u1_results.jsonl`; console: `evidence/u1_console.txt`; control: `evidence/u1_control_results.jsonl`.

| ID | Runs | Exit codes | Status | `xgboost` imported | NVIDIA module seen |
|---|---|---|---|---|---|
| C0 baseline (no import) | 1 | 0 | PASS | no | no |
| S2A xgboost, instrumented | 3 | 0,0,0 | PASS | yes | no |
| S2B xgboost, minimal | 3 | 0,0,0 | PASS | yes | no (final snapshot only) |
| S3 shap | 3 | 0,0,0 | PASS | no | no |
| S3b flaml | 3 | 0,0,0 | PASS | yes | no |
| S3c autogen | 3 | 0,0,0 | PASS | yes | no |
| S3d agents.debate (module only) | 3 | 0,0,0 | PASS | no | no |
| S4a nodes | 3 | 0,0,0 | PASS | no | no |
| S4b graph | 3 | 0,0,0 | PASS | no | no |
| S4c analysis_service | 3 | 0,0,0 | PASS | no | no |
| S4d lifespan + dependencies | 3 | 0,0,0 | PASS | no | no |
| S4e all routers (no main) | 3 | 0,0,0 | PASS | no | no |
| S4f training.behaviour | 3 | 0,0,0 | PASS | no | no |

Classes recorded: PASS 37; FAIL 0; BLOCKED 0 (after labelling the two benign library patterns); ENVIRONMENT FAILURE 0; NATIVE PROCESS CRASH 0. Every experiment was repeated three times.

## 10. Limitations

1. **Imports only.** Nothing that uses XGBoost was run, as required. The trigger for the R3 fault is XGBoost use, so this investigation cannot show whether a backend process that loaded XGBoost would fault.
2. **No crash information.** The R3 crash cannot be provoked on demand; "no crash in 37 runs" says nothing about its absence in a long-running server.
3. **Model loading not exercised.** `lifespan.warm_model_caches` (which `joblib.load`s `rf_v1.pkl`, the preprocessor and `iforest_v1.pkl` and reads the FAR-Trans CSVs) was deliberately not called: it is startup behaviour, not an import. The pickles were inspected statically only; the `iforest_v1.pkl` opcode scan is partial.
4. **Lazy imports not executed.** The function-level imports of `google.genai` (explanation, Q&A, debate), `autogen` (debate), and `torch`/`transformers` (sentiment, flag off) were not triggered, except `autogen`, which was imported directly in S3c. What those libraries do when *used* is untested.
5. **`wealthpilot.api.main` not imported** (BLOCKED, section 6); the assembled application object was never built.
6. **Instrumentation is Python-level.** The audit hook and poller are Python code; the poller control was done in an idle interpreter; very short or GIL-starved windows during heavy native loads cannot be excluded. The `S2B` runs add no independent DLL evidence.
7. **One machine, one driver (32.0.15.5597), one XGBoost build (2.1.2).** A different driver or wheel could behave differently.
8. **Static analysis can miss dynamic imports** (`importlib`, plugin loading) in third-party libraries; the dynamic runs were meant to cover that for the modules imported.
9. The benign-event labels (`platform` Windows-version probe, `urllib3` IPv6 check) were added after the first pass; both are standard-library/third-party behaviour, but they mean the first pass's `BLOCKED` status is superseded, not that the process behaved differently.

## 11. Open questions

1. Is `agents/debate.py::run_strategy_debate` intended to be wired into the served flow? If it is, `import autogen` brings XGBoost into the server process on first debate call. (Today nothing calls it.)
2. Does *using* a loaded XGBoost in a server process reproduce the R3 fault there? Untested; needs a separately approved, isolated runtime investigation.
3. `sys.modules` and loaded DLLs after a real served request, after `warm_model_caches`, and after a long idle period: **NOT RUN** (Stage 6).
4. Do `xgb_v1.pkl`-style artifacts ever get loaded by any script in `backend/scripts` that operators might run on this machine? (Only `find_demo_risk_candidates.py` loads a model, and it loads `rf_v1.pkl`.)
5. Should the declared dependency on `shap`/`xgboost` for the `wealthpilot` package be separated into a training extra? Not part of this investigation; any dependency change needs approval (`CLAUDE.md` section 5).

## 12. Final exposure classification

**No exposure observed in tested imports.**

- The backend's served import closure (everything `main.py` imports, in six module groups) does not import XGBoost and does not map any NVIDIA module; nothing crashed.
- This is **not** "safe": a latent path exists (`autogen` -> `flaml` -> `xgboost`, reachable only through `run_strategy_debate`, which no backend code calls), use of XGBoost was not tested, model warming and served requests were not run, and `api.main` was not imported.
- It is **not** "confirmed exposure": no run showed the NVIDIA DLL being mapped by anything the backend imports.
- The driver defect is not fixed. R4 remains a machine-specific, test-only mitigation for `tests/training/`; it was not touched, extended or applied to the backend.

Explicit NOT RUN list: `sys.modules` after a served request; DLL state after a served request; live backend behaviour; `warm_model_caches`; any use (fit / predict / DMatrix / Booster) of XGBoost; the debate execution path; `wealthpilot.api.main` import.
