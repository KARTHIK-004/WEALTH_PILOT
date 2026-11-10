# Sentiment model — owner approval record and gate result (2026-10-26)

Written for: the project owner. This record answers the brief "proceed with the approval and isolated compatibility phase only after recording explicit owner decisions for every unresolved item".

## Gate result at the first brief (2026-10-26): **BLOCKED — nothing was executed** (superseded in part by the decisions recorded below)

The brief authorises the isolated compatibility phase only after an explicit owner decision is recorded for each required item. **The brief itself contains no decision on any item** (it describes what to do once decisions exist), and the approval checklist (`reports/sentiment_transformer_dependency_request.md`, section F) holds 15 UNRESOLVED items and one APPROVED item (keep intensity regression deferred). Silence is not approval, so all 14 required items below are **UNRESOLVED** and the stop rule applies:

- no package was installed and no virtual environment was created;
- no model weights and no dataset were downloaded or looked up;
- no statement was collected or generated;
- no runtime code, configuration, dependency manifest or production method was changed;
- the rules baseline `user_text_rules_v1` is active, `SENTIMENT_MODEL_ENABLED=false`, and ADR-050 / ADR-052 remain accurate.

## Decisions recorded 2026-10-26 (second brief) — the gate is partly open

The owner recorded **R1, R2, R3 and R4 APPROVED** (exact versions, `torch` CPU-only) and **R5 APPROVED for isolated verification only**; **R6–R14 remain UNRESOLVED and were not changed**. The approval covers only the isolated dependency compatibility phase, with this scope: a disposable virtual environment outside the repository at `C:\Users\Administrator\.copilot\sentiment-compatibility-venv`; downloading and installing only the four exact versions (and the transitive dependencies pip must resolve for them) from the configured Python package index with pip; PyPI project metadata and the OSV database as the advisory sources; no change to `backend/pyproject.toml`, requirements files, application code, configuration or production environments; no model weights, tokenizer files, datasets or Hugging Face assets; no model revision queried or selected; no statement collected, generated or labelled; `SENTIMENT_MODEL_ENABLED` not enabled; no training and no production inference. If an install fails, a package is unavailable, an advisory is unresolved or compatibility cannot be verified, stop and report; no version is substituted. The results are recorded in the section "Isolated compatibility results" below.

## Decision recorded 2026-10-26 (third brief) — A1 REJECTED for the original pins; installation BLOCKED

Written for the project owner. **A1 (risk acceptance for the published advisories at `torch==2.6.0` and `transformers==4.57.1`) is REJECTED.** Installation of those two pins stays blocked. The owner opened a security-remediation and version-selection phase only: no package was installed or downloaded, no model weight, tokenizer, dataset or Hugging Face asset was touched, no model revision was queried, no runtime code or configuration changed, and the Transformer stays disabled. **R6 to R14 remain UNRESOLVED.** Replacement versions are listed as **candidates only**; each needs explicit owner approval, recorded here as new item **A2 (UNRESOLVED)**. No production behaviour changed. Full evidence, the 29-CVE advisory register and the hash tables are in section J of `reports/sentiment_transformer_dependency_request.md`.

### Status of the gate

| Id | Item | State |
| --- | --- | --- |
| R1 `torch==2.6.0`, R2 `transformers==4.57.1` | Approved by the owner earlier | Recorded as approved, but **not executable**: installing them is blocked by the rejection of A1 |
| R3 `tokenizers==0.22.1`, R4 `safetensors==0.6.2` | APPROVED | Unchanged; no OSV record for either; compatible with the S1 to S3 candidates |
| R5 Python 3.11 / Windows CPU | APPROVED for isolated verification only | Resolution verified by metadata; install-time verification still not run |
| R6 to R14 | UNRESOLVED | Unchanged |
| A1 | **REJECTED** for the original pins | The owner, third brief |
| A2 (new) | Approve exact replacement versions (and the `transformers` 4.x to 5.x major-version move) | **UNRESOLVED**; candidates S1 to S4 below; none selected |

### Security decision matrix

**1. Verified facts** (PyPI project metadata, OSV, and the source files read on 2026-10-26)

| Fact | Evidence |
| --- | --- |
| The two approved pins carry 36 OSV records = 29 distinct CVEs by OSV's per-version query (`torch` 22 CVEs in 24 records, `transformers` 7 CVEs in 12 records); none withdrawn. **Corrected in the fourth brief: `torch==2.6.0` has 24 CVEs in 32 records, so at least 31 CVEs with `transformers`, plus one official-only advisory** | OSV per-version lookup; PyPI `vulnerabilities` field |
| `torch` has no OSV record from **2.13.0** (2.13.0, 2.14.0, 2.14.1); 2.6.0 to 2.12.1 all have at least one | OSV for all 13 releases |
| `transformers` **4.x never reaches zero** (4.57.1: 12 records, 4.57.2 to 4.57.6: 11 each); zero from **5.10.1**; 5.10.0 is clean but **yanked** (unstable main-branch push) | OSV for all 44 releases, PyPI yank flag and reason |
| Every candidate release has a Windows `cp311` / `abi3` / pure-Python wheel on the configured index and none is yanked; Python 3.11 accepted | PyPI JSON |
| `transformers` 5.10.1 to 5.12.1 accept `tokenizers==0.22.1` and `safetensors==0.6.2` (R3 and R4 unchanged) | transformers `requires_dist` |
| Windows `torch` declares no CUDA / `nvidia-*` / `triton` dependency (Linux markers only) | PyPI `requires_dist` |
| The runtime loader forces `local_files_only=True`, `trust_remote_code=False`, `use_safetensors=True`, CPU, a confined path and per-file SHA-256; the training loader sets none of the first three and has no `revision`; no `Trainer`, `torch.compile`, `torch.load` or `pickle` in the sentiment code; `save_pretrained` is used | Source read (`sentiment_model.py:258-259`, `train_sentiment_transformer.py:122-123,155-156`) and grep |
| Metadata-only reverse check of the 133 installed distributions finds no unsatisfied requirement for any candidate set; the only existing package that must change is `setuptools` (65.5.0 to at least 77.0.3) | My own metadata resolver, **not pip** |
| All wheel SHA-256 values for S1 to S4 are recorded; all resolved packages have zero OSV and PyPI records | Section J.4 |

**2. Candidate proposals (not selected; each needs explicit owner approval)**

| Set | `torch` | `transformers` | `tokenizers` | `safetensors` | Approvals changed |
| --- | --- | --- | --- | --- | --- |
| S1 (smallest change) | 2.13.0 | 5.12.1 | 0.22.1 | 0.6.2 | R1, R2 |
| S2 | 2.13.0 | 5.10.1 | 0.22.1 | 0.6.2 | R1, R2 |
| S3 | 2.14.1 | 5.12.1 | 0.22.1 | 0.6.2 | R1, R2 |
| S4 (latest) | 2.14.1 | 5.20.2 | 0.23.3 | 0.8.0 | R1 to R4 |

Other zero-record releases in the same ranges (`torch` 2.14.0; `transformers` 5.10.2, 5.10.4, 5.11.0, 5.12.0) are possible too. Any compliant `transformers` candidate is a major-version move that R2 did not approve.

**3. Applicability judgments** (my reading of the advisory text; not a decision, not a security review)

| Question | Judgment |
| --- | --- |
| Does `trust_remote_code=False` mitigate CVE-2026-4372? | **No, as described**: the advisory says it bypasses that setting (fixed in `transformers` 5.3.0) |
| Does `local_files_only=True` mitigate it? | **Not established** (not stated by the advisory; fix not read) |
| Does safetensors-only loading prevent the unsafe-loading advisories? | It covers the pickle / `.pth` / `.pt2` ones **on the runtime path**; it does not cover config-driven code loading, nested-config overrides or file writes, and **the training path does not use it** |
| Does the training path use `Trainer`, `torch.compile`, pickle or an affected loader? | No to all four; **yes to `save_pretrained`** (CVE-2026-9856) |
| Applicable to offline CPU inference? | Original pins: **only CVE-2026-4372 is not shown to be mitigated**; the rest are in code the repository does not call, or need a pickle / `.pt2` file the loader refuses. Candidates: none listed |
| Applicable to training or optional APIs only? | `save_pretrained`, the pickle fallback when a base model lacks safetensors, `Trainer`, `torch.compile`, `torch.jit`, quantisation, generation, model-specific loaders |

**4. Unresolved questions** (detail in section J.6)

- U1: no record is not proof; the candidates are 4 weeks to 5 months old, the fixes were not independently reviewed, and the owner has not stated a soak or review rule.
- U2: whether `local_files_only` or a missing `kernels` package blocks CVE-2026-4372 on the original pins.
- U3: OSV records for CVE-2026-5241 and several torch records disagree on affected versions.
- U4: whether the two call sites work on `transformers` 5.x (no runtime test).
- U5: CPU-only behaviour, `numpy 1.26.4` and TensorFlow 2.17 + PyTorch coexistence at runtime.
- U6: effect of upgrading `setuptools` in the project environment.
- U7: **unrelated, pre-existing:** the project environment's `certifi 2026.7.22` has two advisories (fixed in 2026.10.18); not fixed here; to be resolved before any Hub download.
- U8: owner decisions on A2, the 4.x to 5.x move, a soak rule and the new `torch` licence expression.
- U9: the other 133 installed distributions were not advisory-checked.

### Commands and sources in this phase (all read-only)

Read: `reports/sentiment_model_approval_record.md`, `reports/sentiment_transformer_dependency_request.md`, `backend/wealthpilot/core/sentiment_model.py`, `training/sentiment/README.md`, `training/sentiment/train_sentiment_transformer.py`, `backend/pyproject.toml`; `grep` for `Trainer`, `torch.compile`, `torch.load`, `pickle`, `from_pretrained`, `trust_remote_code`, `local_files_only`, `use_safetensors`, `save_pretrained` and related names under `backend/wealthpilot`, `training/sentiment` and `scripts`. Network (metadata only, public package names and versions): `https://pypi.org/pypi/<package>/json` and `/<version>/json` for `torch`, `transformers`, TensorFlow 2.17.0 and every package in the candidate sets, and `https://api.osv.dev/v1/querybatch` and `/v1/vulns/<id>`. Local read-only: `importlib.metadata` dump of the project `.venv` (133 distributions). Scripts live in the session scratchpad, outside the repository; they download no wheel and install nothing. `pip` was not run in this phase.

### Tests

Only the existing documentation and model-safety tests were run, after the documents were updated, in the project environment (which still has no `torch`, `transformers`, `tokenizers` or `safetensors`, and still has `setuptools` 65.5.0, TensorFlow 2.17.0 and numpy 1.26.4): `tests/backend/scripts/test_dry_run_package*.py`, `test_regression_tests_are_effective.py`, `tests/backend/core/test_user_text_pilot_pack.py`, `test_sentiment_model.py`, `test_user_text_model_policy.py` and `tests/training/sentiment`: **260 passed, 2 skipped** (the skips were not investigated). No database test was run.

### Confirmations

No package was installed or downloaded; no model weight, tokenizer, dataset or Hugging Face asset was accessed; no model revision was queried; `backend/pyproject.toml`, requirements files, runtime code, configuration and production environments are unchanged; `SENTIMENT_MODEL_ENABLED` is not enabled; `user_text_rules_v1` remains the active method; sentiment still cannot affect risk, goals, portfolio, recommendations, compliance or any financial calculation; no raw user text was logged, stored, cached, sent or placed on-chain; intensity regression stays deferred.

## Review recorded 2026-10-26 (fourth brief) — read-only review of candidate sets S1 to S4; A2 remained UNRESOLVED at the time (superseded on 2026-10-27: A2 APPROVED for isolated verification only, set S1 — see the fifth-brief section)

Written for the project owner. The owner asked for a read-only security, licensing and compatibility review of S1 to S4 and **did not approve A2**. **States unchanged: A1 REJECTED for `torch==2.6.0` and `transformers==4.57.1`; A2 UNRESOLVED; R6 to R14 UNRESOLVED; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; intensity regression deferred; installation BLOCKED.** Nothing was installed, resolved with pip, downloaded or executed; no model weight, tokenizer file, dataset or Hugging Face asset was touched; no model revision was queried; no runtime code, training code, manifest or configuration changed. Full evidence is in section K of `reports/sentiment_transformer_dependency_request.md`. Labels: VERIFIED FACT, VERIFIED FROM OFFICIAL SOURCE, PRELIMINARY APPLICABILITY ASSESSMENT, CANDIDATE PROPOSAL, UNRESOLVED.

### Candidate comparison

| Criterion | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- |
| Pins (torch / transformers / tokenizers / safetensors) | 2.13.0 / 5.12.1 / 0.22.1 / 0.6.2 | 2.13.0 / 5.10.1 / 0.22.1 / 0.6.2 | 2.14.1 / 5.12.1 / 0.22.1 / 0.6.2 | 2.14.1 / 5.20.2 / 0.23.3 / 0.8.0 |
| Exists on PyPI, none yanked; Windows CPython 3.11 / pure-Python wheel; Python 3.11 accepted (VERIFIED FACT) | yes | yes | yes | yes |
| CUDA / NVIDIA dependency active on Windows (VERIFIED FACT) | none (7 declared, all Linux-only) | none | none | none |
| OSV records listing the pinned versions; PyPI `vulnerabilities`; upstream advisory lists (VERIFIED FACT / OFFICIAL SOURCE) | 0 / 0 / none list these versions | 0 | 0 | 0 |
| Approvals changed | R1, R2 | R1, R2 | R1, R2 | R1 to R4 |
| Age in days, torch / transformers / tokenizers / safetensors (VERIFIED FACT) | 110 / 133 / 402 / 444 | 110 / 145 / 402 / 444 | 26 / 133 / 402 / 444 | 26 / 7 / 17 / 139 |
| Source change needed at the two call sites (PRELIMINARY) | training script, `save_pretrained(safe_serialization=True)` | same | same | same, plus tokenizer-truncation and safetensors-reader changes to review |
| numpy 1.26.4 / TensorFlow 2.17.0 at metadata level (VERIFIED FACT) | compatible; runtime unverified | same | same | same |

### Licence findings

All four direct packages are permissive: `transformers`, `tokenizers`, `safetensors` Apache-2.0 (the upstream `LICENSE` files of the last two were read); `torch` declares `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT` with 107 (2.13.0) or 95 (2.14.1) licence files, against `BSD-3-Clause` for 2.6.0. PyTorch's own `pyproject.toml` explains it (VERIFIED FROM OFFICIAL SOURCE): "The main Pytorch project license is BSD-3-Clause. The SPDX license expression below reflects installed pytorch packages"; the 2.13.0 notes say the build adopted PEP 639 `license-files`. So it is a fuller declaration of bundled third-party components, not a change of PyTorch's licence. **PRELIMINARY ASSESSMENT (not legal advice): no licensing concern identified** — every licence is permissive and OSI-approved, none is copyleft or non-commercial, the project does not redistribute `torch`; obligations (keep notices, Apache-2.0 notice and patent terms) arise only if a bundle is ever redistributed. UNRESOLVED: which licence files actually ship in the Windows CPU wheel. The transitive closure has no GPL, LGPL or AGPL; `tqdm` and `certifi` are MPL-2.0 (already installed). The model licences (R6 to R8, non-commercial and share-alike) are the real licensing risk and are untouched.

### Advisory applicability findings

- **Correction (VERIFIED FACT):** the original `torch==2.6.0` pin has 24 CVEs in 32 records, not 22 in 24 (OSV's per-version query missed nine records with non-standard version strings), plus one official-only advisory that OSV lacks (GHSA-2rj9-7h5r-q4h8); with `transformers` that is at least 31 CVEs. The rejection of A1 stands.
- **No OSV record, in any of the 99 ever filed for `torch` and `transformers`, lists any candidate version** (two cross-checks); `tokenizers` and `safetensors` have none; the PyPI `vulnerabilities` field is empty for the candidates; the `transformers` repository publishes no advisories of its own and PyTorch's five official advisories do not list 2.13.0 or 2.14.x (VERIFIED FROM OFFICIAL SOURCE).
- **CVE-2026-4372:** `trust_remote_code=False` does **not** mitigate it (the advisory says it bypasses that setting); `local_files_only=True` is **not established** as a mitigation (the advisory is silent and the fix commit does not use it); the fix sanitises two private config keys and restricts kernels to the `kernels-community` repository; fixed in 5.3.0, so not applicable by version to S1 to S4 (fix completeness UNRESOLVED).
- **Safetensors-only loading** addresses the pickle, `.pth` and `.pt2` advisories on the runtime path (PyTorch's policy recommends it); it does not address config-driven code loading, and **the training loader has neither `use_safetensors=True` nor a pinned revision** (VERIFIED FACT, code).
- **Current training script:** uses `save_pretrained` (CVE-2026-9856; fixed from 5.10.1); does not use `Trainer`, `torch.compile`, `torch.load`, pickle, `.pt` or `.pt2`.
- **Six torch records have no fixed version** ("affected <= 2.6.0, patched None"): reporters tested old versions, so "no record for 2.13+" is not a confirmed fix; all six are in code the repository does not call. PyTorch's policy: operator crashes and local denial of service are ordinary bugs, and **fixes are not backported**, so any pinned torch needs recurring advisory re-checks.

### Release-age analysis

S1 and S2: youngest direct package 110 days; S3: `torch` 26 days; S4: `transformers` 7 days, `tokenizers` 17 days, `huggingface-hub` 2.3.0 three days. Advisories for these libraries surfaced a median of 74 days (`transformers`, 7 CVEs) and 60.5 days (`torch`, 22 CVEs) after the affected release, and most after more than 30 days (rough, small sample). **PRELIMINARY ASSESSMENT:** a maturity window alone is a weak control; it helps against yanked or unstable releases. **CANDIDATE PROPOSAL (owner decision):** a project policy should require a window together with a hash-pinned lock, a same-day OSV / PyPI / upstream advisory check, no yanked release and recurring re-checks; starting values to decide: 90 days for direct and 30 days for transitive packages. Under those values S1 and S2 pass for direct packages, S3 and S4 do not; some young transitive packages (`filelock` 7 days, `hf-xet` and `typer` 20 days) would need exact older pins, whose existence was not checked.

### `setuptools` and `certifi`

`torch` 2.13+ needs `setuptools>=77.0.3` (project: 65.5.0). The setuptools changelog shows `pkg_resources` removed in v82.0.0, and `tensorboard/default.py`, which TensorFlow 2.17 requires, imports it unconditionally: **PRELIMINARY: setuptools 82 or newer would break that import; CANDIDATE PROPOSAL: constrain `setuptools>=77.0.3,<82`** in any environment holding `torch`; a project-environment change needs its own approval. `certifi 2026.7.22` in the project is affected by GHSA-6q48-6c7w-9gw2 (Critical, CVSS 9.1; compromised emSign intermediates): **use 2026.10.19 or later** (2026.10.18 removed all emSign roots); no installed dependent sets an upper bound; the project's `pip 26.2.1` vendors the affected `certifi 2026.6.17` (a `pip` 26.2.2 exists; whether it is fixed is UNRESOLVED). Not fixed here; needs its own task before any Hugging Face download.

### Static call-site review against transformers 5.x (nothing run)

Required source change: the training script's `model.save_pretrained(directory, safe_serialization=True)` (the official migration guide says the parameter "has been removed"; VERIFIED FROM OFFICIAL SOURCE + VERIFIED FACT). Not mentioned by the guide, so UNRESOLVED: the runtime and training `from_pretrained` keywords (`local_files_only`, `trust_remote_code`, `use_safetensors`, `num_labels`, `id2label`, `label2id`, `ignore_mismatched_sizes`), `set_seed`, `get_linear_schedule_with_warmup`, offline tokenizer loading and whether `accelerate` is needed. No version gate exists in `dependencies_available()` / `check_environment()`, and no existing test exercises these calls (a fake trainer is used).

### Recommendation

**The evidence supports a ranking, not an approval.** Security does not separate the four sets. **S1 is the most defensible candidate to take into isolated verification, conditionally; S4 should be excluded for now; S3 buys nothing over S1; S2 differs from S1 only by an earlier `transformers` patch.** A2 remains UNRESOLVED and installation remains blocked pending the owner's decision. S1 is not shown to be safe: releases are 3.5 to 4.5 months old, fixes were not independently reviewed, and the `transformers` 4.x to 5.x move has never been run against this project's code.

### Unresolved questions

N1 torch with numpy 1.26.4 and TensorFlow + PyTorch coexistence at runtime; N2 licence files actually shipped in the Windows wheel; N3 whether the no-fix torch records persist in 2.13 / 2.14; N4 completeness of the CVE-2026-4372 fix and the effect of the missing `kernels` package; N5 transformers 5.x keyword, `accelerate` and offline-tokenizer behaviour; N6 whether anything imports `tensorboard.default`; N7 `pip` 26.2.2 vendored `certifi` and project endpoints' chains; N8 existence of older transitive releases under a maturity rule; N9 the maturity rule and who re-checks advisories; N10 a second advisory source (OSV lacks two official PyTorch advisories; `transformers` publishes none); N11 R6 to R14 untouched.

### Exact owner decision required before an isolated installation (not recorded; A2 stays UNRESOLVED)

> I approve A2 for **isolated verification only**: `torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2` (set S1), with transitive packages fixed by a hash-pinned list prepared and checked on the day of installation, installed with pip from the configured package index into a disposable virtual environment outside the repository, with `setuptools>=77.0.3,<82`, and removed afterwards unless I say otherwise. I accept, for this verification only: the `transformers` 4.x to 5.x major-version move; the `torch` licence expression in section K.3; and the maturity rule `[direct packages >= N days, transitive packages >= M days, no yanked release, no OSV / PyPI / upstream advisory on the day]` with N = ___ and M = ___. I understand that the isolated test may show the project's two call sites need code changes, that those changes, any production use, any weight or dataset access, R6 to R14 and activation remain separate approvals, that the project environment (including `setuptools` and `certifi`) is not changed by this approval, and that the unrelated `certifi` advisory needs its own task before any Hugging Face download.

### Tests

Only the existing documentation and model-safety tests were run, after the documents were updated: `tests/backend/scripts/test_dry_run_package*.py`, `test_regression_tests_are_effective.py`, `tests/backend/core/test_user_text_pilot_pack.py`, `test_sentiment_model.py`, `test_user_text_model_policy.py` and `tests/training/sentiment`: **260 passed, 2 skipped** (the skips were not investigated). No file under `backend/`, `training/`, `tests/`, `config/` or the dependency manifests was modified in this phase (checked by modification time). The project environment is unchanged (no `torch`, `transformers`, `tokenizers` or `safetensors`; `setuptools` 65.5.0, `certifi` 2026.7.22, TensorFlow 2.17.0, numpy 1.26.4). No database test was run.

### Commands and sources (all read-only)

Read: the two reports, `backend/wealthpilot/core/sentiment_model.py`, `training/sentiment/train_sentiment_transformer.py`, `training/sentiment/artifacts.py`, `training/sentiment/README.md`, `backend/pyproject.toml`; `grep` over `backend/wealthpilot` and `training/sentiment`; static scan of the project `.venv` `site-packages` for `pkg_resources` imports; `importlib.metadata` dump of the 133 installed distributions. Network, metadata only: PyPI project JSON and the wheels' PEP 658 `.metadata` text files; OSV `/v1/query`, `/v1/querybatch`, `/v1/vulns`; GitHub pages of the upstream projects (security advisories and lists, `SECURITY.md`, release notes, `MIGRATION_GUIDE_V5.md`, PyTorch `pyproject.toml` and `requirements.txt`, two `LICENSE` files, one fix commit referenced by the CVE-2026-4372 advisory); the setuptools changelog. No wheel was downloaded; no `huggingface.co` page, model, tokenizer or dataset was requested; `pip` was not run. Scripts are in the session scratchpad, outside the repository.

## Decisions recorded 2026-10-27 (fifth brief) — A2 APPROVED for isolated verification only, set S1

**Recorded before any environment was created or any package installed.** The owner supplied the following decisions in the brief that opens the isolated compatibility validation phase; they are recorded here as given.

| Id | Decision |
| --- | --- |
| A1 | **REJECTED** for `torch==2.6.0` and `transformers==4.57.1` (unchanged) |
| A2 | **APPROVED for isolated verification only, set S1:** `torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2` |
| R1 / R2 | **APPROVED only as replaced by the S1 set** (`torch==2.13.0`, `transformers==5.12.1`); the earlier `torch==2.6.0` / `transformers==4.57.1` approvals stay non-executable |
| R3 / R4 | **REMAIN APPROVED** as `tokenizers==0.22.1` / `safetensors==0.6.2` |
| R5 | **APPROVED for isolated verification only** |
| R6 to R14 | **UNRESOLVED**, not to be changed by this phase |

**A2 includes (conditions, as given):** a disposable virtual environment outside the repository at `C:\Users\Administrator\.copilot\sentiment-compatibility-venv`; a hash-pinned dependency list checked on install day; `setuptools>=77.0.3,<82`; no change to the project environment or to runtime code; no model weights, datasets, tokenizer downloads or Hugging Face access; no production activation; no training or inference; no change to `certifi` outside the approval note; no change to the active method, which remains `user_text_rules_v1` with `SENTIMENT_MODEL_ENABLED=false`.

**Scope of the phase (as given):** create the disposable Python 3.11 environment and confirm the interpreter, pip and free disk; install only the exact S1 pins into it; use pip's hash and metadata checks and record wheel hashes, file sizes, transitive dependencies, licences and advisories; verify Python 3.11 compatibility, Windows CPU wheel availability, absence of a CUDA / NVIDIA dependency on the Windows wheel, imports of `torch`, `transformers`, `tokenizers` and `safetensors`, CPU-only `torch`, a minimal tokenizer / safetensors smoke test without downloading a model, TensorFlow + PyTorch coexistence in a separate process if possible, and `pip check` with metadata consistency. No change to `backend/pyproject.toml` or application code; the model loader and model artifacts stay disabled; no weights, tokenizers or datasets are downloaded; the project `certifi` issue is not touched. Only this record, `reports/sentiment_transformer_dependency_request.md` and `docs/MEMORY.md` are updated.

**Points the brief does not state, and how this phase treats them** (recorded so they are not read as decisions):

- The maturity-rule values N and M proposed in section K.8 were **not** set. No age rule is enforced; this phase reports the age of every pinned package. Whether to adopt a rule remains an owner decision.
- The `transformers` 4.x to 5.x move is part of the S1 pins and is therefore approved for this verification only; the licence expression of `torch` (section K.3) was not separately addressed and is reported, not accepted for any other purpose.
- `numpy==1.26.4` is used as a **constraint** in the disposable environment (it is the project's pinned version and TensorFlow 2.17.0 requires numpy below 2.0); it is a transitive requirement of `transformers`, not an added direct dependency. The two constraints in the disposable environment are therefore `setuptools>=77.0.3,<82` and `numpy==1.26.4`.
- "No training or inference": this phase runs no model forward pass and loads no model, including no stand-in model. Library checks are limited to imports, version and build attributes, signature introspection, a tokenizer built from an in-memory vocabulary, a safetensors file round trip, and CPU tensor arithmetic.
- No activation decision is made from this phase. R6 to R14 and every dataset, weight and revision step remain separate approvals.

**State of the gate after this record:** installation of the S1 pins into the disposable environment only is authorised. Everything else remains blocked. The results are recorded in the section "Isolated compatibility validation results (S1)" below once the phase has run.

## Isolated compatibility validation results (S1) — 2026-10-27: completed; one flagged advisory finding on a transitive build tool

Written for the project owner. The phase ran after the A2 decision above was recorded. Full evidence, the 35-row hash table and the static findings are in section L of `reports/sentiment_transformer_dependency_request.md`.

### Updated decision matrix

| Id | State | Result of this phase |
| --- | --- | --- |
| A1 | **REJECTED** for `torch==2.6.0` and `transformers==4.57.1` | unchanged |
| A2 | **APPROVED for isolated verification only, set S1** | executed: `torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2` installed and verified in a disposable environment, since deleted |
| R1 / R2 | APPROVED only as replaced by `torch==2.13.0` / `transformers==5.12.1` | wheels installed and verified on Windows CPython 3.11.9; no OSV, PyPI or upstream advisory lists them on 2026-10-27 |
| R3 / R4 | APPROVED as `tokenizers==0.22.1` / `safetensors==0.6.2` | installed and verified; no advisory |
| R5 | APPROVED for isolated verification only | **Python 3.11 and Windows CPU verified** (L.6); `torch` reports `2.13.0+cpu`, no CUDA |
| R6 to R14 | **UNRESOLVED** | untouched; no weight, tokenizer or dataset step is possible |
| New: setuptools advisory handling | **UNRESOLVED when written; on 2026-10-27 (sixth brief) the owner accepted `setuptools==81.0.0` and the two advisories as residual risks for the isolated Windows pip-only environment only** | every `setuptools` release inside the approved `>=77.0.3,<82` range is listed for two advisories (see below) |

### Commands executed (all against the disposable environment or read-only)

`python --version` and platform on the base interpreter; `df -h`; `pip config list` (empty); environment-variable check for `PIP_*`, `HF_*`, `TRANSFORMERS_*`, `PYTHONPATH` (none); `python -m venv C:\Users\Administrator\.copilot\sentiment-compatibility-venv`; `pip install --dry-run --ignore-installed --disable-pip-version-check -c constraints.txt -r s1_direct.txt --report resolve_s1.json` (constraints: `setuptools>=77.0.3,<82`, `numpy==1.26.4`); a script that cross-checks every pinned wheel against PyPI JSON and OSV; OSV lookups for the `setuptools` advisories; the upstream advisory pages of `pytorch/pytorch` and `huggingface/transformers`; `pip download --only-binary=:all: --no-deps --require-hashes -r pins_s1.txt -d wheels`; an independent SHA-256 of all 35 files; `pip freeze --all` before and after; `pip install --no-index --find-links wheels --only-binary=:all: --no-deps --require-hashes -r pins_s1.txt`; `pip check`; a metadata audit script; an offline smoke script (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, scratch `HF_HOME`); a signature-introspection script; a numpy-bridge script; four coexistence processes (`coexist.py`, both import orders, from both interpreters); static reads of the installed `transformers/modeling_utils.py`; a check that no file in the project environment or repository changed; the documentation and model-safety tests; deletion of the environment. All scripts live in the session scratchpad, outside the repository.

### Environment and wheel results (VERIFIED FACT)

Python 3.11.9 (AMD64), Windows 10.0.26300, pip 24.0, 161 GB free, default PyPI index. **35 wheels, 170.3 MB**, resolved by pip with **no conflict**, every wheel hash equal to PyPI's published digest (35 of 35), none yanked; installed with `--require-hashes` (pip's own check) and hashed again independently. **Installed size 852.8 MB** (`torch` 524 MB). `pip check`: "No broken requirements found." Installed metadata equals the pinned list.

### Transitive packages and licences

31 transitive packages. Compared with the project environment, 15 of the 35 packages are not installed there today: the four direct packages and `annotated-doc`, `filelock`, `fsspec`, `hf-xet`, `huggingface_hub` 1.33.0, `Jinja2`, `mpmath`, `networkx`, `shellingham`, `sympy`, `typer`. All permissive: MIT, BSD, Apache-2.0, ISC, PSF-2.0; MPL-2.0 for `certifi` and `tqdm`; no GPL, LGPL or AGPL. `torch` declares `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT` and **all 107 declared licence files ship in the Windows wheel**. No licensing concern identified (preliminary, not legal advice).

### Security and advisory findings and their applicability

- **None** for `torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2` or the other 31 packages, in OSV or the PyPI vulnerabilities field, on 2026-10-27; upstream lists unchanged (PyTorch 5 advisories, newest 2026-01-26, none lists 2.13.0; `transformers` 0).
- **One finding, `setuptools==81.0.0`** (the highest release inside the owner's approved range, installed because the conditions specify that range): GHSA-h35f-9h28-mq5c = CVE-2026-59890 = PYSEC-2026-3447 (Moderate; `MANIFEST.in` exclusion bypass in a source distribution on macOS APFS / HFS+; fixed in 83.0.0) and GHSA-xmj3-9gf7-h52w (Low; Windows path escape in setuptools' legacy egg-style wheel installation; fixed in 84.1.0; published 2026-10-23). **PRELIMINARY ASSESSMENT: neither applies here** (Windows, no sdist built, wheels installed by pip's installer, disposable environment, since deleted). Every release from 77.0.3 to 81.0.0 is affected, so the approved range has no clean release; releases 84.1.0 and newer are outside both advisories by OSV's ranges but also remove `pkg_resources`, which the project's `tensorboard` imports. I proceeded under the literal condition and am flagging the conflict; **the owner decides** whether to accept these two advisories as inapplicable to disposable environments or to amend the bound for them (for example `setuptools>=84.1.0`) before any further install.
- The project's `certifi 2026.7.22` and `pip 26.2.1` advisory (section K.6) was not touched.

### Compatibility and TensorFlow coexistence (VERIFIED FACT)

- Python 3.11 and the Windows CPU wheel are compatible; `torch.__version__` is `2.13.0+cpu`, `torch.version.cuda` is `None`, `torch.cuda.is_available()` is `False`, the build reports `USE_CUDA=0`, `torch/lib` holds nine DLLs and none is CUDA or NVIDIA; seven `cuda-*` / `nvidia-*` / `triton` requirements are declared for Linux only and none is active on Windows.
- Imports of `torch`, `transformers`, `tokenizers`, `safetensors` (and `huggingface_hub`, `numpy 1.26.4`) work offline; an in-memory `tokenizers` WordLevel tokenizer, a safetensors round trip, CPU tensor arithmetic and the `torch`-`numpy` bridge all work; nothing was fetched or cached.
- **TensorFlow 2.17.0 + Keras 3.15.1 and PyTorch 2.13.0+cpu coexist in one process in both import orders, from both environments' interpreters: four of four runs passed** with no errors or warnings (working set about 520 to 530 MB with both loaded).
- Static findings on the installed `transformers` 5.12.1 (PRELIMINARY; section L.7): the five names the code imports exist with matching signatures; `use_safetensors=True` on a directory with only a pickle checkpoint raises `OSError`, so the loader's refusal of pickle weights holds; `save_pretrained(..., safe_serialization=True)` silently ignores the keyword (no crash, but a dead argument the migration guide says was removed); the hub branch can start a background Hub conversion request for pickle checkpoints unless offline. No model was built or loaded, so the runtime behaviour of the two call sites is **still UNRESOLVED**.

### Blocked items

- The setuptools decision above.
- Runtime verification of `from_pretrained` / `save_pretrained` / the offline tokenizer load, which needs a stand-in model; A2 excluded any model or inference.
- Everything that needs R6 to R14: model weights, tokenizer downloads, datasets, annotation, metrics, activation.
- The unrelated project `certifi` / `pip` advisory, the possible `setuptools<82` need in the project environment (N6), and the code changes the static review points to (training script `safe_serialization`, `use_safetensors=True`, revision pinning, offline conversion switch, README) — all separate tasks.

### Safeguards confirmed

No file in the project `.venv`, `backend/`, `training/`, `tests/`, `config/`, `scripts/`, `models/`, `datasets/` or the dependency manifests changed; the project environment still has no `torch`, `transformers`, `tokenizers` or `safetensors`; `models/sentiment` and `datasets/raw/sentiment` do not exist; `user_text_rules_v1` is active, `SENTIMENT_MODEL_ENABLED=false`, the Transformer is disabled, sentiment cannot affect risk, goals, portfolio, recommendations, compliance or financial calculations; no raw user text was used, logged, persisted, cached, sent or placed on-chain (only fixed synthetic words were processed); no intensity regression; no activation decision is made from this phase.

### Tests

Only the existing documentation and model-safety tests were run in the project environment, after the documents were updated: `tests/backend/scripts/test_dry_run_package*.py`, `test_regression_tests_are_effective.py`, `tests/backend/core/test_user_text_pilot_pack.py`, `test_sentiment_model.py`, `test_user_text_model_policy.py` and `tests/training/sentiment`: **260 passed, 2 skipped** (the skips were not investigated). No database test was run. The project environment still has no `torch`, `transformers`, `tokenizers` or `safetensors` (`setuptools` 65.5.0, `certifi` 2026.7.22, TensorFlow 2.17.0, numpy 1.26.4).

### Cleanup

The environment `C:\Users\Administrator\.copilot\sentiment-compatibility-venv` (903 MB), the 35 downloaded wheels and the scratch pip cache were deleted after the results were recorded. Reproduction commands are in section L.10.

## Decisions recorded 2026-10-27 (sixth brief) — setuptools residual risk accepted for the isolated environment; one stand-in test authorised

**Recorded before any environment was created or any package installed.** The owner resolved the S1 compatibility blocker with the following decisions, recorded as given.

### setuptools decision and residual-risk scope

- **A2 remains APPROVED only for isolated verification** (set S1).
- **`setuptools==81.0.0` is accepted for the disposable Windows pip-only environment.**
- **GHSA-h35f-9h28-mq5c** (= CVE-2026-59890 = PYSEC-2026-3447; `MANIFEST.in` exclusion bypass in source distributions on macOS APFS / HFS+; fixed in 83.0.0) **and GHSA-xmj3-9gf7-h52w** (Windows path escape in setuptools' legacy egg-style wheel installation; fixed in 84.1.0) **are recorded as ACCEPTED RESIDUAL RISKS for this isolated environment only.** (The owner's brief wrote the second identifier as "GHSA-xmj3-9gf7-h52"; the advisory identifier is GHSA-xmj3-9gf7-h52w, and that is what is recorded.)
- **The acceptance rests on the documented scope, and applies only while all of it holds:** a Windows CPython 3.11 virtual environment; installation of wheels with pip only; no source distributions built or installed; no macOS execution; no legacy egg installation; the environment deleted after testing.
- **This is a risk acceptance, not a finding that the advisories are fixed or irrelevant.** Both stay open and unresolved for any other environment, any other `setuptools` use and any other platform. Nothing here changes the project environment, `backend/pyproject.toml`, requirements files or production configuration, and neither `certifi` nor `pip` is modified.

### Decisions kept unchanged

A1 **REJECTED** for `torch==2.6.0` and `transformers==4.57.1`; A2 **APPROVED only for S1 isolated verification**; R6 to R14 **UNRESOLVED**; `user_text_rules_v1` remains the active production method; `SENTIMENT_MODEL_ENABLED=false`; no model weights, Hugging Face assets, datasets or user text; intensity regression remains deferred.

### One additional isolated stand-in test, authorised (scope as given)

- A **new disposable virtual environment** outside the repository, with the exact S1 pins reinstalled: `torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2`, `setuptools==81.0.0`, `numpy==1.26.4`, from a **fully hash-pinned local wheel set**. No access to Hugging Face, the Hub, external model repositories or datasets; no pretrained weights; no project model artifact created or modified.
- A **tiny randomly initialised local classifier** built with the installed Transformers library, driven by fixed synthetic token IDs only. The test must exercise the loader's exact keyword arguments and verify `local_files_only=True`, `trust_remote_code=False` and `use_safetensors=True`; load only a locally generated safetensors model; run one CPU forward pass and check the output shape and finite logits; verify that no network request and no Hugging Face cache access occurs; verify that no pickle, `.pt` or `.pt2` artifact is created or accepted; test the current tokenizer-loading call path with a locally created tokenizer fixture only; and test the current training call path statically or with a minimal stand-in, especially `save_pretrained`, the obsolete `safe_serialization=True` argument and any 5.x-compatible replacement the training seam needs.
- **No silent code rewrite.** If a current call site fails under Transformers 5.12.1, the test stops at that point, reports the exact failure, identifies the smallest required source change, leaves the repository unchanged and requests a separate approval for code changes.
- Only the stand-in compatibility and model-safety tests are run: no training, no real inference, no browser tests, no database tests, no production flows. The environment, wheels and cache are deleted afterwards unless retention is explicitly required for reproducibility.
- Only this record, `reports/sentiment_transformer_dependency_request.md` and `docs/MEMORY.md` are updated.

**State of the gate after this record:** the stand-in test in a new disposable environment is authorised. Everything else remains blocked. Results are recorded in the section "Stand-in compatibility test results (S1)" below once the test has run.

## Stand-in compatibility test results (S1) — 2026-10-27: 19 of 19 checks passed; no current call site failed; code changes recommended, not applied

Written for the project owner. Evidence, per-check results and the exact edits are in section M of `reports/sentiment_transformer_dependency_request.md`.

### Decisions in force (unchanged by this test)

A1 **REJECTED** for `torch==2.6.0` and `transformers==4.57.1`; A2 **APPROVED only for S1 isolated verification**; `setuptools==81.0.0` and GHSA-h35f-9h28-mq5c / GHSA-xmj3-9gf7-h52w **accepted as residual risks for the isolated Windows pip-only environment only** (not fixed, not irrelevant elsewhere); R6 to R14 **UNRESOLVED**; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; intensity regression deferred. **No model weight, tokenizer download, dataset, Hugging Face asset or user text was accessed**; the stand-in model was random-initialised locally and the only inputs were fixed synthetic token ids and synthetic words.

### Environment, commands and package hashes

New disposable venv `C:\Users\Administrator\.copilot\sentiment-compatibility-venv` (Python 3.11.9, pip 24.0). Commands: `python -m venv`; an install-day re-check (PyPI JSON digests, OSV, PyPI vulnerability field) on the recorded pip resolution (35 packages, 0 hash mismatches, 0 yanked, only the two accepted `setuptools` advisories); `diff` of the new hash-pinned list against the first run's (**identical**, so the 35-row table in section L applies); `pip download --only-binary=:all: --no-deps --require-hashes -r pins_s1.txt -d wheels`; an independent SHA-256 of all 35 files (35 of 35 equal); `pip install --no-index --find-links wheels --only-binary=:all: --no-deps --require-hashes -r pins_s1.txt`; `pip check` ("No broken requirements found"); `standin_test.py` (19 checks) plus two side probes (`control_probe.py`, `lfo_probe.py`) and a tokenizer probe, all run with `-B` and offline switches; a repository check by modification time; deletion. Hashes of the required pins (all 35 are in section L):

| Package | Wheel | Size | SHA-256 |
| --- | --- | --- | --- |
| `torch==2.13.0` | `torch-2.13.0-cp311-cp311-win_amd64.whl` | 122.0 MB | `a0d8b11f16a48d60e2015d8213aa0390744cbebb98e58b62b3514dddc656e330` |
| `transformers==5.12.1` | `transformers-5.12.1-py3-none-any.whl` | 11.2 MB | `2a5e109d2021265df7098ffbb738295acaf5ad256f12cbc586db2ea4dcbb1a8a` |
| `tokenizers==0.22.1` | `tokenizers-0.22.1-cp39-abi3-win_amd64.whl` | 2.7 MB | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` |
| `safetensors==0.6.2` | `safetensors-0.6.2-cp38-abi3-win_amd64.whl` | 0.3 MB | `c7b214870df923cbc1593c3faee16bec59ea462758699bd3fee399d00aac072c` |
| `setuptools==81.0.0` | `setuptools-81.0.0-py3-none-any.whl` | 1.1 MB | `fdd925d5c5d9f62e4b74b30d6dd7828ce236fd6ed998a08d81de62ce5a6310d6` |
| `numpy==1.26.4` | `numpy-1.26.4-cp311-cp311-win_amd64.whl` | 15.8 MB | `cd25bcecc4974d09257ffcd1f098ee778f7834c3ad767fe5db785be9a4aa9cb2` |

### Stand-in model and tokenizer results (VERIFIED FACT)

- A random-initialised tiny BERT classifier (4,035 parameters, seed 42; labels `positive, negative, neutral`) saved with `save_pretrained` is **`config.json` + `model.safetensors` only**; no `.bin`, `.pt`, `.pth`, `.pt2` or pickle file was created.
- Loaded with the loader's exact call (`local_files_only=True`, `trust_remote_code=False`, `use_safetensors=True`): CPU, one forward pass on fixed ids `[[2, 5, 6, 7, 3]]`, logits shape `(1, 3)`, finite, deterministic, and equal to the in-memory model it was saved from.
- Tokenizer: a hand-written legacy BERT directory (`vocab.txt` + `tokenizer_config.json` + `special_tokens_map.json`) loads through the loader's tokenizer call with 25 tokens and exact ids; truncation and `return_tensors="pt"` work; `save_pretrained` writes `tokenizer.json` + `tokenizer_config.json` and the reloaded tokenizer is identical. A `tokenizers`-built fast tokenizer also works.

### Loader and 5.x call-site results (VERIFIED FACT)

- **Runtime loader (`sentiment_model.py:258-259`) works unchanged under transformers 5.12.1.** The real `TransformersBackend`, `verify_artifact`, `TrainedSentimentModel` and `load_model` behave as designed on the stand-in: `load_model` refuses it as `not_validated` (an unvalidated model is never primary), an artifact without `model.safetensors` is refused as `artifact_incompatible`, a pickle-only or `.pt` / `.pth` / `.pt2`-only directory is refused (`load_failed` / `OSError`), `torch.load` was never called.
- **`use_safetensors=True`** refuses pickle-style weights; **`trust_remote_code=False`** ignores `auto_map` and never executes local custom model or tokenizer code (a control in its own process shows `True` would execute it and would also write into the Hugging Face modules cache); **`local_files_only=True`** is forwarded to the hub layer (control `False` differs) and means cache-only resolution; a local config carrying `_attn_implementation_internal` naming a synthetic Hub repository is loaded without applying the key and without any network or hub-level attempt.
- **Training seam (`train_sentiment_transformer.py:116-158`) runs unchanged**: the real `fine_tune_with_torch` was called with `epochs=0` (no optimiser step) against a local base directory, with every call as written, **including `model.save_pretrained(directory, safe_serialization=True)`**. The keyword is accepted silently and has no effect: saving with no keyword, `True` and `False` writes byte-identical `model.safetensors`. The artifact it wrote passes the project's own `write_artifact` / `verify_artifact`, and the tokenizer it wrote reloads with the same vocabulary. Not run: a real base model, a real download, a real size mismatch, a real training loop.

### Network and cache safety results (VERIFIED FACT)

0 refused network attempts across imports and all checks (an independent guard on every socket call, with a positive control); 0 hub-level calls (`hf_hub_download`, `snapshot_download`, `try_to_load_from_cache` were replaced by refusing recorders); 0 `torch.load` and 0 `pickle` calls; the scratch `HF_HOME` stayed empty and `~/.cache/huggingface` was never created; 0 serialized pickle or zip files (the only checkpoint-named files were placeholder bytes, "NOT-A-CHECKPOINT-PLACEHOLDER", used to prove refusal). No file in the repository or the project environment changed.

### Findings and required code changes (NOT applied; each needs a separate approval)

**No code change is required for the current call sites to work.** The smallest changes the evidence points to:

1. `training/sentiment/train_sentiment_transformer.py:155` — `model.save_pretrained(directory, safe_serialization=True)` becomes `model.save_pretrained(directory)` (dead argument in 5.x; byte-identical output). Optional, recommended.
2. **Tokenizer integrity:** under 5.12.1 the 4.x argument `BertTokenizer(vocab_file=...)` silently builds a **5-token** tokenizer, and `verify_artifact` accepts an artifact whose tokenizer has lost its vocabulary, because its vocabulary check compares two numbers that both come from `config.json`. Smallest change: record `len(tokenizer)` as its own metadata field at training time and compare it with `len(self._tokenizer)` after loading in `TransformersBackend.__init__`, raising `ModelUnavailable("artifact_incompatible")` on a mismatch; do not require equality with `config.vocab_size` (some models pad the embedding matrix). Recommended.
3. With R6 / R7: `use_safetensors=True` and a pinned `revision` on the two `from_pretrained(hub_id, ...)` calls (lines 122-123) and `DISABLE_SAFETENSORS_CONVERSION=1` / offline mode after the approved download, so the Hub conversion thread cannot start. Not exercised (no Hub access).
4. `training/sentiment/README.md`: correct the "v4 is the long-term-support branch" statement.
5. Optionally a stand-in test module behind `pytest.importorskip("torch")`; it would not run in the project environment.

Other observations: `tokenizers 0.22.1` emits a `DeprecationWarning` when loading a legacy `vocab.txt` (a newer `tokenizers` may remove the path; relevant to S4, not S1); the stand-in did not exercise `ignore_mismatched_sizes=True` against a real head-size mismatch.

### Blocked items

Everything that needs R6 to R14 (weights, tokenizer downloads, datasets, annotation, metrics, calibration, activation); the code changes above; the project `certifi` / `pip` advisory (separate task, before any Hugging Face download); whether the project environment needs `setuptools<82` (N6); a real-model test with a real base checkpoint.

### Tests

Besides the 19 stand-in checks above (run in the disposable environment), only the existing documentation and model-safety tests were run in the project environment, after the documents were updated: `tests/backend/scripts/test_dry_run_package*.py`, `test_regression_tests_are_effective.py`, `tests/backend/core/test_user_text_pilot_pack.py`, `test_sentiment_model.py`, `test_user_text_model_policy.py` and `tests/training/sentiment`: **260 passed, 2 skipped** (the skips were not investigated). No training, real inference, browser, database or production-flow test was run. The project environment still has no `torch`, `transformers`, `tokenizers` or `safetensors` (`setuptools` 65.5.0, `certifi` 2026.7.22, TensorFlow 2.17.0, numpy 1.26.4); `models/sentiment` and `datasets/raw/sentiment` do not exist.

### Cleanup

The venv (about 900 MB), the 35 downloaded wheels, the scratch pip cache and the scratch work directories were deleted after the results were recorded. Reproduction commands are in section M.9; the scripts exist only in the session scratchpad.

## Approval recorded 2026-10-27 (seventh brief) — narrowly scoped Transformer integration hardening: code changes approved

**Recorded before any file under `backend/`, `training/` or `tests/` was edited.** The owner approved a narrowly scoped hardening phase and these code changes, as given. No model weight is downloaded, no Hugging Face revision is queried, no dataset is accessed, no production inference is run and the Transformer is not enabled.

### The approved changes (as given)

1. **Training serialization:** `model.save_pretrained(directory, safe_serialization=True)` becomes `model.save_pretrained(directory)`; the artifact must be confirmed safetensors-only; no change to training behaviour; no dependency added.
2. **Tokenizer integrity:** record the actual tokenizer vocabulary length in the trained artifact's metadata; when the artifact is loaded, compare the loaded tokenizer's length with the recorded length and **reject the artifact explicitly** if they differ; do **not** require the tokenizer length to equal `config.vocab_size` (padded embedding matrices are valid); preserve the existing path, hash, safetensors, label-map, calibration and validation checks; the error must be explicit and follow repository-standard error handling.
3. **Training safety seam:** add the minimal safe-loading parameters for the future approved model path: `use_safetensors=True`; an immutable `revision` supplied by the caller; offline / local-only behaviour where applicable; `trust_remote_code=False`. Do not invent a revision, add a default Hub model, or download or resolve any model. If the existing function signatures cannot safely accept these values, stop and report the required API decision.
4. **Hub conversion protection:** prevent or disable background Hub conversion on the future training path only where the installed Transformers version supports it by a **documented** mechanism; if the exact supported mechanism is unclear, leave the code unchanged and document the blocker.
5. **Documentation:** the training README no longer describes Transformers 4.x as the long-term-support branch; document the validated Transformers 5.12.1 behaviour and the remaining limitations; update only directly related ADR, approval, memory or training documentation.

**Required tests (as given):** the existing artifact and model-safety tests, and new tests for matching and mismatched tokenizer length, malformed or missing length metadata, padded embedding matrices, safetensors-only output, refusal of pickle / `.bin` / `.pt` / `.pt2`, the immutable-revision requirement, `trust_remote_code=False`, local / offline loading, no network access, no Hugging Face cache writes, and no `torch.load` or pickle calls, using only local randomly initialised stand-in models and hand-written tokenizer fixtures (no real weights, real Hub ids, user text or datasets).

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; **R6 to R14 UNRESOLVED**; no model licence or revision approved; no dataset or annotation decision approved; no production configuration or dependency-manifest change; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; intensity regression deferred; raw user text never persisted, logged, cached, transmitted or placed on-chain. A1 stays REJECTED; A2 stays approved only for S1 isolated verification. If any test exposes a broader design choice, work stops and it is reported rather than expanded.

### Design decisions taken inside this scope (recorded so none is silent; each can be reversed by the owner)

| Id | Decision | Why |
| --- | --- | --- |
| D1 | The tokenizer-length mismatch and a missing or malformed recorded length are rejected with the existing code **`artifact_incompatible`** (`ModelUnavailable`), not a new code | The reason codes are enumerated in the public API schema (`api/schemas.py`), the generated TypeScript types (`frontend/src/types/api.ts`) and the frontend message map (`frontend/src/lib/user-text-input.ts`); a new code would be a cross-cutting API change that was not approved. `artifact_incompatible` is the repository-standard code for every artifact consistency failure, including the existing vocabulary check. The error stays a fixed code with no text or path, as `ModelUnavailable` requires; the distinct check and its dedicated tests make the rejection explicit. A new, more specific code needs a separate approval |
| D2 | The recorded value is `metadata["tokenizer"]["length"]` (an integer of at least 1, recorded as `len(tokenizer)` at training time); `tokenizer.vocab_size` keeps its existing meaning and check | Preserves the existing checks; the new field is required, so an artifact without it is refused. No real artifact exists, so nothing is invalidated |
| D3 | `fine_tune_with_torch` gains two keyword-only parameters: `revision` (required; a 40-character lowercase hexadecimal commit hash; branch names, tags, short hashes and empty values are refused before any package is imported) and `allow_hub_download` (default `False`, meaning `local_files_only=True`). The command line gains `--revision` (required) and `--allow-hub-download` | The existing signature can accept additive keyword-only parameters, so no stop was needed. The offline-by-default choice is mine and is the secure default; the first approved download must say so explicitly. The owner may prefer a different default |
| D4 | The revision is validated and passed to the loaders but is **not** written into the artifact metadata | Recording it changes the artifact schema and was not approved; reported as an API decision for later (the previously known provenance gap stays open) |
| D5 | Item 4 is limited to documented parameters (`use_safetensors=True`, a pinned `revision`, `local_files_only`); the `DISABLE_SAFETENSORS_CONVERSION` environment variable is **not** set by the code unless the installed library documents it (checked and recorded below) | "Do not rely on undocumented behavior" |
| D6 | The library-dependent tests are skipped (`pytest.importorskip`) in the project environment, which has none of the four packages. To run them, the disposable environment is recreated from the existing hash-pinned S1 list under the standing A2 isolated-verification approval and the sixth-brief setuptools acceptance (no new package; `pytest` comes from the project environment, which is not modified, through a launcher that appends the disposable `site-packages`), and is deleted afterwards | The tests need `torch` and `transformers`; nothing else is added |

**State of the gate after this record:** the changes and tests above are authorised. Results are recorded in the section "Integration hardening results" below once the work has run.

## Integration hardening results (seventh brief) — 2026-10-27: the approved code changes are applied and tested; nothing activated

Written for the project owner. The approval and the design decisions D1 to D6 were recorded before any code was edited (section above). **No deviation from them was needed, and no broader design choice was forced.** No model weight was downloaded, no Hugging Face revision was queried, no dataset or user text was used, no production inference was run, and the Transformer is not enabled.

### Preserved states (unchanged)

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; **R6 to R14 UNRESOLVED**; no model licence or revision approved; no dataset or annotation decision approved; no production configuration, `backend/pyproject.toml`, requirements file or `.env` change; the project environment still has none of `torch`, `transformers`, `tokenizers`, `safetensors`; sentiment remains isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; intensity regression deferred; no raw user text was used, logged, persisted, cached, sent or placed on-chain (the tests process fixed token ids and synthetic words only). A1 REJECTED; A2 approved only for S1 isolated verification.

### Item by item

| # | Requested | Outcome |
| --- | --- | --- |
| 1 | `save_pretrained(directory, safe_serialization=True)` becomes `save_pretrained(directory)`; artifact safetensors-only; no behaviour change, no dependency | **Done** (`train_sentiment_transformer.py`). Confirmed with the real function: the output holds `config.json`, `model.safetensors` and tokenizer files only, no `.bin`, `.pt`, `.pth`, `.pt2` or pickle, and the safetensors header is `{"format": "pt"}`; the earlier stand-in check T10 (dependency request, section M) had shown byte-identical output with and without the keyword. A source-level test fails if `safe_serialization=` returns |
| 2 | Record the real tokenizer length; compare at load; reject a difference explicitly; not tied to `config.vocab_size`; keep every other check; repository-standard error | **Done.** `write_artifact` records `tokenizer.length` (new required argument, `TrainerOutput.tokenizer_length = len(tokenizer)`); `verify_artifact` requires an integer of at least 1 (missing, `None`, string, `0`, negative, boolean, float, list or mapping are `artifact_incompatible`); `check_tokenizer_length` and `TransformersBackend(..., tokenizer_length=...)` (required keyword, no default, also passed by `evaluate_sentiment_model.py`) refuse any other loaded length with the fixed code `artifact_incompatible`, outside the `load_failed` wrapper; a padded embedding matrix (config 32, tokenizer 25) loads. All earlier checks are unchanged and still tested |
| 3 | Safe-loading parameters for the future model path; revision supplied by the caller; no invented revision, no default Hub model; stop if the signature cannot take them | **Done without a stop.** `fine_tune_with_torch` takes keyword-only `revision` (required) and `allow_hub_download=False`; `base_model_loading_kwargs` returns `revision`, `trust_remote_code=False`, `local_files_only=not allow_hub_download` and the model load adds `use_safetensors=True`; the revision must be a 40-character lowercase hexadecimal hash and is checked before any package is imported; the command line has a required `--revision` and an explicit `--allow-hub-download`. No hash is written in any source file (a test searches for one) |
| 4 | Prevent background Hub conversion where a **documented** mechanism exists | **Blocker documented; code unchanged beyond item 3.** The installed transformers 5.12.1 has one switch, `DISABLE_SAFETENSORS_CONVERSION`, in a single line of `modeling_utils.py` and nowhere else in the installed package, and a web search found no documentation for it, so it is not used. With the documented parameters (`use_safetensors=True`, a pinned `revision`) the installed source does not start a conversion (a test pins this with a simulated Hub: the control call on `main` does request one); that is installed-version behaviour, not a documented guarantee, so it must be re-checked on any version change |
| 5 | Documentation | **Done:** `training/sentiment/README.md` (no longer calls 4.x the long-term-support branch; new sections "Loading the base model safely" and "Validated behaviour of transformers 5.12.1, and what is still unproven"), an ADR-052 addendum in `docs/DECISIONS.md`, `docs/MEMORY.md`, this record and a status note in the dependency request report |

### Changed files

Code: `backend/wealthpilot/core/sentiment_model.py`, `training/sentiment/artifacts.py`, `training/sentiment/train_sentiment_transformer.py`, `training/sentiment/evaluate_sentiment_model.py`. Existing tests adapted to the new signatures only: `tests/backend/conftest.py` (the artifact factory records `tokenizer.length`), `tests/backend/core/test_sentiment_model.py` (two calls), `tests/training/sentiment/sentiment_fixtures.py` (`TrainerOutput`), `tests/training/sentiment/test_sentiment_training_pipeline.py` (a valid synthetic revision in the command-line test; docstring). New tests: `tests/backend/core/test_sentiment_tokenizer_integrity.py` (41), `tests/training/sentiment/test_transformer_training_seam.py` (40), `tests/training/sentiment/test_transformer_standin.py` (32), helper `tests/training/sentiment/standin_helpers.py`. Documents: `training/sentiment/README.md`, `docs/DECISIONS.md`, `docs/MEMORY.md`, this record, `reports/sentiment_transformer_dependency_request.md`. Not changed: `backend/pyproject.toml`, `.env.example`, settings, API schemas, frontend, any model artifact.

### Tests run and results (exact)

| Run | Command shape | Result |
| --- | --- | --- |
| A. Project environment only | `pytest` on `tests/backend/scripts/test_dry_run_package*.py`, `test_regression_tests_are_effective.py`, `tests/backend/core/test_user_text_pilot_pack.py`, `test_sentiment_model.py`, `test_sentiment_tokenizer_integrity.py`, `test_user_text_model_policy.py`, `tests/backend/api/test_personalized_insights_model.py`, `tests/training/sentiment` | **359 passed, 3 skipped** (the stand-in module skips as a whole because `torch` is absent; two skips are the earlier symlink-privilege ones) |
| B. Same groups with the disposable S1 packages available through a launcher (the project environment is only read) | the same, via `runner.py` (project interpreter, disposable `site-packages` appended, offline switches, scratch `HF_HOME`) | **391 passed, 2 skipped** (the two symlink skips); the difference from A is exactly the 32 stand-in tests |
| C. Remaining API tests that reference the sentiment model | `tests/backend/api/test_personalized_insights_interpretation.py`, `test_personalized_insights_model.py` | **42 passed** |
| D. Effectiveness (mutation) check | six in-memory defects, one process each, over the 113 new tests | baseline 113 passed; **every defect detected**: tokenizer-length check removed (21 failing), loading keywords dropped (14), any revision accepted (31), online by default (2), remote code allowed (4), the forbidden design of requiring tokenizer length equal to `config.vocab_size` (3) |

A final re-run of the project-environment groups of run A plus the interpretation API test, after the documentation edits, gave **383 passed, 3 skipped**.

The stand-in tests cover: matching and mismatched tokenizer length; a tokenizer that lost its vocabulary (5 tokens against a recorded 25); missing and malformed length metadata (eleven malformed values); padded embedding matrices; safetensors-only output; refusal of `pytorch_model.bin`, `model.pt`, `model.pth`, `model.pt2` and `pytorch_model.pt2` by the backend, the library and the verifier; the immutable-revision requirement (twenty bad values); `trust_remote_code=False` for model and tokenizer code; offline and local loading, checked by spying on the exact keywords the runtime backend and the trainer pass; and an autouse guard on every stand-in test that refuses and records any socket operation, hub-level call, `torch.load` and checks that the Hugging Face cache directories are unchanged (0 network attempts, 0 hub-level calls, 0 `torch.load` or pickle calls, no cache entry). A control test shows the guard fires. The trainer ran with `epochs=0` (no optimiser step), against a local random base model and a hand-written tokenizer; the only revision used is a synthetic hash.

### Remaining blockers and open decisions

1. **Item 4 stays a documented blocker:** no documented Hub-conversion switch; protection rests on documented parameters plus installed-version behaviour that a test pins.
2. **API decision (D4):** the base-model revision is validated and used but not recorded in the artifact metadata; recording it changes the artifact schema. Recommended before the first real training run.
3. **API decision (D1):** a more specific reason code than `artifact_incompatible` would change the public API schema, the generated TypeScript types and the frontend message map.
4. A tokenizer **longer** than `config.vocab_size` is not checked at artifact time (the model would fail on an id it has no row for); adding the check is an owner choice.
5. Nothing has run against a real checkpoint, a real download, a real head-size mismatch or a real training loop; `tokenizers` 0.22.1 warns that building a WordPiece tokenizer from a `vocab.txt` path is deprecated; the stand-in module runs only where the packages exist (a disposable environment).

### Next approval required before a real checkpoint or dataset can be accessed

1. **R6** (FinBERT: licence read from the model card and accepted, plus the exact 40-character commit hash to pass as `--revision`) and/or **R7** (the RoBERTa-family candidate and its hash); no revision is approved today.
2. The owner's **recorded network approval** to run the trainer with `--allow-hub-download` for exactly those pinned revisions, and an approval to **install the S1 packages in the environment where training will run** (A2 covers isolated verification only).
3. The project `certifi` / `pip` advisory resolved first (use `certifi` 2026.10.19 or later) as a separate task, and a decision on D4 (record the revision in the metadata).
4. For any dataset or annotation work: **R8 to R10** (and R11 to R13 for targets and calibration); **R14**, a separate recorded decision, for any activation. None is requested or decided here.

### Cleanup

The disposable environment (about 900 MB), the 35 downloaded wheels, the scratch pip cache and the scratch directories were deleted after the results were recorded; the scripts exist only in the session scratchpad. The hash-pinned list is the table in section L of the dependency request report (identical on every run).

## Owner decision record (eighth brief) — remaining blockers and design choices D7 to D13: 1 approved, 2 unresolved, 4 blocked; no code changed

Written for the project owner. This section prepares the decisions that remain after the integration-hardening package. It is a **read-only review**: no real checkpoint, dataset, user text or Hugging Face asset was accessed, no model revision was queried, nothing was installed or downloaded, and **no code, test, manifest, configuration or environment was changed** (D8 and D9 are not approved, and the brief allows implementation only after approval). Reviewed: this record, the dependency request report, ADR-052 and its addenda, `docs/MEMORY.md`, `training/sentiment/README.md`, `backend/wealthpilot/core/sentiment_model.py`, `training/sentiment/artifacts.py`, `training/sentiment/train_sentiment_transformer.py`, `training/sentiment/evaluate_sentiment_model.py`, and the tokenizer-integrity and training-seam tests. **One path in the brief's reading list does not exist:** `backend/wealthpilot/core/artifacts.py`; the artifact writer is `training/sentiment/artifacts.py`, which is what was read.

**How to read this section.** Two things are kept apart and must not be confused. **Owner decisions** are what the owner's brief states as rules or defaults; they are recorded as such. **Engineering recommendations** are mine; they are *not* approvals, and an item the owner has not decided stays UNRESOLVED however strongly it is recommended. A status of **BLOCKED** means the owner's own gate is not yet met.

### Preserved states (unchanged)

`user_text_rules_v1` is the active production method; `SENTIMENT_MODEL_ENABLED=false`; **R6 to R14 UNRESOLVED** (none is decided below); A1 REJECTED; A2 approved only for disposable S1 compatibility verification; no model, revision, licence, dataset or annotation decision is approved; no change to `backend/pyproject.toml`, runtime configuration or any production environment; intensity regression deferred; sentiment remains isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no raw user text is persisted, logged, cached, transmitted or placed on-chain.

### Decision matrix

| Id | Item | Status | Owner decision recorded now | Engineering recommendation (NOT an approval) | What unlocks it |
| --- | --- | --- | --- | --- | --- |
| D7 | Public failure reason for a tokenizer-length mismatch | **APPROVED** | Retain `artifact_incompatible`. No new public API error code is approved | Keep as is | A separate explicit approval to add a new code (public API change) |
| D8 | Base-model revision and provenance metadata in every trained artifact | **UNRESOLVED when written; APPROVED on 2026-10-28 (ninth brief) and implemented** | None yet. Nothing in the schema is modified | Approve: require the exact 40-character base-model revision, and the companion fields below, with a schema version, **before any real training run** | The owner records the decision text prepared below; then a narrowly scoped local change and tests |
| D9 | Reject an artifact whose tokenizer is longer than `config.vocab_size` | **UNRESOLVED when written; APPROVED on 2026-10-28 (ninth brief) and implemented** | None yet. Equality is not required (padded embedding matrices stay valid) | Approve: reject `len(tokenizer) > config.vocab_size` explicitly | The owner records the decision text prepared below; then a targeted test and check |
| D10 | Hub conversion behaviour | **BLOCKED** | (a) no undocumented environment-variable switch is added; (b) the pinned-revision plus `use_safetensors=True` behaviour is an **observed Transformers 5.12.1 property, not a permanent guarantee**; (c) before any real download or training one of three conditions must hold (below); (d) no real model may be fetched while this is unresolved | Path B (local conversion-free workflow) is the most controllable, but needs an API decision | One of: documented upstream mechanism, local pre-download conversion-free workflow, or a separate security approval of the residual risk. **None is satisfied today** |
| D11 | Network approval for a real checkpoint | **BLOCKED** | Standing rules recorded: `local_files_only=True` stays the default; `trust_remote_code=False` stays mandatory; no floating branch, tag or `main`. An explicit approval is required for eight named things (below), **none of which has been supplied** | Note: `--allow-hub-download` does not enforce a file allow-list today (see D11) | A completed request form signed off by the owner |
| D12 | Package installation scope | **BLOCKED** (for any real training environment) | A2 stays limited to disposable compatibility verification; any real training environment needs a separate approval to install the S1 set; `backend/pyproject.toml` is not modified until production activation is separately approved; the setuptools residual-risk acceptance stays explicit and environment-limited | Approve a named, dedicated, hash-pinned environment when the time comes | A separate installation approval naming the environment |
| D13 | Project certificate tooling (`certifi` / `pip` advisory) | **BLOCKED** (separate task created, not started) | Create a separate blocked task; do not fix it in this phase; no Hugging Face download until the approved remediation is complete or explicitly risk-accepted | See the observation under D13 about which environment's certificate bundle a download would use | Remediation completed, or an explicit risk acceptance |

Status counts: **APPROVED 1** (D7), **UNRESOLVED 2** (D8, D9), **BLOCKED 4** (D10, D11, D12, D13).

### D7 — Public failure reason: APPROVED (retain `artifact_incompatible`)

- **Current state (VERIFIED FACT, code):** a tokenizer-length mismatch, and a missing or malformed recorded length, are refused with `ModelUnavailable("artifact_incompatible")` (`check_tokenizer_length`, `verify_artifact`), the same fixed code as every other artifact consistency failure.
- **Why this preserves compatibility (VERIFIED FACT):** the reason codes are enumerated in `backend/wealthpilot/api/schemas.py` (two places), the generated `frontend/src/types/api.ts` and the message map in `frontend/src/lib/user-text-input.ts`, and `tests/backend/core/test_user_text_model_policy.py` parametrizes over `FALLBACK_REASONS`. Retaining the existing code leaves the API contract, the generated types and the frontend untouched.
- **What a new code would cost (engineering note):** `FALLBACK_REASONS`, both literals in `schemas.py`, regeneration of the OpenAPI types, a frontend message, test updates and a documentation change. Not approved.

### D8 — Base-model revision and provenance metadata: UNRESOLVED when written (superseded: APPROVED and implemented on 2026-10-28, ninth brief)

**Today (VERIFIED FACT, `training/sentiment/artifacts.py` and the trainer):** the metadata records `base_model` (the Hub identifier from the candidate register), `base_model_license` (a placeholder text), `library_versions` (only `torch`, `transformers`, `numpy`), `seed`, the per-file SHA-256 list and, since the seventh brief, `tokenizer.length`. It does **not** record the revision the base model was loaded at (the revision is validated and used, then discarded), the tokenizer's source, the versions of `tokenizers`, `safetensors`, `huggingface_hub` or Python, a schema version, or a hash of the manifest.

| Field the brief names | Recorded today | Engineering recommendation (not an approval) |
| --- | --- | --- |
| Model identifier | yes: `base_model` | keep |
| Exact 40-character revision | **no** | **require** `base_model_revision`: the same validated value passed as `--revision`, so the recorded revision is by construction the one that was loaded; refused if absent or not a 40-character lowercase hash. This is the item the brief recommends approving |
| Tokenizer identifier and revision | no | record `tokenizer_source` as `{id, revision}`; in this seam the tokenizer is loaded from the same repository at the same revision, so the two values equal the model's by construction; recording them makes the claim explicit and leaves room for a different tokenizer later without a schema change. No separate tokenizer-revision argument is proposed now |
| Dependency versions | partly | extend `library_versions` to `torch`, `transformers`, `tokenizers`, `safetensors`, `numpy` and the Python version; **informational provenance, not a load gate** (the loader does not compare them) |
| Artifact-manifest hash | no | record `manifest_sha256`: the SHA-256 of the canonical JSON (sorted keys, no whitespace) of the `files` map; the loader recomputes and compares it. **Honest limit:** the metadata file and the hash live in the same directory, so this detects an inconsistent edit, not someone who rewrites the whole directory (the same self-attesting limit as the existing per-file hashes). Its real value is being citable: the future R14 activation record can name the exact artifact. Pinning an expected hash in a setting would be a production-configuration change and is **not proposed now** |

**Proposed schema versioning and backward-compatibility policy (applies only if D8 is approved):**

1. A required integer `metadata_schema_version`. The first versioned format is **1** and contains everything recorded today (including `tokenizer.length`) plus the fields above.
2. The loader supports exactly the versions it lists (initially `{1}`). A missing, unknown or newer version is refused with `artifact_incompatible`. There is no silent upgrade and no best-effort reading.
3. **No compatibility shim is needed**: no real artifact exists, and the only artifacts are test fixtures, which are updated in the same change (`tests/backend/conftest.py` `make_artifact`, the fake trainer, and the stand-in tests).
4. Artifacts are immutable. They are never edited in place; a different format means retraining or a rewrite by the trainer.
5. Any later change increments the version and needs an ADR addendum and the owner's approval; which older versions remain readable is an explicit owner choice recorded then.
6. Nothing is checked against the Hub: the revision is validated for format only, never resolved.

**Tests that would be added after approval (not added now):** a schema version present and supported; missing, unknown and non-integer versions refused; revision present, 40-character lowercase, and refused when missing, short, uppercase, a branch or a tag; tokenizer source present and consistent; `manifest_sha256` matches and a mismatch is refused; extended library versions recorded; the stand-in trainer records the revision it was given; no network, cache or pickle access.

**Decision text for the owner to record (if approved):** "D8 APPROVED: every trained artifact records `metadata_schema_version: 1`, the base-model identifier and exact 40-character revision, `tokenizer_source` (identifier and revision), the extended library versions, and `manifest_sha256`; the loader requires and validates them as specified in the eighth-brief record; unversioned or other-version artifacts are refused; local validation changes and tests only; no Hub resolution, no settings change." Fields may be struck from the list if the owner wants fewer.

### D9 — Tokenizer/config size invariant: UNRESOLVED when written (superseded: APPROVED and implemented on 2026-10-28, ninth brief)

- **Today (VERIFIED FACT):** a tokenizer **longer** than `config.vocab_size` is accepted by the artifact check, and an existing test (`test_a_tokenizer_longer_than_the_embedding_matrix_is_not_this_checks_business`) asserts that on purpose, because the seventh-brief scope did not include the check.
- **Why it matters (engineering reasoning):** if `len(tokenizer) > config.vocab_size`, the tokenizer can emit an id with no row in the embedding matrix, which fails at inference or reads out of range. The valid padded case is the opposite direction (tokenizer shorter than the matrix) and stays valid; equality is not required.
- **Recommendation (not an approval):** reject explicitly, with the same fixed code (`artifact_incompatible`, consistent with D7), at two points: in `verify_artifact` from the metadata (`tokenizer.length` against the `vocab_size` already read from `config.json`; stdlib only, so it fails early and at artifact-writing time), and in `TransformersBackend.__init__` (loaded tokenizer length against the loaded model's `config.vocab_size`).
- **Tests after approval:** longer than the matrix refused at both points; equal accepted; shorter (padded) accepted; the existing test flipped to expect refusal; the mutation check extended. Not added now.
- **Decision text for the owner to record (if approved):** "D9 APPROVED: an artifact or a loaded tokenizer with `len(tokenizer) > config.vocab_size` is refused with `artifact_incompatible`; equality is not required; padded embedding matrices remain valid."

### D10 — Hub conversion behaviour: BLOCKED

- **Owner decisions recorded:** no undocumented environment-variable switch (the one in the installed library's code, `DISABLE_SAFETENSORS_CONVERSION`, is undocumented and stays unused); the current protection (a pinned revision plus `use_safetensors=True`) is treated as an **observed Transformers 5.12.1 property, pinned by a test, not a permanent guarantee**; **no real model may be fetched while this stays unresolved.**
- **Gate: at least one of these three must hold before any real download or training, and none holds today:**

| Path | Description | State | Engineering assessment (not an approval) |
| --- | --- | --- | --- |
| A. A documented upstream mechanism | The library's documentation or release notes name a supported switch that disables Hub conversion | **Not satisfied.** The only switch is a single code occurrence in the installed package with no documentation, and a documentation search found none | Re-check the documentation and release notes whenever the version changes |
| B. A local, conversion-free artifact workflow | The files are obtained at the exact pinned revision as a named list, verified against owner-supplied SHA-256 values, and the trainer is then pointed at the local directory, so the library's Hub branch (the only place conversion exists) is never reached | **Not designed, not approved.** It would need (1) the D11 request, (2) a documented file-level download of exactly the named files, and (3) **a trainer API decision**: `fine_tune_with_torch` takes a Hub identifier from the candidate register today and has no parameter for a local base-model directory, so this is a design choice I did not make | Strongest control and it also gives D11 its enforceable file allow-list; costs one API decision |
| C. A separate security approval accepting the residual risk | The owner states the risk in writing: the library may, in a version-dependent way, ask the Hub to convert a checkpoint | **Not given** | Acceptable only if scoped to one named revision and one run, with the observed-behaviour test re-run first |

### D11 — Real-checkpoint network approval: BLOCKED

- **Standing rules recorded as owner decisions:** `local_files_only=True` stays the default (the trainer is offline unless `--allow-hub-download` is passed); `trust_remote_code=False` stays mandatory; no floating branch, tag or `main` is allowed (the trainer already refuses anything but a 40-character lowercase hash).
- **Eight things need explicit approval before any real checkpoint is fetched. None has been supplied:**

| # | Required | Supplied |
| --- | --- | --- |
| 1 | Exact model repository (for example the candidate register's identifier, confirmed by the owner) | no |
| 2 | Exact 40-character revision | no |
| 3 | Exact files permitted (names, sizes, expected SHA-256) | no |
| 4 | Destination directory | no |
| 5 | Use of `--allow-hub-download` for that run | no |
| 6 | Account and network boundary (which machine and account, anonymous or token, proxy, nothing persisted) | no |
| 7 | Hash verification (every file against the owner-supplied values; a mismatch aborts and deletes) | no |
| 8 | Cleanup and rollback (what is deleted, where caches live, how a failed or rejected run is undone) | no |

- **Engineering finding that bears on item 3:** `--allow-hub-download` only switches the library to online mode; it is **not a file allow-list**. The library decides which files it fetches (weights, configuration, tokenizer files). So the owner's "exact files permitted" requirement cannot be enforced by that flag alone; it needs path B of D10 (file-level download of named files) or a post-download check that nothing outside the list was written. This is a recommendation to resolve together with D10.

### D12 — Package installation scope: BLOCKED for any real training environment

- **Owner decisions recorded:** A2 remains limited to disposable compatibility verification; any real training environment requires a **separate approval** to install the S1 package set; `backend/pyproject.toml` is not modified until production activation is separately approved; the setuptools residual-risk acceptance (`setuptools==81.0.0`, GHSA-h35f-9h28-mq5c and GHSA-xmj3-9gf7-h52w) stays explicit and limited to the disposable Windows pip-only environment described in the sixth-brief record.
- **What the installation approval would have to name (engineering note):** the environment's path and owner; the hash-pinned list (the 35-package table of section L of the dependency request report, re-checked against OSV on the day); whether the same `setuptools` acceptance is extended to it (it is **not** extended by default); the deletion or retention rule; and the statement that the project environment is not used.

### D13 — Project certificate tooling: BLOCKED (task created, not started)

**Task card TASK-CERT-1 (BLOCKED; no work done in this phase).**

| Field | Content |
| --- | --- |
| Problem (VERIFIED FACT, earlier phases) | The project environment has `certifi 2026.7.22` and `pip 26.2.1`, which vendors `certifi 2026.6.17`; both are affected by GHSA-6q48-6c7w-9gw2 (Critical; compromised emSign intermediates; use `certifi` 2026.10.19 or later) |
| Scope when unblocked | Upgrade `certifi` in the project environment to 2026.10.19 or later; move `pip` to a release whose vendored `certifi` is fixed (`pip` 26.2.2 exists; its vendored version has not been checked); check that no project endpoint chains to the removed emSign root; run the full regression suite; record rollback |
| Out of scope | Any sentiment, model, package or dataset change |
| Gate | The owner approves the task, or accepts the residual risk in writing for a stated scope |
| Rule recorded | No download from Hugging Face until the approved remediation is complete or explicitly risk-accepted |
| Engineering observation (NOT an approval; the owner may narrow the gate) | A real download would run in a dedicated training environment, not necessarily in the project environment. The S1 hash-pinned list pins `certifi 2026.10.23`, which is outside the affected range, and the Hub client uses the environment's own `certifi`; `pip`'s vendored copy matters only for `pip`'s own package downloads, which are hash-checked. So the project-environment remediation may not be the bundle that matters for a download. This is an expectation, not a verified fact for a training environment that does not exist yet |

### R6 to R14 — unchanged

| Id | State |
| --- | --- |
| R6 FinBERT licence and exact immutable revision | UNRESOLVED |
| R7 RoBERTa-family candidate and exact revision | UNRESOLVED |
| R8 Financial PhraseBank as a development benchmark | UNRESOLVED |
| R9 Personal-finance annotation protocol | UNRESOLVED |
| R10 Evaluation size and class quotas | UNRESOLVED |
| R11 Macro-F1 and precision targets | UNRESOLVED |
| R12 Minimum coverage | UNRESOLVED |
| R13 Calibration and abstention policy | UNRESOLVED |
| R14 Activation criteria | UNRESOLVED |

### The exact approvals still missing before the first real checkpoint can be accessed

The first missing approval, in the order I would take them, is **R6 (or R7)**. Nothing below has been given:

1. **R6 and/or R7:** the model card's licence read and accepted by the owner, and the exact 40-character commit hash to use. No revision may be queried or resolved by me; the owner supplies it.
2. **D10:** path A, B or C satisfied (and, for B, the trainer API decision for a local base-model directory).
3. **D11:** the eight-item request completed and signed off for that one checkpoint.
4. **D12:** a separate approval to install the S1 package set in a named training environment.
5. **D13:** TASK-CERT-1 completed, or an explicit written risk acceptance (possibly narrowed as noted).
6. **D8 and D9 decided** (recommended before any real artifact is written; D8 is the owner's stated pre-condition for any real training run), and, if approved, implemented with their tests.
7. For **training** (not for the download itself): a dataset and annotation approval (R8 to R10) and targets and calibration (R11 to R13). **R14**, a separate recorded decision, for any activation.

### Confirmation

Production remains on the rules baseline `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`; the Transformer is not enabled and no model artifact exists; nothing was fetched, installed or run in this phase.

## Decisions recorded 2026-10-28 (ninth brief) — D8 and D9 APPROVED: artifact provenance and the tokenizer/embedding invariant

**Recorded before any file under `backend/`, `training/` or `tests/` was edited.** The owner resolved only D8 and D9, as given below. Nothing is queried from Hugging Face, no model revision is accessed, no package is installed or downloaded, no weight or dataset is fetched, no production configuration is changed and the Transformer is not enabled.

### D8 — Revision and provenance metadata: **APPROVED** (as given)

Every trained sentiment artifact must include: `metadata_schema_version` (currently `1`); the exact model identifier; the exact 40-character lowercase base-model revision; the tokenizer identifier; the exact tokenizer revision; the tokenizer length; dependency versions for `torch`, `transformers`, `tokenizers` and `safetensors`; the artifact-manifest SHA-256; and the label-map and calibration metadata the existing loader already requires.

Rules: a missing or unknown `metadata_schema_version` is rejected; missing or malformed revision or provenance fields are rejected; revisions must be immutable 40-character lowercase commit hashes; **no migration code is added**; artifacts are never edited in place; existing artifact hashes and validation checks remain enforced; no model identifier or revision is invented; **an existing artifact without the new metadata fails closed as `artifact_incompatible`**.

### D9 — Tokenizer/config size invariant: **APPROVED** (as given)

An artifact is rejected when `len(tokenizer) > config.vocab_size`. Equality is not required: a tokenizer length equal to `config.vocab_size` is accepted, a lower one is accepted (padded embedding matrices are valid), a greater one is rejected with `artifact_incompatible`; a missing or malformed tokenizer length is rejected; the check occurs before inference; the error exposes no raw user text and no sensitive metadata.

### Scope (as given)

Only the artifact writer, the artifact verifier, the loader's metadata types, the trainer and evaluator where required, and directly related tests, ADR-052, this record and memory documentation. No new public API failure code (`artifact_incompatible` is used). No change to the active rules baseline or to activation behaviour, to dependency manifests or configuration. No undocumented Hub-conversion environment variable. No real model identifier, revision, dataset or weight. If the existing schema cannot carry these fields without a broader migration or a public API change, the work stops and the exact blocker is reported.

### Design details fixed inside this scope (recorded so none is silent; each can be reversed by the owner)

| Id | Detail | Why |
| --- | --- | --- |
| S1 | Field names and placement in `model_metadata.json`: `metadata_schema_version`; `base_model` (the model identifier, already present); `base_model_revision`; inside the existing `tokenizer` block: `identifier`, `revision`, `length` (and the existing `vocab_size`, `files`); `library_versions` (existing key; the four required entries `torch`, `transformers`, `tokenizers`, `safetensors` must be non-empty strings, extra entries such as `numpy` are allowed); `manifest_sha256` | The existing schema carries these fields without a migration or an API change |
| S2 | `manifest_sha256` is the SHA-256 (64 lowercase hexadecimal characters) of the canonical JSON of the `files` map (keys sorted, separators `,` and `:`, ASCII). It is computed by one function (`manifest_sha256`) used by the writer and the verifier. A malformed value is `artifact_incompatible`; a well-formed value that differs from the recomputed one is `artifact_corrupt` (it is a hash mismatch, like a file hash mismatch), and the check runs after the per-file hash loop so the existing reasons for file problems are unchanged | Consistent with the existing meaning of the two codes. It detects an inconsistent edit of the metadata; like the per-file hashes it cannot detect someone who rewrites the whole directory |
| S3 | The trainer reports what it actually used: `TrainerOutput` gains `base_model_revision`, `tokenizer_identifier` and `tokenizer_revision` (required, no defaults), and the dependency versions of `tokenizers` and `safetensors` join `torch`, `transformers` and `numpy`. In the current seam the tokenizer is loaded from the same identifier at the same revision as the model, so those values are equal by construction; no separate tokenizer-revision argument is added | The recorded revision is then the one that was loaded, never a second value that could drift |
| S4 | The revision regular expression lives once, in the loader module (`is_commit_hash`); the trainer's `validate_revision` uses it | The backend must not import the training package, and two copies could drift |
| S5 | The D9 check runs at two points with the same code: in `verify_artifact` (recorded `tokenizer.length` against `config.json` `vocab_size`; stdlib only, so it also fails at artifact-writing time) and in `TransformersBackend.__init__` (the loaded tokenizer's length against the loaded model's `config.vocab_size`; a missing or non-integer value is also refused) | The brief requires the check before inference |
| S6 | `dependency versions` are provenance only: the loader checks that they are present and well-formed but does not compare them with the installed libraries | Not requested; comparing would be a new runtime gate |
| S7 | **No package is installed or downloaded in this phase**, including in a disposable environment (the brief lists installation among its prohibitions). The library-dependent stand-in tests (`test_transformer_standin.py`) are therefore updated for the new signatures but **cannot be run now**; they skip in the project environment. Running them needs the disposable S1 environment recreated, which the owner has not asked for in this brief | Honours the prohibition; the limitation is reported, not hidden |

### Preserved states

D10, D11, D12 and D13 stay **BLOCKED**; R6 to R14 stay **UNRESOLVED**; D7 stays APPROVED (`artifact_incompatible`); `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; no model, revision, licence or dataset approved; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; raw user text never persisted, logged, cached, transmitted or placed on-chain.

## D8 and D9 implementation results (ninth brief) — 2026-10-28: artifact provenance and the tokenizer/embedding invariant are enforced; nothing activated

Written for the project owner. The decisions and the design details S1 to S7 were recorded before any file was edited (section above). **No design blocker appeared**: the existing metadata schema carried every field without a migration or a public API change. No package was installed or downloaded in this phase, no Hugging Face asset, revision, weight, dataset or user text was accessed, no model identifier or revision was invented (every test value is a synthetic hash that names nothing), and the Transformer was not enabled.

### Exact schema (`model_metadata.json`, `metadata_schema_version` 1)

Required, in addition to the fields the loader already required (names, dataset, labels, calibration, validation evidence, regression, per-file hashes):

| Field | Rule enforced by `verify_artifact` |
| --- | --- |
| `metadata_schema_version` | integer, not boolean, a member of `SUPPORTED_SCHEMA_VERSIONS` = `{1}` |
| `base_model` | non-empty text (the exact model identifier) |
| `base_model_revision` | 40-character lowercase hexadecimal string (`is_commit_hash`) |
| `tokenizer.identifier` | non-empty text |
| `tokenizer.revision` | 40-character lowercase hexadecimal string |
| `tokenizer.length` | integer of at least 1 (not boolean) |
| `library_versions` | a mapping with non-empty text for `torch`, `transformers`, `tokenizers` and `safetensors`; extra entries (for example `numpy`) allowed; provenance only, never compared with what is installed |
| `manifest_sha256` | 64 lowercase hexadecimal characters; equal to the SHA-256 of the canonical JSON of the `files` map (sorted keys, separators `,` and `:`, ASCII), recomputed with the one function `manifest_sha256` |

### Exact rejection behaviour (every error is the fixed code only: no value, path, revision or text)

| Condition | Code |
| --- | --- |
| `metadata_schema_version` missing, unknown, newer, boolean, float, text or null | `artifact_incompatible` |
| any provenance field above missing or malformed (including a branch name, tag, short, uppercase, padded or non-text revision) | `artifact_incompatible` |
| an artifact written before these fields existed (the seventh-brief format) | `artifact_incompatible` (fails closed; no migration code exists, verified by a test) |
| `manifest_sha256` malformed | `artifact_incompatible` |
| `manifest_sha256` well formed but different from the recomputed value | `artifact_corrupt` |
| a listed file missing or with a different hash; the file list altered | `artifact_corrupt` (unchanged) |
| a listed path that escapes the directory | `path_not_allowed` (unchanged) |
| `.bin`, `.pt`, `.pth`, `.pt2`, `.ckpt`, `.pkl` listed in place of `model.safetensors` | `artifact_incompatible` (unchanged rule, now tested for each name) |
| wrong `model_version` | `version_mismatch` (unchanged) |
| `tokenizer.length` greater than `config.vocab_size` (**D9**) | `artifact_incompatible`, at artifact verification, before any backend exists |
| `tokenizer.length` equal to or smaller than `config.vocab_size` | accepted (padded embedding matrices are valid) |
| `tokenizer.length` missing, zero, negative, boolean, float, text, list or mapping | `artifact_incompatible` |
| loaded tokenizer length different from the recorded `tokenizer.length` | `artifact_incompatible` (in the `TransformersBackend` constructor) |
| loaded tokenizer longer than the loaded model's `vocab_size`, or that value missing or malformed (**D9**) | `artifact_incompatible` (in the constructor, before any text is processed) |

Order inside `verify_artifact`: required keys, then schema version, then provenance, then version and name, then the file checks and per-file hashes, then the manifest hash, then labels, `config.json`, vocabulary and tokenizer length and the D9 comparison, then positions, calibration and validation evidence. A rejected artifact never reaches a backend.

### Changed files

Code: `backend/wealthpilot/core/sentiment_model.py` (schema constants, `is_commit_hash`, `manifest_sha256`, provenance validation, `check_tokenizer_fits_embeddings`, new `ArtifactInfo` fields, the D9 check in the backend constructor), `training/sentiment/artifacts.py` (the writer takes and records the provenance and the manifest hash; it still ends with the loader's own verification), `training/sentiment/train_sentiment_transformer.py` (`TrainerOutput` reports the revisions and tokenizer identifier actually used and the four dependency versions; `validate_revision` uses the loader's single definition). Not changed: `training/sentiment/evaluate_sentiment_model.py` (it goes through `verify_artifact` and already passes the recorded length), settings, API schemas, the frontend, `backend/pyproject.toml`, any manifest or configuration. Existing tests adapted: `tests/backend/conftest.py` (the artifact factory writes version 1 metadata; new `metadata_tools` fixture), `tests/training/sentiment/sentiment_fixtures.py` (the fake trainer reports synthetic provenance), `tests/backend/core/test_sentiment_tokenizer_integrity.py` (the superseded "longer is accepted" test now expects refusal; the fake model has a `config`; five D9 backend tests added), `tests/training/sentiment/test_transformer_training_seam.py` (eight trainer-side provenance tests added), `tests/training/sentiment/test_transformer_standin.py` (new writer arguments, provenance assertions, two real-model D9 tests added; see the limit below). New: `tests/backend/core/test_sentiment_artifact_provenance.py` (184 tests). Documents: `training/sentiment/README.md`, `docs/DECISIONS.md` (ADR-052 addendum), `docs/MEMORY.md`, this record.

### Tests and results

| Run | Result |
| --- | --- |
| Project environment, the smallest relevant groups: `tests/backend/scripts/test_dry_run_package*.py`, `test_regression_tests_are_effective.py`, `tests/backend/core/test_user_text_pilot_pack.py`, `test_sentiment_model.py`, `test_sentiment_tokenizer_integrity.py` (60), `test_sentiment_artifact_provenance.py` (184), `test_user_text_model_policy.py`, `tests/backend/api/test_personalized_insights_model.py`, `test_personalized_insights_interpretation.py`, `tests/training/sentiment` (seam file: 62) | **608 passed, 3 skipped** (two are the earlier symlink-privilege skips; the third is the stand-in module, skipped as a whole because `torch` is absent) |
| Effectiveness check: eight deliberate in-memory defects, one process each, over the four core test files (baseline 347 passed) | **all eight detected**: D9 check removed (35 failing), any revision accepted (50), any schema version accepted (6), provenance not validated (117), recorded length not compared (15), new fields no longer required (5), manifest hash check disagreeing with the writer (72), the trainer accepting any revision (26) |

The new tests cover: valid schema version 1; missing and unknown schema versions (fifteen bad values); malformed base-model and tokenizer revisions (twenty bad values each); missing and malformed model and tokenizer provenance, including each of the four dependency versions; the independent manifest hash vector, a malformed hash, a wrong hash, and a hash that follows only the file list; old-format artifacts failing closed; matching, shorter, equal and longer tokenizer lengths at the artifact and at the backend; padded embedding matrices; missing and malformed tokenizer length; unchanged hash, missing-file, version, label-map and calibration checks; refusal of `pytorch_model.bin`, `model.bin`, `model.pt`, `model.pth`, `model.pt2`, `pytorch_model.pt2`, `model.ckpt` and `model.pkl`; that no error contains the offending value or a path; that no migration or upgrade function exists and the loader writes no file; and an autouse guard on the provenance tests that refuses sockets, records `pickle` calls and checks that nothing imported `torch`, `transformers`, `huggingface_hub`, `tokenizers` or `safetensors` (0 attempts, 0 pickle calls, 0 imports).

### Limit: the library-dependent stand-in tests were NOT re-run

`tests/training/sentiment/test_transformer_standin.py` needs `torch` and `transformers`. This phase installed nothing, so that module was **updated but not executed**; it skips here. It compiles, its edits are mechanical (the writer's new required arguments, taken from what the real trainer reports) plus two tests that mirror the passing pure tests (a tokenizer longer than a 20-row embedding matrix is refused by the writer and by the backend; equal is accepted). **Until it is re-run in the disposable S1 environment (the 32 earlier tests passed there on 2026-10-27 before this change), the new schema is verified only through the pure tests and the fake-package backend tests.** *(Superseded on 2026-10-28, tenth brief: it was re-run and all 34 tests passed; see "Disposable S1 regression check results".)* Re-running needs the disposable environment recreated from the hash-pinned S1 list; the owner has not asked for that in this brief.

### Preserved states

D7 APPROVED (`artifact_incompatible`; no new public API code); D10, D11, D12 and D13 remain BLOCKED; R6 to R14 remain UNRESOLVED; no model, revision, licence or dataset approved; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; the rules baseline and activation behaviour untouched; no dependency manifest, configuration or environment changed; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations. No real checkpoint, dataset, Hugging Face asset or production method was accessed.

### What D8 and D9 do not change in the remaining approvals

The first missing approval before any real checkpoint is still R6 (or R7) with the exact revision supplied by the owner, then D10, D11, D12 and D13. D8 and D9 are no longer open decisions; the one new item is the **re-run of the stand-in tests** in the disposable environment, which should precede any real training.

## Decision recorded 2026-10-28 (tenth brief) — the disposable S1 regression check is authorised

**Recorded before execution.** The owner approved running only the library-dependent regression check that the ninth brief could not run, in the already-approved disposable S1 environment.

### Authorised (as given)

- **A2 remains APPROVED only for isolated verification.** The disposable environment is recreated outside the repository at `C:\Users\Administrator\.copilot\sentiment-compatibility-venv` from the **existing hash-pinned S1 wheel set only**: `torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2`, `setuptools==81.0.0`, `numpy==1.26.4` (with the 29 other packages of the recorded 35-package list). No new version is resolved and no package is added.
- Run only: (1) the updated `tests/training/sentiment/test_transformer_standin.py`; (2) the directly related Transformer seam, artifact-provenance and tokenizer-integrity tests, to confirm the new required metadata arguments; (3) the existing model-safety guards.
- The tests use only randomly initialised local stand-in models, hand-written local tokenizer fixtures, synthetic 40-character revisions that identify no real model, local safetensors artifacts and fixed synthetic token ids.
- To be verified: the new required provenance arguments; schema version 1 metadata loads; tokenizer-length metadata is accepted; equal and shorter tokenizer lengths stay valid; longer ones are rejected; padded embedding matrices stay valid; safetensors-only loading; pickle, `.bin`, `.pt` and `.pt2` artifacts stay rejected; `trust_remote_code=False` and `local_files_only=True` are preserved; no sockets or network requests, no Hub calls, no pickle or `torch.load` calls, no Hugging Face cache writes; no real model or dataset is accessed.
- **If any test fails: stop, report the exact failure and the affected file, change no code automatically, do not broaden the scope.**
- Afterwards: record the exact commands, package hashes, environment details and results; delete the disposable venv, the wheel directory and the caches; confirm the repository and the project environment are unchanged. Only the approval record, the dependency report, the ADR-052 addendum and MEMORY are updated.
- No real training, real inference, browser test, database test or production flow.

### How the prohibition on accessing PyPI is read (recorded so it is not silent)

The recreation needs the wheels, which were deleted after the last run, so the **same hash-pinned wheels are fetched once, before the tests**, with `pip download --only-binary=:all: --no-deps --require-hashes` from the recorded pin list: no resolution, no metadata or advisory query, no other package. Every file is then hashed again independently against the pin list. **The test run itself is offline**: the network, hub-level, `torch.load` and pickle guards of the tests apply, the Hugging Face switches are set to offline and `HF_HOME` points at an empty scratch directory. If the owner meant that no PyPI contact at all is allowed, the check cannot be run and this section is to be withdrawn.

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7 APPROVED; D8 and D9 APPROVED and implemented; D10, D11, D12 and D13 BLOCKED; R6 to R14 UNRESOLVED; no real checkpoint, model revision, dataset or user text accessed; intensity regression deferred; no dependency manifest, configuration or production environment change.

## Disposable S1 regression check results (tenth brief) — 2026-10-28: 381 passed, 1 skipped; no failure; nothing activated

Written for the project owner. The check authorised in the section above ran in full. **No test failed, so the stop rule did not trigger and no code was changed.** No real model, dataset, Hugging Face asset, revision or user text was accessed, and nothing was queried about any model revision.

### Environment (VERIFIED FACT)

Disposable venv `C:\Users\Administrator\.copilot\sentiment-compatibility-venv` (outside the repository), base interpreter Python 3.11.9 (MSC v.1938, AMD64), Windows 10.0.26300, pip 24.0. The pin list was byte-identical to the first isolated run's (`diff`, 35 packages), so the 35-row hash table of section L of the dependency request report applies. The six named pins:

| Package | SHA-256 of the pinned wheel |
| --- | --- |
| `torch==2.13.0` | `a0d8b11f16a48d60e2015d8213aa0390744cbebb98e58b62b3514dddc656e330` |
| `transformers==5.12.1` | `2a5e109d2021265df7098ffbb738295acaf5ad256f12cbc586db2ea4dcbb1a8a` |
| `tokenizers==0.22.1` | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` |
| `safetensors==0.6.2` | `c7b214870df923cbc1593c3faee16bec59ea462758699bd3fee399d00aac072c` |
| `setuptools==81.0.0` | `fdd925d5c5d9f62e4b74b30d6dd7828ce236fd6ed998a08d81de62ce5a6310d6` |
| `numpy==1.26.4` | `cd25bcecc4974d09257ffcd1f098ee778f7834c3ad767fe5db785be9a4aa9cb2` |

Steps: `python -m venv`; `pip download --only-binary=:all: --no-deps --require-hashes -r pins_s1.txt -d wheels` (exit 0; the only PyPI contact, fetching exactly the pinned files); an independent SHA-256 of all 35 files (**35 of 35 equal to the pin list, none missing, none extra, 170.3 MB**); `pip install --no-index --find-links wheels --only-binary=:all: --no-deps --require-hashes -r pins_s1.txt` (exit 0, offline); `pip check` ("No broken requirements found"); `pip freeze --all` (36 lines: the 35 pins plus pip), with `torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2`, `setuptools==81.0.0`, `numpy==1.26.4` and `certifi==2026.10.23`. No version was resolved and no package was added.

### The check (VERIFIED FACT)

Launcher `runner.py` (session scratchpad): the project's own interpreter and pytest, the disposable `site-packages` appended to `sys.path` (the project environment is only read, bytecode writing off), `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_HOME` pointing at an empty scratch directory. Command shape: `pytest tests/training/sentiment/test_transformer_standin.py tests/training/sentiment/test_transformer_training_seam.py tests/backend/core/test_sentiment_artifact_provenance.py tests/backend/core/test_sentiment_tokenizer_integrity.py tests/backend/core/test_sentiment_model.py -p no:cacheprovider -q -rfEs`.

| File | Result |
| --- | --- |
| `tests/training/sentiment/test_transformer_standin.py` (the library-dependent stand-in tests, updated in the ninth brief) | **34 passed** (the 32 earlier tests plus the two real-model D9 tests) |
| `tests/training/sentiment/test_transformer_training_seam.py` | 62 passed |
| `tests/backend/core/test_sentiment_artifact_provenance.py` | 184 passed |
| `tests/backend/core/test_sentiment_tokenizer_integrity.py` | 60 passed |
| `tests/backend/core/test_sentiment_model.py` (the existing loader guards) | 41 passed, 1 skipped (symbolic links are not permitted for this account: the earlier skip) |
| **Total** | **381 passed, 1 skipped, 0 failed** |

### What the check verified, with the evidence

| Requirement | Evidence |
| --- | --- |
| The new required provenance arguments work | the real `fine_tune_with_torch` (with `epochs=0`) reports `base_model_revision`, `tokenizer_identifier`, `tokenizer_revision` and the four dependency versions as the installed libraries report them; `write_artifact` accepts them; the metadata holds `base_model_revision`, `tokenizer.revision`, `tokenizer.identifier`, the versions of torch / transformers / tokenizers / safetensors equal to the installed ones, and a `manifest_sha256` equal to `manifest_sha256(files)` (`test_the_real_trainer_writes_a_safetensors_only_artifact_and_records_the_real_tokenizer_length`) |
| Schema version 1 metadata loads; tokenizer length metadata is accepted | the same artifact verifies as `metadata_schema_version` 1 and the real `TransformersBackend` loads it and returns finite logits (`test_a_matching_tokenizer_length_loads_and_one_cpu_forward_pass_gives_finite_logits`) |
| Equal and shorter tokenizer lengths remain valid; padded embedding matrices remain valid | `test_a_tokenizer_equal_to_the_embedding_matrix_is_accepted_with_a_real_model` (25 and 25), `test_a_padded_embedding_matrix_remains_valid` (matrix 32, tokenizer 25) |
| Longer tokenizer lengths are rejected | `test_a_tokenizer_longer_than_the_embedding_matrix_is_refused_by_the_writer_and_by_the_backend` (matrix 20, tokenizer 25: refused by `write_artifact` and by the backend constructor as `artifact_incompatible`) |
| A recorded length that differs from the loaded tokenizer is rejected | four recorded lengths (24, 26, 5, 1) and a tokenizer that silently lost its vocabulary (5 tokens against a recorded 25) |
| Safetensors-only loading | the real trainer's output holds `config.json`, `model.safetensors` and tokenizer files only; the header is `{"format": "pt"}`; no `.bin`, `.pt`, `.pth`, `.pt2` or pickle file exists |
| Pickle, `.bin`, `.pt` and `.pt2` remain rejected | a directory holding only each of `pytorch_model.bin`, `model.pt`, `model.pth`, `model.pt2`, `pytorch_model.pt2` is refused by the backend (`load_failed`) and by the library (`OSError`); metadata listing each of the first four in place of safetensors is refused by the verifier; a placeholder pickle beside safetensors is never read |
| `trust_remote_code=False` preserved | spies show the runtime backend and the trainer pass `trust_remote_code=False` on both loads; local custom model and tokenizer code is never executed (marker files absent) |
| `local_files_only=True` preserved | the runtime backend passes `local_files_only=True`; the trainer defaults to `True` and passes `False` only with the explicit switch; `use_safetensors=True` on the model load; an invalid or floating revision is refused before the base model is touched |
| The Hub-conversion property | with a pinned revision and `use_safetensors=True` no conversion is requested, and the control call on `main` does request one (an observed 5.12.1 property, not a guarantee; unchanged D10 status) |
| No sockets or network requests | the autouse guard refuses and records every socket operation: 0 recorded in every stand-in test; the control test proves the guard fires |
| No Hub calls | `hf_hub_download`, `snapshot_download` and `try_to_load_from_cache` replaced by refusing recorders: 0 calls |
| No pickle or `torch.load` calls | `torch.load` replaced by a refusing recorder and `pickle.load(s)` recorded: 0 calls |
| No Hugging Face cache writes | the stand-in guard compares the Hugging Face cache directories before and after every test (unchanged); the scratch `HF_HOME` was empty after the run; `~/.cache/huggingface` does not exist |
| No real model or dataset | every model is randomly initialised in the test; the tokenizers are hand-written; every revision is a synthetic hash; the only inputs are fixed token ids and synthetic words |

### Cleanup and unchanged state

Deleted after the run: the venv (903 MB), the 35 downloaded wheels (163 MB), the scratch pip cache (166 MB) and the scratch directory; the path of the venv no longer exists. Only this record was changed in the repository during the phase (checked by modification time); `backend/pyproject.toml`, `.env.example`, `pytest.ini`, every source file, test, setting and API schema are as the ninth brief left them. The project environment is unchanged: no file in it is newer than the decision record, and it still has none of `torch`, `transformers`, `tokenizers` or `safetensors` (`setuptools` 65.5.0, `certifi` 2026.7.22). `models/sentiment` and `datasets/raw/sentiment` do not exist.

### Open item created by this result

`training/sentiment/README.md` still says, in its sections "Validated behaviour of transformers 5.12.1" and "Tests", that the library-dependent stand-in tests were updated but **not re-run**. That is now out of date: they were re-run and passed. The brief limits documentation updates to the four documents named, so the README was not edited; it should be corrected under a one-line approval.

### Readiness for the R6/R7 phase

**Ready to enter the separate R6/R7 model-licence and exact-revision approval phase, which is a paper decision that needs no further engineering; not ready for any download.** What supports the first: the schema (D8) and the tokenizer/embedding rule (D9) are enforced and now verified against real libraries as well as fakes; the revision rule, the offline default, `trust_remote_code=False`, `use_safetensors=True` and the refusal of pickle, `.bin`, `.pt` and `.pt2` are verified; nothing in the guards fired. What still blocks a download is unchanged: **R6 / R7** (licence accepted and the exact 40-character revision supplied by the owner), **D10** (Hub conversion: a documented mechanism, a local conversion-free workflow that needs a trainer API decision for a local base directory, or a separate security approval), **D11** (the eight-item request for one named checkpoint), **D12** (installation in a named training environment), **D13** (the project `certifi` / `pip` task or an explicit risk acceptance). Still unproven, because nothing real has ever been run: behaviour with a real checkpoint, a real head-size mismatch, a real training loop.

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7 APPROVED; D8 and D9 APPROVED and implemented; D10, D11, D12 and D13 BLOCKED; R6 to R14 UNRESOLVED; no real checkpoint, model revision, dataset or user text accessed; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations.

## R6 / R7 approval preparation (eleventh brief) — 2026-10-28: decision matrix and owner decision fields prepared; nothing decided, nothing accessed

Written for the project owner. This section prepares the decisions; it makes none. **Every decision below is UNRESOLVED until the owner records it.** No Hugging Face page, API or file was queried, no weight or tokenizer was downloaded, no dataset was opened, no package was installed. Every fact below comes from evidence already recorded in this repository, and each carries its source and a state:

- **RECORDED** — read from a model card or API response by the earlier owner-approved metadata read of 2026-10-20 (three anonymous GETs per model, `huggingface.co` only; `reports/phaseB2S2_SENTIMENT_COMPLETION_REPORT.md` sections 6 and 11.1). The saved metadata files are not in the repository now. A RECORDED licence is a *model-card claim*, not verified permission, and it was **not re-read in this phase**.
- **OWNER-SUPPLIED** — stated by the owner in an earlier brief, not confirmed against the card.
- **UNRESOLVED** — not established by any recorded evidence. A recollection is not recorded as a fact.

### Documentation correction (approved in the eleventh brief)

`training/sentiment/README.md` said in two places (the section "Validated behaviour of transformers 5.12.1" and the section "Tests") that the library-dependent stand-in tests had not been re-run. Both statements are corrected, and no other line of the README changed. The corrected statement (second place):

> the S1 disposable-environment regression check of 2026-10-28 then passed: 381 tests passed, 1 skipped, 0 failed (34 of them in this module), using only local randomly initialised stand-in models and hand-written tokenizers, with no real model weights, Hugging Face assets, datasets or user text accessed.

No code, dependency manifest, configuration, production environment or activation state changed.

### R6 / R7 decision matrix (both UNRESOLVED)

R7 is recorded as `FacebookAI/roberta-base`, which the earlier briefs proposed as "one general-language RoBERTa-family candidate". It has **no sentiment head**: it is a fine-tuning base, so it cannot be evaluated at all until a training set is approved (R8 to R13). The owner must name the R7 candidate; the other RoBERTa-family models in the record are listed under the matrix.

| Item | **R6 — `ProsusAI/finbert`** | **R7 — `FacebookAI/roberta-base`** (candidate to be confirmed by the owner) |
| --- | --- | --- |
| Model identifier | `ProsusAI/finbert` — the key `finbert` of `training/sentiment/config.py::CANDIDATES` | `FacebookAI/roberta-base` — the key `roberta-base` of the same register |
| Model-card licence | CC BY-NC-SA 4.0 — RECORDED (card front matter, API tag and a "License and Usage Terms" section); not re-read | UNRESOLVED (no card was ever read; the earlier register lists it as "to verify") |
| Weight licence and restrictions | the card applies the same licence to the weights and says it "restricts commercial use ... any adaptations must be shared under the same license"; it says Prosus cannot answer commercial or legal questions and disclaims warranty, so **the user decides whether a use is non-commercial** — RECORDED | UNRESOLVED |
| Tokenizer licence if separate | no separate licence recorded and no `LICENSE` file listed in the repository at the time — RECORDED; whether the tokenizer files fall under the repository licence is UNRESOLVED | UNRESOLVED |
| Training-data licence and provenance | Financial PhraseBank (CC BY-NC-SA **3.0**) and Reuters TRC2 "distributed by NIST under its own access terms" (the base language model was further trained on it) — RECORDED card claims; the corpora's own terms and what they pass to derived weights are UNRESOLVED | UNRESOLVED (general web and book corpora; provenance not verified) |
| Commercial / non-commercial | non-commercial if the card's licence is confirmed — RECORDED claim. Whether a research prototype whose output feeds an advisory demo is "non-commercial" is a legal question for the owner | UNRESOLVED |
| Attribution and share-alike | BY (attribution) and SA (share-alike) — RECORDED claim. A model fine-tuned from it is an *adaptation*; whether share-alike also reaches its outputs or features, or only redistributed weights, is UNRESOLVED | UNRESOLVED |
| 4.0 versus 3.0 | the card's 4.0 licence on weights trained on a 3.0 corpus is an open question: can a model trained on that data carry either licence? **Legal, not answerable here** | not applicable until a licence is recorded |
| Domain and language limits | English; sentences from financial **news about companies**. The repository's use is a person's own financial narratives and short macro headlines: a domain mismatch — RECORDED | general English; no financial-domain knowledge; a new head would be trained on whatever set is approved |
| Label taxonomy | three classes; declared index order **0 positive, 1 negative, 2 neutral** — RECORDED from the config; must be re-read from the pinned revision's own `config.json` at approval, never assumed (the artifact writer re-maps by name) | none (a new three-class head would be trained; the order would be ours) |
| Known training / evaluation data | Financial PhraseBank and TRC2 (card); the FinBERT paper is cited by a mirror as arXiv:1908.10063 (search listing); **no self-reported evaluation on the card** — RECORDED | UNRESOLVED |
| Suitable for personal-finance narratives | **Not established.** No evidence exists for this use; the domain differs; no personal-finance validation set exists. **Financial PhraseBank is a development benchmark at most and is not sufficient validation for personal-finance narratives** | **Not established**, and not evaluable without a training set |
| Exact immutable 40-character revision | **RECORDED, NOT APPROVED:** `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` (40 lowercase hexadecimal characters; matches `is_commit_hash`), read on 2026-10-20. It is not re-verified, may no longer be the revision the owner wants, and becomes usable only if the owner writes it into decision P4 | UNRESOLVED — none recorded; none queried |
| Expected tokenizer / architecture compatibility | 109.5M parameters and weights for PyTorch, TensorFlow, Flax and safetensors — RECORDED. A BERT-base encoder with a WordPiece tokenizer is the **expected** family (inference from the parameter count; the `architectures` and `vocab_size` fields were not recorded) — UNVERIFIED. The stand-in tests used a hand-written WordPiece fixture, so this is the family closest to what was tested; no real vocabulary, head size or `len(tokenizer) <= vocab_size` result exists | a RoBERTa encoder with a byte-level BPE tokenizer is the **expected** family — UNVERIFIED. **No BPE tokenizer fixture exists in the stand-in tests**, so BPE loading, special tokens and the D9 length rule are untested with that tokenizer type |
| Weight files that would be needed | a `safetensors` weight file is listed — RECORDED; exact file names were not recorded. The PyTorch / TensorFlow / Flax files in the repository must **not** be downloaded | UNRESOLVED |
| Pickle risk | not recorded for this repository; any `.bin` / `training_args.bin` / `.h5` is excluded by the safetensors-only rule | UNRESOLVED |
| Unresolved legal, provenance and safety questions | (1) is the research use "non-commercial"? (2) does share-alike bind derived weights, outputs or features? (3) 4.0 weights versus 3.0 corpus; (4) TRC2 access terms; (5) whether the repository's tokenizer files carry a licence; (6) the revision above comes from one API response of 2026-10-20 and is unverified; (7) whether the repository holds loader code or a pickle (`trust_remote_code` is `False` regardless); (8) label order at the pinned revision | all of the above, plus: which licence the card carries; which corpora; whether the tokenizer is separately licensed; the revision |
| Overall state | **UNRESOLVED** — approve / reject / keep unresolved is the owner's | **UNRESOLVED** — the owner must also name the candidate |

**Other RoBERTa-family models already in the record** (none is selected; each is UNRESOLVED): `distilbert/distilroberta-base` (smaller fine-tuning base, same limits as R7); `cardiffnlp/twitter-roberta-base-sentiment-latest` (already has a sentiment head, label order negative / neutral / positive, licence tag CC BY 4.0 from a single secondary snapshot, trained on about 124 million tweets per an aggregator page: social-media language, not personal finance); `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis` (revision `ae0eab9ad336d7d548e0efe394b07c04bcaf6e91` RECORDED, card says Apache-2.0 yet trained on Financial PhraseBank, which is non-commercial share-alike: the card is auto-generated and **inconsistent on its face**). The brief asks for a RoBERTa-family *sentiment* candidate; `roberta-base` has no sentiment head. If the owner wants a candidate that can be scored without fine-tuning, the choice is between the last two.

### Owner decision fields (all UNRESOLVED; nothing here is pre-filled as approved)

| ID | Decision required | Options | Proposal, **not** approval | Owner decision |
| --- | --- | --- | --- | --- |
| P1 | R6: `ProsusAI/finbert` | APPROVE / REJECT / KEEP UNRESOLVED | none | |
| P2 | R7: which candidate, and whether it is approved | name the identifier; APPROVE / REJECT / KEEP UNRESOLVED | none | |
| P3 | Licence and usage restrictions accepted for each model | accept / reject, with the reading chosen (for example: research, non-commercial use only; no redistribution of weights or derivatives except under the same licence; or written confirmation / legal opinion first) | read each model card at the pinned revision first | |
| P4 | Exact 40-character revision for each selected model | the hash, written by the owner (or an explicit approval to query metadata) | for R6 the RECORDED `0bc2ac10...f031` may be confirmed or replaced | |
| P5 | Exact files permitted for download | an enumerated list per model | `config.json`, the safetensors weight file, the tokenizer files the model needs (for example `vocab.txt`, `tokenizer_config.json`, `special_tokens_map.json` for a WordPiece model; `vocab.json`, `merges.txt` for a BPE model); exclude every `.bin`, `.pt`, `.h5`, `.msgpack`, `training_args.bin`. **The exact names are unverified and need an approved file-listing read** | |
| P6 | Destination directory | a path | a directory outside the repository, one per `<identifier>@<revision>` (`models/sentiment/` ignores `.safetensors` but a third-party checkpoint is not a project artifact) | |
| P7 | Network access and the `--allow-hub-download` boundary | hosts, number of requests, method, time window; whether the switch may be used once | `huggingface.co` only, anonymous, no token, abort on any off-domain redirect. **Weight files are normally served from a different host through a redirect** (expected, not verified), so that host would have to be approved by name. The default stays offline. This is decision D11 and also needs D10 | |
| P8 | SHA-256 verification and provenance recording | approve / change | record the SHA-256 of every downloaded file, the revision, the licence reading and the date before first use, in the artifact metadata (`base_model_revision`, `tokenizer.revision`, `manifest_sha256` already exist) | |
| P9 | Cleanup and rollback | approve / change | delete the destination directory, caches and any environment on failure or on request; nothing is added to the repository, the project environment or the database | |
| P10 | Use of the weights | offline evaluation only / evaluation and training | evaluation only first. **Training creates an adaptation**, which for R6 inherits the share-alike term; it also needs R8 to R13 | |
| P11 | Activation | confirm | **Activation remains a separate R14 decision.** Nothing in P1 to P10 activates a model | |

None of P1 to P11 is enough on its own: a download also needs **D10** (Hub conversion behaviour), **D11** (the eight-item network request for one named checkpoint), **D12** (installation in a named training environment) and **D13** (the project `certifi` / `pip` task or an explicit risk acceptance), all BLOCKED; scoring or training needs **R8 to R13** (dataset, annotation, targets, calibration), UNRESOLVED.

### Commands and sources in this phase

- Read-only: the approval record, `reports/sentiment_transformer_dependency_request.md` (candidate register, section C), `reports/phaseB2S2_SENTIMENT_COMPLETION_REPORT.md` (sections 6 and 11.1), `reports/phaseB2S2_OWNER_APPROVAL_WORKSHEET.md`, `training/sentiment/config.py`, `.gitignore`, and a pattern search of the repository for "finbert" and "roberta".
- A local check that the recorded FinBERT revision is 40 lowercase hexadecimal characters.
- **No network access of any kind, no package installed, no model, tokenizer or dataset opened.**

### Preserved states

`user_text_rules_v1` remains the active production method; `SENTIMENT_MODEL_ENABLED=false`; D7, D8 and D9 APPROVED (D8 and D9 implemented); D10, D11, D12 and D13 BLOCKED; R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no real checkpoint, revision, tokenizer, dataset or user text accessed; no model download or real inference; intensity regression deferred; sentiment is isolated from risk, goals, portfolio, recommendations, compliance and financial calculations.

## R6 / R7 selection phase (twelfth brief) — 2026-10-28: no selection was supplied, so R6 and R7 stay UNRESOLVED; the decision form is complete

Written for the project owner. **No decision is recorded as made.** The brief defines the choices (approve / reject / keep unresolved for R6; exactly one of three candidates or unresolved for R7) and the licence items to accept or reject, but it contains **no selection and no accept / reject value for any item**. An owner decision is never inferred from the wording of a brief, from a recommendation of mine, or from a model-card label, so the result of this phase is: **R6 — UNRESOLVED; R7 — UNRESOLVED; every licence and provenance item — UNRESOLVED; no candidate selected, none rejected.** What the phase adds is the form below, filled in with every fact already on record, so that one reply can resolve it.

Nothing was queried, downloaded, installed, enabled or changed: no Hugging Face page, API or file, no model, tokenizer, dataset, revision or user text, no package, no runtime code, no manifest or configuration. Evidence labels as in the eleventh-brief section: **RECORDED** (model-card claim or API response read by the owner-approved metadata read of 2026-10-20, or a single secondary snapshot where stated; not re-read; not verified permission), **OWNER-SUPPLIED**, **UNRESOLVED**. Nothing is invented: no licence, tokenizer licence, training-data permission, revision, file list, download host or commercial-use conclusion appears below that is not on record, and where the record is empty the cell says so.

### R6 — FinBERT: form (state UNRESOLVED)

`ProsusAI/finbert` is the only R6 candidate. The recorded revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` is **a proposal only** until separately approved (decision R6-9).

| ID | Item | Evidence on record | Owner entry (ACCEPT / REJECT / UNRESOLVED) |
| --- | --- | --- | --- |
| R6-0 | Approve FinBERT as the R6 candidate | not evaluated for personal-finance text; domain mismatch (company news) | |
| R6-1 | CC BY-NC-SA 4.0 model-card licence | RECORDED claim (front matter, API tag, "License and Usage Terms"); not re-read | |
| R6-2 | Financial PhraseBank CC BY-NC-SA 3.0 dependency | RECORDED (the card states the dataset is 3.0; the dataset card read earlier agrees, secondary) | |
| R6-3 | Reuters TRC2 training-data terms | RECORDED: "distributed by NIST under its own access terms"; the terms themselves were never read | |
| R6-4 | Non-commercial restriction | RECORDED claim; whether a research prototype whose output feeds an advisory demo is "non-commercial" is the owner's reading, not the card's (the card says the user decides) | |
| R6-5 | Attribution and share-alike obligations | RECORDED (BY and SA; "any adaptations must be shared under the same license"); whether SA reaches outputs or features is UNRESOLVED | |
| R6-6 | Unresolved compatibility between the model licence (4.0) and the training-data licences (3.0, TRC2) | open legal question, not answerable here | |
| R6-7 | Unresolved tokenizer licensing | none recorded; no `LICENSE` file was listed in the repository | |
| R6-8 | Exact model identifier | `ProsusAI/finbert` | |
| R6-9 | Exact 40-character revision | proposal `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` (single API response of 2026-10-20; not re-verified) | |

A single ACCEPT on R6-0 would not accept R6-1 to R6-7: each is a separate entry, and any that stays UNRESOLVED keeps R6 UNRESOLVED.

### R7 — one general-language comparison candidate: the three options and what is on record

The owner chooses exactly one, or keeps R7 unresolved. **Having a sentiment head or a permissive-looking card label is not a reason to approve** (R7-B and R7-C both have a head and a permissive-looking label, and both carry open questions below).

| | **R7-A `FacebookAI/roberta-base`** | **R7-B `cardiffnlp/twitter-roberta-base-sentiment-latest`** | **R7-C `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis`** |
| --- | --- | --- | --- |
| What it is | base language model, **no sentiment head**: a new head would be trained | sentiment model (three classes) | sentiment model (three classes), fine-tuned on financial news |
| Licence on record | **none** — no card was ever read; UNRESOLVED | CC BY 4.0 — OWNER-SUPPLIED and consistent with a licence tag seen once in a **single secondary snapshot**; the card text itself was not read; terms beyond the tag not read | Apache-2.0 — RECORDED card claim (front matter, API tag); the card is auto-generated and **inconsistent on its face** (permissive label on a model trained on a non-commercial, share-alike corpus) |
| Training-data provenance on record | UNRESOLVED (provenance not verified) | about 124 million tweets from 2018-2021 per an aggregator page (secondary, UNVERIFIED); fine-tuning data unverified; tweets carry platform terms and third-party content questions | fine-tuned on `financial_phrasebank` (4,840 sentences) per the card; the card does not state that dataset's licence (the FinBERT card states CC BY-NC-SA 3.0) |
| Label order | none (new head) | negative, neutral, positive — OWNER-SUPPLIED; must be read from the model's own `config.json` | 0 negative, 1 neutral, 2 positive — RECORDED |
| Domain | general English, no financial knowledge | **social-media language**: short, informal, emoji and hashtags; not personal finance | financial **news** about companies; not personal narratives |
| Revision on record | none | none | `ae0eab9ad336d7d548e0efe394b07c04bcaf6e91` — RECORDED (read 2026-10-20), not approved |
| Self-reported quality | not applicable | none verified | 0.982 accuracy on the PhraseBank `sentences_allagree` split (easiest subset, best epoch picked on it): no evidence about this project's text |
| Architecture / tokenizer (expected, UNVERIFIED) | RoBERTa encoder, byte-level BPE tokenizer | same family | DistilRoBERTa, BPE; 82.1M parameters, PyTorch weights only, built with Transformers 4.10.2 / PyTorch 1.9; the repository also lists `training_args.bin`, a pickle that must never be loaded — RECORDED |
| Can be scored without further training | **no** (needs a training set, R8 to R13) | yes, zero-shot, but its domain is tweets | yes, zero-shot, but its licence and corpus terms are unresolved |
| Open legal and provenance questions | everything: licence, corpora, tokenizer licence, revision | CC BY 4.0 versus the tweet corpus's platform terms; whether the data permits the use; tokenizer licence; revision | is the Apache-2.0 label valid for weights derived from a non-commercial share-alike corpus (only the author or the data owner can say); the same share-alike question as R6; tokenizer licence; revision |
| Evidence strength | none | weakest (secondary snapshot) | strongest, but it shows an unresolved conflict |
| Owner entry | SELECT / REJECT / UNRESOLVED | SELECT / REJECT / UNRESOLVED | SELECT / REJECT / UNRESOLVED |

R7 selected: **none** (UNRESOLVED). If R7-A is selected, a training set is needed before it can be compared with anything. The stand-in tests hold no byte-level BPE tokenizer fixture for any of the three.

### Decision fields per selected candidate (R6 and the one R7 candidate; every entry UNRESOLVED)

| ID | Field | What the owner must enter | On record | Entry |
| --- | --- | --- | --- | --- |
| F1 | Exact model identifier | the identifier | R6 `ProsusAI/finbert`; R7 per the choice above | |
| F2 | Accepted licence and usage restrictions | the licence text read, the reading adopted (for example research and non-commercial only), and any restriction on redistribution | claims above only; none verified | |
| F3 | Accepted training-data provenance and terms | each corpus and the terms accepted | R6: PhraseBank, TRC2; R7: per candidate | |
| F4 | Exact immutable 40-character revision | the hash, or an explicit approval of one metadata query to read it | R6 proposal `0bc2ac10...f031`; R7-C `ae0eab9a...e91`; R7-A and R7-B none | |
| F5 | Exact permitted files | an enumerated list per model | **none on record**: no file listing was ever recorded; the list can only come from an approved listing read | |
| F6 | Destination directory | a path | none chosen | |
| F7 | Allowed download hosts and redirects | hosts named one by one, and whether any redirect is followed | the only host on record is `huggingface.co`, used for the 2026-10-20 metadata read (6 requests, no redirects). **No file-serving host is on record and none is assumed** | |
| F8 | Network approval boundary | the number and kind of requests, the time window, anonymous or not, abort rules | the 2026-10-20 precedent was three anonymous GETs per model with an abort on an off-domain redirect; it is a precedent, not an approval | |
| F9 | `--allow-hub-download` permitted | yes (once, under F7 and F8) / no | the default stays offline; the switch exists in the trainer | |
| F10 | SHA-256 verification requirements | which files, compared with what, recorded where | the project already hashes the fine-tuned artifact's files and the manifest (`manifest_sha256`); a hash of the *downloaded base files* is not recorded anywhere yet | |
| F11 | Provenance metadata required in the artifact | the fields | schema v1 already records `base_model`, `base_model_revision`, `tokenizer.identifier`, `tokenizer.revision`, `tokenizer.length`, `tokenizer.vocab_size`, `tokenizer.files`, `library_versions` and `manifest_sha256`; **no licence, no data-terms and no download-file-hash field exists**, and none is added in this phase (no runtime change) | |
| F12 | Cleanup and rollback | the procedure | none approved | |
| F13 | Offline evaluation only, or training permitted | evaluation only / evaluation and training | training creates an adaptation (for R6 the share-alike term applies) and needs R8 to R13 | |
| F14 | Activation remains a separate R14 decision | confirm | **confirmed in this record as the standing rule** | |

### The exact approvals still required

**Before any metadata query** (a metadata query is not authorised by anything above, and it is not implied by choosing a candidate):
1. R6 and/or R7 selected by the owner (R6-0, R7 choice).
2. An explicit approval of the query itself: which model identifiers, which items (for example API metadata, model card, config, file listing), the number of requests, anonymous access, the host(s), the abort rule for off-domain redirects, and where the response is stored. The 2026-10-20 read was three anonymous GETs per model; the owner may reuse that boundary or set another.
3. Only an approved query can supply a revision (F4) or a file list (F5); until then they are the owner's to write.

**Before any download or any other access to a checkpoint**, additionally, and unchanged by an R6 or R7 approval:
4. R6-1 to R6-7 (or the R7 equivalents) each ACCEPTED, and F1 to F13 entered.
5. **D10** (Hub conversion behaviour), **D11** (the eight-item network request for one named checkpoint), **D12** (installation in a named training environment) and **D13** (the project `certifi` / `pip` task or an explicit risk acceptance), all BLOCKED.
6. For scoring or training: R8 to R13 (dataset, annotation, targets, calibration). For activation: **R14**, separate.

### One-reply form

The owner can resolve this phase by replying with one line per item, for example: `R6-0: KEEP UNRESOLVED`, `R7: R7-B`, `R6-1: ACCEPT`, `R6-2: UNRESOLVED`, `F4: approve one metadata query for the two selected identifiers under the 2026-10-20 boundary`. Any item not answered stays UNRESOLVED.

### Preserved states

`user_text_rules_v1` remains the active production method; `SENTIMENT_MODEL_ENABLED=false`; D7, D8 and D9 APPROVED; D10, D11, D12 and D13 BLOCKED (and to be resolved before any real checkpoint access even if R6 or R7 is approved); R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no model, tokenizer, dataset, revision query or user text accessed; no package installed; no production configuration or manifest change; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations.

## Decision recorded 2026-10-28 (thirteenth brief) — the R6/R7 decision form is resolved conservatively: every model item KEEP UNRESOLVED, no candidate selected

Written for the project owner. The thirteenth brief instructs that exactly one value be recorded for each item of the decision form of the twelfth-brief section and that no unanswered decision be inferred. The values it gives are the conservative ones, and they are recorded here **as written in the brief**. Because every value is "keep unresolved", "not selected" or "remains blocked", **this decision approves nothing and rejects nothing**: it fixes the state of the form so that it cannot be read as an approval later.

**Reason recorded (as given):** the current evidence is insufficient to accept a model licence, training-data licence, tokenizer licence, commercial-use position, exact revision, permitted-file list or download boundary. No candidate is approved until those questions are resolved from authoritative sources.

No Hugging Face page, API or metadata, no model, tokenizer, revision, dataset or user text was queried or accessed; no package was installed; no runtime code, production setting or dependency manifest changed.

### The completed decision form

"Explicit" means the thirteenth brief names the item and gives the value. "Inherited" means an earlier recorded decision that the brief tells me to preserve. "No value given" means the brief does not mention the item, so it is not decided.

| Item | Recorded value | Basis |
| --- | --- | --- |
| R6-0 approve or reject FinBERT | **KEEP UNRESOLVED** | explicit |
| R6-1 CC BY-NC-SA 4.0 model-card licence | **KEEP UNRESOLVED** | explicit |
| R6-2 Financial PhraseBank CC BY-NC-SA 3.0 dependency | **KEEP UNRESOLVED** | explicit |
| R6-3 Reuters TRC2 training-data terms | **KEEP UNRESOLVED** | explicit |
| R6-4 non-commercial restriction | **KEEP UNRESOLVED** | explicit |
| R6-5 attribution and share-alike obligations | **KEEP UNRESOLVED** | explicit |
| R6-6 model-licence versus training-data-licence compatibility | **KEEP UNRESOLVED** | explicit |
| R6-7 tokenizer licensing | **KEEP UNRESOLVED** | explicit |
| R6-8 exact model identifier | **KEEP UNRESOLVED** (`ProsusAI/finbert` stays the identifier on record, not approved) | explicit |
| R6-9 exact 40-character revision | **KEEP UNRESOLVED** (`0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` stays a proposal) | explicit |
| R7 choice | **KEEP UNRESOLVED** | explicit |
| R7-A `FacebookAI/roberta-base` | **NOT SELECTED** (not rejected) | explicit |
| R7-B `cardiffnlp/twitter-roberta-base-sentiment-latest` | **NOT SELECTED** (not rejected) | explicit |
| R7-C `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis` | **NOT SELECTED** (not rejected) | explicit |
| F1 model identifier; F2 licence and usage restrictions; F3 training-data provenance and terms; F4 exact revision; F5 permitted files; F6 destination directory; F7 download hosts and redirects; F8 network approval boundary; F9 `--allow-hub-download`; F10 SHA-256 requirements; F11 provenance metadata in the artifact; F12 cleanup and rollback; F13 evaluation only versus training; F14 activation separate from R14 | **KEEP UNRESOLVED**, each, for R6, R7-A, R7-B and R7-C | explicit ("F1-F14 for every candidate") |
| R8, R9, R10, R11, R12, R13, R14 | **KEEP UNRESOLVED** | explicit |
| D10, D11, D12, D13 | **remain BLOCKED** | explicit |
| D7, D8, D9 | APPROVED (D8 and D9 implemented and verified) | inherited |
| Metadata-only query (identifier, fields, request count, hosts, redirect policy, anonymous access, response storage) | **NOT AUTHORISED**; no values were given for any of its parameters | no value given |
| A metadata query does not authorise a file download, tokenizer access, weight access or dataset access | recorded as a standing rule for any future query approval | explicit (condition 7 of the brief) |
| The eleventh-brief fields P1 to P11 | superseded by the form above; all UNRESOLVED | inherited |
| `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false` | unchanged | explicit |

**Explicit owner decisions in this brief:** 0 approvals, 0 rejections, 3 "not selected" (R7-A, R7-B, R7-C), and "keep unresolved" or "blocked" for everything else. **Unresolved fields:** R6-0 to R6-9, R7, F1 to F14 for four candidates (56 entries), R8 to R14; D10 to D13 are blocked. Nothing is pre-filled as accepted.

### What would reopen the form (the brief's own conditions, recorded as the required inputs)

If the owner wants to select a candidate, work stops until explicit values are supplied for:

1. R6-0: approve or reject FinBERT.
2. R6-1 to R6-7: accept or reject each licence, dataset, attribution, share-alike and commercial-use condition.
3. R6-9: approve or reject the recorded FinBERT revision.
4. R7: exactly one of R7-A, R7-B and R7-C, or unresolved.
5. The selected candidate's licence, training-data terms and tokenizer licence.
6. Permission for a metadata-only query, with: the exact model identifier; the allowed metadata fields; the maximum request count; the permitted hosts; the redirect policy; the anonymous-access requirement; the response storage location.
7. Confirmation that a metadata query does not authorise file download, tokenizer access, weight access or dataset access.

Even with those, a download or any checkpoint access still needs D10 to D13 resolved first; scoring or training needs R8 to R13; activation needs the separate R14.

### Commands and sources in this phase

Read-only: this record. Documentation edits only. No network access, no package installation, no model, tokenizer, revision, dataset or user text accessed.

### Preserved states

`user_text_rules_v1` remains the active production method; `SENTIMENT_MODEL_ENABLED=false`; D7, D8 and D9 APPROVED; D10, D11, D12 and D13 BLOCKED; R6 to R14 UNRESOLVED; no model, tokenizer, revision, dataset or user text accessed; no package installed; no production, configuration or dependency-manifest change; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations.

## Sentiment phase completion (fourteenth brief) — 2026-10-28: one rules-baseline gap fixed; seam, boundaries and frontend verified; nothing activated

Written for the project owner. The brief asks for the sentiment phase to be completed end to end, autonomously, stopping only at hard gates. Most of it was already built and recorded in earlier briefs; this phase re-verified the whole chain against the code and the test suite instead of assuming it, fixed the one defect it found, and wrote the remaining gates down. **No hard gate was crossed**: no network access, package installation, model or dataset download, personal-data collection, licence acceptance, public API change, financial-behaviour change, blockchain write or activation.

### Production state (VERIFIED FACT)

`user_text_rules_v1` is the active method (`METHOD_VERSION`, `UNVALIDATED_BASELINE`); `SENTIMENT_MODEL_ENABLED=false` (`.env.example`, settings default); every `SENTIMENT_MODEL_*` setting is documented in `.env.example` and `training/sentiment/README.md`, there is no undocumented control, and neither the loader nor the trainer reads an environment variable; the loader refuses any device but `cpu`, requires an explicit `max_tokens` and a positive timeout. The project environment has `tensorflow 2.17.0`, `numpy 1.26.4`, `setuptools 65.5.0`, `certifi 2026.7.22` and none of `torch`, `transformers`, `tokenizers`, `safetensors`. `models/sentiment` and `datasets/raw/sentiment` do not exist. Intensity regression is disabled (the trainer refuses it; `sentiment_intensity` is `None` on every rules reading).

### Defect found and fixed in the rules baseline (VERIFIED FACT)

A probe of 26 inputs (empty, whitespace, too short, symbols, emoji, Devanagari, romanised Hindi, off-topic, ambiguous, negation, quotation, third person, past feeling, hypothetical, conditional, hypothetical preference, wish, mixed, opposing preferences, explicit and generic preference, URL / e-mail / digits, over-length, control characters) behaved as documented for every case **except hypothetical and conditional statements**. Before the fix, "If the market crashes I would be very worried about my investments" returned `negative` / `concerned` / `valid` with that sentence as evidence, and "If I had more money I would want higher returns" returned a `growth_seeking` preference. That contradicts the brief's rule that a current view is never inferred from a hypothetical statement.

The fix is confined to `backend/wealthpilot/core/user_text_sentiment.py` and uses the mechanism that already handles past feelings. A clause is hypothetical when it carries a conditional marker (`if`, `unless`, `suppose`, `imagine`, `assuming`, `in case`, `provided that`, `as long as`, `were I`, `had I`, `should` + a subject such as the market), a wish construction (`I wish I could ...`), or a conditional-mood phrase (`would / might / could be, feel, get, panic ...`), or when it is the consequent of such a clause in the same sentence (carried across a comma, ended by a sentence end or a contrast word such as `but`). Indirect questions ("tell me if I should worry") and idioms ("if possible") are not conditions. A hypothetical clause yields no cue, no tone, no evidence and no preference; the response carries `NOTE_HYPOTHETICAL` in `limitations`; a text whose only cues were hypothetical is `uncertain` / `weak` with tone `unknown` (the same treatment as a negation-only text); topics are still reported as mentions. A trained model is never shown a hypothetical clause when a current clause exists, and cannot turn a hypothetical-only text into a label (the existing uncertain safeguard).

**Consequences, stated:** the rule is deliberately conservative: a clause containing a marker is dropped as a whole, so "I feel safe even if prices fall" is not read as a current positive feeling. That trades coverage for safety, matches the project's abstention policy, and is a documented limit. **No public API field, enum or schema changed** (the note is one more string in the existing `limitations` list); the generated TypeScript types were regenerated into a scratch file and are byte-identical to `frontend/src/types/api.ts`.

### Rules-baseline behaviour against the brief (VERIFIED FACT, each by a test or the probe)

| Requirement | Result |
| --- | --- |
| empty / whitespace | `status = unavailable`, no label, no tone |
| too short, symbol-heavy, emoji-only | abstain `too_short` / `low_quality_text`, `insufficient_evidence`, `interpretation_state = abstained`, no preference, `confidence = None`, fixed bounded message |
| unsupported or code-mixed language (Devanagari, romanised Hindi) | abstain `unsupported_language`; the documented policy (no translation, reported separately) is unchanged |
| off-topic / ambiguous financial text | abstain `unrelated_text` / `ambiguous_context` |
| negation, quotation, third person, past feeling | not the user's current view (existing tests) |
| **hypothetical, conditional, wish** | **fixed in this phase**, 20 new tests |
| multiple clauses, mixed sentiment, conflicting clauses | `mixed`; opposing preferences give none and a note, state `weak` |
| explicit preferences, generic stance verbs | only from an explicit phrase or a generic word after a first-person stance verb; always `unconfirmed`, `requires_confirmation` |
| structured conflicts (stated preference versus stored assessment) | unchanged; the stored assessment stays authoritative (`remains_authoritative = true`) |
| output taxonomy | unchanged |
| `artifact_incompatible` for artifact incompatibility | unchanged (D7) |

### Privacy (VERIFIED FACT: code audit plus tests)

No logger, `print`, file access, database write, cache or ledger / audit call exists in the sentiment, insight, service, router or model-loading code (an AST test, `test_the_insight_code_has_no_logger_print_database_write_or_file_access`, plus the new `test_sentiment_ledger_boundary.py`); the text arrives in the POST body, never a URL or header; `validate_text` refuses control characters and over-length text without echoing it, and the service re-raises with `from None`; evidence is capped (100 characters, 6 items) and URLs, e-mail addresses and long digit runs are masked; model failures are replaced by fixed codes and the exception object is dropped. Frontend: the sentiment components use no `localStorage`, `sessionStorage`, `indexedDB` or cookie; the query key holds the text in memory only with `gcTime: 0`; the card is keyed by the profile id, so switching profile unmounts it and clears its state.

### Blockchain boundary (VERIFIED FACT, static)

`wealthpilot/security/ledger.py` records only a sequence number, an event type, a timestamp, an opaque `record_ref` and a schema version, chained by hash. Five new database-free tests assert that no sentiment / insight / model / training module imports `wealthpilot.security` or names a ledger, anchor or blockchain; that the security package imports none of them; that the ledger event, head and canonical-payload shapes contain no field whose name suggests sentiment, preference, evidence, text, label, risk, profile, emotion, topic or probability; and that `append` accepts only an event type and an opaque reference. **The only permitted future anchor payload remains the ledger identifier, sequence number, head hash and (if the protocol needs it) a timestamp. No blockchain integration was implemented and none was requested.**

### Transformer seam and artifact integrity (VERIFIED FACT, unchanged this phase)

The metadata schema v1 (D8), the tokenizer-versus-embedding rule (D9), safetensors-only loading, immutable 40-character revisions, `trust_remote_code=False`, `local_files_only=True` by default, `use_safetensors=True`, CPU-only inference, token and time limits and the fallback to the rules baseline are all in code and covered by the provenance (184), tokenizer-integrity (60), seam (62) and loader (41) tests. The library-dependent stand-in tests were **not re-run in this phase**: the 2026-10-28 disposable-environment approval covered that one run, a re-run needs the wheels fetched again (a network access outside that approval), and this phase changed no file the stand-in tests import.

### Dataset, annotation and evaluation (status)

No dataset exists, none was generated, downloaded or collected, no annotation took place, no evaluation was run, and no validation is claimed. The protocol is recorded in `reports/sentiment_transformer_dependency_request.md` section G and `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md` (two independent annotators, a third adjudicator, blinding to every model, rules output, risk profile and recommendation, frozen manifest and rubric with SHA-256, exact and near-duplicate removal, separate training / calibration / held-out sets, no synthetic example as validation evidence, personal-finance narratives rather than news sentences, all unapproved proposals). The tooling that exists is `training/sentiment/dataset.py` (manifest validation, group-aware split, leakage check) and `metrics.py` (accuracy, macro-F1, per-class report, confusion matrix, ECE, temperature fitting, threshold selection). **Two items surfaced by this phase's fix are added to the open list:** (1) the proposed coverage list in section G has negation, contradiction, low-information and unsupported text but **no hypothetical / conditional category**, and `docs/USER_TEXT_ANNOTATION_RUBRIC.md` (decision rules 1 to 10) says nothing about hypothetical or conditional statements, so an annotator could tag a stated conditional want as a preference that the baseline now deliberately does not infer; the owner should add a coverage line and a labelling rule (no number is proposed here) before the rubric is frozen; (2) the confidence interval, bootstrap and agreement statistics listed in the evaluation plan (95% intervals, Cohen's kappa, Krippendorff's alpha, topic / difficulty / negation / code-mixed breakdowns, the paired comparison with the rules baseline) are **not implemented in `metrics.py`**; they are to be built under a separate code approval when a dataset exists. The proposed targets (macro-F1 at least 0.80, precision at least 0.85 on accepted predictions) remain proposals; high precision reached by abstaining on nearly all inputs does not qualify.

### Evidence classes (for the approval package)

| Class | Items |
| --- | --- |
| VERIFIED FACT | this phase's test results (below); the installed-package state; the S1 hashes, installation and advisory findings of sections I to L of the dependency report; the 2026-10-28 regression result (381 passed, 1 skipped, 0 failed); file and flag state above |
| VERIFIED FROM OFFICIAL SOURCE | package metadata, wheel hashes and OSV / GitHub advisory records read on 2026-10-26 and 2026-10-27 (dependency report sections I to L) |
| PRELIMINARY APPLICABILITY ASSESSMENT | advisory applicability to this repository, the licence-concern assessment of the S1 packages, the Hub-conversion property of transformers 5.12.1 |
| CANDIDATE PROPOSAL | the S1 package set; the three model candidates and their recorded revisions; the 300-statement held-out set, quotas and coverage lists; the proposed metrics and targets |
| OWNER DECISION | A1 REJECTED; A2 APPROVED for S1 isolated verification only; `setuptools` 81.0.0 residual risk accepted for the isolated environment only; D7, D8, D9 APPROVED; R6 and R7 kept UNRESOLVED with R7-A, R7-B, R7-C NOT SELECTED; the 2026-10-28 regression check authorised and passed |
| UNRESOLVED | R6 to R14; every licence, tokenizer licence, training-data term, revision, file list, download host and boundary; the dataset, annotation, quota, coverage, calibration, metric and activation criteria |
| BLOCKED | D10, D11, D12, D13; any metadata query, download, installation outside the disposable test, dataset collection, annotation, evaluation and activation; TASK-CERT-1 |

### Activation gate (Phase 8): every item, as of today

| Required before a Transformer may be activated | State |
| --- | --- |
| approved dependency versions and security position | MISSING (A2 covers isolated verification only; D12, D13 blocked) |
| approved model licence | MISSING (R6, R7 unresolved) |
| approved training-data and tokenizer terms | MISSING |
| approved immutable revision | MISSING |
| approved download files and hosts | MISSING |
| approved hashes | MISSING (no download exists) |
| approved dataset and annotation process | MISSING (R8 to R10) |
| completed independent evaluation | MISSING (nothing to evaluate) |
| approved metrics and confidence intervals | MISSING (R11 to R13; the intervals are not implemented) |
| acceptable coverage; calibration policy passed | MISSING |
| privacy tests passed | MET for the rules path and for the model path against fake backends; not yet for a real model |
| fallback tests passed | MET against fake and stand-in backends |
| artifact provenance verified | MET for locally generated stand-in artifacts only |
| threat-model review complete | MISSING (`docs/THREAT_MODEL.md` has a sentiment section; no activation review is recorded) |
| R14 activation approval recorded | MISSING |

Exact blocker: **R6 / R7 selection, then D10 to D13, then R8 to R14.** `SENTIMENT_MODEL_ENABLED` stays `false` and the rules baseline stays active.

### Tests run in this phase (they actually ran)

- Baseline before any change: 697 passed, 2 skipped (user-text, insight API, model-loader, provenance, tokenizer-integrity and training groups).
- After the fix: the same groups plus the 20 hypothetical tests and the 5 ledger-boundary tests, together with the documentation / approval guard tests (`test_ai_gates_snapshot`, `test_guards_gates`, `test_dry_run_package_audit`, `test_regression_tests_are_effective`): **849 passed, 2 skipped, 0 failed** in one run (2026-10-28, project interpreter, no concurrent process; 844 before the five ledger-boundary tests were added).
- Mutation check of the new rule: 8 mutations (no clause hypothetical; no consequent carry-over; model shown hypothetical clauses; hypothetical preferences inferred; hypothetical-only text not `uncertain`; indirect questions treated as conditions; a contrast never ending a consequent; hypothetical cues still read as feelings), one process each, in memory, repository file untouched: **8 of 8 detected**.
- Frontend: `npx tsc -b` exit 0; `npx oxlint` exit 0 (warnings only, in files outside the sentiment feature); `npm test` 174 passed; `npm run typecheck:tests` exit 0; `npm run test:mutations` **150 of 150** mutations detected.
- Generated-type consistency: `app.openapi()` into a scratch file, `openapi-typescript` 7.13.0 into a scratch file, diff against `frontend/src/types/api.ts`: **0 differing lines**.
- Skipped, with the reason: `test_transformer_standin.py` (needs `torch`, absent from the project environment by design) and one loader test (symbolic links are not permitted for this account).
- Not run: the database-backed suite (no schema or database change), browser tests, any real model, training or inference, the disposable S1 environment.

### Files changed in this phase

`backend/wealthpilot/core/user_text_sentiment.py` (hypothetical / conditional handling); new `tests/backend/core/test_user_text_hypothetical.py` and `tests/backend/core/test_sentiment_ledger_boundary.py`; documentation: this record, `reports/sentiment_transformer_dependency_request.md`, `docs/DECISIONS.md`, `docs/MEMORY.md`, `docs/TEST_PLAN.md`, `docs/THREAT_MODEL.md`. No dependency manifest, configuration, `.env.example`, frontend file, generated type, model-loader or trainer file changed.

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no model, tokenizer, dataset, revision query or user text accessed; no package installed; intensity regression disabled; sentiment isolated from risk, goals, portfolio, recommendations, savings-first logic, compliance, financial calculations and any trade or payment action; no raw text persisted, logged, cached, transmitted or placed on a ledger; no blockchain payload containing sentiment or personal data.

## Decision recorded 2026-10-28 (fifteenth brief) — two independent preparation tasks authorised: the annotation rubric update and offline evaluation-statistics support

**Recorded before execution.** The owner authorised two independent, offline preparation tasks. Nothing in them queries Hugging Face or model metadata, downloads weights or datasets, installs a package, collects user text, enables the Transformer, or changes production behaviour. The owner asked that routine implementation decisions be made conservatively without stopping, and that work stop only for a public API, legal / licensing, privacy, security or production-activation decision.

### Task 1 — approval to update `docs/USER_TEXT_ANNOTATION_RUBRIC.md` (recorded before the edit)

**Approved edit:** the smallest precise change that covers hypothetical, conditional, wish and counterfactual statements: (1) a coverage rule that such statements are not labelled as the person's current sentiment, tone or preference; (2) a labelling rule with examples ("If the market crashes, I would be worried" is not a current view; "If I had more money, I would want higher returns" is not a current preference; "I feel safe even if prices fall" keeps the current clause); (3) the existing rules for quotes, other people, past feelings, negation, ambiguity and mixed clauses stay; (4) no existing label or example changes unless consistency requires it; (5) the new SHA-256 of the rubric and of its annotator excerpt is computed and only the directly related manifest and hash records and tests are updated; (6) no labelled data is invented and the rubric is not described as validated.

**Status of the rubric, recorded so it is not misread:** the brief calls the rubric "frozen". The repository records it as `v0-draft`, **not frozen** (`DRAFT_MANIFEST.json`: `manifest_status = DRAFT`, `frozen = false`, `distribution_ready = false`, annotation NOT STARTED, no participant named). The edit therefore changes a draft that no annotator has received, and it stays a draft afterwards; it is **not** a freeze and starts no annotation. The earlier statement in `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md` that the rubric is "deliberately not edited" described the position before this approval; it receives a dated superseded-by note.

### Task 2 — approval to prepare offline evaluation-statistics support

**Approved:** reusable, offline, deterministic functions in `training/sentiment/metrics.py` for a future approved dataset: confidence intervals, annotator agreement, per-class and per-group breakdowns, coverage and abstention reporting, calibration reporting, a rules-baseline comparison, explicit handling of undersized groups; standard library plus the already approved `numpy` only. Where a method needs a new package or a methodological owner decision, only the dependency-free part is built and the blocker is recorded. **Safeguards (as given):** a confidence score is never treated as validated without labels; no metric computed from synthetic stand-in data counts as production evidence; no validation is claimed while no approved dataset exists; accepted-prediction precision, coverage and abstention stay distinct; unsupported or undersized groups are reported explicitly; the production rules baseline is not changed; the metrics are not connected to activation.

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no model, tokenizer, dataset, revision query or user text accessed; no package installed; no network call; intensity regression deferred; sentiment isolated from risk and all financial calculations; no sentiment or personal data on a ledger or blockchain.

## Rubric update and evaluation-statistics support (fifteenth brief) — 2026-10-29: both preparation tasks done offline; nothing activated, nothing accessed

Written for the project owner. The two tasks authorised in the section above ran in full. No Hugging Face or model-metadata query, download, dataset, installation, user text, network call, activation or production change took place, and no hard gate (public API, legal / licensing, privacy, security, activation) was reached.

### Task 1 — annotation rubric: rules 11 and 12 added (VERIFIED FACT)

**What changed in `docs/USER_TEXT_ANNOTATION_RUBRIC.md`** (a draft that no annotator has received): (1) **rule 11**, the coverage rule: hypothetical, conditional, wish and counterfactual statements are not labelled as the person's current `sentiment`, `emotional_tone` or `preferences`, and their topics are still tagged; (2) **rule 12**, the labelling rule: a hypothetical-only text is `uncertain` with no tone and no preference; a text that also states a current view is labelled on that view only; a condition that only qualifies a statement true now does **not** make it hypothetical ("I feel safe even if prices fall" keeps its current clause); quoted or attributed hypothetical wording is not the person's own view; negating a hypothetical does not make it current; a hedged want stays tagged `hedged` while a want that exists only under a condition is not tagged; a six-row table of examples marked as illustrations, not dataset records; (3) a revision note in the header; (4) two bullets in section 7 (known rubric risks). Rules 1 to 10, the label sets and the existing examples are unchanged (a test pins the rule leads, their order and the label-set rows).

**Hash status.** The pilot-pack manifest records the hash of the rubric and of the annotator excerpt, and the existing `scripts/build_dry_run_package.py --verify` fails when the rubric changes, so the package was rebuilt with the repository's own builder (`python scripts/build_dry_run_package.py`, then `--verify`: consistent). Nothing was written by hand.

| Item | Before | After |
| --- | --- | --- |
| rubric SHA-256 (`DRAFT_MANIFEST.json` `rubric_sha256`) | `24a8f252e11911c402ced17df08b8da957372cdda2df0d5c7936e8ce52573eb9` | `c77179950111c4ffaedf1564e5ee6466f6f38c753d012e1930672c1b77808fd3` |
| annotator excerpt SHA-256 (`rubric_excerpt_sha256`, and `RUBRIC_EXCERPT.md` in `package_files`) | `01aeab41874de5818372b82caf9e0cc79ad0f83a25282f215444836f2449a69c` | `a7bc2d328c55e9bddece4023ebd609c2713b6a1e3df679ba0ddd83f6bac9cd9b` |
| the 30 fictional texts, the template, `INSTRUCTIONS.md`, `ids_sha256` | unchanged | unchanged (a test pins them) |
| `manifest_status`, `frozen`, `freeze_process_completed`, `rubric_version` | DRAFT, false, false, `v0-draft` | DRAFT, false, false, `v0-draft` |
| `distribution_ready`, `annotation_status` | false, NOT STARTED | false, NOT STARTED |

**It is still a draft.** The brief calls the rubric "frozen"; the repository records it as `v0-draft`, not frozen, and the edit did not freeze it, validate it, start annotation or name a participant. The version label was kept at `v0-draft` (a draft is identified by its hash, and the package builder pins the label); the revision note records the date. The statement in the decision sheet that the rubric is "deliberately not edited" described the position before this approval and now carries a superseded-by note.

**Two findings the owner should know.** (1) The brief assumed the rubric already had rules for quotes, other people's statements and past feelings. It does **not** (those exist in the rules baseline, ADR-050, not in the annotator text), so rules 11 and 12 cover them only where the wording is also hypothetical and the gap is recorded as an open item rather than silently filled. (2) Rule 12 keeps "I feel safe about my savings even if the market falls" as a current positive feeling, but the rules baseline drops any clause with a conditional marker and does not label it positive. The baseline was **not** changed (the brief forbids a production change); the disagreement is documented in section 7 of the rubric and pinned by a test, and it is to be reported, not hidden.

**Tests (all passing):** `tests/backend/core/test_user_text_rubric_hypothetical.py` (20): rules 11 and 12 are in the excerpt annotators receive; the six examples carry the stated outcomes; every example uses only the rubric label sets; rules 1 to 10 and the label sets are unchanged; the excerpt contains no author-only wording; the rubric claims neither validation nor a freeze; the baseline gives no label, tone or preference for hypothetical, wish and negated-hypothetical text; quoted and third-person hypothetical text is never the user's view; a current clause beside a hypothetical one is labelled; five current statements are handled exactly as before; the one documented disagreement is still real and still documented. `tests/backend/scripts/test_rubric_hash_records.py` (2): the manifest records the current hashes and still says draft / not frozen / not started, and the other package hashes are untouched. The repository guard that forbids a test from running the baseline on the pilot texts caught my first layout (manifest and baseline in one file); the manifest checks moved to their own file. **Not done:** a mutation check of the rubric tests (the assertions are exact-phrase checks, so they are sensitive by construction, but that was not demonstrated).

### Task 2 — offline evaluation statistics in `training/sentiment/metrics.py` (VERIFIED FACT)

Standard library plus `numpy` (1.26.4, already approved); no dependency was added. The older `classification_report`, `expected_calibration_error`, temperature fitting, threshold selection and `regression_metrics` are unchanged (`classification_report` still returns 0.0 for an undefined precision because the training pipeline and its tests rely on it; the new functions never do). `evaluate_sentiment_model.py` is **unchanged and not connected**.

| Function | What it computes | Method |
| --- | --- | --- |
| `StatisticsPlan` (required everywhere; `.proposed()` builds the proposals) | confidence level, resamples, seed, minimum group support, minimum class support, `approved` flag | validated; echoed in every output; the proposed values are labelled "PROPOSED defaults, not approved"; `min_class_support` has no proposal and prints "unresolved" |
| `EvidenceBasis` (required; no default) | whether the data is approved, a development fixture, synthetic | `not_validation_evidence` unless approved, not a fixture and not synthetic; even then only `eligible_for_owner_review`; `validation_claimed` and `confidence_scores_validated` are always false; activation is stated to be the separate R14 decision |
| `wilson_interval` | interval for a proportion | Wilson score, exact 0 / 1 bounds at 0 or n successes, `None` for n = 0 |
| `evaluate_predictions` | strict accuracy and macro-F1; accepted-prediction precision and selective macro-F1; coverage and abstention rate; per-class precision, recall (Wilson) and F1 (bootstrap); confusion matrix with an `abstained` column | strict counts an abstention as a miss; selective looks at accepted predictions only with the coverage beside it; macro-F1 averages only classes with a defined F1 and is `None` when fewer than two true classes exist; stratified percentile bootstrap for F1 |
| `grouped_report` | the same measures per dimension and value (dimensions and values sorted; a record may belong to several values) | groups below the minimum support are `descriptive_only` (no interval), empty or required-but-absent groups are `no_data`; `groups_not_supported` lists them all |
| `calibration_report` | reliability bins (fixed order, empty bins shown as `None`), ECE over all scored and over accepted predictions, Wilson interval per supported bin, `sparse` flag | reuses `expected_calibration_error`; records without probabilities are counted and excluded; malformed probabilities raise; `validated` is always false |
| `compare_predictions` | two candidates (for example a model and the rules baseline) on the same examples: each summary, discordance counts, paired difference in strict accuracy, strict macro-F1 and coverage | paired stratified bootstrap; `interval_excludes_zero` is descriptive; no p-value, ranking or winner |
| `cohen_kappa`, `specific_agreement`, `krippendorff_alpha_nominal`, `agreement_report` | agreement between named annotators: pairwise kappa with bootstrap interval, observed and chance agreement, per-label specific agreement, Krippendorff's alpha (any number of annotators, missing ratings allowed) | unlabelled items excluded and counted; `None` with a reason when undefined (chance agreement 1, fewer than two usable ratings) |
| `evaluation_report` | summary + groups + calibration of one candidate | assembly only; decides nothing |

Determinism: records are put in item-id order before anything is computed, dictionary order is fixed, the bootstrap draws from a generator created from `plan.seed` inside each call, and the point estimates and every replicate come from one counting function. Safeguards enforced in code and tests: no default plan or evidence basis; unknown labels, duplicate ids, a bare-string group value and malformed probabilities raise instead of being repaired; no NaN or numpy value reaches the output; the module imports only `math`, `dataclasses`, `statistics`, `typing`, `numpy` and the project's own `training` package, and uses no file, network or `print`; no target (0.80, 0.85), threshold, pass / fail or activation field exists anywhere in a report (a test walks every key).

**Tests:** `tests/training/sentiment/test_sentiment_statistics.py` (39), checked against hand computations: perfect and imperfect predictions (a worked 70-example case: strict macro-F1 (50/55 + 1 + 30/40) / 3, selective macro-F1 (50/55 + 1 + 30/35) / 3, accepted precision 60/65, coverage 65/70); abstentions, including a candidate that abstains on everything; empty input for every report; one-class and never-seen classes; the minimum-support boundary (20 inclusive, 19 not); group reporting; ordering independent of input order and of repeated runs; seed changes only the intervals; Wilson known values (50/100 gives 0.4038 to 0.5962; 10/10 low 0.7225) and exact boundaries; plan validation; kappa 0.4 on the textbook table, perfect and reversed; Krippendorff alpha 1 - 10/18 on the hand table, missing ratings, undefined cases; calibration bins and ECE (0.05 on the hand case), sparse bins, no-prediction cases; the rules-versus-model comparison (discordance 25 / 10 / 1 / 4, difference 0.225); evidence eligibility for all five combinations; no validation, pass / fail or target field anywhere; no unavailable number is NaN or zero; no new dependency. **The tests caught one real defect while I was writing them:** the confusion matrix listed its abstained column first while labelling it last; fixed in the code. **Mutation check:** 22 deliberate defects, one process each, in memory, repository file untouched (wrong Wilson sign, lost exact bounds, abstention not a miss, seed ignored, no canonical order, undersized samples given intervals, exclusive boundary, one-class macro-F1, kappa and alpha formulas, synthetic data no longer disqualifying, confidence called validated, reversed difference, coverage inverted, bare-string groups accepted, empty sample not reported, sparse bins given intervals, specific agreement, strict denominator, accepted precision denominator, unlabelled items in kappa, matrix column order): **22 of 22 detected** (the first run missed one because it targeted a value nothing read; that dead key was removed and the mutation re-aimed at the real accepted-precision path).

### Remaining methodological approvals (each is the owner's; none is assumed)

1. **The interval methods and their values** (Wilson for proportions; stratified percentile bootstrap; level 0.95; 2,000 resamples; seed 42): still PROPOSALS. A BCa bootstrap or an exact (Clopper-Pearson) interval would need a decision and, for the exact interval, a root-finder the standard library does not provide.
2. **Support thresholds:** the minimum group support (20) is a proposal; the **minimum class support has no proposed value** and "no validation if a primary class has inadequate support" cannot be applied until it is set.
3. **Agreement:** which statistic is primary (Cohen's kappa per field or Krippendorff's alpha), and the agreement floor. The code handles one single-label field at a time (sentiment). **Multi-label fields (topics, preferences) and the two-flag fields need a method decision** (for example one binary kappa per label) before they are implemented; no method was invented.
4. **Calibration and selection criteria:** the number of bins (10 is a code parameter, not a decision), the ECE ceiling, the minimum coverage and the per-class recall floor have no values. The proposed targets (macro-F1 0.80; precision 0.85 on accepted predictions) are **not encoded anywhere** and no report says whether they are met, on purpose.
5. **Comparison with the rules baseline:** the paired bootstrap difference is descriptive. Whether a significance test (for example an exact McNemar test), a multiplicity correction or a minimum meaningful difference is wanted is undecided and not implemented.
6. **Which label set an evaluation uses** (the three classes a Transformer head has, or the rubric's five with `mixed` and `uncertain` reported separately as the protocol says): the functions accept either; the choice is the owner's.
7. **Wiring:** connecting these functions to `evaluate_sentiment_model.py`, deriving `EvidenceBasis` from an approved `DatasetManifest` (today the caller states it), and writing a report to disk each need a separate code approval and an approved dataset.
8. **A dataset, annotators and an annotation process (R8 to R13)** remain unresolved, so none of this has ever been run on real labels, and no accuracy, agreement or calibration figure for any real classifier exists.

### Final test run for this phase (they actually ran)

One run on 2026-10-29, project interpreter, no concurrent process: the user-text, rubric, pilot-pack, package-builder, insight-API, model-loader, provenance, tokenizer-integrity, training, ledger-boundary and documentation-guard groups: **1121 passed, 3 skipped, 0 failed**. Skips, with the reason: `test_transformer_standin.py` (needs `torch`, absent from the project environment by design); `test_sentiment_model.py` (symbolic links are not permitted for this account); `test_dry_run_package_adversarial.py` (creating symlinks needs a privilege this machine lacks). `scripts/build_dry_run_package.py --verify`: package and DRAFT manifest consistent. Not run: frontend suites (no frontend file changed), database-backed suites, browser checks, any real model, training or inference, the disposable S1 environment.

### Open owner items created or confirmed by this task

(a) Add explicit rubric rules for plain quotations, statements about other people and past feelings (the rubric has none). (b) Decide how the rubric and the baseline should agree on "even if" clauses (the baseline is deliberately conservative). (c) The items 1 to 7 above.

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no model, tokenizer, dataset, revision query or user text accessed; no package installed; no network call; intensity regression deferred; sentiment isolated from risk and all financial calculations; no sentiment or personal data on a ledger or blockchain; no code in `core/`, the loader, the trainer, the evaluation script or the API changed.

## Decision recorded 2026-10-29 (sixteenth brief) — remaining offline evaluation-policy work: what is authorised, and what stays unresolved

**Recorded before execution.** The owner asked for the remaining offline evaluation-policy work, to be done conservatively without stopping for routine choices, stopping only for a legal, licensing, privacy, external-network, dataset, production-activation or public-API decision. Everything stays offline; no Hugging Face or model-metadata query, download, dataset, installation, user text, Transformer enablement or production change is authorised.

### What the brief decides, and what it does not (recorded so nothing is read into silence)

| Item | Status recorded |
| --- | --- |
| Rubric / baseline alignment for "even if" (`ALIGN_BASELINE_TO_RUBRIC`, `ALIGN_RUBRIC_TO_BASELINE`, `KEEP_DOCUMENTED_DIFFERENCE`) | **UNRESOLVED.** The brief names the three outcomes and says to keep the decision unresolved and to change neither production code nor the rubric on that point if no choice is supplied. None is supplied. Rule 12 of the rubric and the baseline stay exactly as they are. |
| Explicit rubric coverage for plain quotations, other people's statements and past feelings | **AUTHORISED** as an addition (the brief asks for it explicitly, "without inventing labels"). Read conservatively: it states that these are not the person's current view (the accepted ADR-050 position the baseline already implements) and routes every unsettled case to `rubric_unclear`; it prescribes **no new label** and no example table. The other four listed cases (hypothetical, negated hypothetical, a current statement with a qualifying condition, mixed current and hypothetical) are already covered by rules 11 and 12. |
| Statistical-policy values (levels, resamples, seed, supports, agreement, calibration, targets, significance testing) | **No value is approved.** The brief supplies candidates only (95%, 2,000, 42, 20, 0.80, 0.85) and forbids encoding a threshold as an activation rule. A decision matrix is prepared; the policy-dependent metric changes (its Task 3) are conditioned on approval and are therefore **not made**. |
| Evaluation-script integration | **Design only**, plus implementation only where it needs no approved value, real data or real model. |
| Annotation-policy gaps | Recorded as **unresolved decisions** in the validation decision sheet; no statement is created or labelled. |

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no model, tokenizer, dataset, revision query or user text accessed; no package installed; no dependency manifest changed; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no sentiment or personal data on a ledger or blockchain. The rubric stays `v0-draft`, not frozen; pilot-pack hashes change only through `scripts/build_dry_run_package.py`.

## Evaluation-policy preparation (sixteenth brief) — 2026-10-29: alignment UNRESOLVED; rule 13 added; policy matrix prepared; no value approved; nothing integrated or activated

*Superseded later the same day: the owner decided every item of this section; see "Owner decisions recorded 2026-10-29 (seventeenth brief)" and "Policy implementation results (seventeenth brief)". This section is kept as the historical record of the undecided state.*

Written for the project owner. Nothing was queried, downloaded, installed or collected; no Hugging Face or model access, no dataset, user text, network call, package, Transformer enablement or production change took place; no hard gate was reached.

### Task 1 — rubric / baseline alignment: UNRESOLVED (VERIFIED FACT)

**The decision is not recorded because the brief supplied none** (`ALIGN_BASELINE_TO_RUBRIC`, `ALIGN_RUBRIC_TO_BASELINE` and `KEEP_DOCUMENTED_DIFFERENCE` were named; no choice was made). Rule 12 and the baseline are unchanged. The options, their consequences and a recommendation that is not a decision (`KEEP_DOCUMENTED_DIFFERENCE` for the dry run, then decide from observed frequency) are item AP4 of `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md`; its owner entry is blank.

**Explicit rubric coverage requested, and how each case stands:**

| Case | Where it is covered | Notes |
| --- | --- | --- |
| plain quotations | **new rule 13** | gives no current view; no label prescribed; unsettled cases go to `rubric_unclear` |
| other people's statements | **new rule 13** | as above |
| past feelings | **new rule 13** | as above |
| hypothetical / conditional | rules 11 and 12 (2026-10-28) | unchanged |
| negated hypothetical | rule 12 and its table | unchanged |
| a current statement with a qualifying condition | rule 12, third bullet and the "I feel safe even if prices fall" row | unchanged; the disagreement with the baseline is the open AP4 |
| mixed current and hypothetical | rule 12, second bullet and the fourth table row | unchanged; the baseline loses the current part when no comma separates the clauses (AP6) |

Rule 13 adds **no label, no example and no table row**; it says that these cases give no current sentiment, tone or preference and routes every case it cannot settle to `rubric_unclear`. It first said, as I drafted it, that topics in such wording are still tagged; the decision-sheet work showed the baseline tags none there, so that sentence was **removed** rather than create a new disagreement, and topic tagging is the open item AP9.

**Pilot-pack hashes** (rebuilt only with `python scripts/build_dry_run_package.py`, then `--verify`: consistent). The rubric is still `v0-draft`, DRAFT, not frozen, `distribution_ready = false`, annotation NOT STARTED; the 30 fictional texts, template and instructions are unchanged.

| | Previous (2026-10-28) | Now |
| --- | --- | --- |
| rubric SHA-256 | `c77179950111c4ffaedf1564e5ee6466f6f38c753d012e1930672c1b77808fd3` | `5a5be11cbe06f0685c91d17670c814c42b1373202d852a70e8d905ed1fbc48a2` |
| annotator excerpt SHA-256 | `a7bc2d328c55e9bddece4023ebd609c2713b6a1e3df679ba0ddd83f6bac9cd9b` | `cc465ffdaad2f4452987df62955146c5664bd929817878d6c5018ba999f93f22` |

**Findings from verifying the baseline against each category (the probe sentences were scratch only and are in no document):**
1. A text that is only a past feeling is read as **neutral and weak**, while a quotation-only or other-person-only text is **declined**: the "nothing current remains" outcome is not uniform. This is why rule 13 prescribes no label (AP1 to AP3).
2. A current clause joined to a conditional clause by "and" **without a comma** is lost: the whole sentence is one conditional clause. With a comma it works. This is a second rubric / baseline disagreement beyond "even if" (AP6). It is pinned by a test and documented in section 7 of the rubric. The baseline was not changed.
3. Topics inside a quotation or another person's clause are not reported by the baseline, whereas rule 4 read literally would tag them (AP9).
4. The baseline has no `hedged` flag, so that annotation field can never be compared with it (AP8).
5. The decision sheet's step 2 recommended running `v0-draft` unchanged; the owner-approved edits supersede that in part (noted in the sheet).

### Task 5 — annotation-policy gaps: nine unresolved decisions recorded

AP1 quotations, AP2 other people, AP3 past feelings, AP4 "even if" (the alignment decision), AP5 hypothetical-only, AP6 mixed current / hypothetical, AP7 negated hypothetical, AP8 hedged versus conditional preferences, AP9 topic tagging when the sentiment is not current: each in the decision sheet with the rubric position, the verified baseline behaviour, options and a non-binding recommendation; every owner entry blank; no statement created or labelled; the sheet's guards (seven original decision rows, no invented number) still hold.

### Task 2 — statistical-policy decision matrix (NO VALUE IS APPROVED)

Status vocabulary: **PROPOSED** = a candidate recorded by the owner (source in the third column); **CODE PARAMETER** = a value the code needs but nobody decided; **UNRESOLVED** = no candidate exists. Every row's owner decision is blank. "In code today" says what `training/sentiment/metrics.py` does (implemented in the fifteenth brief, tests passing); nothing there encodes a threshold or is connected to activation.

| # | Decision | Candidate | Source | In code today | Owner decision |
| --- | --- | --- | --- | --- | --- |
| 1.1 | Interval for proportions (accuracy, precision, recall, coverage) | Wilson score | brief; dependency report E.2 | implemented; exact 0 / 1 bounds; `None` for no examples | UNRESOLVED |
| 1.2 | Interval for F1, kappa, paired differences | stratified percentile bootstrap | brief; dependency report E.2 | implemented for F1 and differences (stratified by true label, paired); **the kappa interval resamples items without stratification**, because kappa has no true class to stratify by | UNRESOLVED; what, if anything, to stratify kappa by is a further question |
| 1.3 | Confidence level | 95% | brief | `plan.confidence`, required | PROPOSED |
| 1.4 | Bootstrap resamples | 2,000 | brief | `plan.resamples`, required (minimum 100) | PROPOSED |
| 1.5 | Seed | 42 | brief; repository convention | `plan.seed`, required | PROPOSED |
| 1.6 | Alternatives (exact Clopper-Pearson, BCa bootstrap) | none proposed | — | not implemented; the exact interval needs a root-finder or beta quantile the standard library lacks, and `scipy` is approved only for portfolio optimisation | UNRESOLVED |
| 2.1 | Minimum support per primary class | at least 75 each where feasible (quota 80 each) | dependency report G | `plan.min_class_support`, **None** (flag only when set); not enforced | PROPOSED, not wired |
| 2.2 | Minimum support for subgroup reporting | 20 | brief | `plan.min_group_support`, required; below it a group is `descriptive_only` | PROPOSED |
| 2.3 | Empty groups | report as `no_data`, never drop | brief (required behaviour) | implemented, including required-but-absent groups | confirm |
| 2.4 | Descriptive-only groups | report values and counts without an interval | brief | implemented | confirm (alternative: withhold values too) |
| 2.5 | Class balance | positive, negative, neutral 80 each; mixed 30; uncertain 30 | dependency report G | not enforced; supports are reported | PROPOSED |
| 2.6 | Minimum held-out size | 300 ("a proposed minimum, not automatic proof of validity") | dependency report G | not enforced | PROPOSED |
| 3.1 | Primary agreement statistic for sentiment | Cohen's kappa between the two independent annotators, Krippendorff's alpha as cross-check | dependency report E.2 | both implemented | PROPOSED; which is primary UNRESOLVED |
| 3.2 | Agreement floor | none | — | none | UNRESOLVED |
| 3.3 | Secondary statistics | observed agreement, per-label specific agreement, alpha | dependency report E.2 | implemented | confirm |
| 3.4 | Adjudication handling | agreement computed on the two independent pre-adjudication labels; the adjudicated label is the reference; report how many items needed adjudication | candidate (assistant's reading of the proposed protocol) | the adjudication count is **not** implemented | UNRESOLVED |
| 3.5 | Multi-label agreement (topics, preferences) | no proposal. Candidates: (a) one binary kappa per label, reported per label with its support and no pooled value (dependency-free, built from the existing function); (b) a set-distance alpha (more code); (c) exact-set match (strict) | assistant's candidates, not proposals | **not implemented** | UNRESOLVED |
| 4.1 | Number of calibration bins | 10 | code parameter | `bins=10` | CODE PARAMETER |
| 4.2 | ECE method | equal-width, top-class confidence (as in the existing function) | existing code | implemented; reused, not duplicated | UNRESOLVED (alternatives: adaptive bins, class-wise ECE) |
| 4.3 | ECE ceiling | none | — | none | UNRESOLVED |
| 4.4 | Minimum sample for calibration | per-bin interval from the subgroup support (20); no overall minimum | brief; none | bins below 20 are flagged `sparse` | PROPOSED / UNRESOLVED |
| 4.5 | Treatment of abstentions | report both views | brief | `all_scored` and `accepted_only` | UNRESOLVED which one governs |
| 4.6 | Selective versus strict calibration | strict = every scored item whatever the abstention; selective = accepted predictions only. An abstention has no correctness, so a "strict" view in the sense used for accuracy does not exist | assistant's reading | the two blocks exist under the names `all_scored` and `accepted_only` | naming and meaning UNRESOLVED |
| 5.1 | Macro-F1 target | 0.80 | brief | **not encoded** | PROPOSED; which view (strict or selective) and whether the point estimate or an interval bound must clear it UNRESOLVED |
| 5.2 | Accepted-prediction precision target | 0.85 | brief | **not encoded** | PROPOSED |
| 5.3 | Per-class recall floor | none | — | none | UNRESOLVED |
| 5.4 | Minimum coverage | none | — | coverage reported | UNRESOLVED (needed so that high precision reached by abstaining does not qualify) |
| 5.5 | Maximum abstention | none | — | abstention rate reported | UNRESOLVED |
| 5.6 | Confidence-interval policy for targets | none | — | intervals reported, never compared with a target | UNRESOLVED |
| 5.7 | Rules-baseline comparison policy | paired difference with discordance counts, descriptive | dependency report E.2 | implemented; no p-value, no ranking | PROPOSED; the criterion for "better" UNRESOLVED |
| 5.8 | No-winner policy | no winner when the evidence is not eligible, a primary class or compared group is undersized or empty, the paired interval contains zero, or a coverage floor is unmet | assistant's candidate | no winner is ever produced | UNRESOLVED |
| 6 | Significance testing | not required unless the owner approves one. Dependency-free options exist: an exact McNemar test or a permutation test from the standard library. Any `scipy.stats` use would need a dependency approval (`scipy` is approved only for portfolio optimisation) | brief | none; no p-value | the current no-p-value behaviour is retained; UNRESOLVED |
| 7 | Label set of an evaluation | the three classes a Transformer head has, or the rubric's five with `mixed` and `uncertain` reported separately | dependency report E / rubric section 6 | the functions accept either | UNRESOLVED |
| 8 | May a report ever say "validated" | the brief allows it only when the evidence basis is approved and complete; today no report says it, even for eligible data | brief | never | UNRESOLVED; to be decided with the activation criteria (R14) |

No row requires a new package. The only items that would are an exact interval and any `scipy.stats` test, and both are outside what the matrix proposes.

### Task 3 — metric-policy implementation: NOT STARTED (conditioned on approval)

The brief makes the policy-dependent changes conditional on explicit approval of the values, and none is approved, so `training/sentiment/metrics.py` is **unchanged** in this phase. Required behaviours against the current code: undefined values as `None` with a reason, empty and undersized groups reported, deterministic ordering, strict and selective kept separate, accepted precision distinct from coverage, abstentions explicit, a paired rules-baseline comparison with discordance, and no winner or activation output **already exist and are tested (fifteenth brief)**. What does **not** exist and waits on a decision: multi-label agreement (3.5); the adjudication count (3.4); a calibration view whose meaning is agreed (4.5, 4.6); enforcement of class support and held-out size (2.1, 2.5, 2.6); any comparison with a target (5.x); a report that may say "validated" (8). The plan values are parameters, so approving or changing a value needs no code change.

### Task 4 — evaluation-script integration: DESIGN ONLY; implementation blocked (nothing connected)

`training/sentiment/evaluate_sentiment_model.py` is unchanged and still does not use the statistics. The smallest safe integration, in order:

1. Load a **frozen** manifest. `DatasetManifest` today has no hash fields; the freeze manifest of rubric section 5a (SHA-256 of the rubric, texts file and every labels file, record and per-class counts, the O5 / O6 decisions in force, the baseline `METHOD_VERSION`, annotator and adjudicator codes, adjudication-log hash, date) is not built and its schema needs approval.
2. Verify the SHA-256 of the texts and labels files against the manifest before reading a row; refuse on any mismatch.
3. Build `EvidenceBasis` **only** from the manifest (`approved`, `development_fixture`, and a new `synthetic` field), never from a command-line flag. `EvidenceBasis` should gain the conditions the brief names for "approved and complete" (frozen, hashes verified, independent labels attested, plan approved) before any report may say more than `eligible_for_owner_review`.
4. Split with the existing group-aware seeded `split_rows` (train, validation as the calibration set, test as the held-out set) and `check_no_leakage`; exact duplicates are already removed on load, **near-duplicate removal is not implemented** (the proposal is token-set similarity plus shared templates).
5. Run `rules_baseline` (existing) and, only when a model is approved and installed (D12), the artifact; convert each answer to an `EvalRecord` (an abstention is `None`). The labelled file needs group tags (topic, difficulty, negation, contradiction, language) that `LabelledRow` does not carry.
6. Emit `evaluation_report` per candidate, `compare_predictions` for the baseline against each model, and `agreement_report` when annotator files are supplied, to a JSON file; list `groups_not_supported`; **no exit code, field or message depends on a target**, and the script imports nothing from the API, settings or activation path.
7. Print a one-line summary that repeats the evidence status.

**Blockers, exactly:** (a) no policy value is approved; (b) the frozen-manifest schema and its hash verification need a code approval; (c) no approved dataset exists (R8 to R13); (d) the label-set decision (row 7); (e) group tags are missing from the data format; (f) near-duplicate removal is unbuilt; (g) a model needs D12 and the R6 / R7 chain. Nothing in this design can run on real data, a real model or the production route, and no part of it was implemented because every part either depends on an unapproved value or on a schema that is itself an owner decision.

### Tests (they actually ran)

One run on 2026-10-29, project interpreter, no concurrent process: the user-text baseline, hypothetical, rubric, pilot-pack, package-builder, evaluation-policy-record, ledger-boundary, insight-API, model-loader, provenance, tokenizer-integrity, training (including the statistics tests) and documentation-guard groups: **1140 passed, 3 skipped, 0 failed**. Skips, with the reason: `test_transformer_standin.py` (needs `torch`, absent from the project environment by design); `test_sentiment_model.py` (symbolic links are not permitted for this account); `test_dry_run_package_adversarial.py` (creating symlinks needs a privilege this machine lacks). `scripts/build_dry_run_package.py --verify`: package and DRAFT manifest consistent. Mutation checks re-run because the baseline and `metrics.py` were not changed but the tests around them were: 22 of 22 statistics mutations and 8 of 8 hypothetical-statement mutations detected (no mutation check of the new rubric, policy-record or decision-sheet guards was run; their assertions are exact-text and key checks). Two of my own guards failed at first and were corrected: a test that matched the word "activation" in a docstring, and one that parsed the decision cells too literally. The earlier repository guard against running the baseline on the pilot-pack texts still holds (no new file mentions both). Not run: frontend, database, browser, real-model, real-training or dataset tests (no such file changed).

### Remaining hard approvals

1. **AP4** (the three outcomes) and, with it, AP6; **AP1 to AP3, AP5, AP7 to AP9** (the annotation-policy decisions).
2. **The statistical-policy values** of the matrix (rows 1.1 to 8), in particular the support thresholds, the primary agreement statistic and floor, the multi-label method, the calibration criteria and the targets together with their view and interval policy.
3. **A code approval** for the frozen-manifest schema, hash verification, group tags, near-duplicate removal, and then the integration itself.
4. The chain already recorded: R6 / R7, D10 to D13, R8 to R13 (dataset and annotation), **R14** (activation).

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no model, tokenizer, dataset, revision query or user text accessed; no package installed; no dependency manifest changed; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no sentiment or personal data on a ledger or blockchain; no code in `core/`, the loader, the trainer, the evaluation script, `metrics.py` or the API changed.

## Owner decisions recorded 2026-10-29 (seventeenth brief) — annotation and evaluation policy: every item decided; recorded before any dependent code

**How these were obtained.** The brief is a decision form: it lists the choices, marks many values "recommended" or "proposed", and states none as chosen. A recommendation is not an approval, so before recording anything I asked the owner two explicit questions and recorded the answers: (1) *"Do you approve recording exactly those stated recommended / proposed values as your explicit decisions?"* — answer **"Approve all stated values"**; (2) *"May I record my conservative proposal for the items with no stated value as your decision?"* — answer **"Adopt your proposal"**, a list given in the question. The decisions below are exactly those two answers applied to the brief, nothing more. Scope fixed by the brief: offline only; no Hugging Face or metadata query, model, tokenizer, revision, dataset, user text, package, network call, Transformer enablement or production change; **no change to the production baseline unless AP4, AP6 or the comma-less rule authorises it, and none does**.

### A. Annotation and rubric policy (owner decisions)

| Item | Decision | How it was obtained |
| --- | --- | --- |
| AP1 quotations | `NO_CURRENT_VIEW` | adopted proposal |
| AP2 other people's statements | `NO_CURRENT_VIEW` | adopted proposal |
| AP3 past feelings | `NO_CURRENT_VIEW` | adopted proposal |
| AP4 current statement qualified by "even if" | `KEEP_DOCUMENTED_DIFFERENCE` (rubric rule 12 and the baseline both stay; direct model-versus-rubric comparability for this case is not claimed) | adopted proposal |
| AP5 hypothetical-only text | `UNCERTAIN_WEAK` | stated value |
| AP6 mixed current and hypothetical | `LABEL_CURRENT_ONLY` | stated value |
| AP7 negated hypothetical | `NO_CURRENT_VIEW` | stated value |
| AP8 hedged versus conditional preference | `HEDGED_CURRENT_CONDITIONAL_NOT_CURRENT` | stated value |
| AP9 topic tagging for non-current wording | `TAG_TOPIC_ONLY` (topics are tagged; no sentiment, tone or preference is taken from the wording) | adopted proposal |
| comma-less "and" before a conditional clause | `RETAIN_DOCUMENTED_BASELINE_BEHAVIOR` | adopted proposal |

**Consequence: the production baseline is not changed.** AP4 keeps the difference, AP6 is a rubric rule (the baseline already labels the current clause when a comma or sentence break separates it), and the comma-less rule retains the baseline's behaviour. The rubric and the decision sheet are updated to say so; the rubric stays `v0-draft` and is not called frozen.

### B. Statistical-policy decisions (owner decisions)

| # | Decision | Value | How obtained |
| --- | --- | --- | --- |
| 1 | Confidence level | 0.95 | stated |
| 2 | Bootstrap resamples | 2,000 | stated |
| 3 | Bootstrap seed | 42 | stated |
| 4 | Bootstrap method | stratified percentile bootstrap for F1 and paired differences; the kappa interval stays the non-stratified item bootstrap (no alternative was chosen) | stated |
| 5 | Minimum primary-class support | 75 per primary class | stated |
| 6 | Minimum subgroup support | 20 | stated |
| 7 | Minimum held-out evaluation size | 300 | stated |
| 8 | Primary label set | `positive_negative_neutral` (`mixed` and `uncertain` are reported separately, not scored as primary classes) | adopted proposal |
| 9 | Primary agreement statistic | `COHEN_KAPPA` for the primary single-label task | stated |
| 10 | Agreement floor | `NO_FLOOR` (agreement is reported, not gated) | adopted proposal |
| 11 | Secondary agreement | report specific agreement and Krippendorff's alpha | adopted proposal |
| 12 | Multi-label agreement (topics, preferences) | deferred | adopted proposal |
| 13 | Adjudication | pre-adjudication agreement is primary; the adjudicated labels are the final reference | adopted proposal |
| 14 | Calibration bins | 10 | stated |
| 15 | ECE method | equal-width bins, with a strict view (every scored item) and an accepted-only view | stated |
| 16 | ECE ceiling | `REPORT_ONLY` | adopted proposal |
| 17 | Minimum calibration sample | descriptive-only below the support of 20 | adopted proposal |
| 18 | Minimum coverage | 0.70 | stated |
| 19 | Maximum abstention | derived: 1 - minimum coverage = 0.30 | adopted proposal |
| 20 | Macro-F1 target | 0.80 | stated |
| 21 | Accepted-prediction precision target | 0.85 | stated |
| 22 | Per-class recall floor | `NO_FLOOR` | adopted proposal |
| 23 | Confidence-interval policy | report the point estimate and the interval; activation requires the point target **and a separately approved lower-bound rule** (that rule is NOT approved) | stated |
| 24 | Rules-baseline comparison | report paired differences and discordance; declare no winner automatically | stated |
| 25 | Significance testing | `NOT_REQUIRED`; no p-values, no new dependency | stated |
| 26 | Validation wording | `validated` only when dataset, rubric, evidence basis, approvals, support and evaluation gates are all complete; otherwise `not_validation_evidence`, `descriptive_only` or `insufficient_support` | stated |

**What approving the targets does and does not do.** Items 18 to 22 become *evaluation gates* a report evaluates and prints (met, not met, or not evaluable, each with the reason). They are **not** activation rules: no code reads them to enable a model, no candidate is ranked or selected, activation remains the separate R14 decision, and item 23 says activation also needs a lower-bound rule nobody has approved.

### Implementation readings I applied (not decided by the owner; recorded so each can be corrected)

1. Where AP1 to AP3 leave "nothing current remains", the rubric uses the same label as AP5: `uncertain`, no tone, no preference. The baseline differs for a past-feeling-only text (neutral and weak) and, in wording, for quotation-only and other-person-only text (it declines to interpret). These stay documented differences; the baseline is not changed.
2. The macro-F1 gate (item 20) does not say which view governs. I evaluate it on **both** the strict and the selective view and call the gate met only if both meet the target (the conservative reading).
3. Items 5 and 7 are checked on the primary label set of item 8; a report on any other label set cannot be assessed against the policy.
4. Item 26's four words are mapped as: evidence basis not eligible gives `not_validation_evidence`; support not met (held-out size, primary-class support) gives `insufficient_support`; everything supported but a gate unmet or not evaluable gives `descriptive_only` with the reasons listed; `validated` only when nothing is missing or unmet.
5. "Strict" calibration (item 15) is the view over every scored item whatever its abstention; an abstention has no correctness, so there is no other meaning of strict for calibration.
6. The polite-form question under AP8 ("would like", "would prefer": a current want or a conditional one) was not decided; the rubric is not changed on it and it stays open.

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no model, tokenizer, dataset, revision query or user text accessed; no package installed; no dependency manifest changed; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no sentiment or personal data on a ledger or blockchain.

## Policy implementation results (seventeenth brief) — 2026-10-29: decisions enforced offline; nothing connected, nothing activated

*Superseded in part later the same day by "Policy implementation results (eighteenth brief)": the frozen-manifest schema was confirmed and wired to the evaluation script (local fixtures only), the lower-bound rule, multi-label agreement and kappa stratification were decided, and the macro-F1 gate is decided by the strict view. Kept as the historical record.*

Written for the project owner. Built on the decisions recorded in the section above. Nothing was queried, downloaded, installed or collected: no Hugging Face or model access, no model, tokenizer, revision, dataset or user text, no package, no network call, no Transformer enablement, no production change. The production baseline (`core/user_text_sentiment.py`) was **not** changed, because AP4, AP6 and the comma-less rule all keep it.

### A. Rubric and decision sheet (VERIFIED FACT)

- **Rubric** (`docs/USER_TEXT_ANNOTATION_RUBRIC.md`, still `v0-draft`, not frozen, not validated, not received by any annotator): rule 13 now reads as decided: quoted text, another person's statements and past feelings give no current sentiment, tone or preference; **topics are still tagged** (AP9); a current view in the person's own words is labelled alone (words that add to it count only for what they say); a text with **nothing current is `uncertain`**, no tone, no preference (the same as AP5); an unclear case is `rubric_unclear`. Section 7 now lists the **documented differences from the baseline**: (a) "even if" (decision: keep the difference, comparison not claimed, reported as a separate group), (b) the comma-less "and" (decision: retain the baseline behaviour), (c) a past-only text (rubric `uncertain`, baseline neutral and weak), (d) topics in quotations and other people's clauses (rubric tags them, baseline reports none), (e) the `hedged` flag (the baseline has none). **(c) to (e) were not covered by an explicit comparability decision** and are flagged for confirmation. Rules 1 to 12 and the label sets are unchanged.
- **Decision sheet:** items AP1 to AP9 each carry their decision and date in the `Owner entry` row (the sheet's seven original decision rows, its guards and its "no number is set here" rule are untouched).
- **Pilot-pack hashes** (rebuilt only with `python scripts/build_dry_run_package.py`, then `--verify`: consistent; DRAFT, not frozen, `distribution_ready = false`, annotation NOT STARTED; the 30 fictional texts, template and instructions unchanged):

| | Before this phase | Now |
| --- | --- | --- |
| rubric SHA-256 | `5a5be11cbe06f0685c91d17670c814c42b1373202d852a70e8d905ed1fbc48a2` | `bcd6b56da929e984faabba825b3377a78a610862d7b0b19e5a6b43e19738b7c0` |
| annotator excerpt SHA-256 | `cc465ffdaad2f4452987df62955146c5664bd929817878d6c5018ba999f93f22` | `a7032ef0b3c6bd747d312a74ab433826bb0025468fba4eb1d717877933e38c6e` |

### B. `training/sentiment/metrics.py` (VERIFIED FACT)

- **Owner-approved values live in exactly two mappings**, `OWNER_APPROVED_STATISTICS` and `OWNER_APPROVED_POLICY`, and nowhere else; a guard test walks the code and fails if 0.7, 0.8, 0.85 or 0.3 appears anywhere else. Every function still takes its plan and policy as an explicit argument: **there is no default policy**. `StatisticsPlan.owner_approved()` and `EvaluationPolicy.owner_approved()` build the approved ones; `approved=True` is **refused for any other value** (tampering with one number raises).
- **`EvaluationPolicy`** holds the gates: primary labels, held-out minimum 300, primary-class support 75, coverage 0.70, abstention 0.30 (checked to equal 1 - coverage), macro-F1 0.80, accepted-prediction precision 0.85, no recall floor (`None` = `NO_FLOOR`), no agreement floor, ECE `REPORT_ONLY`, calibration minimum sample 20, 10 bins, `COHEN_KAPPA`. `None` is an explicit choice, and every field is required.
- **`EvidenceBasis` now has eight required fields**: dataset approved, not a development fixture, not synthetic, rubric frozen, manifest hashes verified, independence attested, duplicates excluded, splits separate; `eligible_for_owner_review` only when all hold, otherwise `not_validation_evidence` with each reason listed.
- **`assess_against_policy`** evaluates one candidate's report against the gates and prints, for every gate, the required value, the observed value and `met`, `not_met`, `not_evaluable` (with the reason), `reported` or `not_applicable`. Wording: `not_validation_evidence` (evidence not eligible); else `insufficient_support` (held-out size or a primary class below its minimum); else `descriptive_only` (any gate unmet, unevaluable or the policy or plan not the approved one); else `validated`. The macro-F1 gate is met only if **both** the strict and the selective view reach the target; the strict view is never above the selective one, so the strict view always decides. High precision reached by abstaining fails the coverage and abstention gates. The lower-bound rule, the baseline comparison and the (not required) significance testing appear as **informational** gates and never count towards completeness. The output states that activation is the separate R14 decision, that a lower-bound rule nobody approved is also needed, and that no candidate is ranked or selected.
- **Other changes:** calibration takes `bins` as a required argument and names its views `strict` (every scored example) and `accepted_only`; `agreement_report` requires the policy and reports `COHEN_KAPPA` as primary, the floor as `NO_FLOOR`, specific agreement and Krippendorff's alpha as secondary, the pre-adjudication basis, and **multi-label agreement as deferred**; `compare_predictions` states that significance testing is `NOT_REQUIRED` and that no candidate is selected; `evaluation_report` takes the policy and assesses only the approved primary label set (any other label set is reported as secondary and not assessed); the kappa bootstrap is documented as non-stratified. The old `proposed()` plan constructor was removed.

### C. `training/sentiment/frozen_evaluation.py` (new, offline, not connected) (VERIFIED FACT)

Verifies and loads an approved frozen set from a manifest, a records file, the rubric file and the adjudication log, and calls the statistics. **The manifest schema is my PROPOSAL** (its field names follow your list and rubric section 5a; it is a separate format, so `DatasetManifest` and the training pipeline are untouched) and **the owner has not confirmed it**: no real manifest exists, and none should be created before it is confirmed. It requires: the SHA-256 of the records file, the rubric and the adjudication log (checked against the files, line-ending independent); text, adjudicated label, split and group metadata per record, with optional pre-adjudication annotator labels; unique ids; declared record, split and class counts that match; **all three splits present**; no exact duplicate (case-folded) inside or across splits; no cross-split pair at or above the manifest's declared token-set similarity threshold (inclusive), and the manifest's own claim of zero cross-split duplicates. Approval, fixture, synthetic, frozen-rubric (a label ending in "draft" is never frozen) and independence flags are **carried into the `EvidenceBasis`, never raised**, so an unapproved, synthetic or draft-rubric set loads but is `not_validation_evidence`. A verification failure raises with problems and counts only: **a record's text never appears in a message** (tested). Predictions must cover exactly the held-out ids (a missing or extra id is an error, never a default). `evaluate_frozen` returns the complete report (summary, groups, strict and accepted-only calibration, agreement, assessment). **Limits stated, not hidden:** the code cannot establish independence, representativeness or that the flags are true; hash and duplicate checks are integrity checks; the near-duplicate method and threshold are the manifest's to declare and the owner's to approve; `evaluate_sentiment_model.py` is unchanged and does not import any of this (a guard test pins that), and no real model or dataset is connected.

### D. Tests (they actually ran)

One run on 2026-10-29, project interpreter, no concurrent process: the user-text baseline, hypothetical, rubric, pilot-pack, package-builder, evaluation-policy-record, ledger-boundary, insight-API, model-loader, provenance, tokenizer-integrity, training (statistics, policy-gate and frozen-evaluation tests included) and documentation-guard groups: **1201 passed, 3 skipped, 0 failed**. Skips, with the reason: `test_transformer_standin.py` (needs `torch`, absent from the project environment by design); `test_sentiment_model.py` (symbolic links are not permitted for this account); `test_dry_run_package_adversarial.py` (creating symlinks needs a privilege this machine lacks). `scripts/build_dry_run_package.py --verify`: package and DRAFT manifest consistent. New or changed test files: `test_sentiment_policy_gates.py` (31), `test_frozen_evaluation.py` (29), `test_sentiment_statistics.py` (40, updated for the new API), `test_evaluation_policy_records.py` (6, rewritten for the decided state), `test_user_text_rubric_hypothetical.py` (33, updated for rule 13). **Mutation checks** (one process each, in memory, repository files untouched): 18 policy-gate mutations, 13 frozen-evaluation mutations, the 22 earlier statistics mutations (one re-aimed because the code it targeted changed) and the 8 hypothetical-statement mutations: **61 of 61 detected**. The first run missed two boundary mutations (exactly 20 calibration samples; similarity exactly at the near-duplicate threshold); a test for each was added and both are now detected. Mistakes of my own found and fixed along the way: a scenario that did not actually breach the macro-F1 gate, a case-sensitive assertion, a line-ending test that doubled carriage returns, a test that expected the wrong error order, and, again, backslash escapes expanded by the shell in one patch (repaired with the editor). Not run: a mutation check of the rubric, decision-sheet and record-guard tests (exact-text and key checks), and frontend, database, browser, real-model, real-training or dataset tests (no such file changed).

### E. Implementation readings applied (also recorded above; each can be corrected)

Nothing-current text is `uncertain`; the macro-F1 gate needs both views; the gates are assessed only on the primary label set; the four validation words map as described in B; strict calibration is the all-scored view; the polite-form boundary of AP8 is still open.

### F. Remaining hard approvals

1. **Confirm** the implementation readings and the documented differences (c) to (e) in A.
2. **The lower-bound rule** for activation (item 23): not approved, so activation can never be recommended from these reports even when the wording is `validated`.
3. **Multi-label agreement** for topics and preferences (deferred), and an alternative stratification for the kappa interval if one is wanted.
4. **The proposed frozen-manifest schema** (field names, the near-duplicate method and threshold, group-dimension names) before any real manifest is created, and a **code approval** to wire `frozen_evaluation.py` into `evaluate_sentiment_model.py`.
5. **The AP8 polite-form boundary.**
6. **An approved dataset and annotation (R8 to R13)**, annotators and a frozen rubric (the rubric is still `v0-draft`), so that `validated` can ever be reached; and the chain already recorded: R6 / R7, D10 to D13, **R14** (activation).

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no model, tokenizer, dataset, revision query or user text accessed; no package installed; no dependency manifest changed; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no sentiment or personal data on a ledger or blockchain; no code in `core/`, the loader, the trainer, the evaluation script or the API changed.

## Owner decisions recorded 2026-10-29 (eighteenth brief) — the remaining offline evaluation-policy decisions; recorded before any dependent change

**How these were obtained.** Section 1 of the brief says to record the listed readings as confirmed unless the owner changes one: none was changed, so they are recorded as confirmed (with the one refinement the brief itself states for the macro-F1 gate). Sections 2 to 6 each give a choice and mark one "recommended" while saying not to infer approval from a recommendation, so I asked the owner one explicit question listing the five recommended choices and their consequences, including that AP8 authorises a limited production-baseline change. The answer was **"Approve all five"**. The decisions below are exactly the confirmation plus that answer.

### 1. Confirmed policy readings (owner confirmation)

| Reading | Status |
| --- | --- |
| A text with no current view is `uncertain`, not a current sentiment label | confirmed |
| AP4 stays `KEEP_DOCUMENTED_DIFFERENCE` for "even if" constructions | confirmed |
| The comma-less "and" behaviour stays the documented baseline behaviour | confirmed |
| Coverage and abstention thresholds are evaluation gates, not automatic activation rules | confirmed |
| Macro-F1 is assessed in both the strict and the selective view, **with the strict view deciding the gate** (the selective view is reported beside it) | confirmed; this replaces my earlier reading that both views must reach the target (the two are equivalent in outcome because the strict view is never above the selective one) |
| The approved gates apply only to the primary label set `positive_negative_neutral` | confirmed |
| `validated` is not permitted unless every evidence, support, rubric, evaluation and approval condition is satisfied; a point estimate passing is never enough | confirmed |
| The baseline / rubric differences for past-only text, topics in quotations or third-person clauses, and the unavailable `hedged` flag are documented comparability limitations | confirmed |

### 2 to 6. Decisions (owner: "Approve all five")

| # | Decision | Value | Scope and consequence |
| --- | --- | --- | --- |
| 2 | Lower-bound rule | `NO_LOWER_BOUND_ACTIVATION_RULE` | confidence intervals are reported only; **activation cannot be recommended from a metric report alone**; R14 remains responsible for activation. No code reads a lower bound as a gate. |
| 3 | Multi-label agreement (topics, preferences) | `DEFER_MULTI_LABEL_AGREEMENT` | topics and preferences stay descriptive; no multi-label agreement claim is made |
| 4 | Kappa interval stratification | `NON_STRATIFIED_ITEM_BOOTSTRAP` | the current method is retained (kappa has no true class to stratify by) |
| 5 | Frozen-manifest schema | `APPROVE_SCHEMA_AND_WIRE_OFFLINE` | the schema is approved **with the extra fields the brief lists** (dataset purpose, licence and provenance, content, label, rubric and annotator-manifest hashes, split assignments, group metadata, duplicate results, primary label set, annotation and adjudication metadata, evidence-basis status, creation timestamp, an immutable manifest hash) and the rules the brief lists. `frozen_evaluation.py` is connected to `evaluate_sentiment_model.py` **only through the validated manifest interface, tested only on local synthetic fixtures**. No real manifest, dataset, model, route or activation is connected, and none is created. |
| 6 | AP8 polite-form boundary | `CONTEXT_DEPENDENT` | a current polite form ("I would like ...", "I would prefer ...") is accepted as a current preference; conditional or counterfactual polite forms are withheld. **This authorises a change to the production baseline, limited to polite-form handling**; nothing else in `core/user_text_sentiment.py` may change. The method stays `user_text_rules_v1`. |

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no model, tokenizer, dataset, revision query or user text accessed; no package installed; no dependency manifest changed; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no sentiment or personal data on a ledger or blockchain; the rubric stays `v0-draft`, not frozen, and its pilot-pack hashes change only through `scripts/build_dry_run_package.py`.

## Policy implementation results (eighteenth brief) — 2026-10-29: decisions enforced offline; schema confirmed and wired to local fixtures only; nothing activated

Written for the project owner. Built on the decisions in the section above. Nothing was queried, downloaded, installed or collected: no Hugging Face or model access, no model, tokenizer, revision, dataset or user text, no package, no network call, no Transformer enablement. **No real manifest or dataset was created.** The only production change is the one the owner authorised for polite forms.

### A. The one production-baseline change (AP8 `CONTEXT_DEPENDENT`) (VERIFIED FACT)

Probing the baseline first showed polite forms already behaved correctly in most cases: a current "I would like ..." / "I would prefer ..." is accepted; a condition before the clause, or inside it, withholds it; quoted, third-person and negated forms give no preference; a condition in a later sentence does not withhold an earlier current polite form. **One real gap:** a condition that *follows* the polite clause after a comma ("..., if my income increased", "..., but only if ...") left the polite form accepted as current. `core/user_text_sentiment.py` now marks a polite clause (only "would like" / "would prefer") as conditional when the next clause in the same sentence is a **bare condition** (`if`, `unless`, `provided that`, `as long as`, `assuming`, `in case`, optionally preceded by "and" or "only") that has no want of its own. Two mistakes in my first versions were found by the tests and fixed: the first draft also withheld a genuinely current want when the next clause was a conditional with its own want ("..., but if my income fell I would like to protect my savings": now kept), and ", and only if ..." was missed. **Limits, tested and documented:** a non-polite want with a trailing condition ("I want ..., if ...") is unchanged (not authorised); "would love" and "would rather" are untouched; the comma-less form stays as before (`RETAIN_DOCUMENTED_BASELINE_BEHAVIOR`); the brief's exact short sentence "I would prefer more growth." is declined by the relevance gate ("growth" is not a finance word), which is ADR-050's gate and not polite-form handling. The method label stays `user_text_rules_v1`. **A further difference found, not changed:** a text with a current preference plus a hypothetical clause gets baseline sentiment `uncertain` / weak with the preference kept, whereas the rubric would label the current clause alone (`neutral` for a plain intent); added to the documented differences as (f), to be confirmed.

### B. Rubric and sheet (VERIFIED FACT)

Rule 12 of the draft rubric (still `v0-draft`, not frozen, not validated, not received by any annotator) gained the decided polite-form wording; the decision sheet records AP8 as fully decided. Pilot pack rebuilt only with `python scripts/build_dry_run_package.py` and verified (DRAFT, `distribution_ready = false`, annotation NOT STARTED; texts, template and instructions unchanged):

| | Before | Now |
| --- | --- | --- |
| rubric SHA-256 | `bcd6b56da929e984faabba825b3377a78a610862d7b0b19e5a6b43e19738b7c0` | `346c5dce27bd37f493decc4d55876adc6dbdf6008e48f10c318f74e217896e8e` |
| annotator excerpt SHA-256 | `a7032ef0b3c6bd747d312a74ab433826bb0025468fba4eb1d717877933e38c6e` | `d98ece044dde43c36b1337d8e4df7cc7015f2b84d1c36402447f2601f180e778` |

### C. `training/sentiment/metrics.py` (VERIFIED FACT)

- `EvaluationPolicy` gained four required fields, each accepting only the decided value (anything else raises, even for a hand-built policy): `macro_f1_deciding_view = strict`, `lower_bound_rule = NO_LOWER_BOUND_ACTIVATION_RULE`, `multi_label_agreement = DEFER_MULTI_LABEL_AGREEMENT`, `kappa_interval = NON_STRATIFIED_ITEM_BOOTSTRAP`. The two-mapping design is kept (they sit in `OWNER_APPROVED_POLICY`); there are still no defaults; `approved=True` is still refused for any other value.
- **The strict view decides the macro-F1 gate**; the selective view is printed as an informational `report:macro_f1:selective` gate. The strict view is never above the selective one, so the outcome is the same as before; an informational gate never appears among the unmet conditions, even when it is not evaluable (tested).
- **Lower bound:** the old "not approved" gate is now an informational `not_applicable` gate saying intervals are reported only and never a gate; the assessment carries `activation_recommendation = none: a metric report alone never recommends activation`. No code reads a lower bound as a gate (tested).
- `agreement_report` prints the multi-label decision (`DEFER_MULTI_LABEL_AGREEMENT`: topics and preferences stay descriptive, nothing computed) and the kappa interval method. Multi-label agreement and any other kappa stratification were **not** implemented.

### D. `training/sentiment/frozen_evaluation.py`: the confirmed schema (VERIFIED FACT)

Required manifest fields now include: schema version, dataset identifier, **dataset purpose, licence, provenance** (source, collection method, de-identification statement), approval, **creation timestamp**, rubric hash with frozen and **approved** flags, records-file hash, the **record-id, content, label and split-assignment hashes** (recomputed from the records, never trusted), declared counts, group dimensions, duplicate and near-duplicate results, the primary label set, annotation and adjudication metadata with an **annotator-manifest hash** (the annotator file must agree with the manifest), the declared **evidence-basis status**, and an **immutable manifest hash** (canonical JSON of every other field). Verification order: schema version (missing or unknown is refused first) and field types; **personal-data markers** in any manifest string (an e-mail address, a link or a long digit run: refused, and the message does not repeat them); the manifest's own hash; the hashes of all four files; records; recomputed hashes; counts; three separate splits; exact and near-duplicate exclusion (inclusive threshold); and finally that the **declared evidence status equals the computed one** (a manifest cannot claim more, or less, than the checks support). The rubric counts as frozen only if it is marked frozen **and approved** and its label does not end in "draft". Reports contain no record text and no record id (tested). **Limits:** the personal-data check is a pattern heuristic and can miss; hashes and duplicate checks establish integrity, not independence or representativeness; the near-duplicate method, its threshold and the group-dimension names are declared by the manifest and remain the owner's to approve before any real manifest exists.

### E. `training/sentiment/evaluate_sentiment_model.py`: wired through the validated interface only (VERIFIED FACT)

New frozen-set mode: `--frozen-manifest --records --rubric --annotator-manifest --adjudication-log` (all five or none; not combinable with `--manifest` / `--data`), candidates `rules_baseline` and precomputed `--predictions NAME=FILE` (a JSON object of held-out id to label or null). The script calls only `load_frozen_evaluation` and `evaluate_frozen` plus `compare_predictions` against the rules baseline, with the owner-approved plan and policy passed explicitly. Every hash is verified before any evaluation; **the evidence basis comes from the verified manifest alone** (no command-line option can state or change it; a test scans every option name); a model artifact candidate is **refused** in this mode (it needs R6 / R7 and D10 to D13); the report ranks and selects nothing, recommends no activation, contains no record text or id, and the **exit status never depends on a target**. The script imports nothing from the API, settings, agents or security packages and builds no evidence basis or report itself (tested). The ordinary mode is unchanged. **Consequence worth knowing:** a labels-only predictions file carries no confidences, so the calibration gate is not evaluable and such a candidate stays `descriptive_only`; reaching `validated` through the script would need a predictions format with probabilities, which nobody approved.

### F. Tests (they actually ran)

One run on 2026-10-29, project interpreter, no concurrent process: the user-text baseline, hypothetical, polite-form, rubric, pilot-pack, package-builder, evaluation-policy-record, ledger-boundary, insight-API, model-loader, provenance, tokenizer-integrity, training (statistics, policy-gate, frozen-evaluation and frozen-mode tests included) and documentation-guard groups: **1266 passed, 3 skipped, 0 failed**. Skips, with the reason: `test_transformer_standin.py` (needs `torch`, absent from the project environment by design); `test_sentiment_model.py` (symbolic links are not permitted for this account); `test_dry_run_package_adversarial.py` (creating symlinks needs a privilege this machine lacks). `scripts/build_dry_run_package.py --verify`: package and DRAFT manifest consistent. New or changed test files: `test_user_text_polite_forms.py` (30), `test_sentiment_policy_gates.py` (43), `test_frozen_evaluation.py` (40, rewritten for the confirmed schema, with the fixture builder moved to `frozen_fixtures.py`), `test_evaluate_frozen_mode.py` (10), `test_evaluation_policy_records.py` (7), `test_user_text_rubric_hypothetical.py` (34), `test_sentiment_statistics.py` (40, unchanged this phase). **Mutation checks** (one process each, in memory, repository files untouched): 23 policy-gate, 20 frozen-evaluation, 7 polite-form baseline, and the earlier 22 statistics and 8 hypothetical-statement mutations re-run against the changed code: **80 of 80 detected**. One mutation survived at first (informational gates counting towards completeness): it was an equivalent mutant for the validated outcome, so a test was added for the one place it shows (the list of unmet conditions when the selective view is undefined) and it is now detected. Mistakes of my own found and fixed along the way: a polite-form rule that also withheld a genuinely current want beside a conditional one, a missed ", and only if ..." form, a test that expected `valid` for a one-signal text, a test that expected `validated` from a labels-only predictions file (no confidences, so `descriptive_only` is right), a stray space in a path, and a section slice that broke when a second numbered table appeared. Not run: a mutation check of the rubric, decision-sheet and record-guard tests (exact-text and key checks), and frontend, database, browser, real-model, real-training or dataset tests (no such file changed).

### G. Documented rubric / baseline differences now on record

(a) "even if" (`KEEP_DOCUMENTED_DIFFERENCE`); (b) the comma-less "and" (`RETAIN_DOCUMENTED_BASELINE_BEHAVIOR`); (c) past-only text (baseline neutral and weak, rubric `uncertain`); (d) topics in quotations and other people's clauses (baseline none, rubric tags them); (e) the `hedged` flag (the baseline has none); (f) a current preference plus a hypothetical clause (baseline sentiment `uncertain` with the preference kept, rubric labels the current clause alone). (a) and (b) were decided; (c) to (e) were confirmed as comparability limitations in this brief; **(f) is new and awaits confirmation.**

### H. Remaining hard approvals

1. **Confirm difference (f)**, and decide whether the baseline should ever be aligned on (a) to (f) (each needs its own production-change approval).
2. **The frozen-manifest content that is still declared, not decided:** the near-duplicate method and threshold, the group-dimension names, the personal-data heuristic, and a **predictions format with probabilities** if calibration is to be evaluated through the script.
3. **Creating a real manifest** and everything it needs: an approved dataset, annotators, adjudication and a frozen, approved rubric (R8 to R13); the rubric is still `v0-draft`.
4. **R6 / R7, D10 to D13** before any model artifact can be evaluated, and **R14** for any activation (no report can recommend it).

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 and R7 UNRESOLVED; R8 to R14 UNRESOLVED; no model, tokenizer, dataset, revision query or user text accessed; no package installed; no dependency manifest changed; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no sentiment or personal data on a ledger or blockchain; no real manifest created.

## Consolidated approval form issued (nineteenth brief) — 2026-10-29: Phase 1 done; Phases 2 to 7 not started because every hard gate is still closed

*Superseded in part later the same day: the owner answered E1 and E2 (approved) and R14 (left unresolved); see "Consolidated approval form answered in part (twentieth brief)". The statement below that every Entry is blank describes the form as issued.*

Written for the project owner. The brief asks for the remaining phases end to end and to stop at explicit hard gates, presenting every decision still required in one form. **All of them are hard gates, none has been decided, and I decided none.** What was done:

- **One consolidated form** (`reports/sentiment_consolidated_approval_form.md`): model selection (R6, R7 and 13 per-model items), the metadata-only query (10 items), D10 to D13 and the cache location (5), dataset and annotation R8 to R13 (20), the code and format approvals the later phases need (4), and R14 (not requested). Every Entry cell is blank, a recommendation is labelled as not an answer, and a phase map shows which answers unlock which phase.
- **Findings that change what the owner must decide** (VERIFIED FACT, from the code): (1) the download currently happens *implicitly inside training* (`from_pretrained(..., local_files_only=False)`): there is no file allow-list, no recorded per-file SHA-256, no host or redirect enforcement and no destination parameter, so Phase 4 as specified (only approved files, reject unexpected ones, verify hashes) is **not met by the current code** and needs a verified fetch step (form item E1) together with D10 path B; (2) no metadata-query tool exists either (the 2026-10-20 read was done ad hoc and its files are gone); (3) a labels-only predictions file leaves calibration not evaluable, so a candidate evaluated that way can never be `validated` (form item E2); (4) whether independently authored fictional statements count as non-synthetic decides whether `validated` is reachable at all (form item D3); (5) whether the Hub library can enforce a host or redirect policy in code is not established, because the library is not installed in the project environment and the disposable environment was deleted.
- **Threat-model analysis** of the whole real-checkpoint, dataset and evaluation path added as `docs/THREAT_MODEL.md` section 18, separating controls that exist (tested) from controls that depend on unapproved work.
- **R14 prerequisite status** verified against the repository (see the form, section F): the privacy, fallback, isolation and provenance checks pass against fake and stand-in backends (1266 passed, 3 skipped on 2026-10-29), but nothing has been tried with a real model or real data.

**Not done, and why:** Phase 2 (no candidate or query approved), Phase 3 (D12 and D13 open), Phase 4 (A3, B, C and E1 open), Phase 5 (D1 to D20 open), Phase 6 (needs 3 to 5), Phase 7 (R14 is asked only after Phase 6). No Hugging Face contact, no download, no installation, no dataset, no annotation, no activation.

**Tests (they actually ran):** one run on 2026-10-29, project interpreter: the user-text baseline, polite-form, rubric, pilot-pack, package-builder, evaluation-policy-record, consolidated-form (7 new guard tests), ledger-boundary, insight-API, model-loader, provenance, tokenizer-integrity, training and documentation-guard groups: **1273 passed, 3 skipped, 0 failed** (skips: `test_transformer_standin.py` needs `torch`; two tests need symbolic-link privilege this account lacks); `scripts/build_dry_run_package.py --verify` consistent. No code changed. The project environment still has none of `torch`, `transformers`, `tokenizers`, `safetensors` or `huggingface_hub`; `models/sentiment`, `datasets/raw/sentiment` and `~/.cache/huggingface` do not exist.

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 to R14 UNRESOLVED; no model, tokenizer, revision, dataset or user text accessed; no package installed; no dependency manifest changed; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no sentiment or personal data on a ledger or blockchain.

## Consolidated approval form answered in part (twentieth brief) — 2026-10-29: E1 and E2 approved, R14 left unresolved, everything else unresolved; no phase unlocked

Written for the project owner. The brief asked for the matrix to be completed explicitly, each ID recorded as exactly one of `APPROVE`, `REJECT`, `KEEP UNRESOLVED`, `BLOCKED`, with the exact requested value for anything approved, and without inferring any decision from a recommendation. **It gave an explicit value for three items only: E1 (item 7), E2 (item 8) and R14 (item 10).** Items 1 to 6 and 9 list what must be resolved (the models, the per-model licence, provenance, revision, file, host, hash and usage items, the metadata query, D10 to D13, R8 to R13, the remaining code and format approvals) but supply **no value**, so, by the brief's own rule and the form's own rule, they stay unresolved. Nothing was queried, downloaded, installed, collected or built; no code was modified.

### Decisions recorded (owner, explicit)

| ID | Status | Exact value |
| --- | --- | --- |
| E1 | **APPROVE** | A **verified download / fetch step** with (1) a file allow-list, (2) per-file SHA-256 verification, (3) host and redirect checks, (4) an explicit destination, (5) rollback. **Covers the fetch step only.** Not covered, still unresolved: the metadata-query tool (B9), the trainer local-directory parameter (C1 path B), the choice between mechanisms (i) and (ii), and any network use. Building and testing would use fakes only; **no code was written in this phase**; running it needs the model, metadata, D10 to D13 and C5 approvals |
| E2 | **APPROVE** | **Calibration requires probability-bearing predictions** (per-class probabilities for every candidate whose calibration is evaluated); **labels-only predictions remain descriptive-only and can never produce `validated`** (this is already the behaviour of the code; the probability-bearing predictions format is designed when the code is written) |
| F1 (R14) | **KEEP UNRESOLVED** (explicit) | R14 is not decided and not requested; production activation is not authorised |
| C1 to C4 (D10 to D13) | **BLOCKED** | the gates keep the repository's existing `BLOCKED` status; no value was supplied |
| the other 49 IDs | **KEEP UNRESOLVED** | A1, A2, A3.1 to A3.13, B1 to B10, C5, D1 to D20, E3, E4: no value was supplied |

Totals over the form's 55 IDs: 2 APPROVE, 0 REJECT, 4 BLOCKED, 49 KEEP UNRESOLVED. (My previous summary said 61; the form has 55 IDs. No file stated 61.)

### Validation of the matrix (tested in `tests/backend/core/test_consolidated_approval_form.py`, on the real form and on invented answer sets)

| Check | Result |
| --- | --- |
| unanswered entries remain unresolved | yes: 49 `KEEP UNRESOLVED`; each of the 55 entries is exactly one of the four statuses |
| a rejected, blocked or unresolved item never unlocks a phase | yes, tested for every ID and every non-approve status |
| approval dependencies respected | yes: phase 2 needs an approved model with all 13 A3 items and B1 to B10; phase 3 needs C3 and C4; phase 4 needs phases 2 and 3 plus C1, C2, C5 and E1; phase 5 needs D1 to D20 and E3; phase 6 needs phases 3, 4 and 5; phase 7 needs phase 6 and F1 |
| no model download without R6 / R7, D10 to D13 and E1 | yes: removing any one of A3.7, A3.13, B3, C1 to C5, E1, or having no approved model, locks phase 4 |
| no evaluation without R8 to R13 and a frozen manifest | yes: removing any of D1 to D20 or E3 locks phases 5 and 6 |
| no activation without a separate R14 decision | yes: with every other ID approved, phase 7 is still locked until F1 is approved |
| `validated` reachable only with E2 | yes (tested); E2 is approved, but no phase is unlocked, so it is moot today |

### Unlocked phases: none

Phases 2 to 7 are all locked (the form's "Resulting state" section lists the reason for each). E1 and E2 are **approved capabilities, not phases**: they authorise building the fetch step and the probability-bearing predictions format later, with fakes and without any network use, and unlock nothing now.

### Remaining blockers (the next reply needs, in one list)

An answer to **A1 or A2** and the thirteen **A3** items for the chosen model (licences accepted, exact revision, files, hosts, destination, hashes, cleanup, use); **B1 to B10** (the metadata-only query, or B1 = NO); **C1 to C5** (D10 conversion strategy, D11 network boundary, D12 environment, D13 TASK-CERT-1 or accepted residual risk, cache location); **D1 to D20** (dataset source and licence, fictional versus consented text and whether fictional text counts as non-synthetic, de-identification, rubric freeze, annotators and adjudication, blinding, agreement, composition, splits, duplicate policy, calibration data, retention and deletion); **E3** (creating a real frozen manifest) and **E4**; the **E1 mechanism** and the **B9 tool**. R14 stays separate.

**Tests (they actually ran):** the consolidated-form guard alone: **46 passed** (it replaced a 7-test guard). The brief asked for only the form guard and the documentation tests; I also ran the wider sentiment groups because they are cheap and share the documentation guards, so the exact scope was larger than asked: the user-text baseline, polite-form, rubric, pilot-pack, package-builder, evaluation-policy-record, consolidated-form, ledger-boundary, insight-API, model-loader, provenance, tokenizer-integrity, training and documentation-guard groups together: **1312 passed, 3 skipped, 0 failed** (skips: `test_transformer_standin.py` needs `torch`; two tests need symbolic-link privilege this account lacks); `scripts/build_dry_run_package.py --verify` consistent. No code was modified. The project environment still has none of `torch`, `transformers`, `tokenizers`, `safetensors` or `huggingface_hub`; `models/sentiment` and `datasets/raw/sentiment` do not exist.

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 to R14 UNRESOLVED; no model, tokenizer, revision, dataset or user text accessed; no package installed; no dependency manifest changed; no code modified; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no sentiment or personal data on a ledger or blockchain.

## Phase 2 gate presented (twenty-first brief) — 2026-10-29: no value supplied, so A1, A2, A3 and B1 to B10 stay unresolved and Phase 2 stays locked

*Superseded in part later the same day: the dependency question below was settled by the owner (Option 2: A3.1 to A3.8 are provisional until Phase 2) and B1 and B3 to B10 were approved as a restricted metadata-only query; see "Phase 2 gate: Option 2 decided". Kept as the historical record.*

Written for the project owner. The brief asked for the Phase 2 gate to be resolved, listing the outcomes for A1 and A2, the fourteen A3 items and B1 to B10, and said not to infer anything from recommendations, earlier proposals, model-card labels or silence. **It chose none of the outcomes and supplied no value for any item**, so every one stays `KEEP UNRESOLVED`. Nothing was queried, downloaded, installed or built; no code changed.

### The Phase 2 matrix as recorded

| IDs | Status | Note |
| --- | --- | --- |
| A1 (`ProsusAI/finbert`) | KEEP UNRESOLVED | no outcome chosen |
| A2 (R7, one of three candidates) | KEEP UNRESOLVED | no outcome chosen |
| A3.1 to A3.13 (licence, tokenizer licence, training-data terms, commercial use, attribution and share-alike, suitability, 40-character revision, files, hosts, destination, SHA-256, cleanup, use) | KEEP UNRESOLVED | there is no approved candidate for them to apply to |
| B1 (approve or reject a metadata-only query) | KEEP UNRESOLVED | no outcome chosen |
| B2 to B10 (identifier, fields, request count, hosts, redirects, anonymous access, storage path, tool, stop condition) | KEEP UNRESOLVED | follow B1: with B1 unresolved they stay unresolved |

**Phase 2: LOCKED.** Unchanged and held by tests: E1 and E2 approved only as future build authorisations; C1 to C4 (D10 to D13) `BLOCKED`; C5, D1 to D20, E3, E4 and F1 / R14 unresolved.

### Two explicit owner statements in the brief, recorded

1. **Constraint on the query (not an approval of B1 to B10):** the query is read-only and downloads none of weights, tokenizer files, **model configuration files**, datasets or training artifacts; if B1 is rejected or unresolved, B2 to B10 stay unresolved and Phase 2 stays locked. This conflicts with the form's earlier B3 candidate, which listed `config`; the candidate was corrected (API metadata, model card text, file listing; no config). **Consequence:** a model's label order (in its `config.json`) can only be read after an approved download, never from the Phase 2 query.
2. **Rule for unlocking:** an approved candidate with any unresolved A3 item must not unlock Phase 2, and metadata access is not authorised unless B1 to B10 are complete.

### A dependency question the owner needs to settle (raised, not decided)

Phase 2 exists to *read* the revision, the file list and the licences, but the gate requires A3.7 (exact revision), A3.8 (exact permitted files) and the licence items to be approved *before* it runs. That is satisfiable only if the owner supplies those values from their own reading of the model's page (which nobody here touches), in which case Phase 2 is a verification of what was approved, stopping on any difference (B10). If the owner wants the query to discover them, an explicit rule change is needed, for example "A3.1 to A3.8 may be approved as provisional, to be confirmed by Phase 2". No such change was made. The form now carries a minimum reply template and this question.

### Validation (tested in `tests/backend/core/test_consolidated_approval_form.py`, 95 tests)

| Check | Result |
| --- | --- |
| unanswered items remain `KEEP UNRESOLVED` | yes: A1, A2, A3.1 to A3.13 and B1 to B10 are all `KEEP UNRESOLVED` in the recorded form |
| a candidate does not unlock Phase 2 unless every A3 item is approved | yes: each of the 13 A3 items, with each of `KEEP UNRESOLVED`, `REJECT`, `BLOCKED`, locks Phase 2, with or without the other candidate; a fully approved candidate without the metadata approval also stays locked |
| metadata access is not authorised unless B1 to B10 are complete | yes: each of B1 to B10 not approved locks Phase 2; B1 not approved locks it even if B2 to B10 were approved |
| metadata authorisation does not authorise file access or download | yes: with a model and B1 to B10 approved, Phase 2 is the only phase unlocked; phases 3 to 7 stay locked, and E1 alone does not unlock a download |
| no rejected or blocked item unlocks a later phase | yes, for every A3 and B item |

**Tests (they actually ran):** only what the brief asked for: the consolidated-form guard (**95 passed**, up from 46) together with the documentation guards (`test_ai_gates_snapshot`, `test_guards_gates`, `test_evaluation_policy_records`, `test_user_text_pilot_pack`, `test_dry_run_package_audit`, `test_rubric_hash_records`): **220 passed, 0 failed, 0 skipped**; `scripts/build_dry_run_package.py --verify` consistent. No code was modified, and the wider sentiment groups were not run this time.

### Remaining blockers for Phase 2

A1 or A2 approved for exactly one model; all thirteen A3 items for it with exact values; B1 = APPROVE and B2 to B10 with exact values; and the owner's answer to the dependency question above. Everything after Phase 2 is as listed under the twentieth brief.

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 to R14 UNRESOLVED; E1 and E2 approved only as future build authorisations; no model, tokenizer, revision, dataset or user text accessed; no package installed; no network call; no code modified; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no sentiment or personal data on a ledger or blockchain.

## Phase 2 gate: Option 2 decided, restricted metadata query approved, Phase 2 still locked (twenty-second brief) — 2026-10-29

Written for the project owner. **No query was made.** The brief decided the rule that resolves the circularity and approved the query's restrictions, but it **selected no candidate** and supplied **no value for A3.9 to A3.13**, and Phase 2 unlocks only after exactly one candidate is selected, its identifier is recorded and A3.9 to A3.13 are approved. So Phase 2 is locked, and the query could not have run in any case (no identifier to query, and the query tool does not exist).

### Decisions recorded (owner, explicit)

| Decision | Recorded |
| --- | --- |
| **Option 2 for the circularity** | A3.1 to A3.8 (licence, tokenizer licence, training-data terms, commercial-use restrictions, attribution and share-alike, suitability limits, exact immutable revision, permitted file list) are **PROVISIONAL** for the selected candidate until Phase 2 metadata verification; Phase 2 may verify, confirm or reject each. **No provisional item authorises a download, tokenizer access, config access, dataset access, training or inference**, so all eight must be confirmed before Phase 4. A3.9 to A3.13 (hosts, destination, SHA-256 policy, cleanup and rollback, evaluation-only versus training) must be explicitly approved *before* Phase 2 unlocks. |
| **B1** | APPROVE a metadata-only query, read-only and anonymous, of the one explicitly selected model identifier only |
| **B2** | KEEP UNRESOLVED: the rule is decided (only the selected identifier), but no candidate is selected, so there is no identifier to record |
| **B3** | APPROVE: API metadata, model-card text, licence metadata, repository file listing, immutable revision metadata, redirect metadata if exposed; **not** weights, tokenizer files, `config.json`, datasets, training artifacts or generated model files |
| **B4** | APPROVE: a maximum of 10 requests |
| **B5** | APPROVE: `huggingface.co` only, unless the API response redirects to an official Hugging Face metadata endpoint |
| **B6** | APPROVE: do not follow a redirect to a weight or file-download host |
| **B7** | APPROVE: anonymous, read-only API access; stop if authentication is required |
| **B8** | APPROVE: only sanitized metadata, stored in the approval report; no tokens, cookies, raw personal data or model files |
| **B9** | APPROVE the method (anonymous read-only API access). **The tool that enforces the cap, the host check, the no-file rule and the stop conditions does not exist**: E1 covers the fetch step only and building this tool is a code change nobody has authorised |
| **B10** | APPROVE the stop conditions: identifier differs; revision differs from the proposed value; licence or data terms conflict with the provisional record; an unapproved host appears; the request would access a file; authentication is required; the request count would exceed 10 |
| E1, E2 | unchanged: E1 approved for a future verified *fetch* implementation only and does not authorise the query's file access; E2 approved for probability-bearing evaluation only |
| A1, A2, A3.1 to A3.13 | KEEP UNRESOLVED (A3.1 to A3.8 annotated PROVISIONAL) |
| C1 to C4 (D10 to D13) | BLOCKED; C5, D1 to D20, E3, E4, F1 (R14): KEEP UNRESOLVED |

Totals over the 55 IDs: 11 APPROVE (E1, E2, B1, B3 to B10), 0 REJECT, 4 BLOCKED, 40 KEEP UNRESOLVED.

### Is Phase 2 unlocked? No

It needs, all together: exactly one candidate selected (A1 or A2); that identifier recorded in B2; A3.9 to A3.13 approved; B1 to B10 approved. Satisfied today: B1 and B3 to B10 (as restrictions). Missing: the candidate, B2, and all five of A3.9 to A3.13. C1 to C5, D1 to D20, E3, E4 and F1 are not needed for Phase 2 and stay locked and unchanged.

### The query, as it would run (nothing was run)

| Item | Value |
| --- | --- |
| metadata fields queried | **none** (no query was made) |
| request count | **0** of the 10 allowed |
| hosts contacted | **none** |
| discrepancies | **none** (nothing was compared) |

### Open points the approval left, recorded rather than guessed

1. **Named redirect endpoint:** B5 allows an "official Hugging Face metadata endpoint" without naming one; an unnamed redirect target is treated as an unapproved host and stops the query unless the owner names it.
2. **Nothing to compare for two candidates:** B10 stops the query if the revision "differs from the proposed value", but only FinBERT (`0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`) and `mrm8488` (`ae0eab9ad336d7d548e0efe394b07c04bcaf6e91`) have a recorded proposal; for `roberta-base` and `cardiffnlp` the discovered revision would be reported for confirmation (A3.7), not treated as a conflict, unless the owner says otherwise.
3. **The query tool must be built** before Phase 2 can run. That is a code change (a small, standard-library, read-only client that enforces B4 to B6 and B10 and writes only sanitized metadata to the report) and it needs its own authorisation.
4. **Provisional items are not yet entered.** Option 2 makes A3.1 to A3.8 provisional for "the selected candidate"; with no candidate there is nothing provisional to confirm, and the provisional record against which B10 compares (the recorded model-card claims and the two proposed revisions) is in the form's facts column.

### Validation (tested in `tests/backend/core/test_consolidated_approval_form.py`, 52 tests, on the real form and on invented answer sets)

| Check | Result |
| --- | --- |
| unanswered items remain `KEEP UNRESOLVED` | yes (40; A1, A2, B2, A3.1 to A3.13, C5, D1 to D20, E3, E4, F1) |
| a candidate does not unlock Phase 2 unless A3.9 to A3.13 are approved | yes, for each of the five items with each non-approve status |
| A3.1 to A3.8 are provisional: not needed for Phase 2, all needed before Phase 4 | yes: removing or rejecting any of them leaves Phase 2 unlocked and Phase 4 locked |
| exactly one candidate | yes: none, both, or none approved all lock Phase 2 |
| metadata access needs B1 to B10 complete | yes: each of B1 to B10 not approved locks Phase 2; B1 rejected cannot be rescued by B2 to B10 |
| metadata authorisation authorises no file access or download | yes: with Phase 2 unlocked, phases 3 to 7 stay locked, and E1 plus C1 to C5 still do not unlock a download without confirmed A3.1 to A3.8; E1 does not change Phase 2 |
| the other gates stay locked and are not needed | yes: C, D, E and F in any status leave Phase 2 unchanged, and the recorded form keeps them unresolved or blocked |
| no rejected or blocked item unlocks a later phase | yes |

**Tests (they actually ran):** only what the brief asked for: the consolidated-form guard (**52 passed**; it was 95 and was rewritten for the Option 2 rule, with the redundant per-item parametrisations folded into loops) together with the documentation guards (`test_ai_gates_snapshot`, `test_guards_gates`, `test_evaluation_policy_records`, `test_user_text_pilot_pack`, `test_dry_run_package_audit`, `test_rubric_hash_records`): **177 passed, 0 failed, 0 skipped**; `scripts/build_dry_run_package.py --verify` consistent. No code was modified and the wider sentiment groups were not run.

### Remaining blockers

To unlock Phase 2: exactly one of **A1 / A2 approved**, **B2** (that identifier), and **A3.9 to A3.13** (hosts, destination, SHA-256 policy, cleanup and rollback, evaluation-only versus training), plus authorisation to **build the query tool**. After the query: confirmation or rejection of A3.1 to A3.8, then C1 to C5, D1 to D20, E3, E4 and the E1 mechanism as before. R14 stays separate.

### Preserved states

`user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; D7, D8, D9 APPROVED; D10, D11, D12, D13 BLOCKED; R6 to R14 UNRESOLVED; no model, tokenizer, revision, dataset or user text accessed; no query, download or network call; no package installed; no code modified; no real manifest created; intensity regression deferred; sentiment isolated from risk, goals, portfolio, recommendations, compliance and financial calculations; no sentiment or personal data on a ledger or blockchain.

## Approval decision matrix

State vocabulary: APPROVED, REJECTED, UNRESOLVED. "Decision needed" is the exact thing the owner must supply for the item to change state; the last three columns are for the owner.

| Id | Required item | State | Decision needed from the owner (exact) | Decided by | Date | Note |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | `torch==2.6.0`, CPU build | **APPROVED** (owner, 2026-10-26; CPU-only; scope below; **not executable: A1 rejected**). **2026-10-27: APPROVED only as replaced by `torch==2.13.0` (set S1), isolated verification only** | Approve or reject this exact version, the CPU-only channel (`https://download.pytorch.org/whl/cpu`) and the network download of its wheel into a disposable environment | | | |
| R2 | `transformers==4.57.1` | **APPROVED** (owner, 2026-10-26; **not executable: A1 rejected**). **2026-10-27: APPROVED only as replaced by `transformers==5.12.1` (set S1), isolated verification only** | Approve or reject this exact version | | | |
| R3 | `tokenizers==0.22.1` | **APPROVED** (owner, 2026-10-26) | Approve or reject this exact version | | | |
| R4 | `safetensors==0.6.2` | **APPROVED** (owner, 2026-10-26) | Approve or reject this exact version | | | |
| R5 | Python 3.11 and Windows CPU compatibility | **APPROVED for isolated verification only** (owner, 2026-10-26: Python 3.11.9 and Windows CPU); **2026-10-27: verified for set S1, see the results section** | Compatibility is **not verified** anywhere (all current statements are estimates). Approve running the isolated, disposable compatibility test (import, tokenizer, safetensors, CPU inference with a stand-in model, TensorFlow + PyTorch coexistence), name the environment location outside the repository, and say how hashes are obtained and which advisory source is consulted | | | |
| R6 | FinBERT licence and exact immutable revision | **UNRESOLVED** | Read the `ProsusAI/finbert` model card and record its licence (supplied as CC BY-NC-SA 4.0, **unverified**), accept it for this academic project, resolve the NC-SA 4.0 versus Financial PhraseBank NC-SA 3.0 question, and supply the 40-character commit hash to be pinned. Resolving the hash is a metadata lookup on the hub that this phase did not perform | | | |
| R7 | One general-language RoBERTa-family candidate and exact revision | **UNRESOLVED** | Name the model identifier (the brief proposes `FacebookAI/roberta-base`), record its licence and commit hash, and approve a training set for it (it has no sentiment head, so it cannot be evaluated without fine-tuning data). `cardiffnlp/twitter-roberta-base-sentiment-latest` (checklist D6) is optional and also UNRESOLVED | | | |
| R8 | Financial PhraseBank for development benchmarking only | **UNRESOLVED** | Approve or reject its use as a development benchmark only (CC BY-NC-SA 3.0, non-commercial, share-alike, English company news), and approve or refuse the download | | | |
| R9 | Personal-finance annotation protocol | **UNRESOLVED** | Choose fictional-statement generation or consented participant text (D8), approve the two-annotator plus adjudicator protocol in the decision-sheet addendum, and name the independent annotators and the adjudicator (none is named; O4 was accepted only for the fictional dry run) | | | |
| R10 | 300-statement evaluation target and class quotas | **UNRESOLVED** | Approve or amend 300 as a proposed minimum and the quotas in report section G (80 / 80 / 80 positive, negative, neutral; 30 mixed; 30 uncertain; topic and wording minimums) | | | |
| R11 | Macro-F1 and precision targets | **UNRESOLVED** | Approve or amend macro-F1 0.80 and precision 0.85 on accepted predictions, and say whether a lower-confidence-bound floor applies | | | |
| R12 | Minimum acceptable coverage | **UNRESOLVED** | Supply the number (none has been proposed) | | | |
| R13 | Calibration and abstention policy | **UNRESOLVED** | Approve the method (temperature scaling fitted on separate calibration data; threshold derived from the owner's precision and coverage targets), the ECE ceiling (none proposed), and where the separate calibration set comes from | | | |
| R14 | Model activation criteria | **UNRESOLVED** | Approve or amend the criteria in report section E.7 and the rule that activation is a separate, recorded owner decision | | | |

Not part of the gate and unchanged: **D16 keep intensity regression deferred — APPROVED** (the owner's earlier instruction, repeated in this brief); it stays disabled and `sentiment_intensity` stays null.

## Isolated compatibility results (2026-10-26) — STOPPED before installation: advisory blocker

**Outcome: the phase stopped on the owner's own stop rule ("an advisory is unresolved ... do not substitute versions"). Nothing was installed.** The disposable environment was created and only dry-run resolution and metadata queries were run. Full detail, the 24-package hash table and the advisory triage are in section I of `reports/sentiment_transformer_dependency_request.md`.

### Updated decision matrix (R1 to R5; R6 to R14 unchanged)

| Id | Item | State | Verification result |
| --- | --- | --- | --- |
| R1 | `torch==2.6.0` CPU | **APPROVED** (owner) | Wheel `torch-2.6.0-cp311-cp311-win_amd64.whl` (204.2 MB) exists on the configured index; hash matches PyPI; BSD-3-Clause. **24 OSV records** (22 CVEs). CPU-only behaviour **not verified** (not installed). |
| R2 | `transformers==4.57.1` | **APPROVED** (owner) | Pure-Python wheel (12.0 MB) exists; hash matches; Apache-2.0. **12 OSV records** (7 CVEs). |
| R3 | `tokenizers==0.22.1` | **APPROVED** (owner) | `cp39-abi3-win_amd64` wheel exists; hash matches; Apache. No OSV record. |
| R4 | `safetensors==0.6.2` | **APPROVED** (owner) | `cp38-abi3-win_amd64` wheel exists; hash matches; Apache. No OSV record. |
| R5 | Python 3.11 / Windows CPU | **APPROVED for isolated verification only**; verification **incomplete** | Resolution on Python 3.11.9 / Windows amd64 verified (no conflict, both with unconstrained numpy 2.4.6 and with numpy 1.26.4). Install, imports, CPU check, smoke test and TensorFlow coexistence **not run**. |
| R6 to R14 | FinBERT, RoBERTa candidate, PhraseBank, annotation, targets, calibration, activation | **UNRESOLVED** (unchanged) | Not touched. |
| A1 | Risk acceptance for the published advisories at the approved pins | **REJECTED** (owner, third brief, 2026-10-26) | Rejected for `torch==2.6.0` and `transformers==4.57.1`; installation stays blocked. |
| A2 (new) | Replacement exact versions (candidates S1 to S4 in the third-brief section above) | **UNRESOLVED** | Needs explicit owner approval of exact versions; none was selected or substituted. |

### Commands executed in the compatibility phase

(`W` is the session scratchpad directory `...\scratchpad\compat`; `V` is `C:/Users/Administrator/.copilot/sentiment-compatibility-venv`.)

1. `C:/Users/Administrator/AppData/Local/Programs/Python/Python311/python.exe -m venv C:/Users/Administrator/.copilot/sentiment-compatibility-venv`; then `V/Scripts/python.exe --version` (3.11.9), `-m pip --version` (24.0), a check that no pip configuration exists (default PyPI index), and a free-disk check.
2. `V/Scripts/python.exe -m pip install --dry-run --ignore-installed --disable-pip-version-check --cache-dir W/pipcache --report W/resolve_natural.json torch==2.6.0 transformers==4.57.1 tokenizers==0.22.1 safetensors==0.6.2` (exit 0; pip downloaded wheels into the scratch cache to read their metadata, installed nothing).
3. The same with `numpy==1.26.4` added and `--report W/resolve_np126.json` (exit 0).
4. `W/build_pins.py` (turns the pip report into a hash-pinned list), `W/advisories.py` (PyPI JSON for each pinned package plus OSV `querybatch` and per-record lookups), `W/summarise_adv.py`, `W/adv_details.py`, `W/make_table.py` (compares pip's hashes to PyPI's digests).
5. `V/Scripts/python.exe -m pip list` (only `pip` and `setuptools`: nothing was installed).

Network traffic: PyPI package index and file host, `pypi.org/pypi/<name>/<version>/json`, and `api.osv.dev`. Only public package names and versions were sent. No Hugging Face host, no model, no dataset and no user text was contacted or used.

### What this phase established and what it did not

- Verified: wheels exist for the approved pins on Python 3.11.9 / Windows amd64; resolution has no conflict; 24 of 24 wheel hashes equal PyPI's digests; wheel sizes total 246.2 MB; licences from PyPI metadata; 36 OSV advisory records against the approved `torch` and `transformers` pins.
- Not verified: the Windows install itself, installed size, imports, `torch` reporting CPU only with no CUDA requirement, the tokenizer / safetensors / stand-in-model smoke test, TensorFlow 2.17 + PyTorch coexistence (neither process order), `pip check`.
- Tests: no code or configuration changed, so only the documentation and model-safety tests were run, in the project environment (`.venv`, which still has no `torch`, `transformers`, `tokenizers` or `safetensors`): `tests/backend/scripts/test_dry_run_package*.py`, `test_regression_tests_are_effective.py`, `tests/backend/core/test_user_text_pilot_pack.py`, `test_sentiment_model.py`, `test_user_text_model_policy.py` and `tests/training/sentiment` gave **260 passed, 2 skipped** (the 2 skips were not investigated). No database test was run.

### Safeguards confirmed unchanged

`user_text_rules_v1` remains the active method; `SENTIMENT_MODEL_ENABLED` is not set and stays false; the Transformer stays disabled; sentiment still cannot affect risk, goals, portfolio, recommendations, compliance or any financial calculation; no raw user text was logged, stored, cached, sent or placed on-chain; intensity regression stays deferred. No model weights, tokenizer files, datasets or Hugging Face assets were accessed and no model revision was queried.

### Cleanup

The disposable environment and the scratch pip cache (about 250 MB of wheels) were deleted after the results were recorded; recreating them is the first command above. The hash-pinned list is the table in section I of the dependency request report.

## The exact blocker and the decision required at the first brief (historical; superseded by the results above)

**Blocker at the first brief:** 14 of 14 required items were UNRESOLVED; none could be inferred.
**Decision required:** record APPROVED or REJECTED for R1–R14 above (in this file or by replying item by item). Until R1–R5 are APPROVED nothing can be installed; until R6 (and R7 for the RoBERTa candidate) are APPROVED, with the exact revisions, no weight can be downloaded.

**A narrower route the owner may choose (not assumed):** the isolated dependency test needs only R1–R5 plus permission to download the four packages from their indexes; the model, dataset, annotation and metric items (R6–R14) are needed later, before weights or data are touched. The brief set the stricter rule (all items first), so that rule was followed; relaxing it is the owner's call and must be stated explicitly.

## What would run once approved (not run)

Planned, in this order, in a disposable Python 3.11 environment outside the repository, installing only the four approved pins, with hashes where the index provides them, and without touching `backend/pyproject.toml`, `.env` or `SENTIMENT_MODEL_ENABLED`:

1. create the environment; record `pip freeze` before and after; install the CPU `torch` from the CPU index and the other three from PyPI;
2. record actual wheel sizes, installed size, the resolved transitive packages, each package's licence from its installed metadata, and any published security advisory for the exact versions;
3. smoke tests with no model weights: import all four packages; build a tokenizer from a tiny local vocabulary; write and read a safetensors file; run CPU inference on a small randomly initialised classifier built in the test (a stand-in, not a real model); import TensorFlow 2.17 and PyTorch in the same process and run one small operation in each; `pip check`;
4. write the measured results into the research documentation, with verified facts separated from estimates;
5. remove the environment unless the owner keeps it.
Model-weight download is a separate approval (R6, R7, with exact revisions).

## Commands actually executed in this phase (read-only)

`date`; `grep` of the checklist states in `reports/sentiment_transformer_dependency_request.md`; `grep -n` for `ADR-050` and `ADR-052` in `docs/DECISIONS.md`; `.venv\Scripts\python.exe --version`; `.venv\Scripts\python.exe -m pip list` filtered to torch, transformers, tokenizers, safetensors, huggingface, tensorflow, keras and numpy; `grep` of `backend/pyproject.toml` for the four packages; `grep` of `.env.example` for `SENTIMENT_MODEL_ENABLED`; `grep` of `backend/wealthpilot/core/sentiment_model.py` for `trust_remote_code=False`, `local_files_only=True` and `use_safetensors=True`; `ls` and `find` for `models/sentiment`, `datasets/raw/sentiment`, `*.safetensors`, `pytorch_model.bin` and the Hugging Face cache; then the documentation and model-safety tests listed below. Nothing else.

## Facts verified in this phase versus estimates

| Fact | Status |
| --- | --- |
| Python is 3.11.9; numpy 1.26.4; TensorFlow 2.17.0; Keras 3.15.1 are installed | VERIFIED locally (`pip list`) |
| `torch`, `transformers`, `tokenizers`, `safetensors` are not installed and are not declared in `backend/pyproject.toml` | VERIFIED locally |
| `.env.example` sets `SENTIMENT_MODEL_ENABLED=false`; the setting defaults to false | VERIFIED locally |
| `sentiment_model.py` enforces `trust_remote_code=False`, `local_files_only=True`, `use_safetensors=True`, a path inside `models/sentiment/`, SHA-256 per file | VERIFIED by reading the source; the real backend has never run |
| No weights, no dataset and no Hugging Face cache exist on this machine | VERIFIED locally |
| Exact model revision is NOT enforced in the metadata or the training script | VERIFIED by reading the source; a runtime change is needed after approval |
| Package sizes, Python 3.11 / Windows wheels, transitive packages, licences of `torch`, `tokenizers`, `safetensors`, security advisories | ESTIMATES / unverified (see the addendum of the dependency request); the isolated test is what would verify them |
| FinBERT licence, revision and training data | OWNER-SUPPLIED or UNRESOLVED; not verified |

## Compatibility and security results

At the first brief: none. After the second brief a partial result exists: see "Isolated compatibility results" above (resolution, hashes, licences and advisories verified; installation not run because of the advisory blocker). Statements about installed size, CPU behaviour and coexistence remain estimates.

## Date note

The addenda written in the previous phase carry the date 2026-10-27; this machine's clock reads 2026-10-26. Dates in this record use the clock; the earlier files are historical and were not rewritten.

## Next approval required

1. **Nothing is pending on the model items by default:** the thirteenth brief fixed R6, R7 and F1 to F14 at KEEP UNRESOLVED, R7-A, R7-B and R7-C at NOT SELECTED, and D10 to D13 at BLOCKED. The work stops here until the owner supplies explicit values.
2. **To select a candidate, the owner supplies** (the brief's seven conditions): R6-0; R6-1 to R6-7 each accepted or rejected; R6-9; the one R7 choice; that candidate's licence, training-data terms and tokenizer licence; a metadata-only query permission with its identifier, fields, request count, hosts, redirect policy, anonymous-access requirement and response storage; and the confirmation that a query authorises no file, tokenizer, weight or dataset access. The authoritative sources for the licence items are not yet read: the model cards, the dataset cards and the TRC2 access terms.
3. **Before any download or checkpoint access, in addition:** D10, D11, D12 and D13 resolved. **For any dataset, scoring or training:** R8 to R13; **R14** is a separate recorded decision for any activation.
4. **Optional design decisions:** a more specific public reason code (D7 retains `artifact_incompatible`).
5. **Annotation rubric (updated 2026-10-29, fifteenth brief):** rules 11 and 12 now cover hypothetical and conditional statements (rubric still `v0-draft`; hashes rebuilt). Still open: (a) add a hypothetical / conditional line to the proposed coverage list in the dependency report section G (no number proposed); (b) explicit rubric rules for plain quotations, statements about other people and past feelings; (c) how the rubric and the baseline agree on "even if" clauses.
6. **Evaluation tooling (updated 2026-10-29, fifteenth brief):** the interval, agreement, breakdown, coverage, calibration and comparison functions now exist in `training/sentiment/metrics.py`, offline and unused by any pipeline. What remains is the set of methodological approvals listed in "Rubric update and evaluation-statistics support (fifteenth brief)" (methods and values, class support, the agreement statistic and multi-label fields, calibration and selection criteria, significance testing, the label set, wiring).
7. **Evaluation policy (sixteenth brief, 2026-10-29):** the alignment decision AP4 and the annotation-policy decisions AP1 to AP9 (decision sheet), the statistical-policy matrix rows 1.1 to 8, and a code approval for the frozen-manifest schema and the evaluation-script integration (section "Evaluation-policy preparation (sixteenth brief)").
8. **After the seventeenth brief (2026-10-29):** confirm the implementation readings and documented differences (c) to (e); approve (or decline) a lower-bound rule; choose a multi-label agreement method and, if wanted, a stratification for the kappa interval; confirm the proposed frozen-manifest schema and approve wiring `frozen_evaluation.py` into the evaluation script; decide the AP8 polite-form boundary; then the dataset, annotation and frozen rubric (R8 to R13), and the chain R6 / R7, D10 to D13, R14.
9. **After the eighteenth brief (2026-10-29):** confirm rubric / baseline difference (f); decide the still-declared manifest content (near-duplicate method and threshold, group-dimension names, a predictions format with probabilities); then a real manifest, which needs the dataset, annotation and a frozen approved rubric (R8 to R13); and the chain R6 / R7, D10 to D13, R14.
10. **The consolidated approval form (nineteenth brief, 2026-10-29):** `reports/sentiment_consolidated_approval_form.md` holds every remaining hard decision in one place (A model selection, B metadata query, C D10 to D13, D dataset and annotation, E code and format approvals, F activation). Answer it in one reply; any ID left unanswered stays unresolved and the phase that needs it does not start.
11. **After the twentieth brief (2026-10-29):** the form is answered in part (E1 and E2 approved, F1 unresolved). Everything listed under "Remaining blockers" in "Consolidated approval form answered in part (twentieth brief)" is still needed; no phase is unlocked.
12. **The Phase 2 gate (twenty-first brief, 2026-10-29):** no outcome was chosen, so A1, A2, A3.1 to A3.13 and B1 to B10 are unresolved and Phase 2 is locked. To unlock it the owner replies with the lines in the form's section "Phase 2 gate: the minimum reply" and settles the dependency question (supply the revision, file list and licence values from their own reading, or approve an explicit rule change that makes A3.1 to A3.8 provisional).
13. **After the twenty-second brief (2026-10-29):** to unlock Phase 2 the owner selects exactly one of A1 / A2 and gives B2 (that identifier) and A3.9 to A3.13, and authorises building the read-only query tool (B9); then the query confirms or rejects A3.1 to A3.8. Nothing was queried.

## Offline build of the approved E1 / E2 / B9 capabilities (2026-10-29, end-to-end brief)

Nothing was queried, downloaded or installed; no network call was made; no dataset or user text was read; no approval was inferred. Independent offline work only:

- **Phase 1 (rules baseline):** `test_user_text_robustness.py` (12 tests) shows arbitrary seeded input never breaks the baseline's contract; the earlier rubric, polite-form and hypothetical suites are unchanged.
- **E1 / B9:** `training/sentiment/hub_fetch.py` and `test_hub_fetch.py` (97 tests, 25 of 25 deliberate defects detected) - built with a scripted transport and a loopback server; never run against a real host. Open points for the owner: model-card text needs `README.md` (read as B3, not B10); B5's "official Hugging Face metadata endpoint" must be named; two candidates have no recorded proposed revision; the trainer local-directory parameter (C1 path B) is not implemented.
- **E2:** `evaluate_sentiment_model.py` accepts probability-bearing predictions (all records or none, validated, nothing echoed); the rules baseline carries none, so it can never be `validated`. 19 new tests.
- **Not done (hard gates):** Phase 3 stand-in re-run (needs a package install), Phases 2, 4 to 8, any HF contact, any dataset, any activation. Form statuses unchanged: 11 APPROVE, 0 REJECT, 4 BLOCKED, 40 KEEP UNRESOLVED.

## Phase 2 execution (2026-10-29, after the owner's second reply)

Owner values recorded first (see the consolidated form): A1 `ProsusAI/finbert`; A2 unresolved; B2 `ProsusAI/finbert`; provisional A3.1 (CC BY-NC-SA 4.0), A3.2, A3.3, A3.4 (non-commercial offline evaluation only), A3.5 attribution (share-alike unresolved), A3.7 revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`; A3.6 suitability unresolved (not validated for personal-finance narratives); A3.9 `huggingface.co` only; A3.10 destination outside the repository; A3.11 SHA-256; A3.12 cleanup; A3.13 `OFFLINE_EVALUATION_ONLY`; B3/B5 clarifications; E5. The owner's list numbered A3.5 to A3.8 differently from the form (attribution and share-alike split); the values were recorded by meaning and no permitted-files value was supplied (A3.8 stays unresolved).

Sanitised result of the one query (B8): requests 2 of 10 (`model_info`, `revision_info`); host `huggingface.co`; redirects none; anonymous, `gated` false; discovered revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` equal to the proposal; licence tag `cc-by-nc-sa-4.0`; library `transformers`, task `text-classification`; downloads none; stopped `malformed_response` at the file listing; the model card was not requested. Probable cause: the dot-file `.gitattributes` refused by the listing name pattern (inference; the raw listing is not kept). Fixed offline; 98 hub-fetch tests pass.

Confirmations: none (missing evidence). Phase 3 to 8 locked. A re-run needs the owner's confirmation.

## Re-run of the incomplete Phase 2 query: APPROVED (2026-10-29, recorded BEFORE any request)

Owner approval: re-run the incomplete Phase 2 metadata query ONCE for `ProsusAI/finbert`, proposed revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`. Request budget: the first run used 2 of 10; this re-run may use at most **3 additional** requests (5 of 10 in total); the limit is not increased. Anonymous, read-only metadata only; `https://huggingface.co` only; every redirect to another host or to a file-download host is refused; no token, cookie, authentication or personal data. Allowed: model API metadata, immutable revision metadata, sanitised model-card / README text, licence metadata, the repository file listing, exposed redirect metadata. Forbidden: weights, tokenizer files, `config.json`, datasets, training artifacts, generated files, any file download. Stored: sanitised metadata only. Stop immediately on a revision mismatch, licence conflict, missing or malformed response, unapproved host or redirect, authentication requirement, file-download request, request-count violation, unexpected identifier, or raw text / sensitive data exposure. Each provisional field is then recorded as exactly one of CONFIRMED / REJECTED / UNRESOLVED / INSUFFICIENT EVIDENCE; a licence tag alone is not proof of all licence terms and the financial-news domain is not validation for personal-finance narratives. Unlocks completion of Phase 2 only: no package, Phase 3, weight / tokenizer download, config access, dataset, annotation, training, inference or activation.

### Result of the approved re-run (2026-10-29): COMPLETE

1. **Requests:** 3 (`model_info`, `revision_info`, `model_card`); with the first run 5 of 10. No request was repeated beyond the tool's own checks (`model_info` and `revision_info` were necessarily sent again because the tool needs both to read the listing). Policy cap for this run: 3.
2. **Hosts / redirects:** `huggingface.co` only; no redirect. Anonymous; not gated. No stop condition fired.
3. **Fields obtained:** identifier, discovered and verified revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` (equal to the proposal), licence tag `cc-by-nc-sa-4.0`, `transformers` / `text-classification`, tags (include `safetensors`, `finance`, `financial-sentiment-analysis`, `arxiv:1908.10063`), file listing, model-card front matter, headings and length.
4. **Sanitised listing:** `.gitattributes`, `README.md`, `config.json`, `flax_model.msgpack`*, `model.safetensors`, `pytorch_model.bin`*, `special_tokens_map.json`, `tf_model.h5`*, `tokenizer_config.json`, `vocab.txt` (* pickle-capable: never fetch). Only `model.safetensors` (437965908 bytes, SHA-256 `e5897858ff819aad7629b96ce521ae5477952d03634ef5dd30ed2d76357a9f00`) has an API-published hash. The full table with sizes and hashes is in the consolidated form.
5. **Card / licence findings:** the licence is stated three times consistently (tag, front matter, "Model Weights License" section: CC BY-NC-SA 4.0; commercial use restricted; adaptations must be shared under the same licence). Training data: Financial PhraseBank (CC BY-NC-SA 3.0 per the card) and Reuters TRC2 (NIST access terms, not read). No tokenizer licence statement. Financial-text domain only.
6. **Provisional fields:** model licence CONFIRMED; tokenizer licence INSUFFICIENT EVIDENCE; training-data licence and provenance INSUFFICIENT EVIDENCE; commercial restriction CONFIRMED; attribution CONFIRMED; share-alike UNRESOLVED; permitted file list UNRESOLVED (listing known, no owner-approved list); personal-finance suitability INSUFFICIENT EVIDENCE; immutable revision CONFIRMED. None REJECTED. These are verification results, not owner approvals; the form's statuses are unchanged.
7. **Blockers:** the owner's decisions on A3.1 to A3.8; A2, C1 to C5, D1 to D20, E3, E4, F1.
8. **Not accessed:** no file, tokenizer file, `config.json`, weight, dataset or user text; the card text was held in memory only and not stored.
9. **No package installed; production unchanged** (`user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`).

## Owner brief of 2026-10-29 on the remaining FinBERT fields: options listed, none chosen

The brief asked to resolve A3.1 to A3.8 and listed, for each field, "accept ... / reject / keep unresolved" without choosing. A verification result is not an approval and silence or an option list is not an answer, so no field was approved or rejected; each stays `KEEP UNRESOLVED` with its Phase 2 verification result shown beside it (see the consolidated form, "Pending owner decisions on A3.1 to A3.8"). Recorded because it was stated outright: the proposed allow-list (`model.safetensors`, `config.json`, `vocab.txt`, `tokenizer_config.json`, `special_tokens_map.json`; recorded and not approved), the never-download list (`pytorch_model.bin`, `tf_model.h5`, `flax_model.msgpack`, anything unexpected, any dataset or training artifact) and the hash procedure for the four files without a published API hash (hashed independently at the first approved download and added to the immutable manifest before use; verification, not approval of contents). No legal clearance is claimed; the licence text was not independently reviewed and the Reuters / NIST terms were not read. No file, package, dataset or user text was accessed; no phase unlocked beyond Phase 2; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

## Owner resolution brief of 2026-10-29 (third): stated decisions recorded, options not chosen, first-download controls still closed

Recorded now from the owner's statement (they had not been recorded as approvals before): A3.1 accepted for non-commercial offline evaluation only, not legal clearance; A3.4 non-commercial offline evaluation only; A3.5a attribution obligation accepted (exact text still required before any distribution; not captured, not invented); A3.7 revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` confirmed; A3.8 the five-file allow-list (`model.safetensors`, `config.json`, `vocab.txt`, `tokenizer_config.json`, `special_tokens_map.json`) approved as a list only, with the never-download list and the independent hashing of the four files without an API hash. Not chosen (options listed again): A3.2 tokenizer licence, A3.3 training-data terms, A3.5b share-alike scope, A3.6 suitability - all `KEEP UNRESOLVED`. First-download controls: the brief gives conservative defaults but no value for the environment, certificate remediation, Hub-conversion path, network boundary, cache location, E3 or E4, so C1 to C4 stay BLOCKED and C5, E3, E4 unresolved; the defaults are recorded as restrictions only. Form: 23 APPROVE, 4 BLOCKED, 29 KEEP UNRESOLVED over 56 IDs. No phase unlocked beyond Phase 2; no network request, file, package, dataset or user text; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

## Owner statement of 2026-10-29 (Phase 3 brief): decisions recorded; Phase 3 NOT started

Recorded: A3.5a accepted, **A3.5b rejected until the legal scope is verified** (the A3.5 row is REJECT; use of the model is not approved until then); A3.6 accepted as an offline research candidate only, not validation; C1 Path B (local conversion-free workflow; the trainer change is documented, not applied); C2 anonymous HTTPS to `https://huggingface.co` only; C3 disposable Python 3.11 CPU environment `C:\Users\Administrator\.copilot\wealthpilot-finbert-eval-venv`; C4 decided as "complete TASK-CERT-1 before any model download"; C5 temporary cache `C:\Users\Administrator\.copilot\wealthpilot-hf-cache`. A3.2, A3.3, D1 to D20, E3, E4 and R14 remain unresolved; E1 and E2 unchanged.

Phase 3 check (read-only, no network, no installation): TASK-CERT-1 is BLOCKED with no work done; the project environment still has `certifi` 2026.7.22 and `pip` 26.2.1; C4 is therefore not satisfied, so the environment was not created and no package was installed. No approved local wheels exist and retrieval from PyPI is not covered by a recorded approval, so the phase stops before retrieval. None of the offline validation checks could run and none is claimed. The two target paths do not exist; nothing was created or deleted. Discrepancies reported, not resolved: the S1 set is 35 to 36 wheels, not six; `setuptools` 81.0.0 (brief, form) versus 84.2.1 (S1 hash table). Form: 28 APPROVE, 1 REJECT, 1 BLOCKED (C4), 26 KEEP UNRESOLVED. No file, dataset or user text accessed; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

## Offline preparation for Phase 3 (2026-10-29, autonomous brief): facts and one decision request; nothing executed

Routine decisions made without asking: the new module `training/sentiment/local_model_dir.py` (standalone, unwired) and its tests; the guard `tests/backend/core/test_s1_pin_list_records.py`; a superseded note on the early S1 table; wording and file placement. Verified facts (read-only): TASK-CERT-1 is BLOCKED and cannot be completed offline (project `certifi` 2026.7.22 and `pip` 26.2.1; the other local Pythons have no `certifi` and older `pip`; no local wheel; the pip cache is an HTTP response cache with 3 unrelated built wheels); the S1 `setuptools` discrepancy is resolved by the record (the executed 35-wheel list of section L.3 with `setuptools==81.0.0` and `certifi` 2026.10.23 is authoritative; the 84.2.1 table was the first proposal and carries the affected `certifi` 2026.7.22), with no version substituted; `tensorboard` 2.17.1 imports `pkg_resources`, so the project environment must stay below `setuptools` 82; the six direct packages are not enough for `--require-hashes` (35 wheels). Path B: the local-directory module is prepared with 56 synthetic-fixture tests (55 passed, 1 skipped for symlink privilege) and 22 of 22 mutations detected; the trainer and evaluation-script wiring is NOT applied. The one consolidated decision request is in the consolidated form ("Phase 3 unblock"). No network, package, environment, model, tokenizer, config, dataset or user text was touched; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`.

The existing guard `test_no_other_call_in_the_training_package_loads_a_pretrained_model` failed on the new module's two local `from_pretrained` calls; it now allows exactly that module and a new AST test asserts its calls take only the local directory variable with literal `local_files_only=True`, `trust_remote_code=False` (and `use_safetensors=True` for the model). No guard was loosened for any other file.

## Owner message of 2026-10-29 (consolidated request, second listing)

Options for C4, PyPI retrieval, S1, Path B, A3.2, A3.3 and A3.5b were listed again without a choice, so nothing was approved and nothing executed. Recorded: C5 retention (use only during the approved disposable operation; delete after the verified artifact is created; delete immediately on failure, mismatch or cancellation; never reuse a partial cache); D1 to D20, E3, E4, R14 remain `KEEP UNRESOLVED`. No remediation, retrieval, environment, wiring, network, package, model, dataset or user text. Production: `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Owner approvals of 2026-10-29 (execution brief): recorded BEFORE any action

Approved by the owner (stated outright): **C4** - complete TASK-CERT-1, limited to `certifi` and `pip`, with no change to `setuptools`, TensorFlow, Keras, NumPy or application dependencies; **PyPI retrieval** - anonymous HTTPS, wheels only, no source distributions, no resolution beyond the lock, only the exact 35-wheel hash-pinned list of dependency-report section L.3 (`setuptools==81.0.0`, `certifi==2026.10.23`), every filename, version and SHA-256 verified independently before any installation, any mismatch stops everything and deletes the retrieved files; **S1** - that 35-wheel list; **Path B** - wire `local_model_dir.py` into the trainer / evaluation path, offline only; **C5** - the cache path and retention already recorded. Still unresolved or rejected: A3.2, A3.3, A3.5b (rejected until the legal scope is verified), D1 to D20, E3, E4, R14. The permitted external access is the PyPI retrieval of the exact lock and nothing else; Hugging Face is never contacted.

Pre-action finding (read-only): the approved lock has no `pip` wheel (35 wheels: the six direct packages plus 29 dependencies). TASK-CERT-1 also needs `pip` moved to a release whose vendored `certifi` is fixed, which is a version outside the approved set, so the project-environment remediation stops BEFORE any change and reports the missing approval. Project versions before (unchanged): `certifi` 2026.7.22, `pip` 26.2.1, `setuptools` 65.5.0, `tensorflow` 2.17.0, `keras` 3.15.1, `numpy` 1.26.4; `pip check` clean. The disposable-environment work (which needs no project change) proceeds.

## Execution of the approved operations (2026-10-29, execution brief): results

**TASK-CERT-1 (C4):** STOPPED before any change. The approved lock has no `pip` wheel; the remediation needs a `pip` release outside the approved set, so the project environment is untouched (before = after: `certifi` 2026.7.22, `pip` 26.2.1, `setuptools` 65.5.0, `tensorflow` 2.17.0, `keras` 3.15.1, `numpy` 1.26.4; `pip check` clean). Missing approval: a named `pip` version with its wheel hash, and whether `certifi` 2026.10.23 (in the lock) may be upgraded alone now. Rollback is not needed (nothing changed).
**PyPI retrieval and S1:** 35 of 35 wheels retrieved (170,314,953 bytes; hosts `pypi.org` and `files.pythonhosted.org`), every filename, version and SHA-256 verified independently, 0 problems; the full hash table is in the dependency report, section S. **Disposable environment** (`...\wealthpilot-finbert-eval-venv`): `--require-hashes` install of the 35 wheels, `pip check` clean, Python 3.11.9 AMD64 Windows, `torch 2.13.0+cpu` (`torch.version.cuda` None, `is_available()` False), no NVIDIA / CUDA distribution, zero socket attempts, TensorFlow 2.17.0 and PyTorch coexist in both orders; 1124 tests passed and 2 skipped inside it; environment, wheels deleted; the temporary cache was never created.
**Path B wiring (offline):** `local_model_dir.py` is now used by `train_sentiment_transformer.py` (`--local-model-dir`, `--local-model-manifest`; `fine_tune_with_torch(..., local_model=...)`, `revision` stays a required keyword, `None` only with a local directory) and by `evaluate_sentiment_model.py` (`--local-model`, `--local-model-manifest`, `parse_predictions` shared with the precomputed-file gate); 22 of 22 deliberate defects detected on the loader and 9 of 12 on the wiring (the other 3 are behaviourally equivalent). No route, setting, schema, dependency manifest or production configuration changed. A3.2, A3.3 unresolved; A3.5b rejected; D1 to D20, E3, E4, R14 unresolved. Hugging Face was never contacted; no model, tokenizer, config, dataset or user text was accessed.

## TASK-CERT-1 metadata phase (2026-10-29): policy decision recorded BEFORE the query

**Owner policy decision (2026-10-29), recorded before the metadata query:** `certifi==2026.10.23` may be upgraded ONLY together with the approved `pip` remediation, never independently (the project `pip` may retain a vulnerable vendored `certifi` copy); the project's `setuptools==65.5.0`, TensorFlow 2.17.0, Keras 3.15.1 and NumPy 1.26.4 must remain unchanged; the approved S1 disposable environment stays separate from the project environment; TASK-CERT-1 remains BLOCKED until the exact `pip` version and wheel hash are explicitly approved. This phase is a read-only PyPI metadata query: no package is installed or upgraded, the project environment is not modified, no model, dataset or user text is accessed, Hugging Face is not contacted, and production configuration does not change.

### Result of the TASK-CERT-1 metadata query (2026-10-29)

Requests: 2, both anonymous to `pypi.org` (`/pypi/pip/json`, `/pypi/pip/26.2.2/json`); no redirect; nothing installed, upgraded or downloaded beyond the two JSON documents; project environment untouched. **Candidate (not selected, not approved, not installed):** `pip` 26.2.2 (the only release after 26.2.1), wheel `pip-26.2.2-py3-none-any.whl` (pure Python; there is no Windows-specific `pip` wheel), 1,819,850 bytes, SHA-256 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`; not yanked; PyPI `vulnerabilities` empty; `Requires-Python` `>=3.10` (project Python 3.11.9 satisfies it); uploaded 2026-10-20. **Vendored `certifi` of 26.2.2: NOT VERIFIED** from PyPI metadata (it records nothing about vendored packages); the project's installed `pip` 26.2.1 vendors `certifi==2026.6.17` (local read). The version therefore stays unresolved. `certifi==2026.10.23` is to be upgraded only together with the approved `pip`, never alone. TASK-CERT-1 stays BLOCKED. Remaining: a separate security decision (read pip's official changelog or source for the vendored version; or retrieve the hash-verified wheel for inspection only; or a written risk acceptance with scope and expiry). No package, model, dataset or user text accessed; `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`.

## TASK-CERT-1 pip-wheel inspection: APPROVED (2026-10-29), recorded BEFORE any action

Owner decisions: **option (b)** - retrieve the single wheel `pip-26.2.2-py3-none-any.whl` from PyPI into a scratch directory, verify its SHA-256 independently against `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`, do NOT install it, inspect ONLY `pip/_vendor/vendor.txt` and `pip/_vendor/certifi/__init__.py`, then delete the wheel and the scratch directory; no Hugging Face contact; the project environment is not modified by this step. The `pip` approval stays PENDING until the inspection succeeds: if the vendored `certifi` is confirmed fixed (the task card: `certifi` 2026.10.19 or later), `pip==26.2.2` with the SHA-256 above is recorded as approved; if it is not confirmed fixed or the hash differs, stop and leave C4 BLOCKED. Policy: `certifi==2026.10.23` only together with the approved `pip`, never alone; `setuptools` 65.5.0, TensorFlow 2.17.0, Keras 3.15.1 and NumPy 1.26.4 unchanged.
Conditional installation decision (takes effect only after a successful inspection): approve `pip==26.2.2` only for TASK-CERT-1, approve `certifi==2026.10.23` together with it, approve no other project-environment package change; require before/after versions, hashes, security checks, regression tests and rollback instructions; on any failure stop immediately, do not retry another version, restore only if the approved rollback requires it, keep C4 BLOCKED.

### Pip-wheel inspection result (2026-10-29): SUCCEEDED; the installation decision takes effect

Retrieved `pip-26.2.2-py3-none-any.whl` (1,819,850 bytes) into a scratch directory with the base interpreter's `pip` 24.0 (`--isolated --no-cache-dir --require-hashes`); its SHA-256 was recomputed independently and equals `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`; only `pip/_vendor/vendor.txt` and `pip/_vendor/certifi/__init__.py` were read (`certifi==2026.10.19` and `__version__ = "2026.10.19"`), which is the first release the task card calls fixed (GHSA-6q48-6c7w-9gw2: 2026.10.19 or later); the wheel was not installed and the scratch directory was deleted. The pip log printed no URLs, so the hosts are not independently evidenced for this step (default index, isolated). **Recorded as approved: `pip==26.2.2` (SHA-256 above) for TASK-CERT-1 only, together with `certifi==2026.10.23` (SHA-256 `e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1`, from the S1 list); no other project-environment package change.**

### TASK-CERT-1 executed (2026-10-29): COMPLETED AND VERIFIED

Upgraded exactly `pip` 26.2.1 to 26.2.2 (SHA-256 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`) and `certifi` 2026.7.22 to 2026.10.23 (SHA-256 `e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1`) in the project environment (hash-pinned, `--no-deps`, wheels only); `pip freeze --all` before and after differ in exactly those two packages; `setuptools` 65.5.0, TensorFlow 2.17.0, Keras 3.15.1, NumPy 1.26.4 and every application dependency unchanged. `pip check` clean; installed `RECORD` hashes verify (0 mismatches); pip vendors `certifi` 2026.10.19, top-level 2026.10.23; TensorFlow / Keras and the application imports work; 1301 tests passed, 5 skipped; zero network attempts in the checks. Advisory GHSA-6q48-6c7w-9gw2: both certifi copies in the environment meet the fixed release; no advisory database re-queried and the project-endpoint chain check NOT performed (needs a connection to the project's endpoints). Rollback backup (491 files, tree SHA-256 `8da3684ee570782c3811494df0fa3ff2a9686fe2974e476264404a997d759801`) kept at `C:\Users\Administrator\.copilot\wealthpilot-taskcert-rollback`; restore steps are in the consolidated form, "TASK-CERT-1 execution". C4 is now APPROVE (completed). No Hugging Face contact, model, tokenizer, config, dataset or user text; production `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## End-to-end brief of 2026-10-29: decision forms requested, no value supplied

The brief restates the current state and asks for one legal form (A3.2, A3.3, A3.5b) and one dataset form (the owner's R8 to R13, this form's D1 to D20), supplying no choice for any item. Both are in the consolidated form ("Consolidated decision request for the legal gate (Phase 1) and the dataset gate (Phase 2)") with a one-line-per-item reply format and a mapping of the brief's 20 items onto D1 to D20 (several are already decided by the approved evaluation policy and need only confirmation; the deciding open question is D3, whether independently authored fictional text counts as valid evidence). Nothing was approved or rejected, so Phases 3 to 6 stay locked: no download (A3.2, A3.3 unresolved and A3.5b rejected), no dataset generated, collected or labelled (D1 to D19 unresolved), no manifest, no evaluation, no R14 request. The rollback backup `...\wealthpilot-taskcert-rollback` was not touched. No network, package, model, dataset or user text; `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Owner reply of 2026-10-29 (legal, dataset, alignment and manifest brief)

The brief listed options for A3.2, A3.3, A3.5b, D3, D5, E3 and E4 without choosing one and asked for values (D1, D2, D4, split sizes, near-duplicate method and threshold, group names, retention, deletion, access) without giving them. It gave direct approvals for: two independent annotators and one adjudicator (D6), blinding (D7), at least 300 held-out statements and 75 per primary class (D9), and coverage at least 0.70 / abstention at most 0.30 (D15); it also restated decided policy (the label set, Cohen's kappa primary with multi-label agreement deferred, probability-bearing calibration with at least 20 scored examples, labels-only predictions descriptive-only), which is confirmed but does not close D8 or D13 (their other clauses were not addressed). Recorded in the consolidated form ("Owner reply of 2026-10-29 (legal, dataset, alignment and manifest brief)"): 33 APPROVE, 1 REJECT (A3.5), 0 BLOCKED, 22 KEEP UNRESOLVED. Phase 4 stays locked (A3.2, A3.3 unresolved; A3.5b rejected); Phase 5 stays locked (D1 to D5, D8, D10 to D14, D16 to D20, E3); E4 and R14 unresolved; no code changed. No network, package, model, dataset or user text; `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Owner reply of 2026-10-29 (third brief: consolidated legal, dataset, manifest and alignment decisions)

The brief again listed options for A3.2, A3.3, A3.5b, D1, D2, D3, D5, E3 and E4 without choosing, gave examples for the group dimensions and asked to specify retention, deletion and access without specifying. Direct statements recorded: D4 privacy and de-identification (APPROVE; the verifier is still to be named in the participant register) and D8 agreement (APPROVE: kappa primary, specific agreement and Krippendorff alpha secondary, two independent labels before adjudication, adjudicated labels final, multi-label deferred). Restated policy confirmed without closing a row: label set, disjoint splits (D10 needs sizes), exact duplicate removal (D11 needs the near-duplicate method and threshold), calibration policy (D13 needs the temperature-scaling clause). Form: 35 APPROVE, 1 REJECT (A3.5), 0 BLOCKED, 20 KEEP UNRESOLVED. Phases 4 to 7 stay locked; nothing generated, collected, labelled or stored; E3, E4, R14 unresolved; no code changed. No network, package, model, dataset or user text; `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Owner decisions of 2026-10-29 (fourth brief)

Recorded as the owner's decisions: A3.2 ACCEPT ABSENCE OF A SEPARATE TOKENIZER LICENSE STATEMENT FOR NON-COMMERCIAL OFFLINE EVALUATION ONLY (not legal clearance); A3.3 unresolved; A3.5b rejected until the legal scope is verified. Dataset: D3 fictional text remains synthetic and can never produce `validated`; D5 rubric kept as `v0-draft`, not frozen (row stays unresolved); D10 splits 600 / 100 / 300; D11 exact removal by normalized-text hash plus character 5-gram Jaccard at or above 0.90 (equality counts); D12 groups topic, difficulty, negation, contradiction, code_mixed; D13 temperature scaling on the calibration split only, 10-bin report-only ECE, descriptive below 20; D17 delete raw text and temporary annotation files after evaluation, audit and the R14 decision, keep hashes, metrics and decision records; D18 two annotators, one adjudicator, one evaluator, no production service; E4 keep the documented difference for all six; D1, D2, D14, D16 (no storage location named), D19, D20, E3 and R14 unresolved. Form: 44 APPROVE, 1 REJECT (A3.5), 0 BLOCKED, 11 KEEP UNRESOLVED. FinBERT stays undownloaded (A3.3 open, A3.5b rejected); nothing generated, collected, labelled, stored or frozen. One offline tooling change: `frozen_evaluation.py` now implements the approved D11 method (previously token-set Jaccard with a manifest-declared threshold), with boundary tests and four caught mutants. Open engineering items, not done: D13 wiring for the frozen path, the register tool's verifier / consent / authorisation fields. No network, package, model, dataset or user text; `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Offline implementation of the participant register and D13 calibration (2026-10-30)

Implemented and tested offline, with no decision changed (44 APPROVE, 1 REJECT, 0 BLOCKED, 11 KEEP UNRESOLVED): the participant-register schema and validator (`training/sentiment/participant_register.py`: anonymous codes, the four roles with the approved counts, independence attestations, access authorizations with scope and start / expiry dates and a role-checked `may_view` list, a verifier with a valid authorization, a deletion authorization, synthetic or consented status with consent metadata, no production services, no personal data or credentials, sanitized errors); D13 temperature calibration in `metrics.py` (fitted on the calibration split's log-probabilities only, applied to held-out probabilities only, 10 equal-width bins, strict and accepted-only, descriptive-only below 20, no invented logits, labels and the rules baseline untouched, never `validated`, never a recommendation); and schema-2 frozen-manifest metadata (register, verifier and consent hashes, calibration-split hash, temperature-policy version, group dimensions, duplicate policy, data status) with the register as a sixth verified input. Mutation checks: 28 of 30 caught, 2 equivalent. A3.3 unresolved and A3.5b rejected, so FinBERT is undownloaded; D1, D2, D5, D14, D16, D19, D20, E3 and R14 unresolved; no real data, register, manifest, consent or rubric freeze; no network, package, model or user text; `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Owner decisions of 2026-10-30 (fifth brief) and the end-to-end brief

Recorded: A3.3 unresolved; A3.5b rejected until the legal scope is verified; D1, D2, D5 (rubric stays `v0-draft`), D16 (no path supplied), D20 and R14 unresolved; "D14 = APPROVE" (adjudication and agreement) and "D19 = APPROVE" (retention and deletion) are the form's D8 and D17 by meaning, already approved, now specified (two independent labels before adjudication, kappa primary, adjudicated labels final, no agreement result alone produces `validated`; raw text kept only until evaluation, audit verification and the R14 decision, deletion authorized by the project owner, completion verified and recorded, a rollback never restores deleted raw text); E3 = schema-2 offline implementation only (row stays unresolved). The register validator now enforces that deletion policy (5 of 5 mutants caught), and new guards show no fixture can pass as real evidence and no real FROZEN manifest or register exists. The end-to-end brief's one consolidated approval table is in the consolidated form. Form unchanged: 44 APPROVE, 1 REJECT, 0 BLOCKED, 11 KEEP UNRESOLVED. FinBERT undownloaded; no real data, register, manifest or consent; no network, package, model or user text; `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`.

## Phase closure (2026-10-30)

> The offline rules-based sentiment phase is complete. Transformer evaluation, real dataset creation and production activation are deferred because the required legal, dataset, storage and activation approvals are unresolved.

Final owner values recorded exactly: A3.3 KEEP UNRESOLVED; A3.5b REJECT USE UNTIL LEGAL SCOPE IS VERIFIED; D1, D2 and D16 KEEP UNRESOLVED; D5 KEEP v0-DRAFT, DO NOT FREEZE; **D20 REJECT real data creation, collection, labeling, storage and manifest creation for this phase (row status REJECT)**; E3 APPROVE SCHEMA-2 OFFLINE IMPLEMENTATION ONLY (the row, which asks for a real manifest, stays unresolved); E4 KEEP DOCUMENTED DIFFERENCE for all six; R14 KEEP UNRESOLVED. Preserved: A3.1, A3.2 (non-commercial offline evaluation only), A3.4, A3.5a, A3.7, A3.8; D3 (fictional text is synthetic, never `validated`); D4, D6 to D13, D15, D17, D18. Form: 44 APPROVE, 2 REJECT (A3.5, D20), 0 BLOCKED, 10 KEEP UNRESOLVED. No FinBERT download, Hugging Face access, real inference, training, real text, real register or manifest, or validation claim. These approval requests are closed for this phase and are not repeated; real Hugging Face use or real-data evaluation would be a new phase with a new explicit approval request. Production method `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`; real model downloaded: no; real dataset created: no; real evaluation run: no; production activation: no; intensity regression: disabled; blockchain / ledger sentiment payload: none.

## Final-state verification (2026-10-30)

No decision changed. The final state was verified directly (runtime probe with the network blocked, a fresh-interpreter import check, 1,652 offline tests with external sockets blocked and counted: 0 attempts). Production method `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`; real model not downloaded; real dataset not created; real evaluation not run; production activation not performed; intensity regression disabled; ledger / blockchain sentiment payload none. The offline rules-based sentiment phase is complete; Transformer evaluation, real dataset creation and production activation remain deferred.

## Transformer enablement requested (2026-11-03): pre-flight BLOCKED, nothing enabled

A brief asked for the Transformer to be enabled end to end, conditional on every pre-flight gate (legal, dependencies, dataset, evaluation) being approved, and to stay fail-closed and report the exact blocker otherwise. It supplied no approval. The read-only command `scripts/sentiment_preflight.py` (tested by `tests/backend/scripts/test_sentiment_preflight.py`) reports gates 1 to 6 BLOCKED and the safe-state gate 7 passing: A3.3 unresolved and A3.5b rejected; `torch`, `transformers`, `tokenizers` and `safetensors` not installed in the project environment; D1, D2, D5, D14, D16, D19 unresolved and D20 rejected; no frozen manifest, evaluation or calibration; no `model.safetensors` anywhere; R14 unresolved. Per the phase closure of 2026-10-30, enabling would be a new phase with a new explicit approval request; the one consolidated request is in the report of this date. Nothing was downloaded, installed, generated, evaluated or enabled; `user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`, intensity null, no ledger payload.

## Scoped owner decision: Horizon multilingual sentiment, research inference only (2026-11-04)

Recorded from the project owner's instruction: `Horizon-Labs/multilingual-sentiment-small` at `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` may be considered for research inference only, accepting its disclosed web-crawl and LLM-generated training data and the absence of human-validated labels.
This is **not** a resolution of A3.3 in general, A3.5 (rejected), D20 (rejected), F1/R14 or any dataset gate, and it authorises no production activation, dataset creation, fine-tuning, automatic download, redistribution, commercial use, validation claim or financial-decision impact. Installation, download, inference and the registry change each need a separate approval. See ADR-054 (addendum) and `docs/sentiment/horizon_runtime_plan.md`. The consolidated approval form is unchanged.
