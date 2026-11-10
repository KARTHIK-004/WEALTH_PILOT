# R1 — Horizon Registered as the `general` Research Candidate (2026-11-07)

Written for: the project owner and reviewers. Authority: the owner's R1 instruction (this session), ADR-054 addendum (research-inference approval, 2026-11-04), ADR-056 (this registration). Evidence labels: **PREVIOUSLY VERIFIED** (earlier stages), **NEWLY VERIFIED** (this run), **INFERENCE**.

## 1. Result

**VERIFIED.** `HORIZON` in `backend/wealthpilot/core/sentiment/registry.py` now has `registration = REGISTERED` (one constant). It fills the `general` role. The `financial` role has no registered candidate and is reported as `no_candidate_approved`. Production is unchanged: the method is `user_text_rules_v1`, `SENTIMENT_TRANSFORMERS_ENABLED` and `SENTIMENT_MODEL_ENABLED` remain `false`, and the status endpoint still reports `production_activation: "not_activated"`.

## 2. Exact model identity

| Item | Value | Status |
|---|---|---|
| Repository | `Horizon-Labs/multilingual-sentiment-small` | PREVIOUSLY VERIFIED (Stage A) |
| Revision | `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` | the registry constant, the manifest and the owner decision agree (NEWLY VERIFIED by tests) |
| Weight licence | Apache-2.0 (LICENSE 11,358 bytes, sha256 `cfc7749b…3d30`; NOTICE 1,566 bytes, sha256 `8dd5797f…b186`) | PREVIOUSLY VERIFIED; LICENSE/NOTICE hashes recorded first-hand in this run |
| Base model | `jhu-clsp/mmBERT-small`, MIT | PREVIOUSLY VERIFIED (review record) |
| Training data disclosure | FineWeb/FineWeb-2 web-crawl snippets plus text written by an LLM (Qwen); soft labels from that LLM; no human annotation | PREVIOUSLY VERIFIED; accepted for research only |
| Weights | `model.safetensors`, 562,584,932 bytes, sha256 `f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1` | re-hashed in this run, matches the repository `SHA256SUMS` and Stage A |
| Labels | `0 negative, 1 neutral, 2 positive` (read from `config.json`) | NEWLY VERIFIED through the adapter |
| Tokenizer | `len(tokenizer) = 256000 = config vocab_size` | NEWLY VERIFIED (offline) |

No other revision was used or downloaded.

## 3. What changed

- `registry.py`: `registration=REGISTERED`; docstring and `registration_note` state "research only, not production, not a financial-domain model, no human validation, no calibration".
- `reviews.py`: the Horizon review is `active_in_registry=True`; its `blockers` list was rewritten to the current truth (the packages are installed; production, financial-domain, accuracy, calibration and human-validation claims stay unauthorised); `HORIZON_OWNER_DECISION_CURRENT` appends the 2026-11-07 update to the original owner-decision text without altering it.
- `.gitignore`: `models/sentiment_pretrained/` is ignored, so placed weights can never be tracked by accident (the pre-existing rules covered only `models/sentiment/`).
- Tests that pinned the old "pending" state were updated deliberately (14 tests in 5 files); they now assert the registered state, the empty financial slot and that nothing is production. A hermetic fixture makes unit tests read an empty directory instead of the real model directory, so no unit test can load the real weights.
- Frontend types, fixtures and wording are covered in `SENTIMENT_TEST_REPORT.md` (regenerated where the registry state is embedded).

## 4. What registration does and does not mean

Registered = "may run when the research flag is on and its verified files exist". It does **not** mean production-runnable, validated, calibrated or suitable for financial text. A general-purpose sentiment model is not presented as a financial classifier anywhere: the panel labels the slot "General sentiment model", the financial slot stays an empty "No model registered" card, and every response carries `validation_status: not_human_validated` and `production_effect: none`.

## 5. Verification of registration

Registry schema and loading, duplicate registration prevention (two registered candidates for one role raise), role validation, licence/format/registration gate order, revision pinning (the manifest must name the exact revision), status-endpoint representation (`research_slots` = financial `no_candidate_approved`, general `registered`/`horizon`) and comparison-slot representation are covered by `test_sentiment_research_slots.py`, `test_sentiment_research_api.py` and `test_sentiment_candidate_reviews.py`. Exact counts: `SENTIMENT_TEST_REPORT.md`, section "R-series".
