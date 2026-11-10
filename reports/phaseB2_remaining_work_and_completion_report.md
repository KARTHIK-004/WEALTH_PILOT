# Research Enhancement Track — B2 Remaining Work and Completion Report

**Result: PARTIAL COMPLETION. B2 is not complete.** Everything that is safe to do without an
unresolved approval is done, tested and documented. The rest is blocked on the decisions and actions
listed in section 9.

- **Research design:** complete.
- **Acquisition tooling and the development sample:** complete and verified.
- **Annotation:** **0 of 1,493** items labelled. This is the concrete deliverable everything else waits on.
- **Evaluation:** implemented and tested on synthetic data only. It cannot run on real data until the
  labels exist and are frozen.
- **Full historical acquisition:** not approved, not started, and its driver is not built.
- **B3 and blockchain:** not started.

**Date:** 2026-10-16 (UTC).

**Phase identifiers:** I kept the existing identifiers (B2, B2-F … B2-U, the B2-T proposal) and invented
none. Work done in this run is described by what it is.

**Labels:**

- **[VERIFIED]**: confirmed in this run by reading code or files, or by running a check.
- **[MEASURED]**: observed directly.
- **[PROPOSED]**: awaiting your decision. Nothing marked PROPOSED is approved.
- **[UNVERIFIED]**: not confirmed.
- **[BLOCKED]**: cannot proceed without an approval or a prerequisite.

---

## 1. Verified phase matrix

The authoritative plan is `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md` §20–21 (B2 = "approved news source,
ingestion, provenance, dedupe, mapping, alignment tests"). No competing roadmap was created. `TASKS.md` and
`docs/BUILD_PLAN.md` do not track the research track.

| Phase | Title | Status | Verified evidence |
| --- | --- | --- | --- |
| B2 | Historical news source evaluation | **Complete** | `phaseB2_historical_news_source_evaluation.md`; GDELT conditionally recommended, market level |
| B2-F | Acquisition feasibility | **Complete** (parts superseded by G and H, with notes) | Report and superseded-by note |
| B2-G | Pilot and master-list audit | **Complete** | One file and the list downloaded, both deleted; 1,854 absent slots audited |
| B2-H | Pre-acquisition readiness gate | **Complete** | 180 header checks; frozen filter proposal; calendar |
| B2-I | Filter review and acquisition preparation | **Complete** (protocol and design) | Rubric, pre-registered sample, manifest schema |
| B2-J | Approval checklist and tool design | **Complete** | Report |
| B2-K | Isolated acquisition tool | **Complete** | `backend/wealthpilot/data/gdelt/`; tests below |
| B2-L | Development sample and filter review | **Superseded:** its blocker was cleared by B2-M. The review it describes is still pending (E1) | Report |
| B2-M | Development sample acquisition | **Complete, verified** | 192 of 192 batches, 384 requests, 1,000,147,201 B; audit reproduces every count (re-run today: unchanged) |
| B2-N | Local verification | **Complete** | Report |
| B2-O | Annotation dataset build | **Complete** | 1,493 items, 312 overlap; byte-identical rebuild |
| B2-P | Annotation evaluation | **Blocked:** gap report only; no labels | Report |
| B2-Q | Annotation workflow | **Complete** | Backup, working copy, batches, merge, validate |
| B2-R | Rubric addendum | **Complete;** decisions recorded 2026-10-13 (ambiguity option b; duplicate order) | Addendum |
| B2-U | Labeller usability fix | **Complete** | Review screen, back navigation |
| B2-T (proposal) | AI-assisted annotation methodology | **Proposal; not approved** | `phaseB2T_…_proposal.md` |
| Remaining | Labelling, evaluation, closure | **Open** | Section 2 |

**Acceptance criteria for B2** (`RESEARCH_ENHANCEMENT_ARCHITECTURE.md` §21):

| Criterion | Status |
| --- | --- |
| Every stored article has source, licence, `published_at` and `ingested_at` | **Partly met for the development sample** [VERIFIED]. Rows store source domain, URL, the verified availability time and per-run ingestion times. Licence is recorded at source level (B2), not per row. GDELT gives no reliable publication time, so the page time is stored as a diagnostic only. **Not met for the full window:** it is not ingested |
| Duplicates and unmapped share reported | **Partly met.** Same-batch duplicates are reported (18.0% of 244,936 valid rows). Cross-batch duplicate rates and the unmapped share are unmeasured: they need the full window or the post-acquisition audit (B2-I §4.11) [UNVERIFIED] |
| A test proves no article can be used before its publication cutoff | **Met at the rule level** [VERIFIED]: tests cover the fail-closed availability time, the exact cutoff boundary, daylight saving, early closes, weekends and the 2025-01-09 closure. **Not yet shown on an acquired full window** |

**Conclusion:** B2 is complete in research design and tooling, and incomplete as an ingestion phase.

---

## 2. Remaining-work matrix

| ID | Task | Category | Status | Dependencies | Authorized? | Approval needed? |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | Fix the AI-suggestion validation gap | A | **Done this run** | None | Yes | No |
| A2 | Implement label freeze, gated evaluation and estimators | A | **Done this run** (synthetic tests only) | A1 | Yes (B2-P allowed "the smallest necessary safe extension") | No |
| A3 | Verify provenance and the sealed-key policy | A | **Done this run** (section 6) | None | Yes | No |
| A4 | Review the GDELT switches | A | **Analysis done;** the change itself is B4 | None | Yes (read-only) | Change: yes |
| B1 | Methodology: keep the human-only overlap, or adopt a new protocol (B2-T gates 1–2) | B | **Open** | Your decision | No | **Yes** |
| B2 | Provider, model, prompt, adapter route, cost caps (gate 3) | B | **Open** | B1 | No | **Yes** |
| B3 | Data handling: paths, retention, sending titles to a provider (gate 4) | B | **Open** | B1, B2 | No | **Yes** |
| B4 | Lock the GDELT network and development-sample switches | B | **Open** | None | No | **Yes** |
| B5 | Approve the 13:00 ET early-close cutoff rule | B | Open (PROPOSED since B2-H) | None | No | **Yes** |
| B6 | Approve the missing-data policy (0.75 coverage provisional; 0.50 and 0.90 sensitivity; near-empty and backlog rules) | B | Open (PROPOSED) | None | No | **Yes** |
| B7 | Freeze the capture rule, the stored columns (full theme string?) and the audit rate | B | Open; follows E1 | E1 | No | **Yes** |
| B8 | Whether the B2-I §4.7 thresholds may be applied to AI-assisted labels | B | Open | B1 | No | **Yes** (part of gate 1) |
| C1 | Label the 312 overlap items | C (your action) | **Ready; 0 labelled** | None | Yes | No |
| C2 | Label the 1,181 non-overlap items | C | Waits on B1 if AI is used | C1 or B1 | Human-only: yes | AI: **yes** |
| C3 | Generate AI suggestions | C | **Not built, not run** | B1–B3, execution gate | No | **Yes** |
| D1 | Build the window-wide acquisition driver (fresh list, diff, unlisted re-checks, per-period byte budget) | D | Not built | B5–B7 | **No:** the B2-K scope was the sample path and the full path must refuse | **Yes** |
| D2 | Full historical acquisition (0.87–0.90 TB on the wire) | D | **Not approved, not started** | D1, E1, B5–B7, your bandwidth and data-cap answers | No | **Yes** |
| E1 | Labelled filter evaluation (precision, recall, errors) | E | **Blocked:** needs all 1,493 labels, frozen | C1, C2 | Yes (A2) | No |
| E2 | Human-versus-AI agreement | E | **Blocked** | B1; independent labels | No | Yes |
| E3 | Coverage, near-empty and missing-news evaluation on the full window | E | **Blocked** | D2 | No | via D2 |
| E4 | Cross-batch duplicate and update audit | E | **Blocked** | D2 | No | via D2 |
| E5 | Declare the filter validated or revise it once, then confirm on stage C if triggered | E | **Blocked** | E1, B7 | No | Stage C needs a trigger and its own approval |
| F1 | Final B2 completion report | F | **Not issuable** | E1–E5, B-items | — | — |
| F2 | ADR for the news source (B2's proposed ADR-043) | F | Not written | After approvals; none implies full acquisition | No | **Yes** |

**Evidence needed to mark B2 complete:** every B item decided; all items labelled, frozen and evaluated
(E1); coverage, duplicates and alignment shown on the acquired window (E3–E4, D2), or the scope formally
reduced by you; the ADR recorded.

---

## 3. Work completed in this run

### 3.1 AI-suggestion validation gap: confirmed and fixed [VERIFIED]

**The defect existed as reported.** In the code, `row_errors` received only a boolean,
`ai_suggestions_exist`, and `validate` and `merge` filled it with `p.ai_suggestions.exists()`. Any file at
the path satisfied an AI-based `label_basis` for **every** item. The repository's own test showed it: a file
holding only the header `item_id` let five different items claim `accepted_ai`.

**The fix (smallest safe change, in `annotate.py`):**

| Change | Effect |
| --- | --- |
| `row_errors(row, *, all_ids, ai_suggested_ids=frozenset())` replaces the boolean | An AI basis is accepted only for an item whose ID is in the set of items with a **valid** suggestion. The default is empty, so it **fails closed** |
| New `load_ai_suggestions(...)` | Reads and validates the file: required columns, no duplicate columns, one valid row per item. A row is valid only if the item is known, appears **once**, is **not** an overlap item, is marked `annotator_type = ai`, and passes the rubric. Unreadable, short, long or non-UTF-8 files and a directory at the path fail closed. Extra provenance columns are allowed |
| New `content_errors(...)` | The rubric's content rules, split out of `row_errors`, so suggestions and human labels are held to the same rubric |
| The file is read **only when a label claims an AI basis** | The human-only workflow and the labeller never read it. A corrupt file does not block human-only work |
| `validate` and `merge` report the file's problems | Only when an AI-based label depends on the file |

**Not changed:** the human-only workflow, corrections, the labeller, the rubric, the real dataset folder.
No suggestion file was created and no suggestion was generated.

**Not enforced (deliberately, because the methodology is unapproved):**

- that an `accepted_ai` label equals its suggestion;
- the richer B2-T provenance fields (model, rubric version, time, input fingerprint).

**One design consequence to know** [VERIFIED]: the rubric requires polarity for an `R` theme, and the
validator applies the rubric to suggestions as well. The B2-T proposal's idea of "not requesting polarity
in v1" would therefore need either `UNC` for polarity or a schema decision.

**Tests:** 30 new tests in `test_ai_suggestion_validation.py`. A mutation check (re-introducing the old
behaviour in memory) made 4 of them fail, which shows they detect the defect.

### 3.2 Label freeze, gated evaluation and estimators [VERIFIED on synthetic data only]

**Why:** B2-P authorised "the smallest necessary safe extension" to evaluate against the sealed key after
a label freeze, and none existed. The estimators are those pre-registered in B2-I §4.6.

| Module | Content |
| --- | --- |
| `estimators.py` (pure, no files) | Weighted precision with ambiguous items excluded and bracketed; pooled recall; capture recall with the rule-of-three lower bound; company-notice statistics; batch-clustered bootstrap; Wilson intervals; reporting floors (100 and 30 items); the B2-I §4.7 thresholds, labelled PROPOSED; agreement arithmetic (raw, Cohen's kappa, Gwet's AC1) |
| `evaluate.py` | `freeze`: refuses until all 1,493 items are labelled and valid; writes a read-only record with the working copy's SHA-256; never overwrites. `evaluate`: checks the freeze, that the labels are unchanged and still valid, and **only then** opens the key, checks it against its build-time fingerprint, and writes aggregates only (never per-item data) |
| CLI | `annotate freeze` and `annotate evaluate` |

**Order and isolation, enforced by tests:**

- A test replaces the key reader with a function that fails the test if called. It is **never called**
  when labels are incomplete, no freeze exists, or the working copy changed after the freeze.
- A bypass check (disabling the freeze test in memory) made 2 of these tests fail.
- A key whose fingerprint does not match, or which covers different items, is refused.
- Only `evaluate.py` and the build (`review.py`) mention the key. A test asserts exactly that.
- AI-based labels, if present, are counted and flagged "NOT independent". **Agreement is not computed
  anywhere:** which label sets are independent is the unapproved decision B1.

**Departure from B2-I, disclosed:** the bootstrap uses `random.Random(42)` rather than numpy's
`default_rng(42)`, because the isolated package may import only the standard library. Results are
deterministic but not numerically identical to numpy's stream.

**On your real data:** `annotate freeze` refuses today ("0 of 1493 items labelled") and creates nothing.
I did **not** run `annotate evaluate` on real data. It would refuse at its first check, but running it
was unnecessary and the sealed key stays closed.

**Tests:** 20 new tests in `test_estimators_evaluate.py`. The estimators are checked against hand-computed
tables, such as a precision of 51/76 and a capture-recall lower bound of 151/551.

### 3.3 Provenance and artifacts [VERIFIED; section 6]

### 3.4 GDELT switch review [VERIFIED; section 8]

### 3.5 Documentation

Updated: the tool README (new modules, new commands, the validator-enforced suggestion schema, what the
tool still cannot do); a short update note on the B2-T proposal; the architecture document; `MEMORY.md`.
No historical report was rewritten.

---

## 4. Files changed in this run

**Code (new):**

- `backend/wealthpilot/data/gdelt/estimators.py`
- `backend/wealthpilot/data/gdelt/evaluate.py`

**Code (modified):**

- `backend/wealthpilot/data/gdelt/annotate.py`
- `backend/wealthpilot/data/gdelt/cli.py`

**Tests (new):**

- `tests/backend/data/gdelt/test_ai_suggestion_validation.py` (30)
- `tests/backend/data/gdelt/test_estimators_evaluate.py` (20)

**Tests (modified):** `tests/backend/data/gdelt/test_annotate.py`.

- **Why:** two tests passed the removed boolean flag, and one used a header-only stand-in file that no
  longer (correctly) satisfies the validator.
- **How:** the third was rewritten to use a real, valid synthetic suggestion file. No assertion about the
  human-only workflow was changed.

**Documentation:**

- `backend/wealthpilot/data/gdelt/README.md`
- `reports/phaseB2T_ai_assisted_annotation_methodology_proposal.md` (update note only)
- `docs/RESEARCH_ENHANCEMENT_ARCHITECTURE.md`
- `docs/MEMORY.md`
- `reports/phaseB2_remaining_work_and_completion_report.md` (this file)

**Not changed:**

- the original annotations, working copy, backup, batch, logs and sealed key;
- the sample, filters, thresholds and rubric;
- the GDELT switches;
- dependencies (`pip freeze` fingerprint `3393be50…`), application code, database, models and market data.

**Not done:** no commit or push.

---

## 5. Test evidence [VERIFIED]

| Command | Result |
| --- | --- |
| `pytest tests/backend/data/gdelt -q -p no:cacheprovider` (before changes, today) | **212 passed** |
| The same, after all changes | **262 passed, 0 failed, 0 errors, 0 skipped** (212 + 30 + 20) |
| Per file | annotate 37; ai_suggestion_validation 30; guards_gates 32; labeller 27; manifest_engine 21; estimators_evaluate 20; parser_integrity 23; filters_dedup 17; sample_isolation 15; time_availability 40 |
| Mutation check 1 | Old AI-suggestion behaviour re-introduced in memory: 4 tests fail |
| Mutation check 2 | Freeze gate bypassed in memory: 2 tests fail |
| Locking both GDELT switches **in memory only** | 261 passed, 1 failed (the test asserting the post-acquisition state), see section 8 |
| Compile with warnings as errors; unused-import scan | OK; 0 |
| `pytest tests --collect-only` | 1,636 tests collected |
| Full backend regression suite | **Not run.** It connects to the hosted database over the network, and this run permits no network use. The new code is imported by no application module, which a test enforces |

All new tests are offline: sockets and the database factory are blocked, and fixtures are synthetic. No
real annotation artifact is mutated by a test.

---

## 6. Provenance and research integrity [VERIFIED]

| Artifact | State | SHA-256 (first 16) |
| --- | --- | --- |
| `annotation_A.csv` (original) | Unchanged | `11db13e668bd3da8…` (equals `selection_log.json`) |
| `annotation_B.csv` (overlap subset, 312) | Unchanged | `211729002893c1e4…` (equals `selection_log.json`) |
| Backup `backup/annotation_A.build.csv` | Unchanged, identical to the original | `11db13e668bd3da8…` |
| Working copy | Unchanged; 0 labels; identical to the original | `11db13e668bd3da8…` |
| Batch 1 export | Unchanged, unlabelled | `105ce3d4bc5d1fd2…` |
| `merge_log.jsonl` | Unchanged: `init`, `export` | `a2b7cde1ccd0d78a…` |
| `ANNOTATION_INSTRUCTIONS.md`, `selection_log.json` | Unchanged | `e9d73df65fd2465c…`, `15fa23029c0284…` |
| Development sample (192 batches) | Full audit unchanged: states, manifest-order hash `a459a3fb…`, SHA-256, CRC, requests (384), bytes (1,000,147,201) | — |
| **Sealed key** | **Not opened, not read, not hashed.** Size 142,900 B and modification time are unchanged since the build; its recorded fingerprint is `cc45a3df0465f2e7…` | — |
| `ai_suggestions_A.csv`, `freeze_record.json`, `evaluation_results.json` | **Do not exist** | — |

**Conflicts between files: none.** I did not overwrite or reconstruct any file.

**Superseded text inside a protected file:** `ANNOTATION_INSTRUCTIONS.md` is a hashed build output, so it
stays as generated. These lines are superseded:

| Instruction in that file | Superseded by |
| --- | --- |
| Label `annotation_A.csv` and save under the same name | The working copy is the authoritative labelled file (B2-Q, B2-R) |
| The overlap subset's second labeller is an AI working blind (human-versus-AI agreement) | Open question B1; no AI output on overlap items while you label (B2-U) |

The rest of that file (the rubric, the polarity rules, the correction rules, the file descriptions) still
applies, including the single `amb_code` field, which is consistent with decision (b).

--- | --- |
| Label `annotation_A.csv` and save under the same name | The working copy is the authoritative labelled file (B2-Q, B2-R) |
| The overlap subset's second labeller is an AI working blind | Open question B1; no AI on overlap items while you label (B2-U) |
| "`annotation_B.csv`: do not edit it yourself" | Still valid |
| `amb_code`: one code per row | Option (b): one primary code, the rest in `note` (B2-S) |

---

## 7. Annotation and AI-generation status [VERIFIED]

| Measure | Value |
| --- | --- |
| Items | **1,493** (overlap 312; non-overlap 1,181) |
| Labelled | **0** (overlap 0; non-overlap 0) |
| AI suggestions | **0.** No file; no provider or generation code exists |
| AI provider invoked | **No** |
| Data sent externally | **No** |
| Labels or suggestions generated | **None** |
| Freeze record / evaluation results | None |
| Test coverage of the human-only workflow | Unchanged and passing |

---

## 8. GDELT switch status [VERIFIED]

| Switch | Current value |
| --- | --- |
| `NETWORK_ENABLED_IN_THIS_BUILD` | **True** |
| `DEV_SAMPLE_ENABLED_IN_THIS_BUILD` | **True** |
| `CONFIRMATION_SAMPLE_ENABLED_IN_THIS_BUILD` | False |
| Full acquisition | No switch exists; it always refuses |
| Local `run_config.yaml` | Mode `dev_sample`; the development-sample approval is still present |

**What this means today:** the gate would **pass** for the development sample with `--confirm-network`
(I built the authorization object only; no request was made). The acquisition itself finished on
2026-10-13, so the capability is no longer needed, and I expect a repeat run to do almost nothing because
every slot is already processed [UNVERIFIED: not run].

**A safe, reversible lock is possible** [VERIFIED by measurement]:

| Aspect | Finding |
| --- | --- |
| The change | Set the first two constants to `False` in `__init__.py` (two lines). Optionally mark the local approval consumed |
| Reversibility | Set them back to `True`; the approval record is untouched |
| Benefit | A network-capable tool no longer stays enabled by default; a fresh, deliberate approval would be needed for any later GDELT request, including the future full-acquisition work |
| Impact on tests | With both locked in memory: **261 of 262 pass.** The one failure is `test_build_state_after_b2m_keeps_every_other_gate`, which asserts the post-acquisition state and would be updated with the change |
| Impact on workflows | `fetch-sample` would refuse; `dry-run` would show the lock as a blocker (informational). Labelling, `build-review`, freeze and evaluation are offline and unaffected |

**I did not change the switches.** Approval B4 is requested in section 9.

---

## 9. Outstanding approvals and decisions

Only what is still needed. Each is separate; none is implied by another.

**Methodology and annotation (from the B2-T proposal):**

1. **B1, methodology and design.** Keep the original human-only overlap design, or adopt a separately
   versioned AI-assisted protocol? Choose Option A, B, C or D from the proposal, the review protocol, and
   the blind-subset size. A decision record follows in section 10.
2. **B2, provider and model.** Provider, exact model, adapter route, prompt and rubric versions, and
   request, token and cost caps (you supply the prices). Whether the isolation rule may be relaxed for one
   adapter module.
3. **B3, data handling.** Output folders, retention, and permission to send titles, domains, URLs and dates
   to the chosen provider.
4. **C3, execution.** Only after items 1 to 3 and a dry run you have seen.
5. **B8.** Whether the pre-registered B2-I §4.7 decision thresholds may apply to AI-assisted labels.

**Engineering and policy:**

6. **B4.** Lock the two GDELT switches (section 8).
7. **B5.** The 13:00 ET early-close rule.
8. **B6.** The missing-data policy (the 0.75 threshold stays provisional).
9. **B7.** Capture-rule freeze and stored columns, after the labelled review.

**Acquisition (not now):**

10. **D1 and D2.** Building the window-wide driver, and the full acquisition, each need their own approval,
    plus your answers to the bandwidth and data-cap questions (B2-I §9.1). The ADR (F2) follows approval.

**Your action, not an approval:**

11. **C1.** Label the 312 overlap items.

Already decided and not repeated: the rubric ambiguity option (b), and the duplicate ordering (2026-10-13).

---

## 10. Methodology decision record [PROPOSED; not approved]

**Question.** The original design reserves 312 overlap items for human-only labels so that a human
baseline stays independent of AI. May AI assistance be used for those items too?

**Facts that decide the question** (from the B2-T proposal, rechecked):

- Nothing is labelled yet, so no independent human labels exist to protect. What is at stake is the
  *option* of an independent baseline.
- Human labels made after seeing AI suggestions are not independent of them. Agreement computed from
  them would partly reflect anchoring and automation bias, and cannot be presented as independent
  human-versus-AI agreement.
- The original overlap membership, `annotation_B.csv` and fingerprints must stay as history under any option.
- There is one annotator, so even the original design measured human-versus-AI agreement and never
  human-versus-human agreement.

**Choices for you** (details and trade-offs in the B2-T proposal §5):

| Option | Independent human-vs-AI comparison | Your labelling effort [ESTIMATED] | Methodology change |
| --- | --- | --- | --- |
| **A.** Keep the original design: 312 overlap items blind; the 1,181 others AI-assisted | 312 items | 1.3–2.6 h blind, then reviewing 1,181 | Blind AI labels on overlap items, or none |
| **B.** AI-assisted for all 1,493 | **None** | Reviewing 1,493 (unmeasured) | Replaces the overlap design |
| **C.** Hybrid: 150 overlap items blind (fixed and hashed before any AI output), the other 1,343 AI-assisted | 150 items (about ±6 points) | 0.6–1.2 h blind, then reviewing 1,343 | A new, separately versioned dataset |
| **D.** All 1,493 blind first, then reveal | 1,493 first-pass labels | 6.2–12.4 h | AI saves no time |

**Recommendation [PROPOSED]:** Option C, in a separately versioned dataset, because it keeps a valid
independent comparison for the least labelling effort while letting AI assistance apply to most items.
Option B is legitimate if you accept that it supports acceptance and correction rates only, with every
figure labelled AI-assisted. **This is a recommendation, not a decision.** If you choose A, the 312 items
stay human-only and nothing in this report changes.

---

## 11. Conditions for completing the remaining B2 tasks

In dependency order:

1. **Decide B1** (and B2, B3 if AI is used). If A or D with no AI, no provider decisions are needed.
2. **Label** the overlap items (C1) and then the rest (C2).
3. **Freeze and evaluate** (`annotate freeze`, then `annotate evaluate`; this is the first time the sealed
   key is opened).
4. **Apply the pre-registered decision (E5):** freeze `gdelt_filter_v1`, or revise once and confirm on
   stage C only if its trigger has fired (and with its own approval).
5. **Decide B5, B6, B7.**
6. **For ingestion completion:** approve and build the window-wide driver (D1), answer the bandwidth
   questions, and approve the acquisition (D2). Then complete E3 and E4 and re-check the three §21
   acceptance criteria.
7. **Record the ADR** (F2) and issue the final B2 completion report (F1).

If you decide that B2 should close **without** the full acquisition, say so explicitly: the §21 ingestion
criteria would then be reported as not met, and the sentiment work would have only the development sample.

---

## 12. Deferred to B3 or later [explicitly out of scope]

- the sentiment classifier and its validation (B3);
- market-only, sentiment-only and hybrid models (B4);
- personalisation and nudge integration (B5);
- ablation, robustness and backtests (B6);
- the audit architecture, ledger and blockchain work (B7, B8; deferred until the AI track is complete);
- any frontend display of news-derived insight (B9);
- any change to recommendations, the optimizer or compliance;
- any model training for the news experiment.

---

## 13. Statement of what happened in this run

- **Network:** no request was made. No GDELT file or other data was downloaded.
- **Provider:** no AI model or provider was invoked; no data was sent anywhere.
- **Labels and suggestions:** none were created, modified or merged.
- **Sealed key:** not opened, not read, not hashed.
- **Original artifacts:** preserved byte for byte.
- **Switches:** not changed.
- **Not committed, not pushed.**
