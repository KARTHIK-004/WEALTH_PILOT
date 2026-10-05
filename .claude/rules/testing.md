# Testing Rules

Quick-reference for test execution. Full detail: `docs/TEST_PLAN.md`,
`docs/RULES.md` Rule 26/30.

- Backend: `pytest tests/ -v` (from the repo root). Frontend:
  `npx tsc -b`, `npm run build`, `npx oxlint` (from `frontend/`).
- Add tests alongside the code that needs them, not after. A new
  endpoint gets isolation/validation tests; a new orchestration wiring
  gets a real, unmocked test against actual data where feasible (prefer
  this over a mock when verifying a genuinely new live code path — see
  `tests/backend/agents/test_financial_inputs_integration.py`).
- Run the full suite in isolation — no concurrent process touching either
  database. For a long run (multiple minutes), avoid piping through
  `tail`: it buffers everything until the process exits, hiding real
  progress and making a slow-but-healthy run indistinguishable from a
  stall. Prefer direct/unbuffered output to a file you can read
  incrementally.
- If a small number of tests fail only in a full-suite run (typically a
  connection-level error, not an assertion failure), re-run those exact
  tests individually before concluding anything. If they pass cleanly in
  isolation, this is a known, transient, full-suite-duration artifact —
  documented, not silently dismissed and not treated as a real
  regression. Get one final, clean, fully-isolated run before reporting
  completion.
- Up to 3 live-Gemini tests SKIP when Gemini is unavailable or out of
  quota at that moment (one has executed and passed when it was
  reachable) — normal, not a failure.
- The databases are hosted, so a machine network drop mid-run causes a
  burst of failures/errors (`getaddrinfo failed`, `Network is
  unreachable`, `Socket is not connected`, `server closed the connection
  unexpectedly`). Tracebacks print only at the END of a `-v` run; classify
  each failure from its own traceback, probe reachability without a DB
  session (`socket.getaddrinfo` + `socket.create_connection` to port
  5432), re-run failures in isolation once reachable, and never claim a
  clean full run that did not happen. See `docs/TEST_PLAN.md`.
- Never claim a task complete while a required regression test is
  failing without first running the isolation check above. Never claim
  browser-based visual/E2E testing was performed unless a headless
  -browser tool was actually used for it.
