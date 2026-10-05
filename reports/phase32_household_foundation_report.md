# Phase 32 — Household Foundation & Family Member Association

## 1. Status

**COMPLETE.** Every completion criterion in the Phase 32 prompt is met. The
household foundation — entity, membership, rules, APIs, authorization, UI,
tests, documentation — is in place, and it is **identity and membership only**:
no household financial data or calculation exists, and `POST /api/analysis` is
provably unchanged. Final isolated backend run: **838 passed, 2 skipped, 0
failed** (§12). One qualification stated up front: the household UI was verified
by source review, a server-side render against real API responses, and
tsc/oxlint/build — **not in a browser** (no browser tool exists here).

## 2. Objective

Introduce a first-class **Household** concept — `Customer → Household
Membership → Household` — as the foundation for later family-level features:
a household entity, membership with controlled relationship and role values,
the rules that keep membership valid, read/manage APIs with customer isolation,
a minimal household/member UI on the Customer Profile page, tests, and
documentation.

**Household financial aggregation is not implemented.** There is no household
income, expense, asset, liability, goal, emergency-fund, risk, portfolio or
recommendation logic anywhere in this phase, no new or changed ML model, and no
change to any existing individual calculation.

## 3. Existing Architecture Preserved

- **`customers` is untouched** — a membership row only references it (a test
  asserts the table's exact column set). No customer was migrated, renamed or
  replaced (ADR-031).
- **`POST /api/analysis` behaves exactly as before.** Household membership is
  contextual data that no analysis code reads. Proven three ways: regression
  tests compare the response body and the cache key before and after
  household creation and member addition; a live run against the four real demo
  personas (rolled back) shows their analysis statuses and ids unchanged (165
  approved, 166 approved/savings-first, 167 rejected, 168 pending) while they
  are in a household, with the 29098 response byte-identical; and the whole
  backend suite still passes.
- **Financial-input endpoints unchanged** (tests, and a live check that 29098's
  and 29099's inputs are still their own values, with nothing shared).
- **Demo personas 29096 / 29098 / 29099 / 29100 untouched** — no household was
  created for any of them; the dev database has 0 household rows.
- No change to ML models, datasets, the compliance rules, recommendation
  precedence, LangGraph, AutoGen, Gemini, or any `core/`, `agents/` or
  `training/` file.

## 4. Household Data Model

Table `households` (`db/models.py::Household`): `id` (integer primary key),
`name` (`VARCHAR(100)`), `created_at`, `updated_at` (timestamptz, server default
`now()`, `updated_at` also on update) — following the existing conventions
(integer `id`, `created_at` server default, a documented model class). **No
financial column of any kind**; a test asserts the exact column set and another
asserts no household API schema contains a financial-sounding field.

## 5. Membership Model

Table `household_members` (`db/models.py::HouseholdMember`): `id`,
`household_id → households.id`, `customer_id → customers.id`, `relationship`,
`role`, `is_dependent`, `created_at`, `updated_at`. (The Python attribute is
`relationship_type` so it cannot shadow SQLAlchemy's `relationship()`; the column
and the API field are both named `relationship`.) Both foreign keys are
`ON DELETE CASCADE` — a membership is meaningless without its customer or its
household. The rules are enforced **in the database**:

| Constraint | Enforces |
|---|---|
| `uq_household_members_customer` — `UNIQUE(customer_id)` | one household per customer; also makes a duplicate within one household impossible (rule 8). There is no soft delete — removing a member deletes the row — so every row is an active membership |
| `uq_household_members_one_primary` — partial unique index on `household_id` `WHERE role = 'primary'` | at most one primary per household |
| `ck_household_members_relationship` / `ck_household_members_role` | the controlled vocabularies |
| `ck_household_members_primary_is_self` | a primary member is always `self` |
| `ck_household_members_self_not_dependent` | `self` is never a dependent |
| `ck_household_members_is_dependent_matches_role` | `is_dependent` is always exactly `role = 'dependent'` |
| index `ix_household_members_household_id` | member lookup |

"Exactly one primary" is split honestly: **at most one** is a database
guarantee (the partial unique index); **at least one** cannot be a plain
PostgreSQL constraint, so it is guaranteed transactionally — the primary
membership is created in the same transaction as its household, and no API path
can remove it. A second `UNIQUE(household_id, customer_id)` was deliberately
omitted as strictly redundant given `UNIQUE(customer_id)` (ADR-031 notes a later
phase must add it if it ever allows several households per customer).

## 6. Relationship Rules

Vocabulary: `self`, `spouse`, `parent`, `child`, `sibling`, `other` — a
`Literal` type in the API schemas (unsupported value → **422**) and a CHECK
constraint in the database; a test asserts the two never drift apart. `self` is
reserved for the household's primary member: `self` with any other role is
rejected (422), `self` with `dependent` is also a CHECK violation.

## 7. Role Rules

Vocabulary: `primary`, `member`, `dependent` (same two enforcement layers).

| Request `(relationship, role)` | Result |
|---|---|
| `(self, primary)` | passes the schema, then **409** "household already has a primary member; a second primary cannot be created" |
| `(spouse|child|other|…, primary)` | 422 — a primary must be `self` |
| `(self, member)` / `(self, dependent)` | 422 — `self` is reserved for the primary / never a dependent |
| `(spouse|parent|child|sibling|other, member|dependent)` | 201; `is_dependent` = (role is `dependent`) |
| unsupported relationship or role value | 422 |

Permissions, kept to the minimum the phase needs: any member may view; **only
the primary may add or remove members** (a member or dependent gets 403); the
**primary cannot be removed** (409) — there is no ownership transfer, and no
API path can leave a household without its primary.

## 8. API Endpoints

Every route requires the caller's associated customer in the `X-Customer-Id`
header (missing or malformed → 401 problem+json). Request models reject unknown
fields (422), so nothing financial can be sent.

| Method and path | Purpose | Statuses |
|---|---|---|
| `POST /api/households` | create a household `{name}`; the caller becomes its `self`/`primary` member | 201; 401; 404 unknown customer; 409 already in a household; 422 |
| `GET /api/households/{household_id}` | household name, `member_count`, timestamps | 200; 401; 403 non-member; 404 |
| `GET /api/profiles/{profile_id}/household` | the caller's own household + membership, or both `null` (never creates one) | 200; 401; 403 (a customer can only ask about themselves); 404 |
| `GET /api/households/{household_id}/members` | members, primary first, with customer names | 200; 401; 403; 404 |
| `POST /api/households/{household_id}/members` | `{customer_id, relationship, role="member"}` | 201; 401; 403 (non-primary or non-member); 404 unknown household / customer; 409 duplicate, already in another household, second primary; 422 |
| `DELETE /api/households/{household_id}/members/{member_id}` | remove one membership | 204; 401; 403; 404 unknown household or member; 409 primary |

There is **no household deletion route** (a test asserts `DELETE
/api/households/{id}` is not defined). No household financial endpoint exists.
All errors are RFC 7807 (`application/problem+json` with `type`, `title`,
`status`, `detail`, `instance`) and never carry a stack trace or SQL.

## 9. Authorization / Customer Isolation

The backend has no server session, so the "associated customer" is the client's
`profileId`, sent as `X-Customer-Id` (`api/dependencies.py::
get_acting_customer_id`), and `api/services/household_service.py` authorizes
against membership:

- unknown household → 404; caller not a member → 403 (the denied response
  contains none of the household's data — asserted); missing/invalid identity →
  401;
- a customer can view only their own household record; only the primary can
  add/remove members; adding is limited by the membership rules (a customer
  already in a household cannot be added to another);
- membership is **not account access**: being in A's household does not let A
  read B's profile-household record, analysis or finances, and the frontend's
  active customer never changes.

**Stated limits, plainly.** The header is an asserted identity — the prototype
has no server session (ADR-020) — so a client that sends another customer's id
gets that customer's view, exactly as with every `profile_id` route today. This
protects against accidental and URL-edited cross-household access, not a
malicious client. Adding a member also needs **no consent** from the added
customer, and the member list then shows their name to the household. Both are
documented in `docs/SECURITY.md` and ADR-031 and are future work
(invitation/consent, real sessions). No JWT, OAuth, password or role system was
built.

## 10. Database Migration

Revision `f59ab6395383` — *add households and household_members*, revising
`8ef3f9affbe5` (the previous head) — generated with `alembic revision
--autogenerate` and inspected line by line: it contains **only** `create_table`
for `households` and `household_members` with the constraints above, and the two
indexes. Nothing else changed; no existing table was touched; migration history
was not modified. Applied to the dev database and to the test database
(`ALEMBIC_TARGET=test`); both report head `f59ab6395383`.

Read-only audit of both databases after the migration (and after the test
suite), all as intended:

| Check | dev | test |
|---|---|---|
| Alembic head | `f59ab6395383` | `f59ab6395383` |
| `households` / `household_members` present | yes | yes |
| `households` columns | exactly `id`, `name`, `created_at`, `updated_at` (all NOT NULL) | same |
| `household_members` columns | exactly `id`, `household_id`, `customer_id`, `relationship`, `role`, `is_dependent`, `created_at`, `updated_at` | same |
| Foreign keys | `customer_id → customers` CASCADE, `household_id → households` CASCADE | same |
| Unique | `uq_household_members_customer(customer_id)` | same |
| Indexes | `ix_household_members_household_id`, `uq_household_members_customer` (unique), `uq_household_members_one_primary` (unique, partial) | same |
| CHECK constraints | all five present | same |
| `customers` columns | unchanged (10 columns, no household column) | unchanged |
| Extra tables not in the models | none | none |
| Alembic `compare_metadata` drift | **none** | **none** |

Dev row counts: `households` **0**, `household_members` **0**, `customers`
29,095 (unchanged) — the live checks were rolled back and no demo persona was
put in a household. The demo personas' analysis runs are unchanged (29096→168,
29098→165, 29099→166, 29100→167, three runs each).

## 11. Frontend Changes

All under `frontend/src`, using existing shadcn/ui components, the generated API
types, and TanStack Query — no new library:

- `lib/api-client.ts` — five household methods; each sends `X-Customer-Id` from
  the single `profileId`.
- `hooks/use-household.ts` (new) — profile-household and member queries; create,
  add and remove mutations that invalidate the right keys.
- `components/profile/household-card.tsx` (new) and `pages/profile-page.tsx` —
  the **Household** card, placed after Goals: with no household, "No household
  created yet." and a create form (labelled name input with a placeholder, never
  a pre-filled value; the button is disabled until a name is typed); with one,
  the household name, **Your role**, **Relationship** and **Members** (the API's
  `member_count`) and a "View Household" toggle that reveals the member table —
  Name / Relationship / Role, a "You" badge, and for the primary only an Actions
  column (two-step Remove; "Cannot be removed" on the primary row) plus a
  clearly labelled **prototype association** add form (existing profile ID,
  relationship, role) that says it "does not let you view, edit or switch into
  their account". A non-primary member sees no actions and is told only the
  primary can manage. Opening the page never creates a household.
- `types/api.ts` — regenerated (see §14).
- No customer selector or switcher was reintroduced; the authenticated customer
  remains the active user. **Zero financial arithmetic**: the audit of the new
  files found only `Number(customerId)` and `> 0` as form-shape validation of a
  profile-id input, and `String(member_count)` for display.

Frontend verification: `npx tsc -b` **0 errors**; `npx oxlint` **0 errors, 8
warnings** (the unchanged pre-existing baseline in shadcn primitives and
provider files — none in a Phase 32 file); `npm run build` succeeds, 2,986
modules, JS 1,057.74 kB (gzip 317.99 kB) and CSS 97.80 kB — +8.5 kB of JS over
Phase 31's 1,049.24 kB, the household card and hooks. A scratch server-side
render of the real application against the real captured API responses passed
**31/31** checks (no-household, primary collapsed, primary expanded, non-primary
member, loading, RFC 7807 error for both the household and the member query, the
add/remove controls, accessibility of the new controls, and that the other pages
render identically with and without a household); the unchanged Phase 31
whole-app harness still passes **71/71**.

## 12. Tests

**Final isolated backend run** (`pytest tests/ -v --tb=long`, nothing else
touching either database): **838 passed, 2 skipped, 0 failed**, 153 warnings,
2223.53 s (37:03). The arithmetic is exact: 763 (Phase 31 baseline) + 74 new
= 837, plus one previously-skipped live-Gemini test that actually ran and passed
this time (§19.8) = 838, with skips down from 3 to 2. No existing test was
modified, weakened or skipped.

Two earlier attempts at this run were killed mid-way by the session ending, and
one of those showed a burst of 18 failures/errors between 28% and 35% — all
DB-touching tests, in a contiguous block, the documented hosted-database
transient pattern (`docs/TEST_PLAN.md` §22). The exact failing set was re-run in
isolation and **all 15 passed** (357 s), and the connectivity probe at that time
showed 9.5 s peak latency with no errors — the database was slow, not the code
wrong. The final run above then passed those same tests cleanly. Reported here
rather than quietly discarded.

**New tests: 74, all passing** — 23 database-level
(`tests/backend/db/test_household_models.py`) and 51 API-level
(`tests/backend/api/test_households.py`). Every item the phase's own list asks
for is covered:

| # | Requirement | Where |
|---|---|---|
| 1 | household creation | `test_creating_a_household_makes_the_creator_the_self_primary_member` |
| 2 | automatic primary membership | same test (relationship `self`, role `primary`, `is_dependent` false) + `test_no_other_members_are_created_automatically` |
| 3 | household retrieval | `test_a_household_can_be_retrieved_by_a_member` |
| 4 | member listing | `test_members_are_listed_with_the_primary_first` (a non-primary may view) |
| 5 | member addition | `test_the_primary_can_add_members_of_each_kind`, `test_role_defaults_to_member` |
| 6 | duplicate member rejection | `test_the_same_customer_cannot_be_added_twice_to_the_same_household` (409) + DB test |
| 7 | customer already in a household | `test_a_customer_already_in_another_household_cannot_be_added`, `test_a_customer_can_create_only_one_household` (409) + DB test |
| 8 | second primary rejection | `test_a_second_primary_cannot_be_created` (409) + DB test |
| 9 | invalid relationship | `test_unsupported_relationship_and_role_values_are_rejected` (422) + parametrised DB test |
| 10 | invalid role | same (422) + parametrised DB test |
| 11 | primary relationship/role validation | `test_primary_and_self_combination_rules_are_validated` (5 parametrised cases) + 2 DB tests |
| 12 | dependent validation | `test_a_dependent_is_flagged_as_dependent_and_may_be_any_non_self_relationship`, `test_is_dependent_must_match_the_role` |
| 13 | primary removal rejection | `test_the_primary_member_cannot_be_removed`, `test_removing_the_only_member_is_also_refused` (409) |
| 14 | household isolation | `test_a_customer_can_access_their_own_household_and_not_another` |
| 15 | cross-household access rejection | `test_a_customer_cannot_modify_or_delete_from_another_households`, `test_another_households_data_is_never_in_a_denied_response`, `test_a_customer_cannot_join_a_household_without_the_primary_adding_them`, `test_only_the_primary_can_add_or_remove_members`, `test_membership_does_not_grant_access_to_another_members_profile_household_or_account` |
| 16 | unknown household | `test_unknown_household_is_a_404_and_a_non_member_gets_a_403` (404 on all four routes) |
| 17 | unknown customer | `test_adding_an_unknown_customer_is_a_404`, `test_an_unknown_customer_cannot_create_a_household`, `test_profile_household_for_an_unknown_customer_is_a_404` |
| 18 | RFC 7807 errors | `assert_problem` asserts content type, status, title, detail, instance and the absence of traceback/SQL text on **every** error assertion in the file |
| 19 | existing analysis regression | `test_household_membership_does_not_change_the_analysis_result`, `test_household_membership_does_not_change_a_members_own_analysis` |
| 20 | existing financial-input regression | `test_financial_inputs_are_unaffected_by_household_membership`, `test_existing_profile_and_goal_endpoints_are_unaffected` |

Beyond the list: the missing/malformed-identity 401 matrix across all six routes
(6 parametrised header values), `test_household_creation_rejects_blank_or_unknown_fields`
(including six attempts to smuggle a financial field), `test_member_creation_rejects_unknown_fields_and_bad_ids`,
`test_there_is_no_household_deletion_endpoint`, `test_openapi_lists_exactly_the_household_routes`,
`test_household_schemas_contain_no_financial_field`, a removed member becoming
free to join elsewhere, `test_removing_an_unknown_member_or_one_from_another_household_is_a_404`,
and `test_a_database_integrity_race_is_reported_as_409_not_500` (which also
proves the session stays usable afterwards). The DB-level file additionally
asserts the exact column sets of both new tables and of `customers`, cascade
behaviour, and that the Python vocabularies match the API `Literal` types and
the CHECK constraints.

**The isolation tests were verified to actually bite**: temporarily disabling
the non-member check made three of them fail
(`test_a_customer_can_access_their_own_household_and_not_another` 200 instead of
403, plus two more); the file was then restored and confirmed byte-identical to
its pre-mutation backup.

No frontend test framework exists in this project and none was added, so the
household UI is covered by the scratch render check described in §11/§18 rather
than by committed tests.

## 13. Existing Analysis Regression

- `test_household_membership_does_not_change_the_analysis_result` — the
  `POST /api/analysis` body is identical (same `analysis_id`: a cache hit on an
  unchanged profile) after the customer creates a household and adds a member,
  and `compute_profile_hash` is unchanged;
- `test_household_membership_does_not_change_a_members_own_analysis`;
- `test_financial_inputs_are_unaffected_by_household_membership` (values,
  merge-not-replace, nothing shared to the spouse) and
  `test_existing_profile_and_goal_endpoints_are_unaffected`;
- live, on the real personas (rolled back): 29098's analysis response
  byte-identical after household creation; 29098 approved (165), 29099
  approved/savings-first (166), 29100 rejected (167), 29096 pending (168) all
  unchanged while in a household; financial inputs unchanged;
- render check: the Risk, Financial Health, Goals, Portfolio, Recommendation and
  Why pages render **identically** with and without a household;
- the whole backend suite (below) and the Phase 31 whole-app render harness
  (71/71) still pass.

## 14. API Contract

`app.openapi()` now lists 18 paths (13 before): exactly the six household
operations on five new path entries, with six new schemas
(`HouseholdCreateRequest`, `HouseholdMemberCreateRequest`, `HouseholdOut`,
`HouseholdMemberOut`, `HouseholdMembersResponse`, `ProfileHouseholdResponse`).
`frontend/src/types/api.ts` was regenerated by dumping `app.openapi()` in a short
process and running `openapi-typescript`; it is **byte-identical to a fresh
generation**, and its diff against the previous file is **418 added lines, 0
removed** — every added line is a household path, schema, operation, or the
structural scaffolding around them. No unrelated route or schema changed. A test
also asserts the exact household route set and that no household schema field is
financial.

## 15. Security Validation

Asserted by the automated suite **and** by a live rollback-safe run on the real
personas (36 checks, all passing), including:

| Case | Result |
|---|---|
| Customer A → Household A | allowed (200) |
| Customer A → Household B (read, list members) | 403, no data from B in the response |
| Customer B → Household B / A → Household A (own) | allowed |
| A adds anyone to Household B, including themself | 403 |
| A deletes a member of Household B | 403 |
| A adds customer B to Household A | allowed only by the rules: 409 if B already has a household, 201 if not |
| A member (non-primary) or dependent adds/removes | 403 |
| Anyone removes a primary | 409 |
| Duplicate member / second primary | 409 |
| Invalid relationship / role / (self, member) / (spouse, primary) | 422 |
| Unknown household 404; missing or malformed `X-Customer-Id` 401; membership grants no access to another member's profile-household record (403) |  |
| A database race the pre-check cannot see (unique constraint) | 409, not 500, session still healthy |

A temporary mutation that disabled the non-member check made three isolation
tests fail and was then reverted (the file was restored and re-verified). The
limits of the asserted-identity model are in §9.

## 16. Documentation Updates

`docs/ARCHITECTURE.md` (entity chain, ER diagram, household tables, API and
frontend sections), `docs/PRD.md` (capability 14.16 — current identity and
membership vs future financial aggregation; out-of-scope and future-scope
updates), `docs/DESIGN.md` (§26 household presentation), `docs/RULES.md` (Rule
31), `docs/SECURITY.md` (household authorization and its limits),
`docs/DECISIONS.md` (**ADR-031**), `docs/MEMORY.md`, `docs/TEST_PLAN.md`,
`CLAUDE.md` (§14) and `.claude/rules/backend.md` (one pointer each), and
`TASKS.md`. No historical report was rewritten.

## 17. Files Changed

Classification (the repository has no commits, so `git diff` has no baseline;
this is from a modification-time audit against a marker taken at Phase 32 start,
plus my own edit log).

**A — expected Phase 32 implementation**

*Backend (new)*
- `backend/wealthpilot/api/routers/households.py` — the six routes.
- `backend/wealthpilot/api/services/household_service.py` — every rule and
  authorization decision.
- `backend/alembic/versions/f59ab6395383_add_households_and_household_members.py`
  — the migration.

*Backend (modified)*
- `db/models.py` — `Household`, `HouseholdMember`, the two vocabulary tuples,
  and the new SQLAlchemy imports. No existing model changed.
- `api/schemas.py` — six household schemas + the two `Literal` types.
- `api/errors.py` — `HouseholdNotFoundError`, `HouseholdMemberNotFoundError`,
  `IdentityRequiredError` (401), `AccessDeniedError` (403), `ConflictError`
  (409). No existing error changed.
- `api/dependencies.py` — `get_acting_customer_id`.
- `api/main.py` — one `include_router` line and its import.

*Tests (new)*
- `tests/backend/db/test_household_models.py` (23 tests)
- `tests/backend/api/test_households.py` (51 tests)

*Frontend*
- `components/profile/household-card.tsx` (new), `hooks/use-household.ts` (new)
- `lib/api-client.ts` — five household methods + the `X-Customer-Id` helper
- `pages/profile-page.tsx` — renders the card; page description updated
- `types/api.ts` — regenerated (household additions only; §14)

*Documentation*
- `docs/ARCHITECTURE.md`, `docs/PRD.md`, `docs/DESIGN.md`, `docs/RULES.md`
  (Rule 31), `docs/SECURITY.md`, `docs/DECISIONS.md` (ADR-031),
  `docs/MEMORY.md`, `docs/TEST_PLAN.md`, `CLAUDE.md` (§14),
  `.claude/rules/backend.md`, `TASKS.md`, and this report.

**B — required integration fixes**: none. Nothing existing needed fixing; the
household foundation is purely additive.

**C — unexpected**: none in this phase. Two items carried over from earlier
phases are unchanged and untouched: `frontend/.venv/` (Phase 31, gitignored) and
customer 29101 / the externally edited `config/settings.py` (Phase 29).

**Not changed**: `backend/wealthpilot/core/`, `agents/`, `data/`, `config/`,
every existing router and service, `training/`, `models/`, `datasets/`,
`scripts/`, every pre-existing migration, `config/compliance_rules.yaml`,
`package.json` (no dependency added or removed), and every existing test file.
Verified by a modification-time audit: `find models datasets config training
backend/wealthpilot/core backend/wealthpilot/agents -newer <marker>` returns
empty. No file was deleted.

## 18. Known Limitations

- **Household financial aggregation does not exist** — by design; a household is
  identity and membership only.
- **Asserted identity.** `X-Customer-Id` is client-supplied; there is no server
  session, so this is not protection against a malicious client (§9).
- **No consent to be added.** A primary can attach any existing customer who is
  not already in a household by profile ID; that customer's name is then visible
  to the household. The UI labels this a prototype association. Invitation and
  acceptance are future work.
- **No ownership transfer**, so the primary can never be removed; and a customer
  deleted outside the API (the demo `reset` script) cascades their membership and
  could leave a household without a primary.
- **No household rename or deletion API.**
- **Membership management is primary-only**; members and dependents can only view.
- **No browser verification.** The household UI was verified by source review, by
  a server-side render of the real components against real API responses (31
  checks) and by tsc / oxlint / build — not in a browser. The member table and add
  form sit behind a toggle a server render cannot click, so that one build variant
  flips only the initial state (in scratch, not in the project); toggle
  behaviour, the select controls, the two-step remove and the mutations' live
  interaction are unverified in a browser.
- The scratch harnesses and the live check are not committed tests (the project
  has no frontend test runner and none may be added); the backend behaviour is
  covered by committed tests.
- The hosted database makes backend tests slow (several seconds each), so the
  suite takes 20–37 minutes depending on latency, and a slow spell can produce a
  burst of transient failures that pass on an isolated re-run (§12).

## 19. Unexpected Findings

1. **The backend has no caller identity at all** (ADR-024, SECURITY §6) — yet
   the prompt requires authorization against membership. The smallest consistent
   design was to make the existing client-side association explicit as an
   `X-Customer-Id` header and authorize on it, with the asserted-identity limit
   documented rather than hidden. This is a design decision, not a defect.
2. A model attribute named `relationship` would shadow SQLAlchemy's
   `relationship()` inside the class body, so the Python attribute is
   `relationship_type` mapped to the `relationship` column.
3. The existing tests' SAVEPOINT fixture means a `session.rollback()` after an
   expected failure would also discard the test's own setup rows; the service
   therefore converts integrity violations inside a nested SAVEPOINT
   (`begin_nested`) rather than rolling the session back, and the DB-level tests
   use the same technique.
4. Adding a member by profile ID is an enumeration surface (it reveals a name to
   the household); it mirrors the prototype's existing unauthenticated
   `GET /api/profiles/{id}` and is documented, not fixed.
5. The hosted database was slow: one connectivity probe showed a 21.9 s latency
   spike (no errors), and every DB-backed test takes several seconds.
6. Harness self-corrections, not application defects: a leading-space
   assertion, and a Windows `?query` on a file-URL import.
7. `frontend/.venv/` (reported in Phase 31) is still present, gitignored and
   untouched. Customer 29101 and the externally edited `settings.py` are as in
   Phase 29.
8. **A live-Gemini test that has skipped since Phase 29 ran and passed**
   (`test_debate_gemini_client.py::test_gemini_model_client_message_retrieval_and_usage_contract`),
   so the final run shows 2 skips rather than the documented 3. The Gemini quota
   has partially recovered: one real call succeeded, while the other two
   live-Gemini tests still skipped. Nothing in this phase touches Gemini — this
   is an environment change, reported because it moves the expected skip count.
9. Two full-suite attempts were killed by the session ending before pytest could
   print its summary, which is also why the final run was launched as a detached
   process that survives the session. The transient failures seen in one of those
   attempts are analysed in §12.

## 20. Final Assessment

Completion criteria from the Phase 32 prompt:

| Criterion | Met | Evidence |
|---|---|---|
| `households` / `household_members` tables created | Yes | §4, §5, §10 |
| Migration created, applied to dev and test, only intended changes | Yes | §10 (head `f59ab6395383` on both; no drift; migration inspected line by line) |
| `customers` remains intact | Yes | §3, §10 (column set unchanged; a test asserts it) |
| At most one household per customer | Yes | `UNIQUE(customer_id)` + service 409 + DB and API tests |
| One primary per household | Yes | partial unique index (at most one) + transactional creation (at least one) |
| Primary = `self`; dependent rules; duplicates blocked | Yes | §6, §7, CHECK constraints + 422/409 tests |
| Household APIs implemented | Yes | §8 (six routes; no deletion route) |
| Customer isolation implemented | Yes | §9, §15 (matrix passes in tests and live) |
| RFC 7807 errors verified | Yes | every error assertion checks the full problem body |
| Frontend household section and member view | Yes | §11 (31 render checks) |
| No customer-switching UI reintroduced | Yes | asserted in the render check and by source |
| No household financial calculations or fields | Yes | schema, DB column-set tests, OpenAPI schema test, frontend audit |
| `POST /api/analysis` unchanged | Yes | §13 (tests, live personas, identical bodies and cache key) |
| Demo personas preserved | Yes | §3, §10 (0 household rows; ids unchanged) |
| API types regenerated | Yes | §14 (byte-identical to a fresh generation; additive only) |
| Backend tests / TypeScript / oxlint / Vite build | Yes | §12, §11 |
| Security isolation tests pass | Yes | §15 (plus a mutation check proving they bite) |
| Documentation updated; report; git audit; no unexplained changes | Yes | §16, §17, §21 |

Assessment: the foundation does what it should and nothing more. The rules are
enforced twice over (database constraints plus the service), so an invalid
household or membership cannot be created by any code path, present or future;
the individual analysis pipeline, the ML models and the FAR-Trans customer
architecture are untouched, which was the whole point of linking through a
membership table rather than reshaping `customers` (ADR-031). What is *not*
built is stated plainly rather than implied: no household finances, no consent
flow, no ownership transfer, no deletion, and an asserted (not authenticated)
caller identity. Those are the seams a later phase will need to address before
household financial aggregation can be trusted.

## 21. Git Status

`git status --short` lists every top-level path as `??` (untracked): the
repository still has **0 commits**, so there is no staged state and no diff
baseline. Nothing was committed. Every changed file is classified in §17 — all
category A (expected Phase 32 implementation and documentation), no category B
(no integration fix was needed), and no category C (no unexpected change). No
file was deleted, `models/` and `datasets/` are untouched, and no dependency was
added or removed.
