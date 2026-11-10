# Annotation rubric for AI suggestions (b2t_rubric_v1)

STATUS: PROPOSED. This restates the existing B2 rubric (B2-I section 3, the B2-R and B2-S decisions) for use in a
prompt. It adds no label, code or rule. It is approved only when approval Gate B binds its SHA-256.

## Task

You are given ONE item: a news headline with its URL text, source domain and date. You cannot see the article.
Judge only what the supplied fields show. Return one JSON object as described under "Output".

Rules for the evidence:

- Use only the supplied title, URL text, source domain and date. Do not use outside knowledge of later events,
  prices or market moves (no hindsight). Judge the TOPIC, not its impact.
- Never invent article content, quotations or facts. If the supplied fields do not decide a label, say so.
- This is a headline-and-URL judgement. It is NOT a full-article review, and your output must say so
  (`evidence_basis` is always "headline_url_only").

## Themes (label all three on every item)

- rel_equity: US equity markets, Nasdaq Composite or Nasdaq-100, S&P 500, Dow, Russell 2000.
- rel_rates: US interest rates and bond markets, Federal Reserve decisions, Treasury yields.
- rel_gold: the gold market.

## Relevance codes (one per theme)

- R: the theme's market is a main subject (its prices, moves or outlook, or a driver explicitly framed through that
  market).
- RL: related or adjacent: one company, a non-US market (for the US themes), local retail prices, macro news with no
  market framing.
- I: irrelevant, or a word used in another sense (a "bond" between people, a gold medal, "stock" as inventory).
- A: the supplied fields cannot decide. Use A rather than guess.

## Ambiguity code (amb_code)

Required, as ONE primary code, whenever any theme is A; otherwise empty. Describe any further ambiguity in `note`.

- A1: title uninformative (generic, truncated, a site name, "live updates"), or empty.
- A2: country unclear, US or not. Applies to the US themes only, never to gold alone.
- A3: market-level or single company unclear.
- A4: word sense unclear (gold, bond, yield, stock, shares, rates).
- A5: title not English, or garbled.
- A6: title and URL disagree.
- A9: other; explain in `note`.

## Company or fund notice (company_notice)

- Y: a company- or fund-level notice: a holdings disclosure (including a position in QQQ, GLD or AGG), an analyst
  rating or price target, an insider trade, a dividend declaration, or one company's earnings.
- N: not such a notice.
- U: unclear.

RULE: if company_notice is Y, NO theme may be R (at most RL). Y and R can not be combined.

## Polarity (pol_equity, pol_rates, pol_gold)

Only for a theme labelled R; otherwise empty. The direction the headline reports or clearly implies for holders of
that asset, never your own forecast.

- POS: stocks rising or supportive news / yields falling or cuts expected / gold price up.
- NEG: stocks falling or adverse news / yields rising or hikes expected / gold price down.
- NEU: factual, no direction.
- MIX: opposite directions in one headline.
- UNC: the direction cannot be determined from the supplied fields. Use UNC rather than infer a direction.

## Evidence excerpts

For every theme you label R or RL, give at least one excerpt that is a verbatim substring of the supplied title,
URL text or source domain, tagged with the theme field it supports. Do not paraphrase. An excerpt that does not
appear in the supplied fields makes the whole answer invalid.

## Uncertainty

For each theme give `low`, `medium` or `high` uncertainty. This is your own rough indication. It is not a
probability and will not be treated as one.

If the supplied fields are not enough to label the item, set `insufficient_evidence` to true and label at least one
theme A with its ambiguity code. A forced guess is worse than an honest A.

## Output

Return ONE JSON object and nothing else (no markdown, no commentary) with exactly these keys:

item_id (the supplied id, unchanged), rel_equity, rel_rates, rel_gold, amb_code, company_notice, pol_equity,
pol_rates, pol_gold, note (one short sentence, at most 300 characters), evidence_excerpts (list of objects with
`field` and `excerpt`), insufficient_evidence (true or false), uncertainty (object with rel_equity, rel_rates,
rel_gold), evidence_basis ("headline_url_only").
