# Research Enhancement Track — Phase B2-R: Annotation Rubric Addendum (PROPOSED)

**Status: PROPOSED; not adopted.** It resolves nothing by itself.

> **Decisions recorded (B2-S, 2026-10-13 18:37 UTC; the project owner's explicit approval):**
>
> 1. **Ambiguity codes: option (b).**
>    - **Kept as is:** the single-code `amb_code` field. Rubric and validator unchanged.
>    - **What to record:** the *primary* ambiguity reason as the one code. Any further theme-specific
>      ambiguity is described in `note`.
> 2. **Duplicate ordering:** "earlier" is decided by the verified batch availability time
>    (`available_at_utc`) first, then the original record sequence (from `gkg_record_id`), as B2-H
>    §4.6 defines. **Never** by page publication time or by the shuffled `item_id`. In practice the
>    annotator only names the other item in `near_dup_of`, and the direction is derived from the
>    working copy at evaluation.
>
> **Points 3–6 stand as assessed below** (compatible; no change).
>
> **Nothing else changes:** the original rubric (B2-I §3), `ANNOTATION_INSTRUCTIONS.md`, filters,
> sampling, thresholds and the sealed key.

- **Unchanged:** the original rubric (B2-I §3), `ANNOTATION_INSTRUCTIONS.md`, the validator rules,
  the sealed key, sampling, filters and thresholds.
- **Two of the six proposals need your decision** before labelling uses them, because they conflict
  with the current tool or with a documented rule. **Four are already compatible.**
- **No implementation change was made.** Only characterisation tests were added: they pin today's
  behaviour.

**Date:** 2026-10-13 17:52 UTC.

**Labels:**

- **[VERIFIED]**: confirmed by a local check or a test.
- **[MEASURED]**: observed directly.
- **[ESTIMATED]**: computed with stated assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

---

## Summary

| # | Issue | Verdict | Change needed |
| --- | --- | --- | --- |
| 1 | Ambiguity codes for three themes | **Needs your decision:** not supported today | Validator change after approval |
| 2 | "Earlier" duplicate | **Needs your decision:** the proposed tie-breaker conflicts with B2-H | None for labelling; a documented direction rule |
| 3 | Annotation timestamp precision | **Compatible** | Documentation only |
| 4 | `company_notice = U` with `R` | **Compatible:** not prohibited | None |
| 5 | Authoritative labelled file | **Compatible:** already implemented | Documentation only (supersedes two older lines) |
| 6 | Empty-title record | **Compatible,** with one caution | Documentation only |

---

## 1. Ambiguity codes for three theme columns

**What the tool does now** [VERIFIED, `annotate.py`]:

- `amb_code` is one free-text CSV field.
- When any theme is `A`, the validator requires **exactly one** code from `A1`–`A6`, `A9`.
- `A2` alone is refused when only gold is `A`.
- `A9` needs a `note`.
- A multi-code value such as `equity:A2;gold:A4` is **rejected**. A new test pins this.

**The gap:** B2-I §3.7 and the instructions define one field and one code. They don't say what to
record when two themes are `A` for different reasons.

**Proposal evaluated** (theme-prefixed codes, semicolon-separated, in the same field):

- **Schema fit:** the CSV column is text, so the value fits without a column change. It is a
  **new value format,** though, and the current validator refuses it. That makes it a rubric change,
  not an existing rule.
- **Proposed minimal, backward-compatible form:**
  - **Single bare code** (`A3`): still valid. It means the same reason applies to every theme marked
    `A`, which is exactly today's meaning.
  - **Prefixed list** (`equity:A2;gold:A4`): new. One entry per theme marked `A`. Prefixes are
    `equity`, `rates` and `gold`, matching `rel_equity`, `rel_rates` and `rel_gold`. Entries are in
    that fixed order, with no spaces and no duplicates.
  - **Rules kept:** `A2` is only valid with the `equity` or `rates` prefix; `A9` still needs a `note`.
- **Evaluation compatibility:** the B2-I estimators use only `rel_* = A` to exclude ambiguous items.
  Codes are descriptive, so precision and recall are unaffected. A later report could count reasons
  per theme.
- **Compatibility risk:** none for existing data, because no labels exist yet.

**Tests required if approved:**

- bare code still valid;
- a prefixed list valid only when its themes exactly equal the themes marked `A`;
- an unknown prefix, wrong order, a duplicate, `gold:A2`, and `A9` without a note are each rejected;
- the existing single-code tests unchanged.

**Decision needed:**

- **(a)** Approve the prefixed form. It is a versioned rubric change (`b2o_annotation_v1.1`), then
  implemented and tested before the first batch.
- **(b)** Keep one code: record the dominant reason and describe the other in `note`. This works
  today and needs no change.

---

## 2. "Earlier" duplicate (`near_dup_of`)

**What the tool does now** [VERIFIED]:

- **Annotator field:** `near_dup_of` must name another existing item. Its direction is **not
  enforced:** a test shows both directions are accepted.
- **Pipeline field:** the read-only `mech_dup` marks same-batch duplicates by record sequence.

**The documented rule** [VERIFIED, B2-H §4.6]: rows are processed causally, "in availability order:
`available_at_utc`, then the `GKGRECORDID` sequence".

**Proposal evaluated** (earliest reliably available timestamp, then stable item ID):

- **Controlling timestamp:** `available_at_utc`. It is the verified, fail-closed availability time.
  `page_pub_ts_utc` must **not** control: B2-G found page times later than their own batch, and B2-K
  keeps page time as a diagnostic only. `batch_ts` is weaker than `available_at_utc`, though the two
  coincide for all 192 batches here.
- **Tie-breaker conflict:** `item_id` is a hash-shuffled presentation order, unrelated to time.
  B2-H already defines the tie-breaker as the record sequence. Ties are not rare: **1,490 of the
  1,493 items share their `available_at_utc` with another item** [MEASURED], because items from the
  same batch share it. The proposal therefore **conflicts with the documented rule**.

**Recommended resolution, consistent with B2-H:**

- **Earlier** = smaller (`available_at_utc`, `batch_ts`, record sequence from `gkg_record_id`).
  `item_id` is only a final fallback, which can never be reached, because record IDs are unique.
- **Practical point:** batch files deliberately carry neither `available_at_utc` nor `gkg_record_id`.
  So the **annotator should only name the other item.** Its direction is derived afterwards by the
  tool from the working copy.
- **Later updates** stay separate records: nothing is ever removed. This is already true.

**Tests required if approved:**

- an evaluation-time function returning the earlier member of each near-duplicate pair;
- tie on availability → record sequence decides;
- page time ignored;
- the pair is symmetric;
- self-reference refused (existing test).

**Decision needed:** accept the B2-H tie-breaker (recommended), or keep the proposal's
stable-item-ID tie-breaker as a documented exception.

---

## 3. Annotation timestamps

**What the tool does now** [VERIFIED]: `labelled_at_utc` accepts `YYYY-MM-DD`,
`YYYY-MM-DDTHH:MMZ` or `YYYY-MM-DDTHH:MM:SSZ`, all UTC. Offsets and local formats are rejected
(tests).

**Source timestamps:**

- `batch_ts` and `available_at_utc` (seconds, `Z`) are written by the tool and never edited.
- `page_pub_ts_utc` is diagnostic.

**Proposal:** UTC ISO 8601 with seconds where supported, without manufactured precision.
**Compatible as is.**

- **Write the full date-time with seconds when you know it,** and a date only when you don't.
- **Never invent seconds.**
- **The system timestamp of each merge** is recorded separately in `working/merge_log.jsonl`.

**Tests:** already present (parametrised accept and reject cases).

**Decision:** none needed.

---

## 4. `company_notice = U` with a relevant theme

**What the tool does now** [VERIFIED]:

- `Y` with any `R` is refused, as the rubric says: "Company and fund notices are never R … at most
  RL".
- `U` with `R` is accepted (test).

**The rubric:** it prohibits `R` only for notices (`Y`). It does not mention `U`.

**Proposal:** allow `U` with `R` when the judgements are independent. **Compatible:** no rule
prohibits it. Recommended practice is to add a short reason in `note`, optional.

- **Evaluation effect:** the company-flag metrics (B2-I §4.6) count `Y` only, so `U` never inflates
  the leakage estimate.

**Tests:** already present.

**Decision:** none needed, unless you would rather treat `U` + `R` as needing a `note`. That would
be a new rule.

---

## 5. The authoritative annotation file

**What the tool does now** [VERIFIED]:

- `annotate init` copied the generated `annotation_A.csv` to `backup/annotation_A.build.csv` and
  `working/annotation_A.working.csv` (all three `11db13e6…`). It refuses to run again.
- Every action re-checks the generated file against `selection_log.json`.
- Only the tool writes the working copy, and every merge is logged.

**Proposal:** generated file immutable; the working copy authoritative. **Compatible,** already
implemented.

**What this supersedes:**

- "label `annotation_A.csv`" in the generated `ANNOTATION_INSTRUCTIONS.md;`
- "same name" in the B2-P gap report.

The instructions file itself stays unchanged: it is one of the hashed build outputs. The evaluation
step will freeze `working/annotation_A.working.csv`.

**Tests:** already present (init, never-overwrite, tamper detection, provenance unchanged).

**Decision:** none needed.

---

## 6. Empty-title record

**The record** [VERIFIED]: only one, item **D0291**. It is not an overlap row, has `mech_dup =
ORIGINAL`, no page time, and a URL with three path segments.

**What the tool does now:** it is retained like every other item. The validator never reads titles
(test), so it neither forces nor forbids any label.

**The rubric:**

- **Allowed evidence:** "the source domain and full URL", not only the title (B2-I §3.1).
- **A1:** "Title uninformative: generic, truncated, a site name, live updates".

**Proposal:** retain it and mark it per the uninformative-title guidance, with no unsupported
inference. **Compatible,** with one caution: because the URL is allowed evidence, forcing `A`/`A1`
on every theme without looking would *discard* permitted evidence.

**Recommended reading, which keeps the rubric:**

- **URL decides the theme:** if the URL clearly decides a theme, label it on that evidence.
- **Otherwise:** `A`, with `amb_code = A1`.
- **Polarity:** only for a theme labelled `R`; `UNC` if the direction is not evident from the URL.
- **`note`:** "empty title; judged on URL".

**Tests:** already present (title-agnostic validation).

**Decision:** none strictly needed. Confirm if you would rather always use `A`/`A1` for it.

---

## 7. Validation [VERIFIED]

| Check | Result |
| --- | --- |
| `pytest tests/backend/data/gdelt -q -p no:cacheprovider` | **185 passed, 0 failed:** 175 before, plus 10 characterisation tests in `test_annotate.py` |
| Compile with warnings as errors; unused-import scan | OK; 0 |
| Labels created | **None.** The working copy is still byte-identical to the original (`11db13e6…`); no batch folder; no AI-suggestion file |
| Generated annotation files and the sealed key | Unchanged: `11db13e6…`, `21172900…`, `cc45a3df…`, `e9d73df6…`, `15fa2302…`. The key's fingerprint only was compared; it was not opened |
| Downloaded sample | Unchanged: full audit equal to B2-O (states, manifest-order hash, SHA-256, CRC, requests, bytes, day files) |
| Network | None |

**Changes:**

- **Created:** this report.
- **Modified:**
  - `tests/backend/data/gdelt/test_annotate.py` (10 tests added, none changed);
  - `docs/MEMORY.md`.

**Not done:** no commit or push.

---

## 8. Remaining blockers before `export-batch`

`export-batch` works today. These are **procedural** blockers, so you don't label under rules you
later change:

1. **Decision on proposal 1:**
   - **(a) prefixed codes:** I then implement and test them, plus a short addendum to the quick
     reference, before your first batch.
   - **(b) one code plus `note`:** no change; you can start immediately.
2. **Decision on proposal 2's tie-breaker:** the B2-H record sequence (recommended) or the item-ID
   exception. **This does not block labelling,** because you only name the other item, but it should
   be fixed before evaluation.
3. **Optional confirmations** for proposals 4 and 6, if you'd rather apply the stricter variants.

**Once 1 is decided** (and 2 ideally too), start with:

```text
.venv/Scripts/python.exe -m wealthpilot.data.gdelt annotate export-batch --size 50 --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml
```

**Not authorised:** the confirmation sample, full acquisition, B3.
