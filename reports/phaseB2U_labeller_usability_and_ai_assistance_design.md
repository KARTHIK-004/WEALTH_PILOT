# Research Enhancement Track — Phase B2-U: Labeller Usability Fix and AI-Assistance Design

**Result:**

- **The labeller is fixed** so a conflicting answer is caught and explained before saving.
- **The AI-suggestion workflow is documented, not built or started.** It stays blocked until all 312
  overlap items are labelled and you approve it.
- **Not touched:**
  - no label was created and no item was labelled for you;
  - D0001 is **not saved**;
  - the sealed key was not opened;
  - no network request was made.

**Date:** 2026-10-15 (UTC).

**Labels:**

- **[VERIFIED]**: confirmed by a local check or a test.
- **[MEASURED]**: observed directly.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: needs an approval or evidence not available.

---

## 1. State on disk before any change [VERIFIED]

| Check | Result |
| --- | --- |
| Labelled rows | **0 of 1,493** (0 of 312 overlap) |
| Working copy | Byte-identical to the original (`11db13e6…`); the merge log has only the init and export entries |
| D0001 | **Not saved.** The rejected answers were never written |
| AI-suggestion file | Does not exist |
| Sealed key, backup, Batch 1, downloaded sample | Unchanged (fingerprints; the sample passes its full audit) |

---

## 2. The exact cause of the usability problem [VERIFIED from `labeller.py`]

- **Where answers were checked:** the old `collect()` asked every field in a fixed sequence and never
  compared one answer with another. The rubric rule "company notice `Y` can not have an `R` theme" was
  only applied inside `annotate.save_item`, **after** you confirmed "Save?".
- **What a refusal did:** on a validator error the old code printed "Please enter this item again" and
  jumped back to the top of the loop. That **discarded every answer** for the item.
- **The rule itself was never wrong.** The validator was right to refuse; the tool let you build an
  invalid item and then lost your work.

---

## 3. What changed (labeller only; the rubric and validator are untouched)

**Files:**

- `backend/wealthpilot/data/gdelt/labeller.py`: rewritten around one answers dictionary.
- `backend/wealthpilot/data/gdelt/annotate.py`: one new helper, `human_only_errors()`.
  - **Behaviour:** it calls the unchanged `row_errors` validator, so the labeller never needs to name
    the AI-suggestion file.
  - **Why:** a test asserts that the labeller source never mentions the key or the AI file.
- `tests/backend/data/gdelt/test_labeller.py`: 27 tests (was 14), several rewritten for the new flow.

**New behaviour:**

| Requirement | How it works now |
| --- | --- |
| The company-notice rule is explained **before** confirmation | The rule is on every item's header. The company prompt says "Y means no theme may be R". `?` prints the full definitions. The review screen repeats it whenever it applies |
| `company_notice = Y` identifies the conflicting `R` fields | Entering `Y` while any theme is `R` prints "Conflict: company_notice is Y, but these themes are R: …" and asks you to reconsider **each** `R` theme. Enter keeps `R`. Entering `R` while the notice is already `Y` also warns at once |
| Nothing is changed or invented for you | The only automatic change is clearing an answer that no longer applies (for example the polarity of a theme you changed from `R`), and the tool says so |
| Go back without restarting | `<` returns to the previous answer, shown with its current value (Enter keeps it). Later answers are kept |
| A failed validation keeps the answers | A **review screen** lists every answer and every problem. Type a number or a field name to change just that answer. If a save is still refused, you return to the review screen with all answers intact |
| Only a fully valid item is saved | `Y` is refused while the validator reports a problem. The save goes through `annotate.save_item`: validate, atomic write, log |
| The validator is not bypassed | The review calls the same `row_errors`; a test replaces it with an always-failing stub and shows saving is blocked |
| Fewer wrong answers at the prompt | A near-duplicate must be an existing other item ID; `A2` (country unclear) is not offered when only gold is ambiguous |
| Corrections | `--item Dxxxx` loads the current labels into the review screen. You edit what you need, and a reason is required and appended to the note. No change means nothing is saved |

**Everything else in the labeller is unchanged:**

- it fills only session facts (initials, `human`, `own`, the UTC time at saving);
- it shows only item ID, date, domain, URL, title and the duplicate mark;
- it covers the overlap subset only;
- it never reads the sealed key or any AI file.

**One test change, disclosed:** a new assertion first banned the word "suggestion" from all labeller
output. That matched the tool's own notice, "No AI suggestions are shown for these items", so I removed
the word from the ban list. The real checks remain: planted marker data in both the key and the AI file
never appears in the output, and the source never names either file.

---

## 4. D0001 [no labels chosen]

I did **not** choose D0001's labels and made no assumption about it. When you run the command, it shows
D0001's source context (date, domain, URL, title, duplicate mark).

**The constraint**, from the existing rubric (B2-I §3.5):

- A **company or fund notice** is one of: a holdings disclosure (including a position in QQQ, GLD or AGG),
  an analyst rating or price target, an insider trade, a dividend declaration, or one company's earnings.
- If you judge the item to be such a notice (`company_notice = Y`), **no theme may be `R`.** At most `RL`.
- If you judge it **not** to be one, answer `N` (or `U` if you can't tell).
- Relevance and the company-notice judgement are separate questions, answered separately.

Whether D0001 is a notice is your call. The tool only enforces the rubric.

---

## 5. AI assistance for the non-overlap items [PROPOSED; not built, not started]

**Compatible with the documented design** [VERIFIED]: `ANNOTATION_INSTRUCTIONS.md` and B2-I §4.5 allow
AI suggestions in a **separate** file `ai_suggestions_A.csv` with `annotator_type = ai`, provisional and
never independent human ground truth. The `label_basis` values `accepted_ai`, `corrected_ai` and
`rejected_ai` already record what you did with each one.

**Gates:**

- All 312 overlap items must be labelled by you first.
- You must give an explicit go-ahead.
- Until then the tool offers no way to create or show suggestions.

**What the future suggestion file needs** (new, beyond the current schema), per your requirements:

| Field | Content |
| --- | --- |
| `item_id` | Non-overlap items only. An overlap item must never appear in this file |
| the label columns | The same columns and allowed values as the rubric |
| `annotator_type` | `ai` |
| `model_id` | The model's identifier, recorded as reported by the session, never invented |
| `rubric_version` | `b2o_annotation_v1` plus the B2-R/B2-S decisions |
| `generated_at_utc` | When generated |
| Inputs used | Title, URL, domain and date only: the same evidence a human gets |

**How it would run:**

1. Suggestions are generated offline and written once. The file's fingerprint is recorded **before** you
   see any item.
2. In `annotate label --with-suggestions`, each item shows the suggestion, clearly marked AI-generated.
   Enter accepts it, changing any answer corrects it, and rejecting it starts you from a blank item.
3. What is saved is always **your** label (`annotator_type = human`). `label_basis` records
   `accepted_ai`, `corrected_ai` or `rejected_ai`. The evaluation reports results by basis, and never
   describes AI output as human ground truth.

**Known gap to close before that workflow** [VERIFIED]: today the validator only checks that
`ai_suggestions_A.csv` *exists* when a label says `accepted_ai`. It does not check that the file holds
a suggestion for that item, or that the item is not an overlap item. The future change must add both
checks, with tests.

---

## 6. A conflict in the documents that needs your decision

**The documented plan:** `ANNOTATION_INSTRUCTIONS.md` and B2-J say the AI works as a **blind second
labeller** for the 312 overlap items (`annotation_B.csv`), so the evaluation can report
**human-versus-AI agreement**.

**Your B2-U instruction:** "Do not generate, display or save AI suggestions for any overlap item."

**These are not the same thing,** but the current instruction rules out the plan as written. The B2-P
evaluation cannot report human-versus-AI agreement without AI labels for the overlap items.

**Choose one before the evaluation:**

- **(a) Keep your rule.** No AI labels on overlap items at all. The evaluation then has no agreement
  figure, and says so.
- **(b) Allow blind AI labels on the overlap items only after all 312 human labels are saved and
  fingerprinted.** They are never shown while you label, are stored separately (`annotator_type = ai`),
  and are used only to measure agreement. They are not suggestions, so you never review them.

Nothing is generated now under either choice.

---

## 7. Validation [VERIFIED]

| Check | Result |
| --- | --- |
| `pytest tests/backend/data/gdelt -q -p no:cacheprovider` | **212 passed, 0 failed.** 199 before this phase; the labeller file grew from 14 to 27 tests |
| New regression tests | A company-notice conflict gets an explanation and a prompt for each `R` theme; reconsidering is optional and nothing changes silently; `R` entered after `Y` warns at once; `<` keeps other answers and at the first question is harmless; editing at the review screen clears only what no longer applies; the review uses the real validator and blocks saving (stub test); a refused save keeps all answers and does not re-ask; the validator still refuses `Y` with `R`; atomic write failure; quit mid-item and mid-review saves nothing, then resumes; an existing annotation is untouched by a later session; `?` explains the rule; overlap-only; corrections need a reason, and no change saves nothing; no key or AI data appears |
| Static checks | Compile with warnings as errors: OK. Unused imports: 0 |
| Real data after the work | 0 labelled. All fingerprints unchanged: generated files, backup, working copy (`11db13e6…`), Batch 1 (`105ce3d4…`), sealed key (fingerprint only). The downloaded sample passes its full audit. `pip freeze` fingerprint `3393be50…` |
| A start on the real data with no input | Stopped at the initials prompt and saved nothing |
| Network | None. Nothing committed |

---

## 8. Exact next steps for you

**Resume labelling:**

```text
.venv/Scripts/python.exe -m wealthpilot.data.gdelt annotate label --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml
```

- **First item:** it starts at D0001.
- **Type `?`** for the definitions.
- **Type `<`** to go back one answer.
- **At the review screen,** type an answer's number or field name to change it, and `Y` only when no
  problems are listed.
- **Quit or skip:** `q` quits and `s` skips. Anything already saved is kept.
- **Progress:**
  ```text
  .venv/Scripts/python.exe -m wealthpilot.data.gdelt annotate status --config datasets/raw/gdelt/english_gkg_v1/provenance/run_config.yaml
  ```

**Decisions for later, not blocking labelling:**

1. When all 312 overlap items are done: do you want AI suggestions for the other 1,181?
2. The overlap agreement question in section 6: (a) or (b)?
