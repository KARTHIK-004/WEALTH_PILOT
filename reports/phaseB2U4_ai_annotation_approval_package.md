# Phase B2-U4: AI annotation approval package

Date: 2026-10-19. Status: **a package for your decision. Nothing is approved, enabled or executed.**

Written for: you, the project owner, who makes the four B2 decisions (methodology, provider, data handling, execution).

**What was and was not done**

- **Done:** read the B2-U3 report and the pipeline code; ran a non-writing dry run and a blocked run against the real, *unlabelled* item file; read public provider documentation; measured the item data.
- **Not done:** no annotation, no AI suggestion, no provider call, no data sent anywhere (the web research used public pages only and sent no project data), no sealed-key access (size and time only), no GDELT acquisition, no change to the original annotation files, no code change, nothing enabled, no commit. No provider is selected.

**Labels:** [VERIFIED] confirmed by a check or an official page; [MEASURED] observed in local data; [ESTIMATED] computed with stated assumptions; [PROPOSED] needs your approval; [UNVERIFIED] unknown or not confirmed.

---

## 1. What you need to decide, and two things I found

| # | Decision | Where |
| --- | --- | --- |
| 1 | **Methodology (Gate A):** option and blind-subset size; whether labels from this protocol may replace human labels in the B2-I §4.7 filter decision | §2 |
| 2 | **Provider and model (Gate B):** which one, as a pinned snapshot; whether the isolation rule and the approved-library list may be relaxed for one adapter | §3, §7 |
| 3 | **Data handling (Gate C):** whether titles and URLs may leave the machine; provider terms and retention | §4 |
| 4 | **Execution (Gate D):** run ID and the limits | §5 |
| 5 | **Two schema conflicts** (duplicates, polarity) | §6 |

**Two issues in my own B2-U3 work, reported not fixed:**

- **Defect: `near_dup_of` is silently dropped.** In the AI-assisted review, the prompt "Same story as item" is shown, but the answer is discarded and every review record stores `near_dup_of = ""` (`ai/reviewer.py:112`, `:166`, and `_enter` returns only the content fields and `note`). A reviewer cannot record a duplicate, and the exported dataset has an always-empty `near_dup_of` column. See §6.
- **Gap: `temperature` is not configurable or recorded.** B2-T proposed temperature 0. The config, the Gate B hash and the run record have no sampling parameters. See §7.

Neither can matter yet, because nothing can run. Both should be decided before Gate B and fixed in a separately approved change.

---

## 2. Methodology for the 312 overlap items

**What changes.** The original design kept the 312 overlap items human-only so human labels could be compared with AI labels. A human label made after seeing a suggestion is a different measurement and is not independent [VERIFIED, B2-T §4]. The original overlap list stays as history in the new dataset (`historical_overlap.json`), and the original files are unchanged [VERIFIED, hashes in §8].

**Options** (from B2-T §5, checked against what the code supports):

| Option | Blind human labels (independent comparison) | AI-exposed items | Supported by the built pipeline? |
| --- | ---: | ---: | --- |
| A. Original design | 312 | 1,181 | Yes: put all 312 overlap IDs in `blind_item_ids` |
| B. Fully AI-assisted | **0** | 1,493 | Yes (default, empty blind list) |
| **C. Hybrid (B2-T's recommendation, unchanged)** | **150** | 1,343 (162 of them original overlap items) | Yes |
| D. Blind-then-reveal for all | up to 1,493 | revisions only | **No.** A blind label is final; there is no reveal-and-revise step. `blind_item_ids` must also be original overlap items. It needs new code |

**The proposed 150-item blind subset** [PROPOSED, reproducible]: rank the 312 overlap items by SHA-256(`wealthpilot-b2i-filter-review-v1|b2t-blind|gkg_record_id`) and take the first 150.

- **Check on the rule's form** [MEASURED]: the same seed and `|iaa|` form reproduces exactly the recorded 312 overlap items.
- **Fingerprint** [MEASURED]: SHA-256 of the 150 sorted item IDs is `919da1c0a1cad544f734b57241a7ef1f48fc38d8e73e10cff915ffccc4f40ff6`. It spans 99 distinct batches.
- **Not committed:** the list was computed in memory and written nowhere. No tool in the repository generates it yet. The config takes an explicit ID list, and Gate A binds that list.

**Consequences for independent human-versus-AI evaluation:**

- **Only the blind items give an independent comparison,** and it is still *one human against one model*. It is not human-versus-human agreement, and it does not measure accuracy.
- **Precision of the blind comparison** [ESTIMATED, Wilson 95% half-width, ignoring batch clustering, which widens it]:

  | Blind items | at 80% agreement | at 90% agreement |
  | ---: | ---: | ---: |
  | 50 | ±10.9 points | ±8.5 |
  | 100 | ±7.8 | ±6.0 |
  | **150** | **±6.4** | **±4.8** |
  | 200 | ±5.5 | ±4.2 |
  | 312 | ±4.4 | ±3.3 |

- **Rare labels are weaker.** Per-theme `R` prevalence in 150 items is unknown until you label, so a per-theme kappa could be unstable. I cannot check prevalence without opening the sealed key.
- **Everything AI-exposed is labelled so.** Every exported row carries `ai_exposure` and `label_origin`. Acceptance and correction rates are descriptive only, never agreement.
- **Blind items still go to the provider.** Their suggestions are generated and sealed, and shown to you only after your blind label is saved. If you want no overlap item sent externally at all, that is a different design from every option above.
- **Effort** [ESTIMATED by B2-T, 15–30 s per item, unmeasured]: 150 blind items take about 0.6–1.2 hours.
- **Your own earlier rule (B2-U): "no AI output on overlap items while you label."** Option C leaves 162 overlap items AI-exposed. That is an exception to your rule and needs your explicit approval.
- **The filter decision.** The B2-I §4.7 thresholds (precision at least 0.70, lower bound 0.60; pooled capture recall at least 0.90) were pre-registered for human labels. Using AI-assisted labels for that decision is an amendment, and this is part of Gate A [VERIFIED, B2-T §10].
- **A build gap:** `annotate freeze` and `annotate evaluate` read only the original dataset (tested), and nothing yet computes the human-versus-AI agreement or the filter estimates on the new export. That evaluation code does not exist for either option.

---

## 3. Provider and model options (no provider is selected)

**How verified.** Retrieved 2026-10-19 from the vendors' own pages. The Anthropic pricing page was read in full. For the Google and OpenAI pages and the data-terms pages, the fetch tool returned a summary produced by a small model, so figures below carry "[VERIFIED via fetch summary]" and **must be re-confirmed on the live page at approval time.** Prices change, and Google's page already lists a scheduled change.

### 3.1 Pricing, USD per million tokens, Standard tier

| Vendor | Model | Input | Output | Batch (50% off, where listed) | Notes |
| --- | --- | ---: | ---: | --- | --- |
| Anthropic [VERIFIED, full page] | Claude Haiku 5.5 | 0.10 | 0.50 | yes | prompts over 100k tokens cost more; not relevant here |
| | Claude Sonnet 5.5 | 2 | 10 | yes | |
| | Claude Opus 5.5 | 4 | 20 | yes | |
| Google [via fetch summary] | gemini-2.5-flash-lite | 0.10 | 0.40 | yes | |
| | gemini-3.5-flash-lite | 0.30 | 2.50 | yes | |
| | gemini-3.8-flash | 0.75 | 3.75 | yes | **scheduled: 1.50 / 7.50 from 2027-01-01**; the page gives no reason |
| OpenAI [via fetch summary] | gpt-6-luna | 0.10 | 0.50 | yes | |
| | gpt-5.4-nano | 0.20 | 1.25 | yes | |
| | gpt-5.4-mini | 0.75 | 4.50 | yes | |
| | gpt-6.1-sol | 2.00 | 10.00 | yes | promotional pricing on another model "through November 21, 2026" |

These are samples from each vendor's list, chosen to span its range. Every vendor lists more models (including much dearer ones). Choosing among them, or leaving this table, is yours.

- **Thinking tokens.** Google bills thinking tokens as output [via fetch summary]. For any reasoning-capable model, the 400-token output cap may truncate or cost more. Behaviour for each vendor's models is [UNVERIFIED].
- **The pipeline does not use a Batch API.** It calls one request at a time. The batch column is informational only, and using it would need new code.
- **Prompt caching** could cut the repeated rubric cost on some vendors. The pipeline does not implement it.
- **Local or self-hosted models:** no data would leave the machine, but this needs an approved library and hardware, and I did not research it. Pricing is not applicable and quality is [UNVERIFIED].

### 3.2 Estimated cost for this task [ESTIMATED]

Inputs from the real dry run [MEASURED]: 1,493 requests, **1,742,841** estimated input tokens (characters ÷ 4; a real tokenizer will differ), and an output **upper bound** of 597,200 tokens (400 per item). A real response is likely well under that. The 2,000-request column scales the same numbers by 2,000 ÷ 1,493. B2-T's 2.9 M input estimate assumed a longer prompt.

| Model | 1,493 requests | 2,000-request cap |
| --- | ---: | ---: |
| Claude Haiku 5.5 | $0.47 | $0.63 |
| Claude Sonnet 5.5 | $9.46 | $12.67 |
| Claude Opus 5.5 | $18.92 | $25.34 |
| gemini-2.5-flash-lite | $0.41 | $0.55 |
| gemini-3.5-flash-lite | $2.02 | $2.70 |
| gemini-3.8-flash (to 2026-12-31) | $3.55 | $4.75 |
| gpt-6-luna | $0.47 | $0.63 |
| gpt-5.4-nano | $1.10 | $1.47 |
| gpt-5.4-mini | $3.99 | $5.35 |
| gpt-6.1-sol | $9.46 | $12.67 |

Across these samples the whole run costs at most about $25, even at the 2,000-request cap. The cost decision is therefore a cap, not a trade-off. Quality on headline-only labelling is **[UNVERIFIED] for every model** and nothing here measures it.

### 3.3 Data-handling terms (the facts that matter for Gate C)

| Question | Anthropic | Google Gemini API | OpenAI |
| --- | --- | --- | --- |
| Used to train models? | "Retained data is never used for model training without your express permission" [VERIFIED, official page] | **Unpaid Services: yes**, and "human reviewers may read, annotate, and process" inputs. **Paid Services: no** [via fetch summary, terms effective 2026-03-23] | "data sent to the OpenAI API is not used to train or improve OpenAI models" unless you opt in [via fetch summary] |
| Default retention | "automatically delete inputs and outputs on our backend within 30 days"; flagged content up to 2 years, classifier scores up to 7 years [via fetch summary, article dated 2026-07-01] | Paid: logged "for a limited period of time" for abuse monitoring; **length not stated** [via fetch summary] | Abuse-monitoring logs "up to 30 days" [via fetch summary] |
| Zero data retention | Opt-in, per organisation, subject to approval [VERIFIED, official page] | Not stated [UNVERIFIED] | Needs prior approval [via fetch summary] |
| Sensitive data | Not checked | Terms say not to submit sensitive, confidential or personal information to Unpaid Services | Not checked |

- **Key consequence for Google:** a free-tier key would let Google train on, and have humans review, the 1,493 titles and URLs. The project's `GEMINI_API_KEY` is in `.env`, which I did not read, so whether it is a paid account is **[UNVERIFIED]**.
- **Training terms for Anthropic's commercial account:** the retention article does not mention training. The "never used for training without permission" line comes from the API retention page. Confirm that both describe the account you would use.
- **No page I read gives a signed data-processing agreement.** Whether you need one is your call.

**Library status** [VERIFIED]: `google-genai` 0.3.0 is approved for the application's debate and explanation features (2026-09-14), not for this research use. `anthropic` is not installed. `openai` 3.13.0 is installed but undeclared. `CLAUDE.md` forbids adding a library outside the approved list without asking. A standard-library HTTP adapter avoids a new dependency but needs more code.

---

## 4. Exactly what would leave the machine

**Per request, one item at a time** [VERIFIED, `ai/prompt.py`, tested]: the fixed rubric text, then a JSON object of five fields:

| Field | Content | Measured on the real 1,493 items |
| --- | --- | --- |
| `item_id` | Opaque ID such as `D0001`; not a GDELT record ID | |
| `batch_date_utc` | A date, 2021-12-02 to 2023-12-24 | |
| `source_domain` | Publisher domain | 832 distinct domains |
| `url` | The **full URL as text**; never fetched | median 109 characters, max 255; **45 contain a query string**; 42 are not https; none has a user-info part or an `@` |
| `title` | The decoded headline | median 65 characters, 90th percentile 98, **max 766**; 77 contain non-ASCII text; 1 is empty; none contains an `@` or a 10-digit number |

Query-string parameter names seen include `cs`, `source`, `id`, `site_id`, `vmcid`, `storyid`; their values were not printed. Whether any value is a tracking or session identifier is **[UNVERIFIED]**.

**Never sent** [VERIFIED, tested]: the GDELT record ID and batch stamp; availability and page timestamps; the duplicate mark; the overlap flag; any label; any sealed-key field; other items' text. Article text is not fetched. Your API key travels in the request header as with any API call.

**Open privacy and policy questions for Gate C:**

1. **Third-party headlines.** Titles are news headlines that may name people. I did not scan them for names. GDELT says its datasets are free for any use with citation [VERIFIED, gdeltproject.org/about.html], but that page **does not address the article titles or text** themselves. Whether sending them to a provider is acceptable is your decision, and B2-T flagged the redistribution question as still open.
2. **Provider retention.** Per §3.3: 30 days (Anthropic, OpenAI), unspecified (Google paid). Is that acceptable, or do you need zero data retention, which needs vendor approval?
3. **Training and human review.** Confirm the exact account tier, and that it is not a free or unpaid tier.
4. **Region.** Data residency is a paid option at OpenAI; the others are not checked. Does location matter?
5. **Local retention.** The config requires `retention_days`, and Gate C binds it. **No code deletes anything** [VERIFIED, `ai/config.py`]; raw responses stay on disk until you delete them. You decide when and how.
6. **Sample files.** Your 2026-10-13 rule stands: keep the sample files until annotation and review are done, then delete them.
7. **Terms reviewed.** `provider_data_terms_reviewed: true` is your attestation. I cannot make it.

---

## 5. Proposed run limits [PROPOSED; every value needs your approval]

| Limit | Proposed | Basis |
| --- | --- | --- |
| Requests (`max_requests`) | **2,000** | 1,493 needed; headroom for about 34% retries and re-asks. The run stops safely at the cap, and raising it later changes Gate D, so it needs re-approval |
| Attempts per item | 3 | The current default. Calls and re-asks share this count |
| Re-asks for invalid output | 1 | The current default |
| Back-off after a retryable error | 2, 4, 8 s | The current default |
| Timeout per request | 60 s | The current default |
| Concurrency | **1 (sequential)** | The only mode implemented. Provider rate limits for your account are **[UNVERIFIED]** |
| Input tokens (`max_input_tokens`) | **3,000,000** | About 1.7 × the 1,743 k estimate, to absorb tokenizer error and retries |
| Output tokens per request | 400 | The current default; may truncate output on reasoning models |
| Budget (`max_cost`) | **1.5 × the base estimate at the unit prices you approve** | Needs currency and both unit prices in the config; the pipeline assumes no price. For the sampled models in §3.2 that is a cap of roughly $0.60 to $28 |
| Run time [ESTIMATED] | about 1–2.5 hours | 1,493 sequential calls at 2–6 s each; unmeasured |

A `STOP` file halts the run before the next item. A stopped run resumes without repeating finished items.

---

## 6. Do the duplicate and polarity rules match the existing rubric?

Reported as conflicts. **The rubric, validator and schema were not changed.**

### 6.1 Duplicates (`near_dup_of`): conflict

- **The rubric** [VERIFIED, B2-I §3.6 and §4]: the annotator marks a clear near-duplicate with `near_dup_of`, naming another item; direction is derived afterwards (B2-S decision).
- **The AI pipeline, as designed:** the model is not asked for `near_dup_of`, because one request sees one item. B2-T said the pipeline's duplicate mark and your review would cover it.
- **The conflict:** the review path cannot record it. The prompt is asked and the answer discarded (see §1). Every record stores an empty `near_dup_of`, so unmarked near-duplicates would inflate the "unique stories" precision that B2-I §3.6 reports.
- **Options for you:** (a) fix the review path to keep the reviewer's `near_dup_of` and nothing else; (b) accept that this dataset records no duplicates and drop the unique-stories figure for it; (c) a second pass that asks the model about candidate pairs, which is new design.

### 6.2 Polarity: conflict between B2-T's text and the implementation

- **The rubric and validator** [VERIFIED, B2-I §3.8, `annotate.content_errors`]: polarity is **required** for any theme labelled `R`, with `UNC` allowed. It is recorded "for a later, separately approved evaluation".
- **B2-T §8.4 proposed otherwise:** "Not requested in v1... fields stay blank", because polarity is where model hindsight is most likely.
- **What was built:** the pipeline follows the validator, so the rubric text asks for polarity on every `R` theme and a suggestion without it is invalid.
- **Options for you:** (a) keep as built: matches the human rubric, and carries hindsight risk on a field nobody analyses yet; (b) tell the model to answer `UNC` for every `R`: keeps the validator, but makes the field uninformative and needs a rubric-text change (Gate B hash); (c) allow blank polarity under a versioned schema: a rubric and validator change needing separate approval.

### 6.3 Other differences (additions, not conflicts)

For the AI output only, `b2t_rubric_v1` adds required evidence excerpts for `R` and `RL`, a per-theme uncertainty, an `insufficient_evidence` flag (which needs at least one `A`), `evidence_basis = headline_url_only`, and a 300-character note limit. Human labels are not held to these. The relevance codes, ambiguity codes, company-notice rule and polarity values match the existing rubric, and the shared validator enforces them. Gate B approves the exact text by hash.

---

## 7. The four gates, their exact artifacts, and the two code prerequisites

Each gate is a record in the experiment YAML under `approvals:`. A record counts only if `approved` is the YAML boolean `true`, `approved_by` is initials or a name (no email), `approved_on` is a date, `reference` is non-empty, and `binds_sha256` is the 64-character hash the dry run prints **for the current config**, in quotes. A record bound to different content is refused, and approving one gate never satisfies another [VERIFIED, tested].

| Gate | You approve | Hash covers | Stable values now |
| --- | --- | --- | --- |
| **A** Methodology | Option, blind subset, original-overlap treatment | experiment ID; protocol ID; sorted blind item IDs; `review_required_for_every_item = true`; SHA-256 of `annotation_B.csv` | `annotation_B.csv` = `211729002893c1e4ce5ae3787112ca4dbe119607a928a2621d36247fe2d3874e` |
| **B** Provider and model | Provider, pinned model ID and version, prompt, rubric | provider; `model_id`; `model_version`; credentials variable **name**; prompt version and hash; rubric version and hash; output version | prompt `e5711d4946e92f11a3dea12ed2a9bd02e1312034214b8af1e8e93c0de2a955e2`; rubric `d513a76bb45c8f3bd0c21dd12221769a738219cfc91089b41199d681b653ff57`; output `b2t_ai_output_v1` |
| **C** Data handling | What leaves the machine, where, retention, terms reviewed | the five transmission fields; the destination path as resolved on this machine; `retention_days`; `provider_data_terms_reviewed` | fields: `item_id, batch_date_utc, source_domain, url, title` |
| **D** Execution | This item set under these limits | experiment ID; item-set hash; `run_id`; every limit | item set `f88185acaa32068757fa778e8f655b1c9aa081931dd78ca02d9ca79a8cdacb10` (1,493 items) |

- **Final hashes do not exist yet.** They depend on choices you have not made. The values my probe printed came from a placeholder config and **must not be approved**. After you fill in the config, `ai dry-run` prints the four hashes to approve.
- **Moving the repository** changes the resolved destination path and so invalidates Gate C. Changing any limit invalidates Gate D, and changing the model invalidates Gate B.

**Prerequisite 1: the build lock.** `AI_SUGGESTIONS_ENABLED_IN_THIS_BUILD` is `False` [VERIFIED]. Changing it to `True` is a reviewed code change made last, after Gates A–D. It does not start anything alone: the config, `--confirm-ai-run`, an adapter and the four gates are all still required.

**Prerequisite 2: a provider adapter.** The registry is empty [VERIFIED]. An adapter for the provider you pick must:

- register under the exact approved provider name and accept `(config, authorization)`;
- return the served model ID and version (the run stops if the served model differs from the approved one), plus a request ID and token counts where available;
- map failures to the defined error kinds so retries follow the limits, and never log or store the key;
- also be tested offline with a fake transport and a canary-secret check.

Further points to settle before Gate B:

- Many APIs return a model alias, not a dated version. The config **requires** a non-empty `model_version`. Whether your chosen model reports one is **[UNVERIFIED]**.
- Adding sampling parameters (such as temperature 0) to the config, the Gate B hash and the run record is a code change. Some newer models may not let you set them.
- The isolation test currently bans network and SDK imports in the `ai/` package. Either the adapter lives in a separate, separately approved module, or the test is narrowed for one file.
- A new library needs your approval under `CLAUDE.md`.

---

## 8. Verification: the dry run is non-destructive and `ai run` stays blocked

Run on 2026-10-19 with a placeholder config kept in the scratchpad (not in the repository), pointing at the real **original, unlabelled** `annotation_A.csv`. No model was invoked and the sealed key was not opened (its size was read).

| Check | Result |
| --- | --- |
| `ai dry-run` | Exit 0. Reports `provider_called: false`, `data_sent: false`, `files_written: false` |
| Files before and after (568 files under `datasets/`: size, modified time, SHA-256, key by size and time only) | **Identical** |
| New destination folder created? | **No** |
| `ai run --confirm-ai-run` | **Exit 3**, `BLOCKED: ... (12 unmet prerequisites)`, listing the build lock, provider fields, credentials variable, both caps, terms reviewed, retention, run ID and all four gates |
| `ai run` without the flag | **Exit 3**, 13 unmet prerequisites (adds the missing flag) |
| `ai progress` before `ai init` | Exit 1 with a clear error; wrote nothing |
| Build lock; adapter registry | `False`; `{}` |

**Real counts from the dry run** [MEASURED]: 1,493 items, all 1,493 sendable, none held back, 312 historical overlap items, 0 blind items.

The offline tests (§10) also cover the same behaviour on synthetic fixtures, including that a fully approved config is still blocked by the two code locks.

---

## 9. Current verified state

| Item | Value |
| --- | --- |
| Items / overlap / non-overlap | 1,493 / 312 / 1,181 |
| Labelled; AI suggestions | 0; 0 |
| `annotation_A.csv`; backup; working copy | `11db13e668bd3da8…` (all three identical) |
| `annotation_B.csv` | `211729002893c1e4…` |
| Sealed key | 142,900 bytes, modified 2026-10-13 22:28 +0530; **not opened** |
| Freeze, evaluation, AI or `b2t` files under `datasets/` | none |
| GDELT `NETWORK` and `DEV_SAMPLE` switches | still `True` (unchanged; your decision to lock them is still open) |
| Pip freeze fingerprint | `3393be502c93f2299cc40bc2ac786caf`, unchanged |

---

## 10. Tests

- `pytest tests/backend/data/gdelt -q -p no:cacheprovider`: **430 passed** (unchanged from B2-U3; this task added no code and no tests).
- Not run: the hosted-database backend suite, which needs network access that was not authorised.
- The §8 checks are a one-off script in the scratchpad; the repeatable form is `ai dry-run --experiment <yaml>` and `ai run --experiment <yaml> --confirm-ai-run` as in the B2-U3 report.

## 11. Other things to know

- **Rubric header wording.** `rubric_v1.md` says it "adds no label, code or rule". That is true of the labels; it does add the AI-output requirements in §6.3.
- **Evaluation code for the new dataset does not exist** (§2). Both blind-subset agreement and the filter estimates need it.
- **Not changed, as instructed:** the original files, the rubric, the validator, and the pipeline code.

## 12. Sources (retrieved 2026-10-19)

- Anthropic pricing, full page: https://platform.claude.com/docs/en/about-claude/pricing
- Anthropic API and data retention: https://platform.claude.com/docs/en/manage-claude/api-and-data-retention
- Anthropic commercial retention: https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data
- Google Gemini API pricing (page dated 2026-10-16): https://ai.google.dev/gemini-api/docs/pricing
- Google Gemini API terms (effective 2026-03-23): https://ai.google.dev/gemini-api/terms
- OpenAI pricing: https://developers.openai.com/api/docs/pricing
- OpenAI data controls: https://developers.openai.com/api/docs/guides/your-data
- GDELT terms of use: https://www.gdeltproject.org/about.html
