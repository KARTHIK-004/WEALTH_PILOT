# Request for approval: Transformer sentiment model — packages, model weights, dataset (ADR-052)

Written for: the project owner, who must decide before anything is installed or downloaded. Nothing in this report has been installed, downloaded or run; **no Transformer model is active, trained or validated**.

## 1. Why a decision is needed

Running a pretrained Transformer needs packages outside the approved stack (`CLAUDE.md` section 5) and weights that are not in the repository. What IS installed: TensorFlow 2.17.0, Keras 3.15.1, scikit-learn 1.5.2, numpy 1.26.4, Python 3.11.9. **Not installed**: `torch`, `transformers`, `tokenizers`, `safetensors`. The `transformers` v5 line is reported to drop TensorFlow / Flax support (v4 stays as the long-term-support branch), so the installed TensorFlow cannot be the practical backend; PyTorch is.

## 2. Packages requested

| Package | Reason | Version | Licence | Approx. size | CPU / GPU | Security and maintenance |
| --- | --- | --- | --- | --- | --- | --- |
| `torch` (CPU build) | tensor runtime for inference and fine-tuning | pin an exact 2.x version after approval (must support Python 3.11 and numpy 1.26) | BSD-style (to verify from the project's LICENSE) | the CPU wheel is a few hundred MB; installed size roughly 1 GB (approximate, unverified) | CPU is enough; no GPU is required or used | very large dependency surface; checkpoint loading by `torch.load` can execute pickled code — mitigated here by accepting `safetensors` only |
| `transformers` | model and tokenizer classes | the 4.x line (long-term support), exact pin after approval | Apache-2.0 (to verify) | tens of MB installed | CPU | `trust_remote_code=False` is enforced; models are loaded only from a local, hash-verified directory |
| `tokenizers` | fast tokenisation | the version `transformers` requires | Apache-2.0 (to verify) | a few MB | CPU | native code |
| `safetensors` | the only accepted weights format | the version `transformers` requires | Apache-2.0 (to verify) | under 1 MB | CPU | memory-safe loading; no code execution |

Versions and sizes above are NOT verified (no network access was used for installation checks). The licences listed are from general knowledge and a limited web search that could not confirm them; the owner should read each package's own LICENSE.
Mitigations if approved: exact version pins in `backend/pyproject.toml`, hash-pinned install, `HF_HUB_OFFLINE=1` when serving, packages only under a `sentiment` optional-dependency group so the default install is unchanged.

## 3. Models (weights) to evaluate — none downloaded

| Candidate (identifier only) | Role | Typical weight size | Licence |
| --- | --- | --- | --- |
| `ProsusAI/finbert` | pretrained financial-language sentiment model | ~440 MB | **not confirmed** (the model card could not be read through the search tool); read its card and its training-data terms |
| `FacebookAI/roberta-base` | general-language comparison, new head | ~500 MB | to verify |
| `distilbert/distilroberta-base` | smaller general-language comparison | ~330 MB | to verify |
| rules baseline (`user_text_rules_v1`) | always evaluated | none | project code |

A fine-tuned model inherits the terms of its base model AND of its training data. The first download is a network request made by an operator running `train_sentiment_transformer.py`; the application never downloads anything.

## 4. Dataset — none approved

The only public financial-sentiment set named in the research, **Financial PhraseBank** (Malo et al.), is listed on its Hugging Face dataset card as **CC BY-NC-SA 3.0** — non-commercial and share-alike, which a derived model's weights inherit (source: the dataset card; a primary statement from the authors was not found). It is also **news/company sentiment**, not a person's own statements about savings, debts, goals, liquidity and investment worries, so a model validated on it is not thereby validated for WealthPilot input (`training/sentiment/config.py::DOMAIN_NOTE`). For a continuous intensity head, a dataset with annotator scores in [-1, 1] is needed (for example FiQA-style data; its licence is not checked here).
The project's own pilot pack and rubric examples are invented / unannotated and are never training or validation data.

## 5. What is already built (needs none of the above)

`core/sentiment_model.py` (verification, cache, calibration, abstention, fallback), the policy in `analyse_user_text`, `training/sentiment/` (manifest gate, loader, split, metrics, calibration, artifact writer, evaluation), the API / frontend states, configuration (default off) and tests with fake backends. Not exercised, because it needs the packages: `TransformersBackend` and `fine_tune_with_torch`.

## 6. Decisions needed

1. Approve (or change) the packages, exact versions and the optional-dependency approach. 2. Approve the model candidates and the one-time weight download. 3. Approve a licensed labelled dataset of personal-finance statements (or accept a news dataset as a development aid only, under its terms). 4. Set the precision and coverage targets (`--target-precision`, `--min-coverage`, `--high-precision`, `--high-min-coverage`) for the abstention threshold and confidence bands. 5. Decide whether an intensity (regression) head is wanted and supply intensity labels. 6. Set the minimum held-out test size for "validated" (structural minimum today: 200). 7. Choose the final model from the measured evaluation report, not from reputation.

Commands once approved: see `training/sentiment/README.md`.


---

# Addendum 2026-10-27 — Approval package for the sentiment-model research phase

Written for: the project owner, who must decide each item in section F. **Nothing in this addendum installs, downloads, trains, evaluates, collects or activates anything.** The rules baseline `user_text_rules_v1` stays the only active method, `SENTIMENT_MODEL_ENABLED=false`, and ADR-052 is unchanged: no Transformer is installed, no weights are downloaded, no dataset is approved, no model is validated, and activation is not allowed.

**How to read the evidence labels.** Every claim below carries one of: **VERIFIED** (read in a web-search result of this session; the source is named; still a secondary read, not a local test), **OWNER-SUPPLIED** (stated in the owner's brief for this phase; not independently verified by me), **ESTIMATE** (from general knowledge; to be confirmed against the package index or model card before approval), or **UNRESOLVED**. **No package was installed or tested locally, so no compatibility or size below is a test result.**

## A. Dependency proposals (exact versions as proposed by the owner)

Environment facts (VERIFIED locally by reading `pip list`): Python 3.11.9, numpy 1.26.4, scikit-learn 1.5.2, TensorFlow 2.17.0, Keras 3.15.1; `torch`, `transformers`, `tokenizers`, `safetensors` are **not** installed; `backend/pyproject.toml` lists none of them.

| | `torch==2.6.0` (CPU build) | `transformers==4.57.1` | `tokenizers==0.22.1` | `safetensors==0.6.2` |
| --- | --- | --- | --- | --- |
| Purpose | tensor runtime for CPU inference and (offline) fine-tuning | model and tokenizer classes, sequence-classification heads | fast subword tokenisation | the only accepted weights format (no pickle) |
| Licence | BSD-3-Clause — ESTIMATE (read the package's LICENSE) | Apache-2.0 — VERIFIED for the project (PyPI project page lists the Apache 2.0 licence); the 4.57.1 page itself was not read | Apache-2.0 — ESTIMATE | Apache-2.0 — ESTIMATE |
| Release facts | 2.6.0 is a General Availability release, published on PyPI and download.pytorch.org (no conda) — VERIFIED (PyTorch GA announcement) | 4.57.1 appears in the release history and is not yanked; 4.57.0 was yanked for a setup error — VERIFIED (PyPI search snippet) | released 19 Sep 2025 — VERIFIED (PyPI release history snippet) | released 8 Aug 2025 — VERIFIED (PyPI release history snippet) |
| Python 3.11 | ESTIMATE: cp311 wheels exist (the 2.6 line supports roughly 3.9–3.13; the announcement VERIFIED only 3.13 for `torch.compile`) | ESTIMATE: the 4.x line supports 3.9+ (older 4.x pages list 3.9+; the 4.57.1 page was not read) | ESTIMATE: ABI3 wheels cover 3.11 (requires-python of 0.22.1 not read) | ESTIMATE: as tokenizers (requires-python of 0.6.2 not read) |
| Windows CPU | ESTIMATE: Windows wheels from PyPI are CPU builds; `torch==2.6.0` from `https://download.pytorch.org/whl/cpu` is the explicit CPU channel (the channel's existence for 2.6.0 VERIFIED from the announcement's install command; the specific `win_amd64` wheel was not seen) | ESTIMATE: pure Python, platform independent | ESTIMATE: `win_amd64` wheel expected | ESTIMATE: `win_amd64` wheel expected |
| Wheel size / installed size | ESTIMATE: roughly 200–250 MB wheel; roughly 0.6–1.2 GB installed including transitive packages | ESTIMATE: roughly 10–12 MB wheel; 50–70 MB installed | ESTIMATE: roughly 2–4 MB wheel | ESTIMATE: well under 1 MB |
| Native components | yes (C++, vendor math libraries and OpenMP DLLs) | no (pure Python) | yes (Rust extension) | yes (Rust extension) |
| CPU memory (inference) | ESTIMATE: importing torch adds a few hundred MB; a 110M-parameter FP32 model is about 0.45 GB of weights, so about 1–1.5 GB resident per serving process — and the same process also holds the existing TensorFlow models | small | small | maps the weights file rather than copying it |
| Security risks | `torch.load` of a pickle checkpoint can execute code (mitigated: safetensors only, never pickle); large native attack surface; check published security advisories for this exact version before approval (not done) | `trust_remote_code=True` would execute downloaded code (mitigated: `False`); bundled network helpers (`huggingface-hub`, `requests`) can download weights (mitigated: `local_files_only=True` and offline environment variables when serving) | native parser of untrusted tokenizer files (the tokenizer files are hash-verified artifacts) | memory-safe format by design; native parser |
| Transitive packages (ESTIMATE from general knowledge of the metadata; resolve with a dry-run once approved) | `filelock`, `typing-extensions`, `networkx`, `jinja2` (+ `MarkupSafe`), `fsspec`, `sympy` (+ `mpmath`) | `huggingface-hub`, `numpy`, `packaging`, `pyyaml`, `regex`, `requests` (+ `urllib3`, `idna`, `certifi`, `charset-normalizer`), `tokenizers`, `safetensors`, `tqdm`, `filelock` | `huggingface-hub` | none expected |

**Coexistence risks with what is installed (ESTIMATE, none tested):** TensorFlow 2.17 and PyTorch load in the same Python process (the backend loads the Keras market models); on Windows two native stacks with OpenMP / oneDNN libraries can conflict (DLL or runtime-library clashes), and two frameworks multiply memory. numpy 1.26.4 is expected to remain acceptable for both. A pip resolution could still move shared packages (`typing-extensions`, `numpy`, `protobuf`-related pins); `pip check` and the full test suite are the guard.

**Proposed commands — NOT RUN, NOT APPROVED.** Run only in the interpreter of the project's `.venv`, only after the owner marks D1 and D2 APPROVED:

```
.venv\Scripts\python.exe -m pip freeze > reports\_env_before_sentiment.txt          # local record, not committed
.venv\Scripts\python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python.exe -m pip install transformers==4.57.1 tokenizers==0.22.1 safetensors==0.6.2
```
Preferred if approved: a hash-pinned requirements file produced from the first install in an isolated environment and installed with `--require-hashes`, and the packages declared as an optional dependency group (for example `sentiment`) in `backend/pyproject.toml` so the default installation is unchanged. Neither file exists yet; no manifest was edited in this phase.

**Verification commands — proposed, not run:**
```
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -c "import torch, transformers, tokenizers, safetensors; print(torch.__version__, torch.cuda.is_available(), transformers.__version__, tokenizers.__version__, safetensors.__version__)"
.venv\Scripts\python.exe -c "import tensorflow, torch; print('coexist')"          # both frameworks in one process
.venv\Scripts\python.exe -m training.sentiment.train_sentiment_transformer --check-environment
.venv\Scripts\python.exe -m pytest tests/backend tests/training -q                 # the full suite after install
```
**Rollback plan:** before any install record `pip freeze`; the install changes only the virtual environment, never the repository, and `SENTIMENT_MODEL_ENABLED=false` keeps the application on the rules baseline throughout. To roll back: `pip uninstall -y torch transformers tokenizers safetensors` plus every package that appears in the freeze difference (`huggingface-hub`, `sympy`, `networkx`, ... — compute from the before / after freeze files), confirm `pip freeze` equals the saved file, run `pip check` and the full suite. If the environment is damaged, recreate `.venv` from `backend/pyproject.toml`. Because the packages would sit in an optional group, "not installing the group" is also a complete rollback.

## B. Security requirements, and where each is (or is not yet) enforced

| Requirement | State in the code today |
| --- | --- |
| CPU-only installation | serving enforces `SENTIMENT_MODEL_DEVICE=cpu` (anything else is `invalid_configuration`); the CPU wheel channel is a proposed install step, not enforced |
| `safetensors` weights only, no pickle checkpoints | enforced: the artifact must list `model.safetensors` (a `pytorch_model.bin` listing is refused) and loading passes `use_safetensors=True` |
| `trust_remote_code=False` | enforced in `TransformersBackend` (source-checked by a test) |
| `local_files_only=True` during serving | enforced in `TransformersBackend`; the training script is the only code that may download, and only when an operator runs it |
| artifacts only under `models/sentiment/` | enforced (`resolve_artifact_directory`: no `..`, no symlink, strictly inside the root) |
| SHA-256 verification | enforced for every file listed in the metadata |
| **exact model revision required** | **NOT YET ENFORCED.** The metadata records `base_model` (the hub identifier) but no commit hash, and `fine_tune_with_torch` loads the hub's default revision. A required `base_model_revision` field and a `revision=` argument are a **runtime change that this phase does not make**; they are listed as a follow-up to implement before any download |
| no model download during application start-up | satisfied by design (the model loads lazily on the first request, offline); proposed extra guard: set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` in the serving environment |
| no external API call containing user text | satisfied (local inference; no network import in the sentiment modules; tested) |

## C. Model candidate register (static; nothing downloaded; none validated for WealthPilot)

| | **A — `ProsusAI/finbert`** | **B — `cardiffnlp/twitter-roberta-base-sentiment-latest`** | **C — `FacebookAI/roberta-base` (or another owner-approved RoBERTa-family base)** |
| --- | --- | --- | --- |
| Proposed role | financial-language comparison model | general-language / social-text comparison model | future fine-tuning candidate (needs a training set; has no sentiment head) |
| Labels | positive, negative, neutral — OWNER-SUPPLIED (the order must be read from the model's own `config.json` at approval, never assumed) | negative, neutral, positive — OWNER-SUPPLIED (note: a different order from A; the artifact writer re-maps by name) | none (a new classification head would be trained) |
| Verified facts | the repository exists on Hugging Face with tags text-classification, English, financial-sentiment-analysis and PyTorch / TensorFlow / JAX weights — VERIFIED (search listing); a mirror cites arXiv:1908.10063 — VERIFIED (listing) | the repository exists; one page snapshot lists the licence tag `cc-by-4.0` and cites arXiv:2202.03829 — VERIFIED (single secondary snapshot; the model card text itself was not read) | none verified |
| Licence | **UNRESOLVED.** OWNER-SUPPLIED: CC BY-NC-SA 4.0. My searches could not read the model card, so I can neither confirm nor contradict it; the owner must read the card | CC BY 4.0 — OWNER-SUPPLIED and consistent with the VERIFIED snapshot tag; terms beyond the tag not read | **UNRESOLVED** (a recollection of what the card says is not a verification) |
| Known training data | OWNER-SUPPLIED: Financial PhraseBank and a Reuters TRC2-related corpus (consistent with the FinBERT paper as I recall it; not verified here) | an aggregator page (secondary, UNVERIFIED) says roughly 124 million tweets from 2018–2021; fine-tuning data unverified | UNRESOLVED (general web / book corpora; provenance not verified) |
| Unresolved dataset provenance | yes: the corpora's own licences and any restriction they pass to derived weights | yes: tweets carry platform terms and third-party content questions | yes |
| Domain mismatch | financial NEWS about companies, not a person's own financial narratives | SOCIAL-MEDIA language (short, informal, emoji, hashtags), not personal finance | general language; no financial domain knowledge |
| Commercial use restricted | **yes if the NC licence is confirmed**; a share-alike term would also bind a fine-tuned derivative | CC BY allows commercial use with attribution, but the underlying data terms are UNRESOLVED | UNRESOLVED |
| Exact revision (commit hash) | UNRESOLVED until owner approval | UNRESOLVED until owner approval | UNRESOLVED until owner approval |
| Weight download | **not approved** | **not approved** | **not approved**; no weights may be downloaded |
| Typical size | ~440 MB — ESTIMATE | ~500 MB — ESTIMATE | ~500 MB — ESTIMATE |
| Status | not validated for WealthPilot; zero-shot use possible only after approval | not validated for WealthPilot | cannot be evaluated at all until a training set is approved |

An open licence question on A that the owner should settle in writing: the dataset it was built on (Financial PhraseBank, section D) is listed at CC BY-NC-SA **3.0** while the supplied licence of A is **4.0**; whether a model fine-tuned further on that data can carry either licence is a legal question this project cannot answer here.

## D. Dataset approval register

**Financial PhraseBank — candidate development benchmark ONLY; not approved for download.**

| Item | State |
| --- | --- |
| Licence | CC BY-NC-SA 3.0 — VERIFIED from its Hugging Face dataset card (secondary read; the authors' own statement was not found): non-commercial and share-alike; the card asks anyone wanting commercial use to contact the authors; a derived model is reported to inherit the terms |
| Content | English sentences from financial news about companies — VERIFIED (descriptions) |
| Labels | positive, negative, neutral — OWNER-SUPPLIED and consistent with the descriptions |
| Size | about 4,800 sentences; sources disagree (4,835 / 4,840 / 4,845) — VERIFIED that they disagree; the exact count must be taken from the approved file |
| Agreement subsets | 50%, 66%, 75% and 100% annotator-agreement subsets exist — VERIFIED (descriptions) |
| Official split | none — OWNER-SUPPLIED; this project would build its own, group-aware, seeded split (`training/sentiment/dataset.py`) |
| Fit | NOT suitable as the sole evidence for personal-finance narratives: different subject (companies), voice and vocabulary |
| Approval | **UNRESOLVED** (checklist D7); it may only ever be a development benchmark, never validation evidence for WealthPilot |

**Other facts.** The repository's rubric examples (`datasets/rubric_examples/user_text_rubric_examples_v0.jsonl`) and the 30-text pilot pack are **synthetic / fictional and unannotated by design** — they can never be validation data. **No real user text may be collected** (O1 is accepted for fictional notes only). **No personal-finance validation dataset exists, and no label or metric may be fabricated.**

**Proposed specification of a new, independent, held-out set** — 300 personal-finance statements; the quotas, coverage requirements and annotation protocol with their numbers are in section G below; the protocol without numbers is in `docs/USER_TEXT_VALIDATION_DECISION_SHEET.md`, section "Addendum 2026-10-27". The statements are **not created** and will not be unless the owner separately approves fictional-data generation (D8).

## E. Evaluation plan (future; needs every approval in section F first)

1. **Candidates**: (1) the current rules baseline `user_text_rules_v1`; (2) FinBERT (A); (3) one approved general RoBERTa-family candidate (C, fine-tuned on an approved training set that is disjoint from the held-out set). Candidate B may be added as a social-text reference if approved. Each is scored once, identically, on the frozen held-out set.
2. **Metrics**: accuracy; macro-F1; precision and recall per class; confusion matrix; **95% confidence intervals** (proposal: stratified bootstrap, 2,000 resamples, seed 42; Wilson intervals for proportions; a paired bootstrap for the difference to the rules baseline); inter-annotator agreement (Cohen's kappa between the two annotators, Krippendorff's alpha as a cross-check, per-class agreement); calibration (reliability table) and **expected calibration error**; **abstention rate** and **coverage**; precision on accepted predictions at that coverage (a risk–coverage curve, not a single point); performance **by topic**, **by difficulty**, on **negation**, on **contradictory text** and on **unsupported / code-mixed text**; the comparison with the rules baseline. A subgroup with fewer than 20 statements is reported as descriptive only.
3. **Two views of every headline number**: *selective* (only accepted predictions, with coverage beside it) and *strict* (an abstention counts as wrong). The model must be judged on both.
4. **Proposed acceptance targets** (PROPOSALS, to be reviewed — not approved): **macro-F1 ≥ 0.80** and **precision ≥ 0.85 on accepted predictions**. They must be reviewed against the final class distribution, annotation agreement, abstention coverage, confidence calibration and personal-finance domain fit. With about 80 statements per class a 95% interval is wide (several points either way), so a point estimate at the target is weak evidence; the owner should decide whether the **lower interval bound** must also clear a floor (UNRESOLVED).
5. **No activation by abstaining**: a model must not be activated if it reaches high precision only by abstaining on nearly all inputs. The minimum coverage is an owner decision (D13); no number is fixed here. Any candidate whose coverage falls below it fails regardless of precision.
6. **Calibration data**: the temperature and the abstention threshold must be fitted on data that is **separate** from the held-out set (proposal: a second, separately annotated personal-finance set, or an explicitly documented limitation if only a news-domain set is available — D14). The held-out set is never used to tune anything.
7. **Proposed activation criteria** (all required; each still needs owner approval, D15): the frozen held-out set exists and is large enough; agreement meets the owner's floor; the targets above are met with the reviewed interval rule; coverage meets the owner's minimum; ECE meets the owner's ceiling; every primary class meets a recall floor; the model is at least as good as the rules baseline on the paired comparison and not worse on negation, contradictory or code-mixed text; the licence, the exact revision and the dependencies are approved; and activation is a separate owner decision recorded in a new ADR. Activation changes only `SENTIMENT_MODEL_ENABLED` and the artifact settings; rollback is setting it back to `false`.
8. **Intensity regression is deferred and stays disabled** until a separate approval is granted, continuous human intensity labels exist, and a separate evaluation protocol is approved. The API keeps returning `sentiment_intensity: null`.

## F. Owner approval checklist

Every item is **UNRESOLVED** unless the owner has said otherwise; silence is not approval. Fill the last three columns when deciding.

| Id | Decision | State | Decided by | Date | Note |
| --- | --- | --- | --- | --- | --- |
| D1 | Approve or reject the exact dependency versions: `torch==2.6.0` (CPU), `transformers==4.57.1`, `tokenizers==0.22.1`, `safetensors==0.6.2` | UNRESOLVED | | | |
| D2 | Approve CPU-only PyTorch (and the optional-dependency-group / hash-pinned install approach) | UNRESOLVED | | | |
| D3 | Approve the FinBERT licence for this academic project (supplied as CC BY-NC-SA 4.0; model card to be read by the owner) | UNRESOLVED | | | |
| D4 | Approve the FinBERT exact revision (commit hash to be read and recorded) | UNRESOLVED | | | |
| D5 | Approve the general RoBERTa-family candidate and its exact revision (and its licence) | UNRESOLVED | | | |
| D6 | Approve `cardiffnlp/twitter-roberta-base-sentiment-latest` as a comparison candidate (licence, revision) | UNRESOLVED | | | |
| D7 | Approve Financial PhraseBank as development-only data (CC BY-NC-SA 3.0; download and its licence-compatibility with D3) | UNRESOLVED | | | |
| D8 | Choose fictional-statement generation versus consented participant statements for the 300-statement set (and who may author them) | UNRESOLVED | | | |
| D9 | Approve the annotator and adjudicator process (two independent annotators, a third adjudicator, blinded) and name the people | UNRESOLVED | | | |
| D10 | Approve the 300-statement target as a proposed minimum | UNRESOLVED | | | |
| D11 | Approve the class-balance policy (at least 75 per primary class where feasible; exact counts reported) | UNRESOLVED | | | |
| D12 | Approve the macro-F1 and precision targets (proposed 0.80 and 0.85) and whether a lower-interval-bound floor applies | UNRESOLVED | | | |
| D13 | Approve a minimum coverage (no number proposed) | UNRESOLVED | | | |
| D14 | Approve the confidence / calibration policy (method, ECE ceiling, source of the separate calibration set) | UNRESOLVED | | | |
| D15 | Approve the future model-activation criteria (section E.7) | UNRESOLVED | | | |
| D16 | Keep intensity regression deferred and disabled | **APPROVED** — the owner's instruction in the brief of 2026-10-27 ("Document that intensity regression is deferred and must remain disabled until ...") | project owner | 2026-10-27 | no further approval implied: lifting it needs its own approval, labels and protocol |

Standing restrictions in force for this phase (instructions, not checklist decisions): no package installed; no weights, dataset or other download; no real user text collected; no training or fine-tuning; no commit or push; rules baseline `user_text_rules_v1` active with `SENTIMENT_MODEL_ENABLED=false`; no change to risk, goals, portfolio, recommendation, savings-first or compliance logic.


## G. Proposed held-out set and annotation protocol — with the numbers (PROPOSALS, none approved)

These figures are the owner's proposals recorded for review (checklist D8–D11, D12–D14). The decision sheet carries the protocol without numbers because its guard forbids numeric thresholds in that packet.

**Size and class balance.** A new, independent set of **300** personal-finance statements, written as a **proposed minimum, not automatic proof of validity**. Initial class quotas (annotation labels, after adjudication): positive 80, negative 80, neutral 80 — the three primary classes, **at least 75 each where feasible** — plus mixed 30 and uncertain 30 (low-information, unrelated or unsupported-language text). Report the **exact class counts** and a **class-specific interval** for every class. **No validation is claimed if any primary class has inadequate support.** With roughly 80 statements per class a 95% interval around a class-level proportion is several points wide on each side, and subgroups are smaller still.

**Coverage requirements (a statement may count in several).** Each of these topics at least 25 statements: investment concerns; savings; debt; liquidity; emergency fund; retirement; financial goals; market concerns. Wording phenomena at least: negation 30; contradictory preferences 20; low-information text 20; unsupported or code-mixed text 15. Difficulty tags easy / moderate / hard, at least 30% hard. A subgroup with fewer than 20 statements is descriptive only.

**Annotation.** Two independent annotators per statement; a third adjudicator for disagreements; annotators blinded to every model and rules output; they see only the statement id and the text; no profile, risk or customer data; no real user text before consent and retention approval; de-identification, access restriction, retention and deletion as in the decision sheet addendum; the rubric version, the text manifest and the labels frozen and recorded with SHA-256 hashes; duplicate and near-duplicate checks (proposal: token-set similarity of 0.8 or more, and shared sentence templates); calibration data separate from validation data. Agreement is reported as Cohen's kappa, Krippendorff's alpha and per-class agreement; a floor below which evaluation does not proceed is an owner decision (UNRESOLVED).

**Authoring conditions (if fictional generation is approved, D8).** Authors are independent of the rubric author and of the baseline's cue lists and do not see them, so the statements do not echo the rules; nothing is copied from a benchmark; no names, numbers, employers or account details.

**Statistics.** 95% intervals by stratified bootstrap (proposal: 2,000 resamples, seed 42) and Wilson intervals for proportions; a paired bootstrap for the difference between a model and the rules baseline; selective and strict views of every headline number (section E.3).

**Targets under review** (section E.4): macro-F1 0.80 or higher; precision 0.85 or higher on accepted predictions; minimum coverage, ECE ceiling, agreement floor and per-class recall floor are unresolved and have no proposed value.

## H. Status update 2026-10-26 — approval gate checked, still closed

The brief to proceed with the isolated compatibility phase was conditional on recorded owner decisions. None was supplied, so every checklist item in section F stays UNRESOLVED (D16, keep intensity regression deferred, stays APPROVED), and the phase was **not started**: no package installed, no environment created, no weight or dataset downloaded or looked up, nothing changed in code or configuration. The decision matrix (R1-R14), the exact blocker, the planned isolated test and the next approval required are in `reports/sentiment_model_approval_record.md`. All sizes, compatibility statements and licences in sections A and C are still estimates or owner-supplied claims; no compatibility or security-advisory check has been run.

## I. Isolated compatibility phase 2026-10-26 — resolution, hashes and advisories VERIFIED; installation NOT performed (advisory blocker)

Evidence labels as above. This section records what the isolated phase established with a disposable environment outside the repository (`C:\Users\Administrator\.copilot\sentiment-compatibility-venv`, Python 3.11.9, pip 24.0, no pip configuration so the default PyPI index). Only dry-run resolution and metadata queries were run; **no package was installed** into that environment, no model weight, tokenizer, dataset or Hugging Face asset was touched, and no repository file other than documentation changed.

**VERIFIED (pip 24.0 on Python 3.11.9 / Windows amd64; PyPI JSON; OSV `querybatch` and per-record lookups):**

- Wheels exist for exactly the approved pins on this platform: `torch-2.6.0-cp311-cp311-win_amd64.whl`, `tokenizers-0.22.1-cp39-abi3-win_amd64.whl`, `safetensors-0.6.2-cp38-abi3-win_amd64.whl`, `transformers-4.57.1-py3-none-any.whl`. None is yanked. No source build is needed.
- `pip install --dry-run` resolves the four pins **without a conflict** in two ways: (a) unconstrained, which pulls `numpy 2.4.6` (23 packages in all); (b) with `numpy==1.26.4`, the version the project's TensorFlow 2.17 environment uses (24 packages, table below). TensorFlow 2.17's own numpy ceiling is a known requirement that the coexistence test would have confirmed; it was not run.
- Every wheel SHA-256 reported by pip equals the digest PyPI publishes for that file (24 of 24; zero mismatches). Total wheel download size: **246.2 MB** (torch 204.2 MB).
- Licences, from PyPI metadata: `torch` BSD-3-Clause; `transformers` Apache-2.0; `tokenizers` Apache; `safetensors` Apache; the transitive set is permissive (MIT, BSD, Apache-2.0, PSF-2.0) except `certifi` MPL-2.0 and `tqdm` MPL-2.0 AND MIT, which are file-level copyleft and need the owner's attention only if they are redistributed. Licence text was read from metadata only, not from the wheels.
- Security advisories (OSV): **`torch==2.6.0` has 24 records and `transformers==4.57.1` has 12**; none of the other 22 packages has one. The 24 torch records are 22 distinct CVEs (two are duplicate PYSEC entries); the 12 transformers records are 7 distinct CVEs. PyPI's own `vulnerabilities` field lists the same counts. None is withdrawn.

**NOT verified (not run, because of the blocker below):** installation on Windows, installed size, imports, `torch` CPU-only behaviour (`torch.version.cuda`, `torch.cuda.is_available()`), tokenizer / safetensors / stand-in-model smoke test, TensorFlow 2.17 + PyTorch coexistence, `pip check`. These remain ESTIMATES or unknown.

**Blocker.** The owner's rule: stop and report if an advisory is unresolved, and do not substitute versions. The approved pins carry published advisories, and for most of them OSV records a fix only in a later release (torch 2.7.0, 2.7.1, 2.8.0, 2.9.0, 2.9.1, 2.10.0, 2.13.0; transformers 5.0.0, 5.3.0, 5.5.0, 5.10.0) or no fix at all. Changing a version is not permitted without a new approval, and no risk acceptance is recorded. So the install was stopped before it started.

**Advisory triage (my reading of the OSV text; a preliminary aid, not a decision and not a security review):**

| Group | Records (count) | What the text says | Relevance to the planned use (local, CPU, safetensors only, `trust_remote_code=False`, `local_files_only=True`) |
| --- | --- | --- | --- |
| torch: local denial of service / memory corruption in specific operators (`mkldnn_max_pool2d`, `lstm_cell`, `jit.script`, `unpack_sequence`, `pad_packed_sequence`, quantised sigmoid, tuple handler) | 7 CVEs: 2953, 2998, 3001, 3000, 2999, 2148, 2149 (8 records) | Local attack, specific operators; fixes in 2.7.1 to 2.13.0 or none | A BERT-style classifier is not expected to call these; not verified |
| torch: unpickler / `pt2` loader (`weights_only` bypass CVE-2026-24747, `pt2` loading CVE-2026-4538) | 2 CVEs: 2026-24747, 2026-4538 | Malicious checkpoint (`.pth` / pickle) when loaded; fixed 2.10.0 or none | Applies to pickle-style checkpoints; the project loads only `.safetensors` and verifies SHA-256 first; the safetensors-only rule is the control |
| torch: correctness / compile (Inductor, `torch.compile`) / other-version records (CVE-2025-46148 to 46153, 55551 to 55560, 3730) | 13 CVEs | Wrong results or compile-time crashes, mostly fixed in 2.7.0 to 2.9.0; several descriptions name another version although OSV matches 2.6.0 | Eager CPU inference without `torch.compile`; not verified |
| transformers: remote code execution through a crafted `config.json` (CVE-2026-4372, fixed 5.3.0) | 2 | The text describes a crafted `config.json` field | **Not shown to be mitigated by `trust_remote_code=False`**; the description does not say it is. The loader's directory is verified by hash, but this needs a specific check before any claim |
| transformers: `Trainer` checkpoint loading (CVE-2026-1839, fixed 5.0.0); LightGlue (CVE-2026-5241); X-CLIP and GLM4 conversion (CVE-2025-14929 / 14930) | 6 | Arbitrary code through `torch.load` or model-specific paths | Not the sentiment inference path; whether the offline training script uses `Trainer` was not checked |
| transformers: `save_pretrained` path traversal (CVE-2026-9856, fixed 5.10.0); custom generation code consent (CVE-2026-80047, no fix) | 4 | File write via chat template names; custom code download | Not used for classification; not verified |

**Resolved package set (numpy pinned to 1.26.4; hash-checked against PyPI; reproducible with `pip install --require-hashes`):**

| Package | Version | Role | Wheel file | Size | SHA-256 (pip report) | PyPI JSON digest | Licence (PyPI metadata) | OSV records |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| certifi | 2026.10.23 | transitive | `certifi-2026.10.23-py3-none-any.whl` | 0.1 MB | `e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1` | match | Mozilla Public License 2.0 (MPL 2.0) | 0 |
| charset-normalizer | 3.5.2 | transitive | `charset_normalizer-3.5.2-cp311-cp311-win_amd64.whl` | 0.2 MB | `87e50a3e7cb90af586b6c5faf23e302a970415ac73bd7bd90a515a04b427ef96` | match | MIT | 0 |
| colorama | 0.4.6 | transitive | `colorama-0.4.6-py2.py3-none-any.whl` | 0.0 MB | `4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6` | match | BSD License | 0 |
| filelock | 4.2.4 | transitive | `filelock-4.2.4-py3-none-any.whl` | 0.2 MB | `301241438c57936ef93f4243a94f2559022268bfcf9b375a9a72eb0f8db8358e` | match | MIT | 0 |
| fsspec | 2026.9.0 | transitive | `fsspec-2026.9.0-py3-none-any.whl` | 0.2 MB | `8dd6e646e99ea382bd85f97a45e6b526a442d79423a7dc673f1e2756d05fcb5f` | match | BSD-3-Clause | 0 |
| huggingface_hub | 0.36.2 | transitive | `huggingface_hub-0.36.2-py3-none-any.whl` | 0.6 MB | `48f0c8eac16145dfce371e9d2d7772854a4f591bcb56c9cf548accf531d54270` | match | Apache Software License | 0 |
| idna | 3.20 | transitive | `idna-3.20-py3-none-any.whl` | 0.1 MB | `ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c` | match | BSD-3-Clause | 0 |
| Jinja2 | 3.1.6 | transitive | `jinja2-3.1.6-py3-none-any.whl` | 0.1 MB | `85ece4451f492d0c13c5dd7c13a64681a86afae63a5f347908daf103ce6d2f67` | match | BSD License | 0 |
| MarkupSafe | 3.0.4 | transitive | `markupsafe-3.0.4-cp311-cp311-win_amd64.whl` | 0.0 MB | `fdb4ca07ab75ffadab4a8b135ad59cdbb3156b99310f3d565370da74a15d6bd3` | match | BSD-3-Clause | 0 |
| mpmath | 1.3.0 | transitive | `mpmath-1.3.0-py3-none-any.whl` | 0.5 MB | `a0b2b9fe80bbcd81a6647ff13108738cfb482d481d826cc0e02f5b35e5c88d2c` | match | BSD License | 0 |
| networkx | 3.6.1 | transitive | `networkx-3.6.1-py3-none-any.whl` | 2.1 MB | `d47fbf302e7d9cbbb9e2555a0d267983d2aa476bac30e90dfbe5669bd57f3762` | match | BSD-3-Clause | 0 |
| numpy | 1.26.4 | requested | `numpy-1.26.4-cp311-cp311-win_amd64.whl` | 15.8 MB | `cd25bcecc4974d09257ffcd1f098ee778f7834c3ad767fe5db785be9a4aa9cb2` | match | BSD License | 0 |
| packaging | 26.3 | transitive | `packaging-26.3-py3-none-any.whl` | 0.1 MB | `d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c` | match | Apache-2.0 OR BSD-2-Clause | 0 |
| PyYAML | 6.0.3 | transitive | `pyyaml-6.0.3-cp311-cp311-win_amd64.whl` | 0.2 MB | `9f3bfb4965eb874431221a3ff3fdcddc7e74e3b07799e0e84ca4a0f867d449bf` | match | MIT License | 0 |
| regex | 2026.9.29 | transitive | `regex-2026.9.29-cp311-cp311-win_amd64.whl` | 0.3 MB | `1043aedf5917caa861bcb25a9c11460049656bdf0017a90a309fa8f255467725` | match | Apache-2.0 AND CNRI-Python | 0 |
| requests | 2.34.2 | transitive | `requests-2.34.2-py3-none-any.whl` | 0.1 MB | `2a0d60c172f83ac6ab31e4554906c0f3b3588d37b5cb939b1c061f4907e278e0` | match | Apache Software License | 0 |
| safetensors | 0.6.2 | requested | `safetensors-0.6.2-cp38-abi3-win_amd64.whl` | 0.3 MB | `c7b214870df923cbc1593c3faee16bec59ea462758699bd3fee399d00aac072c` | match | Apache Software License | 0 |
| sympy | 1.13.1 | transitive | `sympy-1.13.1-py3-none-any.whl` | 6.2 MB | `db36cdc64bf61b9b24578b6f7bab1ecdd2452cf008f34faa33776680c26d66f8` | match | BSD License | 0 |
| tokenizers | 0.22.1 | requested | `tokenizers-0.22.1-cp39-abi3-win_amd64.whl` | 2.7 MB | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` | match | Apache Software License | 0 |
| torch | 2.6.0 | requested | `torch-2.6.0-cp311-cp311-win_amd64.whl` | 204.2 MB | `46763dcb051180ce1ed23d1891d9b1598e07d051ce4c9d14307029809c4d64f7` | match | BSD License | 24 |
| tqdm | 4.70.1 | transitive | `tqdm-4.70.1-py3-none-any.whl` | 0.1 MB | `c293e525e6fef9c20e8728fd4612df02a0aa31bb5fe91ecd93e123b1b7bffa73` | match | MPL-2.0 AND MIT | 0 |
| transformers | 4.57.1 | requested | `transformers-4.57.1-py3-none-any.whl` | 12.0 MB | `b10d05da8fa67dc41644dbbf9bc45a44cb86ae33da6f9295f5fbf5b7890bd267` | match | Apache Software License | 12 |
| typing_extensions | 4.16.0 | transitive | `typing_extensions-4.16.0-py3-none-any.whl` | 0.0 MB | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` | match | PSF-2.0 | 0 |
| urllib3 | 2.8.0 | transitive | `urllib3-2.8.0-py3-none-any.whl` | 0.1 MB | `0cf3cae568d36aa9576b28dfb35f11328f1cb974ca7647d9475ebb86c75ac6e3` | match | MIT | 0 |

TOTAL wheel bytes 246.2 MB; digest mismatches: 0

**Owner decision needed to resume (new item A1; R1 to R5 are unchanged):** either (a) record an explicit risk acceptance for these published advisories at `torch==2.6.0` and `transformers==4.57.1` for an isolated, offline, safetensors-only test and for the later use, or (b) approve different exact versions (a new approval; none was substituted). The isolated install, import, CPU, smoke, `pip check` and TensorFlow coexistence tests then run unchanged from the hash-pinned list above.

## J. Security-remediation and version-selection phase 2026-10-26 — A1 REJECTED for the original pins; installation BLOCKED; replacement versions are CANDIDATES ONLY

Written for the project owner. Decision recorded in this phase: **A1 is REJECTED for `torch==2.6.0` and `transformers==4.57.1`.** Installation of those pins stays blocked, and nothing was installed. This phase read the source files and ran read-only queries against PyPI project metadata and the OSV database (package names and versions only). **No package was installed, no wheel was downloaded, no model weight, tokenizer, dataset or Hugging Face asset was touched, no model revision was queried, no runtime code or configuration changed, and the Transformer stays disabled.** R6 to R14 remain UNRESOLVED. Every replacement version below is a **candidate that needs explicit owner approval**; none is selected, adopted or recorded in any manifest. Evidence labels: VERIFIED (read from a source named here), MY READING (my interpretation of advisory text, not a decision and not a security review), NOT VERIFIED, UNRESOLVED.

### J.1 Facts verified

- **Project constraints (VERIFIED, `backend/pyproject.toml`):** `requires-python = ">=3.11,<3.12"`, `numpy==1.26.4`, `tensorflow==2.17.0`; no `torch`, `transformers`, `tokenizers` or `safetensors` is declared. TensorFlow 2.17.0 requires `numpy>=1.23.5,<2.0.0` on Python 3.11, `typing-extensions>=3.6.6`, `requests<3,>=2.21`, `setuptools` (any), `packaging` (any), `protobuf<5` (PyPI metadata). The project environment has Python 3.11.9, TensorFlow 2.17.0, Keras 3.15.1, numpy 1.26.4, setuptools 65.5.0, packaging 25.0, and none of the four ML packages.
- **How the code uses the libraries (VERIFIED by reading):**
  - Runtime (`backend/wealthpilot/core/sentiment_model.py:258-259`): `AutoTokenizer.from_pretrained(dir, local_files_only=True, trust_remote_code=False)` and `AutoModelForSequenceClassification.from_pretrained(dir, local_files_only=True, trust_remote_code=False, use_safetensors=True)`, inside `torch.inference_mode()`, CPU only. Before that, `verify_artifact` checks the path is inside `models/sentiment/`, refuses symlinks, requires `model.safetensors`, and checks the SHA-256 of every file listed in `model_metadata.json`. That metadata file sits in the same directory, so the check detects corruption and partial tampering, not an attacker who can rewrite the whole directory. Files in the directory that the metadata does not list are not hashed.
  - Offline training (`training/sentiment/train_sentiment_transformer.py:122-123,155-156`): `AutoTokenizer.from_pretrained(hub_id)` and `AutoModelForSequenceClassification.from_pretrained(hub_id, ...)` with **no** `local_files_only`, no `use_safetensors=True` and no `revision`, a plain PyTorch loop, then `model.save_pretrained(..., safe_serialization=True)` and `tokenizer.save_pretrained(...)`. The name `Trainer` in that file is a local type alias, **not** `transformers.Trainer`. There is no `torch.compile`, `torch.jit`, `torch.load`, `pickle` or `weights_only` anywhere under `training/sentiment/` or the sentiment code (grep). The base models named in the project are `ProsusAI/finbert`, `FacebookAI/roberta-base` and `distilbert/distilroberta-base`, all loaded through `AutoModelForSequenceClassification`.
  - `training/sentiment/README.md` calls the transformers v4 line "the long-term-support branch". The advisory data below shows the v4 line has no release without published advisories.
- **Release scan (VERIFIED, PyPI JSON plus OSV `querybatch` per version, 2026-10-26):**
  - `torch`: 13 releases from 2.6.0 to 2.14.1, none yanked. OSV records per version: 2.6.0 24; 2.7.0 15; 2.7.1 10; 2.8.0 8; 2.9.0 5; 2.9.1 4; 2.10.0 2; 2.11.0, 2.12.0, 2.12.1 1 each; **2.13.0, 2.14.0, 2.14.1: 0**. Every release has a `cp311-win_amd64` wheel.
  - `transformers`: 44 releases from 4.57.1 to 5.20.2. **The 4.x line never reaches zero:** 4.57.1 has 12 records and 4.57.2 to 4.57.6 have 11 each (the remote-code-execution record CVE-2026-4372 is fixed only in 5.3.0, `save_pretrained` traversal only in 5.10.0). 5.0.0 to 5.2.0: 8; 5.3.0, 5.4.0: 5; 5.5.0 to 5.8.1: 4; 5.9.0: 2; **5.10.0: 0 but YANKED** (reason on PyPI: "pushed from a week old main branch ... uncertain its gonna be working properly and mostly it is missing a bunch of fixes"); **5.10.1 to 5.20.2: 0**, not yanked. Every release is a pure-Python `py3-none-any` wheel requiring Python 3.10 or newer.
  - Consequence: **any compliant `transformers` candidate is a major-version move from 4.x to 5.x**, which R2 did not approve (R2 named 4.57.1).
- **Second source (VERIFIED):** the PyPI `vulnerabilities` field was read for all 45 package versions in the candidate sets. It agrees with OSV: no entry for any candidate package; the only entry is for `certifi 2026.7.22` already installed in the project environment (see J.6).
- **The pins' 36 OSV records are 29 distinct CVEs** (torch 22 CVEs in 24 records; transformers 7 CVEs in 12 records). Register in J.3. Correction (2026-10-26, fourth brief): reading OSV's affected ranges directly gives `torch==2.6.0` 24 CVEs in 32 records (OSV's per-version query returned 24 records / 22 CVEs because nine records use non-standard version strings such as `2.6.0-NA`), plus one official-only advisory (GHSA-2rj9-7h5r-q4h8, libuv in tensorpipe, affected <=2.8.0, no CVE id), so the original pins carry at least 31 CVEs (24 + 7); the rejection of A1 and the candidate sets are unaffected (section K.1).

### J.2 Mandatory security questions

| # | Question | Answer | Label |
| --- | --- | --- | --- |
| 1 | Does `trust_remote_code=False` mitigate CVE-2026-4372? | **No, not as described.** The OSV text says the crafted `config.json` field `_attn_implementation_internal` makes the library "download and execute arbitrary Python code from the attacker's repository ... the vulnerability **bypasses the `trust_remote_code` security mechanism**". The comment in `sentiment_model.py` that remote code is excluded therefore cannot be relied on for `transformers<5.3.0`. | VERIFIED (advisory text); MY READING of its consequence |
| 2 | Does `local_files_only=True` mitigate it? | **Not established.** The advisory says the code comes from a Hub repository, and `local_files_only=True` forbids Hub downloads in the model-loading path, but the text does not say the kernel loader honours it, and I did not read the fix commit. The related record CVE-2026-5241 shows a nested path overriding `trust_remote_code` from untrusted `config.json`, so a single flag cannot be assumed to cover every nested loader. Context that lowers exposure but does not prove safety: the execution path is described in terms of "downloaded kernels"; transformers lists `kernels` only as an optional extra (`kernels<0.13,>=0.12.0` in 5.10.1) and no resolved candidate set contains it; the project loads only a hash-listed local directory. | NOT VERIFIED; UNRESOLVED |
| 3 | Does safetensors-only loading prevent the unsafe-loading advisories? | **It addresses the pickle ones, on the runtime path only.** `use_safetensors=True` (library behaviour, not exercised here) and the artifact check keep `torch.load` off the model weights: this covers CVE-2026-24747 (`weights_only` unpickler), CVE-2026-4538 (`.pt2` loader) and the checkpoint-parsing records (CVE-2025-14929, CVE-2025-14930) for inference. It does **not** cover CVE-2026-4372 (config-driven), CVE-2026-5241 (nested config), CVE-2026-9856 (file writes) or CVE-2026-80047. **The training path is not covered at all:** it passes neither `use_safetensors=True` nor a pinned `revision`, so a base repository without safetensors weights would fall back to a pickle checkpoint. | MY READING; training-path gap VERIFIED by reading the code |
| 4 | Does the project's training path use `Trainer`, `torch.compile`, pickle loading or affected model-specific loaders? | `Trainer`: no (plain loop). `torch.compile` / `torch.jit`: no. `torch.load` / `pickle` in the sentiment code: no (the library may call `torch.load` itself if a base repo has only `.bin` weights). X-CLIP, GLM4, LightGlue loaders, `load_custom_generate`: no, the candidate base models are BERT / RoBERTa classifiers. `save_pretrained`: **yes**, for the model and the tokenizer. | VERIFIED by grep and reading |
| 5 | Which advisories remain applicable to offline CPU inference? | For the original pins: **CVE-2026-4372 is the only one not shown to be mitigated**; the others are in code paths the repository does not call, or need a pickle / `.pt2` file that the loader refuses (register J.3). For the candidate sets: **none is listed by OSV or PyPI** for any resolved package. That is not proof of safety (J.6, U1). | MY READING; the zero counts are VERIFIED |
| 6 | Which apply only to training or optional APIs? | Training only: CVE-2026-9856 (`save_pretrained`) and the pickle fallback behind CVE-2026-24747 when a base model lacks safetensors; also CVE-2026-4372, because the training path downloads `config.json`. Optional APIs: `Trainer` (CVE-2026-1839), `torch.compile` / Inductor (seven torch CVEs), `torch.jit.script`, quantisation, generation (`load_custom_generate`), model-specific loaders (LightGlue, X-CLIP, GLM4). | MY READING |

### J.3 Advisory register for the approved pins (every record, with applicability)

The "OSV affected range" column is what OSV states for the package; "first release in this scan with no record" is the first of the scanned releases for which OSV lists none of the records for that CVE. Applicability columns are MY READING of the advisory text and of where the repository calls the libraries; none was tested at runtime.

| CVE | OSV ids | Package | OSV affected range | First release in this scan with no record | Offline CPU inference, safetensors-only (my reading) | Training or optional API only (my reading) | Basis |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CVE-2025-2953 | GHSA-3749-ghw9-m3mg, PYSEC-2025-191 | torch | fixed in 2.7.1-rc1 / last affected 2.6.0+cu124 | 2.7.1 | Not applicable: code path unused by this repository (conv pooling op) | - | Local DoS in `mkldnn_max_pool2d`; not a BERT-style operator. Unverified at runtime. |
| CVE-2025-3730 | GHSA-887c-mr87-cxwp, PYSEC-2026-1970 | torch | fixed in 2.8.0 | 2.8.0 | Not applicable: code path unused by this repository (CTC loss) | Training-time loss op, not used | Local DoS in `ctc_loss`. |
| CVE-2025-2148 | GHSA-c678-jfcj-6jmf | torch | last affected 2.6.0 | 2.7.0 | Not applicable: code path unused by this repository (profiler / JIT future callback) | - | Memory corruption through a profiler JIT callback. |
| CVE-2025-2998 | GHSA-f4hp-rmr7-r7v8 | torch | last affected 2.6.0 | 2.7.0 | Not applicable: code path unused by this repository (RNN utility) | - | `pad_packed_sequence` is an RNN helper. |
| CVE-2025-3001 | GHSA-qfhq-4f3w-5fph | torch | fixed in 2.10.0 | 2.10.0 | Not applicable: code path unused by this repository (LSTM cell) | - | `lstm_cell` is an RNN operator. |
| CVE-2025-3000 | GHSA-rrmf-rvhw-rf47 | torch | fixed in 2.13.0 | 2.13.0 | Not applicable: code path unused by this repository (`torch.jit.script`) | Optional API | No `jit.script` call in the repository; eager inference. |
| CVE-2025-2999 | GHSA-vgrw-7cvw-pwgx | torch | fixed in 2.9.1 | 2.9.1 | Not applicable: code path unused by this repository (RNN utility) | - | `unpack_sequence` is an RNN helper. |
| CVE-2025-2149 | GHSA-x3gm-94wq-g975 | torch | last affected 2.6.0 | 2.7.0 | Not applicable: code path unused by this repository (quantised module) | Optional API | Quantised sigmoid; no quantisation used. |
| CVE-2025-46148 | PYSEC-2025-198 | torch | fixed in 2.7.0 | 2.7.0 | Correctness only; operator not used | - | Wrong result in `nn.PairwiseDistance(p=2)` (eager). |
| CVE-2025-46149 | PYSEC-2025-199 | torch | from 2.6.0; fixed in 2.7.0 | 2.7.0 | Not applicable: code path unused by this repository (Inductor / compile) | Optional API | Needs `torch.compile`. |
| CVE-2025-46150 | PYSEC-2025-200 | torch | from 2.6.0; fixed in 2.7.0 | 2.7.0 | Not applicable: code path unused by this repository (Inductor / compile) | Optional API | Needs `torch.compile`. |
| CVE-2025-46152 | PYSEC-2025-201 | torch | from 2.6.0; fixed in 2.7.0 | 2.7.0 | Correctness only; operator not used | - | `bitwise_right_shift` out-of-range input. |
| CVE-2025-46153 | PYSEC-2025-202 | torch | from 2.6.0; fixed in 2.7.0 | 2.7.0 | Not applicable: code path unused by this repository (Inductor decomposition) | Optional API | Needs `torch.compile` with `fallback_random`. |
| CVE-2025-55551 | PYSEC-2025-203 | torch | fixed in 2.9.0 | 2.9.0 | Not applicable: code path unused by this repository (`torch.linalg.lu`) | - | Local DoS in one linear-algebra op; description names v2.8.0. |
| CVE-2025-55552 | PYSEC-2025-204 | torch | fixed in 2.9.0 | 2.9.0 | Not applicable: unusual operator combination | - | `rot90` with `randn_like`; description names v2.8.0. |
| CVE-2025-55553 | PYSEC-2025-205 | torch | fixed in 2.7.1 | 2.7.1 | Not applicable: code path unused by this repository (`proxy_tensor`, tracing) | Optional API | Description names v2.7.0. |
| CVE-2025-55554 | PYSEC-2025-206 | torch | fixed in 2.9.0 | 2.9.0 | Not applicable: operator not used | - | `nan_to_num` integer overflow; description names v2.8.0. |
| CVE-2025-55557 | PYSEC-2025-207 | torch | fixed in 2.7.1 | 2.7.1 | Not applicable: code path unused by this repository (Inductor / compile) | Optional API | Needs `torch.compile`; description names v2.7.0. |
| CVE-2025-55558 | PYSEC-2025-208 | torch | fixed in 2.7.1 | 2.7.1 | Not applicable: code path unused by this repository (Inductor / compile) | Optional API | Needs `torch.compile`; description names v2.7.0. |
| CVE-2025-55560 | PYSEC-2025-209 | torch | fixed in 2.7.1 | 2.7.1 | Not applicable: code path unused by this repository (Inductor / compile) | Optional API | Needs `torch.compile`; description names v2.7.0. |
| CVE-2026-4538 | PYSEC-2026-139 | torch | last affected 2.10.0 | 2.11.0 | Only if a `.pt2` archive is loaded; the loader refuses non-safetensors weights | Optional API | `pt2` loading handler; the text names 2.10.0 and reports no maintainer reaction. |
| CVE-2026-24747 | PYSEC-2026-2286 | torch | fixed in 2.10.0 | 2.10.0 | Only if a pickle `.pth` is loaded via `torch.load`; the runtime loader forces `use_safetensors=True` and the artifact check refuses anything else | **Training path:** `from_pretrained(hub_id)` there does not force safetensors; a base repo with only `.bin` weights would go through `torch.load` | `weights_only` unpickler memory corruption; needs a malicious checkpoint file. |
| CVE-2026-4372 | GHSA-29pf-2h5f-8g72, PYSEC-2026-2289 | transformers | fixed in 5.3.0 | 5.3.0 | **NOT SHOWN TO BE MITIGATED** (see the security questions) | Also the training path (config.json of the downloaded base model) | Crafted `config.json` field `_attn_implementation_internal` -> code from an attacker's Hub repo; the advisory says it **bypasses `trust_remote_code`**. |
| CVE-2026-1839 | GHSA-69w3-r845-3855, PYSEC-2026-2288 | transformers | fixed in 5.0.0rc3 / fixed in 5.0.0 | 5.0.0 | Not applicable: code path unused by this repository (`Trainer` class) | `Trainer` only; the repository uses a plain loop | `Trainer._load_rng_state` uses `torch.load` without `weights_only`; the text limits it to torch below 2.6. |
| CVE-2026-5241 | GHSA-fgcw-684q-jj6r, PYSEC-2026-2290 | transformers | fixed in 5.5.0 / last affected 5.2.0 | 5.5.0 | Not applicable: code path unused by this repository (LightGlue model path) | Model-specific loader | Nested `trust_remote_code` taken from `config.json` in the LightGlue path; candidate base models are BERT / RoBERTa classes. OSV records disagree on the fixed version (5.5.0 vs last affected 5.2.0). |
| CVE-2026-80047 | GHSA-x9r9-c232-4q39, PYSEC-2026-4174 | transformers | from 4.49.0; last affected 5.8.1 | 5.9.0 | Not applicable: code path unused by this repository (`load_custom_generate`) | Optional generation API | Remote file written before the trust check; no text generation in this project. |
| CVE-2026-9856 | GHSA-xrqw-3rrv-vx5w, PYSEC-2026-3929 | transformers | fixed in 5.10.0 | 5.10.0 (yanked) / 5.10.1 | Not applicable to inference (`save_pretrained` is never called at runtime) | **Training path:** `tokenizer.save_pretrained` / `model.save_pretrained`; needs a malicious upstream `tokenizer_config.json` | Chat-template dictionary keys become file names. 5.10.0 is the first fixed release but was yanked; 5.10.1 is the first non-yanked one. |
| CVE-2025-14929 | PYSEC-2025-217 | transformers | last affected 5.0.0-rc0 | 5.0.0 | Not applicable: code path unused by this repository (X-CLIP checkpoint conversion) | Conversion script | Deserialization in a model-conversion path. |
| CVE-2025-14930 | PYSEC-2025-218 | transformers | last affected 4.57.1 | 4.57.2 | Not applicable: code path unused by this repository (GLM4 weights parsing) | Model-specific loader | OSV lists 4.57.1 as the last affected version. |

### J.4 Candidate replacement sets (CANDIDATES ONLY; none selected, none approved)

Selection criteria applied: no OSV or PyPI advisory for any package in the set; not yanked; Python 3.11 and Windows `cp311` / `abi3` / pure-Python wheel; `tokenizers` and `safetensors` inside transformers' declared ranges; no CUDA dependency declared for Windows; no conflict with `numpy==1.26.4` or the TensorFlow 2.17.0 requirements. "Newer" was not treated as "safe".

| Set | `torch` | `transformers` | `tokenizers` | `safetensors` | Approvals it would change | Records for all resolved packages |
| --- | --- | --- | --- | --- | --- | --- |
| **S1** (smallest change; reviewer's first look, not a selection) | 2.13.0 (uploaded 2026-07-08) | 5.12.1 (2026-06-15) | 0.22.1 (unchanged, R3) | 0.6.2 (unchanged, R4) | R1, R2 | 0 |
| S2 | 2.13.0 | 5.10.1 (2026-06-03) | 0.22.1 | 0.6.2 | R1, R2 | 0 |
| S3 | 2.14.1 (2026-09-30) | 5.12.1 | 0.22.1 | 0.6.2 | R1, R2 | 0 |
| S4 (latest) | 2.14.1 | 5.20.2 (2026-10-19) | 0.23.3 | 0.8.0 | R1, R2, R3, R4 | 0 |

Also zero-record in the same ranges and not tabulated: `torch` 2.14.0; `transformers` 5.10.2, 5.10.4, 5.11.0, 5.12.0. `transformers` 5.13.0 to 5.15.1 need `safetensors>=0.8.0` (R4 would change); 5.16.0 and later need `tokenizers>=0.23.1` (R3 would change). 5.10.1 to 5.12.1 declare `tokenizers>=0.22.0,<=0.23.0` and `safetensors>=0.4.3`, which the approved `tokenizers==0.22.1` and `safetensors==0.6.2` satisfy (PyPI metadata).

**Compatibility evidence (VERIFIED from PyPI metadata; no install, so no runtime evidence):**

- Python 3.11 / Windows: `torch-2.13.0-cp311-cp311-win_amd64.whl` (122.0 MB), `torch-2.14.1-cp311-cp311-win_amd64.whl` (124.1 MB), `tokenizers-0.22.1-cp39-abi3-win_amd64.whl`, `safetensors-0.6.2-cp38-abi3-win_amd64.whl`, pure-Python `transformers`. All are served by the configured index (PyPI), none is yanked, and `requires_python` is `>=3.9` or `>=3.10` for every package in the set, so Python 3.11 is accepted.
- CPU only / no CUDA: the Windows `torch` metadata declares **no** `nvidia-*`, `cuda-*` or `triton` dependency (those carry `platform_system == "Linux"` markers) and the wheel is CPU-sized. **That `torch.version.cuda` is `None` and `torch.cuda.is_available()` is false is NOT VERIFIED until an install is allowed.** The wheel is 122 MB against 204 MB for 2.6.0, a difference I cannot explain from metadata alone.
- `numpy==1.26.4` and TensorFlow 2.17.0: `transformers` requires `numpy>=1.17` and `torch` declares no `numpy` requirement. Metadata-only reverse check of the 133 installed distributions (my own resolver, **not pip**, preferring installed versions that satisfy): **no unsatisfied requirement** for S1 to S4. Runtime coexistence of TensorFlow and PyTorch in one Windows environment is NOT VERIFIED.
- Dependency impact on the project environment: new packages (15): `torch`, `transformers`, `tokenizers`, `safetensors`, `huggingface-hub` (1.x), `hf-xet`, `typer`, `shellingham`, `annotated-doc`, `sympy`, `networkx`, `jinja2`, `mpmath`, `filelock`, `fsspec`. **One existing package must change: `setuptools` 65.5.0 must become `>=77.0.3` (torch 2.13+ requirement).** Nothing installed requires an older `setuptools`. `transformers` 5.x no longer needs `requests`; `huggingface-hub` 1.x uses `httpx` (installed 0.27.2 satisfies it) and `transformers` 5.x adds `typer`.
- Licences (PyPI metadata): `torch` 2.13.0 declares `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT` (the 2.6.0 metadata said BSD-3-Clause; the owner should read the new expression); `transformers` Apache-2.0; `tokenizers`, `safetensors`, `huggingface-hub`, `hf-xet` Apache; the remaining transitive packages are MIT, BSD, ISC, PSF-2.0, or `tqdm` MPL-2.0 AND MIT and `certifi` MPL-2.0 (file-level copyleft). Licence text was not read from the wheels.
- Download size: all 36 wheels of S1 total 170.1 MB if everything were fetched (S2 169.9, S3 172.2, S4 174.0 MB); 15 packages are new.

> **SUPERSEDED (2026-10-29): the early candidate table below is historical.** It lists `setuptools` 84.2.1 and `certifi` 2026.7.22 (the affected release). The executed 35-wheel list of section L.3 is authoritative: `setuptools==81.0.0` (the owner accepted `setuptools==81.0.0` on 2026-10-27 for the disposable Windows pip-only environment, see section M), `certifi` 2026.10.23, installed twice with byte-identical pins. The table was left unedited and no version was substituted anywhere.

**Hash table for S1** (PyPI JSON digests of the wheels; the versions of already-installed packages are the project's current ones because the resolver keeps them when they satisfy the requirements):

| Package | Version | Role | Wheel | Size | SHA-256 (PyPI JSON digest) | Licence (PyPI metadata) | OSV records | In project env now |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| annotated-doc | 0.0.5 | transitive | `annotated_doc-0.0.5-py3-none-any.whl` | 0.0 MB | `117bac03a25ede5df5440e855b32d556049ca169ead221505badf432fed4b101` | MIT | 0 | not installed |
| anyio | 4.15.1 | transitive | `anyio-4.15.1-py3-none-any.whl` | 0.1 MB | `6152fdbbf9a77fdec97731721bebf7c4c44f7c29b424b0065826173efc7ed101` | MIT | 0 | 4.15.1 |
| certifi | 2026.7.22 | transitive | `certifi-2026.7.22-py3-none-any.whl` | 0.1 MB | `62f22742b58a1a33014a2b6b706588a8d7e2a88ae7bd1a6ebe8c992928483775` | Mozilla Public License 2.0 (MPL 2.0) | 2 (GHSA-6q48-6c7w-9gw2, PYSEC-2026-4320) | 2026.7.22 |
| click | 8.5.0 | transitive | `click-8.5.0-py3-none-any.whl` | 0.1 MB | `255bc9599cf7748b4b1a446ccc735421bd08a2ae529a8b88597d3de5664ee360` | BSD-3-Clause | 0 | 8.5.0 |
| colorama | 0.4.6 | transitive | `colorama-0.4.6-py2.py3-none-any.whl` | 0.0 MB | `4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6` | BSD License | 0 | 0.4.6 |
| filelock | 4.2.4 | transitive | `filelock-4.2.4-py3-none-any.whl` | 0.2 MB | `301241438c57936ef93f4243a94f2559022268bfcf9b375a9a72eb0f8db8358e` | MIT | 0 | not installed |
| fsspec | 2026.9.0 | transitive | `fsspec-2026.9.0-py3-none-any.whl` | 0.2 MB | `8dd6e646e99ea382bd85f97a45e6b526a442d79423a7dc673f1e2756d05fcb5f` | BSD-3-Clause | 0 | not installed |
| h11 | 0.16.0 | transitive | `h11-0.16.0-py3-none-any.whl` | 0.0 MB | `63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86` | MIT License | 0 | 0.16.0 |
| hf-xet | 1.7.0 | transitive | `hf_xet-1.7.0-cp38-abi3-win_amd64.whl` | 3.8 MB | `2b7bb5727889b0f2436dbaaad8fc4c3e66b8240d992716989e0c086b4278b1bc` | Apache-2.0 | 0 | not installed |
| httpcore | 1.0.9 | transitive | `httpcore-1.0.9-py3-none-any.whl` | 0.1 MB | `2d400746a40668fc9dec9810239072b40b4484b640a8c38fd654a024c7a1bf55` | BSD-3-Clause | 0 | 1.0.9 |
| httpx | 0.27.2 | transitive | `httpx-0.27.2-py3-none-any.whl` | 0.1 MB | `7bb2708e112d8fdd7829cd4243970f0c223274051cb35ee80c03301ee29a3df0` | BSD License | 0 | 0.27.2 |
| huggingface-hub | 1.33.0 | transitive | `huggingface_hub-1.33.0-py3-none-any.whl` | 0.8 MB | `04e434b06e100eddbce9a6e817d72693a7884b10a79bd67ab48080d5c07eb899` | Apache Software License | 0 | not installed |
| idna | 3.19 | transitive | `idna-3.19-py3-none-any.whl` | 0.1 MB | `815e7be7a7806d54abb586dc943addc79e8b2ee16915059658cbeff4b1b43bf4` | BSD-3-Clause | 0 | 3.19 |
| jinja2 | 3.1.6 | transitive | `jinja2-3.1.6-py3-none-any.whl` | 0.1 MB | `85ece4451f492d0c13c5dd7c13a64681a86afae63a5f347908daf103ce6d2f67` | BSD License | 0 | not installed |
| markdown-it-py | 4.2.0 | transitive | `markdown_it_py-4.2.0-py3-none-any.whl` | 0.1 MB | `9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a` | MIT License | 0 | 4.2.0 |
| markupsafe | 3.0.3 | transitive | `markupsafe-3.0.3-cp311-cp311-win_amd64.whl` | 0.0 MB | `de8a88e63464af587c950061a5e6a67d3632e36df62b986892331d4620a35c01` | BSD-3-Clause | 0 | 3.0.3 |
| mdurl | 0.1.2 | transitive | `mdurl-0.1.2-py3-none-any.whl` | 0.0 MB | `84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8` | MIT License | 0 | 0.1.2 |
| mpmath | 1.3.0 | transitive | `mpmath-1.3.0-py3-none-any.whl` | 0.5 MB | `a0b2b9fe80bbcd81a6647ff13108738cfb482d481d826cc0e02f5b35e5c88d2c` | BSD License | 0 | not installed |
| networkx | 3.6.1 | transitive | `networkx-3.6.1-py3-none-any.whl` | 2.1 MB | `d47fbf302e7d9cbbb9e2555a0d267983d2aa476bac30e90dfbe5669bd57f3762` | BSD-3-Clause | 0 | not installed |
| numpy | 1.26.4 | requested | `numpy-1.26.4-cp311-cp311-win_amd64.whl` | 15.8 MB | `cd25bcecc4974d09257ffcd1f098ee778f7834c3ad767fe5db785be9a4aa9cb2` | BSD License | 0 | 1.26.4 |
| packaging | 25.0 | transitive | `packaging-25.0-py3-none-any.whl` | 0.1 MB | `29572ef2b1f17581046b3a2227d5c611fb25ec70ca1ba8554b24b0e69331a484` | Apache Software License; BSD License | 0 | 25.0 |
| pygments | 2.21.0 | transitive | `pygments-2.21.0-py3-none-any.whl` | 1.3 MB | `2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9` | BSD-2-Clause | 0 | 2.21.0 |
| pyyaml | 6.0.2 | transitive | `PyYAML-6.0.2-cp311-cp311-win_amd64.whl` | 0.2 MB | `e10ce637b18caea04431ce14fabcf5c64a1c61ec9c56b071a4b7ca131ca52d44` | MIT License | 0 | 6.0.2 |
| regex | 2026.9.10 | transitive | `regex-2026.9.10-cp311-cp311-win_amd64.whl` | 0.3 MB | `ce7c118cb102975f974585688357a717ffbf9dddd64ab0bb1bc93eb5b367cf95` | Apache-2.0 AND CNRI-Python | 0 | 2026.9.10 |
| rich | 15.0.0 | transitive | `rich-15.0.0-py3-none-any.whl` | 0.3 MB | `33bd4ef74232fb73fe9279a257718407f169c09b78a87ad3d296f548e27de0bb` | MIT License | 0 | 15.0.0 |
| safetensors | 0.6.2 | requested | `safetensors-0.6.2-cp38-abi3-win_amd64.whl` | 0.3 MB | `c7b214870df923cbc1593c3faee16bec59ea462758699bd3fee399d00aac072c` | Apache Software License | 0 | not installed |
| setuptools | 84.2.1 | transitive | `setuptools-84.2.1-py3-none-any.whl` | 0.9 MB | `ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2` | MIT | 0 | 65.5.0 |
| shellingham | 1.5.4 | transitive | `shellingham-1.5.4-py2.py3-none-any.whl` | 0.0 MB | `7ecfff8f2fd72616f7481040475a65b2bf8af90a56c89140852d1120324e8686` | ISC License (ISCL) | 0 | not installed |
| sniffio | 1.3.1 | transitive | `sniffio-1.3.1-py3-none-any.whl` | 0.0 MB | `2f6da418d1f1e0fddd844478f41680e794e6051915791a034ff65e5f100525a2` | Apache Software License; MIT License | 0 | 1.3.1 |
| sympy | 1.14.0 | transitive | `sympy-1.14.0-py3-none-any.whl` | 6.3 MB | `e091cc3e99d2141a0ba2847328f5479b05d94a6635cb96148ccb3f34671bd8f5` | BSD License | 0 | not installed |
| tokenizers | 0.22.1 | requested | `tokenizers-0.22.1-cp39-abi3-win_amd64.whl` | 2.7 MB | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` | Apache Software License | 0 | not installed |
| torch | 2.13.0 | requested | `torch-2.13.0-cp311-cp311-win_amd64.whl` | 122.0 MB | `a0d8b11f16a48d60e2015d8213aa0390744cbebb98e58b62b3514dddc656e330` | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT | 0 | not installed |
| tqdm | 4.70.1 | transitive | `tqdm-4.70.1-py3-none-any.whl` | 0.1 MB | `c293e525e6fef9c20e8728fd4612df02a0aa31bb5fe91ecd93e123b1b7bffa73` | MPL-2.0 AND MIT | 0 | 4.70.1 |
| transformers | 5.12.1 | requested | `transformers-5.12.1-py3-none-any.whl` | 11.2 MB | `2a5e109d2021265df7098ffbb738295acaf5ad256f12cbc586db2ea4dcbb1a8a` | Apache 2.0 License | 0 | not installed |
| typer | 0.27.3 | transitive | `typer-0.27.3-py3-none-any.whl` | 0.1 MB | `e50022f28b82a86313e54501317a1db64bf8f8d036ff8cfe5ca7e47675454aff` | MIT | 0 | not installed |
| typing-extensions | 4.16.0 | transitive | `typing_extensions-4.16.0-py3-none-any.whl` | 0.0 MB | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` | PSF-2.0 | 0 | 4.16.0 |

**Key packages in every set:**

| Set | Package | Version | Wheel | Size | SHA-256 (PyPI JSON digest) |
| --- | --- | --- | --- | --- | --- |
| S1 | huggingface-hub | 1.33.0 | `huggingface_hub-1.33.0-py3-none-any.whl` | 0.8 MB | `04e434b06e100eddbce9a6e817d72693a7884b10a79bd67ab48080d5c07eb899` |
| S1 | safetensors | 0.6.2 | `safetensors-0.6.2-cp38-abi3-win_amd64.whl` | 0.3 MB | `c7b214870df923cbc1593c3faee16bec59ea462758699bd3fee399d00aac072c` |
| S1 | setuptools | 84.2.1 | `setuptools-84.2.1-py3-none-any.whl` | 0.9 MB | `ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2` |
| S1 | tokenizers | 0.22.1 | `tokenizers-0.22.1-cp39-abi3-win_amd64.whl` | 2.7 MB | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` |
| S1 | torch | 2.13.0 | `torch-2.13.0-cp311-cp311-win_amd64.whl` | 122.0 MB | `a0d8b11f16a48d60e2015d8213aa0390744cbebb98e58b62b3514dddc656e330` |
| S1 | transformers | 5.12.1 | `transformers-5.12.1-py3-none-any.whl` | 11.2 MB | `2a5e109d2021265df7098ffbb738295acaf5ad256f12cbc586db2ea4dcbb1a8a` |
| S2 | huggingface-hub | 1.33.0 | `huggingface_hub-1.33.0-py3-none-any.whl` | 0.8 MB | `04e434b06e100eddbce9a6e817d72693a7884b10a79bd67ab48080d5c07eb899` |
| S2 | safetensors | 0.6.2 | `safetensors-0.6.2-cp38-abi3-win_amd64.whl` | 0.3 MB | `c7b214870df923cbc1593c3faee16bec59ea462758699bd3fee399d00aac072c` |
| S2 | tokenizers | 0.22.1 | `tokenizers-0.22.1-cp39-abi3-win_amd64.whl` | 2.7 MB | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` |
| S2 | torch | 2.13.0 | `torch-2.13.0-cp311-cp311-win_amd64.whl` | 122.0 MB | `a0d8b11f16a48d60e2015d8213aa0390744cbebb98e58b62b3514dddc656e330` |
| S2 | transformers | 5.10.1 | `transformers-5.10.1-py3-none-any.whl` | 11.0 MB | `ccb919ea1b77338b44d0d45d23f7472081906b1bb6ed8e5f5cf4d692d1da03d4` |
| S3 | huggingface-hub | 1.33.0 | `huggingface_hub-1.33.0-py3-none-any.whl` | 0.8 MB | `04e434b06e100eddbce9a6e817d72693a7884b10a79bd67ab48080d5c07eb899` |
| S3 | safetensors | 0.6.2 | `safetensors-0.6.2-cp38-abi3-win_amd64.whl` | 0.3 MB | `c7b214870df923cbc1593c3faee16bec59ea462758699bd3fee399d00aac072c` |
| S3 | tokenizers | 0.22.1 | `tokenizers-0.22.1-cp39-abi3-win_amd64.whl` | 2.7 MB | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` |
| S3 | torch | 2.14.1 | `torch-2.14.1-cp311-cp311-win_amd64.whl` | 124.1 MB | `0bd2fb0c4098856bc5af59fe5988bf38bdbcdb6550b44273c12ae425cb8ec17e` |
| S3 | transformers | 5.12.1 | `transformers-5.12.1-py3-none-any.whl` | 11.2 MB | `2a5e109d2021265df7098ffbb738295acaf5ad256f12cbc586db2ea4dcbb1a8a` |
| S4 | huggingface-hub | 2.3.0 | `huggingface_hub-2.3.0-py3-none-any.whl` | 0.9 MB | `5da369600233568a126eb5578754935b2add9446b42d9e2fc0927d56840ac1a5` |
| S4 | safetensors | 0.8.0 | `safetensors-0.8.0-cp310-abi3-win_amd64.whl` | 0.4 MB | `096ec1a98435df7beb08853bb5aa9081a84f23d0adc67ed1a0a10550f608373f` |
| S4 | tokenizers | 0.23.3 | `tokenizers-0.23.3-cp310-abi3-win_amd64.whl` | 2.9 MB | `1f0823bb00c5fdc98e487354d54dd55a03848d61a1a0bf29a68c77f24f3b26c3` |
| S4 | torch | 2.14.1 | `torch-2.14.1-cp311-cp311-win_amd64.whl` | 124.1 MB | `0bd2fb0c4098856bc5af59fe5988bf38bdbcdb6550b44273c12ae425cb8ec17e` |
| S4 | transformers | 5.20.2 | `transformers-5.20.2-py3-none-any.whl` | 12.8 MB | `7ae75dbc1fb3922aff1b6c97b9e5479d6cf26fd86a8866bfb71324190479f807` |

### J.5 Open items in the source tree that this phase did not touch (runtime changes need approval)

These came from reading the code; none was changed. For the owner's list: (1) the training loader has no `use_safetensors=True`, no `local_files_only=True` after the first download and no pinned `revision`; (2) the exact model revision is still not enforced in the metadata or the training script (previously known); (3) `training/sentiment/README.md` still calls the v4 line the long-term-support branch; (4) the comment in `sentiment_model.py` that remote code is excluded rests on `trust_remote_code=False`, which question 1 above shows is not sufficient for `transformers<5.3.0`; (5) `verify_artifact` hashes only the files its own metadata lists.

### J.6 Unresolved questions and limits

| Id | Unresolved | Why it matters |
| --- | --- | --- |
| U1 | OSV and PyPI showing no record is not proof of safety. The 5.x releases are young (5.12.1 about four months, 5.20.2 one week; `torch` 2.13.0 about three and a half months, 2.14.1 about four weeks), CVE-2026-4372 was published about five months ago, and no independent review of the fixes was done (I read advisory text only, not the fix commits). | The owner has not stated a minimum age ("soak") or a review rule for a new release |
| U2 | Whether `local_files_only=True` or a missing `kernels` package blocks CVE-2026-4372 on the **original** pins (question 2). | Decides whether a hardened v4.57.x could ever be argued; at present no v4 release is clean, so it only matters as evidence |
| U3 | The OSV records for CVE-2026-5241 disagree (fixed 5.5.0 versus last affected 5.2.0), and several PYSEC torch records name other versions than the range OSV matches. | The "first clean release" for those CVEs follows OSV's per-version matching, the conservative reading |
| U4 | Whether the project's two call sites work on transformers 5.x (`from_pretrained` keywords, `AutoTokenizer` backend changes, `get_linear_schedule_with_warmup`, `set_seed`, `save_pretrained(safe_serialization=True)`), and whether 5.x still raises when `use_safetensors=True` finds only a `.bin` file. | A major-version move with no runtime test; needs the isolated smoke test with a tiny local stand-in model |
| U5 | CPU-only behaviour, `numpy 1.26.4` with torch, and TensorFlow 2.17 + PyTorch in one Windows environment (DLL / OpenMP interaction) at runtime. | Only an isolated install can show it |
| U6 | `setuptools` 65.5.0 to at least 77.0.3 in the project environment; effect on `hatchling` editable installs and other tooling not tested. | The only existing package the candidates force to change |
| U7 | **Unrelated, pre-existing:** the project environment's `certifi 2026.7.22` has two advisories (GHSA-6q48-6c7w-9gw2 / PYSEC-2026-4320, compromised eMudhra intermediate CA keys; fixed in 2026.10.18 / 2026.10.19). Not caused by any candidate, not fixed here (out of scope). | Every future weight or dataset download over `requests` / `httpx` trusts that CA bundle; it should be resolved before any Hub download |
| U8 | The owner's decisions on: replacement versions (A2), the v4 to v5 move, a soak rule, and the new `torch` licence expression. | Required before any install |
| U9 | No package in the other 133 installed project distributions was advisory-checked in this phase (only the candidates' dependency closure). | Out of scope; stated so it is not read as a clean bill |

### J.7 Status

A1 REJECTED for the original pins. Installation, weight download, model-revision queries, dataset access, training and activation all remain blocked. The replacement versions in J.4 are candidates for the owner's review; choosing one is recorded as new item **A2 (UNRESOLVED)** in `reports/sentiment_model_approval_record.md`. If the owner approves a set, the next step is the isolated, hash-pinned install and the nine verification steps of the earlier brief, repeated for that exact set.

## K. Read-only security, licensing and compatibility review of candidate sets S1 to S4 — 2026-10-26 (fourth brief): A2 remains UNRESOLVED; installation remains BLOCKED

Written for the project owner. This review compares the four candidate sets from section J. **Nothing was installed, resolved with pip, downloaded or executed; no model weight, tokenizer file, dataset or Hugging Face asset was touched; no model revision was queried; no runtime code, training code, dependency manifest or configuration was changed.** States unchanged: **A1 REJECTED** for `torch==2.6.0` and `transformers==4.57.1`; **A2 UNRESOLVED**; **R6 to R14 UNRESOLVED**; `user_text_rules_v1` is the active method; `SENTIMENT_MODEL_ENABLED=false`; intensity regression deferred. The review recommends nothing for approval; section K.8 says what the evidence supports and what the owner must decide.

**Classification labels used on every conclusion:** VERIFIED FACT (read from a stated source in this repository or from PyPI / OSV metadata); VERIFIED FROM OFFICIAL SOURCE (read from an upstream project's own page: GitHub advisory, release notes, migration guide, project file, setuptools changelog); PRELIMINARY APPLICABILITY ASSESSMENT (my reading of how a fact applies here; not a decision, not a legal or security review); CANDIDATE PROPOSAL (a suggestion that needs the owner's approval); UNRESOLVED.

**Sources.** PyPI project JSON and the wheels' PEP 658 core-metadata text files (`.metadata`, a few KB each; the wheels themselves were not downloaded); OSV (`/v1/query` for every record ever filed for the four direct packages, `/v1/querybatch`, `/v1/vulns/<id>`); GitHub pages of the upstream projects: security-advisory pages and lists for `pytorch/pytorch` and `huggingface/transformers`, `pytorch/pytorch` `SECURITY.md`, release notes of PyTorch 2.13.0 and 2.14.1, transformers 5.12.1, tokenizers 0.23.3 and safetensors 0.8.0, `MIGRATION_GUIDE_V5.md`, PyTorch `pyproject.toml` and `requirements.txt` at v2.13.0, `LICENSE` files of tokenizers and safetensors, and **one fix commit that the CVE-2026-4372 advisory references** (a7f8e7f; read as part of that advisory); the setuptools changelog on `setuptools.pypa.io`. No `huggingface.co` page, model, tokenizer, dataset or wheel was requested. The earlier phases' metadata computation of each set's dependency closure was reused, not re-run; it is my own computation, not pip's, and no new resolution was performed.

### K.1 Correction to figures in section J (VERIFIED FACT)

Reading OSV's affected ranges directly gives **`torch==2.6.0`: 24 distinct CVEs in 32 records**, not 22 CVEs in 24 records. OSV's per-version query missed nine records whose version strings are non-standard (`2.6.0-NA`, `2.6.0-cu124`): PYSEC-2025-189, -190, -192 to -197 and -210. Of those, CVE-2025-3121 (`torch.jit.jit_module_from_flatbuffer`) and CVE-2025-3136 (`torch.cuda.memory.caching_allocator_delete`) are two CVEs section J did not count. `transformers==4.57.1` is unchanged (7 CVEs, 12 records). PyTorch's own advisory list also holds two advisories that OSV does not have at all (404 on lookup): GHSA-2rj9-7h5r-q4h8 (libuv in tensorpipe, affected `<=2.8.0`, patched 2.9.0, no CVE id) and GHSA-g6v3-crfc-cggj (flatbuffer parsing, affected `<2.1.0`). So the original pins carry **at least 31 CVEs (24 + 7) plus one official-only advisory**. This changes nothing about the rejection of A1, and it does not touch S1 to S4: the same range reading, run against the candidate versions with a tolerant parser, finds **no record, in any of the 99 OSV records filed for `torch` and `transformers`, that lists any candidate version** (cross-checked two ways: affected ranges and explicit version lists). `tokenizers` and `safetensors` have **no** OSV record at all.

An important limit (VERIFIED FROM OFFICIAL SOURCE and PRELIMINARY): the GitHub pages for GHSA-c678-jfcj-6jmf (CVE-2025-2148) and GHSA-f4hp-rmr7-r7v8 (CVE-2025-2998) say "Affected versions: <= 2.6.0, Patched versions: None". Six torch records (CVE-2025-2148, -2149, -2998, -3121, -3136, -63396) therefore carry **no fixed version**. "No record lists 2.13.0" means the reporters tested older versions, **not** that a fix was confirmed. All six are in code the repository does not call (see K.4).

### K.2 Candidate comparison

| Criterion | S1 | S2 | S3 | S4 | Label |
| --- | --- | --- | --- | --- | --- |
| Exact pins | torch 2.13.0, transformers 5.12.1, tokenizers 0.22.1, safetensors 0.6.2 | torch 2.13.0, transformers 5.10.1, tokenizers 0.22.1, safetensors 0.6.2 | torch 2.14.1, transformers 5.12.1, tokenizers 0.22.1, safetensors 0.6.2 | torch 2.14.1, transformers 5.20.2, tokenizers 0.23.3, safetensors 0.8.0 | — |
| 1. Release exists on the configured index; any yanked | all four exist; **none yanked** | same | same | same | VERIFIED FACT (`transformers` 5.10.0 is yanked and not used) |
| 2. Python 3.11 / Windows CPython 3.11 wheel | `torch-2.13.0-cp311-cp311-win_amd64.whl` (122.0 MB); `transformers-5.12.1-py3-none-any.whl` (11.2 MB); `tokenizers-0.22.1-cp39-abi3-win_amd64.whl`; `safetensors-0.6.2-cp38-abi3-win_amd64.whl` | `transformers-5.10.1-py3-none-any.whl` (11.0 MB), rest as S1 | `torch-2.14.1-cp311-cp311-win_amd64.whl` (124.1 MB), rest as S1 | `transformers-5.20.2-py3-none-any.whl` (12.8 MB); `tokenizers-0.23.3-cp310-abi3-win_amd64.whl`; `safetensors-0.8.0-cp310-abi3-win_amd64.whl`; torch as S3 | VERIFIED FACT. `requires_python`: torch and transformers `>=3.10`, tokenizers and safetensors `>=3.9` (S4: `>=3.10`); Python 3.11 accepted |
| 3. CUDA / NVIDIA dependency declared for the Windows wheel | **none**: every `cuda-*`, `nvidia-*` and `triton` requirement (7 declared) carries a Linux marker; I evaluated all `Requires-Dist` lines of the wheel metadata for Windows / Python 3.11: active requirements are `filelock, typing-extensions>=4.10.0, setuptools>=77.0.3, sympy>=1.13.3, networkx>=2.5.1, jinja2, fsspec>=0.8.5` | same | same | same | VERIFIED FACT. That the installed build reports `torch.version.cuda is None` is UNRESOLVED until an install is allowed |
| 4. numpy 1.26.4 and TensorFlow 2.17.0 at metadata level | `transformers` needs `numpy>=1.17`; `torch`, `tokenizers`, `safetensors` declare no numpy requirement; TensorFlow 2.17.0 needs `numpy>=1.23.5,<2.0.0`, `typing-extensions>=3.6.6`, `setuptools` (any), `keras>=3.2.0` (installed 3.15.1); `tokenizers 0.22.1` needs `huggingface-hub<2.0,>=0.16.4`, `transformers 5.12.1` needs `>=1.5.0,<2.0` | same | same | `transformers 5.20.2` needs `huggingface-hub>=1.31.0,<3.0`, `safetensors>=0.8.0`, `tokenizers>=0.23.1,<0.24` | VERIFIED FACT: no unsatisfied requirement against the 133 installed distributions (my own check, not pip). **UNRESOLVED:** the PyTorch 2.13.0 notes and `requirements.txt` say nothing about NumPy 1.x support, so torch with numpy 1.26.4 at runtime, and TensorFlow + PyTorch in one Windows process, are unverified |
| 5. Direct licences | see K.3 | see K.3 | see K.3 | see K.3 | VERIFIED FACT / OFFICIAL SOURCE |
| 6. OSV records listing the pinned versions | **0 for all four direct packages** | 0 | 0 | 0 | VERIFIED FACT |
| 6b. PyPI `vulnerabilities` field; GitHub advisory lists | 0; transformers repository lists **zero** published advisories; PyTorch lists five, none of which lists 2.13.0 or 2.14.x (GHSA-g6v3 `<2.1.0`, GHSA-2rj9 `<=2.8.0`, GHSA-63cw fixed 2.10.0, GHSA-53q9 fixed 2.6.0, GHSA-hw6r is a CI workflow) | same | same | same | VERIFIED FROM OFFICIAL SOURCE |
| 7. Approvals changed | R1, R2 | R1, R2 | R1, R2 | **R1 to R4** | VERIFIED FACT |
| 8. Upload dates (torch / transformers / tokenizers / safetensors) | 2026-07-08 / 2026-06-15 / 2025-09-19 / 2025-08-08 | 2026-07-08 / 2026-06-03 / same / same | 2026-09-30 / 2026-06-15 / same / same | 2026-09-30 / 2026-10-19 / 2026-10-09 / 2026-06-09 | VERIFIED FACT |
| 9. Age on 2026-10-26, days (same order); youngest direct | 110 / 133 / 402 / 444; **110** | 110 / 145 / 402 / 444; **110** | 26 / 133 / 402 / 444; **26** | 26 / 7 / 17 / 139; **7** | VERIFIED FACT |
| 10. Source changes needed for the two existing call sites | at least one in the training script (K.7) | same | same | same, plus tokenizer-truncation and safetensors-reader changes to review | PRELIMINARY APPLICABILITY ASSESSMENT |
| 11. What the newer `torch` buys | — (2.13.0 includes memory-safety fixes in the C++ TorchScript unpickler) | same | 2.14.1 fixes MPS and CUDA regressions only; **nothing for Windows CPU** | same as S3 | VERIFIED FROM OFFICIAL SOURCE (release notes) |
| 12. Dependency impact on the project environment | 15 new packages; `setuptools` must change (K.6) | same | same | same; `huggingface-hub` 2.x | PRELIMINARY (metadata computation) |

### K.3 Licence findings

| Package | Exact licence metadata | Label |
| --- | --- | --- |
| `torch` 2.13.0 and 2.14.1 | Wheel `METADATA`: `License-Expression: Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT`; **107** `License-File` entries (2.13.0) and **95** (2.14.1), `LICENSE` plus `third_party/**/LICENSE*` | VERIFIED FACT (PEP 658 metadata) |
| `torch` 2.6.0 (for comparison) | `License: BSD-3-Clause`; 2 license files (`LICENSE`, `NOTICE`); classifier BSD | VERIFIED FACT |
| `transformers` 5.10.1, 5.12.1, 5.20.2 | `License: Apache 2.0 License`, `License-File: LICENSE`; no SPDX expression and no licence classifier in the 5.x metadata (4.57.1 had the classifier "Apache Software License") | VERIFIED FACT |
| `tokenizers` 0.22.1, 0.23.3 | Metadata carries only the classifier "License :: OSI Approved :: Apache Software License" (no `License` field, no licence file); the upstream `LICENSE` is the **Apache License, Version 2.0** | VERIFIED FACT + VERIFIED FROM OFFICIAL SOURCE |
| `safetensors` 0.6.2, 0.8.0 | Classifier Apache Software License and `License-File: LICENSE`; the upstream `LICENSE` is the **Apache License, Version 2.0** | VERIFIED FACT + VERIFIED FROM OFFICIAL SOURCE |
| Transitive packages (my metadata closure of S1 to S4) | `huggingface-hub`, `hf-xet`: Apache-2.0; `typer`, `filelock`, `setuptools`, `annotated-doc`, `pyyaml`: MIT; `fsspec`, `networkx`, `markupsafe`: BSD-3-Clause; `sympy`, `mpmath`, `jinja2`, `numpy`, `colorama`: BSD; `shellingham`: ISC; `typing-extensions`: PSF-2.0; `regex`: Apache-2.0 AND CNRI-Python; `packaging`: Apache-2.0 OR BSD-2-Clause; **`tqdm`: MPL-2.0 AND MIT and `certifi`: MPL-2.0** (file-level copyleft; both already installed in the project). No GPL, LGPL or AGPL appears in the closure | VERIFIED FACT for each entry; the closure itself is my computation |

**The changed `torch` licence expression (VERIFIED FROM OFFICIAL SOURCE).** PyTorch's `pyproject.toml` at v2.13.0 states: "The main Pytorch project license is BSD-3-Clause. The SPDX license expression below reflects installed pytorch packages", sets `license` to that six-part expression, and lists `license-files` as `LICENSE`, `third_party/**/LICENSE`, `third_party/**/LICENSE.txt`, `third_party/**/LICENSE.rst`, `third_party/**/COPYING.BSD`. The 2.13.0 release notes say they "Drop the setuptools `concat_license_files` hook and adopt PEP 639 `license-files`". So the broader expression is a more complete declaration of the third-party components that PyTorch packages (Apache-2.0 including the LLVM exception, BSD-2 and BSD-3, BSL-1.0 which is the Boost licence, and MIT), produced by adopting PEP 639; it is not a change of PyTorch's own licence, which stays BSD-3-Clause.

**Does it create a project licensing concern? (PRELIMINARY APPLICABILITY ASSESSMENT; not legal advice.)** No concern that I can identify. All six licences are permissive, OSI-approved licences with no copyleft and no non-commercial term; the project is an academic prototype that installs `torch` from PyPI and does not redistribute it. Obligations (keep copyright and licence notices, Apache-2.0's notice and patent terms) arise on redistribution only: if the project ever ships a bundled environment, container, installer or archive containing `torch`, it should carry the wheel's licence files. Two limits: the expression covers everything the sdist can contain (the file list includes ROCm components such as `aiter` and `composable_kernel`), so **which of the 107 / 95 licence files and components are actually in the Windows CPU wheel is UNRESOLVED**; it can be read from the wheel's `.dist-info/licenses/` in the isolated install. And the library licences are not the licensing risk in this work: the **model** licences (FinBERT CC BY-NC-SA 4.0 as supplied, unverified; Financial PhraseBank CC BY-NC-SA 3.0) are non-commercial and share-alike and remain open items R6 to R8.

### K.4 Advisory findings and applicability

**Complete lists.** Section J.3 lists every record for the two original pins. The table at the end of this section lists **every OSV record ever filed for `torch` (31 CVE / id groups) and `transformers` (32 groups)** with publication date, last-modified date, OSV affected range and whether it lists any version in S1 to S4 (**none does**), plus the two official-only PyTorch advisories. `tokenizers` and `safetensors`: no record.

**Mandatory questions, updated with official evidence.**

| Question | Answer | Label |
| --- | --- | --- |
| Does `trust_remote_code=False` mitigate CVE-2026-4372? | **No, not as described.** The GitHub advisory (affected `< 5.3.0`, patched `5.3.0`, High, CVSS 7.8, published 2026-05-26, CWE-502 and CWE-1066) says the issue "bypasses the `trust_remote_code` security mechanism"; the only mitigation it gives is upgrading. | VERIFIED FROM OFFICIAL SOURCE |
| Does `local_files_only=True` mitigate it? | **Not established.** The advisory does not say. The referenced fix commit (a7f8e7f, "fix security vuln", 2 files, +22/-9) does not use `local_files_only` or `trust_remote_code` either: it stops `PretrainedConfig.__init__` from deserialising the private keys `_attn_implementation_internal` and `_experts_implementation_internal` taken from hub configs, and makes `is_kernel()` in `integrations/hub_kernels.py` accept only the `kernels-community` repository ("as otherwise loading random kernels will lead to arbitrary code execution"). So the vulnerable path is the hub-kernels integration; the optional `kernels` package is absent from every candidate closure, but whether its absence blocks the path is **UNRESOLVED**. The commit page does not name the CVE; OSV lists it as a reference. | VERIFIED FROM OFFICIAL SOURCE (diff); UNRESOLVED (effect of the flags) |
| Is CVE-2026-4372 relevant to S1 to S4? | Not applicable by version: the fix is in 5.3.0 and every candidate is 5.10.1 or newer. Fix completeness was not independently reviewed. | VERIFIED FACT (version); UNRESOLVED (completeness) |
| What does the loader do that the advisory text does not cover? | `verify_artifact` hashes only the files its own `model_metadata.json` lists, and that file sits in the same directory, so it detects corruption, not a writer of the whole directory; a `config.json` that is not listed is not hashed. | VERIFIED FACT (code) |

**Applicability by topic.** "Original pins" are the rejected `torch==2.6.0` and `transformers==4.57.1`; "S1 to S4" is every candidate.

| Topic | Original pins (A1 rejected) | S1 to S4 | Label |
| --- | --- | --- | --- |
| Offline CPU inference | CVE-2026-4372 is the only advisory not shown to be mitigated; the other advisories are in operators or APIs that a BERT-style classifier does not call (`mkldnn_max_pool2d`, `ctc_loss`, RNN helpers, quantised modules, profiler, `torch.jit`, Inductor) | no advisory lists these versions | PRELIMINARY (original pins); VERIFIED FACT (zero records) |
| Safetensors-only loading | prevents the pickle advisories on the **runtime** path (CVE-2026-24747 `weights_only` unpickler, GHSA-53q9 `torch.load`, CVE-2026-4538 `.pt2`, checkpoint parsers CVE-2025-14929 / -14930); PyTorch's own policy recommends safetensors as "the most restrictive" format | same | VERIFIED FROM OFFICIAL SOURCE (policy); PRELIMINARY (effect) |
| `trust_remote_code=False` | does not cover CVE-2026-4372 or the nested override CVE-2026-5241 | n/a | VERIFIED FROM OFFICIAL SOURCE |
| `local_files_only=True` | not established (above) | n/a | UNRESOLVED |
| Current model loader | `local_files_only`, `trust_remote_code=False`, `use_safetensors=True`, path confinement, per-file SHA-256: covers the pickle class; does not cover config-driven code loading on `transformers<5.3.0` | the same controls, with the config-field fix in the library | VERIFIED FACT (code) + PRELIMINARY |
| Current training script | passes no `local_files_only`, no `use_safetensors=True`, no `revision` to `from_pretrained(hub_id)` (so a base repo with only `.bin` weights would be read through `torch.load`) and downloads `config.json` from the hub: exposed to CVE-2026-4372, CVE-2026-24747 and CVE-2026-9856 on the original pins | exposure removed by the library fixes; the missing `use_safetensors=True` and revision pin stay a hardening gap | VERIFIED FACT (code) + PRELIMINARY |
| `save_pretrained` | CVE-2026-9856 (chat-template keys become file names; fixed in 5.10.0, yanked, first non-yanked release 5.10.1): applies to the training path only, and needs a malicious upstream `tokenizer_config.json` | not applicable (all candidates are 5.10.1 or newer) | VERIFIED FACT (range) + PRELIMINARY |
| `Trainer` | CVE-2026-1839: not used (the training script is a plain loop; `Trainer` in that file is a local type alias) | not applicable | VERIFIED FACT (code) |
| `torch.compile` | seven Inductor CVEs on the original pin; not used | not applicable | VERIFIED FACT (code) |
| `torch.load`, pickle, `.pt` / `.pth` | not called in the sentiment code; may be called by the library only for a base repo without safetensors (training) | the 2.13.0 notes list unpickler memory-safety fixes | VERIFIED FACT (code); VERIFIED FROM OFFICIAL SOURCE (notes) |
| `.pt2`, TorchScript, flatbuffer artifacts | CVE-2026-4538, CVE-2025-3121, GHSA-g6v3 (`<2.1.0`): need such a file; the loader accepts only `.safetensors` | not applicable | PRELIMINARY |

**PyTorch's own policy (VERIFIED FROM OFFICIAL SOURCE, `SECURITY.md`):** operator crashes and memory errors on bad input, local denial of service and resource-heavy inputs "are not security vulnerabilities" but ordinary bugs; "running untrusted models is equivalent to running untrusted code"; prefer Safetensors; and **"fixes apply only to the current release and are not backported."** The last point matters for any torch pin: a pinned older release will not receive later fixes, so the OSV and GitHub lists must be re-checked on every install and at a regular interval, whichever version is chosen. HuggingFace publishes **no** repository security advisories for `transformers` (the page says "There aren't any published security advisories"); its records reach OSV through the GitHub Advisory Database and NVD, so completeness relies on third-party reporting (UNRESOLVED).

**Complete OSV listing for `torch` and `transformers`** (every record ever filed; ranges are OSV's ECOSYSTEM ranges; nine torch records use non-standard version strings, see K.1):

| Package | CVE / id | OSV ids | Published | Affected range (OSV) | Last modified | Withdrawn | Summary | Affects S1 to S4 versions? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| torch | CVE-2022-45907 | GHSA-47fc-vmwq-366v, PYSEC-2022-43015 | 2022-11-26 | fixed in 1.13.1 | 2026-06-10 | no | PyTorch vulnerable to arbitrary code execution | no |
| torch | CVE-2024-31580 | GHSA-5pcm-hx3q-hm94, PYSEC-2024-252 | 2024-04-17 | fixed in 2.2.0 | 2026-07-27 | no | PyTorch heap buffer overflow vulnerability | no |
| torch | CVE-2024-31583 | GHSA-pg7h-5qx3-wjr3, PYSEC-2024-251 | 2024-04-17 | fixed in 2.2.0 | 2026-06-10 | no | Pytorch use-after-free vulnerability | no |
| torch | CVE-2024-31584 | PYSEC-2024-250 | 2024-04-19 | fixed in 2.2.0 | 2025-06-04 | no | Pytorch before v2.2.0 has an Out-of-bounds Read vulnerability via the component torch/csrc | no |
| torch | CVE-2024-48063 | PYSEC-2024-259 | 2024-10-29 | fixed in 2.5.0 | 2025-07-16 | no | In PyTorch <=2.4.1, the RemoteModule has Deserialization RCE. NOTE: this is disputed by mu | no |
| torch | CVE-2025-2148 | GHSA-c678-jfcj-6jmf, PYSEC-2025-189 | 2025-03-10 | last affected 2.6.0 / last affected 2.6.0-cu124 | 2026-06-10 | no | PyTorch Tuple Handler is Vulnerable to Memory Corruption through Manipulation of None Argument | no |
| torch | CVE-2025-2149 | GHSA-x3gm-94wq-g975, PYSEC-2025-190 | 2025-03-10 | last affected 2.6.0 / last affected 2.6.0-cu124 | 2026-06-10 | no | PyTorch: Manipulation of the argument scale/zero_point leads to improper initialization via Quantized Sigmoid  | no |
| torch | CVE-2025-2953 | GHSA-3749-ghw9-m3mg, PYSEC-2025-191 | 2025-03-30 | fixed in 2.7.1-rc1 / last affected 2.6.0+cu124 | 2026-09-10 | no | PyTorch susceptible to local Denial of Service | no |
| torch | CVE-2025-2998 | GHSA-f4hp-rmr7-r7v8, PYSEC-2025-192 | 2025-03-31 | last affected 2.6.0 / last affected 2.6.0-NA | 2026-06-10 | no | PyTorch is Vulnerable to Memory Consumption through pad_packed_sequence Function | no |
| torch | CVE-2025-2999 | GHSA-vgrw-7cvw-pwgx, PYSEC-2025-193 | 2025-03-31 | fixed in 2.9.1 / last affected 2.6.0-NA | 2026-07-13 | no | PyTorch is vulnerable to memory corruption through its unpack_sequence function | no |
| torch | CVE-2025-3000 | GHSA-rrmf-rvhw-rf47, PYSEC-2025-194 | 2025-03-31 | fixed in 2.13.0 / last affected 2.6.0-NA | 2026-09-10 | no | PyTorch is vulnerable to memory corruption through its torch.jit.script function | no |
| torch | CVE-2025-3001 | GHSA-qfhq-4f3w-5fph, PYSEC-2025-195 | 2025-03-31 | fixed in 2.10.0 / last affected 2.6.0-NA | 2026-07-13 | no | PyTorch is vulnerable to memory corruption through its torch.lstm_cell function | no |
| torch | CVE-2025-3121 | PYSEC-2025-196 | 2025-04-02 | last affected 2.6.0-NA | 2026-05-21 | no | A vulnerability classified as problematic has been found in PyTorch 2.6.0. Affected is the | no |
| torch | CVE-2025-3136 | PYSEC-2025-197 | 2025-04-03 | last affected 2.6.0-NA | 2026-05-21 | no | A vulnerability, which was classified as problematic, has been found in PyTorch 2.6.0. Thi | no |
| torch | CVE-2025-3730 | GHSA-887c-mr87-cxwp, PYSEC-2026-1970 | 2025-04-16 | fixed in 2.8.0 | 2026-09-10 | no | PyTorch Improper Resource Shutdown or Release vulnerability | no |
| torch | CVE-2025-32434 | GHSA-53q9-r3pm-6pq6, PYSEC-2025-41 | 2025-04-18 | fixed in 2.6.0 | 2026-08-07 | no | PyTorch: `torch.load` with `weights_only=True` leads to remote code execution | no |
| torch | CVE-2025-46148 | PYSEC-2025-198 | 2025-09-25 | fixed in 2.7.0 | 2026-05-20 | no | In PyTorch through 2.6.0, when eager is used, nn.PairwiseDistance(p=2) produces incorrect  | no |
| torch | CVE-2025-46149 | PYSEC-2025-199 | 2025-09-25 | from 2.6.0; fixed in 2.7.0 | 2026-05-20 | no | In PyTorch before 2.7.0, when inductor is used, nn.Fold has an assertion error. | no |
| torch | CVE-2025-46150 | PYSEC-2025-200 | 2025-09-25 | from 2.6.0; fixed in 2.7.0 | 2026-05-20 | no | In PyTorch before 2.7.0, when torch.compile is used, FractionalMaxPool2d has inconsistent  | no |
| torch | CVE-2025-46152 | PYSEC-2025-201 | 2025-09-25 | from 2.6.0; fixed in 2.7.0 | 2026-05-20 | no | In PyTorch before 2.7.0, bitwise_right_shift produces incorrect output for certain out-of- | no |
| torch | CVE-2025-46153 | PYSEC-2025-202 | 2025-09-25 | from 2.6.0; fixed in 2.7.0 | 2026-05-20 | no | PyTorch before 3.7.0 has a bernoulli_p decompose function in decompositions.py even though | no |
| torch | CVE-2025-55551 | PYSEC-2025-203 | 2025-09-25 | fixed in 2.9.0 | 2026-05-20 | no | An issue in the component torch.linalg.lu of pytorch v2.8.0 allows attackers to cause a De | no |
| torch | CVE-2025-55552 | PYSEC-2025-204 | 2025-09-25 | fixed in 2.9.0 | 2026-05-20 | no | pytorch v2.8.0 was discovered to display unexpected behavior when the components torch.rot | no |
| torch | CVE-2025-55553 | PYSEC-2025-205 | 2025-09-25 | fixed in 2.7.1 | 2026-05-20 | no | A syntax error in the component proxy_tensor.py of pytorch v2.7.0 allows attackers to caus | no |
| torch | CVE-2025-55554 | PYSEC-2025-206 | 2025-09-25 | fixed in 2.9.0 | 2026-05-20 | no | pytorch v2.8.0 was discovered to contain an integer overflow in the component torch.nan_to | no |
| torch | CVE-2025-55557 | PYSEC-2025-207 | 2025-09-25 | fixed in 2.7.1 | 2026-05-20 | no | A Name Error occurs in pytorch v2.7.0 when a PyTorch model consists of torch.cummin and is | no |
| torch | CVE-2025-55558 | PYSEC-2025-208 | 2025-09-25 | fixed in 2.7.1 | 2026-05-20 | no | A buffer overflow occurs in pytorch v2.7.0 when a PyTorch model consists of torch.nn.Conv2 | no |
| torch | CVE-2025-55560 | PYSEC-2025-209 | 2025-09-25 | fixed in 2.7.1 | 2026-05-20 | no | An issue in pytorch v2.7.0 can lead to a Denial of Service (DoS) when a PyTorch model cons | no |
| torch | CVE-2025-63396 | PYSEC-2025-210 | 2025-11-12 | last affected 2.7.1-NA | 2026-05-21 | no | An issue was discovered in PyTorch v2.5 and v2.7.1. Omission of profiler.stop() can cause  | no |
| torch | CVE-2026-24747 | PYSEC-2026-2286 | 2026-01-27 | fixed in 2.10.0 | 2026-07-13 | no | PyTorch is a Python package that provides tensor computation. Prior to version 2.10.0, a v | no |
| torch | CVE-2026-4538 | PYSEC-2026-139 | 2026-03-22 | last affected 2.10.0 | 2026-05-21 | no | A vulnerability was identified in PyTorch 2.10.0. The affected element is an unknown funct | no |
| transformers | CVE-2023-2800 | GHSA-282v-666c-3fvg, PYSEC-2023-299 | 2023-05-18 | fixed in 4.30.0 | 2026-06-10 | no | transformers has Insecure Temporary File | no |
| transformers | CVE-2023-6730 | GHSA-3863-2447-669p, PYSEC-2023-300 | 2023-12-19 | fixed in 4.36.0 | 2026-06-10 | no | transformers has a Deserialization of Untrusted Data vulnerability | no |
| transformers | CVE-2023-7018 | GHSA-v68g-wm8c-6x7j, PYSEC-2023-301 | 2023-12-20 | fixed in 4.36.0 | 2026-06-10 | no | transformers has a Deserialization of Untrusted Data vulnerability | no |
| transformers | CVE-2024-3568 | GHSA-37q5-v5qm-c9v8, PYSEC-2026-1978 | 2024-04-10 | fixed in 4.38.0 | 2026-07-07 | no | Transformers Deserialization of Untrusted Data vulnerability | no |
| transformers | CVE-2024-11392 | GHSA-qxrp-vhvm-j765, PYSEC-2024-227 | 2024-11-22 | fixed in 4.48.0 | 2026-09-10 | no | Deserialization of Untrusted Data in Hugging Face Transformers | no |
| transformers | CVE-2024-11393 | GHSA-wrfc-pvp9-mr9g, PYSEC-2024-228 | 2024-11-22 | fixed in 4.48.0 | 2026-09-10 | no | Deserialization of Untrusted Data in Hugging Face Transformers | no |
| transformers | CVE-2024-11394 | GHSA-hxxf-235m-72v3, PYSEC-2024-229 | 2024-11-22 | fixed in 4.48.0 | 2026-09-10 | no | Deserialization of Untrusted Data in Hugging Face Transformers | no |
| transformers | CVE-2024-12720 | GHSA-6rvg-6v2m-4j46, PYSEC-2026-1982 | 2025-03-20 | fixed in 4.48.0 | 2026-08-13 | no | Transformers Regular Expression Denial of Service (ReDoS) vulnerability | no |
| transformers | CVE-2025-1194 | GHSA-fpwr-67px-3qhx, PYSEC-2026-1984 | 2025-04-29 | fixed in 4.50.0 | 2026-08-13 | no | Transformers Regular Expression Denial of Service (ReDoS) vulnerability | no |
| transformers | CVE-2025-2099 | GHSA-qq3j-4f4f-9583, PYSEC-2025-40 | 2025-05-19 | fixed in 4.50.0 / fixed in 4.49.0 | 2026-06-10 | no | Hugging Face Transformers Regular Expression Denial of Service | no |
| transformers | CVE-2025-3262 | GHSA-489j-g2vx-39wf, PYSEC-2026-1979 | 2025-07-07 | from 4.49.0; fixed in 4.51.0 | 2026-07-07 | no | Transformers vulnerable to ReDoS attack through its SETTING_RE variable | no |
| transformers | CVE-2025-3263 | GHSA-q2wp-rjmx-x6x9, PYSEC-2026-1987 | 2025-07-07 | fixed in 4.51.0 | 2026-07-07 | no | Transformers's ReDoS vulnerability in get_configuration_file can lead to catastrophic backtracking | no |
| transformers | CVE-2025-3264 | GHSA-jjph-296x-mrcr, PYSEC-2026-1985 | 2025-07-07 | fixed in 4.51.0 | 2026-07-07 | no | Transformers vulnerable to ReDoS attack through its get_imports() function | no |
| transformers | CVE-2025-3777 | GHSA-phhr-52qp-3mj4, PYSEC-2026-1986 | 2025-07-07 | fixed in 4.52.1 | 2026-09-10 | no | Transformers's Improper Input Validation vulnerability can be exploited through username injection | no |
| transformers | CVE-2025-3933 | GHSA-37mw-44qp-f5jm, PYSEC-2026-1977 | 2025-07-11 | fixed in 4.52.1 | 2026-09-10 | no | Transformers is vulnerable to ReDoS attack through its DonutProcessor class | no |
| transformers | CVE-2025-5197 | GHSA-9356-575x-2w9m, PYSEC-2026-1983 | 2025-08-06 | fixed in 4.53.0 | 2026-09-10 | no | Hugging Face Transformers Regular Expression Denial of Service (ReDoS) vulnerability | no |
| transformers | CVE-2025-6638 | GHSA-59p9-h35m-wg4g, PYSEC-2026-1981 | 2025-09-12 | fixed in 4.53.0 | 2026-09-10 | no | Hugging Face Transformers is vulnerable to ReDoS through its MarianTokenizer | no |
| transformers | CVE-2025-6051 | GHSA-rcv9-qm8p-9p6j, PYSEC-2026-1988 | 2025-09-14 | fixed in 4.53.0 | 2026-09-10 | no | Hugging Face Transformers library has Regular Expression Denial of Service | no |
| transformers | CVE-2025-6921 | GHSA-4w7r-h757-3r74, PYSEC-2026-1980 | 2025-09-23 | fixed in 4.53.0 | 2026-09-10 | no | Hugging Face Transformers vulnerable to Regular Expression Denial of Service (ReDoS) in the AdamWeightDecay op | no |
| transformers | CVE-2025-14920 | PYSEC-2025-211 | 2025-12-23 | last affected 4.54.1 | 2026-05-21 | no | Hugging Face Transformers Perceiver Model Deserialization of Untrusted Data Remote Code Ex | no |
| transformers | CVE-2025-14921 | PYSEC-2025-212 | 2025-12-23 | last affected 4.54.1 | 2026-05-21 | no | Hugging Face Transformers Transformer-XL Model Deserialization of Untrusted Data Remote Co | no |
| transformers | CVE-2025-14924 | PYSEC-2025-213 | 2025-12-23 | last affected 4.55.0 | 2026-05-21 | no | Hugging Face Transformers megatron_gpt2 Deserialization of Untrusted Data Remote Code Exec | no |
| transformers | CVE-2025-14926 | PYSEC-2025-214 | 2025-12-23 | last affected 4.57.0 | 2026-05-21 | no | Hugging Face Transformers SEW convert_config Code Injection Remote Code Execution Vulnerab | no |
| transformers | CVE-2025-14927 | PYSEC-2025-215 | 2025-12-23 | last affected 4.57.0 | 2026-05-21 | no | Hugging Face Transformers SEW-D convert_config Code Injection Remote Code Execution Vulner | no |
| transformers | CVE-2025-14928 | PYSEC-2025-216 | 2025-12-23 | last affected 4.57.0 | 2026-05-21 | no | Hugging Face Transformers HuBERT convert_config Code Injection Remote Code Execution Vulne | no |
| transformers | CVE-2025-14929 | PYSEC-2025-217 | 2025-12-23 | last affected 5.0.0-rc0 | 2026-05-21 | no | Hugging Face Transformers X-CLIP Checkpoint Conversion Deserialization of Untrusted Data R | no |
| transformers | CVE-2025-14930 | PYSEC-2025-218 | 2025-12-23 | last affected 4.57.1 | 2026-05-21 | no | Hugging Face Transformers GLM4 Deserialization of Untrusted Data Remote Code Execution Vul | no |
| transformers | CVE-2026-1839 | GHSA-69w3-r845-3855, PYSEC-2026-2288 | 2026-04-07 | fixed in 5.0.0rc3 / fixed in 5.0.0 | 2026-09-10 | no | HuggingFace Transformers allows for arbitrary code execution in the `Trainer` class | no |
| transformers | CVE-2026-4372 | GHSA-29pf-2h5f-8g72, PYSEC-2026-2289 | 2026-05-24 | fixed in 5.3.0 | 2026-09-10 | no | HuggingFace transformers vulnerable to remote code execution | no |
| transformers | CVE-2026-5241 | GHSA-fgcw-684q-jj6r, PYSEC-2026-2290 | 2026-06-03 | fixed in 5.5.0 / last affected 5.2.0 | 2026-09-10 | no | huggingface/transformers: Arbitrary Code Execution During Model Initialization in the LightGlue Model Loading  | no |
| transformers | CVE-2026-9856 | GHSA-xrqw-3rrv-vx5w, PYSEC-2026-3929 | 2026-08-02 | fixed in 5.10.0 | 2026-09-10 | no | Transformers save_pretrained path traversal allows arbitrary file writes through chat template names | no |
| transformers | CVE-2026-80047 | GHSA-x9r9-c232-4q39, PYSEC-2026-4174 | 2026-09-01 | from 4.49.0; last affected 5.8.1 | 2026-10-01 | no | Hugging Face Transformers downloads custom generation code before trust consent | no |
| torch | (none; cites CVE-2024-24806) | GHSA-2rj9-7h5r-q4h8 (**not in OSV**) | 2025-09-29 | `<= 2.8.0`, patched 2.9.0 (GitHub) | - | no | CVE for libuv used by tensorpipe | no |
| torch | (none) | GHSA-g6v3-crfc-cggj (**not in OSV**) | 2025-09-29 | `< 2.1.0`, patched 2.1.0 (GitHub) | - | no | Access to arbitrary address while parsing flatbuffer format | no |

### K.5 Release-age analysis and a maturity window

Age of every package version in the four sets, on 2026-10-26 (VERIFIED FACT, PyPI upload time of the first file; the sets list the versions this phase's metadata computation would pick, which are the newest allowed unless a project package already satisfies):

| Package | Version | Uploaded | Age on 2026-10-26 (days) | In sets |
| --- | --- | --- | --- | --- |
| huggingface-hub | 2.3.0 | 2026-10-23 | 3 | S4 |
| setuptools | 84.2.1 | 2026-10-20 | 6 | S1,S2,S3,S4 |
| filelock | 4.2.4 | 2026-10-19 | 7 | S1,S2,S3,S4 |
| transformers | 5.20.2 | 2026-10-19 | 7 | S4 |
| tokenizers | 0.23.3 | 2026-10-09 | 17 | S4 |
| hf-xet | 1.7.0 | 2026-10-06 | 20 | S1,S2,S3,S4 |
| typer | 0.27.3 | 2026-10-06 | 20 | S1,S2,S3,S4 |
| torch | 2.14.1 | 2026-09-30 | 26 | S3,S4 |
| huggingface-hub | 1.33.0 | 2026-09-24 | 32 | S1,S2,S3 |
| fsspec | 2026.9.0 | 2026-09-18 | 38 | S1,S2,S3,S4 |
| tqdm | 4.70.1 | 2026-09-11 | 45 | S1,S2,S3,S4 |
| regex | 2026.9.10 | 2026-09-09 | 47 | S1,S2,S3,S4 |
| anyio | 4.15.1 | 2026-09-05 | 51 | S1,S2,S3,S4 |
| click | 8.5.0 | 2026-08-26 | 61 | S1,S2,S3,S4 |
| httpcore2 | 2.12.0 | 2026-08-18 | 69 | S4 |
| httpx2 | 2.12.0 | 2026-08-18 | 69 | S4 |
| idna | 3.19 | 2026-08-18 | 69 | S1,S2,S3,S4 |
| pygments | 2.21.0 | 2026-08-17 | 70 | S1,S2,S3,S4 |
| annotated-doc | 0.0.5 | 2026-07-28 | 90 | S1,S2,S3,S4 |
| certifi | 2026.7.22 | 2026-07-22 | 96 | S1,S2,S3 |
| torch | 2.13.0 | 2026-07-08 | 110 | S1,S2 |
| typing-extensions | 4.16.0 | 2026-07-02 | 116 | S1,S2,S3,S4 |
| transformers | 5.12.1 | 2026-06-15 | 133 | S1,S3 |
| safetensors | 0.8.0 | 2026-06-09 | 139 | S4 |
| transformers | 5.10.1 | 2026-06-03 | 145 | S2 |
| markdown-it-py | 4.2.0 | 2026-05-07 | 172 | S1,S2,S3,S4 |
| rich | 15.0.0 | 2026-04-12 | 197 | S1,S2,S3,S4 |
| networkx | 3.6.1 | 2025-12-08 | 322 | S1,S2,S3,S4 |
| markupsafe | 3.0.3 | 2025-09-27 | 394 | S1,S2,S3,S4 |
| tokenizers | 0.22.1 | 2025-09-19 | 402 | S1,S2,S3 |
| truststore | 0.10.4 | 2025-08-12 | 440 | S4 |
| safetensors | 0.6.2 | 2025-08-08 | 444 | S1,S2,S3 |
| sympy | 1.14.0 | 2025-04-27 | 547 | S1,S2,S3,S4 |
| h11 | 0.16.0 | 2025-04-24 | 550 | S1,S2,S3,S4 |
| httpcore | 1.0.9 | 2025-04-24 | 550 | S1,S2,S3 |
| packaging | 25.0 | 2025-04-19 | 555 | S1,S2,S3,S4 |
| jinja2 | 3.1.6 | 2025-03-05 | 600 | S1,S2,S3,S4 |
| httpx | 0.27.2 | 2024-08-27 | 790 | S1,S2,S3 |
| pyyaml | 6.0.2 | 2024-08-06 | 811 | S1,S2,S3,S4 |
| sniffio | 1.3.1 | 2024-02-25 | 974 | S1,S2,S3 |
| numpy | 1.26.4 | 2024-02-05 | 994 | S1,S2,S3,S4 |
| shellingham | 1.5.4 | 2023-10-24 | 1098 | S1,S2,S3,S4 |
| mpmath | 1.3.0 | 2023-03-07 | 1329 | S1,S2,S3,S4 |
| colorama | 0.4.6 | 2022-10-25 | 1462 | S1,S2,S3,S4 |
| mdurl | 0.1.2 | 2022-08-14 | 1534 | S1,S2,S3,S4 |

**Advisory latency (VERIFIED FACT, small sample; rough evidence).** For the 7 `transformers` CVEs that list any scanned release, the advisory was published a median of **74 days** (range -24 to +111) after the upload of the newest release OSV lists as affected; 6 of 7 were published more than 30 days later, 2 of 7 more than 90 days. For the 22 `torch` CVEs: median **60.5** days (range -443 to +239); 17 of 22 more than 30 days, 9 of 22 more than 90 days. Negative values are advisories published before the newest affected release existed (records with no fix, so OSV keeps later releases in range), so the figures mix disclosure lag with unfixed records. First fixed releases appeared before the advisory was published in most cases for which a fixed version is recorded.

**Assessment and proposal.** (PRELIMINARY APPLICABILITY ASSESSMENT) A short maturity window alone is a weak control: most advisories for these two libraries surfaced two to three months after the affected release, so a 30-day rule would not have kept most of the later-affected releases out. It still has value against yanked or unstable releases (`transformers` 5.10.0 was yanked as an unstable main-branch push) and gives time for regressions to surface (tokenizers 0.23.1 had a truncation regression fixed in 0.23.3). (CANDIDATE PROPOSAL, owner decision) A project policy should require a maturity window **combined with** a hash-pinned lock, a re-check of OSV, PyPI and the upstream GitHub advisory lists on the day of every install, no yanked release, and a recurring re-check afterwards. As a starting value to decide: at least 90 days for the four direct packages and at least 30 days for transitive packages. Under that proposal S1 and S2 pass for the direct packages (youngest 110 days), S3 fails (`torch` 2.14.1, 26 days) and S4 fails (`transformers` 5.20.2, 7 days; `tokenizers` 0.23.3, 17 days). Several transitive packages would also need exact older pins: `filelock` 4.2.4 (7 days), `hf-xet` 1.7.0 and `typer` 0.27.3 (20 days each), and `setuptools` 84.2.1 (6 days; constrained anyway, K.6); whether older releases exist inside their declared ranges was **not** checked (UNRESOLVED).

### K.6 Impact of upgrading `setuptools` and of resolving the unrelated `certifi` advisory

**`setuptools` (VERIFIED FACT for the requirement; VERIFIED FROM OFFICIAL SOURCE for the changes).** `torch` 2.13.0 and 2.14.1 require `setuptools>=77.0.3` on Windows; the project environment has 65.5.0 (required by `tensorboard>=41.0.0` and `tensorflow-intel` with no bound). The setuptools changelog lists, between 65.5.0 and 84.2.1: v66.0.0 drops support for non-PEP 440 versions (all 133 installed distributions have valid versions: VERIFIED FACT); v77.0.0 starts PEP 639 licence handling (affects building packages, not installing wheels); v79.0.0 removes legacy editable installs (the project's own editable install uses `hatchling`, per `pyproject.toml`); v83.0.0 needs Python 3.10 or newer (met); and **v82.0.0 removes `pkg_resources`**. The project environment contains runtime imports of `pkg_resources` in `tensorboard/default.py` (unconditional, module level) and `tensorboard/data/server_ingester.py`; `werkzeug`, `pytz` and `_pytest` import it only conditionally. TensorFlow 2.17.0 requires `tensorboard>=2.17,<2.18`. So (PRELIMINARY APPLICABILITY ASSESSMENT) **setuptools 82 or later (84.2.1 is the newest) would break `import tensorboard.default`** in the project environment; whether `import tensorflow` or any project script reaches that module is UNRESOLVED. (CANDIDATE PROPOSAL) Constrain `setuptools>=77.0.3,<82` in any environment that holds `torch`. In a disposable environment outside the repository nothing existing is affected; changing the project environment would need its own approval and is not requested now.

**`certifi` (VERIFIED FROM OFFICIAL SOURCE).** GHSA-6q48-6c7w-9gw2: severity **Critical** (CVSS 9.1), affected `>= 2019.03.09, < 2026.10.18`, published 2026-10-20. The CA bundle trusted `emSign ECC Root CA - G3`, eight eMudhra intermediate keys under it are compromised and revoked, so an on-path attacker could intercept TLS traffic of clients that trust the bundle (`requests`, `urllib3`, `pip`). The "patched" field says 2026.10.18, but the description says that release removed all emSign roots and **2026.10.19 restored the unaffected ones: use 2026.10.19 or later** (latest 2026.10.23). The project environment has `certifi 2026.7.22` (affected) and `pip 26.2.1`, which vendors `certifi 2026.6.17` (also affected; VERIFIED FACT, `pip/_vendor/vendor.txt`); `pip 26.2.2` was uploaded on 2026-10-20 and whether it vendors a fixed copy is UNRESOLVED. Installed packages that require `certifi` (`requests>=2023.5.7`, `httpx`, `httpcore`, `curl-cffi>=2024.2.2`) set no upper bound, so upgrading satisfies all of them (VERIFIED FACT). Effect (PRELIMINARY): a server whose chain ends in the removed emSign root will fail verification, which is the intent; the project's endpoints (PyPI, Yahoo Finance, Google AI, GDELT, the databases) were not probed, so whether any chains to emSign is UNRESOLVED. Hash-pinned installs (`--require-hashes`) mean an interception could not substitute a different wheel, but the recorded hashes themselves came from PyPI over TLS and have not been checked through an independent channel. This is unrelated to S1 to S4 and is **not fixed here**.

### K.7 Static inspection of the two existing call sites against transformers 5.x (nothing was run)

Source: the official `MIGRATION_GUIDE_V5.md`. "Not mentioned" means the guide is silent, which is **not** confirmation that nothing changed.

| Call site | What the code does | What the official guide says | Assessment | Label |
| --- | --- | --- | --- | --- |
| Runtime `sentiment_model.py:258` | `AutoTokenizer.from_pretrained(dir, local_files_only=True, trust_remote_code=False)`, then `tokenizer(text, truncation=True, max_length=..., return_tensors="pt")` | `AutoTokenizer` "automatically selects the appropriate backend based on available files and dependencies"; slow tokenizer files are removed in favour of fast ones; the three keywords are not mentioned | no documented source change; UNRESOLVED whether a saved artifact loads offline in every case (a backend that needs a conversion from Hub files would fail and be caught as `load_failed`); S4 pulls `tokenizers` 0.23.3 whose notes mention a truncation fix | PRELIMINARY + UNRESOLVED |
| Runtime `sentiment_model.py:259` | `AutoModelForSequenceClassification.from_pretrained(dir, local_files_only=True, trust_remote_code=False, use_safetensors=True)`, `.logits[0].tolist()` | the keywords are not mentioned; safetensors is "the preferred file format" | no documented change; UNRESOLVED whether `use_safetensors=True` still raises when only a `.bin` file exists | PRELIMINARY + UNRESOLVED |
| Training `train_sentiment_transformer.py:118,120` | `from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup`; `transformers.set_seed(seed)` | `get_linear_schedule_with_warmup` and `set_seed` are not mentioned (the guide removes `AutoModelWithLMHead`, which the code does not use) | UNRESOLVED | UNRESOLVED |
| Training `:122-123` | `AutoTokenizer.from_pretrained(hub_id)`; `AutoModelForSequenceClassification.from_pretrained(hub_id, num_labels=..., id2label=..., label2id=..., ignore_mismatched_sizes=True)` | `num_labels`, `id2label`, `label2id`, `ignore_mismatched_sizes` not mentioned | no documented change; UNRESOLVED | UNRESOLVED |
| **Training `:155`** | **`model.save_pretrained(directory, safe_serialization=True)`** | **"The `safe_serialization` parameter has been removed from all `save_pretrained` and `push_to_hub` methods."** | **A source change is required** (drop the keyword; safetensors is the only format). Whether the keyword raises or is ignored is UNRESOLVED; either way the call must change | VERIFIED FROM OFFICIAL SOURCE + VERIFIED FACT |
| Training `:156-158` | `tokenizer.save_pretrained(directory)`; the file list excludes `generation_config.json`; reads `model.config.vocab_size` | non-generative models "will no longer have a `generation_config`" (harmless to the exclusion list); `vocab_size` not mentioned | no change expected | PRELIMINARY |
| `dependencies_available()` and `check_environment()` | only `importlib.util.find_spec` for the four names | n/a | no version gate: neither the loader nor the training script would refuse transformers 5.x, so a mismatch would show up only at call time | VERIFIED FACT |

Other observations (VERIFIED FACT, from the guide and metadata): `huggingface-hub>=1.0` replaces `requests` with `httpx`; `transformers` 5.x adds `typer` as a requirement; TensorFlow and Flax support is removed (irrelevant: the project uses `torch`); `tests/training/sentiment` uses a fake trainer, so **no existing test would catch any of the API changes above**; `training/sentiment/README.md` still calls the v4 line the long-term-support branch, which no longer helps because no v4 release is free of advisories. Whether `accelerate` (part of the `transformers[torch]` extra) is needed for `from_pretrained` on 5.x is UNRESOLVED. No code was modified.

### K.8 Recommendation, unresolved questions and the owner decision required

**Recommendation (the evidence supports a ranking, not an approval).** On the evidence reviewed, **S1 is the most defensible candidate to take into isolated verification, conditionally; S4 should be excluded for now; A2 remains UNRESOLVED and installation remains blocked.** Reasons (PRELIMINARY APPLICABILITY ASSESSMENT): all four sets are equal on advisories (zero records, zero on the PyPI field and on the upstream advisory lists), so security does not separate them; S4 is the least defensible because it is the youngest (`transformers` 7 days, `huggingface-hub` 2.3.0 three days, `tokenizers` 17 days), changes R3 and R4 and moves `tokenizers` and `safetensors` to new minor lines; S3 buys nothing over S1 (`torch` 2.14.1 is 26 days old and its fixes are for MPS and CUDA); S2 against S1 differs only in `transformers` 5.10.1 (the first non-yanked build after an unstable one) versus 5.12.1 (later patch with more fixes), with no advisory difference. This is **not** a finding that S1 is safe: U1 to U9 below remain, the releases are 3.5 to 4.5 months old, the fixes were not independently reviewed, and the move from `transformers` 4.x to 5.x has never been run against this project's code.

**Conditions I would attach to S1** (CANDIDATE PROPOSALS): hash-pinned install into a disposable environment outside the repository; `setuptools>=77.0.3,<82`; transitive packages pinned exactly under the owner's maturity rule; a fresh OSV, PyPI and GitHub advisory check on the day; no change to the project environment; the `save_pretrained` change, a `use_safetensors=True`, `local_files_only` and revision-pinning hardening of the training loader, and the README correction made later as a separate approved code change; the unrelated `certifi` advisory resolved (K.6) before any download from the Hub.

**Unresolved questions.**

| Id | Question |
| --- | --- |
| N1 | Does `torch` 2.13.0 / 2.14.1 work with `numpy==1.26.4` at runtime, and do TensorFlow 2.17 and PyTorch coexist in one Windows process? (the 2.13.0 notes and `requirements.txt` are silent) |
| N2 | Which of the 107 / 95 declared licence files ship in the Windows CPU wheel? |
| N3 | Do the six torch records with no fixed version describe weaknesses that persist in 2.13 / 2.14? (all are in code the repository does not call, and PyTorch's policy treats such operator bugs as ordinary bugs) |
| N4 | Is the CVE-2026-4372 fix complete, and does the absence of the `kernels` package block that path on the original pins? |
| N5 | Do `use_safetensors=True`, `num_labels` / `id2label` / `label2id`, `ignore_mismatched_sizes`, `set_seed` and `get_linear_schedule_with_warmup` behave as the code expects on 5.x, does `from_pretrained` need `accelerate`, and does a saved tokenizer load offline? |
| N6 | Does anything in the project (or `import tensorflow`) import `tensorboard.default`, i.e. is `setuptools<82` required for the project environment? |
| N7 | Does `pip` 26.2.2 vendor a fixed `certifi`, and does any project endpoint chain to the removed emSign root? |
| N8 | Do older releases exist inside the declared ranges for the young transitive packages (`filelock`, `hf-xet`, `typer`) if a maturity rule is adopted? |
| N9 | Which maturity rule, if any, does the owner adopt, and who re-checks advisories after install? |
| N10 | `transformers` publishes no GitHub advisories of its own, and OSV is missing two PyTorch advisories: what second source does the owner want for advisory completeness? |
| N11 | The base-model licences and immutable revisions (R6, R7) and every dataset item (R8 to R14) are untouched by this review. |

**Exact owner decision required before an isolated installation** (to be recorded in `reports/sentiment_model_approval_record.md`; not recorded now):

> I approve A2 for **isolated verification only**: `torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2` (set S1), with transitive packages fixed by a hash-pinned list prepared and checked on the day of installation, installed with pip from the configured package index into a disposable virtual environment outside the repository, with `setuptools>=77.0.3,<82`, and removed afterwards unless I say otherwise. I accept, for this verification only: the `transformers` 4.x to 5.x major-version move; the `torch` licence expression in section K.3; and the maturity rule `[direct packages >= N days, transitive packages >= M days, no yanked release, no OSV / PyPI / upstream advisory on the day]` with N = ___ and M = ___. I understand that the isolated test may show the project's two call sites need code changes, that those changes, any production use, any weight or dataset access, R6 to R14 and activation remain separate approvals, that the project environment (including `setuptools` and `certifi`) is not changed by this approval, and that the unrelated `certifi` advisory needs its own task before any Hugging Face download.

If the owner prefers a different set (for example S2) or wants the security review to read the fix commits and the source before any install, that replaces the text above; A2 stays UNRESOLVED until a decision is recorded.

## L. Isolated compatibility validation of set S1 — 2026-10-27 (fifth brief): completed; one flagged advisory finding on a transitive build tool

Written for the project owner. The owner recorded **A2 APPROVED for isolated verification only, set S1** (`torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2`) in the approval record **before** any environment was created. A1 stays REJECTED for `torch==2.6.0` and `transformers==4.57.1`; R3 / R4 remain approved as `0.22.1` / `0.6.2`; R5 approved for isolated verification only; R6 to R14 UNRESOLVED and untouched. This section holds the evidence. Labels: VERIFIED FACT, VERIFIED FROM OFFICIAL SOURCE, PRELIMINARY APPLICABILITY ASSESSMENT, UNRESOLVED.

### L.1 What was and was not done

Done, in a disposable virtual environment at `C:\Users\Administrator\.copilot\sentiment-compatibility-venv` (outside the repository): installed exactly the 35 hash-pinned wheels below; verified hashes, metadata, imports, CPU-only behaviour, an in-memory tokenizer, a safetensors round trip, `pip check` and TensorFlow + PyTorch coexistence in separate processes. **Not done, by the terms of A2:** no model was built or loaded (not even a randomly initialised stand-in), no forward pass, no training, no model weight, tokenizer file, dataset or Hugging Face asset was requested (offline switches `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` were set before every import and `HF_HOME` pointed at an empty scratch directory, which stayed empty; `~/.cache/huggingface` was never created), the model loader and `models/sentiment/` were not enabled, `backend/pyproject.toml`, application code, configuration and the project environment were not changed, the project `certifi` was not touched, and `SENTIMENT_MODEL_ENABLED` stays false with `user_text_rules_v1` active. The environment, the downloaded wheels and the pip cache were deleted afterwards (L.10).

### L.2 Environment (VERIFIED FACT)

Base interpreter `C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe`: **Python 3.11.9** (MSC v.1938, AMD64), Windows 10.0.26300 amd64; the venv shows the same interpreter and **pip 24.0**; 161 GB free on `C:`; no pip configuration (`pip config list` empty; default PyPI index) and no `PIP_*`, `HF_*`, `TRANSFORMERS_*` or `PYTHONPATH` variables. A fresh venv holds only `pip 24.0` and `setuptools 65.5.0`. Constraints applied to the resolver (`constraints.txt`): `setuptools>=77.0.3,<82` (the approved bound) and `numpy==1.26.4` (the project's pin; TensorFlow 2.17.0 needs numpy below 2.0).

### L.3 Resolution, hashes and installation (VERIFIED FACT)

- pip's own resolver (`pip install --dry-run --ignore-installed --report`) resolved the four pins plus constraints to **35 packages with no conflict**; every file is a wheel from the configured index (no source build).
- Every wheel's SHA-256 in pip's report equals the digest PyPI publishes for that file (35 of 35); none is yanked. `pip download --only-binary=:all: --no-deps --require-hashes` and then `pip install --no-index --find-links <wheels> --only-binary=:all: --no-deps --require-hashes` succeeded; I also hashed the 35 files on disk independently (match: pinned list, pip report and PyPI digest, sizes equal). The downloads therefore did not depend on pip 24.0's vendored CA bundle alone: the digests were also fetched by Python's `urllib` through the operating-system trust store, and the two sources agree.
- **Wheel sizes: 170.3 MB in total** (`torch` 122.0 MB). **Installed size: 852.8 MB** for the 35 distributions (RECORD files; `torch` 524 MB, `transformers` 99 MB, `sympy` 76 MB, `numpy` 72 MB, `networkx` 17 MB, `hf-xet` 10 MB); whole `site-packages` 865.8 MB; whole venv 868.2 MB.
- `pip check`: **"No broken requirements found."** Installed metadata equals the pinned list for all 35 packages; no unpinned package besides `pip` is installed; `pip freeze --all` before: `pip==24.0`, `setuptools==65.5.0`; after: 36 lines (the 35 plus `pip`).
- `torch` 2.13.0 declares 17 requirements; **active on Windows / Python 3.11**: `filelock`, `typing-extensions>=4.10.0`, `setuptools>=77.0.3`, `sympy>=1.13.3`, `networkx>=2.5.1`, `jinja2`, `fsspec>=0.8.5`. `transformers` 5.12.1: `huggingface-hub>=1.5.0,<2.0`, `numpy>=1.17`, `packaging>=20.0`, `pyyaml>=5.1`, `regex>=2025.10.22`, `tokenizers>=0.22.0,<=0.23.0`, `typer`, `safetensors>=0.4.3`, `tqdm>=4.60`. `tokenizers` 0.22.1: `huggingface-hub>=0.16.4,<2.0`. `safetensors` 0.6.2: none.

**The 35 hash-pinned packages** (PyPI JSON digests equal pip's; ages on 2026-10-27; this is the install-day list):

| Package | Version | Role | Wheel | Size | SHA-256 | Hash = PyPI digest | Yanked | Uploaded | Age (days) | Licence (PyPI metadata) | OSV | PyPI vuln field |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| annotated-doc | 0.0.5 | transitive | `annotated_doc-0.0.5-py3-none-any.whl` | 0.0 MB | `117bac03a25ede5df5440e855b32d556049ca169ead221505badf432fed4b101` | yes | no | 2026-07-28 | 91 | MIT | 0 | 0 |
| anyio | 4.15.1 | transitive | `anyio-4.15.1-py3-none-any.whl` | 0.1 MB | `6152fdbbf9a77fdec97731721bebf7c4c44f7c29b424b0065826173efc7ed101` | yes | no | 2026-09-05 | 52 | MIT | 0 | 0 |
| certifi | 2026.10.23 | transitive | `certifi-2026.10.23-py3-none-any.whl` | 0.1 MB | `e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1` | yes | no | 2026-10-23 | 4 | Mozilla Public License 2.0 (MPL 2.0) | 0 | 0 |
| click | 8.5.0 | transitive | `click-8.5.0-py3-none-any.whl` | 0.1 MB | `255bc9599cf7748b4b1a446ccc735421bd08a2ae529a8b88597d3de5664ee360` | yes | no | 2026-08-26 | 62 | BSD-3-Clause | 0 | 0 |
| colorama | 0.4.6 | transitive | `colorama-0.4.6-py2.py3-none-any.whl` | 0.0 MB | `4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6` | yes | no | 2022-10-25 | 1463 | BSD License | 0 | 0 |
| filelock | 4.2.4 | transitive | `filelock-4.2.4-py3-none-any.whl` | 0.2 MB | `301241438c57936ef93f4243a94f2559022268bfcf9b375a9a72eb0f8db8358e` | yes | no | 2026-10-19 | 8 | MIT | 0 | 0 |
| fsspec | 2026.9.0 | transitive | `fsspec-2026.9.0-py3-none-any.whl` | 0.2 MB | `8dd6e646e99ea382bd85f97a45e6b526a442d79423a7dc673f1e2756d05fcb5f` | yes | no | 2026-09-18 | 39 | BSD-3-Clause | 0 | 0 |
| h11 | 0.16.0 | transitive | `h11-0.16.0-py3-none-any.whl` | 0.0 MB | `63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86` | yes | no | 2025-04-24 | 551 | MIT License | 0 | 0 |
| hf-xet | 1.7.0 | transitive | `hf_xet-1.7.0-cp38-abi3-win_amd64.whl` | 3.8 MB | `2b7bb5727889b0f2436dbaaad8fc4c3e66b8240d992716989e0c086b4278b1bc` | yes | no | 2026-10-06 | 21 | Apache-2.0 | 0 | 0 |
| httpcore | 1.0.9 | transitive | `httpcore-1.0.9-py3-none-any.whl` | 0.1 MB | `2d400746a40668fc9dec9810239072b40b4484b640a8c38fd654a024c7a1bf55` | yes | no | 2025-04-24 | 551 | BSD-3-Clause | 0 | 0 |
| httpx | 0.28.1 | transitive | `httpx-0.28.1-py3-none-any.whl` | 0.1 MB | `d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad` | yes | no | 2024-12-06 | 690 | BSD License | 0 | 0 |
| huggingface_hub | 1.33.0 | transitive | `huggingface_hub-1.33.0-py3-none-any.whl` | 0.8 MB | `04e434b06e100eddbce9a6e817d72693a7884b10a79bd67ab48080d5c07eb899` | yes | no | 2026-09-24 | 33 | Apache Software License | 0 | 0 |
| idna | 3.20 | transitive | `idna-3.20-py3-none-any.whl` | 0.1 MB | `ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c` | yes | no | 2026-09-17 | 40 | BSD-3-Clause | 0 | 0 |
| Jinja2 | 3.1.6 | transitive | `jinja2-3.1.6-py3-none-any.whl` | 0.1 MB | `85ece4451f492d0c13c5dd7c13a64681a86afae63a5f347908daf103ce6d2f67` | yes | no | 2025-03-05 | 601 | BSD License | 0 | 0 |
| markdown-it-py | 4.2.0 | transitive | `markdown_it_py-4.2.0-py3-none-any.whl` | 0.1 MB | `9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a` | yes | no | 2026-05-07 | 173 | MIT License | 0 | 0 |
| MarkupSafe | 3.0.4 | transitive | `markupsafe-3.0.4-cp311-cp311-win_amd64.whl` | 0.0 MB | `fdb4ca07ab75ffadab4a8b135ad59cdbb3156b99310f3d565370da74a15d6bd3` | yes | no | 2026-10-02 | 25 | BSD-3-Clause | 0 | 0 |
| mdurl | 0.1.2 | transitive | `mdurl-0.1.2-py3-none-any.whl` | 0.0 MB | `84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8` | yes | no | 2022-08-14 | 1535 | MIT License | 0 | 0 |
| mpmath | 1.3.0 | transitive | `mpmath-1.3.0-py3-none-any.whl` | 0.5 MB | `a0b2b9fe80bbcd81a6647ff13108738cfb482d481d826cc0e02f5b35e5c88d2c` | yes | no | 2023-03-07 | 1330 | BSD License | 0 | 0 |
| networkx | 3.6.1 | transitive | `networkx-3.6.1-py3-none-any.whl` | 2.1 MB | `d47fbf302e7d9cbbb9e2555a0d267983d2aa476bac30e90dfbe5669bd57f3762` | yes | no | 2025-12-08 | 323 | BSD-3-Clause | 0 | 0 |
| numpy | 1.26.4 | transitive | `numpy-1.26.4-cp311-cp311-win_amd64.whl` | 15.8 MB | `cd25bcecc4974d09257ffcd1f098ee778f7834c3ad767fe5db785be9a4aa9cb2` | yes | no | 2024-02-05 | 995 | BSD License | 0 | 0 |
| packaging | 26.3 | transitive | `packaging-26.3-py3-none-any.whl` | 0.1 MB | `d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c` | yes | no | 2026-08-04 | 84 | Apache-2.0 OR BSD-2-Clause | 0 | 0 |
| Pygments | 2.21.0 | transitive | `pygments-2.21.0-py3-none-any.whl` | 1.3 MB | `2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9` | yes | no | 2026-08-17 | 71 | BSD-2-Clause | 0 | 0 |
| PyYAML | 6.0.3 | transitive | `pyyaml-6.0.3-cp311-cp311-win_amd64.whl` | 0.2 MB | `9f3bfb4965eb874431221a3ff3fdcddc7e74e3b07799e0e84ca4a0f867d449bf` | yes | no | 2025-09-25 | 397 | MIT License | 0 | 0 |
| regex | 2026.9.29 | transitive | `regex-2026.9.29-cp311-cp311-win_amd64.whl` | 0.3 MB | `1043aedf5917caa861bcb25a9c11460049656bdf0017a90a309fa8f255467725` | yes | no | 2026-09-29 | 28 | Apache-2.0 AND CNRI-Python | 0 | 0 |
| rich | 15.0.0 | transitive | `rich-15.0.0-py3-none-any.whl` | 0.3 MB | `33bd4ef74232fb73fe9279a257718407f169c09b78a87ad3d296f548e27de0bb` | yes | no | 2026-04-12 | 198 | MIT License | 0 | 0 |
| safetensors | 0.6.2 | requested | `safetensors-0.6.2-cp38-abi3-win_amd64.whl` | 0.3 MB | `c7b214870df923cbc1593c3faee16bec59ea462758699bd3fee399d00aac072c` | yes | no | 2025-08-08 | 445 | Apache Software License | 0 | 0 |
| setuptools | 81.0.0 | transitive | `setuptools-81.0.0-py3-none-any.whl` | 1.1 MB | `fdd925d5c5d9f62e4b74b30d6dd7828ce236fd6ed998a08d81de62ce5a6310d6` | yes | no | 2026-02-06 | 263 | MIT | 3 GHSA-h35f-9h28-mq5c,GHSA-xmj3-9gf7-h52w,PYSEC-2026-3447 | 3 |
| shellingham | 1.5.4 | transitive | `shellingham-1.5.4-py2.py3-none-any.whl` | 0.0 MB | `7ecfff8f2fd72616f7481040475a65b2bf8af90a56c89140852d1120324e8686` | yes | no | 2023-10-24 | 1099 | ISC License (ISCL) | 0 | 0 |
| sympy | 1.14.0 | transitive | `sympy-1.14.0-py3-none-any.whl` | 6.3 MB | `e091cc3e99d2141a0ba2847328f5479b05d94a6635cb96148ccb3f34671bd8f5` | yes | no | 2025-04-27 | 548 | BSD License | 0 | 0 |
| tokenizers | 0.22.1 | requested | `tokenizers-0.22.1-cp39-abi3-win_amd64.whl` | 2.7 MB | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` | yes | no | 2025-09-19 | 403 | Apache Software License | 0 | 0 |
| torch | 2.13.0 | requested | `torch-2.13.0-cp311-cp311-win_amd64.whl` | 122.0 MB | `a0d8b11f16a48d60e2015d8213aa0390744cbebb98e58b62b3514dddc656e330` | yes | no | 2026-07-08 | 111 | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT | 0 | 0 |
| tqdm | 4.70.1 | transitive | `tqdm-4.70.1-py3-none-any.whl` | 0.1 MB | `c293e525e6fef9c20e8728fd4612df02a0aa31bb5fe91ecd93e123b1b7bffa73` | yes | no | 2026-09-11 | 46 | MPL-2.0 AND MIT | 0 | 0 |
| transformers | 5.12.1 | requested | `transformers-5.12.1-py3-none-any.whl` | 11.2 MB | `2a5e109d2021265df7098ffbb738295acaf5ad256f12cbc586db2ea4dcbb1a8a` | yes | no | 2026-06-15 | 134 | Apache 2.0 License | 0 | 0 |
| typer | 0.27.3 | transitive | `typer-0.27.3-py3-none-any.whl` | 0.1 MB | `e50022f28b82a86313e54501317a1db64bf8f8d036ff8cfe5ca7e47675454aff` | yes | no | 2026-10-06 | 21 | MIT | 0 | 0 |
| typing_extensions | 4.16.0 | transitive | `typing_extensions-4.16.0-py3-none-any.whl` | 0.0 MB | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` | yes | no | 2026-07-02 | 117 | PSF-2.0 | 0 | 0 |

### L.4 Licence findings (VERIFIED FACT from installed metadata and PyPI)

| Package | Installed licence metadata |
| --- | --- |
| `torch` 2.13.0 | `License-Expression: Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT`; **107 `License-File` entries, and all 107 files are present under `torch-2.13.0.dist-info/licenses/`** (`LICENSE` plus `third_party/**`, for example `FP16`, `FXdiv`, `NNPACK`, `NVTX`, `tensorpipe/third_party/libuv`, `pybind11`). This closes the open question of which licence files ship in the Windows wheel: all declared ones do. |
| `transformers` 5.12.1 | `License: Apache 2.0 License`; 1 licence file (`LICENSE`) |
| `tokenizers` 0.22.1 | no `License` field and no licence file; classifier "Apache Software License"; the upstream `LICENSE` is Apache-2.0 (read in the fourth-brief review) |
| `safetensors` 0.6.2 | classifier "Apache Software License"; 1 licence file; upstream `LICENSE` is Apache-2.0 |
| Transitive (31 packages) | permissive throughout: MIT (`annotated-doc`, `anyio`, `filelock`, `h11`, `markdown-it-py`, `mdurl`, `PyYAML`, `rich`, `setuptools`, `typer`), BSD (`click`, `colorama`, `fsspec`, `httpcore`, `httpx`, `idna`, `Jinja2`, `MarkupSafe`, `mpmath`, `networkx`, `numpy`, `sympy`), BSD-2-Clause (`Pygments`), Apache-2.0 (`hf-xet`, `huggingface_hub`), Apache-2.0 OR BSD-2-Clause (`packaging`), Apache-2.0 AND CNRI-Python (`regex`), ISC (`shellingham`), PSF-2.0 (`typing_extensions`); **MPL-2.0: `certifi`; MPL-2.0 AND MIT: `tqdm`** (file-level copyleft, no effect unless those files are modified and redistributed). No GPL, LGPL or AGPL. |

PRELIMINARY APPLICABILITY ASSESSMENT (not legal advice): no licensing concern for an academic prototype that installs these packages and does not redistribute them; section K.3 explains the wider `torch` expression (PEP 639 adoption). The model and dataset licences (R6 to R8) are untouched and remain the real licensing risk.

### L.5 Security and advisory findings on install day (2026-10-27)

Sources: OSV (`querybatch` for each of the 35 name / version pairs, then per-record lookups), the PyPI `vulnerabilities` field for each, and the upstream GitHub advisory lists.

| Check | Result |
| --- | --- |
| OSV records for `torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2` | **none** (VERIFIED FACT) |
| OSV records for the 31 other packages | **none, except `setuptools==81.0.0`: three records (two advisories)** below |
| PyPI `vulnerabilities` field | empty for all except `setuptools 81.0.0` |
| Upstream lists | PyTorch repository: 5 advisories, newest 2026-01-26, none lists 2.13.0 (unchanged since 2026-10-26); `transformers` repository: 0 advisories (VERIFIED FROM OFFICIAL SOURCE) |
| Yanked releases | none |
| Maturity | no rule was set by the owner; ages reported only. Direct packages: `torch` 111 days, `transformers` 134, `tokenizers` 403, `safetensors` 445. Youngest transitive: `certifi` 2026.10.23 (4 days), `filelock` 4.2.4 (8), `hf-xet` 1.7.0 and `typer` 0.27.3 (21 each) |

**Flagged finding: `setuptools`.** The approved bound `>=77.0.3,<82` admits only releases that OSV lists for two advisories, so a clean version was not available inside the approved range. I installed the highest release in range, `setuptools==81.0.0` (the version pip chose), because that is what the owner's conditions specify, and I am flagging the conflict rather than resolving it.

| Advisory | Affected | Fixed | Content | Applicability here (PRELIMINARY APPLICABILITY ASSESSMENT) |
| --- | --- | --- | --- | --- |
| GHSA-h35f-9h28-mq5c = CVE-2026-59890 = PYSEC-2026-3447 (Moderate, CVSS 3.1 AV:L; published 2026-07-21) | all releases before 83.0.0 | 83.0.0 | `MANIFEST.in` exclusion rules are matched without Unicode normalisation, so on **macOS APFS / HFS+** an NFD file name can bypass an NFC exclusion and be packed into a **source distribution** | not applicable: Windows, no sdist is built in or from this environment |
| GHSA-xmj3-9gf7-h52w (Low, CVSS 4.0; published 2026-10-23, four days before the install) | 38.2.2 up to but excluding 84.1.0 | 84.1.0 | on **Windows**, a crafted wheel's `.dist-info/namespace_packages.txt` can make setuptools' **legacy egg-style wheel installation** (`Wheel.install_as_egg`) create an `__init__.py` outside the target directory; the attacker controls the path, not the contents | not applicable: every wheel here was installed by pip's own installer, never through `setuptools`' legacy path |

Releases of `setuptools` in the approved range 77.0.3 to 81.0.0 are all listed for both advisories (77.0.3 to 78.1.0 also for older records), and by OSV's affected ranges (fixed in 83.0.0 and in 84.1.0) release 84.1.0 or later is outside both; I did not query each of those releases individually. Raising the bound would also remove `pkg_resources` (setuptools 82), which the **project** environment's `tensorboard` imports; the disposable environment contains no `tensorboard`. **Owner decision (not made here):** accept the two advisories as inapplicable to this disposable environment and its pip-only installs, or amend the condition for disposable environments only (for example `setuptools>=84.1.0`) before any further install. The project environment is not involved either way.

Other advisory notes (carried from section K, unchanged today): the `torch` records with no fixed version describe operators this repository does not call; `trust_remote_code=False` does not mitigate CVE-2026-4372, which is fixed in 5.3.0 and so out of range for 5.12.1; pip 24.0 in the venv vendors its own `certifi` bundle (its version was not read; any copy older than 2026.10.18 is inside the affected range of GHSA-6q48-6c7w-9gw2), which is why the hash checks above matter. The project's own `certifi 2026.7.22` and `pip 26.2.1` were not touched.

### L.6 Python 3.11, Windows CPU wheel, CPU-only and CUDA findings (VERIFIED FACT)

- **Python 3.11 / Windows:** all 35 wheels installed on CPython 3.11.9 win_amd64: `torch-2.13.0-cp311-cp311-win_amd64.whl`, `tokenizers-0.22.1-cp39-abi3-win_amd64.whl`, `safetensors-0.6.2-cp38-abi3-win_amd64.whl`, `transformers-5.12.1-py3-none-any.whl`, `hf_xet-1.7.0-cp38-abi3-win_amd64.whl`, `numpy-1.26.4-cp311-cp311-win_amd64.whl`, `MarkupSafe`, `PyYAML`, `regex` as `cp311-win_amd64`, the rest pure Python.
- **Imports:** `torch 2.13.0+cpu`, `transformers 5.12.1`, `tokenizers 0.22.1`, `safetensors 0.6.2`, `huggingface_hub 1.33.0`, `numpy 1.26.4`, all loaded from the venv. Working set: 20.8 MB at process start, 199.6 MB after `import torch`, 225.1 MB after all four imports, 314.2 MB at the end of the smoke test.
- **CPU-only:** `torch.__version__` carries the local tag **`+cpu`**; `torch.version.cuda is None`; `torch.version.hip is None`; `torch.cuda.is_available()` is `False`, `device_count()` is 0; the build settings string reports `USE_CUDA=0, USE_CUDNN=OFF, USE_ROCM=OFF, USE_NCCL=OFF, USE_XPU=OFF`, `USE_MKL=ON`, `USE_MKLDNN=ON`, `USE_OPENMP=ON`; CPU capability AVX512; 4 threads. `torch/lib` holds nine DLLs (`c10`, `libiomp5md`, `libiompstubs5md`, `shm`, `torch`, `torch_cpu`, `torch_global_deps`, `torch_python`, `uv`), none named for CUDA or NVIDIA.
- **No CUDA / NVIDIA dependency on the Windows wheel:** 7 `cuda-*`, `nvidia-*` and `triton` requirements are declared in the metadata, all with `platform_system == "Linux"` markers; **none is active on Windows**, and no such distribution is installed.
- **Smoke test, no model:** CPU tensor arithmetic correct (`[[1,2],[3,4]] @ itself = [[7,10],[15,22]]`); a `tokenizers` WordLevel tokenizer built from an in-memory vocabulary on the fixed synthetic string "alpha beta epsilon gamma" gives ids `[1, 2, 0, 3]` (unknown word to `[UNK]`) and truncation to 2 tokens works; a safetensors file written and read back is bit-identical (120 bytes, header metadata `{"format": "pt"}`); the `torch` to `numpy` bridge works in both directions with numpy 1.26.4, and `safetensors.numpy` round-trips, with no warnings.

### L.7 Static findings on the installed transformers 5.12.1 (PRELIMINARY APPLICABILITY ASSESSMENT; installed library source read, nothing executed)

These bear on the two existing call sites (section K.7) and on questions N5 and N6 there. No model was built, so none of this is a runtime test.

- All five names the code imports exist: `AutoModelForSequenceClassification`, `AutoTokenizer`, `PreTrainedModel`, `get_linear_schedule_with_warmup(optimizer, num_warmup_steps, num_training_steps, last_epoch)` and `set_seed(seed, deterministic)`. The two calls in the training script match those signatures.
- `PreTrainedModel.from_pretrained` has explicit parameters `ignore_mismatched_sizes` (default `False`), `local_files_only` (`False`), `revision` (`'main'`, so a commit hash can be pinned), `use_safetensors` (`None`) and a new `weights_only` (**default `True`**); `trust_remote_code` is read from `**kwargs`; `AutoModelForSequenceClassification.from_pretrained(*model_args, **kwargs)` and `AutoTokenizer.from_pretrained(name, *inputs, **kwargs)` forward keywords. `num_labels`, `id2label`, `label2id` are not explicit parameters: they travel in `**kwargs` to the configuration class (`config_class.from_pretrained(..., return_unused_kwargs=True, **kwargs)`), as before.
- **`use_safetensors=True` with a local directory that holds only a pickle checkpoint raises `OSError("Error no file named model.safetensors found in directory ...")`** (the directory branch of `modeling_utils.py`), so the runtime loader's refusal of pickle weights is preserved in 5.12.1.
- **`save_pretrained(..., safe_serialization=True)` (training script line 155):** the keyword is not a parameter, appears nowhere in `modeling_utils.py` or `tokenization_utils_base.py`, and `**kwargs` are consumed only inside the `push_to_hub` branch, so with `push_to_hub=False` the keyword is **silently ignored** and weights are written as safetensors regardless (`metadata["format"] = "pt"`). The official migration guide says the parameter was removed; the call should be changed, but it would not crash.
- **Hub branch (training path):** when a repository has no safetensors file and `use_safetensors` is not forced, the loader falls back to the pickle file, read with `torch.load(weights_only=True)` by default; when it loads a pickle file online it may also **start a background thread that asks the Hub to convert the checkpoint** (`auto_conversion`), unless offline mode or `DISABLE_SAFETENSORS_CONVERSION` is set. That is an extra network action in the training path, to be controlled in a later approved code change.

### L.8 TensorFlow + PyTorch coexistence (VERIFIED FACT)

Four separate processes, each running one tiny matrix product in each framework; the other environment's `site-packages` was appended to `sys.path` (it never shadows the running one); nothing is written to either environment. Project TensorFlow: 2.17.0 with Keras 3.15.1, numpy 1.26.4 in both environments.

| Run | Interpreter | Order | Result | Working set after first / second framework |
| --- | --- | --- | --- | --- |
| A1 | disposable venv + project packages appended | `torch` then TensorFlow | pass: `torch` 2.13.0+cpu sum 27.0, TensorFlow 2.17.0 sum 54.0, no GPU, no errors, no warnings | 201 MB / 520 MB |
| A2 | disposable venv + project packages appended | TensorFlow then `torch` | pass, same values | 365 MB / 522 MB |
| B1 | project `.venv` + disposable packages appended | `torch` then TensorFlow | pass, same values | 201 MB / 530 MB |
| B2 | project `.venv` + disposable packages appended | TensorFlow then `torch` | pass, same values | 375 MB / 532 MB |

No import-order, DLL (`libiomp5md.dll` is bundled with `torch`) or numpy conflict appeared. Limits: this is import plus one operation, not a workload; it used appended paths rather than one environment holding both; `import tensorflow` did not import `tensorboard.default` in these runs, so whether `setuptools<82` is needed in the **project** environment (N6) is still UNRESOLVED.

### L.9 Safeguards and what stayed unchanged (VERIFIED FACT)

Checked after the run: no file under `backend/`, `training/`, `tests/`, `config/`, `scripts/`, `docs/` (except `docs/MEMORY.md`), `models/`, `datasets/` or `reports/` (except the two reports) changed; `backend/pyproject.toml`, `.env.example` and `pytest.ini` unchanged; **no file in the project `.venv` changed**, and it still has no `torch`, `transformers`, `tokenizers` or `safetensors` (`setuptools 65.5.0`, `certifi 2026.7.22`, `pip 26.2.1`, TensorFlow 2.17.0, Keras 3.15.1, numpy 1.26.4); `models/sentiment` and `datasets/raw/sentiment` do not exist; `user_text_rules_v1` is active, `SENTIMENT_MODEL_ENABLED=false`, sentiment cannot affect risk, goals, portfolio, recommendations, compliance or any financial calculation; no raw user text was used, logged, stored, cached or sent (the only strings processed were fixed synthetic words); no intensity regression.

### L.10 Cleanup and reproduction

The venv `C:\Users\Administrator\.copilot\sentiment-compatibility-venv`, the 35 downloaded wheels (about 163 MiB on disk) and the scratch pip cache were deleted after the results were recorded. To reproduce: create a Python 3.11 venv at the same path, then `pip install --no-index --find-links <folder with the 35 wheels> --only-binary=:all: --no-deps --require-hashes -r pins_s1.txt`, where `pins_s1.txt` is the table above in `name==version --hash=sha256:<digest>` form; the wheels can be re-fetched with `pip download --require-hashes` from the same list.

### L.11 Blocked items and unresolved questions after this phase

| Id | Status |
| --- | --- |
| N1 `torch` with numpy 1.26.4 | **Closed for import, tensor operations and the numpy bridge** (L.6); a model workload remains unrun |
| N2 licence files shipped | **Closed:** all 107 declared files ship in the Windows wheel (L.4) |
| N5 transformers 5.x keywords | **Partly answered by static reading (L.7)**; runtime behaviour of `from_pretrained`, `save_pretrained` and the offline tokenizer load needs a stand-in model, which A2 excluded; UNRESOLVED |
| N6 `setuptools<82` for the project environment | UNRESOLVED |
| setuptools advisories (L.5) | **Owner decision needed** (accept as inapplicable or amend the bound for disposable environments) |
| N3, N4, N7, N8, N9, N10 | unchanged from section K |
| Project `certifi` / `pip` advisory | untouched; own task before any Hugging Face download |
| R6 to R14 | UNRESOLVED; no weight, tokenizer or dataset step is possible |

## M. Stand-in compatibility test of set S1 under transformers 5.12.1 — 2026-10-27 (sixth brief): 19 of 19 checks passed; no current call site failed; no code change is required to run; recommended changes are listed and NOT applied

Written for the project owner. Decisions recorded before anything was created (approval record, "Decisions recorded 2026-10-27 (sixth brief)"): `setuptools==81.0.0` accepted for the disposable Windows pip-only environment; **GHSA-h35f-9h28-mq5c** (= CVE-2026-59890 = PYSEC-2026-3447) **and GHSA-xmj3-9gf7-h52w** accepted as **residual risks for this isolated environment only** (the brief wrote the second id as "GHSA-xmj3-9gf7-h52"; the advisory id is GHSA-xmj3-9gf7-h52w), on the documented scope: Windows CPython 3.11 venv, pip wheel installation only, no source distributions, no macOS execution, no legacy egg installation, environment deleted after testing. This is a risk acceptance, not a statement that either advisory is fixed or irrelevant elsewhere. Unchanged: A1 REJECTED; A2 APPROVED only for S1 isolated verification; R6 to R14 UNRESOLVED; `user_text_rules_v1` active; `SENTIMENT_MODEL_ENABLED=false`; intensity regression deferred. One additional isolated stand-in test was authorised; this section holds its evidence. Labels: VERIFIED FACT (observed in this test), VERIFIED FROM OFFICIAL SOURCE, PRELIMINARY APPLICABILITY ASSESSMENT, CANDIDATE PROPOSAL, UNRESOLVED.

### M.1 Environment and wheel set (VERIFIED FACT)

A new disposable venv at `C:\Users\Administrator\.copilot\sentiment-compatibility-venv` (Python 3.11.9, pip 24.0). Install-day re-check on the recorded resolution: 35 packages, 0 hash mismatches, 0 yanked, OSV and PyPI vulnerability records only for `setuptools 81.0.0` (the two accepted advisories). **The hash-pinned list is byte-identical to the first run's** (`diff` of the 35-package `--require-hashes` file: identical), so every digest in the table of section L applies. Wheels were fetched with `pip download --only-binary=:all: --no-deps --require-hashes`, hashed again independently (35 of 35 equal to the pinned list, pip's report and PyPI), and installed with `pip install --no-index --find-links <wheels> --only-binary=:all: --no-deps --require-hashes`; `pip check`: "No broken requirements found". Pins that were required, with their SHA-256:

| Package | Wheel | Size | SHA-256 |
| --- | --- | --- | --- |
| `torch==2.13.0` | `torch-2.13.0-cp311-cp311-win_amd64.whl` | 122.0 MB | `a0d8b11f16a48d60e2015d8213aa0390744cbebb98e58b62b3514dddc656e330` |
| `transformers==5.12.1` | `transformers-5.12.1-py3-none-any.whl` | 11.2 MB | `2a5e109d2021265df7098ffbb738295acaf5ad256f12cbc586db2ea4dcbb1a8a` |
| `tokenizers==0.22.1` | `tokenizers-0.22.1-cp39-abi3-win_amd64.whl` | 2.7 MB | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` |
| `safetensors==0.6.2` | `safetensors-0.6.2-cp38-abi3-win_amd64.whl` | 0.3 MB | `c7b214870df923cbc1593c3faee16bec59ea462758699bd3fee399d00aac072c` |
| `setuptools==81.0.0` | `setuptools-81.0.0-py3-none-any.whl` | 1.1 MB | `fdd925d5c5d9f62e4b74b30d6dd7828ce236fd6ed998a08d81de62ce5a6310d6` |
| `numpy==1.26.4` | `numpy-1.26.4-cp311-cp311-win_amd64.whl` | 15.8 MB | `cd25bcecc4974d09257ffcd1f098ee778f7834c3ad767fe5db785be9a4aa9cb2` |

### M.2 What the test is (VERIFIED FACT)

One script (`standin_test.py`, in the session scratchpad, outside the repository), run by the venv's interpreter with the repository only **read** (modules imported with bytecode writing off; no file under `backend/`, `training/`, `tests/`, `config/`, `scripts/`, `models/`, `datasets/` or the manifests changed, and no `.pyc` appeared). It uses **the real project code**: `TransformersBackend`, `verify_artifact`, `load_model`, `TrainedSentimentModel` (`backend/wealthpilot/core/sentiment_model.py`), `write_artifact` (`training/sentiment/artifacts.py`) and the **real `fine_tune_with_torch`** (`training/sentiment/train_sentiment_transformer.py`) called with **`epochs=0`, so no optimiser step is taken**; only the in-memory `CANDIDATES["finbert"]["hub_id"]` entry is pointed at a local directory.

Guards built in before any other import: every `socket` connect, `connect_ex`, `create_connection`, `getaddrinfo` is refused and recorded (with a positive control that proves the guard fires); `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` and a scratch `HF_HOME`; `hf_hub_download`, `snapshot_download` and `try_to_load_from_cache` replaced by recorders that refuse; `torch.load` replaced by a recorder that refuses; `pickle.load` / `loads` recorded. Inputs: a random-initialised tiny BERT classifier (4,035 parameters, seed 42, 3 labels in the project's order `positive, negative, neutral`), fixed synthetic token ids `[2, 5, 6, 7, 3]`, synthetic words from a 25-token local vocabulary; nothing is downloaded and nothing comes from the project. Two small side probes ran in their own processes (M.5).

### M.3 Results (19 checks)

| Check | Result and evidence |
| --- | --- |
| T01 environment, offline switches, guard control | PASS. `torch 2.13.0+cpu`, `transformers 5.12.1`, `tokenizers 0.22.1`, `safetensors 0.6.2`, `huggingface_hub 1.33.0`, `numpy 1.26.4`, all from the venv; offline mode on; **zero network attempts during imports**; the control attempt was refused and recorded, then cleared |
| T02 tokenizer fixture, legacy BERT layout | PASS. Hand-written directory with `vocab.txt`, `tokenizer_config.json`, `special_tokens_map.json` (the layout of a downloaded BERT-style base model) loads through `AutoTokenizer.from_pretrained(dir, local_files_only=True, trust_remote_code=False)` as `BertTokenizer` with 25 tokens |
| T02b tokenizer fixture, `tokenizers` WordPiece to `PreTrainedTokenizerFast` | PASS. Saved as `tokenizer.json` + `tokenizer_config.json`, reloaded (class `TokenizersBackend`), 25 tokens, ids `[5, 6, 7]` |
| T02c informational: 4.x `BertTokenizer(vocab_file=...)` | **Finding.** The `vocab_file` argument is accepted through `**kwargs` and **ignored**: the tokenizer silently has only the 5 special tokens (`[2, 1, 1, 1, 3]` for "alpha beta gamma"). Not used at any project call site; it is a trap for anyone building a tokenizer directly. My own first fixture fell into it, which is why the first run's tokenizer check was rebuilt with exact-id assertions |
| T03 current tokenizer-loading path | PASS. Exact ids `[2, 5, 6, 1, 7, 3]` for "alpha beta unknownword gamma" (unknown word to `[UNK]`), truncation to `max_length=4` gives 4 tokens, keys `attention_mask`, `input_ids`, `token_type_ids`, `return_tensors="pt"` works; `save_pretrained` writes `tokenizer.json` + `tokenizer_config.json` and the **reloaded tokenizer has the same 25 tokens and identical ids** |
| T04 stand-in model saved with `save_pretrained` | PASS. Files: `config.json`, `model.safetensors` only (18,700 bytes, 25 tensors, header metadata `{"format": "pt"}`); no `.bin`, `.pt`, `.pth`, `.pt2`, `.pkl` |
| T05 loader's exact model call | PASS. `AutoModelForSequenceClassification.from_pretrained(dir, local_files_only=True, trust_remote_code=False, use_safetensors=True)` returns `BertForSequenceClassification` on CPU, `id2label` `{0: positive, 1: negative, 2: neutral}`, attention implementation `sdpa`; `torch.load` calls: 0 |
| T06 one CPU forward pass | PASS. Input ids `[[2, 5, 6, 7, 3]]`; logits shape `(1, 3)`, all finite (`[9.6e-05, 0.00139, 0.002762]`), identical on a repeat, and equal (`atol=1e-6`) to the in-memory model the file was saved from, so the safetensors round trip is exact; output type `SequenceClassifierOutput` |
| T07a `use_safetensors=True` on a pickle-only directory | PASS. `OSError: Error no file named model.safetensors found in directory ...`; the placeholder `pytorch_model.bin` (bytes "NOT-A-CHECKPOINT-PLACEHOLDER", not a serialized pickle) was never read; `torch.load` calls: 0 |
| T07b safetensors beside a placeholder `.bin` | PASS. Loads from safetensors; `torch.load` calls: 0 |
| T07c `trust_remote_code=False`, custom model code | PASS. A local `config.json` with `auto_map` pointing at a module that writes a marker file: loaded the **native** class, `auto_map` ignored, **marker not created**, nothing copied into the Hugging Face modules cache |
| T07d `trust_remote_code=False`, custom tokenizer code | PASS. Native `BertTokenizer` loaded, `auto_map` ignored, marker not created |
| T07e CVE-2026-4372 mechanism defanged | PASS. A local `config.json` carrying `_attn_implementation_internal: "synthetic-attacker/synthetic-kernel"` loads normally; the key is **not applied** (`_attn_implementation` stays `sdpa`); **0 network attempts, 0 hub-level calls**; the `kernels` package is not installed. This is the behaviour the 5.3.0 fix describes; it does not prove the fix complete |
| T07f placeholders named `.pt`, `.pth`, `.pt2` | PASS. A directory holding only `model.pt`, `model.pth`, `model.pt2`, `pytorch_model.pt`, `pytorch_model.pt2` placeholders is refused (`OSError`, no `model.safetensors`); `torch.load` calls: 0 |
| T09 the real `fine_tune_with_torch`, `epochs=0` | PASS. Every call in the function ran unchanged against a local base directory (tiny random masked-LM + the legacy-layout tokenizer): `transformers.set_seed`, `AutoTokenizer.from_pretrained(hub_id)`, `AutoModelForSequenceClassification.from_pretrained(hub_id, num_labels=3, id2label=..., label2id=..., ignore_mismatched_sizes=True)` (load report: `classifier.*` and `bert.pooler.*` newly initialised, `cls.predictions.*` unexpected), `AdamW` and `get_linear_schedule_with_warmup` construction, **`model.save_pretrained(directory, safe_serialization=True)`**, `tokenizer.save_pretrained(directory)`, and the two batched logit passes. Output files: `config.json`, `model.safetensors`, `tokenizer.json`, `tokenizer_config.json` (**no `generation_config.json`**, consistent with the migration guide); validation and test logits shape `(2, 3)`, finite; library versions recorded; **the tokenizer it wrote reloads with the same 25 tokens and identical ids**; 0 optimiser steps; 0 network attempts |
| T09b real artifact writer and loader | PASS. `write_artifact` (which calls `verify_artifact`) accepts the output as unvalidated and uncalibrated; labels in logit order `positive, negative, neutral`; `TransformersBackend.predict` returns three finite logits using the real vocabulary (`[2, 5, 6, 7, 3]`); `TrainedSentimentModel.interpret` returns a reading with `validation_status: unvalidated`; **`load_model` refuses the stand-in as `not_validated`** (an unvalidated model is never primary); `verify_artifact` on an artifact without `model.safetensors` (a placeholder `.bin` beside it) is refused as `artifact_incompatible`; `TransformersBackend` on a pickle-only directory is refused as `load_failed`. **Observation:** `verify_artifact` also accepts an artifact whose tokenizer has silently lost its vocabulary (5 tokens loaded, `config.vocab_size` 25), because its vocabulary check compares two numbers that both come from `config.json` |
| T10 obsolete `save_pretrained(safe_serialization=...)` | PASS. `save_pretrained` with no keyword, with `safe_serialization=True` and with `safe_serialization=False` all complete without error or warning and write **byte-identical `model.safetensors`** (SHA-256 `675894c0...e1e2` for all three): the keyword is accepted silently and has no effect, and `False` no longer produces a pickle checkpoint |
| T11 static call sites (AST) | PASS. Loader `sentiment_model.py:258` `AutoTokenizer.from_pretrained` with `local_files_only`, `trust_remote_code`; `:259` `AutoModelForSequenceClassification.from_pretrained` with `local_files_only`, `trust_remote_code`, `use_safetensors`. Training `train_sentiment_transformer.py:120` `transformers.set_seed`; `:122` `AutoTokenizer.from_pretrained` (no keywords); `:123` `from_pretrained` with `id2label`, `ignore_mismatched_sizes`, `label2id`, `num_labels`; `:141` `get_linear_schedule_with_warmup`; `:155` `model.save_pretrained(..., safe_serialization=True)`; `:156` `tokenizer.save_pretrained`. The test exercised exactly these keywords |
| T12 final safety | PASS. Network attempts recorded by the guard: **0**; hub-level calls: **0**; `torch.load` calls: **0**; `pickle.load` / `loads` calls: none; scratch `HF_HOME` entries: **none**; `~/.cache/huggingface` exists: **no**; serialized pickle or zip files created: **0** (the only files with checkpoint-style names are the three `pytorch_model.bin` placeholders, plus the `.pt` / `.pt2` names of T07f, none with pickle or zip magic bytes) |

Forward passes run, all on random-initialised stand-ins and synthetic inputs: 3 in T06, 2 batched passes inside the real training function (validation and test rows), 2 in T09b (`predict` and `interpret`). No training step, no real inference.

### M.4 Loader and 5.x call-site conclusions

- **Runtime loader (`sentiment_model.py:258-259`): works under transformers 5.12.1 without change.** All three keywords are honoured as intended (M.5), pickle-style weights are refused, and the real `TransformersBackend`, `verify_artifact` and `load_model` behave as designed against a locally generated stand-in. VERIFIED FACT.
- **Training seam (`train_sentiment_transformer.py:116-158`): runs without error under 5.12.1** with every call as written, including the obsolete keyword; the artifacts it writes pass the project's own verifier and the tokenizer round-trips. VERIFIED FACT (with `epochs=0`, a local base, 25-token vocabulary and tiny model; a real base model, a real download and a real training loop were not run).
- **No current call site failed, so the stop condition did not trigger and nothing was rewritten.**

### M.5 Network, cache and keyword-effect probes

| Probe | Result |
| --- | --- |
| Main run, network | 0 refused attempts across imports and all 19 checks (VERIFIED FACT) |
| Main run, Hugging Face cache | 0 hub-level calls, scratch `HF_HOME` empty, user cache absent (VERIFIED FACT) |
| `local_files_only=True` (separate process, hub functions intercepted, no network, no cache) | With a synthetic repository id, the hub layer receives `local_files_only=True` for both `AutoModelForSequenceClassification` and `AutoTokenizer`, against `False` in the control; 0 real network attempts; scratch cache empty. The flag is forwarded and means cache-only resolution: for a non-directory id the library still **consults the local Hugging Face cache** (`try_to_load_from_cache`), which a plain directory path never does (0 such calls in the main run). Because `resolve_artifact_directory` only returns an existing directory inside `models/sentiment/`, the runtime loader never reaches that branch (PRELIMINARY ASSESSMENT) |
| `trust_remote_code` control (separate process, its own scratch cache) | `trust_remote_code=False`: native class loaded, marker not created. `trust_remote_code=True` on a harmless locally authored module: it **executed** (marker created) and the library **copied the module into the Hugging Face modules cache** (`modules/transformers_modules/...`). So the marker test can detect execution, and `True` writes to the cache while `False` does not |

### M.6 Required and recommended code changes — NOT applied; each needs a separate approval

No change is **required** for the two existing call sites to work under 5.12.1. The smallest changes the evidence points to (CANDIDATE PROPOSALS):

1. **`training/sentiment/train_sentiment_transformer.py:155`**: `model.save_pretrained(directory, safe_serialization=True)` to `model.save_pretrained(directory)`. Behaviour is byte-identical under 5.12.1 (T10); the keyword is removed in 5.x per the official migration guide and is a dead argument that would mislead a reader into thinking `False` selects another format. Optional but recommended.
2. **Tokenizer integrity (the observation in T09b):** record the tokenizer's real size, `len(tokenizer)`, as its own metadata field in `training/sentiment/artifacts.py` / `train_sentiment_transformer.py` (today `vocab_size` is `model.config.vocab_size`, the same number the loader compares it with), and compare it with `len(self._tokenizer)` after loading in `TransformersBackend.__init__` (`sentiment_model.py` after line 259), raising `ModelUnavailable("artifact_incompatible")` on a mismatch. Do **not** require `len(tokenizer) == config.vocab_size`: some pretrained models pad the embedding matrix beyond the tokenizer, so an equality test against the config would reject valid models. Recommended: a tokenizer that loads with 5 tokens would otherwise pass every existing check.
3. **Training loader hardening, together with R6 / R7:** pass `use_safetensors=True` and a pinned `revision=<40-character commit>` to the two `from_pretrained(hub_id, ...)` calls (lines 122-123), and set `DISABLE_SAFETENSORS_CONVERSION=1` (or run offline after the approved download) so the Hub conversion thread described in section L.7 cannot start. Not exercised here (no Hub access).
4. **`training/sentiment/README.md`**: replace the statement that the v4 line is the long-term-support branch (no 4.x release is free of advisories, section J) and the "not exercised" wording once the change is approved.
5. **Tests:** `tests/training/sentiment` uses a fake trainer, so no existing test covers any of the above. A test module could reuse `standin_test.py`'s stand-in approach behind `pytest.importorskip("torch")`; it would not run in the project environment, which has none of the four packages.

### M.7 Other observations (VERIFIED FACT unless marked)

- Loading a legacy `vocab.txt` BERT directory with `tokenizers 0.22.1` emits `DeprecationWarning: Deprecated in 0.9.0: WordPiece.__init__ will not create from files anymore, try WordPiece.from_file instead`. It works now; a newer `tokenizers` could remove the path (relevant to S4, not to S1). PRELIMINARY.
- `from_pretrained` has the explicit parameter `weights_only` (default `True`), so pickle fallbacks, where they exist (training path, hub branch), are read with `torch.load(weights_only=True)`.
- The stand-in did not exercise `ignore_mismatched_sizes=True` against a real **size mismatch** (the base had no classification head, which is the missing-head case); UNRESOLVED, and only relevant for a base with a different head size.

### M.8 Status of earlier unresolved questions

| Id | Status after this test |
| --- | --- |
| N5 transformers 5.x keywords and tokenizer behaviour | **Closed for the two call sites on a local stand-in:** `local_files_only`, `trust_remote_code`, `use_safetensors`, `num_labels` / `id2label` / `label2id`, `ignore_mismatched_sizes` (missing-head case), `set_seed`, the scheduler, `save_pretrained` with the obsolete keyword, tokenizer load and save with a legacy layout all work. Not covered: a real Hub download, a real base model, a real size mismatch, a real training loop |
| N6 `setuptools<82` needed in the project environment | UNRESOLVED (not tested here) |
| setuptools advisories | accepted as residual risk for the isolated environment only (above); open elsewhere |
| N3, N4, N7 to N10, project `certifi` / `pip`, R6 to R14 | unchanged |

### M.9 Cleanup and reproduction

The venv, the 35 wheels (about 163 MiB), the scratch pip cache and the scratch work directories (which held the stand-in models, tokenizers, placeholders and marker files) were deleted after the results were recorded. To reproduce: create a Python 3.11 venv, fetch the 35 wheels with `pip download --only-binary=:all: --no-deps --require-hashes -r pins_s1.txt`, install with `pip install --no-index --find-links <wheels> --only-binary=:all: --no-deps --require-hashes -r pins_s1.txt` (the pin list is the table in section L), then run the scripts, which exist only in the session scratchpad. If the owner wants them kept, they would need to be added to the repository under a separate approval.

### M.10 Status update 2026-10-27 (seventh brief): the recommended changes of M.6 were approved and applied

Items 1 and 2 of M.6 (drop the obsolete `safe_serialization` argument; record and compare the real tokenizer length) and the safe-loading parameters of item 3 (an immutable caller-supplied `revision`, `use_safetensors=True`, `trust_remote_code=False`, offline by default) are now in the code and tested (`reports/sentiment_model_approval_record.md`, "Integration hardening results (seventh brief)"; `training/sentiment/README.md`). Item 3's Hub-conversion switch stays a documented blocker: `DISABLE_SAFETENSORS_CONVERSION` appears once in the installed library's code and in no documentation, so it is not used. Item 4 (README) is done. Item 5 (tests) is done: 113 new tests, 32 of which need the packages and ran in a disposable environment. The base-model revision is still not recorded in the artifact metadata (open decision). Nothing in this status changes A1, A2, R6 to R14 or the state of the Transformer (disabled).

### N. Disposable S1 regression check, 2026-10-28 (tenth brief): 381 passed, 1 skipped

The disposable environment was recreated from the unchanged 35-package hash-pinned list of section L (the pin list was byte-identical to the first isolated run's; the wheels were fetched with `pip download --only-binary=:all: --no-deps --require-hashes`, all 35 files re-hashed independently, 170.3 MB, installed offline with `--require-hashes`, `pip check` clean; `torch==2.13.0`, `transformers==5.12.1`, `tokenizers==0.22.1`, `safetensors==0.6.2`, `setuptools==81.0.0`, `numpy==1.26.4`, `certifi==2026.10.23` as installed). The updated library-dependent stand-in tests (34) and the related seam (62), artifact-provenance (184), tokenizer-integrity (60) and loader-guard (41, 1 skipped) tests all passed offline under guards that refused sockets, hub-level calls, `torch.load` and pickle (0 recorded) with an unchanged Hugging Face cache. The environment, wheels and caches were deleted afterwards; the project environment and the repository (apart from the approval record) are unchanged. Details and the requirement-by-requirement evidence: `reports/sentiment_model_approval_record.md`, "Disposable S1 regression check results (tenth brief)". This closes the one limit of the ninth brief; sections J to M are otherwise unchanged.

### O. R6 / R7 candidate register update, 2026-10-28 (eleventh brief): nothing decided, nothing accessed

The candidate register of section C (A = `ProsusAI/finbert`, C = `FacebookAI/roberta-base`) gains one recorded item and no verification: the full 40-character revision of A that the owner-approved metadata read of 2026-10-20 recorded (`0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`, `reports/phaseB2S2_SENTIMENT_COMPLETION_REPORT.md` section 6) is **RECORDED, NOT APPROVED**; it is not re-verified and the licence statements remain model-card claims. Column C remains UNRESOLVED in every row; `roberta-base` has no sentiment head, and the expected-compatibility note is that RoBERTa uses a byte-level BPE tokenizer for which the stand-in tests hold no fixture. Candidate B is unchanged. The full item-by-item matrix, the owner decision fields P1 to P11 and the sources are in `reports/sentiment_model_approval_record.md`, "R6 / R7 approval preparation (eleventh brief)". No Hugging Face page, API or file was queried; no weight, tokenizer or dataset was accessed; no package was installed. D3 to D6 of section G remain UNRESOLVED.

### P. R6 / R7 selection phase, 2026-10-28 (twelfth brief): no selection supplied; nothing decided, nothing accessed

The brief defined the choices (R6: approve / reject / keep unresolved; R7: `FacebookAI/roberta-base`, `cardiffnlp/twitter-roberta-base-sentiment-latest`, `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis`, or unresolved) but supplied no selection and no accept / reject value, so no decision was recorded: **R6 UNRESOLVED, R7 UNRESOLVED, no candidate selected or rejected.** The candidate register of section C is extended by one fact, from the earlier record: the revision of the `mrm8488` model read on 2026-10-20 is `ae0eab9ad336d7d548e0efe394b07c04bcaf6e91` (RECORDED, not approved); candidate B (`cardiffnlp`) has no revision on record and its licence tag comes from a single secondary snapshot. The completed form (R6-0 to R6-9, the three-way R7 matrix, fields F1 to F14, and the approvals required before a metadata query and before a download) is in `reports/sentiment_model_approval_record.md`, "R6 / R7 selection phase (twelfth brief)". No licence, tokenizer licence, training-data permission, revision, file list, download host or commercial-use conclusion was invented; where the record is empty the form says so. D3 to D6 of section G remain UNRESOLVED. No Hugging Face access, download, dataset access or installation took place.

### Q. R6 / R7 decision form resolved conservatively, 2026-10-28 (thirteenth brief): nothing approved, nothing rejected, nothing accessed

The owner's thirteenth brief fixed the form of section P at: R6-0 to R6-9 KEEP UNRESOLVED; R7 KEEP UNRESOLVED; R7-A (`FacebookAI/roberta-base`), R7-B (`cardiffnlp/twitter-roberta-base-sentiment-latest`) and R7-C (`mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis`) NOT SELECTED; F1 to F14 KEEP UNRESOLVED for every candidate; R8 to R14 KEEP UNRESOLVED; D10 to D13 remain BLOCKED. The reason recorded is that the evidence is insufficient to accept a model licence, a training-data licence, a tokenizer licence, a commercial-use position, an exact revision, a permitted-file list or a download boundary, and that no candidate is approved until these are resolved from authoritative sources. The candidate register of section C is therefore unchanged: every revision in it is a proposal (FinBERT `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`, `mrm8488` `ae0eab9ad336d7d548e0efe394b07c04bcaf6e91`), every licence is a model-card claim, and D3 to D6 of section G remain UNRESOLVED. No metadata-only query is authorised (no parameter of one was given), and any future query approval authorises no file download, tokenizer access, weight access or dataset access. The completed form, the inputs that would reopen it, and the explicit-versus-unresolved split are in `reports/sentiment_model_approval_record.md`, "Decision recorded 2026-10-28 (thirteenth brief)". No Hugging Face access, model, tokenizer, revision, dataset or user text was accessed, and no package was installed.

### R. Sentiment phase completion, 2026-10-28 (fourteenth brief): no change to the dependency position

No package was installed, resolved or queried, and no dependency manifest changed. The S1 position of sections I to N is unchanged (hash-pinned set approved for isolated verification only; installation in a training environment is D12, the project `certifi` / `pip` advisory is D13, both BLOCKED). The library-dependent stand-in tests were not re-run because the only change in the phase (hypothetical and conditional statements in the rules baseline) touches no file they import and a re-run needs the pinned wheels fetched again, outside the 2026-10-28 approval; the 381-passed result of section N still describes the seam. Rollback plan for any future installation, as already recorded: delete the dedicated environment and its caches; nothing is added to the project environment, the lock files or the database. Full phase record and activation-gate table: `reports/sentiment_model_approval_record.md`, "Sentiment phase completion (fourteenth brief)".


### S. Execution of the approved S1 retrieval and disposable validation, 2026-10-29: 35 of 35 wheels verified; environment validated and deleted

Written for the project owner. Under the owner's execution brief (recorded before any action): the exact 35-wheel list of section L.3 (`setuptools==81.0.0`, `certifi==2026.10.23`) was retrieved from PyPI, every filename, version and SHA-256 was verified independently, the disposable environment was created and validated, then deleted. **Nothing was changed in the project environment** (TASK-CERT-1 stopped before any change: the approved lock holds no `pip` wheel).

- **Retrieval (VERIFIED FACT).** The base Python 3.11.9 interpreter's `pip` 24.0 (not the project environment): `pip download --isolated --no-cache-dir --only-binary=:all: --no-deps --require-hashes -r <the 35 pins> -d <wheel directory>`; anonymous HTTPS; hosts seen in the verbose log: `pypi.org` and `files.pythonhosted.org` (PyPI's own file host), nothing else; 35 files, 170,314,953 bytes, no source distribution.
- **Independent verification (VERIFIED FACT).** A separate standard-library script hashed every file and compared the filename, the version in the wheel's `METADATA` and the SHA-256 with the record: expected 35, present 35, problems 0 (table below).
- **Installation.** `python -m venv` at `C:\Users\Administrator\.copilot\wealthpilot-finbert-eval-venv`, then `pip install --isolated --no-cache-dir --no-index --find-links <wheels> --only-binary=:all: --no-deps --require-hashes`: "Successfully installed" the 35 packages (the venv's own `setuptools` 65.5.0 was replaced by 81.0.0); `pip check`: "No broken requirements found."; 36 distributions (the 35 and `pip` 24.0).
- **Checks (VERIFIED FACT).** Python 3.11.9, AMD64, Windows; `torch 2.13.0+cpu`, `transformers 5.12.1`, `tokenizers 0.22.1`, `safetensors 0.6.2`, `numpy 1.26.4`, `setuptools 81.0.0`, `certifi 2026.10.23`; `torch.version.cuda` is `None`; `torch.cuda.is_available()` is `False`; cuDNN `None`; no distribution whose name contains `nvidia`, `cuda` or `triton`; a CPU tensor operation succeeded; zero socket connection attempts during imports (a blocking guard was installed first); no Hugging Face home directory was created. TensorFlow 2.17.0 (the project's own site-packages, appended after the environment's, never first) and PyTorch import and run in both orders (`torch` then `tensorflow`, `tensorflow` then `torch`), `numpy 1.26.4` and `torch` from the disposable environment, tensor operations equal to 4.0 in both.
- **Tests inside the disposable environment.** The stand-in, seam and Path B stand-in tests: 105 passed; the wider sentiment, artifact, tokenizer, model-safety, approval and documentation groups (`tests/training/sentiment` and the matching `tests/backend/core` tests): **1124 passed, 2 skipped** (symbolic-link privilege), 0 failed; the seam and Path B stand-in tests once more after a final test was added: 72 passed. The stand-in modules install autouse guards that fail a test on any socket attempt, Hub-level call (`hf_hub_download`, `snapshot_download`, `try_to_load_from_cache`), `torch.load`, pickle call or change to the Hugging Face cache directories; none fired. No model, tokenizer, `config.json` or dataset of any real model was accessed; every model is a random local stand-in.
- **Advisories.** `setuptools` 81.0.0's two advisories (GHSA-h35f-9h28-mq5c, GHSA-xmj3-9gf7-h52w) stay accepted only for this isolated Windows pip-only environment as recorded on 2026-10-27; they were NOT re-queried today (no approved access to OSV or the advisory pages).
- **Cleanup (VERIFIED FACT).** The environment and the wheel directory were deleted; the temporary Hugging Face cache path was never created; none of `wealthpilot-finbert-eval-venv`, `wealthpilot-s1-wheels`, `wealthpilot-hf-cache` exists afterwards. Retained: this section and the sanitised logs' content.

| Package | Version | Wheel | SHA-256 (independently computed) | Result |
| --- | --- | --- | --- | --- |
| annotated-doc | 0.0.5 | `annotated_doc-0.0.5-py3-none-any.whl` | `117bac03a25ede5df5440e855b32d556049ca169ead221505badf432fed4b101` | MATCH |
| anyio | 4.15.1 | `anyio-4.15.1-py3-none-any.whl` | `6152fdbbf9a77fdec97731721bebf7c4c44f7c29b424b0065826173efc7ed101` | MATCH |
| certifi | 2026.10.23 | `certifi-2026.10.23-py3-none-any.whl` | `e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1` | MATCH |
| click | 8.5.0 | `click-8.5.0-py3-none-any.whl` | `255bc9599cf7748b4b1a446ccc735421bd08a2ae529a8b88597d3de5664ee360` | MATCH |
| colorama | 0.4.6 | `colorama-0.4.6-py2.py3-none-any.whl` | `4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6` | MATCH |
| filelock | 4.2.4 | `filelock-4.2.4-py3-none-any.whl` | `301241438c57936ef93f4243a94f2559022268bfcf9b375a9a72eb0f8db8358e` | MATCH |
| fsspec | 2026.9.0 | `fsspec-2026.9.0-py3-none-any.whl` | `8dd6e646e99ea382bd85f97a45e6b526a442d79423a7dc673f1e2756d05fcb5f` | MATCH |
| h11 | 0.16.0 | `h11-0.16.0-py3-none-any.whl` | `63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86` | MATCH |
| hf-xet | 1.7.0 | `hf_xet-1.7.0-cp38-abi3-win_amd64.whl` | `2b7bb5727889b0f2436dbaaad8fc4c3e66b8240d992716989e0c086b4278b1bc` | MATCH |
| httpcore | 1.0.9 | `httpcore-1.0.9-py3-none-any.whl` | `2d400746a40668fc9dec9810239072b40b4484b640a8c38fd654a024c7a1bf55` | MATCH |
| httpx | 0.28.1 | `httpx-0.28.1-py3-none-any.whl` | `d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad` | MATCH |
| huggingface-hub | 1.33.0 | `huggingface_hub-1.33.0-py3-none-any.whl` | `04e434b06e100eddbce9a6e817d72693a7884b10a79bd67ab48080d5c07eb899` | MATCH |
| idna | 3.20 | `idna-3.20-py3-none-any.whl` | `ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c` | MATCH |
| jinja2 | 3.1.6 | `jinja2-3.1.6-py3-none-any.whl` | `85ece4451f492d0c13c5dd7c13a64681a86afae63a5f347908daf103ce6d2f67` | MATCH |
| markdown-it-py | 4.2.0 | `markdown_it_py-4.2.0-py3-none-any.whl` | `9f7ebbcd14fe59494226453aed97c1070d83f8d24b6fc3a3bcf9a38092641c4a` | MATCH |
| markupsafe | 3.0.4 | `markupsafe-3.0.4-cp311-cp311-win_amd64.whl` | `fdb4ca07ab75ffadab4a8b135ad59cdbb3156b99310f3d565370da74a15d6bd3` | MATCH |
| mdurl | 0.1.2 | `mdurl-0.1.2-py3-none-any.whl` | `84008a41e51615a49fc9966191ff91509e3c40b939176e643fd50a5c2196b8f8` | MATCH |
| mpmath | 1.3.0 | `mpmath-1.3.0-py3-none-any.whl` | `a0b2b9fe80bbcd81a6647ff13108738cfb482d481d826cc0e02f5b35e5c88d2c` | MATCH |
| networkx | 3.6.1 | `networkx-3.6.1-py3-none-any.whl` | `d47fbf302e7d9cbbb9e2555a0d267983d2aa476bac30e90dfbe5669bd57f3762` | MATCH |
| numpy | 1.26.4 | `numpy-1.26.4-cp311-cp311-win_amd64.whl` | `cd25bcecc4974d09257ffcd1f098ee778f7834c3ad767fe5db785be9a4aa9cb2` | MATCH |
| packaging | 26.3 | `packaging-26.3-py3-none-any.whl` | `d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c` | MATCH |
| pygments | 2.21.0 | `pygments-2.21.0-py3-none-any.whl` | `2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9` | MATCH |
| pyyaml | 6.0.3 | `pyyaml-6.0.3-cp311-cp311-win_amd64.whl` | `9f3bfb4965eb874431221a3ff3fdcddc7e74e3b07799e0e84ca4a0f867d449bf` | MATCH |
| regex | 2026.9.29 | `regex-2026.9.29-cp311-cp311-win_amd64.whl` | `1043aedf5917caa861bcb25a9c11460049656bdf0017a90a309fa8f255467725` | MATCH |
| rich | 15.0.0 | `rich-15.0.0-py3-none-any.whl` | `33bd4ef74232fb73fe9279a257718407f169c09b78a87ad3d296f548e27de0bb` | MATCH |
| safetensors | 0.6.2 | `safetensors-0.6.2-cp38-abi3-win_amd64.whl` | `c7b214870df923cbc1593c3faee16bec59ea462758699bd3fee399d00aac072c` | MATCH |
| setuptools | 81.0.0 | `setuptools-81.0.0-py3-none-any.whl` | `fdd925d5c5d9f62e4b74b30d6dd7828ce236fd6ed998a08d81de62ce5a6310d6` | MATCH |
| shellingham | 1.5.4 | `shellingham-1.5.4-py2.py3-none-any.whl` | `7ecfff8f2fd72616f7481040475a65b2bf8af90a56c89140852d1120324e8686` | MATCH |
| sympy | 1.14.0 | `sympy-1.14.0-py3-none-any.whl` | `e091cc3e99d2141a0ba2847328f5479b05d94a6635cb96148ccb3f34671bd8f5` | MATCH |
| tokenizers | 0.22.1 | `tokenizers-0.22.1-cp39-abi3-win_amd64.whl` | `65fd6e3fb11ca1e78a6a93602490f134d1fdeb13bcef99389d5102ea318ed138` | MATCH |
| torch | 2.13.0 | `torch-2.13.0-cp311-cp311-win_amd64.whl` | `a0d8b11f16a48d60e2015d8213aa0390744cbebb98e58b62b3514dddc656e330` | MATCH |
| tqdm | 4.70.1 | `tqdm-4.70.1-py3-none-any.whl` | `c293e525e6fef9c20e8728fd4612df02a0aa31bb5fe91ecd93e123b1b7bffa73` | MATCH |
| transformers | 5.12.1 | `transformers-5.12.1-py3-none-any.whl` | `2a5e109d2021265df7098ffbb738295acaf5ad256f12cbc586db2ea4dcbb1a8a` | MATCH |
| typer | 0.27.3 | `typer-0.27.3-py3-none-any.whl` | `e50022f28b82a86313e54501317a1db64bf8f8d036ff8cfe5ca7e47675454aff` | MATCH |
| typing-extensions | 4.16.0 | `typing_extensions-4.16.0-py3-none-any.whl` | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` | MATCH |
