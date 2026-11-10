# Research Enhancement Track — B2-T: AI-Assisted Annotation for All 1,493 Items (Methodology Proposal)

> **Update (2026-10-16, master completion run):** the validator gap reported in §2.4 and §13 step 6 is fixed. An
> AI-based `label_basis` now needs a valid suggestion **for that item**, and the file is checked for
> columns, duplicates, overlap items and rubric validity. See
> `reports/phaseB2_remaining_work_and_completion_report.md`. The rest of this proposal is unchanged and
> still unapproved.

**Status: PROPOSAL ONLY. Nothing here is approved.**

- **What this report does:** inspects the repository, explains how AI assistance would change the B2
  experiment, and designs a safe option for your decision.
- **What was not done:** no annotation was run, no AI model or provider was invoked, and no label or AI
  suggestion was generated.
- **What was not touched:** no annotation, backup, working copy, sample or sealed key was altered or
  opened, and no file other than this report and a short `MEMORY.md` entry was written.
- **Not a decision:** requesting this proposal is not approval of a methodology change.

**Date:** 2026-10-16 (UTC).

**Name note:** an earlier step in this conversation was also called "B2-T" (validating Batch 1). It
produced no report file, so this file name does not collide with anything.

**Labels:**

- **[VERIFIED]**: confirmed by reading the repository or running a read-only check.
- **[MEASURED]**: observed directly in the files.
- **[ESTIMATED]**: computed with stated assumptions.
- **[PROPOSED]**: awaiting your approval.
- **[UNVERIFIED]**: not confirmed.

---

## 1. Executive summary

- **Current state** [VERIFIED]: 1,493 items, 312 in the human-only overlap set and 1,181 outside it.
  **0 labelled, 0 AI suggestions.** Every protected artifact is intact.
- **Why the change matters:** the original design keeps 312 items human-only so that human labels can be
  compared with AI labels. If AI suggestions are visible when those items are labelled, the human labels
  are no longer independent. Any agreement figure would then partly reflect anchoring and automation
  bias, not two independent judgements.
- **What can still be saved:** nothing has been labelled yet, so no independent human labels are being
  lost. What is at stake is the *option* of having an independent baseline. Preserving it for 150 items
  costs about 0.6–1.2 hours of labelling [ESTIMATED]; for all 312 items, 1.3–2.6 hours.
- **Recommendation** [PROPOSED]: do **not** reuse the original dataset for AI-assisted labels. Use a
  **separately versioned dataset** with clearly separate conditions. My preferred design is a hybrid
  (Option C, section 5):
  - AI suggestions are generated **blind** for all 1,493 items, without seeing any human label.
  - A **pre-registered blind subset** of the overlap items (150 proposed) is labelled by you *before*
    seeing any AI output. That keeps a valid, if single-annotator, human-versus-AI comparison.
  - The remaining 1,343 items are labelled with AI suggestions visible, and each is recorded as
    AI-assisted.
- **Fully AI-assisted for all 1,493** (Option B) is feasible and cheaper in effort, but it gives up the
  independent comparison. Its labels can support acceptance and correction rates, not an independent
  agreement claim.
- **Existing code** [VERIFIED]: no AI-generation or provider code exists in the GDELT tool, only
  validation hooks and instruction text. The approval gate refuses an AI-annotation approval it does not
  know, so a flag alone cannot start anything.
- **Five separate approvals** are needed before anything runs (section 12). Approving one does not imply
  the others.
- **One housekeeping finding** [VERIFIED]: the GDELT network and development-sample switches are still
  on, though that acquisition is finished (section 2.5). I did not change them.

---

## 2. Verified current repository state

### 2.1 Counts [MEASURED from `annotation_A.csv` and its working copy]

| Item | Value |
| --- | ---: |
| Review items (`D0001`–`D1493`, unique IDs) | **1,493** |
| Overlap set (`overlap_subset = Y`) | **312** |
| Non-overlap set | **1,181** |
| Rows in `annotation_B.csv` | 312; the same IDs as the overlap set |
| Labelled rows in the working copy | **0** (0 of 312 overlap) |
| AI suggestions | **0**: no `ai_suggestions_A.csv`, no suggestion artifact anywhere under `datasets/` |
| Working copy vs original | Identical in every row |

### 2.2 Composition of the two sets [MEASURED; permitted columns only]

| Property | Overlap (312) | Non-overlap (1,181) |
| --- | --- | --- |
| Batch year (2021 / 2022 / 2023) | 18 / 135 / 159 | 42 / 542 / 597 |
| Distinct source domains | 230 | 696 |
| Distinct batches | 138 | 185 (136 shared with the overlap set) |
| Duplicate mark (original / syndicated / same-URL) | 262 / 47 / 3 | 1,007 / 167 / 7 |
| Title length, median characters (10th–90th percentile) | 67 (43–96) | 65 (41–98) |
| Titles under 30 characters | 9 | 41 |
| Empty titles | 0 | 1 (`D0291`) |

- **The two sets look alike** in year mix and title length, so the overlap set is a reasonable proxy
  for the rest.
- **Only three normalised titles** appear in both sets, so near-duplicate leakage between them is small.
- **Titles are short** (median about 66 characters). That bears on how much an AI can decide from a
  headline alone (section 8.4).

### 2.3 Fingerprints [VERIFIED]

| Artifact | SHA-256 (first 16) | Notes |
| --- | --- | --- |
| `annotation_A.csv` | `11db13e668bd3da8…` | Equals the value recorded in `selection_log.json` |
| `annotation_B.csv` | `211729002893c1e4…` | Overlap subset; equals the recorded value |
| `ANNOTATION_INSTRUCTIONS.md` | `e9d73df65fd2465c…` | Equals the recorded value |
| `backup/annotation_A.build.csv` | `11db13e668bd3da8…` | Byte-identical to the original |
| `working/annotation_A.working.csv` | `11db13e668bd3da8…` | Byte-identical to the original |
| `working/batches/batch_001_overlap.csv` | `105ce3d4bc5d1fd2…` | Unlabelled export |
| `working/merge_log.jsonl` | `a2b7cde1ccd0d78a…` | Two events: `init`, `export` |
| `manifest/manifest.sqlite` | `ea734b8a6e9a8ce1…` | Acquisition manifest (SQLite; the hash can change if SQLite checkpoints its log) |
| Sample list (stage D) | `a459a3fb44afd7e1…` | Pre-registered, unchanged |

**Sealed key** [VERIFIED, without reading it]: `key_sealed.csv` exists, 142,900 bytes, last modified at
the B2-O build (2026-10-13 16:58 UTC). Its recorded fingerprint is `cc45a3df0465f2e7…`. **This time I
neither opened it nor recomputed its hash:** I compared only its size and modification time with the
build record.

### 2.4 What the existing code can and cannot do [VERIFIED]

| Capability | Finding |
| --- | --- |
| AI-suggestion generation, model or provider abstraction | **None.** No reference to any LLM provider, API key or model in the GDELT tool or its tests |
| Labelling | `labeller.py` is human-only. It never reads AI files or the key, and writes `annotator_type = human`, `label_basis = own` |
| Validator hooks | `annotate.py` allows `label_basis` values `own`, `accepted_ai`, `corrected_ai`, `rejected_ai`; refuses any AI-based basis on overlap rows; and refuses an AI-based basis unless `ai_suggestions_A.csv` exists |
| **Gap** | The validator checks only that the file *exists*. It does not check that the file holds a suggestion for that item, nor that the item is outside the overlap set. A future workflow must close this |
| Approval gate | `config.py` accepts only `dev_sample`, `confirmation_sample` and `full_acquisition`. An offline test with an `ai_annotation` approval record was **refused** ("unknown approval names"). So a flag or record alone cannot authorise AI annotation |
| Provider libraries | `google-genai` 0.3.0 is declared in `backend/pyproject.toml` (approved stack). `anthropic` is not installed. An `openai` package (3.13.0) is installed but not declared and unused here |
| Isolation | Tests require the GDELT tool to import only the standard library, PyYAML and itself. A provider SDK inside it would need that rule relaxed for one module |
| Tests | 212 pass (run earlier today, before this task) |

### 2.5 Discrepancies and observations (reported, not resolved)

1. **The GDELT network and development-sample switches are still on** [VERIFIED].
   `NETWORK_ENABLED_IN_THIS_BUILD` and `DEV_SAMPLE_ENABLED_IN_THIS_BUILD` are `True`, and the local
   `run_config.yaml` still holds the development-sample approval. The acquisition finished on
   2026-10-13. A repeat `fetch-sample` would pass the gate. I expect it to do almost nothing, since every
   slot is already processed [UNVERIFIED, not run]. **Proposal:** lock both switches and mark the
   approval consumed, in a small separately approved change. This also matters here, because a
   network-capable tool should not stay enabled by default.
2. **`ANNOTATION_INSTRUCTIONS.md` is partly superseded.** The file is hashed and unchanged. It still
   says to label `annotation_A.csv` and describes an AI as blind second labeller for the overlap set. The
   B2-Q, B2-R, B2-S and B2-U reports supersede those lines: the working copy is authoritative, and AI on
   the overlap set is an open decision.
3. **B2-U's open question stands:** whether blind AI labels on the overlap items are allowed at all. This
   proposal turns that question into a design choice (section 5).
4. **A project rule applies:** `CLAUDE.md` forbids adding a library outside the approved list without
   asking. That affects the provider choice (section 8.1).

---

## 3. The original research design

**Source of the design:** B2-I §3–4, B2-J §2, `ANNOTATION_INSTRUCTIONS.md`.

- **Sample:** 192 pre-registered batches yielded 1,493 items in seven cells, chosen by a seeded hash
  (seed `wealthpilot-b2i-filter-review-v1`). The sealed key records each item's cell and filter results.
- **Overlap set:** 312 items (about 20.9%), selected by a content-independent hash rule: the first 8 hex
  digits of SHA-256(`seed|iaa|record_id`) below `0x33333333`.
- **Purpose of the overlap set:** to measure agreement between independent labellers. B2-I §4.5 allows
  "Claude as a second annotator … disclosed as model labels … never the only basis for a precision
  figure."
- **Plan (c), your choice on 2026-10-13:** you plus disclosed AI assistance. AI suggestions are
  provisional and never human ground truth. B2-U added your rule: no AI output on overlap items while
  you label.
- **Pre-registered use of the labels:** the B2-I §4.7 thresholds (precision at least 0.70 with lower
  bound 0.60; pooled capture recall at least 0.90) decide whether `gdelt_filter_v1` is frozen or revised.
  They were written assuming human labels.
- **Protected artifacts:** the sample, its fingerprints, the overlap definition and the sealed key. All
  stay unchanged in every option below.

---

## 4. How AI assistance changes the 312-item overlap experiment

1. **It is no longer a human-only condition.** Once suggestions are visible to the annotator, the
   overlap items stop being human-only. The original design reserved them *precisely* to avoid that.
2. **Exposed labels are not independent labels.** A human label made after seeing a suggestion is a
   different measurement from one made without it.
3. **Agreement results would be contaminated.** Anchoring (the first number seen pulls the judgement),
   automation bias (deferring to a machine) and direct copying all raise agreement without improving
   accuracy. I cannot separate them afterwards.
4. **The original overlap design must stay intact as history.** Its membership, `annotation_B.csv` and
   fingerprints remain as provenance, even if a new protocol is adopted.
5. **Three things must stay distinguishable:** (a) an independent human label, (b) a raw AI suggestion,
   and (c) a human label made after seeing a suggestion. They must never share a field value. In
   particular, the existing `label_basis = own` must keep meaning "no AI seen". It must not be reused for
   an AI-exposed label, and neither should `rejected_ai`, because a rejected suggestion has still been
   seen.
6. **Nothing is silently relabelled.** No human label exists today, so none can be mislabelled. If any
   appear in the original working copy before this protocol starts, they stay in that dataset and keep
   their original meaning.
7. **Further caveats, true under any option:**
   - **Single annotator:** there is one human annotator, so even the original design measured
     human-versus-AI agreement, never two-human agreement. The human's own reliability is unmeasured
     unless some items are re-labelled later.
   - **Model hindsight:** a model trained on text that postdates 2021–2023 may "know" later events,
     while the rubric forbids hindsight.
   - **Shared lineage:** if the labelling model is from the same family that helped design the rubric
     and filters, errors may be correlated.

---

## 5. Recommended design and alternatives [PROPOSED; your choice]

**Recommended: a separately versioned dataset with separate, labelled conditions.**

- **Why not reuse the original files:** the original dataset, its working copy and its sealed key
  describe a human-only design. Mixing exposed and unexposed labels into those files would blur the
  provenance that the evaluation depends on.
- **Cost of a new dataset:** one more set of artifacts and a small schema extension. That is small next
  to the cost of an unusable comparison.
- **Both datasets stay valid.** The original one becomes the "human-only" record, and the new one the
  "AI-assisted" record.

| | **A. Original design** | **B. Fully AI-assisted** | **C. Hybrid (recommended)** | **D. Blind-then-reveal for all** |
| --- | --- | --- | --- | --- |
| What happens | You label the 312 overlap items blind. The 1,181 others are AI-assisted | AI suggestions visible on all 1,493 | AI generates blind for all 1,493. You label 150 overlap items blind. The other 1,343 are AI-assisted | You label all 1,493 blind first, then see suggestions and may revise |
| Independent human-vs-AI comparison | **312 items** | **None** | **150 items** (interval half-width about ±6 points at 80–90% agreement) | **1,493 items**, on the first-pass labels |
| Anchoring risk | None on 312; present on 1,181 | On all items | None on 150; present on 1,343 | None on first-pass labels; revisions are exposed |
| Your effort [ESTIMATED, 15–30 s per item] | 312 blind: 1.3–2.6 h, then AI-assisted review of 1,181 | AI-assisted review of 1,493 (review speed unmeasured) | 150 blind: 0.6–1.2 h, then AI-assisted review of 1,343 | 6.2–12.4 h, no saving from AI |
| Needs methodology change | Yes: blind AI labels on the overlap set (B2-U question) | **Yes: replaces the overlap design** | Yes, but keeps an independent subset | Yes, but AI adds no speed |
| Supports the B2-I §4.7 thresholds | Yes, on mostly independent labels | Only as AI-assisted labels; weaker evidence | Yes; sensitivity check on the blind subset | Yes |
| Main weakness | Smallest AI-assistance benefit | No independent check at all | Blind subset smaller than 312 | Defeats the purpose of AI assistance |

**Why C over A:** B2-U asked for no AI output on overlap items. C keeps that for the 150 blind items,
and still lets AI help on the rest. A needs no new protocol but gives AI help on only 1,181 items.
Under either option, the blind subset must be fixed **before** any suggestion is generated (section 6).

**Why not B alone:** it is the cheapest option and is legitimate if you accept that the result cannot
support an independent agreement claim. If you choose B, the report must state that plainly and all
figures must be labelled "AI-assisted".

**Subset size:** 150 is a trade-off, not a derived number. Interval half-widths [ESTIMATED, Wilson 95%]
at observed 80% agreement: 312 items ±4.4 points; 200 ±5.5; 150 ±6.4; 100 ±7.8; 50 ±10.9. Items within a
batch are correlated, so the real intervals are somewhat wider.

**How the blind subset would be chosen** [PROPOSED]: sort the 312 overlap items by
SHA-256(`seed|b2t-blind|record_id`), take the first 150, and commit the list and its fingerprint **before
any suggestion exists**. That rule is deterministic and uses no content.

---

## 6. Proposed workflow and architecture [PROPOSED; nothing is built]

**Principles:**

- **New code, new names:** additive code in a new module group under `backend/wealthpilot/data/gdelt/`.
  Nothing in the existing labeller, validator or acquisition code changes behaviour.
- **Separate gate:** a new approval kind (`ai_annotation`), a new build lock
  (`AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD`, default `False`) and a separate run command. It is not tied to
  the GDELT network switch.
- **Dry run first:** a dry run invokes no provider and prints only counts, a token estimate, prompt
  hashes and output paths.
- **Execution:** needs an approval record **and** a command-line confirmation **and** an unlocked build
  lock. A flag or record alone does nothing.

### Stage A: immutable source snapshot

1. A snapshot command copies the following, read-only, into the new dataset folder's `snapshot/`:
   `annotation_A.csv`, `annotation_B.csv`, the build backup, the working copy as of that moment,
   `merge_log.jsonl`, `selection_log.json` and a copy of the manifest.
2. It writes `SNAPSHOT_FINGERPRINTS.json` with the SHA-256, size and modification time of every file.
   The sealed key is **not copied**; only its recorded fingerprint is noted.
3. It verifies each copy against the original, and refuses to run if the destination exists.
4. The original working copy is **never** an output destination. It is read through the snapshot only.

**Versioning mechanism:** none exists beyond hashes in `selection_log.json` and a git-ignored data
folder. I propose the snapshot plus a per-dataset `fingerprints.json` (section 7). Data stays out of Git;
the tracked report records the hashes.

### Stage B: AI suggestion generation

Defined in section 8. In short: stored context only, one validated JSON object per item, raw responses
kept verbatim and separate from human labels, and no network retrieval of article text.

### Stage C: human review

Defined in section 9.

### Stage D: versioned outputs

Defined in section 7.

### Stage E: evaluation

Defined in section 10. It runs offline, after labels are frozen and fingerprinted. The sealed key opens
only after that freeze, as in B2-P.

---

## 7. Artifact paths and versioning [PROPOSED]

**Location** (git-ignored through `datasets/raw/*`): a sibling of the original review folder, never inside it.

```text
datasets/raw/gdelt/english_gkg_v1/review/b2t_ai_assisted_v1/
  config/experiment_v1.yaml                 # protocol id, approvals, provider, model, prompt+rubric hashes, caps; no secrets
  snapshot/                                 # read-only copies + SNAPSHOT_FINGERPRINTS.json (Stage A)
  inputs/ai_input_v1.jsonl                  # approved input fields only, with a fingerprint per item
  blind_subset_v1.csv                       # the pre-registered blind item IDs + selection fingerprint (committed first)
  suggestions/ai_suggestions_raw_v1.jsonl   # one record per attempt, append-only, verbatim provider responses
  suggestions/ai_suggestions_valid_v1.csv   # derived: validated suggestions, one per item
  review/annotation_b2t_v1.csv              # human-reviewed labels (new schema, below)
  audit/events_v1.jsonl                     # append-only, hash-chained
  fingerprints.json                         # SHA-256, size, time for every artifact; changed only by the tool
```

| Artifact | Format | Why | Fingerprint and change tracking |
| --- | --- | --- | --- |
| Immutable original sample | CSV (copies) | Matches the existing convention | Hashes in `SNAPSHOT_FINGERPRINTS.json`; files set read-only; re-verified at every run |
| Pre-existing independent human labels | CSV, left in the original working copy | They stay where they were made | Recorded in the snapshot; never modified |
| Raw AI suggestions | JSONL, append-only | Keeps verbatim responses and failures | SHA-256 per response, plus a file hash locked **before** any review starts |
| Human-reviewed AI-assisted labels | CSV, new schema | Same rubric columns as the original | The tool writes it; the hash is logged after every save |
| Audit log | JSONL, hash-chained | Each event holds the previous event's hash, so deletions or edits are detectable | Chain head recorded in `fingerprints.json` |
| Configuration and provenance | YAML + a tracked report | Human-readable; the report carries hashes only | Config hash recorded in every run and event |

**New label schema `b2t_annotation_v1`** keeps the original rubric columns and adds provenance:

| Added field | Values | Purpose |
| --- | --- | --- |
| `protocol_id` | e.g. `b2t_hybrid_v1` | Ties every row to its experimental condition |
| `ai_exposure` | `none` / `seen` | **The key independence flag.** `none` only if no suggestion was shown before the label was saved |
| `label_origin` | `human_blind`, `accepted_ai`, `edited_ai`, `rejected_ai_after_seeing`, `human_uncertain` | Distinguishes independent labels, accepted suggestions, edited suggestions, and rejections after exposure |
| `suggestion_ref` | Suggestion ID + SHA-256 | Links the label to the exact suggestion shown |
| `reviewer_id`, `reviewed_at_utc`, `review_seconds` | Initials, ISO time, seconds | Who, when, and a coarse effort measure |
| `edit_reason_code` | `title_misread`, `url_context`, `rubric_boundary`, `other` (+ note) | Why a suggestion was changed. Metadata, not a new rubric label |

**Rules:**

- **No renaming or reuse of original values:** `own` keeps its meaning of "no AI seen", and the original
  `b2o_annotation_v1` files are never edited.
- **Rubric unchanged:** no new relevance, polarity or company-notice value is introduced.

---

## 8. AI input and output schema [PROPOSED]

### 8.1 Provider abstraction and configuration

A small interface, `SuggestionProvider.suggest(item_batch, prompt) → raw_response`, with three
implementations:

- **`DryRunProvider`:** raises if called, so a dry run provably makes no call.
- **`FixtureProvider`:** returns scripted responses; used only by tests.
- **A real provider adapter:** inert until approved.

**Provider options, for your decision:**

| Option | For | Against |
| --- | --- | --- |
| Gemini through the already-declared `google-genai` 0.3.0 | No new dependency; already in the approved stack | The isolation test must be relaxed for one adapter module; the account's key and costs are yours to confirm; the provider's data-retention and training terms are [UNVERIFIED] |
| A provider REST API through the standard library (`http.client`) | Keeps the isolation rule and adds no dependency | More code to write and test; structured-output features are hand-rolled |
| An interactive Claude Code session writes the suggestions | No API key and no new network path | **Weak audit trail:** no provider request IDs, a less verifiable model identity, and the suggestions pass through this conversation, where they could be seen. Not recommended for a blind subset |

**Configuration** (in `experiment_v1.yaml`, no secrets): provider name, exact model ID, temperature
(proposed 0), maximum output tokens, request and token caps, a cost cap computed from a unit price **you**
supply, one request at a time by default, timeouts, and the retry policy. The API key is read from an
environment variable at run time and never stored, logged or echoed.

### 8.2 Input fields the model may see

| Sent | Not sent |
| --- | --- |
| Opaque item ID, date, source domain, URL **as text**, decoded title | Record IDs and batch stamps; availability and page timestamps; the duplicate mark; the overlap flag; **any** sealed-key field (cell, weights, filter results, themes, tone); other items' labels; any human label |

**No network retrieval:** the default is stored context only. Source URLs are **not** fetched. Fetching
article text would be a separate, explicit approval; it also raises copyright, availability and
reproducibility issues.

**Fingerprint:** each input record gets `input_fingerprint = SHA-256(canonical JSON of the sent fields)`.

### 8.3 Prompt and rubric

- **Rubric:** the definitions from `phaseB2Q_annotation_quick_reference.md` and the B2-R/B2-S decisions,
  verbatim, with a recorded `rubric_version` and SHA-256.
- **Examples:** only synthetic few-shot examples, marked as such. No real item goes into a prompt as an
  example.
- **Prompt:** versioned and hashed; one item per request by default (batching saves tokens but lets items
  influence each other).

### 8.4 What the model is asked to return, per item [PROPOSED]

| Field | Handling |
| --- | --- |
| `rel_equity`, `rel_rates`, `rel_gold` | `R` / `RL` / `I` / `A`, same values and meanings as for you |
| `amb_code` | One primary code, only when a theme is `A` (decision b) |
| `company_notice` | `Y` / `N` / `U`. `Y` with any `R` is invalid, by the existing validator |
| Polarity | **Not requested in v1.** The review does not analyse polarity (B2-I §3.8), and polarity is where model hindsight is most likely. Fields stay blank |
| Duplicate / `near_dup_of` | **Not requested.** One item per request cannot see the others. The pipeline's duplicate mark and your review cover it |
| `note` | One short sentence of rationale, limited to the title and URL |
| `evidence_spans` | Exact substrings of the title or URL that support each non-`I` label. The tool **rejects** a suggestion whose spans are not literally present: this catches fabricated evidence |
| `uncertainty` | An ordinal `low` / `medium` / `high` per theme, plus `needs_evidence` when the answer would depend on article text |

**Fields that need more than the headline or an explicit unknown** [VERIFIED limitation]:

- **Relevance:** many themes cannot be decided from about 66 characters. The model should return `A`
  with a code, not guess.
- **Company-notice status:** often needs the body text. `U` is the honest answer.
- **Country (A2):** often unknown from a title.

### 8.5 Validation, failures and recording

1. **Parse** the response as JSON; **validate** the schema, allowed values and conditional rules with the
   **existing rubric validator**, using `annotator_type = ai`; then **check** the evidence spans.
2. **Malformed, incomplete or contradictory output** (for example `Y` with `R`) is stored verbatim with
   status `invalid_output`. It is **never repaired**. One re-request with a fixed, versioned
   "return only valid JSON" instruction is allowed. If it fails again, the item gets no suggestion and
   goes to you unaided.
3. **Provider failures** (timeout, rate limit, 5xx) get bounded retries with backoff (default 3, never
   silent). Each attempt is recorded with its outcome, latency and any request ID.
4. **Recorded per suggestion:** provider, exact model ID and any version reported, prompt version and
   hash, rubric version and hash, parameters, timestamp (UTC), attempt number, token counts, the input
   fingerprint, and the SHA-256 of the raw response.
5. **Secrets:** the key is never written. A test with a canary key string checks that logs and the audit
   trail never contain it.
6. **Blind subset protection:** suggestions for blind-subset items are generated and **hash-committed but
   never displayed** until you have saved your blind label for that item.

---

## 9. Human review protocol [PROPOSED]

A new review command (a later task) extends the current labeller. It shows:

- the permitted source context (ID, date, domain, URL, title);
- the suggestion, in a block headed **"AI-GENERATED SUGGESTION (provisional, not a human judgement)"**,
  with its evidence spans and uncertainty;
- the rubric definitions on `?`, and the existing company-notice rule.

**Actions:**

| Action | Result |
| --- | --- |
| Accept (Enter) | `label_origin = accepted_ai`, `ai_exposure = seen` |
| Edit any field | `edited_ai`; an `edit_reason_code` is required; the usual validator still applies |
| Reject | You label from a blank item; `rejected_ai_after_seeing`, `ai_exposure = seen` |
| Uncertain | The existing `A` plus a code, and `needs_evidence` recorded as metadata. **No new rubric label is introduced** |
| Skip / quit / go back | As in the current labeller; nothing is saved until the item is valid |

**Always recorded:** reviewer initials, UTC time, and seconds on the item (a coarse effort measure; long
gaps from interruptions are flagged, not trusted).

**Resume:** a restart continues from the first unreviewed item. Saves are atomic and the audit chain is
checked on start.

**Confidence:** the model's stated uncertainty is a **triage hint, not evidence of correctness.**
Verbalised confidence from language models is often poorly calibrated. Any use is limited to ordering
items for your attention. It can be checked against your blind labels (a reliability table) only on the
blind subset, and only descriptively.

**Guards against rubber-stamping:** show the context before the suggestion where practical; report
acceptance rates, so a near-100% rate is visible as such.

---

## 10. Evaluation and agreement methodology [PROPOSED]

The original design changed, so every result carries its condition. **Nothing AI-exposed is reported as
independent.**

| Comparison | Valid only if | How it is labelled |
| --- | --- | --- |
| Raw AI suggestions vs independent human labels | Independent labels exist: the blind subset (Option C) or the overlap set (Option A) | "Independent human vs AI" |
| Human-reviewed AI-assisted labels vs raw AI suggestions | Always computable | "Acceptance and correction rates", **never** agreement. It measures how much you changed, not how accurate either is |
| AI-exposed labels on any original overlap item | n/a | "AI-exposed" on every table and figure |
| Human corrections, rejections, uncertain rates, reviewer effort | Always | Descriptive; time per item with its caveats |

**Agreement measures** (per theme, never pooled across themes; multi-theme data is treated as three
separate categorical judgements):

- **Raw agreement**, and **Cohen's kappa** for two raters, for the four-way label (`R/RL/I/A`) and for
  the binary `R` versus not-`R` that the filters depend on.
- **Gwet's AC1** alongside kappa, because `R` is uncommon in some themes and kappa can mislead at skewed
  prevalence.
- **Company notice** (`Y/N/U`) the same way.
- **Confusion matrices**, and 95% confidence intervals from a **batch-clustered bootstrap**
  (`numpy` `default_rng(42)`, as in B2-I), because items within a batch are correlated.
- **Ambiguous (`A`) and missing labels:** the primary analysis excludes pairs where either side is `A`
  and reports that count; a sensitivity analysis treats `A` as a category. `invalid_output` and abstentions
  are tabulated, with the denominator stated.

**Filter quality:** the B2-I estimators and §4.7 decision thresholds apply to the final labels, **with
`label_origin` stratification** and a sensitivity result on the blind subset alone. Using AI-assisted
labels for the decision is itself an amendment to the pre-registered protocol and is part of approval gate 1.

**What an independent baseline would need:** fresh blind human labels, made **before** any exposure, on
at least the proposed 150 items (about 0.6–1.2 hours), or all 312 (1.3–2.6 hours). I will not fabricate
or retrofit one. If you want to know your own consistency, re-label about 10% after a week (roughly 15–31
items), as B2-I suggests.

**Limits that stay:**

- **One annotator:** there is no human-versus-human agreement.
- **Anchoring cannot be isolated:** with one person, I cannot randomise exposure across the same items.
- **Possible correlated errors:** if the AI shares lineage with the system that designed the rubric.
- **Headline-only context** caps how well any labeller can do.

---

## 11. Risks, limitations and mitigations

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Anchoring and automation bias | Inflated agreement; weaker labels | Blind subset; `ai_exposure` flag; acceptance-rate reporting |
| Contaminating the blind subset | The independent baseline is lost | List fixed and hashed before generation; blind suggestions sealed until your label is saved; no display in this conversation |
| Model hindsight | Labels informed by later events | Request no polarity in v1; instruct topic-only judgement; disclose the residual risk |
| Headline-only evidence | Over-confident labels | `A` with a code is an expected output; evidence spans enforced; uncertainty recorded |
| Fabricated evidence | False support for a label | Evidence spans must appear literally in the title or URL |
| Prompt, model or provider drift | Results not reproducible | Pin model ID; hash prompt and rubric; one frozen run, with raw responses kept; optionally a second run on a sample to measure self-consistency |
| Titles leave your machine | Third-party headlines go to a provider | Needs explicit approval (gate 4). Provider retention and training terms are [UNVERIFIED]. Send only the approved fields. B2 kept titles local and the redistribution question is still open |
| Cost or rate overrun | Surprise bill | Caps on requests, tokens and cost; dry-run estimate; stops at a cap; one request at a time |
| Cost estimate is uncertain | Wrong expectation | Per-item prompts of about 1,800 tokens: roughly 2.9 M input and 0.2 M output tokens in total; with a 600-token prompt about 1.1 M input; batching 20 items per call about 0.3 M input [ESTIMATED]. **No price is assumed** |
| Secrets in logs | Credential leak | Environment variable only; redaction test with a canary |
| Switch left enabled | Unintended network use | Separate gate for AI; lock the GDELT switches (section 2.5) |
| Reviewer fatigue | Rubber-stamping | Batch the work; report acceptance rates; per-item time |
| Schema confusion | `own` misread as independent | New schema; `ai_exposure` as a first-class field; original files untouched |
| Validator gap | An AI basis passes without a suggestion | Close it first (section 13, step 6) |
| Rubric pressure | Pressure to add an "evidence needed" label | None added; metadata only. A real rubric change would need its own approval |

---

## 12. Approval checklist [nothing is approved]

Each item is separate. **Approving one does not approve another.** A configuration flag alone does not
authorise anything.

1. **Methodology.** Do you accept replacing the human-only overlap design with a new, separately
   versioned protocol, and amending the B2-I §4.7 decision to use AI-assisted labels? If not, Option A
   stays.
   - [ ] Approve
   - [ ] Decline
2. **Experimental design.**
   - **Option:** A, B, C or D (section 5).
   - **Review protocol:** immediate AI-visible review, blind-then-reveal, or the hybrid.
   - **Blind subset size:** 150 proposed. Any other number must be fixed before generation.
   - [ ] Choice recorded
3. **Model and provider.** Which provider and exact model; which adapter route; the prompt version, the
   rubric version, the one-request-at-a-time default, the request, token and cost caps (your unit price);
   and whether the isolation rule may be relaxed for one adapter module.
   - [ ] Approve
   - [ ] Decline
4. **Data handling.** The new output folder, retention (including when raw responses are deleted), and
   permission to send titles, domains, URLs and dates to the chosen provider. Also confirm that no network
   fetching of article text is allowed.
   - [ ] Approve
   - [ ] Decline
5. **Execution.** An explicit instruction to generate suggestions, given after items 1–4, and after a
   dry run you have seen.
   - [ ] Authorise
   - [ ] Not yet

**Also needing your answer, not part of the five gates:**

- **A.** Lock the GDELT network and development-sample switches now that the acquisition is finished?
- **B.** The B2-U overlap question (a or b) is replaced by item 2.
- **C.** The confirmation sample stays locked, whatever you choose.

---

## 13. Implementation steps for a later, separately authorised task

None of this starts without the gates above.

1. **Snapshot command** (Stage A), with tests on synthetic folders: copies, hashes, read-only, refusal if
   the destination exists, the key never copied.
2. **Experiment configuration and gate:** a new `ai_annotation` approval kind, a new build lock set to
   `False`, and a config loader that refuses anything incomplete.
3. **Provider interface:** `DryRunProvider`, `FixtureProvider`, and the approved adapter, with a canary
   test for secrets.
4. **Input builder and prompt builder:** approved fields only, fingerprints, rubric hashing, token
   estimate.
5. **Suggestion schema and validation:** JSON schema, the existing validator with `annotator_type = ai`,
   evidence-span check, hash-chained audit log.
6. **Fix the validator gap:** an AI basis must name an item present in the suggestions file, and not an
   overlap or blind-subset item under protocols that forbid it.
7. **`ai-suggest --dry-run`** (invokes nothing), then the gated execution command.
8. **Blind-subset sealing:** commit the subset and suggestion hashes; the review command refuses to show
   a blind item's suggestion before its label is saved.
9. **Review command** (section 9), with tests for every action, resume and atomic saves.
10. **Evaluation module** (offline; opens the sealed key only after the label freeze).
11. **Re-lock the GDELT switches** if approved.

**Tests throughout:**

- synthetic fixtures only;
- no real annotation file mutated;
- no provider call: tests assert zero calls;
- the isolation tests extended and, only if approved, relaxed for the single adapter module;
- one test that a dry run, a flag alone, or an approval record alone each cannot trigger a call.

**No new packages** are required for the stdlib route. Any dependency needs your separate approval.

---

## 14. Statement of what happened

- **No annotation was run.** None of the 1,493 items was labelled.
- **No AI model or provider was invoked,** and no network request was made.
- **No label, suggestion or evidence was generated.**
- **No artifact was altered or exposed:** the original annotations, backup, working copy, sample
  membership, batch file and logs are byte-identical to before. The sealed key was not opened, read or
  re-hashed.
- **Files written:** this report, and a short pending-approval entry in `docs/MEMORY.md`. Nothing was
  committed.
