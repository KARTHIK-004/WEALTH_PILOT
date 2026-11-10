# Annotation instructions: wording tone (version v1)

You will see rows of `item_id`, `theme` and `title`. Fill the `code` column for every row. Use only the title text.

Rules that make your labels usable as independent ground truth:

- Work on your own judgement. Do not use any suggestion, score, tone number or model output, and do not discuss items with another annotator before you have finished.
- If you have seen any such output for an item, leave `code` blank and write `SEEN` in `note`; the item is then dropped, not guessed.
- Record your initials (never an email) as `annotator_id` when you return the sheet.
- Codes: `POS`, `NEG`, `NEU`, `MIX` (the headline clearly points both ways) and `UNC` (you cannot tell). `MIX`, `UNC` and `NEU` are three different answers: do not use `NEU` to mean "not sure".
- `MIX` and `UNC` are valid answers. They are reported as counts and are not compared with a scorer's positive/negative/neutral.
- Leave nothing blank except under the `SEEN` rule above. Do not edit `item_id`, `theme` or `title`.

## Question

Judging only the WORDS of the headline, is its tone positive (`POS`), negative (`NEG`) or neutral (`NEU`)? Ignore what you think the news means for any market or asset: a headline about falling prices can be written in
neutral words, and a cheerful headline can describe a bad event. The `theme` column does not change the question.
