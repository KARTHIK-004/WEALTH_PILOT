# Frontend Rules

Quick-reference for `frontend/`. Full detail: `docs/RULES.md`,
`docs/DESIGN.md`, `docs/ARCHITECTURE.md` §4.

- React 19, Vite, TypeScript (no `any`), Tailwind, shadcn/ui, TanStack
  Query, React Router, Recharts, lucide-react. No other library without
  asking first.
- Add shadcn primitives via `npx shadcn@latest add <name>` — never
  hand-write one the CLI provides.
- `frontend/src/types/api.ts` is GENERATED (`npm run generate-types`, or
  `app.openapi()` called directly in Python when no server should be
  started). Never hand-edit it or hand-write a duplicate interface.
- The frontend never calculates a financial number — no risk, financial
  health, goal feasibility, Monte Carlo probability, required
  contribution, emergency-fund status, portfolio weight, compliance
  decision, or recommendation strategy in React. It formats, validates
  form shape, and manages UI state only. If a number is needed, it must
  come from an API field.
- Charts live in `components/charts/` (Recharts only) and are display-only:
  typed props in, no API call, no calculation, `null` shown as unavailable
  (never `0`, never an empty series), and always beside a table/text
  carrying the same values. Never plot a derived number (shortfall,
  normalised weight, score, frontier) — see `docs/DESIGN.md` section 16,
  ADR-029.
- Every API-dependent page/section handles loading, empty, unavailable
  (with reason), error, and success states (`LoadingState`, `ErrorState`,
  `SectionUnavailable`, `NoProfileSelected`).
- One `useCustomer().profileId` is the single source of truth for "which
  customer is this session showing" — no page or component keeps its own
  independent customer-id state, and no UI lets a user select or switch
  to a different customer. No numeric customer id is ever hard-coded into
  a page component.
- Preserve accessibility: keyboard nav, visible focus, `aria-label`/
  `aria-current`, accessible form errors. A change must not regress an
  existing accessibility property.
- Responsive via Tailwind breakpoints; no page-specific breakpoint
  system.
