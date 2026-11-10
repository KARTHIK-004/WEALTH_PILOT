# Rubric dry run - instructions for participants

These 30 notes are invented. Nobody wrote them about themselves, and nothing you enter is used to judge a model or a person. The purpose is to find places
where the labelling rules (`RUBRIC_EXCERPT.md`) are unclear.

0. You label the text only. You are given no information about who wrote it and none about any customer, profile, risk assessment or automatic reading, and you must not look for any. Use only `RUBRIC_EXCERPT.md` (the labelling rules and flag definitions); you need nothing else.
1. Work alone. Do not discuss the texts or look at anyone else's sheet until the group session.
2. Copy `annotation_template.csv`, set `annotator_id` on every row (an anonymous code you were given), and label each text in `pilot_texts.jsonl` using only the text and the rubric.
3. Allowed values: `sentiment` = positive | negative | neutral | mixed | uncertain. `emotional_tone` = concerned | hopeful, or empty (one value only).
   `emotional_tone_proposed` = zero or more of concerned | hopeful joined by `|` (the PROPOSED reading; leave it empty if you would not add anything beyond `emotional_tone`).
   `topics` = any of investment_risk | saving | debt | goals | liquidity, joined by `|`. `preferences` = any of capital_preservation | growth_seeking | liquidity_access | debt_reduction, joined by `|`.
   `contradictory`, `ambiguous_tone`, `hedged`, `negation` = true or false. `language` = en | unsupported. `difficulty` = easy | moderate | hard.
4. Whenever the rubric did not tell you what to do, write `true` in `rubric_unclear` and say what was unclear in `note`. That is the most useful output of this exercise.
5. Return only your filled sheet.
