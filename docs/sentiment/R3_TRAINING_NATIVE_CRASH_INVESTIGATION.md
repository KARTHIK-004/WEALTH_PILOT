# R3 — Investigation of the Intermittent Native Access Violation in `tests/training` (2026-11-07/08)

Written for: the project owner and reviewers. Evidence labels: **VERIFIED** (recorded run output in `docs/sentiment/r_series/evidence/`), **OBSERVED** (seen, not generalised), **INFERENCE** (reasoned, not directly demonstrated), **UNRESOLVED**.

## 1. Conclusion

**Root cause: RESOLVED (established by observation and by a controlled intervention). Mitigation: NOT applied (needs a decision, see section 8).**

- The crash is **not caused by the Transformer installation** and **not by TensorFlow, joblib, PyTorch, the sentiment code or memory pressure.** It also occurs in a reconstruction of the pre-install environment that contains no Transformer package and no `torch` at all.
- It is triggered by **XGBoost 2.1.2**. Its Windows wheel is CUDA-enabled (`xgboost.dll` is 177 MB). The first time XGBoost runs, it probes the CUDA driver even with `CUDA_VISIBLE_DEVICES=-1` and `device="cpu"`. On this machine (hybrid graphics: NVIDIA GeForce MX450, driver 32.0.15.5597, plus Intel Iris Xe) that loads `nvcuda.dll` -> `nvapi64.dll` -> **`nvdxgdmal64.dll`**, and the driver then **unloads `nvdxgdmal64.dll` about 21 ms later**.
- Something in the driver still has a native thread/callback whose entry point is in that DLL. When it later runs (seconds to minutes afterwards, apparently on an asynchronous driver or GPU event) the CPU executes unmapped memory: **`EXCEPTION_ACCESS_VIOLATION` (execute) at `nvdxgdmal64.dll + 0x8080`**, on a non-Python native thread, and the whole process dies with exit code `0xC0000005` (3221225477). Whether it happens in the middle of a long run or at interpreter exit depends only on when that late callback fires, which is why it looks random and why long or slow runs are hit more often.
- **Intervention proof:** keeping `nvdxgdmal64.dll` mapped for the process (one extra `LoadLibrary`, diagnostic only, not applied to the project) removed the crash in 8 of 8 runs, while the same environments without it crashed in 14 of 16.

## 2. What was asked and what was held fixed

Preserve the project `.venv` (it was **not** touched: no install, uninstall or upgrade); no dependency change; no speculative environment variable or downgrade as a fix; no database; no network beyond one `pip download` of the recorded `setuptools==65.5.0` wheel (sha256 `f62ea9da9ed6289bfe868cd6845968a2c854d1427f8548d52cae02a42b4f0356`) into a temporary folder. A request to enable Windows Error Reporting dumps (a machine-wide registry change) was refused by the permission layer and was not worked around; an in-process locator was used instead.

## 3. Comparison environments (outside the repository, `C:\Users\Administrator\.copilot\wealthpilot-r3\`)

| Env | How it was built | Verified |
|---|---|---|
| **envA** (current) | byte-for-byte copy of the project `.venv` (Python 3.11.9) | `pip freeze` equals the project's, line for line |
| **envB** (pre-Transformer reconstruction) | the same copy with the 15 B2.1 packages uninstalled and `setuptools` set back to 65.5.0 | `pip freeze` equals `docs/sentiment/stage_b/evidence/pip_freeze_before.txt` line for line; `pip check` clean |

Limits of the reconstruction: it is exact at package level (every version, including TensorFlow 2.17.0, Keras 3.15.1, XGBoost 2.1.2, joblib 1.6.0, NumPy 1.26.4, SciPy 1.14.1, scikit-learn 1.5.2), but it is a copy-then-uninstall, not a fresh install, and it cannot reproduce the machine's state at the time of the one clean run on 2026-11-04 21:07. A leftover empty `torch/` folder in envB initially made `import torch` succeed as an empty namespace package (found, removed, and the affected rows are flagged below); all conclusions below hold with and without it. Environment snapshot: `r3_environment_snapshot.txt` (versions; relevant environment variables are only `CUDA_VISIBLE_DEVICES=-1`; thread pools: two OpenBLAS builds and `vcomp140.dll`).

## 4. Controlled runs (identical command: `pytest -p netguard -p no:cacheprovider -q tests/training`; raw rows in `r3_results.jsonl`)

Runs 5-8 and the first `probe_1` overlapped with other runs (a stopped shell left its loop running); they are listed but **excluded** from the counts. All other rows were strictly sequential. "Crash" = exit code `0xC0000005` with `Windows fatal exception: access violation`; a crash either aborts the run mid-way (no summary) or occurs after the summary at interpreter exit (all tests had passed).

| Group | Runs | Result |
|---|---|---|
| envA (current), no intervention | rows 1, 3, 9, 11, 13 | **5 of 5 crashed** (3 mid-run; 2 at exit after 774 passed / 1 skipped) |
| envB (no Transformer packages), no intervention | rows 2, 4, 10, 12, 14, 15, 16, 17, 18, `ctl_unpinned_1/2` | **9 of 11 crashed**, 2 passed (735 passed / 3 skipped) |
| envB with the DLL pinned | `pinned_1-4`, `ctl_pinned_1-2` | **0 of 6 crashed** (735 passed / 3 skipped each) |
| envA with the DLL pinned | `ctl_envA_pinned_1-2` | **0 of 2 crashed** (774 passed / 1 skipped each; `torch`, `transformers` imported) |

Interleaved controls (unpinned, pinned, unpinned, pinned in one session on the same machine state): unpinned crashed both times (501 s, 484 s), pinned passed both times (237 s, 211 s). Pinned vs unpinned overall: 0/8 vs 14/16 (Fisher exact test, one-sided p of about 6e-5).

The earlier single clean run before the installation (2026-11-04 21:07, 735 passed) is consistent with this: in envB a run passes about one time in six, so one clean sample was not evidence of absence.

## 5. Where the fault is (locator plugin, `scripts/r3_avprobe.py`)

A first-chance vectored exception handler plus a 20 ms module-list poller was loaded by the runner. Fault records (full logs in `r3_results.jsonl_av/`):

- `envB_avprobe3_1`: `00:15:01.324 LOADED nvdxgdmal64.dll base=0x7ff912050000` -> `00:15:01.345 UNLOADED nvdxgdmal64.dll` -> `00:15:05 tid=29656 python_thread=False fault_at=nvdxgdmal64.dll+0x8080 (unloaded 00:15:01.345) execute target=0x7ff912058080`. The load/unload happened inside `tests/training/risk/test_artifact_roundtrip.py::test_xgboost_wrapper_round_trip`; the process died in the next sklearn test.
- `envB_avprobe_2`: `execute` fault at `0x7ff8d4678080`, again a non-Python thread, again offset `0x8080` in an address range that no module occupied at fault time.

Faulting thread is never a Python thread (faulthandler prints only "Thread ..." lines and no "Current thread"); the fault is an instruction fetch from unmapped memory, which is the signature of a callback into an unloaded DLL.

## 6. Minimal reproducer of the trigger (`scripts/r3_repro.py`, envB)

| Mode | NVIDIA DLLs loaded | `nvdxgdmal64.dll` unloaded |
|---|---|---|
| `xgboost` (fit + predict on random data), 3 runs | yes (`nvcuda`, `nvcuda64`, `nvapi64`, `nvdxgdmal64`) | yes, about 21 ms later |
| `xgboost_cpu_param` (`device="cpu"`, `tree_method="hist"`) | yes | yes |
| `tensorflow` (build, compile, fit a tiny Keras model) | **no** | - |
| `sklearn` (random forest) | **no** | - |
| `numpy` (SVD) | **no** | - |

The three xgboost reproducer processes survived a 20 s wait: the late callback does not fire on demand, so the trigger can be shown but the crash cannot be produced on command. (OBSERVED)

## 7. Hypotheses examined

| Hypothesis | Verdict | Evidence |
|---|---|---|
| Transformer installation / PyTorch | **Rejected as cause** | envB has none and crashes 9/11; crashing processes without `torch` |
| OpenMP runtime conflict (`libiomp5md` + `vcomp140`) | Not the cause of this crash | fault is in an NVIDIA DLL; the pin removes it with all runtimes still present |
| TensorFlow | **Rejected** | TF alone loads no NVIDIA DLL |
| joblib / loky workers | **Rejected** | present in the passing pinned runs too |
| Memory pressure / commit exhaustion | **Rejected** | pinned runs passed with the lowest free memory seen (about 450 MB free physical); one crash run had 4.4 GB free |
| Import order | **Rejected** | not required; XGBoost alone triggers the load |
| Test fixture lifecycle / sentiment code | **Rejected** | the faulting module and the trigger are outside the project code; the crash also occurs in `tests/training/risk` alone |
| Python extension ABI | Not indicated | no Python module at the fault |
| **XGBoost CUDA probe leaving a dangling driver callback** | **Established** | sections 4-6 |

INFERENCE (not demonstrated): what event makes the callback fire (a GPU power-state or display event on this hybrid-graphics laptop is likely, because the delay varies from seconds to minutes and the fault can occur at exit); and that a different driver version would not show it.

## 8. Remaining exposure and options (no change made; each needs a decision)

- **Exposure beyond tests (INFERENCE, corrected 2026-11-10 - see section 11):** the first version of this note said the application's risk model uses XGBoost. A static check of the repository shows the served risk model is the random forest (`models/metrics.json` `best_model: random_forest`; `agents/nodes.py` loads `rf_v1.pkl`), so the backend's exposure is **unresolved**, not inferred. The investigation did not run the API server and does not show a backend crash.
- Options, none applied: (1) update or roll back the NVIDIA driver (hybrid graphics, version 32.0.15.5597); (2) disable the NVIDIA GPU or force the Intel GPU for `python.exe` in Windows graphics settings; (3) replace the CUDA-enabled XGBoost wheel with the CPU-only build (a dependency change that needs approval under `CLAUDE.md` section 5); (4) a test-only guard that holds the DLL mapped, as used in the intervention (works, but hard-codes a driver path and is a workaround rather than a fix, so it was deliberately **not** added to the repository **at that time**; the owner later chose it, and a hardened test-only version was implemented - see section 10).
- Until one is chosen: use `scripts/run_isolated_db_tests.py`/sub-directory runs as before, and treat an exit code `0xC0000005` after "N passed" as this known driver-level fault, not as a test failure.

## 10. Mitigation implemented (owner decision, 2026-11-09): test-only DLL lifetime guard

Written after the owner chose option 4 of section 8 (no driver, GPU-preference, XGBoost or dependency change; no production change).

**Hypothesis (supported by sections 4-6):** the crash is a use-after-unload: the NVIDIA driver unloads `nvdxgdmal64.dll` ~21 ms after XGBoost's CUDA probe while a native callback still points into it. Holding one extra reference keeps the module mapped, so the late callback finds valid code. Evidence it is sufficient: 0 crashes in 8 R3 runs with the DLL held (8 of 8 passed, in two environments) versus 14 of 16 without.

**Implementation (all under `tests/training/`, nothing outside tests):**

- `tests/training/nvidia_dll_guard.py` - class `DllLifetimeGuard` (idempotent, thread-safe `activate()`, `is_retained()`, `release()`), module singleton `SESSION_GUARD`; standard library only (`ctypes` for `LoadLibraryExW` / `FreeLibrary` / `GetModuleHandleExW`). It never calls into the DLL and never touches XGBoost, environment variables (read-only), GPU selection or the driver.
- `tests/training/conftest.py` - activates the session guard at conftest import (before any test module imports XGBoost) and prints its state in the pytest header. Because it lives in `tests/training/`, it applies only to a pytest run that collects the training tests, and only on Windows.
- `tests/training/test_nvidia_dll_guard.py` - 22 tests (+1 skipped: this account cannot create symbolic links) with a fake driver store and fake loader; 2 real-machine tests that skip when the DLL is absent.
- Switches: `WEALTHPILOT_NVIDIA_DLL_GUARD=0` turns it off; `WEALTHPILOT_NVIDIA_DLL_PATH` names an exact file (same validation); `WEALTHPILOT_NVIDIA_DLL_SHA256` pins the hash.

**Trust rules (the DLL is never loaded by bare name):** the file must sit at `<SystemRoot>\System32\DriverStore\FileRepository\nv*.inf_amd64_<16 hex>\nvdxgdmal64.dll`, be a regular file (no symlink or reparse point on the file, its package folder or the store), be non-empty, at most 16 MB, start with `MZ`, and be the only candidate (several installed packages -> `ambiguous_candidates`, guard stays inactive instead of guessing). Missing DLL, non-Windows, a failed load or a hash mismatch leave the guard inactive and visible in the header; none raises. On this machine: one candidate, `nvam.inf_amd64_900a074fe80431cd\nvdxgdmal64.dll`, 596,608 bytes, SHA-256 `6ce2215dda5fcf9c0a3c64bf318b2fa3e7e212142ce3a3eb7961bdf44eea243b`, Authenticode signature Valid (publisher "Microsoft Windows Hardware Compatibility Publisher", checked by hand).

**Lifetime:** one `LoadLibraryExW` reference is kept until the process exits; the session guard is never released during a run. `release()` exists for tests and returns exactly that one reference; a repeated `activate()` returns `already_pinned` without a second load; a second guard object in the same process maps the same module base (verified on the real DLL).

**Results (project `.venv`, `pytest -p netguard tests/training`, strictly sequential and interleaved; rows in `r4_results.jsonl`):**

| Condition | Runs | Process crashes (`0xC0000005`) | Test failures | Result when it did not crash |
|---|---|---|---|---|
| Before: guard off (`WEALTHPILOT_NVIDIA_DLL_GUARD=0`) | 5 | **4** (runs 2, 3, 4, 5) | 0 | 795 passed, 3 skipped (run 1) |
| After: guard on (default) | 5 | **0** | 0 | **796 passed, 2 skipped** in every run, exit code 0 |

Together with R3 (unprotected 14 of 16 crashed): about 18 of 21 unprotected runs crash versus 0 of 5 guarded project-venv runs (and 0 of 8 in the earlier intervention). One-sided Fisher exact p for this series alone: 5/126 = 0.04. All sub-directories pass individually after the change (behaviour 13, expense 10, portfolio 12, market 51, risk 13, sentiment 675 passed / 1 skipped) and `tests/training/test_nvidia_dll_guard.py` gives 22 passed / 1 skipped. The suite totals one more file than before because of the 22 + 1 guard tests (795/796 passed versus 774 earlier counted in envA). No contaminated or overlapping run is counted: each row started after the previous one had ended.

**Production isolation (VERIFIED):** `pip freeze` is unchanged (XGBoost 2.1.2; the only textual difference is a byte-order mark on the first line); no file under `backend/`, `scripts/`, `training/`, `config/` or `models/` mentions the guard (enforced by a test); the risk model and agents were not touched; `SENTIMENT_TRANSFORMERS_ENABLED=false` and `SENTIMENT_MODEL_ENABLED=false`; production sentiment stays `user_text_rules_v1`; Horizon stays a research-only candidate. Git: three new untracked files (`tests/training/conftest.py`, `nvidia_dll_guard.py`, `test_nvidia_dll_guard.py`); nothing committed or pushed.

**Why it is test-only:** it works around a defect in a third-party driver component that only affects processes that run XGBoost on this kind of machine. Putting a DLL pin in the application would change production process behaviour (hard-coded driver path, an extra driver reference in a server process) for a problem that has not been shown to occur there. If the backend turns out to be affected, the supported fixes remain the driver update, forcing the Intel GPU, or the CPU-only XGBoost wheel (a dependency change needing approval).

**Limitations:** it is a workaround, not a fix of the cause; it assumes the late callback belongs to `nvdxgdmal64.dll` (true for both captured faults, but a different driver version could involve another component); it is inert when more than one NVIDIA driver package is installed unless the path is named; it does not verify the DLL signature in code; it only protects pytest runs that collect `tests/training/` (other suites that run XGBoost, e.g. under `tests/backend/`, are not covered and were not part of this task); 5+5 runs is a modest sample, which is why the R3 numbers are quoted alongside.

## 11. Unresolved investigation item U1 - backend XGBoost exposure (opened 2026-11-10)

R4 (section 10) is treated as an established baseline: it is a machine-specific, test-only mitigation, not proof that the NVIDIA driver defect is fixed, and it does not cover the backend. Nothing in this section changes it.

**Question:** can a running backend process load XGBoost, and so trigger the CUDA probe and the late `nvdxgdmal64.dll` fault, on a machine with this driver?

**Static findings (VERIFIED by reading the repository on 2026-11-10; no code was executed, no server started, no database touched):**

| Fact | Where |
|---|---|
| Served risk model is the random forest, not XGBoost | `models/metrics.json` `risk.best_model = "random_forest"`; `backend/wealthpilot/agents/nodes.py:179-180` loads `preprocessor_v1.pkl` and `rf_v1.pkl` |
| `xgb_v1.pkl` exists as a trained comparison artifact only | `models/risk/xgb_v1.pkl`; no backend reference |
| No backend module imports `xgboost` | no match under `backend/**/*.py` |
| The only `training.*` imports in `backend/wealthpilot` are `training.behaviour.common` and `training.behaviour.detection` | `nodes.py:340,360-361`; `training/behaviour/common.py` imports only numpy, pandas, sklearn and `wealthpilot.data.acquisition` |
| `import xgboost` appears only in training code | `training/risk/common.py:26`, `training/risk/xgboost_model.py:30`, `training/market/common.py:164` (inside a function) |
| Startup only `joblib.load`s existing artifacts | `backend/wealthpilot/api/lifespan.py` |

**Reading (INFERENCE, not demonstrated):** the documented serving path does not appear to import XGBoost, so the backend is probably **not** exposed through the risk model. This is a static conclusion only.

**Still open (NOT checked - each needs a separate, owner-scoped step):**

1. Dynamic confirmation that `xgboost` is absent from `sys.modules` (and `nvdxgdmal64.dll` is never mapped) after the API app has started and served an analysis request. Not done: it requires importing/running the application, and any run must be offline with no development database.
2. Whether a transitive import (for example `shap`, if the explanation path uses it, or any optional-dependency probe) pulls `xgboost` in at runtime. Not traced.
3. Whether `import xgboost` alone, without fitting or predicting, triggers the DLL load. R3 only showed that fit + predict does (section 6).
4. Whether the Transformer research adapters or any other loaded native library (`torch`, `onnxruntime`) interact with the same driver component. Not examined and not suggested by any evidence.
5. Any other suite outside `tests/training/` that imports XGBoost is unguarded (for example tests that import `training.risk`).

**U1 outcome (2026-11-10, read-only; full detail `r_series/U1_BACKEND_XGBOOST_RUNTIME_EXPOSURE_REPORT.md`):** items 2 and 3 above were investigated with fresh-subprocess import tests (37 runs, all exit 0). The backend's served import closure (all routers, lifespan, errors, sse, `agents.nodes/graph`, `analysis_service`, `training.behaviour`) does **not** import `xgboost`; `import shap` does not; `import xgboost` alone mapped **no** NVIDIA module (items 3). A latent path was found for item 2: `import autogen`/`import flaml` imports `xgboost` (`autogen/oai/client.py:9` -> `flaml/__init__.py:5` -> `flaml/automl/ml.py:12`), reachable only through `agents/debate.py::run_strategy_debate`, which no backend code calls. Items 1, 4 and the use of XGBoost remain NOT RUN. Classification: **no exposure observed in tested imports** - not "safe", not "confirmed exposure"; the driver defect is not fixed.

**Boundaries kept:** no change to XGBoost, the NVIDIA driver, GPU selection, dependencies or any production module; the guard is not applied to the backend. If item 1 or 2 shows XGBoost is loaded in a server process, the supported options remain those in section 8 and need an owner decision.

## 9. Reproducing and cleaning up

Scripts: `docs/sentiment/r_series/evidence/scripts/` (`r3_runner.py`, `r3_avprobe.py`, `r3_pin.py`, `r3_repro.py`, `r3_series_*.sh`). The two comparison environments (about 3.2 GB each) remain at `C:\Users\Administrator\.copilot\wealthpilot-r3\` for follow-up; deleting that folder removes them. The project `.venv`, the repository code, `requirements` and the registry were not changed by R3.
