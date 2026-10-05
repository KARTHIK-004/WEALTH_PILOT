# Phase 15 — FastAPI API Layer Report

## 1. Objective

Expose the already-built deterministic backend (Phases 4-14) through a
typed, documented FastAPI API layer — orchestration and serialization
only. No financial calculation, no recommendation logic, no compliance
logic, and no AutoGen/Gemini methodology was added or changed by this
phase; every number in every response was computed by an earlier phase
and is only ever read, assembled, and returned.

## 2. Exact routes

Determined from `docs/BUILD_PLAN.md` section 12's own "FastAPI API Map"
table — the single authoritative route list, which the document itself
states "supersedes `MASTER_PROMPT.md` §20's REST-nested-per-customer
endpoint list" (an architecture decision already made 2026-09-13), so no
route-naming conflict existed to resolve. All nine routes are
implemented, verified present in the live OpenAPI schema:

| Method | Route | Router |
|---|---|---|
| GET | `/api/health` | `api/routers/health.py` |
| GET | `/api/questionnaire` | `api/routers/profiles.py` |
| POST | `/api/profiles` | `api/routers/profiles.py` |
| GET | `/api/profiles/{profile_id}` | `api/routers/profiles.py` |
| POST | `/api/analysis` | `api/routers/analysis.py` |
| GET | `/api/analysis/{analysis_id}` | `api/routers/analysis.py` |
| GET | `/api/analysis/stream` | `api/sse.py` |
| POST | `/api/scenarios/compare` | `api/routers/scenarios.py` |
| POST | `/api/qa` | `api/routers/qa.py` |

**A real routing bug found and fixed**: FastAPI matches routes in
registration order. `/api/analysis/{analysis_id}` was originally
registered before `/api/analysis/stream`, so a request for the stream
endpoint matched `{analysis_id}="stream"` first and failed int-parsing
validation (a genuine 422 this project's own test suite caught, not a
hypothetical). Fixed by registering `sse.router` before `analysis.router`
in `api/main.py`, with the reasoning documented inline.

## 3. Request schemas

`api/schemas.py` — deliberately separate, public Pydantic v2 models for
every request (`AnalysisRequest`, `ProfileCreateRequest`, `GoalCreate`,
`ScenarioCompareRequest`, `QARequest`, ...), never a re-export of an
internal `AgentState`/`core.recommendation.Recommendation` model (section
5). Field-level validation throughout (`gt=0` on target amounts, `ge=0`/
`le=120` on age, `min_length=1` on required strings/questions) so a
malformed request fails Pydantic validation before reaching any service
code.

## 4. Response schemas

`api/schemas.py`'s `AnalysisResult` and its nested sections
(`RiskSection`, `FinancialHealthSection`, `GoalSection`,
`EmergencyFundSection`, `MarketSection`, `PortfolioSection`,
`ComplianceSection`, `RecommendationSection`, `ExplanationSection`) mirror
the internal Phase 4-14 models field-for-field where that shape is
already correct, but are independent classes — none of them subclass or
directly expose `agents/state.py`'s `AgentState`, `core.recommendation.
Recommendation`, or `agents/explanation.py`'s `ExplanationResult`/
`ExplanationOutput`. `explanation`'s internally-nested `output` object is
flattened into the public schema's top-level prose fields (the shape the
UI pages actually consume) — a serialization choice, not a recalculation;
every value is copied verbatim. `recommendation`/`explanation` are `None`
whenever the pipeline did not reach that stage — never a fabricated
placeholder (see section 11).

## 5. RFC 7807 design

`api/errors.py` extends Phase 0's inline `_problem_response` helper into
a proper `problem_response()` (adds `type`/`instance`) plus a small
hierarchy of named domain exceptions (`CustomerNotFoundError` → 404,
`AnalysisNotFoundError` → 404, `InvalidRequestError` → 400,
`ServiceUnavailableError` → 503) registered once via
`register_exception_handlers`. A route raises a specific exception
instead of building a response inline — Pydantic's own
`RequestValidationError` still maps to 422, any unhandled exception still
maps to a generic 500 with no stack trace in the body (only logged
server-side, and even there never a secret — nothing in this codebase
logs an API key, a database URL, or a Gemini prompt). Verified: every
error response across every tested failure mode carries
`application/problem+json` with `type`/`title`/`status`/`detail`/
`instance`, and never contains a stack trace, `site-packages`, an API
key, or a database URL (`tests/backend/api/test_rfc7807.py`).

## 6. SSE design

`GET /api/analysis/stream` streams `api/services/analysis_service.py`'s
`PipelineRun.events()` — the SAME execution path `POST /api/analysis`
consumes synchronously, so there is one place sequencing/timing nodes,
not two independently-written orchestrations. Each frame is
`event: node_progress\ndata: {"node", "status", "duration_ms", "summary",
"model_version"}\n\n` — BUILD_PLAN.md section 16's own vocabulary
(`{node, status, duration, summary, model_version}`), never a prompt, a
reasoning trace, or a raw exception. `summary` is always a short,
templated sentence built from already-computed structured fields
(`_node_summary` in `analysis_service.py`) — never free text. On an
unexpected failure, a single safe `event: error` frame is emitted with a
fixed, generic message — never the underlying exception's message or
type. Verified directly: a full transcript of an approved run contains
none of `chain-of-thought`, `system_instruction`, `prompt`, `autogen`,
`debate`, `transcript`, or `traceback` (`test_sse.py`).

**REJECT terminal behaviour (CRITICAL, section 24)**: `recommendation`/
`explanation` are only invoked — and therefore their progress events only
emitted — when the graph's own terminal state is `approved`. For REJECT,
`pending_information`, or `failed`, the stream ends at
`analysis_completed` with the terminal status embedded, with no
`recommendation`/`explanation` event at all — "did not execute" is
literal, not merely unreported (verified by
`test_stream_stops_after_reject_no_downstream_recommendation_or_
explanation`).

**Session lifecycle**: uses a dedicated non-generator dependency
(`api/dependencies.py::get_session_factory`) rather than the regular
`get_session`, because a `Depends()` GENERATOR's cleanup runs once the
route function returns — for a `StreamingResponse`, that is before the
body generator is actually drained, which would close/commit the session
mid-stream. The generator itself commits on success / rolls back on
failure, mirroring `get_session`'s policy inline. No queue, no worker, no
Redis/Celery — a plain synchronous generator; a client disconnect simply
stops iteration (`GeneratorExit`), and the `finally: session.close()`
still runs (section 26).

## 7. Startup model loading

`api/lifespan.py::warm_model_caches()` eagerly calls the THREE existing
`@lru_cache(maxsize=1)`-decorated loaders already in `agents/nodes.py`
(Phase 10) — `_risk_artifacts_cached`, `_behaviour_artifacts_cached`,
`_far_trans_tables_cached` — once, at application startup, rather than
lazily on the first request. No new loading logic was written; this
module only TRIGGERS the existing one earlier. `models/metrics.json`'s
presence and `market` section are also checked at startup (Market
Analyst's own artifact). Verified: `joblib.load` is called exactly once
per artifact across many simulated "requests"
(`test_model_artifacts_are_not_reloaded_per_request`, which counts real
`joblib.load` invocations). `GEMINI_API_KEY` is deliberately NOT checked
at startup — Phase 13's `run_explanation` and this phase's own
`qa_service.answer_question` already have an approved graceful-
degradation path (templated fallback / 503) when it is absent, and
treating it as fatal here would impose a stricter policy than Phase 13
itself defines.

**Request-time training: NO.** Confirmed by direct inspection — no
`fit`/`train`/`GridSearchCV`/dataset download appears anywhere in
`api/`; `core.optimizer`'s MVO/HRP/1-N are the same deterministic,
non-trained, closed-form functions Phase 8/10 already established (not
"training" in the ML sense — see section 15).

**A real, pre-existing launch-command bug found and fixed**: starting
uvicorn exactly as the Phase 0 `Makefile`'s `dev-backend` target already
did (`cd backend && uvicorn wealthpilot.api.main:app --app-dir .`) failed
at startup with `ModuleNotFoundError: No module named 'training'` —
`agents/nodes.py`'s behaviour-model loader imports the top-level
`training/` package (a documented, intentional cross-boundary import),
which is on `sys.path` during `pytest` (via `pytest.ini`'s
`pythonpath = .`) but was never on `sys.path` for a real server process,
because nothing ever eagerly triggered that loader at startup before this
phase's lifespan did. Fixed by adding `PYTHONPATH=..` to the `Makefile`'s
`dev-backend` target (repo root on `sys.path`, not just `backend/`) —
documented inline in the Makefile; no `agents/nodes.py` code was changed.

## 8. Startup failure behaviour

`warm_model_caches()` lets `joblib.load`'s own `FileNotFoundError`
propagate uncaught out of the `lifespan` context manager — FastAPI/
uvicorn surfaces this as a hard startup failure; the application never
starts serving requests with a missing/corrupted artifact. Verified by
`test_missing_artifact_fails_startup_clearly` (points `RISK_MODELS_DIR`
at a nonexistent path, asserts `FileNotFoundError` propagates).

## 9. OpenAPI

Verified against the live `/openapi.json`: all 9 routes present with
correct methods; request/response schemas generated from `api/schemas.py`
(including the `Literal` enums for `status`, `compliance_decision`,
`selected_strategy`); the RFC 7807 problem-detail shape is visible in
error responses; the app-level `description` states "Educational
decision-support prototype. Not licensed financial advice." — no claim of
licensed or guaranteed advice appears anywhere in the schema.

## 10. TypeScript generation

The Phase 0 `frontend/package.json` already had `openapi-typescript` as a
dev dependency and a `generate-types` npm script targeting
`http://localhost:8000/openapi.json` — reused exactly as-is, not
recreated. Regenerated `frontend/src/types/api.ts` against the live,
fully-built Phase 15 schema (the old file was a stale Phase 0 placeholder
with only `/api/health`); the new file has all 9 `operations` entries and
passes `tsc --noEmit --strict` cleanly. No hand-written TypeScript
interface exists anywhere mirroring a Pydantic model — the file's own
header states "Do not make direct changes to the file," unmodified. No
React code was written or touched in this phase.

## 11. Provenance

Every response that carries a component result also carries that
component's own `model_version`/`data_source`/`evaluated_at`, read
directly from the underlying Phase 4-14 object — never replaced with a
bare `"FastAPI"` label. `GET /api/health`'s `model_versions` object
(`risk`, `behaviour`, `market`, `portfolio`, `compliance_rules`) reads the
SAME version constants/files the graph nodes themselves use
(`nodes.RISK_MODEL_VERSION`, `models/metrics.json`'s `market.model_
version`, `core.compliance.load_rules().version`), not an
independently-invented health-check version string.

## 12. Compliance handling

`PipelineRun.events()` only calls `recommendation_engine_node`/
`explanation_node` when the graph's own terminal state is `approved` —
REJECT is checked via the SAME `state.blocked` flag `apply_delta` itself
already derives from `compliance_result.decision` (Phase 10/11), not a
re-implemented check. A REJECT case's `AnalysisResult.recommendation` and
`.explanation` are both `None`; nothing downstream is computed, nothing
is persisted (section 17), and no client parameter exists anywhere in
`AnalysisRequest`/`ScenarioParameters` that could influence the
compliance decision itself. Verified directly (CRITICAL, matching Phase
14's own section-37 precedent):
`test_rejected_analysis_produces_no_recommendation_and_no_portfolio_in_
recommendation`, `test_rejected_analysis_is_not_persisted_as_a_
recommendation`, `test_stream_stops_after_reject_no_downstream_
recommendation_or_explanation`.

## 13. Savings-first handling

Not treated as a distinct API-level branch: `PipelineRun.events()` always
calls the existing `recommendation_engine_node` (Phase 14) whenever
`approved`, and Phase 14's own Layer 2 independently determines
`savings_first` vs a normal allocation from the SAME
`state.emergency_fund.sufficient` field the graph itself already
populated — no second, competing check was written in this phase.

## 14. Recommendation handling

Exposed as the `recommendation` field of `AnalysisResult` (no separate
`/api/recommendations` route — `BUILD_PLAN.md`'s table has none, and
`MASTER_PROMPT.md`'s own page-to-endpoint map confirms the "AI
Recommendation" page reads from `GET /api/analysis/{id}`, not a dedicated
endpoint). `api/services/analysis_service.py` calls the existing,
unmodified `agents.recommendation.recommendation_engine_node` — this
phase does not reimplement, duplicate, or alter Phase 14's decision logic
anywhere (confirmed by direct inspection: no risk/goal/market preference
table, no precedence rule, and no strategy-selection logic exists in any
`api/` file). `selected_strategy` in the response is always exactly one
of `mvo`/`hrp`/`equal_weight` (the `RecommendationSection` schema types it
as that literal `Literal`) — the existing internal naming, never renamed
for aesthetics.

## 15. Gemini role

Unchanged from Phase 13: `explanation_node` is called unmodified; its
output is flattened into the response (section 4), never parsed to
derive a decision. The one NEW Gemini use in this phase — `POST /api/qa`
— is a narrowly-scoped, separate system prompt (`api/services/qa_service.
py`) reusing the SAME `google-genai` client/credentials Phase 12/13
already established, explicitly forbidden from stating a number, a
recommendation, or a compliance outcome for the asking customer (its
system prompt's rules 2-4); nothing in `qa_service.py` or `qa.py` parses
the returned prose for a decision, since none is ever extracted from it.
Not a change to `agents/explanation.py`'s or `agents/debate.py`'s own
methodology.

## 16. AutoGen role

None in this phase's API surface. `agents/debate.py` is not imported by
any `api/` file; `/api/analysis`'s pipeline never invokes the Phase 12
debate (a deliberate choice — see section 22, Known limitations). No
client-submitted parameter can influence AutoGen, since AutoGen is simply
never called from the API layer at all.

## 17. Database behaviour

`api/dependencies.py::get_session`/`get_session_factory` both build on
`db/session.py`'s existing `get_engine`/`get_db` — no second engine, no
second database configuration. No schema change, no Alembic migration:
`AnalysisRun.result` (JSON), `Recommendation`, `AgentLog`, and
`RiskAssessment` are all used exactly as they already existed (built at
Phase 0/1 with this phase in mind — `db/models.py`'s own docstrings
already anticipated "Written by `POST /api/profiles`" /
"the recommendation engine (Phase 14)" / "backs the Agent Activity page's
SSE replay").

**Persistence, exactly matching Phase 14's approved rule** — this phase
adds no new policy, it only calls the existing `persist_recommendation`
(via `recommendation_engine_node`) and writes `agent_logs`/
`risk_assessments` itself:
- `approved` → a `Recommendation` row (Phase 14's own logic), plus
  `agent_logs` rows (one per safe progress event) and, when representable
  (see below), one `risk_assessments` row.
- `savings_first` → a `Recommendation` row (Phase 14's own logic:
  "persist if representable using the existing schema").
- `blocked_rejected`/`failed` → no `Recommendation` row (verified,
  section 12).
- `AnalysisRun` — one row per DISTINCT profile hash (customer + goals +
  any `portfolio_strategy` override, so a different override is never
  silently served the previous override's stale cached result); repeat
  calls with an identical profile hash return the cached row rather than
  recomputing (verified: `test_second_call_with_identical_profile_
  returns_cached_analysis_id`).

**A genuine, disclosed data-representability gap found (not a bug this
phase introduces or should fix)**: `risk_assessments.risk_score` is
`NOT NULL`, but Phase 4 never produces an ordinal risk score at all
(already documented on `RiskAssessmentResult.risk_score`'s own Phase 10
docstring: "not computed by Phase 4 — no ordinal score was ever defined
there"). Writing a fabricated placeholder would violate this project's
own "never invent a number" rule, so `_persist_risk_assessment` simply
skips the row whenever `risk_score` is unavailable — the same
"skip-persistence-rather-than-fabricate" pattern Phase 14's own
`persist_recommendation` already established for an unrepresentable
`risk_category`. In practice this means NO `risk_assessments` row is ever
written by the current pipeline (every real risk assessment lacks a
score) — disclosed here rather than silently accepted.

**A second genuine, disclosed finding, this one about the underlying
Phase 7/9/10/11 pipeline itself (also not something this phase changes)**:
scanning 80 real FAR-Trans customers, NONE reached `approved` — the
majority reach `pending_information` (low risk confidence) or `rejected`.
Root cause: FAR-Trans has no expense/liquid-asset data at all, so
`emergency_fund.sufficient` is always `None` (unavailable, never `False`)
for a real customer; `savings_first_node` can only build a savings-first
proposal for the `False` case, returning a `missing_data` error (not a
`processing_failure`) for the `None` case instead, leaving
`state.portfolio_result` unset; compliance then correctly, and by
design, fails-closed on a proposal with no weights at all, producing
REJECT. This is a genuine, already-approved characteristic of Phases
7/9/10/11's interaction — this phase does not alter any of those files
(section 2 forbids it) and instead documents it here as a known
limitation (section 22) and adjusts its own test strategy accordingly
(a controlled, hand-built `AgentState` sequence for the `approved` test
scenarios, real FAR-Trans customers only for the naturally-occurring
`rejected`/`pending_information` cases).

## 18. Security

- No API key, database URL, environment variable, internal filesystem
  path, prompt, or chain-of-thought appears in any response body, log
  line, or SSE frame — verified directly across health, error, and SSE
  responses (sections 5/6/9).
- CORS: Phase 0's `settings.cors_origins` (`http://localhost:5173`
  default) preserved unmodified — no wildcard/unrestricted origin was
  introduced.
- No authentication was added (matches BUILD_PLAN.md's own "Auth: None
  (local prototype)" column for every route, and this phase's own
  boundary: no new dependency, no auth framework).
- No trade execution, brokerage integration, order placement, or fund
  transfer exists anywhere in this phase's code (confirmed by direct
  inspection — no such concept appears in any router or service).
- No new dependency was added beyond what Phase 0 already declared
  (`fastapi`, `sqlalchemy`, `google-genai` — all pre-approved); no
  Docker/Redis/Celery/second ORM/second validation framework.

## 19. Tests

**43 new tests**, all passing, across `tests/backend/api/`:

- `test_health.py` (extended, +2 new) — model_versions shape, no secrets.
- `test_lifespan.py` (3) — app starts, artifacts load once (not per
  request, proven by counting real `joblib.load` calls), missing
  artifact fails startup.
- `test_profiles.py` (6) — questionnaire parsing, profile create/fetch,
  404, validation failures.
- `test_rfc7807.py` (7) — problem+json consistency across 5 different
  failure modes, no stack trace/secret, 404-not-500 for known domain
  outcomes.
- `test_analysis.py` (11) — approved (mocked graph)/rejected (mocked
  graph)/naturally-occurring real-customer terminal states, the CRITICAL
  numerical-integrity test (exact QQQ=0.55/AGG=0.30/GLD=0.15 pass-through,
  raw decimals not `%`-formatted), persistence (Recommendation +
  AgentLog rows), profile-hash caching, REJECT-blocks-persistence.
- `test_sse.py` (4) — safe node progress for an approved run, no
  prohibited content (chain-of-thought/prompt/AutoGen/transcript/
  traceback substrings), the CRITICAL REJECT-stops-downstream-events
  test, documented event shape.
- `test_scenarios.py` (2) — two-scenario comparison, 404 on a
  nonexistent profile.
- `test_qa.py` (5) — answer+disclaimer, analysis-context passthrough
  (never a raw figure restated as the "context" itself, only category-
  level labels), 404 on a bad `analysis_id`, 503 on Gemini unavailability,
  422 on an empty question.

Full-suite results:

```text
tests/backend/api/                                                        43 passed
tests/  (entire project, all phases)                                     697 passed, 3 skipped, 0 failed
```

The 3 skips are the pre-existing, quota-exhaustion-tolerant Phase 12/13
live-Gemini tests (unrelated to this phase). Zero regressions across
Phases 0-14.

## 20. Manual verification

- [x] FastAPI starts (`test_application_starts`; also verified live via
  `uvicorn` + `curl`/`npm run generate-types` during development).
- [x] Health works, with the documented `model_versions` shape.
- [x] All 9 required routes work (verified against the live OpenAPI
  schema — section 9).
- [x] OpenAPI works and is valid.
- [x] Request validation works (422 + problem+json for bad input).
- [x] Response validation works (every route declares a `response_model`;
  FastAPI itself validates the outgoing shape).
- [x] RFC 7807 works consistently across every tested failure mode.
- [x] Model artifacts load once, not per request (proven by call
  counting, not by inference).
- [x] No request-time training/fitting anywhere (direct inspection; also
  structurally true since MVO/HRP/1-N were never "trained" models to
  begin with — Phase 8's own closed-form/convex functions).
- [x] Provenance preserved end-to-end (risk/market/portfolio/compliance/
  recommendation model versions all traceable to their source phase).
- [x] Phase 4/6/7/8 values preserved (read-only pass-through, never
  recalculated — verified by the numerical-integrity test).
- [x] Phase 9 compliance preserved (REJECT still blocks everything
  downstream, unchanged decision logic).
- [x] Phase 14 recommendation preserved (unmodified
  `recommendation_engine_node` call, unmodified decision logic).
- [x] Savings-first preserved (Phase 14's own independent check, not
  reimplemented here).
- [x] REJECT remains blocking (verified at both the sync-response and
  SSE-stream levels).
- [x] Rejected cases are not persisted (verified directly against the
  `recommendations` table).
- [x] SSE works, with only safe progress content, no hidden reasoning.
- [x] TypeScript generated from the live OpenAPI schema, no handwritten
  mirror.
- [x] No React implementation anywhere in this change.
- [x] All previous Phase 0-14 tests pass (699 total, zero regressions).

## 21. Known limitations

- **No real FAR-Trans customer reaches `approved`** in the current
  dataset (section 17's disclosed finding) — every genuine end-to-end
  `approved` scenario in this phase's own test suite uses a hand-built,
  fully deterministic `AgentState` sequence rather than a real customer,
  because none exists to use. This is a limitation of the underlying
  Phase 7/9/10/11 pipeline against FAR-Trans's actual data (no
  expense/liquid-asset fields), not something Phase 15 introduces.
- **`risk_assessments` is never populated** by the current pipeline,
  since Phase 4 never produces the `NOT NULL` `risk_score` column any row
  there would require — disclosed rather than worked around with a
  fabricated value.
- **AutoGen (Phase 12) is not part of `/api/analysis`'s synchronous
  pipeline** — a deliberate choice: it is not listed in `BUILD_PLAN.md`
  section 12's own `AnalysisResult` output tuple, Phase 14's approved
  four-layer rule never consumes a debate verdict at all, and invoking it
  on every analysis request would multiply an already-tight Gemini
  rate-limit/quota exposure (5/minute, 20/day per model — confirmed
  directly in Phase 12/13) for no corresponding benefit to the returned
  result. `agents/debate.py` remains available, unmodified, for a future
  integration decision.
- **`POST /api/scenarios/compare`'s "compare" is a real re-run of the
  existing pipeline for each scenario**, not a side-by-side diff computed
  from a single run — the two calls are independent, cached separately by
  their own (strategy-inclusive) profile hash.
- **`/api/analysis/stream` does not itself persist an `AnalysisRun`/
  `AgentLog` history** (unlike `POST /api/analysis`) — it is a live view
  of one run, to avoid a second, parallel, hard-to-reconcile history of
  the same computation. Phase 14's own `recommendation_engine_node` still
  persists its `Recommendation` row exactly as designed either way.

## 22. Phase 16 boundary

No React code, dashboard UI, navigation UI, chart, frontend component, or
frontend calculation was implemented — `frontend/src/` was touched in
exactly one place, the generated `types/api.ts`, via the pre-existing
`npm run generate-types` script, never hand-edited.

## 23. Next phase

Phase 16 — React shell. Do not begin Phase 16.

---

## PHASE 15 COMPLETION REPORT

**Status:** COMPLETE

**Exact API routes:** All 9 routes from `BUILD_PLAN.md` section 12 —
`GET /api/health`, `GET /api/questionnaire`, `POST /api/profiles`,
`GET /api/profiles/{profile_id}`, `POST /api/analysis`,
`GET /api/analysis/{analysis_id}`, `GET /api/analysis/stream`,
`POST /api/scenarios/compare`, `POST /api/qa` — verified live against
`/openapi.json`.

**Request schemas:** Deliberately separate public Pydantic v2 models in
`api/schemas.py` — never a re-export of `AgentState`/`Recommendation`/
`ExplanationResult`.

**Response schemas:** `AnalysisResult` + nested sections, field-matched to
the internal models where correct, independently defined; `recommendation`/
`explanation` are `None` when the pipeline did not reach that stage.

**RFC 7807:** `api/errors.py` — named domain exceptions
(`CustomerNotFoundError`, `AnalysisNotFoundError`, `ServiceUnavailableError`,
...) mapped once to `application/problem+json` with
`type`/`title`/`status`/`detail`/`instance`; never a stack trace or secret.

**SSE:** `GET /api/analysis/stream` shares the exact same `PipelineRun`
execution path as the synchronous endpoint; emits only
`{node, status, duration_ms, summary, model_version}`; recommendation/
explanation events (and DB persistence) only occur on the `approved`
path — REJECT/pending_information/failed genuinely never invoke them.

**Startup model loading:** `api/lifespan.py` eagerly warms Phase 10's
existing `@lru_cache`d loaders once; a missing artifact fails startup
hard. Verified via a real `joblib.load` call-count test.

**Request-time training:** NO.

**OpenAPI:** Valid; all 9 routes, request/response schemas, and RFC 7807
error shape present; no unlicensed-advice claim anywhere.

**Generated TypeScript:** `frontend/src/types/api.ts` regenerated from
the live schema via the pre-existing `npm run generate-types` script;
passes `tsc --noEmit --strict`.

**Provenance:** Every component result carries its own
`model_version`/`data_source`/`evaluated_at`, read from the source phase,
never replaced by a bare `"FastAPI"` label.

**Compliance:** REJECT verified structurally blocking at both the
synchronous response and the SSE stream — no recommendation, no
explanation, no persistence, no client parameter can bypass it.

**Savings-first:** Preserved via Phase 14's own unmodified independent
check — not reimplemented in this phase.

**Recommendation:** Exposed via `AnalysisResult.recommendation`, calling
the existing, unmodified `recommendation_engine_node`; `selected_strategy`
always exactly `mvo`/`hrp`/`equal_weight`.

**Gemini:** Unchanged role (explanation-only) for the existing pipeline;
one new, narrowly-scoped Q&A use with an explicit no-decision-authority
system prompt.

**AutoGen:** Not part of the API's synchronous/streamed pipeline (a
disclosed, justified choice — section 21); `agents/debate.py` untouched.

**Database:** No schema change, no migration; existing tables
(`AnalysisRun`, `Recommendation`, `AgentLog`, `RiskAssessment`) used
exactly as designed; two genuine data-representability gaps disclosed
(section 17) rather than worked around with fabricated values.

**Files created:** `api/schemas.py`, `api/errors.py`,
`api/dependencies.py`, `api/lifespan.py`, `api/sse.py`,
`api/services/__init__.py`, `api/services/analysis_service.py`,
`api/services/questionnaire_service.py`, `api/services/qa_service.py`,
`api/routers/profiles.py`, `api/routers/analysis.py`,
`api/routers/scenarios.py`, `api/routers/qa.py`,
`tests/backend/api/conftest.py` + 7 new test files,
`reports/phase15_fastapi_report.md`.

**Files modified:** `api/main.py` (lifespan + routers + RFC 7807 moved
into `errors.py`), `api/routers/health.py` (model_versions),
`tests/backend/api/test_health.py` (extended, not broken), `Makefile`
(`dev-backend`'s `PYTHONPATH` fix — see section 7), `frontend/src/types/
api.ts` (regenerated, not hand-edited).

**Database migrations:** None.

**Phase 15 tests:** 43 new, all passing.

**Full project tests:** 697 passed, 3 skipped (pre-existing,
quota-related, unrelated to this phase), 0 failed.

**Manual verification:** All items completed (section 20).

**Security verification:** No secret/path/prompt exposure found anywhere
in responses, logs, or SSE frames; CORS unchanged; no auth added (matches
the documented "local prototype" scope); no trade execution anywhere; no
undeclared dependency added.

**Known limitations:** No real FAR-Trans customer currently reaches
`approved` (a disclosed characteristic of the underlying Phase 7/9/10/11
pipeline against this dataset, not a Phase 15 defect); `risk_assessments`
is never populated (Phase 4 never produces the required `NOT NULL`
score); AutoGen is not part of the synchronous/streamed pipeline (a
deliberate, disclosed choice); scenario comparison re-runs the pipeline
per scenario rather than diffing a single run; SSE does not itself
persist a parallel run history.

**Phase 16 boundary:** No React/dashboard/frontend code — only the
generated `types/api.ts`.

Next Phase: Phase 16 — React shell.

Do not begin Phase 16.
