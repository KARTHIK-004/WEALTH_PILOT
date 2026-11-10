# GDELT Development Sample — Annotation Quick Reference

**Sources:**

- `review_files/ANNOTATION_INSTRUCTIONS.md` (generated in B2-O);
- the rubric in `reports/phaseB2I_filter_review_and_acquisition_preparation.md` §3.

**Nothing here adds a label or changes the rubric.** Where the sources are unclear, the point is listed
in section 8, not decided.

---

## 1. The ground rules

- **Allowed evidence:** the title, the URL, the source domain and the dates. Do not open the link.
- **No hindsight:** never use knowledge of later market moves. Judge the **topic**, not its impact.
- **Label every theme** on every row:
  - `rel_equity`: US equity / Nasdaq markets;
  - `rel_rates`: US interest rates and bond markets;
  - `rel_gold`: the gold market.
- **One row can be `R` for several themes,** for example a market wrap covering stocks, yields and
  gold.

## 2. Relevance: `R`, `RL`, `I`, `A`

| Code | Use when |
| --- | --- |
| `R` | The theme's market is **a main subject**: its prices, moves or outlook, or a driver explicitly framed through that market |
| `RL` | It is mentioned or adjacent but not mainly about it: one company, a non-US market (for the US themes), local retail prices, macro news with no market framing |
| `I` | No real connection, or the word is used in another sense (a "bond" between people, a gold medal, "stock" as inventory) |
| `A` | The allowed evidence cannot decide. Keep `A` rather than guessing, and add an ambiguity code |

**Theme reminders** (B2-I §3.4):

| Theme | `R` | `RL` |
| --- | --- | --- |
| Equity | The US stock market, Nasdaq Composite or Nasdaq-100, S&P 500, Dow, Russell 2000; market-wide drivers framed by their effect on US stocks | One company's shares, earnings or rating, crypto, investing advice |
| Rates | Fed decisions or signals on rates, Treasury yields, US bond-market moves, inflation or jobs data framed through rates, the Fed or bonds | Non-US central banks, mortgage rates, one issuer's bond sale |
| Gold | Gold price or gold-market moves, central-bank buying, gold-fund flows | A miner's results, local retail gold rates, other metals, a passing mention |

## 3. Ambiguity code (`amb_code`): required whenever any theme is `A`

| Code | Meaning |
| --- | --- |
| A1 | Title uninformative: generic, truncated, a site name, "live updates" |
| A2 | Country unclear, US or not. **US themes only** |
| A3 | Market-level or single company unclear |
| A4 | Word sense unclear: gold, bond, yield, stock, shares, rates |
| A5 | Title not English, or garbled |
| A6 | Title and URL disagree |
| A9 | Other. **Explain it in `note`** |

Leave `amb_code` blank when no theme is `A`.

## 4. `company_notice`: on every row

| Value | Meaning |
| --- | --- |
| `Y` | A company- or fund-level notice: holdings disclosures (including positions in QQQ, GLD or AGG), analyst ratings and price targets, insider trades, dividend declarations, one company's earnings |
| `N` | Not such a notice |
| `U` | Unclear |

If `company_notice` is `Y`, **no theme may be `R`.** Such items are at most `RL`.

## 5. Polarity: only for a theme labelled `R`

Polarity is a **separate question from relevance.**

- `R` says the item is about that market; it says nothing about direction.
- Record the direction the title reports or clearly implies **for holders of that asset**, never your
  own forecast.

| Value | Equity | Rates (holders of US bonds) | Gold |
| --- | --- | --- | --- |
| `POS` | Stocks rising, or supportive news | Yields falling, or cuts expected | Gold price up |
| `NEG` | Stocks falling, or adverse news | Yields rising, or hikes expected | Gold price down |
| `NEU` | Factual, no direction | Same | Same |
| `MIX` | Opposite directions, e.g. Nasdaq up and Dow down | Same | Same |
| `UNC` | **The direction cannot be determined.** Use it instead of guessing | Same | Same |

Leave `pol_x` blank whenever that theme is not `R`.

## 6. The other fields: required on every labelled row

| Field | Value |
| --- | --- |
| `annotator_id` | Your initials (never an email) |
| `annotator_type` | `human` (AI suggestions never go in this file) |
| `label_basis` | `own` on all 312 overlap rows. On other rows: `own`, or, only once AI suggestions exist, `accepted_ai`, `corrected_ai` or `rejected_ai` |
| `labelled_at_utc` | The UTC date (`2026-10-14`), or date and time (`2026-10-14T09:30Z`) |
| `near_dup_of` | Optional: the `item_id` of another item that tells the same story |
| `note` | Optional, except: **required** for `amb_code` A9, and when you change an existing label (a correction) |

## 7. Preserving uncertainty

- **Relevance:** if you cannot decide, use `A` with a code. Don't force `R` or `I`.
- **Direction:** if a relevant title's direction is unclear, use `UNC`. Don't infer one.
- **Company notices:** if you can't tell whether it is one, use `U`.
- **Never delete or blank a label** to "fix" it. Change it and give the reason in `note`.

## 8. Points the existing rubric leaves unclear (not decided here)

1. **One `amb_code` field serves three themes.**
   - **The gap:** the rubric does not say what to record when two themes are `A` for different
     reasons.
   - **The validator** accepts one code and does not choose for you.
   - **Your options:** pick the dominant reason and describe the other in `note`, or approve a rubric
     change before labelling. Either decision should be made before you start.
2. **`near_dup_of` says "an earlier item".** "Earlier" is not defined (file order or publication
   time). The validator only checks that the value names another existing item.
3. **`labelled_at_utc` says "ISO time"** without a precision. The validator accepts a UTC date or a
   UTC date-time ending in `Z`.
4. **`company_notice = U` together with `R`.** The rubric rules out `R` only for `Y`. The validator
   follows that literally, and does not block `U` with `R`.
5. **Which file holds the final labels.**
   - **Then:** the generated instructions and the B2-P gap report said to label `annotation_A.csv`
     itself.
   - **Now:** to keep the generated file unchanged, B2-Q uses a working copy. Labels go in
     `working/annotation_A.working.csv`, and the evaluation will freeze that file.
6. **One item has an empty title.**
   - **The gap:** the rubric does not mention empty titles.
   - **B2-O's suggestion:** A1 ("title uninformative"). That was a reading, not a rubric rule.
   - **The validator** does not force any value.
