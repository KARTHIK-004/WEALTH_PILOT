# Model Card — Horizon-Labs/multilingual-sentiment-small (registered research candidate; NOT production)

Written for: the project owner, reviewers and examiners. This card describes a model the project has **verified can be loaded and run in isolation**, and states plainly what has **not** been established. No accuracy, calibration, fairness or human-validation claim is made.

## 1. Identity

| Item | Value |
|---|---|
| Repository | `Horizon-Labs/multilingual-sentiment-small` |
| Approved revision | `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` (40-character; any other revision is refused by the adapter's manifest check) |
| Weights | `model.safetensors`, sha256 `f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1` (agrees with the Hub's recorded hash and the repository's `SHA256SUMS`) |
| Architecture | `ModernBertForSequenceClassification`, base `jhu-clsp/mmBERT-small` (MIT); config in transformers-5 format (`rope_parameters`) → requires `transformers` ≥ 5 (5.17.0 verified; 4.57.1 is incompatible) |
| Labels | `0 negative, 1 neutral, 2 positive` (read from the model's own `config.json`; the adapter refuses any other label set) |
| Training length | 512 tokens (the adapter's default `max_tokens`) |
| Weight licence | Apache-2.0 (LICENSE and NOTICE present) |
| WealthPilot role slot | `general` |
| Registration | **`registered`** as the `general` RESEARCH candidate (owner's R1 decision, 2026-11-07, ADR-056; code constant in `core/sentiment/registry.py`). Not production. |
| Owner decision | May be considered for **research inference only** (ADR-054 addendum, 2026-11-04) |

## 2. Training data and labels (as disclosed by the publisher; not verified by WealthPilot)

Web-crawl snippets (FineWeb / FineWeb-2; the dataset licence ODC-BY does not cover the rights in the underlying pages) plus synthetic text written by an LLM (Qwen, Apache-2.0 declared). Labels are **soft labels produced by that LLM; there is no human annotation**. The real/synthetic split is not stated. The card's claim of "trained only on openly licensed text" cannot be verified from the repository. The owner accepted these facts for research inference only.

## 3. What has been verified (and how)

| Claim | Evidence | Status |
|---|---|---|
| Files download from the approved revision and match the recorded hashes | Stage A (isolated environment, outside the repository) | VERIFIED |
| The model loads from local safetensors files offline and produces three logits with a stable label order | Stage A smoke run; B2.1 in the project `.venv` (logits identical to Stage A) | VERIFIED (direct loading) |
| It coexists in-process with TensorFlow 2.17 / Keras 3.15 in both import orders | B2.1 after the setuptools 81.0.0 recovery (`docs/sentiment/stage_b/evidence/`) | VERIFIED |
| It loads and runs **through the application's adapter and service** | Opt-in `tests/backend/core/test_horizon_real_weights_smoke.py` (2026-11-07, R2): 9 passed on the real files; logits equal the Stage A logits to rounding; one softmax; first call incl. hashing and load 10.2 s, warm median 24.9 ms, peak working set 1285 MB (this machine) | **VERIFIED** (smoke only; `R2_APPLICATION_ADAPTER_SMOKE_TEST_REPORT.md`) |
| It is accurate, calibrated, or better than the rules baseline on personal-finance text | — | **NOT ESTABLISHED; NOT CLAIMED** |

Measured in B2.1 (OBSERVED on one Windows CPU machine, not a benchmark): load ≈ 3.3–3.6 s in-process; single-sentence inference median ≈ 24 ms; peak process memory ≈ 1.3–1.6 GB with TensorFlow also imported.

## 4. Smoke observations (Stage A, eight invented sentences) — not evidence of quality

On eight fictional sentences the model's native label agreed with the rules baseline on three (positive, negative, and a neutral one the rules mark "weak"). It labelled the mixed sentence "neutral" (rules: negative), the negation sentence "positive" (rules: uncertain, a context safeguard), the hypothetical sentence "negative" (rules: uncertain), the ambiguous statement "neutral" (rules: abstained) and a Spanish sentence "positive" (rules: abstained — non-English never reaches a model in WealthPilot). Eight sentences chosen by the project say nothing about accuracy; they are shown only to explain why the combined reading marks model-versus-rules differences and rules safeguards as **uncertain** instead of trusting the model.

## 5. Intended and prohibited use

**Intended (registered by the owner for research, 2026-11-07):** an off-by-default, display-only, clearly labelled *experimental* second reading shown beside the rules-based reading for English text a customer chose to write.

**Prohibited:** production activation without owner approval and validation evidence (F1/R14); any effect on risk, goals, portfolio, recommendations, compliance or savings-first routing; decisions about individuals; treating a score as a confidence or probability of being correct; comparing scores across models; non-English or code-mixed text (safe abstention, the model never sees it); storing, logging or transmitting the text; fine-tuning, dataset creation or labelling (D20 is rejected); describing the output as human-validated.

## 6. Known limitations

LLM-derived labels inherit the teacher's biases; weaker on sarcasm, very short or context-dependent text and negation/hypotheticals; domain mismatch (web text vs a person's statements about their own savings and debts); three classes only (`mixed`, `uncertain`, `insufficient_evidence` come from WealthPilot's rules safeguards); one uncalibrated softmax; 512-token training length; the multilingual capability is not used and is not validated for this project; no subgroup/fairness analysis exists.

## 7. Provenance of this card

Compiled from `docs/sentiment/model_licence_review.md`, ADR-054 and its addenda, `STAGE_A_COMPLETION_REPORT.md` and the B2.1 evidence. Publisher-reported benchmark figures are deliberately omitted: they are not WealthPilot evidence.
