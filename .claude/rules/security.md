# Security Rules

Quick-reference. Full detail: `docs/SECURITY.md`.

- Never commit, log, or echo a secret (`.env`'s `GEMINI_API_KEY`,
  `DATABASE_URL`, `TEST_DATABASE_URL`, etc.). Secrets are read via
  `pydantic-settings` only.
- Never expose Gemini/AutoGen chain-of-thought, prompts, or a raw
  exception/stack trace to the frontend — errors are RFC 7807
  problem+json only.
- Every per-customer route/query is scoped by `customer_id`/`profile_id`
  at the query level. This is data-scoping, not authorization — this
  prototype has no per-account authorization layer; do not describe it as
  having one.
- Prototype authentication (`docs/DECISIONS.md` ADR-020) is intentionally
  minimal: client-side credential check, no server session/token,
  devtools-editable `localStorage` state. Do not build out a
  production-grade auth system (JWT/OAuth, password hashing, roles,
  admin) unless explicitly instructed — doing so silently would
  contradict this project's own disclosed scope.
- Customer-supplied free text reaching a Gemini prompt is untrusted
  context only — it must never be able to alter a computed number or
  bypass structured-output validation (verify with the existing
  prompt-injection tests in `tests/backend/agents/test_explanation.py`
  when touching that code path).
- No demo persona or test fixture may contain a real email, phone number,
  government ID, or financial account identifier.
- Raw datasets under `datasets/raw/` are immutable — never modified by
  application code, a training script, or a demo-seeding script.
