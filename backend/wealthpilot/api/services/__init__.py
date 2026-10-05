"""Phase 15 — API orchestration/serialization layer. No financial logic
lives here (CLAUDE.md rule 1/2, this phase's own section 40): every
number returned by anything in this package was computed by Phases
4-14 and is only ever read, combined into a response shape, and
persisted — never calculated or altered here."""
