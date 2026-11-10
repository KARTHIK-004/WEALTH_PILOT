# Phase B2-U11: bridge-hardening plan (F1 to F4)

Date: 2026-10-19. Status: **a plan. No fix is implemented; none will be without your explicit authorisation (D11 in the [decision sheet](phaseB2U11_methodology_decision_sheet.md)).** No real AI output is needed for any of them.

Written for: you, the project owner, and a reviewer of the bridge code.

> **Status (B2-U12, 2026-10-19):** F1, F2, F3 and F4b were authorised and implemented offline (F4a held); see the decision log in `phaseB2U12_m2_selection_and_plan.md`. The plan text below is unchanged.

**Evidence.** F1 to F3 come from three throwaway probes on synthetic data (U10, a temporary test file since deleted). The code locations below were re-read in U11. Every test named here is **synthetic**: it shows that a rule fires, not that real annotation or evaluation is valid.

**Common constraints for every fix:** read-only (no new write path, no new record); no weakening of any existing check; the legacy validator and its default behaviour unchanged; no provider, network, sealed-key or dataset access; the build lock and adapter list untouched; the 794 existing GDELT tests must still pass.

## What the export manifest records [VERIFIED, `ai/export.py` lines 86 to 96]

`chain_heads` holds the heads of the suggestion, review and audit chains **at export time**. The audit event `export_created` is appended **after** the manifest is built, so the audit head in the manifest is always an **ancestor** of the current audit head, never equal to it. Any audit check must therefore be "appears in the chain", not equality. Suggestion and review heads are equal immediately after export (U10 probe P0).

---

## F1. Suggestion-chain head not compared with the manifest

- **Current behaviour.** `ai_bridge.load` verifies the chain and the derived CSV but never reads `chain_heads`. After a valid export, appending a **non-terminal** attempt to the suggestion chain leaves the bridge, and `ai_origin.verified`, still `VERIFIED` (probe P1); the manifest head no longer equals the chain head. The freeze fingerprint would catch it only **after** a freeze.
- **Failure scenario.** Someone (or a bug) appends records to the suggestion chain between export and freeze. Terminal changes are caught by the derived-CSV comparison; non-terminal ones are not.
- **Proposed change.** In `ai_origin.attach` (which holds the manifest), when a bridge exists, require `manifest["chain_heads"]["suggestions"]` to equal the verified current head. Mismatch: add problem `chain_changed_after_export` and block.
- **Files and functions.** `backend/wealthpilot/data/gdelt/ai_origin.py` (`attach`, a small `_chain_checks` helper); `ai_bridge.py` exposes the head it already computes (`Bridge.chain_sha256` is a file hash, so a `head` field is added). About 15 lines.
- **Tests (synthetic).** valid export passes; non-terminal append after export is refused; terminal append is refused (by both checks); manifest without `chain_heads` and no bridge is unchanged (legacy path); freeze refuses and creates nothing.
- **Regression risks.** A legitimate second run on the same experiment would grow the chain after an export; but an export is only made after review of all items and is never overwritten, and a rerun is blocked in this build. Acceptable and intended: a changed store needs a fresh export.
- **Acceptance.** Probe P1 becomes a refusal; all existing tests pass; no write path added.
- **Needs real AI output?** No.

## F2. Review chain not verified; recorded review hash not checked

- **Current behaviour.** The freeze and evaluation path never reads the review chain. `review_record_sha256` in each export row is only checked for format. Editing the review chain after export stays `VERIFIED` although reading that chain raises `ChainError` (probe P2); a self-consistent export carrying a made-up review hash also verifies (probe P3).
- **Failure scenario.** The export CSV (hashed in its manifest) is trusted as the sole record of the human reviews. A forged or altered review record, or an export that does not match the reviews it claims to come from, is not detected.
- **Proposed change.** In `ai_origin.attach`, when a bridge exists: (a) read the review chain (this verifies its hash chain) and refuse on `ChainError`; (b) require each export row's `review_record_sha256` to equal the **current** review record's `record_sha256` for that item; (c) require the manifest's `chain_heads.reviews` to appear in the current review chain, and to equal its head unless a documented correction exists; (d) require the manifest's audit head to appear in the verified audit chain.
- **Design choice for you.** Strict equality of the review head (c) blocks any review correction made after the export, which then needs a new export (an export is never overwritten). The ancestor-plus-row-check form lets later corrections through only when they do not touch an exported row. **Recommended: ancestor plus row check**, because the row check (b) already catches any exported row whose review was superseded.
- **Files and functions.** `ai_origin.py` (`attach`, `_chain_checks`); it reuses `ReviewStore.current` and `ChainedJsonl` from `ai/`. About 30 lines.
- **Tests (synthetic).** edited review chain refused; forged `review_record_sha256` refused; a review superseded after export (new record for an exported item) refused; a review for a non-exported item added later accepted under the recommended form; audit head not an ancestor refused; a valid export passes.
- **Regression risks.** The checks need the experiment folder to be present next to the export; for an export copied elsewhere, `layout_for_export` returns `None` and the checks cannot run (see F3).
- **Acceptance.** Probes P2 and P3 become refusals; all existing tests pass.
- **Needs real AI output?** No.

## F3. Silent fallback when the expected suggestion chain is missing

- **Current behaviour.** `ai_bridge.load` returns `None` if no suggestion chain file sits beside the export, and the legacy source applies. Deleting the chain does exactly that (probe P4). It fails safe today because the legacy validator then needs `ai_suggestions_A.csv` and refuses AI-based labels without it, but the fallback is silent, and a hand-made legacy file would be accepted instead.
- **Failure scenario.** The chain is removed (accident or tamper) and a legacy suggestion file is supplied; AI-based labels then validate against a source the export never mentioned.
- **Proposed change.** If the export directory is a B2-T layout (named `export`, with a sibling `snapshot/` or a manifest whose `chain_heads.suggestions` is not the genesis value) and the chain file is missing, return a failing `Bridge` (a problem, no valid IDs) instead of `None`. A directory that is not a B2-T layout, such as the synthetic exports in `test_end_to_end_evaluation_wiring.py`, keeps the legacy behaviour.
- **Files and functions.** `ai_bridge.py` (`load`). About 10 lines.
- **Tests (synthetic).** chain deleted from a real layout: refused with a clear reason; no layout at all: `None` as before; genesis head and no chain (an experiment with no suggestions): not treated as missing.
- **Regression risks.** An experiment that legitimately has no suggestion chain (M1 with an export, if one is ever made) must not be blocked; the genesis-head rule covers it.
- **Acceptance.** Probe P4 becomes a refusal for a real layout; legacy tests unchanged.
- **Needs real AI output?** No.

## F4. Inconsistent weighting of capture recall in the independent-reference scope

Keep this **separate** from F1 to F3: it is not an integrity fix, it changes how a reported number is computed, and it depends on D3.

- **Current behaviour.** `evaluate._independent_reference` calls the estimators on the human-only items with each item's **parent** weight N_c / n_c, but the rule-of-three term uses the number of C7 items actually present (`len(c7)`). On a roughly 20% subset the numerator shrinks by about 0.2 and the bound grows by about 5. Best case on the real cell sizes: **0.3569** under parent weights against **0.7351** with realised weights (independent reproduction, [reconciliation](phaseB2U11_statistical_reconciliation.md)). Pooled recall is a ratio in which both sides scale together and is not distorted in the same way.
- **Failure scenario.** The reported capture recall for the reference scope is not a valid estimate of anything. It is reported only (never decides), but it would be quoted.
- **Two options.**
  - **F4a (label only, no number changes):** mark capture recall in that scope "not valid under parent weights". Needs no decision on D3. About 5 lines in `evaluate.py` plus a test.
  - **F4b (correct the weights, needs D3 = reweight):** for the reference scope, build the scored items with `cell_items` equal to the realised count of reference items in that cell, so `weight = N_c / n'_c` and the rule of three uses a consistent n. This is a change of about 10 lines inside `evaluate.evaluate` after the key join; it leaves every function in `estimators.py` unchanged. When the reference scope equals all items (M1), `n'_c = n_c` and nothing changes. Add a minimum-reference-items-per-cell rule if you set one (D3).
- **Files and functions.** `evaluate.py` (`_independent_reference`, the call site in `evaluate`); `test_end_to_end_evaluation_wiring.py` or a new test file.
- **Tests (synthetic).** best-case items reproduce 0.9328 (full), 0.7351 (reweighted subset) and are flagged or corrected as chosen; M1-equivalent input gives identical numbers before and after; a cell with no reference items is reported, not crashed; pooled recall is unchanged in value for balanced fractions; the result's fingerprint changes (so a stale freeze is refused).
- **Regression risks.** F4b changes a pre-registered estimator's application and the results format; it changes the evaluation fingerprint. No result or freeze exists, so nothing is invalidated.
- **Acceptance.** F4a: the field carries the note and no number changes. F4b: the reference-scope capture recall equals the independently derived value on synthetic best-case data.
- **Needs real AI output?** No. (It needs the sealed key only at the real evaluation, which is the authorised step after a freeze.)

## Suggested order and a single authorisation request

1. F3, then F1, then F2 (smallest to largest; all in the bridge, all independent of weighting).
2. F4a at any time; F4b after D3.

**To authorise, write:** "authorise F1", "authorise F2", "authorise F3", "authorise F4a" and/or "authorise F4b (after D3)". Without that, none is touched.

## What these fixes do not do

They do not make any real AI output valid, do not prove real annotation quality, do not approve any gate or criterion, do not enable any run, and do not change the build lock, the adapter list, the switches or any data.
