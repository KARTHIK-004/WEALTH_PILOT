# Rubric dry run - instructions for the adjudicator

The 30 notes are invented. You settle only the texts where the two annotators' labels differ. You are given the two label sets for each such text **without annotator identities** (they appear as "S1" and "S2", in an order that changes from text to text), the text, and the rules in `RUBRIC_EXCERPT.md`. You are given nothing else: no customer, profile, risk assessment or automatic reading.

1. For each text on your worklist, apply the rubric yourself first, then compare with S1 and S2. Do not pick by guessing who wrote which.
2. In `adjudication_template.csv` set `adjudicator_id` (your anonymous code) and fill the labels you consider correct under the rubric.
3. `basis`: `S1`, `S2`, `neither` or `rubric_gap`. Use `rubric_gap` (and `rubric_gap` = `true` with a note) when the rubric does not decide the case; do not force a label. Never use your own authority to change the rubric; rubric edits are made separately and versioned.
4. Texts where both annotators agree are not on your worklist.
5. Return only the filled template.
