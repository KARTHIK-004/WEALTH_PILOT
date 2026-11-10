# Synthetic pilot pack v0 (FICTIONAL, rubric-clarity dry run only)

**This is a rubric-preparation exercise. It is NOT independent validation.** All 30 texts are invented by the pack author. No real customer text is involved. Under the owner's limited approvals of 2026-10-20, O1 is
accepted for fictional notes only (real participant text collection remains prohibited) and O4 for this dry run with two independent annotators and one adjudicator who are independent of the rubric author; O2, O3 and O7 are
undecided, O5 (Option A for annotation) and O6 are still PROPOSED. Nothing here may be used to measure `user_text_rules_v0`, tune it, or train anything; it stays `UNVALIDATED_BASELINE`. The pack must never be merged
into a validation set, and the dry run produces rubric findings, never an accuracy figure. The rubric is `v0-draft` and **not frozen**; the manifest is a DRAFT.

**Status: annotation has NOT started.** No suitable human reviewers have been identified. The rubric author (an AI assistant) did not annotate, and AI-generated labels are not accepted as independent labels. Do not substitute self-annotation and call it independent.

Layout
- `package/` - **the only folder an annotator receives.** Built and checked by `python scripts/build_dry_run_package.py` (then `--verify`): the fictional texts, a blank template, instructions and `RUBRIC_EXCERPT.md` (only the rubric parts between its `annotator-excerpt` markers (sections 1-3 and the flag definitions)).
- `annotator/` - the source files the package is built from. `adjudicator/` - instructions and a blank template for the adjudicator, who also receives `RUBRIC_EXCERPT.md`.
- `author_only/` - never distributed: `author_challenge_map.json` (challenge tags, not labels), `pre_annotation_ambiguities.md` (the author's hypotheses A1-A11, not results), `DRAFT_MANIFEST.json`
  (hashes, approvals in force, `frozen: false`, remaining freeze steps) and `participant_register_TEMPLATE.csv`.

Procedure
1. The owner names two annotators and one adjudicator who are independent of the rubric author and records them (anonymous codes) in a copy of `participant_register_TEMPLATE.csv` with `independent_of_rubric_author` = `yes`.
   `python scripts/build_dry_run_package.py --register REGISTER.csv` then reports `distribution_ready=True` only if two annotators and one adjudicator are attested; otherwise it lists the blockers.
2. Give each annotator `package/` only. Each labels all 30 texts alone and blind (text and id only), setting `rubric_unclear` to `true` wherever the rubric did not decide, with a note.
3. Check the sheets with `python scripts/pilot_disagreements.py sheetA.csv sheetB.csv` (validates allowed values; lists differences and unclear notes; does no scoring).
4. Give the adjudicator the **blind** worklist from `python scripts/pilot_disagreements.py --blind sheetA.csv sheetB.csv` (annotators appear as S1/S2, order varying per text) plus `adjudicator/`. The adjudicator labels only the differing texts and marks `rubric_gap` where the rubric does not decide.
5. Classify each difference as (a) annotator slip, (b) rubric ambiguity, (c) genuinely ambiguous text. Only (b) changes the rubric, as a new rubric version. Tally separately the `rubric_unclear` ticks, the not-entirely-English rows (O5 Option A), and the use of `emotional_tone_proposed` and `ambiguous_tone` (O6).
6. After any rubric change, re-test on a NEW fictional set; this pack has been seen. Freezing is a separate, later process (see the manifest's remaining steps); no claim of a frozen rubric is made.

What the dry run can show: unclear wording, labels people apply inconsistently, missing label values. What it cannot show: model accuracy, how real users write, or that the rubric is valid. The baseline is not run on this pack.
Future real-text collection is blocked, among other things, by the unresolved conflict between withdrawal and unlinkability (decision sheet C3).
