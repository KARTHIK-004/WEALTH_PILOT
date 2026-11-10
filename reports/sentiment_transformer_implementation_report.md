# Pretrained FinBERT + RoBERTa research comparison — implementation report (ADR-053)

Written for: the project owner. Date: 2026-11-03. Status words used exactly: IMPLEMENTED, TESTED_WITH_MOCKS, INFERENCE_VERIFIED, BLOCKED_BY_LICENCE, BLOCKED_BY_APPROVAL, DEFERRED, NOT_IMPLEMENTED.

**Headline.** The comparison layer is built and tested with stand-in backends. **No real model has run, and neither can:** FinBERT is BLOCKED_BY_LICENCE and Twitter-RoBERTa is BLOCKED_BY_LICENCE (unverified, no approval) and has no safetensors weights.
No accuracy, calibration or superiority claim is made or possible. Production is still `user_text_rules_v1`.

## Status by item

| Item | Status |
| --- | --- |
| Model registry with exact revisions and licence/format findings (`core/sentiment/registry.py`) | IMPLEMENTED |
| FinBERT adapter (`ProsusAI/finbert`, `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`) | IMPLEMENTED, TESTED_WITH_MOCKS; running it is **BLOCKED_BY_LICENCE** (cc-by-nc-sa-4.0; share-alike rejected, A3.5; training-data terms A3.3 unresolved) |
| Twitter-RoBERTa adapter (`cardiffnlp/twitter-roberta-base-sentiment-latest`, `3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7`) | IMPLEMENTED, TESTED_WITH_MOCKS; running it is **BLOCKED_BY_LICENCE** (licence/provenance unapproved) and has no safetensors file at that revision (BLOCKED_BY_APPROVAL for any alternative) |
| Label normalisation by name; native labels preserved | IMPLEMENTED, TESTED_WITH_MOCKS |
| Two-model comparison, rules relation, fallback, abstention/eligibility | IMPLEMENTED, TESTED_WITH_MOCKS |
| Artifact verification (revision pin, SHA-256 manifest, no pickle, symlink/root confinement, label check), timeout, back-off, cache | IMPLEMENTED, TESTED_WITH_MOCKS (symlink case skipped on this machine) |
| API: optional `transformer_research` object; additive status fields | IMPLEMENTED, TESTED_WITH_MOCKS |
| Frontend panel A/B/C with all states | IMPLEMENTED, TESTED_WITH_MOCKS (server-rendered markup tests; **no browser run this phase**) |
| `scripts/write_pretrained_manifest.py` | IMPLEMENTED, TESTED_WITH_MOCKS |
| Actual model inference | **NOT_IMPLEMENTED / not run** — BLOCKED_BY_LICENCE, BLOCKED_BY_APPROVAL (packages) |
| Package installation (`torch`, `transformers`, `tokenizers`, `safetensors`) | DEFERRED — BLOCKED_BY_APPROVAL |
| Weight download | DEFERRED — BLOCKED_BY_LICENCE |
| Dataset / human annotation / fine-tuning / training | NOT_IMPLEMENTED by design (this phase is pretrained-only); D20 stays rejected |
| Evaluation metrics, calibration, confidence, model selection | NOT_IMPLEMENTED — nothing can be measured; **selection is inconclusive** |
| Intensity / regression | DEFERRED — `null`, no field |
| Production activation | **BLOCKED_BY_APPROVAL** — not activated; `user_text_rules_v1` remains the method |

## Files created

`backend/wealthpilot/core/sentiment/{__init__,registry,normalization,adapter,comparison,inference_service}.py`; `scripts/write_pretrained_manifest.py`; `docs/sentiment/{model_licence_review,transformer_architecture,inference_and_fallback,limitations}.md`; `reports/sentiment_transformer_implementation_report.md`;
`tests/backend/core/test_sentiment_research_pair.py`; `tests/backend/api/test_sentiment_research_api.py`; `tests/backend/scripts/test_write_pretrained_manifest.py`;
`frontend/src/lib/transformer-research.ts`; `frontend/src/components/financial-health/transformer-research-panel.tsx`; `frontend/tests/transformer-research.cases.tsx`.

## Files modified

`backend/wealthpilot/config/settings.py` (4 research settings, default off); `.env.example`; `backend/wealthpilot/api/schemas.py` (new models; additive optional fields); `backend/wealthpilot/api/services/personalized_insight_service.py` (panel + status wiring);
`frontend/src/types/api.ts` (regenerated from `app.openapi()`, additive only); `frontend/src/components/financial-health/behaviour-sentiment-view.tsx`; `frontend/tests/component.test.mjs`, `frontend/tests/mutation-check.mjs` (+12 mutants TR1-TR12);
`frontend/tests/fixtures/demo/*.json` (regenerated real responses); `tests/backend/api/test_personalized_insights_model.py` (one exact-equality assertion relaxed to "every previous field unchanged, plus the new ones");
`docs/DECISIONS.md` (ADR-053), `docs/MEMORY.md`, `docs/TEST_PLAN.md` (section 30), `docs/SECURITY.md`, `docs/THREAT_MODEL.md`, `docs/ARCHITECTURE.md`, `training/sentiment/README.md`.

## Exact commands

```
# tests (no internet, no packages, no model)
PYTHONPATH=. .venv/Scripts/python.exe -m pytest tests/backend/core/test_sentiment_research_pair.py tests/backend/api/test_sentiment_research_api.py tests/backend/scripts -q
cd frontend && npm test && npx tsc -b && npx oxlint && npm run build && npm run test:mutations
# production-activation gate report (read-only; exit 1 while anything is open)
python scripts/sentiment_preflight.py --json
# regenerate frontend types without a server
python -c "import sys,json; sys.path[:0]=['backend']; from wealthpilot.api.main import app; print(json.dumps(app.openapi()))" > openapi.json && (cd frontend && npx openapi-typescript ../openapi.json -o src/types/api.ts)
```
Enabling a candidate (not permitted today) is described in `docs/sentiment/inference_and_fallback.md`.

## Remaining blockers (recorded once; owner decisions)

1. FinBERT: licence (CC BY-NC-SA 4.0, share-alike rejected) and training-data terms (A3.3).
2. Twitter-RoBERTa: licence/provenance approval, and a safetensors source (different repository/revision, or an isolated owner-approved conversion).
3. Approval of the four packages and a revision-pinned download.
4. A registry change with an ADR, then a separate real-weights smoke test.
5. Production activation (F1 / R14) is a separate, later decision and needs validation evidence that does not exist.

## Unrelated, pre-existing

`tests/backend/data/gdelt/test_sentiment_scaffold.py::test_no_production_entry_point_or_helper_imports_the_sentiment_scaffold` still fails, as before this work. Not touched.
