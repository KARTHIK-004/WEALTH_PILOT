# Stage B2.1 — Horizon runtime installed in the application environment; STOPPED at a stop condition

Written for: the project owner, who must decide how to proceed. Date: 2026-11-04.
Evidence labels: **VERIFIED** (recorded command output), **OBSERVED** (seen, not established as general), **UNRESOLVED**, **NOT RUN** (planned in the brief, not executed because of the stop), **NOT AUTHORIZED**.
All evidence files are in `docs/sentiment/stage_b/evidence/`.

## 1. Executive Summary

**Status: STOPPED. The runtime was installed exactly as specified, the environment is otherwise healthy, but the installation broke part of an installed package and contradicted a constraint the project had already recorded, so I stopped before the coexistence tests and made no further change.**

- **VERIFIED:** the 16 specified packages were installed into the project `.venv` from hash-pinned wheels (exit 0). `pip check`: clean. TensorFlow 2.17.0, Keras 3.15.1, NumPy 1.26.4, protobuf 4.25.9, SciPy 1.14.1, scikit-learn 1.5.2 and the 7 shared packages are unchanged. Every package of the application stack, TensorFlow, PyTorch, transformers, safetensors and `wealthpilot.api.main` import successfully.
- **VERIFIED (the problem):** the specified `setuptools` 84.2.1 **no longer ships `pkg_resources`** (it was importable under 65.5.0). Three `tensorboard` modules do an unguarded `import pkg_resources` and now fail: `tensorboard.default`, `tensorboard.data.server_ingester` and `tensorboard.program` (TensorBoard's server and plugin loading). `tensorboard.summary` still imports. The project does not use TensorBoard (searched), so I found no effect on the application, but a part of an installed TensorFlow dependency is broken.
- **VERIFIED (provenance):** the project had **already recorded this constraint**: `reports/sentiment_consolidated_approval_form.md` (line 247) states that `tensorboard` 2.17.1 imports `pkg_resources`, which `setuptools` 82 or later no longer ships, "so the project environment must stay below 82", and the owner had approved **`setuptools==81.0.0`**. My B1 report took `setuptools` 84.2.1 from the resolver's "latest" choice and listed its effect only as an unresolved risk; I did not find the recorded answer. **That was my miss in B1, and this brief then specified 84.2.1.** I executed that specification faithfully, and it is the cause.
- **NOT RUN (stopped):** the TensorFlow/PyTorch import-order tests, the existing TensorFlow market model test, the Horizon model test, sequential inference, the resource measurements, and the targeted tests (sections 5-9). **TensorFlow/PyTorch coexistence is therefore still UNRESOLVED**, with one small OBSERVED data point (section 5).
- **Not touched:** production, registry, flags, `api/lifespan.py`, database (no access, no `neondb`), Gemini, model files, schemas.

**Recommended next step (needs your approval, because it departs from the specified plan):** change exactly one package, `setuptools` 84.2.1 -> **81.0.0** (the previously approved pin; torch needs `>=77.0.3`, so it is satisfied), verify, then run the coexistence tests. Details in section 11.

## 2. Environment Before Installation (VERIFIED; `RECOVERY_RECORD.md`, `pip_freeze_before.txt`, `key_versions_before.json`)

`C:\Users\Administrator\Desktop\Project\TEST\.venv\Scripts\python.exe`; Python 3.11.9, AMD64, 64-bit, Windows 11; base interpreter `...\Python311`; pip 26.2.2; 130 `pip freeze` lines (129 packages and the editable `wealthpilot` install); `pip check` clean; TensorFlow 2.17.0 (+ tensorflow-intel 2.17.0), Keras 3.15.1, NumPy 1.26.4, protobuf 4.25.9, SciPy 1.14.1, scikit-learn 1.5.2, ml-dtypes 0.4.1, h5py 3.16.0, flatbuffers 25.12.19, **setuptools 65.5.0**; the 7 shared packages anyio 4.15.1, httpx 0.27.2, idna 3.19, markupsafe 3.0.3, packaging 25.0, pyyaml 6.0.2, regex 2026.9.10. Git status: 294 entries. The Stage A lock (sha256 `bf3ed520...f8eb0`) and the model directory (all 8 files) were re-verified before the change.

## 3. Approved Dependency Changes (VERIFIED; `dry_run_b2_1.json`, `requirements-b2-1-install-set.lock.txt`, `install_output.txt`)

The resolver dry-run with the project's own pip (26.2.2) proposed **the same 16 packages, versions and wheel hashes as B1's dry-run**, and every entry equals the Stage A lock's version and SHA-256. It did not touch TensorFlow, Keras, NumPy, protobuf, SciPy, scikit-learn or any other protected package, so no stop condition fired at that point. The 19 other Stage A lock packages were deliberately **not** installed (that would have moved the 7 shared packages).

Installed with `pip install --require-hashes --no-deps --only-binary=:all: -r requirements-b2-1-install-set.lock.txt --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple` (exit 0, 149 s): 15 new packages: `annotated-doc 0.0.5`, `filelock 4.2.8`, `fsspec 2026.9.0`, `hf-xet 1.8.0`, `huggingface-hub 1.33.0`, `jinja2 3.1.6`, `mpmath 1.3.0`, `networkx 3.6.1`, `safetensors 0.8.0`, `shellingham 1.5.4`, `sympy 1.14.0`, `tokenizers 0.23.3`, `torch 2.15.0+cpu` (from `download-r2.pytorch.org`), `transformers 5.17.0`, `typer 0.27.3`; and one upgrade: **`setuptools` 65.5.0 -> 84.2.1** (named in the brief).

## 4. Environment After Installation (VERIFIED; `pip_check_after.txt`, `pip_freeze_diff.txt`, `post_install_imports.json`)

- `pip check`: **No broken requirements found.** (It cannot see the TensorBoard problem, because `tensorboard` does not declare an upper bound on `setuptools`.)
- Freeze diff: 15 added lines, 0 removed; the `pip list` comparison shows exactly one changed existing package (`setuptools`); no package removed.
- Protected versions unchanged: tensorflow 2.17.0, keras 3.15.1, numpy 1.26.4, protobuf 4.25.9, scipy 1.14.1, scikit-learn 1.5.2, ml-dtypes 0.4.1, h5py 3.16.0, flatbuffers 25.12.19, anyio, httpx, idna, markupsafe, packaging, pyyaml, regex.
- Imports that succeeded in one process (`CUDA_VISIBLE_DEVICES=-1`): numpy, scipy, pandas, sklearn, xgboost, statsmodels, numba, shap, arch, yaml, regex, packaging, httpx, anyio, setuptools 84.2.1, tensorboard 2.17.1, werkzeug, pytz, pytest 8.3.3, tokenizers 0.23.3, safetensors 0.8.0, huggingface_hub 1.33.0, transformers 5.17.0, torch 2.15.0+cpu (CUDA available: no, 4 default CPU threads, built without CUDA), tensorflow 2.17.0 (devices: CPU only), keras 3.15.1, `wealthpilot.api.main`.
- **Failed:** `import pkg_resources` -> `ModuleNotFoundError` (section 10).

## 5. TensorFlow/PyTorch Import-Order Tests — NOT RUN

The designed tests (both import orders, tensor operations, repeated operations, thread counts, DLL and OpenMP inspection, memory and time) were **not run**. One incidental data point, **OBSERVED only**: in the post-install import check, `torch` (via `transformers`) was imported first and then `tensorflow` in the same process; both imported without an exception, TensorFlow listed only a CPU device, and the only messages were TensorFlow's usual oneDNN notice and an unrelated LangChain deprecation warning. No tensor operation, repeat, memory or native-library inspection was done, so this is **not** a coexistence result.

## 6. Existing TensorFlow Model Test — NOT RUN

## 7. Horizon Model Test — NOT RUN

## 8. Sequential Inference Results — NOT RUN

## 9. Memory and Performance Measurements — NOT RUN

Reference values from earlier phases (not B2.1 measurements): Horizon alone peaked at 1,139.7 MB after load (Stage A, isolated environment); the application imports at about 215 MB and the first TensorFlow import reaches about 344 MB (B1). The combined in-process figure remains unmeasured.

## 10. Failures and Compatibility Issues

### 10.1 `setuptools` 84.2.1 removes `pkg_resources` and breaks TensorBoard modules — VERIFIED

| Item | Finding |
| --- | --- |
| What broke | `tensorboard.default`, `tensorboard.data.server_ingester`, `tensorboard.program` raise `ModuleNotFoundError: No module named 'pkg_resources'` (`tensorboard_pkg_resources_check.txt`) |
| What still works | `tensorboard.summary` imports; TensorFlow and Keras import; the three other files that reference `pkg_resources` are guarded or conditional (`werkzeug`, `pytz`, `_pytest`), and `pytest` 8.3.3 imports |
| Impact on WealthPilot | none found: searching `backend`, `training`, `scripts`, `tests` and `pyproject.toml` finds no TensorBoard use and no `pkg_resources` import by the project. Unused-by-the-project is the extent of the evidence; I did not run the training scripts |
| Root cause | the version choice, not the installation mechanism. `setuptools` 82 and later no longer ship `pkg_resources` |
| Recorded constraint | `reports/sentiment_consolidated_approval_form.md` line 247: the project environment must stay below 82; owner-approved pin `setuptools==81.0.0` (also recorded in its S1 approval items). The index offers 81.0.0 (and 80.10.2 and others below 82) |
| Why `pip check` missed it | `tensorboard` declares no `setuptools` upper bound |
| Declared requirements that must all hold | `torch` needs `setuptools>=77.0.3`; `tensorboard`, `tensorflow-intel` and `torch` all list `setuptools`; the compatible window is therefore `>=77.0.3` and `<82`, and the previously approved 81.0.0 is inside it |

### 10.2 What did not go wrong

No TensorFlow, Keras, NumPy or protobuf change; no resolver conflict; no import failure of TensorFlow, PyTorch, transformers, safetensors or the application.

## 11. Recovery Information (nothing below has been executed; `RECOVERY_RECORD.md` has the full record)

| Option | Action | Effect | My view |
| --- | --- | --- | --- |
| **A. One-package correction (recommended; needs your approval)** | `.venv\Scripts\python.exe -m pip install --no-deps --only-binary=:all: "setuptools==81.0.0"` (hash-pinned once the wheel's digest is read from the index and compared with the previously recorded S1 list), then verify: `pip check`, `import pkg_resources`, `import tensorboard.default`, `tensorboard.program`, `torch` and `tensorflow` imports | restores `pkg_resources`; keeps all 15 new packages; torch's `>=77.0.3` is satisfied | resolves the issue with a single change to the previously approved pin; departs from the 84.2.1 your brief named, hence the need for your approval |
| B. Accept 84.2.1 | none | TensorBoard server and plugin loading stay unavailable (unused by the project); contradicts the recorded constraint | not recommended |
| C. Roll back | `pip uninstall -y annotated-doc filelock fsspec hf-xet huggingface-hub jinja2 mpmath networkx safetensors shellingham sympy tokenizers torch transformers typer`, then `pip install "setuptools==65.5.0"`; verify `pip freeze` equals `pip_freeze_before.txt` | returns to the exact pre-B2.1 state | available if you prefer; also needs your approval |

`.venv` is never deleted or recreated. No broad upgrade or downgrade is proposed.

## 12. Production Isolation Verification (VERIFIED after the installation)

Production sentiment method `user_text_rules_v1`; `sentiment_model_enabled` False; `sentiment_transformers_enabled` False; registry unchanged (FinBERT and Twitter-RoBERTa, both gated off, no runnable candidate; Horizon not in it); 12 key source files hashed and identical to the start of B1 (the registry, the six other `core/sentiment` modules, `settings.py`, `.env.example`, `schemas.py`, the insight service and the generated `api.ts`; no source file changed), and `api/lifespan.py` unmodified; `api/lifespan.py` unmodified, Horizon not added to start-up warming; no migration; no database access (no test run, no connection), no `neondb`; no Gemini call; no model download (the only model directory is the existing Stage A one, re-verified against `SHA256SUMS`); no process left running. One factual change: `sentiment_model.dependencies_available()` now returns **True** (it only reports that the packages import; every feature stays disabled), so the status endpoint's `dependencies_available` field would now read true.

## 13. Changed Files and Git Status

- **Environment (outside Git):** the project `.venv`: 15 packages added and `setuptools` upgraded (section 3).
- **Repository, created:** `docs/sentiment/stage_b/STAGE_B2_1_RUNTIME_COEXISTENCE_REPORT.md` (this file) and the evidence folder `docs/sentiment/stage_b/evidence/` (recovery record, before/after freeze, check and list files, freeze diff, dry-run report and output, hashed 16-package install set, install output, post-install import results and script, TensorBoard check, source hashes, git status before and after).
- **Repository, modified:** a correction note appended to `docs/sentiment/stage_b/STAGE_B1_RUNTIME_READINESS_REPORT.md` (my B1 miss) and one line in `docs/MEMORY.md`.
- **Git status:** 294 entries before and after (identical diff); the new files sit inside already-untracked folders. Nothing committed or pushed. No pre-existing file was reverted or overwritten.
- **Not changed:** any source code, test, fixture, setting, schema, migration, the registry, `api/lifespan.py`.

## 14. Recommendation: In-process or Out-of-process

**Cannot be decided from B2.1; the decisive test did not run.** What B2.1 does establish: the packages install cleanly beside TensorFlow without moving any protected package, and both libraries import in one process (OBSERVED, once). The one real incompatibility found is the `setuptools` window (`>=77.0.3` for torch, `<82` for TensorBoard), which is satisfiable. My B1 lean is unchanged and still conditional: in-process behind the section 10 guards of the B1 report if the coexistence tests (not yet run) pass, an out-of-process worker if they show any TensorFlow/PyTorch native-library conflict, instability or unacceptable memory.

## 15. B2.1 Verdict

**INCOMPLETE: stopped at a stop condition ("existing functionality breaks"; an unexpected side effect of a specified dependency change).** The installation itself succeeded and is hash-verified; the application environment is healthy by `pip check` and by every import except `pkg_resources`; TensorFlow/PyTorch coexistence, the market-model test, the Horizon load, sequential inference and the resource measurements were **not run**. The cause is traceable to my B1 report, which did not find the project's own recorded `setuptools<82` constraint. **B2.2 was not started.** Waiting for your decision between options A, B and C (section 11).

## 16. Addendum (2026-11-05): recovery executed, coexistence tests completed — supersedes sections 5-9, 14 and 15

**Written for: the project owner. Sections 1-15 above are left intact as the record of the stopped state; this addendum records what happened after your approval.**

**Recovery (VERIFIED; `evidence/RECOVERY_RECORD.md`, `recovery_install_output.txt`, `recovery_import_check.txt`, `tensorboard_pkg_resources_check.txt`, `pip_*_after_recovery.*`).** Exactly one package changed: `setuptools` 84.2.1 -> **81.0.0** (hash-pinned wheel `fdd925d5c5d9f62e4b74b30d6dd7828ce236fd6ed998a08d81de62ce5a6310d6`; resolver dry-run first). `pip check`: clean. `pkg_resources` imports again and `tensorboard.default`, `tensorboard.data.server_ingester` and `tensorboard.program` import. TensorFlow 2.17.0, Keras 3.15.1, NumPy 1.26.4, protobuf 4.25.9 and every other package are unchanged. No model inference, model loading or production activation was performed as part of the recovery itself.

**Authority for the coexistence tests.** Reading: the B2.1 brief already authorised modifying the project `.venv` and running the coexistence tests, and the stop was caused only by the setuptools defect that you then approved fixing; the tests need no new package, no model placement in the repository, no registry change and no inference through the application. They were therefore run as a continuation of B2.1, loading Horizon only from the Stage A directory outside the repository, in throwaway processes. If you read the scope differently, the evidence is in `evidence/coexist_*.json` and can be disregarded.

**Results (VERIFIED, one Windows 11 machine, 8 logical CPUs, CPU only; OBSERVED values are not benchmarks).**

| Test | TensorFlow first | PyTorch first |
|---|---|---|
| Both libraries import and run in one process | pass | pass |
| Existing TensorFlow market model loads and predicts (input `(None, 20, 1)`) | pass, 0.16 s | pass, 0.07 s |
| Horizon loads offline from local safetensors (140,642,691 parameters; labels negative/neutral/positive) | pass, 3.62 s | pass, 3.27 s |
| 31 sequential rounds of both models | outputs bitwise identical every round | bitwise identical every round |
| Horizon logits vs the Stage A run | **identical (max abs diff 0.0)** | identical |
| Market forecast vs its first call after both are loaded | unchanged | unchanged |
| Median latency: market model / Horizon | 78.8 ms / 24.6 ms | 75.4 ms / 23.7 ms |
| Peak process memory (application baseline 216 MB) | 1573 MB | 1332 MB |
| Network attempts | 0 | 0 |

Import-order tests also passed (`coexist_import_*.json`); two OpenMP runtimes load in one process (`libiomp5md.dll`, `vcomp140.dll`) without error in either order (OBSERVED). The default thread counts were torch 4/4 and TensorFlow 0/0 (let the library decide). The application backend does not import TensorFlow at runtime (the `.keras` models are offline-training artifacts), so the combination exists only in these test processes.

**Recommendation (updates section 14).** In-process inference is viable behind the guards implemented under ADR-055 (non-loading status, per-candidate non-blocking load lock, timeout and circuit breaker, optional thread cap), with these caveats: memory of about 1.3-1.6 GB peak when both libraries are present, a synchronous first load of about 3-4 s, and no real-weights run through the application's adapter yet. An out-of-process worker is not needed on this evidence and remains the fallback if the adapter smoke test or production load shows otherwise.

**Verdict (updates section 15).** B2.1 COMPLETE for its stated scope: runtime installed, environment healthy, coexistence VERIFIED in both import orders. **Not done and not authorised:** B2.2, Horizon registration, placing model files in the repository, production activation.

**Unrelated observation made afterwards (UNRESOLVED).** An intermittent native `access violation` aborted some full `pytest tests/training` runs (TensorFlow / xgboost / joblib test processes; in the crashing risk-test process `torch` was not imported). Sub-directories pass on re-run and one run before the installation was clean, so a connection to this installation is neither shown nor excluded; see `SENTIMENT_TEST_REPORT.md`.

**Update 2026-11-09 (R3): the crash is explained and is NOT connected to this installation.** A reconstruction of the pre-install environment (no Transformer packages, `setuptools` 65.5.0, `pip freeze` identical to the recorded one) crashes in 9 of 11 runs; the cause is the CUDA-enabled XGBoost wheel loading and then unloading the NVIDIA driver DLL `nvdxgdmal64.dll`, after which a late driver callback executes unmapped code. Holding that DLL mapped removed the crash in 8 of 8 runs, including with `torch` and `transformers` imported. Details and options: `docs/sentiment/R3_TRAINING_NATIVE_CRASH_INVESTIGATION.md`. The coexistence results above are unaffected.
