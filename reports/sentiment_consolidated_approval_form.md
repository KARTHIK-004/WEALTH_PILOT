# Sentiment model: consolidated approval form (one reply resolves everything)

Written for the project owner. **Status: ANSWERED IN PART (2026-10-29).** The owner approved **E1** and **E2**, explicitly left **R14 (F1)** unresolved, and supplied no value for any other ID, so every other Entry is `KEEP UNRESOLVED` (the D10 to D13 gates, C1 to C4, keep the repository's `BLOCKED` status). A recommendation was never taken as an answer. **Second reply (2026-10-29):** the owner selected `ProsusAI/finbert` (A1), recorded B2, A3.9 to A3.13 and E5, and gave provisional values for A3.1 to A3.8; Phase 2 unlocked and ran twice - the first run (2 requests) was stopped by a tool defect and the owner-approved re-run (3 requests) completed it; 5 of 10 requests in total, all anonymous to `huggingface.co` (see "Phase 2 result"). Nothing else the form describes has been done:
no download, no model, tokenizer, `config.json`, dataset or user text accessed, no package installed, no annotation, nothing activated.

## How to answer

- Reply with one line per ID, for example `A1: REJECT`, `A2: cardiffnlp/twitter-roberta-base-sentiment-latest`, `A3.1 R7: ACCEPT (CC BY 4.0, read at the pinned revision)`, `C3: <named environment path>`. Any ID you do not answer stays **UNRESOLVED**.
- **A recommendation is not an answer.** Where this form says "candidate" or "proposal" it is *my* suggestion or an earlier recorded proposal; it takes effect only if you write it as your entry. Silence approves nothing.
- A licence "accepted" here means *you* accept it as a legal reading for this project. I do not give legal advice and I cannot read a licence for you; the model cards' texts are not in the repository (only the claims recorded on 2026-10-20).
- **Standing rules, not decisions (already in code or recorded):** no floating branch, tag or `main` is ever used — only a full 40-character lowercase commit hash you approve; `trust_remote_code=False`; `local_files_only=True` unless a run is explicitly approved to download; `use_safetensors=True`; CPU only; the rules baseline `user_text_rules_v1` stays active and `SENTIMENT_MODEL_ENABLED=false` until R14; sentiment never touches risk, goals, portfolio, recommendations, compliance or any financial calculation; raw text and personal data are never logged, persisted, cached, sent externally or written to the ledger or blockchain.

## What each answer unlocks (the phases do not start until their rows are answered)

| Phase | Needs (all) | What I would do | Work that does not exist yet |
| --- | --- | --- | --- |
| 2 Metadata-only query | exactly one of A1 / A2 approved and its identifier recorded in B2, A3.9 to A3.13, B1 to B10 (A3.1 to A3.8 are **provisional** and not required) | read only the approved items of the approved repository, record revision, file list, licences, redirects; stop on any conflict | a minimal audited query tool (E1) |
| 3 Environment | C3 (D12), C4 (D13), and C1 (D10) if the environment will load a model | disposable environment outside the repository from the hash-pinned S1 set; `pip check`; record hashes, licences, sizes, advisories | none (the S1 list exists) |
| 4 Checkpoint download | A1/A2 and A3.1 to A3.13 for the model with **A3.1 to A3.8 confirmed (no longer provisional) by the phase 2 verification**, C1, C2 (D11), C3, C4 | download only the approved files at the approved revision, verify SHA-256, safetensors only, write `model_metadata.json` | **a verified fetch step (E1)**: today the download happens implicitly inside training |
| 5 Dataset and annotation | D1 to D20 (R8 to R13), E3, E4 | build or acquire only the approved data, freeze, de-duplicate, verify hashes | a real frozen manifest (E3); an approved frozen rubric (D5) |
| 6 Offline evaluation | phases 3 to 5 complete | rules baseline, approved Transformer, approved comparison; full report; gates | a predictions format with probabilities (E2) if calibration is to be evaluated |
| 7 R14 activation | phase 6 complete and F1 | nothing is activated without F1 | — |

---

## Resulting state (2026-10-29)

Each Entry is exactly one of `APPROVE`, `REJECT`, `KEEP UNRESOLVED`, `BLOCKED`. Totals over the 56 IDs: **44 APPROVE** (A1, A3.1, A3.2, A3.4, A3.6 to A3.13, B1 to B10, C1 to C5, D3, D4, D6 to D13, D15, D17, D18, E1, E2, E4, E5), **2 REJECT** (A3.5, D20), **0 BLOCKED**, **10 KEEP UNRESOLVED** (A2, A3.3 [provisional], D1, D2, D5, D14, D16, D19, E3, F1).

| Phase | State | Why |
| --- | --- | --- |
| 2 Metadata-only query | **COMPLETED (2026-10-29): metadata verification done in two runs, see "Phase 2 result, completed by the re-run"** | exactly one candidate (A1 `ProsusAI/finbert`; A2 unresolved), B2 recorded, A3.9 to A3.13 approved, B1 to B10 approved, E5 approved; A3.1 to A3.8 are provisional and Phase 2 is the step that verifies them. The query tool is built and tested offline |
| 3 Environment | **EXECUTED for the disposable S1 environment (2026-10-29: created, validated, deleted); C4 (TASK-CERT-1) COMPLETED the same day** | the owner approved S1 and the PyPI retrieval; C4 (D13) is satisfied by the completed project-environment remediation; see "Phase 3 execution" and "TASK-CERT-1 execution" |
| 4 Checkpoint download | **LOCKED** | needs an approved model with all of A3.1 to A3.13, the verified metadata (phase 2), C1 to C5 (D10 to D13 and the cache location) **and** E1; only E1 is approved |
| 5 Dataset and annotation | **LOCKED** | D1 to D20 and E3 are unresolved |
| 6 Offline evaluation | **LOCKED** | needs phases 3, 4 and 5; and `validated` additionally needs E2 (approved) |
| 7 R14 activation | **LOCKED** | F1 is unresolved by explicit decision; no evaluation exists; no report recommends activation |

**Approved capabilities that are not phases:** E1 (the verified fetch step) and E2 (probability-bearing predictions for calibration). They authorise *building* those things, with fakes and without any network use; they unlock no phase. **Both are now built offline (2026-10-29, `training/sentiment/hub_fetch.py` and the probability-bearing predictions of `evaluate_sentiment_model.py`) and tested with fakes and a loopback server only; neither has ever contacted a real host.**

**Dependency rules this form is held to (tested):** an unanswered ID is unresolved; a rejected or blocked item never unlocks a phase; no model download without an approved model (A1 or A2) with all of its A3 items, the metadata verification, D10 to D13 (C1 to C4), the cache location (C5) and E1; no evaluation without R8 to R13 (D1 to D20), a real frozen manifest (E3) and phases 3 and 4; no activation without a separate F1 approval; `validated` is unreachable without E2.

**What is needed next (updated 2026-10-29):** the owner's decision on A3.1 to A3.8 in the light of the Phase 2 result (A3.2, A3.3 and the suitability item have insufficient evidence, share-alike scope and the permitted-file list are unresolved), then C1 to C5, D1 to D20, E3 and E4 and the E1 mechanism, and F1 last. The earlier list follows for the record: to unlock Phase 2, exactly one of A1 / A2 approved, B2 (its identifier) and A3.9 to A3.13 (hosts, destination, SHA-256 policy, cleanup and rollback, evaluation-only versus training), plus authorisation to build the B9 query tool; later, the confirmation of A3.1 to A3.8 by the Phase 2 result, then C1 to C5, D1 to D20, E3 and E4 and the E1 mechanism. Until then nothing starts.

---

## A. Model selection (R6, R7)

| ID | Decision | Options | Entry |
| --- | --- | --- | --- |
| A1 | R6 `ProsusAI/finbert` | APPROVE / REJECT / UNRESOLVED | APPROVE (2026-10-29). Value: `ProsusAI/finbert` as the one selected candidate. A2 is `KEEP UNRESOLVED`, so exactly one candidate is selected. This selects a restricted, read-only, metadata-only Phase 2 query and nothing else: not a download, not training, not validation for personal-finance text, not activation |
| A2 | R7 candidate (exactly one) | `FacebookAI/roberta-base` / `cardiffnlp/twitter-roberta-base-sentiment-latest` / `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis` / REJECT / UNRESOLVED | KEEP UNRESOLVED (2026-10-29: the owner kept A2 unresolved; with A1 approved, exactly one candidate is selected and no other candidate is queried) |

### A3. For each model you approve in A1 or A2 (answer once per model, quoting R6 or R7)

| ID | Item | Recorded facts (RECORDED = a model-card claim read on 2026-10-20 or a single secondary snapshot; nothing here is verified permission) | Entry |
| --- | --- | --- | --- |
| A3.1 | Model licence accepted | R6: CC BY-NC-SA 4.0 (RECORDED claim). R7 `roberta-base`: none recorded. R7 `cardiffnlp`: CC BY 4.0 tag from one secondary snapshot, card text never read. R7 `mrm8488`: Apache-2.0 claim, card auto-generated and inconsistent on its face | APPROVE (2026-10-29, owner statement). Value: CC BY-NC-SA 4.0 is accepted for **non-commercial offline evaluation only**; **not legal clearance** (the licence text was not independently reviewed). Phase 2 verified the declared licence from the tag, the front matter and the card's licence section |
| A3.2 | Tokenizer licence | none recorded for any candidate (no `LICENSE` file was listed for FinBERT); whether the tokenizer files fall under the repository licence is unresolved | APPROVE (2026-10-29, owner decision, fourth brief): ACCEPT ABSENCE OF A SEPARATE TOKENIZER LICENSE STATEMENT FOR NON-COMMERCIAL OFFLINE EVALUATION ONLY. No tokenizer redistribution, no commercial use; the model-card licence and the absence of a separate statement are not legal clearance. **Superseded earlier text:** KEEP UNRESOLVED (PROVISIONAL, owner rule 2026-10-29, Option 2: not required before Phase 2; Phase 2 may verify, confirm or reject it; it authorises no download, tokenizer access, config access, dataset access, training or inference; it must be confirmed before Phase 4) **Owner value (2026-10-29):** PROVISIONALLY ACCEPT for Phase 2 verification only; final acceptance is BLOCKED until the tokenizer licence terms are confirmed. **Owner brief (2026-10-29, second listing of the options):** no option chosen (options: accept the absence of a separate tokenizer licence statement for offline evaluation only, with no tokenizer redistribution or commercial use / reject / keep unresolved). Stays `KEEP UNRESOLVED`. |
| A3.3 | Training-data licence and provenance accepted | R6: Financial PhraseBank (CC BY-NC-SA 3.0) and Reuters TRC2 (NIST access terms). `cardiffnlp`: about 124 million tweets (aggregator page, unverified). `mrm8488`: `financial_phrasebank`, 4,840 sentences. `roberta-base`: unresolved | KEEP UNRESOLVED (PROVISIONAL, owner rule 2026-10-29, Option 2: not required before Phase 2; Phase 2 may verify, confirm or reject it; it authorises no download, tokenizer access, config access, dataset access, training or inference; it must be confirmed before Phase 4) **Owner value (2026-10-29):** PROVISIONALLY ACCEPT for Phase 2 verification only; Phase 2 must check Financial PhraseBank, Reuters TRC2 and all access terms. **Owner brief (2026-10-29, second listing of the options):** no option chosen (options: keep unresolved because Reuters / TRC2 terms were not independently read / reject / accept for offline evaluation only with explicit unverified-terms risk acceptance). Stays `KEEP UNRESOLVED`; no Financial PhraseBank or Reuters / NIST permission is claimed as verified. |
| A3.4 | Commercial / non-commercial position | R6: non-commercial if the claim is confirmed; whether a research prototype whose output feeds an advisory demo is "non-commercial" is your reading, not the card's | APPROVE (2026-10-29, owner statement). Value: **non-commercial offline evaluation only**. No commercial, training, distribution or production use is authorised unless separately approved |
| A3.5 | Attribution and share-alike | R6: BY and SA ("adaptations must be shared under the same license"); whether SA reaches outputs or features, or only redistributed weights, is unresolved. A fine-tuned model is an adaptation | REJECT (2026-10-29, owner statement). A3.5a, the model-card attribution obligation, is ACCEPTED (the exact attribution text is still required before any distribution; it is not captured and not invented). **A3.5b, share-alike, is REJECTED until the legal scope is verified**: use of the model is not approved until then, with no claim that share-alike does or does not reach weights, adaptations, features or outputs. A rejected item never unlocks a later phase, so the download stays locked |
| A3.6 | Suitability limits accepted | R6: English company-news sentences, not personal narratives. `cardiffnlp`: tweets, not personal finance. `mrm8488`: financial news. `roberta-base`: no sentiment head, cannot be scored without a training set. **None is validated for personal-finance text; Financial PhraseBank is not sufficient validation** | APPROVE (2026-10-29, owner statement). Value: accepted as an **offline research candidate only, NOT validation**. FinBERT is not validated for personal-finance narratives; financial-news training does not establish suitability for them |
| A3.7 | Exact 40-character lowercase revision | RECORDED proposals only, never approved: FinBERT `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`; `mrm8488` `ae0eab9ad336d7d548e0efe394b07c04bcaf6e91`; none recorded for the other two. You may write the hash, or approve the metadata query B1 to read it | APPROVE (2026-10-29, owner statement). Value: the exact immutable revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` is confirmed (Phase 2 verified it: `model_info` and `revision_info` returned it in both runs). No floating branch, tag or short hash is ever used |
| A3.8 | Exact permitted files | none recorded (no file listing was ever saved). Candidate shape, to be confirmed against the real listing: the configuration, one safetensors weight file, the tokenizer files the model needs; nothing in `.bin`, `.pt`, `.pt2`, `.h5`, `.msgpack`, `training_args.bin` | APPROVE (2026-10-29, owner statement). Value: the five-file allow-list `model.safetensors`, `config.json`, `vocab.txt`, `tokenizer_config.json`, `special_tokens_map.json`. Never download `pytorch_model.bin`, `tf_model.h5`, `flax_model.msgpack`, any unexpected file, or any dataset or training artifact; every other file is rejected. The four files without a published API hash are hashed independently at the first approved download and added to the immutable manifest before use (verification, not approval of unknown contents). This approves a list only: it authorises no download |
| A3.9 | Permitted download hosts and redirects | only `huggingface.co` is on record (the 2026-10-20 read: 6 requests, HTTP 200, no redirects). **No file-serving host is on record and none is assumed**; weight files are normally served after a redirect (expected, not verified) | APPROVE (2026-10-29). Value: **`huggingface.co` only**; reject every other host and every redirect to another host |
| A3.10 | Destination directory | candidate: a directory outside the repository per `<identifier>@<revision>`, for example under `C:\Users\Administrator\.copilot\` (a base checkpoint is not a project artifact; `models/sentiment/` ignores `.safetensors` but is for trained artifacts) | APPROVE (2026-10-29). Value: `C:\Users\Administrator\.copilot\wealthpilot-approved-models\ProsusAI-finbert\0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` (outside the repository). Nothing is written there in Phase 2 |
| A3.11 | SHA-256 verification | candidate: record the SHA-256 of every downloaded file before first use; where the metadata supplies a content hash, compare; a mismatch aborts and deletes | APPROVE (2026-10-29). Value: independently hash every permitted downloaded file and compare it with the approved manifest before use. Nothing is downloaded in Phase 2 **Owner clarification (2026-10-29):** the four listed files without a published API hash (`config.json`, `vocab.txt`, `tokenizer_config.json`, `special_tokens_map.json`) are hashed independently during the first approved download and added to the immutable artifact manifest before use; this is verification, not approval of unknown contents. Only `model.safetensors` has an API-published hash. |
| A3.12 | Cleanup and rollback | candidate: delete the destination, caches and partial files on any mismatch, refusal or on request; nothing is added to the repository, the project environment or the database | APPROVE (2026-10-29). Value: delete incomplete, unexpected or mismatched artifacts and temporary cache; never reuse partial downloads |
| A3.13 | Use of the weights | OFFLINE EVALUATION ONLY / EVALUATION AND TRAINING. Training makes an adaptation (R6: share-alike) and needs a training split (D14) | APPROVE (2026-10-29). Value: **`OFFLINE_EVALUATION_ONLY`**; no training and no production activation |

## B. Metadata-only query (Phase 2)

A metadata query authorises **no** file, tokenizer, weight or dataset access, and choosing a candidate does not authorise it.

**Owner constraint on the query (stated 2026-10-29, twenty-first brief; a constraint, not an approval of B1 to B10):** the query is **read-only** and downloads **none** of: weights, tokenizer files, model configuration files, datasets, training artifacts. If B1 is rejected or unresolved, B2 to B10 stay unresolved and Phase 2 stays locked.

| ID | Decision | Candidate (not an answer) | Entry |
| --- | --- | --- | --- |
| B1 | Approve one metadata-only query? | YES / NO | APPROVE (2026-10-29). Value: a **metadata-only query**, read-only and anonymous, of the **one explicitly selected model identifier only**, under the restrictions of B2 to B10. It downloads and requests no weights, tokenizer files, `config.json`, datasets, training artifacts or generated model files. **Nothing can run until a candidate is selected (A1 or A2) and B2 and A3.9 to A3.13 are answered** |
| B2 | Exact model identifier(s) | the ones you approve in A1/A2 | APPROVE (2026-10-29). Value: **`ProsusAI/finbert`** (equal to the candidate approved in A1). Only this identifier may be queried |
| B3 | Items to read | API metadata (the model's information record), the model card text, the file listing (names, sizes, content hashes if the API gives them); **NOT config files, weights, tokenizer files, datasets or training artifacts** (owner constraint above; the 2026-10-29 candidate no longer lists `config`: a label order is therefore read from the model's `config.json` only later, after an approved download) | APPROVE (2026-10-29). Value: query only (1) API metadata, (2) model-card text, (3) licence metadata, (4) the repository file listing, (5) immutable revision metadata, (6) redirect metadata if exposed. Do not request or download weights, tokenizer files, `config.json`, datasets, training artifacts or generated model files **Owner clarification (2026-10-29):** README / model-card text is covered by B3 as sanitized metadata text only; never weights, tokenizer files, `config.json`, datasets or training artifacts. |
| B4 | Maximum request count | the 2026-10-20 precedent was 3 anonymous GETs per model | APPROVE (2026-10-29). Value: a maximum of **10 requests**; stop before an eleventh |
| B5 | Permitted hosts | `huggingface.co` only | APPROVE (2026-10-29). Value: **`huggingface.co` only**, unless the approved API response redirects to an official Hugging Face metadata endpoint. No endpoint is named in the approval, so an unnamed redirect target is treated as an unapproved host and stops the query (the owner may name one) **Owner clarification (2026-10-29):** `https://huggingface.co` only; no endpoint is named beyond it, so unnamed, non-Hugging-Face or file-download redirect endpoints stop the query. |
| B6 | Redirect policy | abort on any redirect to a host not named here | APPROVE (2026-10-29). Value: **do not follow a redirect to a weight or file-download host**; a redirect to any host that is not an approved metadata endpoint stops the query |
| B7 | Anonymous / token | anonymous, no token, no account | APPROVE (2026-10-29). Value: **anonymous, read-only API access**; no token, no cookie, no account; stop if the API requires authentication |
| B8 | Response storage location | a directory outside the repository, deleted after the decision unless you say otherwise | APPROVE (2026-10-29). Value: store **only sanitized metadata in the approval report** (`reports/sentiment_model_approval_record.md`); store no tokens, cookies, raw personal data or model files; no other copy of a response is kept |
| B9 | Tool | a purpose-written standard-library script that enforces B4 to B6 and writes only B3 to B8 (needs E1), or you fetch the pages yourself and give me the files | APPROVE (2026-10-29). Value: the method is **anonymous read-only API access** limited by B3 to B8. **The tool that enforces the 10-request cap, the host check, the no-file rule and the stop conditions was built offline in this phase** (E1 covers the fetch step only; the query tool is built as the same module's separate `query_metadata`; `training/sentiment/hub_fetch.py::query_metadata`, standard library only, tested with a scripted transport and a loopback server, then run once against `huggingface.co` on 2026-10-29, see "Phase 2 result"). Open points for the owner: the model card is read from `README.md`, which this record reads as B3 "model-card text" and not as B10 "access a file" (say so if it should be narrowed); B5's "official Hugging Face metadata endpoint" must be named, because an unnamed redirect target is treated as an unapproved host; two candidates have no recorded proposed revision to compare. Phase 2 stays locked |
| B10 | Stop condition | stop and report if the returned revision, licence, file list or host differs from anything you approved | APPROVE (2026-10-29). Value: **stop immediately** if (1) the model identifier differs; (2) the revision differs from the proposed value; (3) the licence or data terms conflict with the provisional record; (4) an unapproved host appears; (5) the request would access a file; (6) the API requires authentication; (7) the request count would exceed 10 |

### Phase 2 gate (rule decided 2026-10-29: Option 2, the revision, files and licences are provisional until Phase 2)

**Owner rule:** A3.1 to A3.8 are **PROVISIONAL** for the selected candidate until Phase 2 metadata verification. Phase 2 may verify, confirm or reject: the model licence, the tokenizer licence, the training-data terms,
the commercial-use restrictions, the attribution and share-alike requirements, the suitability limitations, the exact immutable revision and the permitted file list. **No provisional item authorises a download,
tokenizer access, config access, dataset access, training or inference.** A3.9 to A3.13 (permitted hosts, destination directory, SHA-256 policy, cleanup and rollback, evaluation-only versus training) must be
explicitly approved **before** Phase 2 can unlock.

**Phase 2 unlocks only when all of these hold:** exactly one candidate is selected (one of A1 / A2 approved, not both); its identifier is recorded in B2; A3.9 to A3.13 are approved; B1 to B10 are approved; and
C1 to C5, D1 to D20, E3, E4 and F1 remain locked (they are not needed and are not changed). **E1 stays fetch-only and does not authorise the query's file access.**

**After the query:** confirm or reject A3.1 to A3.8; keep the candidate unresolved if any metadata is missing or conflicting; download nothing, install nothing, access no dataset, create no real manifest, enable
nothing. A rejected or unconfirmed item keeps Phase 4 locked.

The remaining reply that unlocks Phase 2 (one line each):

```
A1: APPROVE ProsusAI/finbert (or REJECT / KEEP UNRESOLVED)      -or-      A2: APPROVE <one identifier> (or REJECT all / KEEP UNRESOLVED)      [exactly one candidate]
B2: <that identifier>
A3.9: <permitted download hosts>    A3.10: <destination directory>    A3.11: <SHA-256 policy>    A3.12: <cleanup and rollback>    A3.13: EVALUATION ONLY | EVALUATION AND TRAINING
```

Three things the approval left open, recorded rather than guessed: (1) B5 allows a redirect to "an official Hugging Face metadata endpoint" without naming one, so an unnamed endpoint stops the query unless you name
it; (2) B10 stops the query if the revision "differs from the proposed value", but only FinBERT (`0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`) and `mrm8488` (`ae0eab9ad336d7d548e0efe394b07c04bcaf6e91`) have a
recorded proposal; for `roberta-base` and `cardiffnlp` there is nothing to compare, so the discovered revision would be reported for confirmation (A3.7) rather than treated as a conflict, unless you say otherwise;
(3) the query tool (B9) must be built before Phase 2 can run, which is a code change that needs its own authorisation.

### Phase 2 result, first run (2026-10-29: STOPPED by the tool; superseded by the re-run below)

Run under B1 to B10 and E5 for `ProsusAI/finbert` only, proposed revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` (A3.7), provisional licence `CC BY-NC-SA 4.0` (A3.1). Sanitised metadata only (B8); no raw response is kept.

| Field | Result |
| --- | --- |
| Requests | **2 of 10** (`model_info`, `revision_info`); the third (model card) was never sent |
| Hosts / redirects | `huggingface.co` only; no redirect |
| Authentication | none required (anonymous; `gated` = false) |
| Discovered revision | `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` - **equal** to the proposed revision, and `revision_info` at that hash returned the same hash |
| Licence metadata | `cc-by-nc-sa-4.0` (one licence tag); **consistent** with the provisional A3.1 value; the licence text and the model card were NOT read |
| Library / task | `transformers`, `text-classification`; tags include `safetensors`, `finance`, `financial-sentiment-analysis`, `arxiv:1908.10063` |
| Files / downloads | **none requested**; the file listing was **not obtained** |
| Stop | `malformed_response` while reading the file listing |

**Cause (probable, not proven).** The tool's file-name pattern refused a name beginning with a dot, and almost every Hub repository lists `.gitattributes`. The raw listing was not kept (B8), so this is an inference. It is fixed offline: a listing may now contain one leading-dot name (`_LISTED_NAME`), traversal names are still refused, and the download path keeps the strict pattern. 98 tests pass (`test_hub_fetch.py`), two new deliberate defects are detected.

**Confirmations.** Because the run stopped with missing evidence, **no provisional field is confirmed or rejected**; A3.1 to A3.8 stay `KEEP UNRESOLVED (PROVISIONAL)`. Partial evidence only: A3.7 (the revision exists and equals the proposal) and A3.1 (the licence tag matches); A3.2, A3.3, A3.5, A3.6, A3.8 have no evidence yet (they need the model card and the file listing). A3.4 is a restriction, not a verifiable fact. Phase 2 is not complete, Phases 3 to 8 stay locked, and a re-run (3 more requests: `model_info`, `revision_info`, `model_card`; 5 of 10 in total) needs the owner's confirmation because B1 approved one query.

### Phase 2 result, completed by the re-run (2026-10-29: COMPLETE, no stop condition)

Run under the owner's re-run approval (recorded before any request; `reports/sentiment_model_approval_record.md`), `ProsusAI/finbert` only, revision `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`, policy cap 3 requests. Sanitised metadata only; the card text was read in memory and not stored.

| Field | Result |
| --- | --- |
| Requests | **3** (`model_info`, `revision_info`, `model_card`); with the first run **5 of 10** |
| Hosts / redirects | `huggingface.co` only; no redirect |
| Authentication | none (anonymous; `gated` = false) |
| Stop | none (`stopped` = null; no conflict) |
| Revision | `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` equal to the proposal |
| Licence metadata | `cc-by-nc-sa-4.0` |
| Model card | 4576 characters; SHA-256 of the text `32d38310f6343e42bb827b47b8342babf6173cfb47f4d28b8b557b4d92f80cb1`; headings: FinBERT, How to use, Model details, Training data, Training Data Attribution, Citation, About Prosus, Contact, License and Usage Terms, Model Weights License, User Responsibilities, Disclaimer |
| Files / downloads | **none requested**; the repository listing was read from the metadata |

**Sanitised file listing (10 files, as listed by the API):**

| File | Size (bytes) | SHA-256 from the API | Class |
| --- | --- | --- | --- |
| `.gitattributes` | 445 | none | git metadata |
| `README.md` | 4590 | none | the model card (read as text) |
| `config.json` | 758 | none | configuration (NOT accessed) |
| `flax_model.msgpack` | 437945404 | `04c231ff252c4b5ed3e277120b1cc961b97be14d81825c51c44ba66b4ee8033e` | **pickle-capable format: never fetch** |
| `model.safetensors` | 437965908 | `e5897858ff819aad7629b96ce521ae5477952d03634ef5dd30ed2d76357a9f00` | the only safetensors weight file |
| `pytorch_model.bin` | 437992753 | `e15a7b5738df7f17553399b6d94c6e2ff69c89245d066e8e5d183f5803a554e3` | **pickle-capable format: never fetch** |
| `special_tokens_map.json` | 112 | none | tokenizer file (NOT accessed) |
| `tf_model.h5` | 438196200 | `195e23248e2e9a4ffed51e671408e390d8b902f070d93dea3b06d8d5e3bfc1da` | **pickle-capable format: never fetch** |
| `tokenizer_config.json` | 252 | none | tokenizer file (NOT accessed) |
| `vocab.txt` | 231508 | none | tokenizer file (NOT accessed) |

**Provisional-field resolution (each exactly one of CONFIRMED / REJECTED / UNRESOLVED / INSUFFICIENT EVIDENCE; the owner's A3.5 to A3.8 numbering differs from this form's, see the notes in the rows):**

| Provisional field | Phase 2 verification | Evidence and limits |
| --- | --- | --- |
| Model licence (A3.1) | **CONFIRMED** (as the declared licence) | `cc-by-nc-sa-4.0` in the Hub licence tag, in the card's front matter, and in the card's own "License and Usage Terms / Model Weights License" section (CC BY-NC-SA 4.0 International). Three consistent sources, not the tag alone. The legal text was not read and the listing has no `LICENSE` file; whether the terms suit this project is the owner's legal reading |
| Tokenizer licence (A3.2) | **INSUFFICIENT EVIDENCE** | the card has no tokenizer statement; the card's licence section is headed "Model Weights License"; `vocab.txt`, `tokenizer_config.json` and `special_tokens_map.json` are listed but no separate licence covers them |
| Training-data licence and provenance (A3.3) | **INSUFFICIENT EVIDENCE** | the card names Financial PhraseBank (stated as CC BY-NC-SA 3.0) and the Reuters TRC2 corpus ("distributed by NIST under its own access terms"); the PhraseBank terms are a card claim and the TRC2 access terms were not read, so the combined terms are not verified |
| Commercial / non-commercial (A3.4) | **CONFIRMED** (the restriction exists) | the card states that the licence "restricts commercial use" and permits non-commercial purposes only, and leaves to the user whether a use qualifies as non-commercial. The owner's restriction (non-commercial offline evaluation only) is consistent with it; the qualification of this project's use remains the owner's reading |
| Attribution (A3.5, first half) | **CONFIRMED** (the obligation exists) | the BY component of the declared licence; the card has "Training Data Attribution" and "Citation" sections. The exact attribution wording was not recorded |
| Share-alike (A3.5, second half; the owner's A3.6) | **UNRESOLVED** | the card says "any adaptations must be shared under the same license"; it does not say whether that reaches weights, derivative artifacts, features or outputs. Offline evaluation without training makes no adaptation, but the scope question stays open |
| Exact permitted file list (A3.8) | **UNRESOLVED** | the complete listing is now known (table above) but the owner has not approved a list. Candidate for the owner (a proposal, not an answer): `model.safetensors` plus the configuration and tokenizer files the model needs (`config.json`, `vocab.txt`, `tokenizer_config.json`, `special_tokens_map.json`); never `flax_model.msgpack`, `pytorch_model.bin` or `tf_model.h5`. **Only `model.safetensors` has an API-published SHA-256**; the other four have none, so A3.11's comparison with an approved manifest needs those hashes recorded at the first approved download and approved by the owner |
| Personal-finance suitability (A3.6 in this form; the owner's A3.7) | **INSUFFICIENT EVIDENCE** | the card describes sentiment of *financial text* in the finance domain; nothing on personal-finance narratives. Financial-news training is not validation for them (the owner's constraint); the Phase 5 and 6 evaluation is the only way to produce such evidence |
| Exact immutable revision (A3.7 in this form; the owner's A3.8) | **CONFIRMED** | `model_info` and `revision_info` (in both runs) returned `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`, equal to the proposed revision |

Nothing is REJECTED. These are Phase 2 verification results, **not owner approvals**: A3.1 to A3.8 stay `KEEP UNRESOLVED (PROVISIONAL)` until the owner accepts them, and Phase 4 additionally needs all of them accepted. Phases 3 to 8 stay locked. No file, tokenizer file, `config.json`, weight or dataset was requested; no package installed.

### Pending owner decisions on A3.1 to A3.8 (first request, 2026-10-29; four rows were answered afterwards, see the next section)

The owner's 2026-10-29 brief listed the options for each field but chose none, and a verification result is not an approval, so, at that time, **every row below stays `KEEP UNRESOLVED`**. Nothing is inferred from the options or from the Phase 2 result. The candidate stays blocked for Phase 4 while any mandatory licence, provenance, file, host, hash or usage field is unresolved. No legal clearance is claimed: the licence text was not independently reviewed, and the NIST / Reuters TRC2 terms were not read.

| Field (this form's row) | Options offered | Phase 2 result | Status |
| --- | --- | --- | --- |
| Model licence (A3.1) | accept CC BY-NC-SA 4.0 for the approved scope / reject / keep unresolved | CONFIRMED as declared | KEEP UNRESOLVED |
| Tokenizer licence (A3.2) | accept the absence of a separate tokenizer-licence statement / reject / keep unresolved | INSUFFICIENT EVIDENCE | KEEP UNRESOLVED |
| Training-data provenance and terms (A3.3) | accept the recorded Financial PhraseBank and Reuters TRC2 terms for the approved scope / reject / keep unresolved | INSUFFICIENT EVIDENCE | KEEP UNRESOLVED |
| Commercial use (A3.4) | accept non-commercial offline evaluation only / reject / keep unresolved | CONFIRMED (restriction exists) | KEEP UNRESOLVED |
| Attribution (A3.5, first half) | accept the model-card attribution obligation / reject / keep unresolved (exact text is recorded only if available; it is not) | CONFIRMED (obligation exists) | KEEP UNRESOLVED |
| Share-alike (A3.5, second half) | accept only for an explicitly defined artifact scope / reject / keep unresolved (the scope for weights, adaptations, features and outputs is not established and must be defined by the owner) | UNRESOLVED | KEEP UNRESOLVED |
| Personal-finance suitability (A3.6) | accept only as a candidate for offline research evaluation, not validation / reject / keep unresolved | INSUFFICIENT EVIDENCE | KEEP UNRESOLVED |
| Immutable revision (A3.7) | confirm `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` / reject / keep unresolved | CONFIRMED | KEEP UNRESOLVED |
| Permitted file list (A3.8) | approve the proposed allow-list recorded in the A3.8 entry / reject / keep unresolved | UNRESOLVED | KEEP UNRESOLVED |

Recorded without choosing anything: the proposed allow-list and the never-download list (A3.8 entry), and the hash procedure for the four files without a published API hash (A3.11 entry, a clarification of an already approved item). Phase 3 still needs the environment and certificate / tooling approvals (C3, C4, and C1 if a model is loaded); Phase 4 still needs the download boundary, file list, hash, rollback and security approvals (C1, C2, C5, A3.1 to A3.8 accepted). Neither unlocks because Phase 2 verification succeeded.

### Owner statement of 2026-10-29 (resolution brief): what was recorded and what was not

The brief says A3.1, A3.4, A3.5a, A3.7 and A3.8 are "already recorded" decisions. They were **not** recorded as approvals before (the previous turn asked for them), so they are recorded now, from this statement, with the dates and scopes the owner gave. For A3.2, A3.3, A3.5b and A3.6 the brief again lists options without choosing, so they stay `KEEP UNRESOLVED`. Verification results remain separate from owner approval throughout.

| Row | Recorded | Status |
| --- | --- | --- |
| A3.1 model licence | accepted for non-commercial offline evaluation only; not legal clearance | APPROVE |
| A3.2 tokenizer licence | no option chosen | KEEP UNRESOLVED |
| A3.3 training-data terms | no option chosen; Reuters / TRC2 terms not read | KEEP UNRESOLVED |
| A3.4 commercial use | non-commercial offline evaluation only | APPROVE |
| A3.5 attribution / share-alike | A3.5a attribution accepted (exact text still required before any distribution); A3.5b share-alike no option chosen | KEEP UNRESOLVED |
| A3.6 suitability | no option chosen; not validated for personal-finance narratives | KEEP UNRESOLVED |
| A3.7 revision | `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031` confirmed | APPROVE |
| A3.8 file list | five-file allow-list approved (a list only; no download) | APPROVE |

**First-download controls (the owner's labels differ from this form's: the owner's C1 environment and package scope is this form's C3, C2 certificate remediation is C4, C3 Hub conversion is C1, C4 network and redirect boundary is C2, and the owner's "E4 evaluation-script format with probabilities" is E2, already approved and built; this form's E4 is the rubric / baseline alignment).** The brief supplies conservative defaults "unless the owner explicitly changes them" but no value for any of these items: no environment path or retention rule, no authorisation to install the pinned set, no certificate remediation or written risk acceptance, no Hub-conversion path (A, B or C), no named network boundary, no cache location. A default is not a choice among those options, so **C1 to C4 stay `BLOCKED`, C5, E3 and E4 stay `KEEP UNRESOLVED`**. E3 additionally cannot be decided before D1 to D19. The defaults are recorded as **restrictions only**, none of which unlocks anything: download only the five approved files and reject every other file; `huggingface.co` only and no redirect to another host; independently hash all five files and store the verified manifest before loading; a disposable environment outside the repository; delete partial artifacts and temporary cache on failure; `local_files_only=True` after download; never `trust_remote_code=True`; never download pickle-capable files; offline evaluation only; no training; no production activation.

**Phases.** Phase 2 stays complete; nothing new unlocks. Phase 3 needs C3 and C4 (and C1 if a model is loaded); Phase 4 needs A3.2, A3.3, A3.5 (both halves) and A3.6 accepted, C1 to C5 and E1; no download starts while any of them is open. The dataset, manifest and real evaluation need D1 to D20 and E3; activation needs F1 separately after evaluation.

### Phase 3 attempt (2026-10-29): NOT STARTED - nothing created, nothing installed

Owner statement recorded first (A3.5 REJECT, A3.6 APPROVE, C1 Path B, C2, C3, C5 approved; C4 decided as "complete TASK-CERT-1", still BLOCKED because the task is not done; A3.2 and A3.3 unresolved). Read-only checks, no network and no installation:

| Check | Result |
| --- | --- |
| TASK-CERT-1 | **BLOCKED, no work done** (`reports/sentiment_model_approval_record.md`); the owner's C4 decision requires it to be completed before any model download |
| Project environment | `certifi` 2026.7.22 and `pip` 26.2.1 - both in the range the recorded C4 facts call affected; Python 3.11.9 AMD64, Windows |
| C4 formally satisfied? | **No** - so the environment must not be created and no package installed |
| Approved local wheels | **none exist** (a search of the repository tree found no `.whl`; the earlier disposable environment and its wheel directory were deleted). Retrieval needs PyPI, and no recorded approval names it, so the phase stops before retrieval |
| Target paths | `C:\Users\Administrator\.copilot\wealthpilot-finbert-eval-venv` and `C:\Users\Administrator\.copilot\wealthpilot-hf-cache` do not exist; neither was created |
| Project environment packages | `torch`, `transformers`, `tokenizers`, `safetensors` not installed; `numpy` 1.26.4 |

**Two discrepancies for the owner (not resolved by me).** (1) The brief lists six packages, but the recorded S1 set is 35 to 36 hash-pinned wheels (their dependencies included, e.g. `huggingface-hub`), and `--require-hashes` needs every wheel pinned; "install only the six" cannot work. (2) The brief names `setuptools==81.0.0`, the form's C3 facts say 81.0.0, but the S1 hash table in `reports/sentiment_transformer_dependency_request.md` lists `setuptools` 84.2.1; one of them is wrong and I did not substitute a version.

**Path B code change required (documented, NOT applied).** `training/sentiment/train_sentiment_transformer.py` loads the base model from a Hub identifier (`--allow-hub-download` only switches the library online). For Path B it needs: (a) a local base-model directory parameter, mutually exclusive with the identifier, loaded with `local_files_only=True`, `use_safetensors=True`, `trust_remote_code=False`; (b) a precondition that the directory carries a verified manifest (the five approved files, every SHA-256 matching, no other file) and contains no pickle-capable file; (c) for offline evaluation, a loader that reads the same directory and writes a probability-bearing predictions file (the E2 format) for the frozen-set mode, with no training. The Hub library's own download path is never reached.

**Validation, cleanup and what could not run.** The offline checks of the brief (hash verification of wheels, `pip check`, CPU-only torch, imports, stand-in tests, no-socket / no-pickle / no-cache checks, TensorFlow coexistence) cannot run without the environment, so none was run and no result is claimed; the stand-in module stays skipped. Cleanup: nothing was created, so there is nothing to delete.

**Phase 3 remains LOCKED.** To unlock it: complete TASK-CERT-1 (C4), authorise wheel retrieval (the PyPI contact) for the exact pinned set, and settle the two discrepancies. Phase 4 additionally needs A3.2, A3.3, A3.5 (now rejected) and the Path B code change.

### Phase 3 unblock: offline preparation (2026-10-29) and the one consolidated decision request

**Verified facts (read-only, no network, nothing installed or changed).**

- **TASK-CERT-1 cannot be completed offline.** The project environment has `certifi` 2026.7.22 and `pip` 26.2.1; the other two Python installs on the machine have no `certifi` and older `pip` (24.0 and 24.3.1); there is no local wheel; the pip cache holds 1986 HTTP response files (1.5 GB, contents not enumerated) and 3 locally built wheels (`markupsafe`, `sqlalchemy`, `typing`; neither is `certifi` or `pip`), and an HTTP response cache cannot be used without contacting the index. Completing the task needs PyPI. The task card says: `certifi` 2026.10.19 or later, a `pip` whose vendored `certifi` is fixed (`pip` 26.2.2 exists; its vendored version has not been checked and cannot be checked offline), the full regression suite, a rollback record. **Prepared, not executed:** rollback = reinstall `certifi==2026.7.22` and `pip==26.2.1` from hash-pinned wheels (their hashes are recorded in the executed S1 list for `certifi` only; the `pip` hash would have to be recorded at retrieval).
- **The `setuptools` discrepancy is resolved by the record, not by a guess.** The early candidate table lists `setuptools` 84.2.1 and the affected `certifi` 2026.7.22 (the first proposal); the executed hash-pinned list of section L.3 lists `setuptools` 81.0.0 and `certifi` 2026.10.23 (installed twice with identical pins, 19 of 19 stand-in checks, 381 tests) and `setuptools==81.0.0` was accepted by the owner on 2026-10-27 for the disposable Windows pip-only environment. The executed list is authoritative; the early table now carries a superseded note and is unedited. No version was substituted. `tests/backend/core/test_s1_pin_list_records.py` pins both facts.
- **The six direct packages are not a sufficient `--require-hashes` set:** the authoritative list has 35 wheels (the six plus 29 others, e.g. `huggingface-hub`, `hf-xet`, `httpx`, `typer`, `sympy`, `jinja2`); every one needs its hash.
- **TensorFlow tooling and `setuptools`:** the project environment's `tensorboard` 2.17.1 imports `pkg_resources` in `default.py` (and `data/server_ingester.py`), which `setuptools` 82 or later no longer ships, so the project environment must stay below 82 (N6 is now a verified fact for the project environment). The disposable environment has no TensorFlow, and TASK-CERT-1 (`certifi` and `pip`) does not touch `setuptools`. The project `setuptools` is 65.5.0.
- **Path B code:** prepared as a new standalone module with synthetic-fixture tests; 22 of 22 deliberate defects are detected. It changes no existing file.

**The one consolidated decision request.** Nothing below was done; reply with one value per line, and an omitted line stays unresolved.

| Decision | Choices | Effect if chosen |
| --- | --- | --- |
| C4 certificate / tooling | `APPROVE TASK-CERT-1 PROJECT-ENVIRONMENT REMEDIATION` (upgrade `certifi` and `pip` in the project environment from PyPI, run the relevant regression tests, record exact versions and rollback) / `ACCEPT WRITTEN RESIDUAL RISK` (state the exact scope and expiry) / `KEEP UNRESOLVED` | the only way C4 stops being BLOCKED; nothing is done until chosen |
| PyPI retrieval | `APPROVE PYPI RETRIEVAL` (anonymous HTTPS, only the approved hash-pinned wheel set, no source distributions, no dependency resolution beyond the lock, no install until hashes and versions are verified) / `REJECT` / `KEEP UNRESOLVED` | needed for both the remediation and the wheels |
| S1 package set | `APPROVE THE 35-WHEEL LIST OF SECTION L.3 WITH setuptools==81.0.0` / `REJECT` / `KEEP UNRESOLVED` | fixes the exact pins for the disposable environment |
| Path B code | `APPROVE OFFLINE CODE CHANGE` (wire the prepared module into the trainer and the evaluation script; no Hub conversion; no production activation) / `REJECT` / `KEEP UNRESOLVED` | does not authorise any download |
| A3.2 tokenizer licence | accept the absence of a separate statement for offline evaluation only / reject / keep unresolved | |
| A3.3 training-data terms | accept for offline evaluation only with explicit unverified-terms risk acceptance / reject / keep unresolved | |
| A3.5b share-alike | currently REJECTED until the legal scope is verified; accept with a written artifact scope / keep rejected / unresolved | |
| C5 cache | the path `C:\Users\Administrator\.copilot\wealthpilot-hf-cache` is recorded; confirm the retention (delete after the phase or on failure) | |
| D1 to D20, E3, E4 | the dataset, annotation, frozen-manifest and evaluation-format decisions | needed only for Phases 5 and 6 |
| R14 | **must not be approved in this phase** | stays unresolved |

Execution order once the relevant approvals are recorded: TASK-CERT-1 (if approved), retrieve only the exact approved wheels, hash every file independently, create the disposable environment at the approved path only, install with `--require-hashes`, run `pip check`, the CPU, import, stand-in and coexistence checks, delete the environment, wheels and cache. Hugging Face is never contacted in Phase 3.

### Owner message of 2026-10-29 (consolidated request, second listing): what was recorded

The message again lists the choices for C4, PyPI retrieval, S1, Path B, A3.2, A3.3 and A3.5b without choosing one, so **none of them is recorded as decided** and each stays as it was (C4 BLOCKED; A3.2 and A3.3 `KEEP UNRESOLVED`; A3.5 REJECT; PyPI retrieval, the S1 set and the Path B wiring not approved). Recorded because it was stated: the C5 retention rules (see the C5 entry), and that D1 to D20, E3, E4 and R14 remain `KEEP UNRESOLVED` (R14 is not approved in this phase). Nothing was executed: no remediation, retrieval, environment or wiring. The unrelated GDELT scaffold failure is untouched.

### Phase 3 execution (2026-10-29): disposable S1 environment validated and deleted; TASK-CERT-1 stopped before any change; Path B wired offline

Owner approvals recorded first (C4 action, PyPI retrieval, the 35-wheel S1 list with `setuptools==81.0.0`, Path B wiring, C5). **TASK-CERT-1: STOPPED, nothing changed.** The approved lock has no `pip` wheel and the remediation needs `pip` moved to a release whose vendored `certifi` is fixed (outside the approved set), so the project environment was not touched (before = after: `certifi` 2026.7.22, `pip` 26.2.1, `setuptools` 65.5.0, `tensorflow` 2.17.0, `keras` 3.15.1, `numpy` 1.26.4; `pip check` clean). **Missing approval:** a named `pip` version with its wheel hash (and whether `certifi` alone may be upgraded now). C4 therefore stays BLOCKED. **PyPI retrieval:** 35 of 35 wheels, hosts `pypi.org` and `files.pythonhosted.org` only, every hash verified independently (dependency report, section S). **Disposable environment:** created at the approved path, `--require-hashes` install, `pip check` clean, CPU-only torch 2.13.0+cpu (`torch.version.cuda` is `None`, `torch.cuda.is_available()` is `False`), no NVIDIA / CUDA distribution, TensorFlow and PyTorch coexist in both import orders, 1124 tests passed and 2 skipped inside it, then the environment and wheels were deleted and the temporary cache path was never created. **Path B wiring (offline):** `local_model_dir.py` is used by the trainer (`--local-model-dir`, `--local-model-manifest`: a verified local directory instead of a Hub identifier, no download, recorded provenance = the manifest's identifier and revision) and by the evaluation script (`--local-model NAME=DIRECTORY` with `--local-model-manifest NAME=FILE`: predictions in the E2 format through the same gate as a precomputed file); no route, setting, schema or dependency changed. No Hugging Face contact, model, tokenizer, config, dataset or user text. A3.2, A3.3 unresolved, A3.5b rejected, D1 to D20, E3, E4, R14 unresolved.

### TASK-CERT-1 metadata phase (2026-10-29): candidate `pip` 26.2.2 found; its vendored `certifi` is NOT verified, so the version stays unresolved

Read-only. Two anonymous requests to `pypi.org` only (`/pypi/pip/json` and `/pypi/pip/26.2.2/json`), no redirect followed, nothing downloaded except those two JSON documents, no package installed or upgraded, the project environment untouched, no Hugging Face contact, no model, dataset or user text.

| Field | Result |
| --- | --- |
| Releases after 26.2.1 | **exactly one: 26.2.2** (PyPI's latest) |
| Release status | not yanked (wheel and sdist: `yanked` false, no reason); PyPI's `vulnerabilities` field for 26.2.2 is empty |
| Upload time | 2026-10-20T16:36:27Z (the wheel) |
| Wheel | `pip-26.2.2-py3-none-any.whl`, 1,819,850 bytes, SHA-256 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70` (PyPI digest) |
| Windows Python 3.11 | there is no Windows-specific `pip` wheel: the pure-Python `py3-none-any` wheel is the one every platform uses; `Requires-Python` `>=3.10` is satisfied by the project's Python 3.11.9; the project's installed `pip` 26.2.1 has the same `Requires-Python` |
| PEP 658 metadata file | present (SHA-256 `fe157a60a970b288770fad79a124001f538a325b0a2270c594792b6a475eb798`); it was NOT fetched |
| Source distribution | `pip-26.2.2.tar.gz` exists; it is not a candidate (wheels only) |
| Vendored `certifi` of 26.2.2 | **NOT VERIFIED.** PyPI's metadata and description say nothing about vendored packages, and `requires_dist` is empty. The vendored copy is recorded only inside the wheel (`pip/_vendor/vendor.txt`) and in pip's changelog (`pip.pypa.io/en/stable/news/`), neither of which is PyPI metadata. The upload date (the day after `certifi` 2026.10.19, the first fixed release) is circumstantial and is not treated as evidence |
| Before-state (local, read-only) | the project's installed `pip` 26.2.1 vendors `certifi==2026.6.17` (`pip/_vendor/vendor.txt`), inside the affected range |

**Candidate (NOT selected, NOT approved, NOT installed):** `pip` 26.2.2, `pip-26.2.2-py3-none-any.whl`, SHA-256 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`. Not selected because it is newer: it is the only later release, and the requirement (a fixed vendored `certifi`) is unverified, so the exact version stays **unresolved**.

**Policy (owner, recorded before the query).** `certifi==2026.10.23` is upgraded only together with the approved `pip` remediation and never alone; the project's `setuptools` 65.5.0, TensorFlow 2.17.0, Keras 3.15.1 and NumPy 1.26.4 stay unchanged; the S1 disposable environment stays separate; TASK-CERT-1 stays BLOCKED until the exact `pip` version and wheel hash are explicitly approved.

**What is needed next (a separate security decision, because official metadata alone cannot verify the vendored copy).** One of: (a) approve a read-only read of pip's official changelog or its source at the 26.2.2 tag for the vendored `certifi` version (an external service other than PyPI); (b) approve retrieving the single wheel above from PyPI into a scratch directory, verifying its SHA-256 against the value above and reading its `pip/_vendor/vendor.txt` and `pip/_vendor/certifi/__init__.py` without installing it (then deleting it); (c) accept the residual risk in writing with a scope and expiry; or (d) keep it unresolved. Only after the version and hash are explicitly approved can the remediation run.

### TASK-CERT-1 execution (2026-10-29): COMPLETED AND VERIFIED; C4 is now APPROVE

**Inspection (option (b)).** `pip-26.2.2-py3-none-any.whl` (1,819,850 bytes) was retrieved into a scratch directory, its SHA-256 recomputed independently and equal to `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`, only `pip/_vendor/vendor.txt` and `pip/_vendor/certifi/__init__.py` were read (`certifi==2026.10.19`), the wheel was not installed, and the scratch directory was deleted. 2026.10.19 is the first fixed release (GHSA-6q48-6c7w-9gw2).

**Upgrade (project environment).** Exactly two packages, hash-pinned, `--no-deps`, wheels only: `pip` 26.2.1 to **26.2.2** (SHA-256 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`) and `certifi` 2026.7.22 to **2026.10.23** (SHA-256 `e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1`, the S1 list's entry), driven by the base interpreter's `pip` 24.0 against the project interpreter. The `pip freeze --all` before and after (133 lines) differ in exactly four lines: those two packages. Unchanged: `setuptools` 65.5.0, `tensorflow` 2.17.0, `keras` 3.15.1, `numpy` 1.26.4, `tensorboard` 2.17.1, `requests` 2.34.2, `httpx` 0.27.2, `urllib3` 2.7.0, every application dependency. `backend/pyproject.toml` was not touched.

**Checks.** `pip check`: "No broken requirements found." The `RECORD` hashes of both installed distributions verify (`pip` 482 files, `certifi` 13 files, 0 mismatches). The installed `pip` vendors `certifi==2026.10.19` (`vendor.txt` and `__version__`); the top-level `certifi` is 2026.10.23; only two `cacert.pem` files exist in the environment (the top-level one and pip's vendored one), so no other vendored copy was found. `ssl.create_default_context(cafile=certifi.where())` loads 118 certificates and `requests.certs.where()` equals `certifi.where()`. TensorFlow 2.17.0 and Keras 3.15.1 import and run a tensor operation; numpy, pandas, scipy, sklearn, xgboost, statsmodels, pydantic, fastapi, sqlalchemy, alembic, uvicorn, langgraph, yfinance, shap and arch import; zero socket connection attempts during the checks. Regression: 1301 passed, 5 skipped (2 stand-in modules that need torch, 3 symbolic-link-privilege tests), the settings / configuration / security group 59 passed, the dry-run package verifier consistent.

**Advisory status.** GHSA-6q48-6c7w-9gw2 (use `certifi` 2026.10.19 or later): both copies present in the project environment now meet it (top-level 2026.10.23, pip's vendored 2026.10.19). Not done: no advisory database was re-queried (no approved access), and the task card's check that no project endpoint chains to a removed emSign root was NOT performed, because it needs a network connection to the project's endpoints. Observation, not interpreted: the bundles differ in labelled entries (before: 20 `emSign`-labelled entries in both copies; after: 5 in the top-level bundle and 15 in pip's vendored bundle).

**Rollback.** An offline backup of exactly the four replaced directories (`pip`, `pip-26.2.1.dist-info`, `certifi`, `certifi-2026.7.22.dist-info`; 491 files, tree SHA-256 `8da3684ee570782c3811494df0fa3ff2a9686fe2974e476264404a997d759801`, verified byte-identical to the originals when taken) is kept at `C:\Users\Administrator\.copilot\wealthpilot-taskcert-rollback` until the owner says to delete it. To restore: with no process using the environment, delete `.venv\Lib\site-packages\pip`, `pip-26.2.2.dist-info`, `certifi` and `certifi-2026.10.23.dist-info`, copy the four backup directories into `.venv\Lib\site-packages`, and check `python -m pip --version` reports 26.2.1 and `import certifi` reports 2026.7.22. Alternative (needs a new approval): reinstall `certifi==2026.7.22` (SHA-256 `62f22742b58a1a33014a2b6b706588a8d7e2a88ae7bd1a6ebe8c992928483775`) and a `pip` 26.2.1 wheel whose hash would have to be recorded at retrieval. No rollback was needed.

Nothing else changed: no Hugging Face contact, no model, tokenizer, config, dataset or user text, no S1 wheel in the project environment, production unchanged. C4 is APPROVE (completed); Phase 3 (the disposable environment, already executed and deleted) no longer has an open gate; Phase 4 still needs A3.2, A3.3, A3.5 (rejected) and the other open items.


### Consolidated decision request for the legal gate (Phase 1) and the dataset gate (Phase 2), asked 2026-10-29

The end-to-end brief of 2026-10-29 asks for these two forms and supplies **no value**, so nothing is approved by it and every row below stays as recorded. Phases 3 to 6 stay locked; no model file is downloaded, no text is generated, collected or labelled, and nothing is evaluated. Verification results are not approvals, and a recommendation is not an answer.

**Phase 1 - the three legal fields that keep FinBERT undownloadable.** Phase 4 also needs C1 to C5 (all approved), E1, the exact revision and the five-file list (approved) and the dataset and manifest approval if evaluation is planned.

| Field | Choices (write exactly one) | State now |
| --- | --- | --- |
| A3.2 tokenizer licence | `ACCEPT ABSENCE OF A SEPARATE TOKENIZER LICENSE STATEMENT FOR OFFLINE EVALUATION ONLY` (no redistribution, no commercial use) / `REJECT` / `KEEP UNRESOLVED` | KEEP UNRESOLVED |
| A3.3 training-data terms | `ACCEPT FOR OFFLINE EVALUATION ONLY WITH EXPLICIT UNVERIFIED-TERMS RISK ACCEPTANCE` (Financial PhraseBank and Reuters / TRC2 terms were not independently read and are not claimed verified) / `REJECT` / `KEEP UNRESOLVED` | KEEP UNRESOLVED |
| A3.5b share-alike | `ACCEPT ONLY FOR THE DOWNLOADED MODEL ARTIFACT AND DIRECT ADAPTATIONS; NO CLAIM ABOUT FEATURES OR OUTPUTS` / `REJECT USE UNTIL LEGAL SCOPE IS VERIFIED` / `KEEP UNRESOLVED` | REJECT (until the legal scope is verified) |

**Phase 2 - the dataset gate (the owner's R8 to R13, this form's D1 to D20).** The brief's 20 items map onto the existing rows; several are already decided by the approved evaluation policy and need only a confirmation, the rest need a value.

| Brief item | Row | State now | What is needed |
| --- | --- | --- | --- |
| 1 dataset source and licence | D1 | unresolved | a source (independently authored fictional statements / consented participant text / a named public corpus with its licence) |
| 2 personal-finance narrative provenance | D2 | unresolved | who authors the statements, independence from the rubric author and the baseline's cue lists, nothing copied from a benchmark |
| 3 fictional versus consented text | D3 | unresolved | one of the two, **and the deciding question: does independently authored fictional text count as valid evidence (`synthetic = false`) or is it synthetic (`synthetic = true`, so never `validated`)?** This decides whether `validated` is reachable at all; the existing fictional pilot examples are NOT validation evidence unless you approve that status here |
| 4 de-identification, 5 prohibited personal-data categories | D4 | unresolved | the method, who verifies it, the list of prohibited categories (the code already refuses e-mail, link and long-digit markers; the heuristic can miss) |
| 6 rubric freeze status | D5 | unresolved | a new version label (not `v0-draft`) and approval of the hash; differences (a) to (f) are on record, (f) unconfirmed |
| 7 two independent annotators, 8 third-person adjudication, 9 blinding | D6, D7 | unresolved | two annotators and one adjudicator as anonymous codes with independence attested by you; annotators see only the text and its id |
| 10 primary label set | D8 / policy | decided: `positive_negative_neutral` | confirm |
| 11 held-out 300, 12 minimum 75 per class | D9 | decided (300 total, 75 per class); quotas, coverage lists and "at least 30% hard" are proposals | confirm, change or drop the proposals; add a hypothetical / conditional coverage line |
| 13 training / calibration / held-out split rules | D10 | unresolved | sizes (none proposed); disjoint; training only if a model is fine-tuned (A3.13 is evaluation only) |
| 14 exact and near-duplicate removal | D11 | unresolved | case-folded exact match; near-duplicate method and threshold (earlier proposal: token-set Jaccard 0.8) |
| 15 topic and difficulty groups | D12 | unresolved | the group-dimension names declared in the manifest |
| 16 agreement, 17 multi-label deferred | D8 | decided: Cohen's kappa primary (no floor), multi-label agreement deferred; specific agreement and Krippendorff alpha are reports | confirm; the secondary statistics are reports, not gates |
| 18 probability-bearing calibration data, 19 minimum 20 scored examples | D13 | decided in the evaluation policy (E2; descriptive-only below 20) | confirm temperature scaling on the calibration split only and 10-bin equal-width ECE, report-only |
| 20 retention and deletion | D16, D17, D18 | unresolved | period, location, who may read, the deletion method and the withdrawal-versus-unlinkability conflict |
| coverage and abstention | D15 | decided gates (coverage at least 0.70, abstention at most 0.30) | confirm |
| validation design, permission | D19, D20 | unresolved | confirm the design; **no text may be generated, collected, downloaded or labelled until D1 to D19 are approved** |

The brief's "E3 frozen-manifest approval" is this form's E3 (create a real frozen manifest; only after D1 to D19). Its "E4 evaluation-format approval" is E2 (probability-bearing predictions, already approved and built); this form's E4 is the rubric / baseline alignment, which still needs your decision case by case.

**Reply format (one line per item; an omitted line stays unresolved):**

```
A3.2:  <choice>      A3.3:  <choice>      A3.5b: <choice>
D1: <source + licence>   D2: <provenance/authors>   D3: <fictional | consented> ; fictional evidence status: <valid evidence | synthetic>
D4: <method, verifier, prohibited categories>   D5: <frozen version label + approval of the hash>   D6: <annotator and adjudicator codes, independence attested>
D7: <confirm blinding>   D8: <confirm kappa primary / pre-adjudication agreement / adjudicated labels final>   D9: <confirm 300 / 75; keep or drop each proposal>
D10: <split sizes>   D11: <near-duplicate threshold>   D12: <group names>   D13: <confirm>   D14: <only if training>   D15: <confirm>
D16: <retention>   D17: <deletion>   D18: <access>   D19: <confirm>   D20: <approve generation/collection/labelling: yes | no>
E3: <approve the real manifest after D1 to D19>   E4: <decision per difference (a) to (f)>   R14: stays unresolved
```


### Owner reply of 2026-10-29 (legal, dataset, alignment and manifest brief): what was recorded and what was not

The brief lists the options for A3.2, A3.3, A3.5b, D3, D5, E3 and E4 **without choosing one**, asks for values (D1, D2, D4, the near-duplicate method and threshold, the split sizes, the group names, retention, deletion and access) **without giving them**, and gives direct approvals for a smaller set. Only the direct approvals are recorded; an option list, a request for a value and silence are not answers.

**Phase 1 - legal gate (unchanged; FinBERT stays undownloadable).**

| Field | Recorded now |
| --- | --- |
| A3.2 tokenizer licence | KEEP UNRESOLVED (no option chosen) |
| A3.3 training-data terms | KEEP UNRESOLVED (no option chosen) |
| A3.5b share-alike | REJECT stands (no option chosen; rejected until the legal scope is verified) |

**Phase 2 - dataset gate (the brief's numbering mapped onto this form's rows).**

| Brief item | Row | Recorded now |
| --- | --- | --- |
| D1 source and licence, D2 provenance | D1, D2 | KEEP UNRESOLVED (no source, licence or provenance named) |
| D3 fictional evidence status | D3 | KEEP UNRESOLVED (options listed, none chosen); fictional text stays `synthetic`, so `validated` stays unreachable and the pilot examples are not validation evidence |
| D4 privacy | D4 | KEEP UNRESOLVED (no method, verifier or prohibited categories given) |
| D5 rubric freeze | D5 | KEEP UNRESOLVED (options listed, none chosen); the rubric stays `v0-draft` |
| D6 two annotators, one adjudicator | D6 | **APPROVE** (the anonymous codes and the independence attestation are still required before annotation) |
| D7 blinding | D7 | **APPROVE** |
| D8 label set `positive_negative_neutral` | policy (not a row) | already the decided primary label set; confirmed |
| D9 at least 300 held-out, D10 at least 75 per class | D9 | **APPROVE** (the earlier quota and coverage proposals are not adopted) |
| D11 disjoint training / calibration / held-out | D10 | the principle is already enforced by the frozen schema; **sizes were not given**, so D10 stays KEEP UNRESOLVED |
| D12 exact-duplicate removal, near-duplicate method and threshold | D11 | exact (case-folded) removal confirmed; **method and threshold not given**, so D11 stays KEEP UNRESOLVED |
| D13 group names | D12 | KEEP UNRESOLVED (none given) |
| D14 Cohen's kappa primary, multi-label agreement deferred | D8 | both statements confirmed; the row also asks for pre-adjudication agreement as primary and adjudicated labels as the final reference, which the brief does not mention, so D8 stays KEEP UNRESOLVED |
| D15 probability-bearing predictions, at least 20 scored examples, descriptive-only below 20 | D13 | confirmed as the E2 / evaluation policy; the row asks about temperature scaling on the calibration split and 10-bin ECE, which the brief does not mention, so D13 stays KEEP UNRESOLVED |
| D16 coverage at least 0.70, D17 abstention at most 0.30 | D15 | **APPROVE** |
| D18 retention, D19 deletion, D20 access | D16, D17, D18 | KEEP UNRESOLVED (the brief says "define" and defines nothing) |
| (not in the brief) | D14, D19, D20 | KEEP UNRESOLVED; **no dataset may be downloaded, generated, collected or labelled until D1 to D19 are approved**, and D20 is the permission |

**Rubric / baseline alignment (E4).** None of the six differences (past-only text, topics in quotations or third-person clauses, the unavailable `hedged` flag, "even if" current clauses, comma-less `and`, current preference plus a hypothetical clause) received one of the three options, so E4 stays KEEP UNRESOLVED. Each stays a documented comparability limitation; no production code changed.

**Frozen manifest (E3).** E3 is KEEP UNRESOLVED (no APPROVE given). The requirements the brief lists (recomputed content, label, split, rubric, annotator and manifest hashes; disjoint splits; duplicate exclusion; no raw text in reports or errors; probability-bearing predictions for calibration; labels-only predictions `descriptive_only`) are recorded as requirements; the existing frozen-evaluation schema and its tests already enforce them (the hash fields, the disjoint-split and duplicate checks and the personal-data marker scan), so no code change was needed and no real manifest was created.

**R14 / F1** stays KEEP UNRESOLVED and unrequested; production activation is not authorised.

Effect on the phases: unchanged. Phase 4 stays locked (A3.2, A3.3 unresolved, A3.5b rejected); Phase 5 stays locked (D1 to D5, D8, D10 to D14, D16 to D20 and E3 unresolved).


### Owner reply of 2026-10-29 (third brief: consolidated legal, dataset, manifest and alignment decisions): what was recorded and what was not

The brief again lists the options for A3.2, A3.3, A3.5b, D1, D2, D3, D5, E3 and E4 **without choosing one**, gives examples rather than a choice for the group dimensions (D12), asks to "specify" retention, deletion and access without specifying, and gives direct "Approve" / "Confirm" statements for a few rows. Only those are recorded. An option list, an example and a request for a value are not answers. This section supersedes the previous section for D4 and D8 only.

**Legal gate (unchanged; FinBERT stays undownloadable):** A3.2 KEEP UNRESOLVED; A3.3 KEEP UNRESOLVED; A3.5b REJECT stands. No Hugging Face query, no download.

| Brief item | Row | Recorded now |
| --- | --- | --- |
| D1 source and licence (now also offers "fictional statements as synthetic research fixtures only") | D1 | KEEP UNRESOLVED (no option chosen) |
| D2 provenance | D2 | KEEP UNRESOLVED |
| D3 evidence status | D3 | KEEP UNRESOLVED (no option chosen); the code keeps fictional text `synthetic`, so no report on it may say `validated` |
| D4 privacy and de-identification | D4 | **APPROVE** (the verifier is still to be named in the participant register; consent wording not approved) |
| D5 rubric status | D5 | KEEP UNRESOLVED; the rubric stays `v0-draft` and is not frozen |
| D8 primary label set `positive_negative_neutral` | policy | confirmed (already decided) |
| D10 disjoint splits, no record or near-duplicate crossing splits, sizes recorded before data creation | D10 | the policy is confirmed (the frozen schema already enforces it); **no sizes were given**, so D10 stays KEEP UNRESOLVED |
| D11 exact removal, a documented near-duplicate method and threshold, boundary tests, text-free decisions | D11 | exact removal and the text-free rule confirmed; **method and threshold not given**, so D11 stays KEEP UNRESOLVED |
| D12 group dimensions (examples only) | D12 | KEEP UNRESOLVED (no choice; an unavailable group is reported unavailable, never fabricated) |
| D13 agreement | D8 | **APPROVE** |
| D14 calibration | D13 | probability-bearing predictions, 10 bins, ECE report-only, at least 20 scored examples, descriptive-only below 20 and labels-only never `validated` are confirmed; the row's one open clause is whether temperature scaling is fitted on the calibration split, which the brief does not mention, so D13 stays KEEP UNRESOLVED |
| D16 retention, D17 deletion, D18 access | D16, D17, D18 | KEEP UNRESOLVED ("specify" with no specification) |
| D19/D20 permission to create, collect, label, store annotations and freeze a manifest | D19, D20 | KEEP UNRESOLVED (neither approved nor rejected); **nothing is generated, collected, labelled, stored or frozen** |
| E3 frozen manifest | E3 | KEEP UNRESOLVED (no option chosen); no real manifest; the existing schema is exercised only by the local synthetic-fixture tests |
| E4, six differences | E4 | KEEP UNRESOLVED (no option chosen for any); all six stay documented comparability limitations; no production code changed |
| R14 | F1 | KEEP UNRESOLVED, unrequested |

Effect on the phases: unchanged. Phase 4 stays locked (A3.2, A3.3 unresolved, A3.5b rejected). Phase 5 stays locked (D1 to D3, D5, D10 to D14, D16 to D20 and E3 unresolved).


### Owner decisions of 2026-10-29 (fourth brief): what was recorded, and what is still needed before anything is created

This brief states its decisions as values, so they are recorded as the owner's decisions. Where it says a value is a conservative default "unless the owner explicitly changes" it, the value stands until it is changed, and a change replaces it without touching the dependent gates.

**Legal gate.**

| Field | Recorded now |
| --- | --- |
| A3.2 tokenizer licence | **APPROVE**: `ACCEPT ABSENCE OF A SEPARATE TOKENIZER LICENSE STATEMENT FOR NON-COMMERCIAL OFFLINE EVALUATION ONLY` (no redistribution, no commercial use; not legal clearance) |
| A3.3 training-data terms | KEEP UNRESOLVED (the Reuters / TRC2 and Financial PhraseBank terms were not independently read) |
| A3.5b share-alike | REJECT USE UNTIL LEGAL SCOPE IS VERIFIED (stands) |

FinBERT stays undownloaded: A3.3 is unresolved and A3.5b is rejected, so Phase 4 stays locked. The model-card licence is not treated as legal clearance.

**Dataset gate.**

| Row | Recorded now |
| --- | --- |
| D1 source and licence | KEEP UNRESOLVED |
| D2 provenance | KEEP UNRESOLVED |
| D3 evidence status of fictional text | **APPROVE the decision: fictional text REMAINS SYNTHETIC and CANNOT produce `validated`** |
| D4 privacy | APPROVE (already recorded) |
| D5 rubric | KEEP UNRESOLVED; the rubric is kept as `v0-draft` and NOT frozen (the choice is recorded in the row) |
| D6, D7, D8, D9, D15 | APPROVE (already recorded); label set `positive_negative_neutral` |
| D10 splits | **APPROVE**: 600 training, 100 calibration, 300 held-out; disjoint; no near-duplicate crossing |
| D11 duplicates | **APPROVE**: exact removal by normalized-text hash; character 5-gram Jaccard at or above 0.90, equality counts; id / hash only. Implemented and tested (below) |
| D12 group dimensions | **APPROVE**: `topic`, `difficulty`, `negation`, `contradiction`, `code_mixed` |
| D13 calibration | **APPROVE**: temperature fitted on the calibration split only; 10 equal-width ECE bins, report-only; descriptive-only below 20 |
| D14 training data | KEEP UNRESOLVED (not addressed; evaluation only) |
| D16 retention / storage | KEEP UNRESOLVED: the policy is recorded but **no storage location is named** ("the approved private project data location" is not designated anywhere) |
| D17 deletion | **APPROVE**: keep raw text until evaluation, audit verification and the R14 decision are complete, then delete raw text and temporary annotation files and keep hashes, aggregate metrics and decision records |
| D18 access | **APPROVE**: two annotators, one adjudicator, one evaluator; no production service; no model or rules output shown to annotators |
| D19 validation design, D20 permission | KEEP UNRESOLVED: **nothing may be generated, collected, labelled, stored or frozen** |

**E3 / E4.** E3 stays KEEP UNRESOLVED (no real manifest; the existing schema is exercised only by local synthetic fixtures). E4 is **APPROVE: KEEP DOCUMENTED DIFFERENCE** for all six differences; no production code changed. R14 / F1 stays KEEP UNRESOLVED and unrequested.

**Before any data is created (preconditions recorded, none yet met).** A participant / annotator register holding: anonymous annotator codes; independence attestations; the adjudicator's code; the de-identification verifier's code; consent wording if consented text is used; and the access and deletion authorisation (who may authorise deletion). The dry-run package tool currently checks only annotator code, role, independence and attestation date, so the verifier, consent and authorisation fields are **not yet checked by any tool**; adding that check is offline work still to do. A storage location (D16) must also be named. No production user text is ever used; no fictional statement is generated unless D20 explicitly authorises it.

**Code change made (offline, tooling only).** The frozen-evaluation check used a token-set Jaccard with a manifest-declared threshold, which is not the approved D11 method. It now normalizes text (NFKC, case-fold, collapse whitespace), detects exact duplicates by the hash of the normalized text, detects near duplicates by character 5-gram Jaccard at or above 0.90 (equality counts), and refuses a manifest that declares any other method or threshold. The boundary is tested at 36/40 = 0.9 exactly, just below (35/40) and just above (37/40), a Unicode / case / whitespace exact duplicate, short and empty texts, and that no message contains record text; four deliberate faults (`>=` to `>`, 4-grams, no Unicode normalization, no normalized hash) were each caught by the tests. Not changed: the temperature-scaling wiring (D13), the register tool, any production code, any model code path.

Effect on the phases: unchanged. Phase 4 stays locked (A3.3 unresolved, A3.5b rejected). Phase 5 stays locked (D1, D2, D5, D14, D16, D19, D20 and E3 unresolved).


### Offline implementation of the participant register and D13 calibration (2026-10-30)

**No decision changed.** Totals stay **44 APPROVE, 1 REJECT (A3.5), 0 BLOCKED, 11 KEEP UNRESOLVED**. A3.3 stays KEEP UNRESOLVED and A3.5b stays rejected, so FinBERT stays undownloaded; D1, D2, D5 (the rubric stays `v0-draft` and unfrozen), D14, D16 (no private storage location is approved), D19, D20, E3 and R14 stay unresolved; D3 stays "fictional text is synthetic and can never produce `validated`"; E4 keeps all six differences documented. **No real data was created, no consented data was collected, no real register or manifest exists, no rubric freeze occurred, and nothing was downloaded, installed or contacted.** This section records code and tests only.

**Participant register (the D4 / D6 / D17 / D18 preconditions).** `training/sentiment/participant_register.py` (standard library only, no clock, no file access) validates a parsed register against an explicit `as_of` date. It requires: an anonymous code per person; a role of `annotator` (exactly 2), `adjudicator` (exactly 1), `evaluator` (exactly 1) or `de_identification_verifier` (at least 1); an independence attestation and an attestation date for everyone; an access authorization with a permitted dataset scope, a start and an expiry date and a `may_view` list checked against the role; a de-identification verifier code naming a verifier who has a valid authorization; a deletion authorization (given by a participant, dated, covering raw text and temporary annotation files); a `synthetic` or `consented` data status, with consent-wording metadata (a version and a SHA-256) required for consented data and refused for synthetic data. It refuses: duplicate codes, invalid roles, a missing attestation, production services (and any service that is not the evaluator), an annotator who may see model output, rules output, a risk profile or a recommendation (nobody may see a risk profile or a recommendation), an expired or not-yet-started authorization, a missing deletion authorization, production-user identifiers as codes, personal-data markers and credential-like strings. **Every error is a fixed description with counts and participant positions; it never echoes a value or a field name.** The register is still the owner's own attestation: the validator checks completeness and consistency and **cannot** verify independence or that a code is not a real name. The pilot-pack builder's four-column register check (`scripts/build_dry_run_package.py`) is unchanged and separate. Tested on invented registers only (`test_participant_register.py`, 96 tests).

**D13 temperature calibration.** `metrics.py` now fits one temperature on the CALIBRATION split's probability-bearing records only (`fit_calibration_temperature`: minimum negative log-likelihood over `log p / T`, deterministic search in [0.05, 20]), applies it to held-out probabilities only (`apply_temperature`) and reports the held-out calibration before and after (`temperature_calibration_report`: 10 equal-width ECE bins, strict and accepted-only, ECE report-only). Only probabilities are available from a candidate, so **no logit is invented**: softmax of `log p` equals `p`, hence dividing `log p` by `T` is exactly temperature scaling of the logits whenever the probabilities are a softmax output and a one-parameter power calibration otherwise; a zero probability stays zero. Required and tested: exactly `positive`, `negative`, `neutral`; finite values in [0, 1]; a sum of 1 within 1e-3; a non-null predicted label that is a most-probable class. Below 20 scored calibration examples nothing is fitted (`descriptive_only`, temperature `None` with a reason); with no probabilities the status is `unavailable`; a labels-only candidate (the rules baseline) is `labels_only`, is never calibrated and keeps its labels. The calibration and held-out ids must be disjoint. Calibration validates nothing and recommends nothing (`validated: false`, no activation recommendation); synthetic evidence still yields `not_validation_evidence`. When the frozen path supplies the fit, `assess_against_policy` adds a `temperature_calibration` gate: a usable fit is `reported`, a descriptive-only or unavailable fit leaves the candidate `descriptive_only`. Tested in `test_temperature_calibration.py` (40 tests).

**Frozen-manifest metadata (schema 2, local synthetic fixtures only; E3 stays unresolved).** `frozen_evaluation.py` now requires `data_status` (agreeing with the `synthetic` flag), `participant_register` {register file hash, verifier hash, consent-wording hash or null}, `calibration` {calibration-split hash, `d13-temperature-v1`, fit split `calibration`, method, 10 bins, minimum 20}, duplicates `exact_method` and `ngram_size`, and group dimensions drawn from the approved five (D12). Loading takes the register file as a sixth input, verifies its hash, validates it (on the freezing day, or an explicit `as_of`; the command line uses today), and checks that its data status, dataset scope, annotator and adjudicator codes, verifier hash and consent hash agree with the manifest; the calibration-split hash is recomputed from the records. `evaluate_frozen` takes the calibration split's probabilities (`calibration_probabilities`, which must cover exactly the calibration ids) and the command line (`--participant-register`, six frozen-mode arguments) lets a probability-bearing predictions file or local model also answer the calibration split. Manifest SHA-256 verification, split disjointness, duplicate exclusion and the no-raw-text rule are unchanged and re-tested (`test_frozen_register_and_calibration.py`, 58 tests, plus the updated frozen tests). Mutation checks: 28 of 30 mutants of the register, calibration and frozen-metadata logic were caught; the two survivors are equivalent (the `isfinite` test is redundant with the `0 <= p <= 1` test, and the "calibration changed a label" guard cannot fire because only probabilities are rebuilt).

**Still not done, and why.** No real register, dataset or manifest can be created while D1, D2, D16, D19, D20 and E3 are unresolved; the register's storage location is the D16 gap; the D4 verifier and the D17 deletion authorizer are entered in a future real register, not here.


### Owner decisions of 2026-10-30 (fifth brief) and the end-to-end brief: recorded values, blocked operations, and the one consolidated approval table

**Owner approvals recorded (values the owner gave).** A3.3 = KEEP UNRESOLVED; A3.5b = REJECT USE UNTIL LEGAL SCOPE IS VERIFIED; D1, D2, D5 = KEEP UNRESOLVED (the rubric stays `v0-draft`, not frozen or distributed); D16 = KEEP UNRESOLVED (no path supplied); D20 = KEEP UNRESOLVED; R14 = KEEP UNRESOLVED. The brief's "D14 = APPROVE" (adjudication and agreement) is this form's D8 and its "D19 = APPROVE" (retention and deletion) is this form's D17, both already approved and now specified (see their rows); this form's own D14 (training data) and D19 (validation design) are different rows, were not decided, and stay unresolved. E3 = APPROVE SCHEMA-2 OFFLINE IMPLEMENTATION ONLY: recorded in the E3 row without changing its status, because the row asks for a real manifest. **Totals do not change: 44 APPROVE, 1 REJECT (A3.5), 0 BLOCKED, 11 KEEP UNRESOLVED.**

**Verified facts (synthetic-only results).** The register validator now also enforces the deletion policy (project-owner authorization, retention only until evaluation, audit verification and the R14 decision, only hashes, aggregate metrics and decision records retained, rollback never restores raw text, completion verified and recorded; 5 of 5 mutants caught). D13 calibration (calibration split only, 10 equal-width bins, at least 20 examples, labels-only candidates `descriptive_only`, no activation recommendation) and schema 2 were re-run. New guards (`test_no_fixture_is_real_evidence.py`) show every fixture is visibly invented, no FROZEN manifest or participant register exists outside the tests, and neither an agreement result alone nor a calibration alone produces `validated`. All of this is synthetic: it validates plumbing, not a model or a dataset.

**Blocked operations (fail-closed).** No download or use of FinBERT (A3.3 unresolved, A3.5b rejected); no creation, collection, download, consent, labelling, storage or manifest of any real text (D1, D2, D5, D16, D20 unresolved); no real manifest (E3 limited); no activation (R14). No network, package, model or user text was touched.

**The one consolidated approval table (the end-to-end brief's gate).** One reply, one value per row; the value on record is shown so that only a change or a new value is needed. An omitted row keeps the value on record (unresolved rows stay unresolved and block their dependent phase).

| Row | Choices (write exactly one, or a value where one is asked) | On record now |
| --- | --- | --- |
| A3.2 tokenizer licence | `ACCEPT ABSENCE OF A SEPARATE TOKENIZER LICENSE STATEMENT FOR NON-COMMERCIAL OFFLINE EVALUATION ONLY` / `REJECT` / `KEEP UNRESOLVED` | ACCEPTED (2026-10-29) |
| A3.3 training-data terms | `ACCEPT FOR NON-COMMERCIAL OFFLINE EVALUATION WITH EXPLICIT ACCEPTANCE THAT PHRASEBANK AND REUTERS / TRC2 TERMS WERE NOT INDEPENDENTLY VERIFIED` / `REJECT` / `KEEP UNRESOLVED` | KEEP UNRESOLVED |
| A3.5b share-alike | `ACCEPT ONLY FOR THE DOWNLOADED ARTIFACT AND DIRECT ADAPTATIONS; NO CLAIM ABOUT FEATURES OR OUTPUTS` / `REJECT UNTIL LEGALLY VERIFIED` / `KEEP UNRESOLVED` | REJECT UNTIL LEGAL SCOPE IS VERIFIED |
| D1 dataset source and licence | the exact source and licence | KEEP UNRESOLVED |
| D2 provenance type | `consented` / `licensed public` / `fictional synthetic` / `approved mixture (state per-item provenance)` | KEEP UNRESOLVED |
| D3 can fictional data ever support `validated` | `NEVER (it stays synthetic)` / `YES, as evaluation evidence` / `KEEP UNRESOLVED` | NEVER (synthetic; recorded 2026-10-29) |
| D5 rubric | `FREEZE AT SHA-256 <exact hash and new version label>` / `KEEP v0-draft` | v0-draft, unfrozen |
| D10 split sizes | exact training / calibration / held-out sizes | 600 / 100 / 300 (recorded 2026-10-29) |
| D11 duplicates | method and threshold | NFKC-normalized hash; character 5-gram Jaccard at or above 0.90, equality counts (recorded and implemented) |
| D12 group dimensions | the names | `topic`, `difficulty`, `negation`, `contradiction`, `code_mixed` (recorded) |
| D14 adjudication and agreement | confirm or change | APPROVED, specified 2026-10-30 (this form's D8) |
| D16 private storage path and permitted operators | the concrete path (outside the repository, access-controlled, unavailable to production services, with operator access, retention controls and deletion verification) and the operator names or codes | KEEP UNRESOLVED |
| D19 retention and deletion authorization | confirm or change | APPROVED, specified 2026-10-30 (this form's D17) |
| D20 permission to generate, collect, label and store | `APPROVE (state which of: generate fictional statements / collect consented statements / label / store annotations / create the frozen manifest)` / `REJECT` / `KEEP UNRESOLVED` | KEEP UNRESOLVED |
| E3 real frozen manifest | `APPROVE A REAL FROZEN MANIFEST AFTER D1, D2, D5, D16, D20` / `SCHEMA-2 OFFLINE ONLY` / `KEEP UNRESOLVED` | SCHEMA-2 OFFLINE ONLY |
| E4 six rubric / baseline differences | per difference: `ALIGN BASELINE TO RUBRIC` / `ALIGN RUBRIC TO BASELINE` / `KEEP DOCUMENTED DIFFERENCE` | KEEP DOCUMENTED DIFFERENCE for all six (2026-10-29) |
| R14 activation | asked only after a real evaluation is complete | KEEP UNRESOLVED, not requested |

This form's own D14 (training data, only if a model is fine-tuned; A3.13 is evaluation only) and D19 (validation design: held-out set, gates and frozen manifest) are not in the end-to-end brief's table; please say whether you want them decided too.

Effect on the phases: unchanged. Phase 4 stays locked (A3.3 unresolved, A3.5b rejected); Phase 5 stays locked (D1, D2, D5, D14, D16, D19, D20 and E3 unresolved); Phases 6 and 7 follow.


### Phase closure (2026-10-30): the offline rules-based sentiment phase

> The offline rules-based sentiment phase is complete. Transformer evaluation, real dataset creation and production activation are deferred because the required legal, dataset, storage and activation approvals are unresolved.

**Final owner decisions for this phase (recorded exactly).**

| Item | Value |
| --- | --- |
| A3.3 training-data terms | KEEP UNRESOLVED |
| A3.5b | REJECT USE UNTIL LEGAL SCOPE IS VERIFIED |
| D1, D2 | KEEP UNRESOLVED |
| D5 rubric | KEEP v0-DRAFT; DO NOT FREEZE (the row stays KEEP UNRESOLVED) |
| D16 storage | KEEP UNRESOLVED |
| D20 permission | **REJECT REAL DATA CREATION, COLLECTION, LABELING, STORAGE AND MANIFEST CREATION FOR THIS PHASE** (row status REJECT) |
| E3 frozen manifest | APPROVE SCHEMA-2 OFFLINE IMPLEMENTATION ONLY (the row, which asks for a real manifest, stays KEEP UNRESOLVED) |
| E4 alignment | KEEP DOCUMENTED DIFFERENCE FOR ALL SIX RECORDED DIFFERENCES (row status APPROVE) |
| R14 activation | KEEP UNRESOLVED |

**Preserved.** `user_text_rules_v1` stays active and `SENTIMENT_MODEL_ENABLED=false`; A3.1, A3.2 (non-commercial offline evaluation only), A3.4, A3.5a, A3.7 and A3.8 as recorded; D3 (fictional text is synthetic and can never produce `validated`); D4, D6, D7, D8, D9, D10, D11, D12, D13, D15, D17 and D18 as recorded. **Totals: 44 APPROVE, 2 REJECT (A3.5, D20), 0 BLOCKED, 10 KEEP UNRESOLVED.** A rejected item never unlocks a later phase: Phases 4 to 7 stay locked.

**Closure rules.** No FinBERT download, no Hugging Face access, no real model inference, no training or fine-tuning, no claim of model validation (A3.3 unresolved, A3.5b rejected). No real text is created, collected, generated, labelled or stored, no real participant register or frozen manifest is created, no claim of dataset validation or `validated` (D1, D2, D5, D16 unresolved; D20 rejected). **The approval requests for A3.3, A3.5b, D1, D2, D5, D16, D20, E3, E4 and R14 are closed for this phase and are not repeated;** if the owner later wants real Hugging Face use or real-data evaluation, that is a new phase with a new explicit approval request. The earlier consolidated approval tables in this form are historical.

**Offline scope completed and verified (synthetic-only results).** The rules baseline; privacy, abstention and evidence masking; hypothetical, conditional, quotation, third-person, past-feeling and polite-form handling; the participant-register validator (invented fixtures); D13 calibration (synthetic fixtures); schema-2 frozen evaluation (synthetic fixtures); Path B local-model loading (random local stand-ins only, skipped where torch is missing); artifact, tokenizer, safetensors, provenance and fallback checks; the ledger boundary; documentation and approval guards; pilot-pack verification. Synthetic fixtures produce only `not_validation_evidence` or `descriptive_only`, never `validated`.

**Final production state.** Production method `user_text_rules_v1`; `SENTIMENT_MODEL_ENABLED=false`; real model downloaded: no; real dataset created: no; real evaluation run: no; production activation: no; intensity regression: disabled (`sentiment_intensity` is `null`); blockchain / ledger sentiment payload: none.

## C. Network and environment (D10 to D13)

| ID | Decision | Facts and options (from `reports/sentiment_model_approval_record.md`) | Entry |
| --- | --- | --- | --- |
| C1 | **D10** Hub conversion | One of: **path A** a documented upstream switch (none exists; the only one, `DISABLE_SAFETENSORS_CONVERSION`, is undocumented and stays unused); **path B** a local conversion-free workflow: download exactly the named files at the pinned revision, verify SHA-256, then point the trainer at the local directory so the library's Hub branch is never reached (needs a **trainer API decision**, E1: today the trainer takes a Hub identifier and has no local-directory parameter); **path C** you accept the residual risk in writing, scoped to one named revision and one run, with the observed-behaviour test re-run first. Today a pinned revision plus `use_safetensors=True` is an observed 5.12.1 property pinned by a test, not a guarantee | APPROVE (2026-10-29, owner statement). Value: **Path B, the local conversion-free workflow**: fetch exactly the approved files (E1), create a local artifact directory, verify every hash, load only from that directory with `local_files_only=True`, never a pickle-capable file, never a conversion thread or remote conversion path, no undocumented Hub switch. **Not implemented:** the trainer has no local-directory parameter (`train_sentiment_transformer.py` takes a Hub identifier); that change is documented under "Phase 3 attempt" and is NOT applied, because it needs its own approval; no download may start before it exists and is tested **Prepared offline (2026-10-29), unwired:** `training/sentiment/local_model_dir.py` (verified-manifest precondition, the fixed five-file allow-list, per-file SHA-256, safetensors-only, `local_files_only=True`, `trust_remote_code=False`, CPU, probability-bearing predictions in the E2 format) with 56 synthetic-fixture tests; nothing imports it. Not implemented: the wiring into `train_sentiment_transformer.py` and the evaluation script, which stays unapplied until the owner approves the offline code change. **Update (2026-10-29): the wiring is approved and applied offline** in the trainer and the evaluation script (see "Phase 3 execution"); it adds no Hub path, no download and no route. |
| C2 | **D11** network boundary | the eight items: repository (A2/A1), revision (A3.7), files (A3.8), destination (A3.10), `--allow-hub-download` for that run (YES once / NO), account and network boundary (which machine and account, anonymous or token, proxy, nothing persisted), hash verification (A3.11), cleanup (A3.12). **`--allow-hub-download` is not a file allow-list** (it only switches the library online), so A3.8 cannot be enforced by it alone | APPROVE (2026-10-29, owner statement). Value: anonymous HTTPS to `https://huggingface.co` only; no credentials; no other host and no redirect to another host. This approves the boundary only: every download run still needs its own explicit start (Phase 4) |
| C3 | **D12** install the S1 set in a named disposable training environment | facts: 35 hash-pinned wheels (170.3 MB; about 903 MB installed): `torch 2.13.0`, `transformers 5.12.1`, `tokenizers 0.22.1`, `safetensors 0.6.2`, `setuptools 81.0.0`, `numpy 1.26.4`, Python 3.11.9; verified compatible in the isolated check (19 of 19 stand-in checks; 381 tests passed); the machine has 8 CPUs, 15.7 GB RAM. You would name: the environment path and owner (candidate `C:\Users\Administrator\.copilot\sentiment-training-venv`), the retention rule (candidate: delete after the phase), whether the `setuptools` 81.0.0 residual-risk acceptance (GHSA-h35f-9h28-mq5c, GHSA-xmj3-9gf7-h52w) is **extended** to it (not extended by default), and that the project environment is not used; I would re-check OSV on the day | APPROVE (2026-10-29, owner statement). Value: a disposable Python 3.11 CPU environment at `C:\Users\Administrator\.copilot\wealthpilot-finbert-eval-venv` (outside the repository), holding only the hash-pinned S1 set, deleted after the phase. **Creation is conditional**: C4 must be satisfied first, and the wheels must come from an approved retrieval; neither holds (see "Phase 3 attempt") **Update (2026-10-29):** the S1 set (the 35-wheel list of section L.3, `setuptools==81.0.0`) is approved; the environment was created at this path, validated and deleted the same day. |
| C4 | **D13** TASK-CERT-1 | the project environment has `certifi 2026.7.22` and `pip 26.2.1` (vendoring `certifi 2026.6.17`), both affected by GHSA-6q48-6c7w-9gw2. Options: **complete the task** (upgrade, regression suite, rollback plan); **accept the risk in writing** for a stated scope; or **narrow the gate**: a download runs in the dedicated environment whose S1 list pins `certifi 2026.10.23` (outside the affected range) and the Hub client uses that environment's `certifi` — an expectation, **not a verified fact** until that environment exists, so you would be accepting that expectation | APPROVE (2026-10-29: the owner decided to COMPLETE TASK-CERT-1 before any model download; the task was COMPLETED AND VERIFIED on 2026-10-29, see "TASK-CERT-1 execution"). Superseded earlier text: completing it means upgrading `certifi` and `pip` in the project environment, which this phase may not do: no package change, no PyPI contact, no change to the project environment **Earlier update (2026-10-29, superseded by the completed remediation):** the owner approved the remediation of `certifi` and `pip`; it STOPPED before any change because the approved lock has no `pip` wheel (a version outside the approved set is needed); the item then stayed BLOCKED. **Owner policy decision (2026-10-29), recorded before the metadata query:** `certifi==2026.10.23` may be upgraded ONLY together with the approved `pip` remediation, never independently (the project `pip` may retain a vulnerable vendored `certifi` copy); the project's `setuptools==65.5.0`, TensorFlow 2.17.0, Keras 3.15.1 and NumPy 1.26.4 must remain unchanged; the approved S1 disposable environment stays separate from the project environment; TASK-CERT-1 remains BLOCKED until the exact `pip` version and wheel hash are explicitly approved. This phase is a read-only PyPI metadata query: no package is installed or upgraded, the project environment is not modified, no model, dataset or user text is accessed, Hugging Face is not contacted, and production configuration does not change. **Completed (2026-10-29):** `pip` 26.2.1 to 26.2.2 (SHA-256 `fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70`) and `certifi` 2026.7.22 to 2026.10.23 (SHA-256 `e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1`), nothing else changed, verified; rollback backup kept (see "TASK-CERT-1 execution"). |
| C5 | Hugging Face cache location | the library writes to its own cache (`~/.cache/huggingface` by default; the machine has none today). Candidate: the destination in A3.10 is the only place anything is written, and the default cache must stay absent or empty after the run (checked). Setting it needs a code parameter, not an undocumented environment switch (E1) | APPROVE (2026-10-29, owner statement). Value: a temporary Hugging Face cache at `C:\Users\Administrator\.copilot\wealthpilot-hf-cache`, deleted after the phase or on failure. It does not exist today; nothing is written to it unless a later approved download runs **Retention (owner statement, 2026-10-29, second listing):** use only during the approved disposable operation; delete after the successful verified artifact creation; delete immediately on failure, mismatch or cancellation; never reuse a partial cache. |

## D. Dataset and annotation (R8 to R13)

Recorded constraints: real user-text collection is **prohibited** (O1 accepted for fictional notes only); O4 accepted for a fictional dry run with two annotators and one adjudicator independent of the rubric author; O2, O3, O7 and the withdrawal-versus-unlinkability conflict (C3 of the decision sheet) are unresolved; the rubric is `v0-draft`, not frozen; annotation has not started and no participant is named; synthetic project examples are never validation evidence. Already decided: label set `positive_negative_neutral`, 300 held-out, 75 per primary class, strict-view macro-F1 0.80, accepted-prediction precision 0.85, coverage 0.70 / abstention 0.30, Cohen's kappa with no floor, no lower-bound activation rule.

| ID | Decision | Candidate or fact | Entry |
| --- | --- | --- | --- |
| D1 | Dataset source and licence | none exists. Options: independently authored fictional personal-finance statements; or text from consenting participants (needs D2 to D4 and O1 widened); a public corpus is a different licence question per corpus | KEEP UNRESOLVED |
| D2 | Provenance statement and who authors the statements | authors independent of the rubric author and of the baseline's cue lists; nothing copied from a benchmark; no names, amounts, employers or account details | KEEP UNRESOLVED |
| D3 | Fictional versus consented text | O1 allows fictional only. If fictional: **does independently authored fictional text count as valid evidence for the `EvidenceBasis` (synthetic = false), or is it synthetic (synthetic = true, so never `validated`)?** This decides whether `validated` is reachable at all | APPROVE (2026-10-29, owner decision, fourth brief): fictional text REMAINS SYNTHETIC (`synthetic = true`) and CANNOT produce `validated`; it can test plumbing only. Consequence: no evaluation report on fictional text may say `validated`; `validated` would need a different, separately approved evidence source (consented text, D1 and D2 open). |
| D4 | De-identification method and who verifies it; consent wording and notice (consented text only) | O2 unresolved | APPROVE (2026-10-29, owner reply, third brief): remove or mask names, e-mail addresses, phone numbers, addresses, account numbers, links, dates of birth, employer identifiers and other direct or quasi-identifiers; scan for prohibited personal-data markers; no raw text in any report, log or error; no user-submitted production text is ever used for annotation. The person who verifies de-identification is not named in the reply and must be entered in the participant register before any text is created; consent wording applies to consented text only and none was approved. Creation stays locked by D1 to D3, D19 and D20 |
| D5 | Rubric freeze | freeze needs the dry run completed, ambiguities resolved, O2 / O3 / O7 decided; a new version label (not `v0-draft`) and your approval of the hash. The documented rubric / baseline differences (a) to (f) are on record; (f) is unconfirmed | KEEP UNRESOLVED **Owner decision (2026-10-29, owner decision, fourth brief):** KEEP THE RUBRIC AS `v0-draft`; DO NOT FREEZE IT. The status stays KEEP UNRESOLVED because the freeze (which a real evaluation needs) is not approved; a draft rubric can never support `validated`. **Final for this phase (2026-10-30):** KEEP v0-DRAFT; DO NOT FREEZE. The row stays unresolved; the rubric is neither frozen nor distributed. |
| D6 | Annotators | two independent annotators and one adjudicator, as anonymous codes with independence attested in the participant register (the register is your attestation; the code cannot verify it) | APPROVE (2026-10-29, owner reply): two independent annotators and one adjudicator for disagreements. The anonymous codes and the independence attestation in the participant register are still required before any annotation; annotation stays locked by D20 |
| D7 | Annotation blinding | annotators see only the text and its id: no model or rules output, risk profile, recommendations or other annotators' labels | APPROVE (2026-10-29, owner reply): annotators must not see model output, rules output, risk profile or recommendations; the row's own clause (no other annotator's labels) is the independence rule of D6 |
| D8 | Agreement and adjudication policy | confirm: Cohen's kappa primary, no floor, pre-adjudication agreement primary, adjudicated labels the final reference | APPROVE (2026-10-29, owner reply, third brief): Cohen's kappa is the primary single-label statistic (no floor); specific agreement and Krippendorff alpha are secondary reports; two independent labels exist before adjudication; the adjudicated labels are the final reference; multi-label agreement stays deferred **Confirmed 2026-10-30 (the owner's brief "D14 = APPROVE" is this row by meaning):** two independent labels are collected before adjudication; Cohen's kappa is primary for the single-label task; specific agreement and Krippendorff alpha are secondary; adjudicated labels are the final reference; multi-label agreement stays deferred; **no agreement result alone can produce `validated`** (tested). This form's own D14 (training data) is a different row and stays unresolved. |
| D9 | Held-out set composition | 300 total, 75 minimum per primary class (decided). The earlier owner proposals — quotas 80 / 80 / 80 plus 30 mixed and 30 uncertain, topic and phenomenon coverage lists, at least 30% hard — are still proposals: confirm, change or drop, and add a hypothetical / conditional coverage line | APPROVE (2026-10-29, owner reply): at least 300 held-out statements and at least 75 per primary class. The earlier proposals (quotas, coverage lists, the 30% hard share, a hypothetical / conditional line) were not mentioned, are NOT adopted, stay non-binding proposals and are not part of this approval |
| D10 | Split sizes | training, calibration and held-out, disjoint; training is needed only if a model is fine-tuned (A3.13). Sizes: none proposed | APPROVE (2026-10-29, owner decision, fourth brief): disjoint training, calibration and held-out splits of **600, 100 and 300 statements** (1,000 in all); no record and no near-duplicate may cross splits. The held-out 300 is the D9 minimum. The sizes bind the dataset when it is created (D20); the schema checks disjointness and its own declared counts, not these sizes. Training data is used only if a model is fine-tuned (A3.13 is evaluation only). |
| D11 | Duplicate and near-duplicate policy | exact: case-folded text; near: token-set Jaccard at or above a threshold the manifest declares (earlier proposal 0.8); the method and the threshold are yours to approve | APPROVE (2026-10-29, owner decision, fourth brief): exact-duplicate removal by the hash of the NFKC, case-folded, whitespace-collapsed text; near duplicates by character 5-gram Jaccard similarity of that text at or above **0.90** (equality counts); decisions recorded by id or hash only, never by text. Implemented and boundary-tested in `training/sentiment/frozen_evaluation.py` (a manifest must declare exactly `nfkc_casefold_char5gram_jaccard` and 0.9). |
| D12 | Group-dimension names for subgroup reports | topic, difficulty and the phenomena of the rubric are the natural set; names are declared in the manifest | APPROVE (2026-10-29, owner decision, fourth brief): group dimensions `topic`, `difficulty`, `negation`, `contradiction` and `code_mixed`. |
| D13 | Calibration policy | confirm: temperature scaling fitted on the calibration split only, equal-width ECE with 10 bins, report-only | APPROVE (2026-10-29, owner decision, fourth brief): temperature scaling fitted ONLY on the calibration split; 10 equal-width ECE bins, ECE report-only; descriptive-only below 20 scored examples; probability-bearing predictions required; labels-only never `validated`. **Wired offline on 2026-10-30** for the frozen-evaluation path: the temperature is fitted on the calibration split's probabilities only and applied to the held-out probabilities only (see "Offline implementation of the participant register and D13 calibration (2026-10-30)"). Earlier text, now superseded: not yet wired. |
| D14 | Training data (only if A3.13 = training) | a separate labelled training set disjoint from the held-out set; its source and licence; Financial PhraseBank is a development benchmark at most and carries share-alike terms | KEEP UNRESOLVED |
| D15 | Coverage and abstention policy | confirm the decided gates (coverage at least 0.70, abstention at most 0.30) | APPROVE (2026-10-29, owner reply): minimum coverage 0.70 and maximum abstention 0.30 |
| D16 | Data retention | period, location, who may read it | KEEP UNRESOLVED **Owner decision (2026-10-29, owner decision, fourth brief):** storage only under the approved private project data location, readers limited to annotators, adjudicator and evaluator, no production service access. Stays KEEP UNRESOLVED because no location is named or approved anywhere (the form, the ADRs and the docs designate none); the period is event-based and recorded under D17. No path was supplied on 2026-10-30, so nothing is invented: still KEEP UNRESOLVED. An approved path must be outside the public repository, access-controlled, unavailable to production services, documented with operator access and retention controls, and suitable for deletion verification. |
| D17 | Deletion | method, and on a participant's request (this is the withdrawal-versus-unlinkability conflict: a text stored with no link to a person cannot be withdrawn) | APPROVE (2026-10-29, owner decision, fourth brief): retain raw text and annotation files until the evaluation, the audit verification and the R14 decision are complete; then delete raw text and temporary annotation files and keep only approved hashes, aggregate metrics and decision records. The identity authorised to delete, and how completion is verified, are entered in the participant register before any text is created; the withdrawal-versus-unlinkability question applies to consented text only, and none is approved (D2 open). **Specified 2026-10-30 (the owner's brief "D19 = APPROVE" is this row by meaning):** raw text and temporary annotation files exist only until the evaluation, the audit verification and the R14 decision are complete; then they are deleted and only approved hashes, aggregate metrics and decision records are retained; deletion is authorized by the project owner; completion is verified and recorded; a rollback may restore metadata and aggregate records, never deleted raw text. Enforced in the register validator's `deletion_authorization`. This form's own D19 (validation design) is a different row and stays unresolved. |
| D18 | Access | who may read raw text; where it is stored | APPROVE (2026-10-29, owner decision, fourth brief): access for two independent annotators, one adjudicator and one evaluator only; no production service access; no model output, rules output, risk profile or recommendation is shown to annotators. The storage location is the open part of D16. |
| D19 | Validation design (O7) | confirm that the held-out set, the gates and the frozen manifest are the design | KEEP UNRESOLVED |
| D20 | Permission to generate, collect or label | **no dataset may be downloaded, generated, collected or labelled until you approve D1 to D19** | REJECT (2026-10-30, owner decision, phase closure): REJECT REAL DATA CREATION, COLLECTION, LABELING, STORAGE AND MANIFEST CREATION FOR THIS PHASE. No real statement is generated, collected, consented, labelled or stored, no real participant register or manifest is created; reopening this needs a new phase with a new explicit approval request. |

## E. Code and format approvals needed for the later phases

| ID | Decision | Why it is needed | Entry |
| --- | --- | --- | --- |
| E1 | Build a verified fetch step (and the metadata-query tool of B9) | **Today the download happens implicitly inside training** (`from_pretrained(..., local_files_only=False)`): no file allow-list, no recorded per-file SHA-256, no host or redirect enforcement in code, no destination parameter. Phase 4 as you specified it (only approved files, reject unexpected ones, verify hashes, approved destination) is therefore **not met by the current code**. Options: (i) a purpose-written standard-library HTTPS fetcher that downloads exactly the named files, refuses any redirect to an unapproved host and hashes each file; (ii) the Hub library's file-level download with a post-download check that nothing outside the list was written; (iii) neither: accept the library's file selection as residual risk (C1 path C). Whether the Hub library can enforce a host or redirect policy in code is **not established** (it is not installed in the project environment and the disposable one was deleted); (i) avoids the question. Also needs the trainer API decision of C1 path B (a local base-model directory parameter) | APPROVE (2026-10-29). Value: build a **verified download / fetch step** with (1) a file allow-list, (2) per-file SHA-256 verification, (3) host and redirect checks, (4) an explicit destination and (5) rollback. Covers the fetch step only. NOT covered by E1: the metadata-query tool (B9) (a separate approval, restricted by B3 to B10), and still unresolved: the trainer local-directory parameter (C1 path B, not implemented), the choice of mechanism (i) or (ii) (the built tool is mechanism (i)), and any network use. **Built offline (`training/sentiment/hub_fetch.py::fetch_files`): allow-list, per-file SHA-256, host and redirect checks, an explicit destination outside the repository, rollback; pickle-capable formats refused; never executed against a real host.** Running it needs the model, metadata, D10 to D13 and C5 approvals |
| E2 | Predictions format with probabilities | a labels-only predictions file leaves calibration not evaluable, so that candidate can never be `validated`; the script needs a format carrying per-class probabilities for approved candidates | APPROVE (2026-10-29). Value: **calibration requires probability-bearing predictions** (per-class probabilities for every candidate whose calibration is to be evaluated); **labels-only predictions remain descriptive-only and can never produce `validated`**. **Built offline:** a predictions file may map each held-out id to a label or null (labels-only) or to `{"label", "probabilities"}` (all records or none; the three primary labels, finite numbers in [0, 1] summing to 1, a non-null label equal to the most probable class); the rules baseline carries no probabilities |
| E3 | Create a real frozen manifest | only after D1 to D19; the manifest schema is confirmed; its near-duplicate method and threshold (D11) and group dimensions (D12) are declared in it | KEEP UNRESOLVED **Owner decision 2026-10-30:** APPROVE SCHEMA-2 OFFLINE IMPLEMENTATION ONLY (synthetic fixtures; the register, verifier, consent, split, label, content, rubric, duplicate-policy and manifest hashes stay mandatory; synthetic data stays `not_validation_evidence`; no real manifest). This row asks for a REAL frozen manifest, which is not approved, so it stays KEEP UNRESOLVED; real-manifest creation also needs D1, D2, D5, D16, D20 and every other dataset approval. |
| E4 | Rubric / baseline alignment | confirm difference (f) and decide, case by case, whether any of (a) to (f) should be aligned (each needs its own production-change approval); until then they remain comparability limitations | APPROVE (2026-10-29, owner decision, fourth brief): KEEP DOCUMENTED DIFFERENCE for all six (past-only text; topics in quotations or third-person clauses; the unavailable `hedged` flag; "even if" constructions; comma-less `and`; a current preference combined with a hypothetical clause). No alignment is authorised and no production code changes; difference (f) is still described as unconfirmed in the rubric record, and this choice does not verify it. **Final for this phase (2026-10-30):** KEEP DOCUMENTED DIFFERENCE FOR ALL SIX RECORDED DIFFERENCES; no production code changes. |
| E5 | Use the built metadata-query tool | `training/sentiment/hub_fetch.py::query_metadata`, standard library, built offline and tested with a scripted transport and a loopback server | APPROVE (2026-10-29). Value: use of the read-only metadata-query tool with a maximum of **10 anonymous requests**, no credentials, cookies or tokens, approved metadata endpoints only, no file-download requests, and an immediate stop on a host, revision, licence, request-count or authentication mismatch. Authorises the Phase 2 query of `ProsusAI/finbert` only |

## F. Activation (R14) — not requested now

| ID | Decision | Entry |
| --- | --- | --- |
| F1 | R14 activation of an approved, evaluated model — **no decision is requested now**: it is asked only after phase 6, and no report recommends it (no lower-bound rule exists); until then `SENTIMENT_MODEL_ENABLED=false` and `user_text_rules_v1` stay | KEEP UNRESOLVED (2026-10-29, explicit). R14 is not decided and not requested; production activation is not authorised |

Status of the R14 prerequisites today (verified against the repository on 2026-10-29): licences accepted — no; exact revision approved — no; hashes verified — nothing downloaded; dependency security — A2 isolated check only (C3, C4 open); dataset and annotation approvals — none; frozen manifest — plumbing built, tested on generated fixtures, no real manifest; evaluation gates — not evaluated (no data); privacy, fallback and isolation tests — pass against fake and stand-in backends (1266 passed, 3 skipped), not yet with a real model; artifact provenance — complete for stand-in artifacts only; threat model — section 17 exists, a pre-approval analysis of the download and evaluation path was added (`docs/THREAT_MODEL.md` section 18) and must be reviewed before R14; no raw text in logs, storage, external services or ledger — verified for the current code by static and behavioural tests, to be re-verified with a real backend; rules-baseline fallback — works (tested); isolation from financial decisions — tested.

## Recorded facts you may need while answering

- **Candidates and sizes (estimates, not verified):** FinBERT about 440 MB, 109.5M parameters, label order 0 positive 1 negative 2 neutral, weights listed for PyTorch, TensorFlow, Flax and safetensors; `roberta-base` about 500 MB, no sentiment head; `cardiffnlp` about 500 MB, label order negative neutral positive (owner-supplied); `mrm8488` 82.1M parameters, PyTorch weights only, its repository also lists `training_args.bin`, a pickle that must never be loaded, and its self-reported 0.982 accuracy is on the easiest PhraseBank subset.
- **Evaluation of a model that is not fine-tuned:** only a model with a sentiment head (FinBERT, `cardiffnlp`, `mrm8488`) can be scored zero-shot; `roberta-base` cannot be compared with anything until it is fine-tuned on an approved training set (A3.13, D14). Zero-shot scoring needs a head over the same three labels, so the label-order mapping is read from each model's own `config.json` at the pinned revision, never assumed.
- **Command shapes (not executed, shown so the scope is clear):** metadata query — the approved script with the B-answers as arguments; environment — `python -m venv <C3 path>` then `pip install --no-index` from wheels fetched once with `--require-hashes` from the recorded list; download — the E1 fetch step with the A3 answers; training — `python -m training.sentiment.train_sentiment_transformer ... --revision <A3.7>` (offline unless C2 allows `--allow-hub-download` for that run); evaluation — `python -m training.sentiment.evaluate_sentiment_model --frozen-manifest ... --records ... --rubric ... --annotator-manifest ... --adjudication-log ... --predictions NAME=FILE`.
- **Abort rules I will follow:** a licence, hash, file, host or revision that differs from your entry — delete the partial artifact and stop; a manifest check failing — nothing is evaluated; an unanswered ID — the phase that needs it does not start.
- **Not changed by anything above:** the production method, the flag, intensity regression (deferred), the isolation of sentiment from every financial decision, and the rule that no sentiment or personal data reaches the ledger or blockchain.
