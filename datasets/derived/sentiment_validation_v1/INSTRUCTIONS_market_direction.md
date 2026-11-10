# Annotation instructions: market direction (version v1)

You will see rows of `item_id`, `theme` and `title`. Fill the `code` column for every row. Use only the title text.

Rules that make your labels usable as independent ground truth:

- Work on your own judgement. Do not use any suggestion, score, tone number or model output, and do not discuss items with another annotator before you have finished.
- If you have seen any such output for an item, leave `code` blank and write `SEEN` in `note`; the item is then dropped, not guessed.
- Record your initials (never an email) as `annotator_id` when you return the sheet.
- Codes: `POS`, `NEG`, `NEU`, `MIX` (the headline clearly points both ways) and `UNC` (you cannot tell). `MIX`, `UNC` and `NEU` are three different answers: do not use `NEU` to mean "not sure".
- `MIX` and `UNC` are valid answers. They are reported as counts and are not compared with a scorer's positive/negative/neutral.
- Leave nothing blank except under the `SEEN` rule above. Do not edit `item_id`, `theme` or `title`.

## Question

For the named `theme` (equity_us = US equities / Nasdaq, rates_us = US rates / bonds, gold = gold), does the news point to a positive (`POS`), negative (`NEG`) or neutral (`NEU`) effect on that asset, from the point of view of
someone who HOLDS it? Rising yields are `NEG` for bonds. Judge only what the headline supports, not what you know happened afterwards. The same headline can have different codes for different themes.
