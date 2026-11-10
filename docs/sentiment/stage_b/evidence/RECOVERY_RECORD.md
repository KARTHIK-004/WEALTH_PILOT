# Stage B2.1 recovery record — written BEFORE modifying the project `.venv` (2026-11-04)

Authority: the project owner explicitly authorised modifying the existing application environment for B2.1 (install the Horizon runtime and verify TensorFlow/PyTorch coexistence). Nothing else is authorised: no application integration, no registry or flag change, no `lifespan.py` change, no migration, no database access.

## State recorded before the change (files in this folder)

| File | Content |
| --- | --- |
| `pip_freeze_before.txt` | `pip freeze` of the project `.venv`: 130 lines (129 packages plus the editable `wealthpilot` install) |
| `pip_list_before.json` | `pip list --format=json` |
| `pip_check_before.txt` | `pip check`: "No broken requirements found." (exit 0) |
| `key_versions_before.json` | TensorFlow 2.17.0 (+ tensorflow-intel 2.17.0), Keras 3.15.1, numpy 1.26.4, protobuf 4.25.9, scipy 1.14.1, scikit-learn 1.5.2, ml-dtypes 0.4.1, h5py 3.16.0, flatbuffers 25.12.19, **setuptools 65.5.0**, pip 26.2.2, and the 7 shared packages: anyio 4.15.1, httpx 0.27.2, idna 3.19, markupsafe 3.0.3, packaging 25.0, pyyaml 6.0.2, regex 2026.9.10 |
| `git_status_before.txt` | `git status --short`: 294 entries |
| `dry_run_b2_1.json`, `dry_run_b2_1_output.txt` | the pre-install resolver dry-run against this environment with its own pip |
| `requirements-b2-1-install-set.lock.txt` | the exact 16 hash-pinned packages to be installed |

Interpreter: `C:\Users\Administrator\Desktop\Project\TEST\.venv\Scripts\python.exe`, Python 3.11.9, AMD64, 64-bit, Windows 11; base interpreter `C:\Users\Administrator\AppData\Local\Programs\Python\Python311`. The `.venv` is never deleted, recreated or replaced.

Preserved and re-verified before the change: `docs/sentiment/stage_a/requirements-stage-a.lock.txt` (sha256 `bf3ed520fbb4ceadcc8377f3c8f48d1e7a4b79eb8ad3462580d2ed98794f8eb0`); the model directory `C:\Users\Administrator\.copilot\wealthpilot-approved-models\horizon-multilingual-sentiment-small` (all 8 files match `SHA256SUMS` and the recorded hashes); the isolated Stage A environment is not touched.

## Planned change (the resolver's own proposal, identical to B1's dry-run)

15 NEW packages: `annotated-doc 0.0.5`, `filelock 4.2.8`, `fsspec 2026.9.0`, `hf-xet 1.8.0`, `huggingface-hub 1.33.0`, `jinja2 3.1.6`, `mpmath 1.3.0`, `networkx 3.6.1`, `safetensors 0.8.0`, `shellingham 1.5.4`, `sympy 1.14.0`, `tokenizers 0.23.3`, `torch 2.15.0+cpu`, `transformers 5.17.0`, `typer 0.27.3`.
1 UPGRADE: `setuptools` 65.5.0 -> 84.2.1 (required by torch's declared `setuptools>=77.0.3`). Packages in the application environment that reference `pkg_resources` (found by a scan before the change): `tensorboard`, `werkzeug`, `pytz`, `_pytest`; each is checked after the change.
Not touched by the plan: TensorFlow, Keras, numpy, protobuf, scipy, scikit-learn, ml-dtypes, h5py, flatbuffers and every other existing package (the 19 other packages in the Stage A lock are deliberately NOT installed, so the application keeps its own versions).

## Recovery plan (PROPOSED; NOT executed unless the environment becomes unhealthy and the owner approves)

1. Stop. Preserve all logs. Compare `pip freeze` now with `pip_freeze_before.txt`.
2. Remove only what B2.1 added: `.venv\Scripts\python.exe -m pip uninstall -y annotated-doc filelock fsspec hf-xet huggingface-hub jinja2 mpmath networkx safetensors shellingham sympy tokenizers torch transformers typer`.
3. Restore the one changed package: `.venv\Scripts\python.exe -m pip install "setuptools==65.5.0"` (the pre-change wheel's hash was not recorded; if the exact wheel is required, take it from the same index and compare `pip freeze`).
4. Verify: `pip freeze` must equal `pip_freeze_before.txt` (ignoring the editable `wealthpilot` line's formatting); `pip check` clean; `import tensorflow, keras, numpy`; a targeted test run.
5. Do not blindly downgrade, upgrade or reinstall anything else; never delete or recreate `.venv` without separate approval.
