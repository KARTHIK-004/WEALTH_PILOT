# Replacement of the blocked FinBERT + RoBERTa candidates — report (ADR-054)

Written for: the project owner. Date: 2026-11-03. Statuses use the requested words: IMPLEMENTED, TESTED_WITH_MOCKS, INFERENCE_VERIFIED, BLOCKED_BY_LICENCE, BLOCKED_BY_PROVENANCE, BLOCKED_BY_APPROVAL, DEFERRED, NOT_IMPLEMENTED.

**Headline.** Both proposed replacements were reviewed from the public repositories and **neither passed the gate**, so nothing was downloaded or installed, no inference ran, and the active comparison pair was **not** replaced (the instruction was conditional on both passing).
The reviews, the Bullish/Bearish label handling and a read-only status listing were implemented and tested with mocks. Production is unchanged: `user_text_rules_v1`.

## 1. ADR-053 architecture reused

Registry, adapter, label normalisation, two-model comparison and rules relation, artifact verification, `transformer_research` API object, status endpoint, comparison panel, manifest tool and privacy tests are all reused unchanged. Additions are small: `core/sentiment/reviews.py`, a wider label vocabulary in `normalization.py`, and one additive status field.

## 2. Original candidates and why they were blocked (history preserved in ADR-053)

| Candidate | Revision | Blocker |
| --- | --- | --- |
| `ProsusAI/finbert` | `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` | CC BY-NC-SA 4.0; share-alike rejected by the owner (A3.5); A3.3 unresolved -> BLOCKED_BY_LICENCE |
| `cardiffnlp/twitter-roberta-base-sentiment-latest` | `3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7` | tweet-derived training data not reviewed or approved; no `model.safetensors` published -> BLOCKED_BY_PROVENANCE (and no safetensors file) |

## 3-7. Replacement candidates: revisions, licence, provenance, safetensors

| | `tooshlegacy/distilbert-financial-tweet-sentiment` | `Horizon-Labs/multilingual-sentiment-small` |
| --- | --- | --- |
| Revision | `ba66b6a858cc775dc9e78d773c437b7e984fd5fc` | `e60eb86fd9e5bdd8c097bf6d6e75dade85a1ccac` |
| Licence | apache-2.0 declared **in metadata only**: no LICENSE/NOTICE file, no named author or organisation | apache-2.0 with a standard LICENSE and a NOTICE |
| Base model | `distilbert-base-uncased`, apache-2.0 | `jhu-clsp/mmBERT-small`, MIT |
| Training data | `zeroshot/twitter-financial-news-sentiment` (MIT declared): tweets "collected using the Twitter API", annotation process undocumented, no platform-terms statement; no Financial PhraseBank or share-alike wording found | FineWeb / FineWeb-2 web-crawl snippets (ODC-BY) plus LLM-written synthetic text; **labels are an LLM teacher's soft labels, no human annotation**; real/synthetic split not stated |
| Safetensors | yes: `model.safetensors`, sha256 `97fcaa54879f7cfd07af3cdcdb73aaa011dc89ced9b4ca479038148b957c6ac0` | yes: sha256 `f0d0b6d2958f2f0a017ec060bb4768bfa720ef67625486ef02710c6484d02dd1` (matches the repo's `SHA256SUMS`) |
| Labels | 0 Bearish, 1 Bullish, 2 Neutral | 0 negative, 1 neutral, 2 positive |
| Other | English only; card: not for trading decisions or high-stakes use | config in transformers-5 format; card: don't use it to make decisions about individuals |
| **Verdict** | **BLOCKED_BY_PROVENANCE** (`blocked_by_provenance`) | **BLOCKED_BY_APPROVAL** (`blocked_by_approval`) |

Full table with sources: `docs/sentiment/model_licence_review.md`. The facts were read through an intermediary summarising fetch of the Hugging Face API and raw files; they must be re-read directly before any approval.

## 8. Dependencies

Installed: none. Deferred: `torch`, `transformers`, `tokenizers`, `safetensors` — BLOCKED_BY_APPROVAL. New engineering finding: Horizon's config is written by transformers 5.17.0 (v5 keys such as `rope_parameters`); the proposed pin 4.57.1 is unverified against it, and version 5 reportedly drops TensorFlow, which the installed TensorFlow 2.17 workflow uses. The latest transformers on PyPI at the check was 5.22.1 (Python >= 3.11).

## 9. Files

Created: `backend/wealthpilot/core/sentiment/reviews.py`; `tests/backend/core/test_sentiment_candidate_reviews.py`; `reports/sentiment_transformer_replacement_report.md`.
Modified: `core/sentiment/normalization.py` (Bullish/Bearish; native spelling preserved); `api/schemas.py` (`CandidateReviewOut`, additive `reviewed_candidates`); `api/services/personalized_insight_service.py` (`candidate_reviews`); `frontend/src/types/api.ts` (regenerated, 61 lines added, none removed);
`frontend/tests/fixtures/demo/*.json` (regenerated real responses); `tests/backend/api/test_personalized_insights_model.py` (the exact-equality status assertion also tolerates `reviewed_candidates`);
`docs/DECISIONS.md` (ADR-054), `docs/MEMORY.md`, `docs/TEST_PLAN.md` (section 31), `docs/sentiment/{model_licence_review,transformer_architecture,inference_and_fallback,limitations}.md`.

## 10-11. API and frontend

API: `GET /api/sentiment-model/status` gains `reviewed_candidates` (all four reviews, verdicts, blockers, hashes; no local path). The per-candidate licence, weight, loaded, enabled, production and fallback fields from ADR-053 remain. `transformer_research` is unchanged.
Frontend: **not changed beyond regenerated types.** The comparison panel still describes the active (blocked) pair, because the registry was not swapped. A panel for the replacements would show only "unavailable" states for models that cannot run, and the swap is a bounded follow-up (ADR-054).

## 12-13. Tests and inference

- Backend sentiment, demo, preflight, review and training suites under the socket guard: **1460 passed, 0 failed, 6 skipped** on the final run (an earlier run had one failure, the old exact-equality status assertion, which I fixed). External connection attempts: 0.
- New: 12 tests in `test_sentiment_candidate_reviews.py`, all passing.
- Frontend: `npx tsc -b` clean, `npm test` 276 of 276, `npm run build` succeeded, `oxlint` reports no errors. The mutation check was **not** rerun (no frontend source changed).
- All model output is a stand-in: **TESTED_WITH_MOCKS**. **INFERENCE_VERIFIED: none. Actual inference ran: no.**
- The GDELT scaffold test failure is pre-existing and untouched.

## 14-15. Licensing and activation

Both models passed licensing: **no**. Production activation: **not activated** (`user_text_rules_v1`, `SENTIMENT_MODEL_ENABLED=false`, `SENTIMENT_TRANSFORMERS_ENABLED=false`, confidence unavailable, intensity null, no ledger payload, no financial-decision impact). The preflight exits 1.

## 16. Remaining owner decisions (once)

1. A3.3 for the web-crawl + LLM-synthetic data and the tweet-derived data; A3.5 stays rejected.
2. Choose or reject each candidate; for the tooshlegacy model ask its publisher for a licence file and the dataset's annotation and platform terms.
3. Approve the packages and decide the `transformers` line.
4. Approve a pinned download, a registry change with an ADR, then a real-weights smoke test. Production activation (F1/R14) is separate.

## 17. Commands to run approved inference (do not run until all of the above is approved)

See `docs/sentiment/inference_and_fallback.md`: install the approved packages; download only the pinned `model.safetensors`, `config.json` and tokenizer files into `models/sentiment_pretrained/<key>/`; `python scripts/write_pretrained_manifest.py --candidate <key> --tokenizer-length <n>`; set `SENTIMENT_TRANSFORMERS_ENABLED=true`, `_MAX_TOKENS`, `_TIMEOUT_SECONDS`, `_DEVICE=cpu`; restart; then run the opt-in smoke test that must be written for the approved weights.
