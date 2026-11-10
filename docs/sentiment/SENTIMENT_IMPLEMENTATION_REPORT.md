# Sentiment Implementation Report (2026-11-05)

Written for: the project owner and reviewers who need to know exactly what changed. Companion documents: `SENTIMENT_ARCHITECTURE.md` (design), `SENTIMENT_TEST_REPORT.md` (evidence), `SENTIMENT_DECISION_LOG.md` (choices), `SENTIMENT_GOVERNANCE_STATUS.md` (approvals). Nothing was committed or pushed; the working tree was not cleaned.

## 1. Phase outcome

| Phase | Outcome |
|---|---|
| 0 Repository and governance audit | Done. 56-row approval matrix extracted (44 approve / 10 unresolved / 2 reject) plus later scoped decisions; Git baseline 294 entries recorded. |
| 1 Runtime recovery | Done within the approved limit: `setuptools==81.0.0` only; integrity and TensorBoard regression verified; no model inference or loading as part of it. |
| 2 Architecture completion | Done: role slots, shared adapter interface, result schema, abstention, error handling, lifecycle guards. |
| 3 Rules-baseline hardening | Done as characterization only (42 tests, 30 fictional sentences); no rule changed. |
| 4 Transformer research implementation | Implemented (exact revision, safetensors only, local files, one softmax, safe failure). **Not run on real weights through the adapter** (needs Stage B placement). |
| 5 Multilingual | Not permitted -> safe abstention. Tamil and code-mixed text never reach a model. |
| 6 API | Done (`transformer_research` reshaped; status endpoint extended). |
| 7 Frontend | Done (one card per slot, empty slot shown plainly). |
| 8 Privacy/security audit | Done; data-flow diagram in `SENTIMENT_PRIVACY_AND_SECURITY.md`. |
| 9 Testing | Done as reported in `SENTIMENT_TEST_REPORT.md`, including one unresolved non-sentiment native crash. |
| 10 Evaluation framework | Reported as unavailable; no metric computed or claimed. |
| 11 Documentation and final audit | This set plus `SENTIMENT_FINAL_COMPLETION_REPORT.md`. |

## 2. Files changed or created (this window; all CRLF/LF conventions of each file preserved)

**Backend core** `core/sentiment/registry.py` (role slots, registration states), `normalization.py` (new reasons, `role`), `comparison.py` (slot comparison, model-vs-rules, overall reading), `adapter.py` (gates, per-key lock, breaker, `candidate_status`, `classify_with`), `inference_service.py` (`run_research`), `reviews.py` (Horizon verdict and owner decision); `core/sentiment_model.py` (`threads` argument).
**API** `api/schemas.py` (research schemas; `protected_namespaces` set on the two new classes to silence a warning), `api/services/personalized_insight_service.py` (`build_transformer_research`, status builders). **Config** `config/settings.py`, `.env.example` (`SENTIMENT_TRANSFORMERS_THREADS`, blank default; the enable flag stays `false`).
**Scripts** `scripts/write_pretrained_manifest.py` (registry-driven, refuses unregistered candidates), `scripts/export_demo_fixtures.py` (pins a machine-dependent field).
**Frontend** `src/lib/transformer-research.ts`, `src/components/financial-health/transformer-research-panel.tsx`, regenerated `src/types/api.ts`, `tests/transformer-research.cases.tsx`, `tests/mutation-check.mjs` (TR12 updated, TR13-TR18 added), regenerated fixtures.
**Tests** new `tests/backend/core/test_sentiment_research_slots.py` (replaces `test_sentiment_research_pair.py`, kept in the scratchpad as a `.bak`), new `test_user_text_rules_regression.py`, new opt-in `test_horizon_real_weights_smoke.py`; rewritten `tests/backend/api/test_sentiment_research_api.py`; updated `test_sentiment_candidate_reviews.py`, `test_write_pretrained_manifest.py`, `test_personalized_insights_model.py`, `test_personalized_insights_interpretation.py`, `test_sentiment_preflight.py`, `tests/training/sentiment/test_local_model_dir_standin.py`, and (setuptools pin) `tests/backend/core/test_task_cert_1_state.py`.
**Docs** `docs/DECISIONS.md` (ADR-055), `docs/MEMORY.md`, `docs/TEST_PLAN.md` (section 34), `docs/SECURITY.md`, `docs/THREAT_MODEL.md`, `docs/sentiment/stage_b/STAGE_B2_1_RUNTIME_COEXISTENCE_REPORT.md` (addendum, section 16), `docs/sentiment/stage_b/evidence/*`, and the ten `docs/sentiment/SENTIMENT_*.md` files.
**Environment** `.venv`: `setuptools` 84.2.1 -> 81.0.0 only (recovery); the B2.1 installation of 15 packages is the earlier, authorised step.

## 3. Behaviour that did NOT change

`user_text_rules_v1` (rules, thresholds, gating); the production method string; `SENTIMENT_TRANSFORMERS_ENABLED=false`; the Horizon registration state; `api/lifespan.py`; the database schema (no migration); Gemini prompts and data flows; risk, goal, portfolio, recommendation and compliance code; compliance rules; the rollback backup directory; the GDELT scaffold.

## 4. Known limitations

No real-weights run through the adapter; no quality evidence of any kind; the English-only gate means the multilingual capability of the model is unused; first load is synchronous (about 3-4 s) and memory is 1.3-1.6 GB peak when TensorFlow is also imported; an intermittent native crash in the `tests/training` full-directory runs is unexplained (see the test report).
