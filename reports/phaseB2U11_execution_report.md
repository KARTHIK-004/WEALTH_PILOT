# Phase B2-U11: execution report

Date: 2026-10-19. Status: **documentation and verification only. No source file, test, dataset, switch or record was changed.** B2 is incomplete, AI execution is blocked, and nothing was committed.

Written for: you, the project owner. It records what was checked and run, what changed, and what was not done. The decisions are in the [decision sheet](phaseB2U11_methodology_decision_sheet.md).

## 1. Verified baseline

| Item | Reported (U10) | Verified in U11 | Match |
| --- | --- | --- | --- |
| Git HEAD, branch | `71b363f`, `master` | `71b363f`, `master`; 0 staged; unrelated user changes left alone | yes |
| Working tree | 93 entries after U10 | 93 at the start; 97 now (the four U11 reports are new, untracked files) plus edits to two existing reports and `docs/MEMORY.md` | yes |
| GDELT suite | 794 passed | 794 passed (run at the start and at the end) | yes |
| Build lock; adapter registry | `False`; empty | `False`; `{}` | yes |
| `NETWORK` / `DEV_SAMPLE` / `CONFIRMATION_SAMPLE` | `True` / `True` / `False` | `True` / `True` / `False`, file unedited | yes |
| Dry-run prerequisites | 15 | 15 under each of the three exclusion modes (scratch configs outside the repository) | yes |
| Evaluation fingerprint | `48ceaaba…` | `48ceaaba5b64325da5adf7be84240211fad0d544e90af50f039130ac425bf2fb` | yes |
| Freeze, results, approval, experiment, suggestion, review, export records | none | none | yes |
| Sealed key | unopened, 142,900 bytes, 2026-10-13 22:28:16 +0530 | the same, by metadata only | yes |
| `datasets/` | unchanged | 0 files newer than the U7 baseline marker | yes |

No reported safety invariant failed. No discrepancy blocked any work.

## 2. What was read and what it established

- The authoritative M1, M2 and M3 definitions: `phaseB2_completion_decision_document.md` section 2 (lines 52 to 61). The B2-T proposal uses a different lettering (A to D); this was flagged, not merged.
- The pre-registered estimators and rules: B2-I sections 4.4, 4.6, 4.7 (lines 417, 448 to 449, 469). The recall wording in 4.7 ("pooled capture recall") is ambiguous and differs from both the code's gate and the constant's name.
- The exclusion behaviour of each mode on the real 1,493 items: measured by the non-writing `ai dry-run` on scratch configurations (section 4).
- Polarity: `annotate.POL_VALUES`, the validator, and the B2-U4 section 6.2 options. "Bootstrap polarity" appears in no document or code.
- Review origins and label bases: `ai/reviewer.py`, the rubric addendum, `review.py`. No definition maps `human_uncertain` or `human_insufficient_evidence` to a working-copy basis.
- Export manifest contents and the order in which the audit event is appended (this fixes how an audit-head check must work).

## 3. Deliverables

| File | Purpose |
| --- | --- |
| `reports/phaseB2U11_methodology_decision_sheet.md` | the exact M1/M2/M3 table, a recommendation labelled as one, and decisions D1 to D11 with choices and consequences |
| `reports/phaseB2U11_bridge_hardening_plan.md` | F1 to F4: current behaviour, scenario, proposed change, files, tests, risks, acceptance |
| `reports/phaseB2U11_statistical_reconciliation.md` | independent reproduction, formulas traced to source, claims classified |
| `reports/phaseB2U11_execution_report.md` | this file |
| `reports/phaseB2U10_readiness_report.md` | a superseded-in-part note at the top (the withdrawn label-basis recommendation; 64.9% is 64.88%); no historical conclusion rewritten |
| `docs/MEMORY.md` | one short factual entry |

## 4. Commands run

| Command | Purpose | Result |
| --- | --- | --- |
| `git rev-parse`, `git status --short`, `git diff --cached --name-only` | repository state | as in section 1 |
| `.venv/Scripts/python.exe -m pytest tests/backend/data/gdelt -q -p no:cacheprovider` | the GDELT suite, real code with synthetic fixtures | **794 passed**, 0 failed, 0 skipped, exit 0 (46 s), at the start and the end |
| `python -m wealthpilot.data.gdelt ai dry-run --experiment <scratch yaml>` x3 (`overlap_and_blind`, `blind_only`, `none`) | measure what each mode lets through | `provider_called`, `data_sent`, `files_written` all `False`; sendable 1,181, 1,493 and 1,493; excluded 312, 0 and 0; 15 unmet prerequisites each. The destination folder was never created. These are not approvals and the configs live outside the repository |
| `python -I u11_independent.py compare` (scratch) | the independent statistical reproduction, then a comparison with the project's estimators on synthetic items | all reproduced; the two parts agree |
| `python -I u8_state.py` (scratch, read-only) | provenance, lock, adapters, fingerprint, freeze existence, key metadata | as in section 1 |
| `find datasets -type f -newer <U7 baseline marker>` | detect any data change | 0 files |

Before each command its side effects were checked: `pytest` writes only to temporary directories; `ai dry-run` is documented and tested to write nothing; the scratch scripts open only `annotation_A.csv` and `selection_log.json` and call `stat` on the key.

**Not run, and not reported as passing:** the hosted-database backend suite, `npx tsc -b`, `npm run build`, `npx oxlint`, and the full-project `pytest tests/`. Nothing outside the GDELT package changed, and the database suites use hosted services that could mutate shared state. No test was added: this is a documentation phase and the planned tests are specified in the hardening plan.

## 5. Safety-boundary confirmation [VERIFIED]

- No provider call and no network request. The dry runs only read local files.
- No dataset content transmitted.
- The sealed key was **not** opened, parsed or revealed; only its size and modification time were read.
- No real label, suggestion, freeze, approval or export record was created.
- `NETWORK` and `DEV_SAMPLE` unchanged; no switch edited.
- No adapter, no build-lock change, no retention implementation, no deletion.
- No dataset or source file modified; the only repository files changed are the four new reports, the superseded note in the U10 readiness report, and `docs/MEMORY.md`.
- No self-authorisation: every approval-shaped item is listed as pending.
- No commit or push. B2 is not marked complete.

## 6. What changed since U10 in conclusions

1. The U10 recommendation to derive a label basis from content is **withdrawn**.
2. "64.9%" is **64.88%**.
3. A new fact: with realised reweighting the independent subset needs **at least 195 C7 items** for a best-case capture recall of 0.90 (expected 60), which makes the earlier conclusion sturdier.
4. A new fact: the audit-chain head in the export manifest is always an ancestor, never equal, so an audit check must be "appears in the chain".
5. A new fact: `blind_only` currently excludes nothing, because no blind subset exists.
6. The meaning of "bootstrap polarity" and of "pooled capture recall" is **not** documented anywhere; both need your clarification.
