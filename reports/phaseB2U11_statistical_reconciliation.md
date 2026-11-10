# Phase B2-U11: statistical reconciliation

Date: 2026-10-19. Status: **independent reproduction of the U9 and U10 statistical claims. No criterion, weight, denominator or target was changed.** No labels exist, so no performance result is produced or implied.

Written for: you, the project owner, and a statistical reviewer.

**Inputs used (public, non-sensitive):** `selection_log.json` (cell sizes, seed), `annotation_A.csv` public columns (item ID, record ID, overlap flag), the B2-I text, and the estimator source. **The sealed key was not opened.** No network, no acquisition.

**Method.** Part A of the scratch script `u11_independent.py` (in the session scratchpad, not in the repository) imports **nothing from the project**: it uses only `hashlib`, `csv`, `json` and `math` with the published definitions. Part B then runs the project's estimators on synthetic best-case items and compares. Both parts ran and agree.

**Labels:** [VERIFIED] reproduced independently and matched to the code; [DERIVED] arithmetic from public numbers; [CORRECTED] an earlier statement changed; [ASSUMPTION] depends on something unseen; [UNRESOLVED] cannot be settled with what may be opened.

---

## 1. Formulas traced to the source

| Quantity | Code (`estimators.py`) | Document | Match |
| --- | --- | --- | --- |
| Weight w = N / n | `Scored.weight = cell_rows / cell_items` | B2-I 4.6 "w = N / n" | yes |
| Precision | weighted R share of series members, **ambiguous excluded**; bounds treat ambiguous as all non-R or all R (line 77) | B2-I 4.6 | yes |
| **Pooled recall** | weighted R among members ÷ weighted R over **C1 to C6** (line 96); `None` if no R in C1 to C6 | line 448 | yes |
| **Capture recall** | weighted R in **C1 to C5** ÷ weighted R over **all cells** (line 103). If no non-ambiguous C7 item is R, the C7 term is the rule-of-three weight `N_C7 x 3 / n_C7` and the result is flagged a lower bound | line 449 | yes, with one detail below |
| Rule of three | `RULE_OF_THREE = 3.0`; `n_C7` is the number of **non-ambiguous** C7 items (`len(c7)` after removing `A`) | "3/n, one-sided 95%" | **detail:** B2-I does not say whether n counts ambiguous items |
| Reporting floor | 100 or more "estimate", 30 to 99 "indicative", under 30 "counts only" (line 68) | B2-I 4.6 | yes |
| Wilson 95% | `wilson(k, n, z=1.96)` (line 59) | B2-I 4.6 cross-check | yes |
| Bootstrap | `cluster_bootstrap`: resample whole batches, `random.Random(42)`, 2,000 resamples, lower bound = 2.5th percentile (line 177) | B2-I 4.6 names numpy `default_rng(42)` | **generator differs** (decision D5) |
| Decision gate | `decision.decide_series` uses precision, bootstrap lower bound and **pooled recall**; capture recall is reported only | B2-I 4.7 "pooled capture recall ≥ 0.90" | **terminology ambiguous** |

**Naming inconsistency inside the code.** `PROPOSED_THRESHOLDS` calls the recall key `pooled_capture_recall_min`, but the value it is compared with is `pooled_recall`. The pre-registered text, the constant's name and the gate each say something slightly different. This is a labelling problem, not an arithmetic one, and is the substance of decision D4.

## 2. Reproduction results

### 2.1 Overlap selection rule [VERIFIED]
Seed `wealthpilot-b2i-filter-review-v1` (from `selection_log.json`); an item is overlap if the first 8 hex digits of SHA-256(`seed|iaa|<record ID>`) are below `0x33333333`. Independent implementation, all 1,493 items: **rule equals the file exactly (0 mismatches), 312 overlap**, probability 0.19999999995. Expected 298.6, standard deviation 15.46, z = 0.87.

### 2.2 Weights and the captured total [VERIFIED]
| Cell | N rows | n items | weight N/n |
| --- | ---: | ---: | ---: |
| C1 | 193 | 193 | 1.0000 |
| C2 | 2,848 | 200 | 14.2400 |
| C3 | 1,953 | 200 | 9.7650 |
| C4 | 1,560 | 100 | 15.6000 |
| C5 | 20,300 | 200 | 101.5000 |
| C6 | 24,492 | 300 | 81.6400 |
| C7 | 193,590 | 300 | 645.3000 |

Weight of the captured cells C1 to C5 if every item were R: 193 + 2,848 + 1,953 + 1,560 + 20,300 = **26,854**; C5 is **75.59%** of it.

### 2.3 Capture recall, full sample [VERIFIED; one number CORRECTED]
Formula: `num / (num + r6 + c7)`, where `c7 = N_C7 x 3 / n_C7 = 1,935.9` when no C7 item is R.

| Case (best case: every captured item R, none in C6) | Recall |
| --- | ---: |
| no R among 300 C7 items (rule-of-three term 1,935.9) | **0.9328** |
| one R in C7 (term 645.3) | 0.9765 |
| two | 0.9541 |
| three (equals the rule-of-three term) | 0.9328 |
| four | 0.9123 |
| five | 0.8927 |
| six | 0.8740 |

For 0.90 with no R in C6 or C7 the captured relevant weight must be at least 9 x 1,935.9 = **17,423.1, which is 64.88% of 26,854** (U10 wrote "64.9%", a rounding up by 0.02 points). [CORRECTED, minor] The U10 statement "about 53% to 60% of C5 must be R" also reproduces: with C1 to C4 all R the C5 requirement is 10,869 of 20,300 (53.5%); with C1 to C4 at 80% R it is 12,180 (60.0%).

**Non-monotone behaviour worth knowing:** finding one to three R items in C7 *raises* the recall relative to finding none, because the rule-of-three term (three items' worth of weight) is replaced by the observed weight. This is a property of the bound, not an error.

**Edge case, rule-of-three n.** If 30 of the 300 C7 items are ambiguous, the code uses n = 270 and the best case becomes 0.9258; the independent calculation gives the same. Whether n should count ambiguous items is not stated in B2-I [UNRESOLVED, decision D4].

### 2.4 Capture recall, independent subset [VERIFIED]
| Treatment | Best-case recall | Why |
| --- | ---: | --- |
| Realised reweighting, n'_C7 = 60 (the expectation) | **0.7351** | numerator 26,854, bound 193,590 x 3 / 60 = 9,679.5 |
| **Parent weights** (what the U8 reference scope computes), n' = 20% of each cell | **0.3569** | numerator scaled by about 0.2 (5,371.2) while the bound is scaled by about 5 (9,679.5) |

Best-case recall depends only on the number of C7 items n'_C7 (when reweighted): 50 items give 0.6981, 60 give 0.7351, 80 give 0.7872, 100 give 0.8222, **195 give 0.9002**, 300 give 0.9328. So the independent subset reaches 0.90 only if it holds **at least 195 C7 items**. Its expectation is 60 with standard deviation 6.9, so that is not credible. **The conclusion that the subset cannot meet 0.90 stands.** The 0.3569 figure is an artefact of mixing weight bases (F4) and is not a property of the data.

The project's estimator, run on the same synthetic best-case items, returns 0.9328, 0.3569 and 0.7351 for the three cases: **identical to the independent derivation.** [VERIFIED]

### 2.5 Pooled recall tolerance [DERIVED; an assumption-laden illustration]
Recall = W_in / (W_in + W_out) is at least 0.90 exactly when W_out ≤ W_in / 9. With the series' members all in their own cell and a fraction f of them relevant:

| Series (cell, items) | f | W_in | tolerated outside weight | items tolerated in C4 / C5 / C6 |
| --- | ---: | ---: | ---: | --- |
| gold (C1, 193) | 0.7 / 0.8 / 0.9 | 135 / 154 / 174 | 15 / 17 / 19 | 0,0,0 / 1,0,0 / 1,0,0 |
| rates (C2, 200) | 0.7 / 0.8 / 0.9 | 1,994 / 2,278 / 2,563 | 222 / 253 / 285 | 14,2,2 / 16,2,3 / 18,2,3 |
| equity (C3, 200) | 0.7 / 0.8 / 0.9 | 1,367 / 1,562 / 1,758 | 152 / 174 / 195 | 9,1,1 / 11,1,2 / 12,1,2 |

This reproduces U9 and U10. It assumes all in-series relevant weight comes from the series' own cell, and that "outside" relevant items are only in C4 to C6. A relevant item for the theme in another series' cell (for example a gold-relevant item in C2) also counts as outside. These are illustrations of fragility under assumed precision, **not results**.

### 2.6 Wilson numbers [VERIFIED]
Independent Wilson implementation: minimum successes for an unweighted 95% lower bound of at least 0.60: n = 20 needs 17; **n = 40 needs 31 (0.775)**; n = 100 needs 70; n = 193 needs 130 (0.674); n = 200 needs 134 (0.670). The project's `wilson` agrees to machine precision. **The decision criterion is the bootstrap lower bound, not the Wilson bound**, so these are an optimistic proxy: the batch bootstrap is wider.

## 3. Mathematical results, assumptions, and empirical claims, separated

| Claim | Kind | Status |
| --- | --- | --- |
| The overlap rule reproduces the file exactly | mathematical, on the public file | [VERIFIED] |
| Capture recall best case is 0.9328 (full) and 0.7351 (subset, reweighted) | mathematical | [VERIFIED] |
| 0.90 capture recall needs at least 64.88% of captured weight relevant (full) | mathematical | [VERIFIED] |
| The subset needs at least 195 C7 items for 0.90 | mathematical | [VERIFIED] |
| Parent-weight subset capture recall (0.3569) is an artefact of mixed weights | mathematical | [VERIFIED] |
| Pooled recall tolerance table | mathematical given assumed f | [DERIVED, illustrative] |
| The subset holds about 40 members per series | expectation | [ASSUMPTION]: realised counts need the key |
| The 312 represent each cell | empirical | **[UNRESOLVED]**: realised per-cell counts unseen; the design is random, the draw is unchecked |
| Labels are independent of the hash | empirical | [ASSUMPTION]: no labels exist |
| Any claim that the filter meets or fails a criterion | empirical | **not made**: no labels, no authorised protocol |

## 4. The estimand, and what changing each thing does

- **Target population.** The pre-registered estimators estimate quantities of the **parent sample's population of rows** across the stage's batches (precision of the series, recall against the cue-bearing and the whole population). That is the estimand.
- **Parent weights on the subset** estimate a distorted quantity. **Realised reweighting** estimates the same quantity as the full sample with fewer items. This changes the *estimator*, not the estimand.
- **Changing a target or the floor** changes the *acceptance rule*, not the estimate.
- **Choosing which recall gates** changes the *question* the criterion answers: pooled recall asks "of the relevant items among cue-bearing rows, what share did the series capture", capture recall asks "of all relevant items including the unreachable C7 tail". They are different quantities and have different attainable ranges.
- **Realised cell counts are not available without the key** (only the parent sizes are public). They become available, legitimately, inside the evaluation after the freeze. Under M1 the whole sample is the reference and the issue does not arise.

## 5. What cannot be reproduced, and what is missing

| Item | What is missing |
| --- | --- |
| Realised overlap items per cell and per series | cell and series membership (sealed key) |
| Whether any series cell has too few reference items | the same |
| The label distribution (precision, recall, ambiguity, polarity, company notice) | labels (none exist) |
| Which n the rule of three should use | a decision (D4) |
| What "pooled capture recall" in B2-I 4.7 means | a decision (D4) |
| Whether the bootstrap lower bound is a two-sided 2.5th percentile as intended | confirmation (D5) |

Nothing was filled with a guessed value.

## 6. Verdict on the reported claims

| Claim | Verdict |
| --- | --- |
| U10: full-sample capture recall maximum 0.933 | **verified** (0.9328) |
| U10: subset 0.735 under realised reweighting | **verified** (0.7351) |
| U10: subset 0.357 under parent weights | **verified**, and explained as a weight-basis artefact (F4) |
| U9: capture recall "cannot meet 0.90" on all items | **corrected** in U10; reconfirmed here: reachable only in a demanding best case |
| U9 and U10: about 40 members per series in the subset | **unresolved**: an expectation only |
| U9 and U10: the 312 are representative | **not claimed**; unresolved |
| U10: 64.9% | **corrected** to 64.88% (rounding) |
| U10: the content-derived label-basis recommendation | **withdrawn** (see the decision sheet, D7) |
