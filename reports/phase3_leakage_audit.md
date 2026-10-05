# Phase 3 — Temporal Leakage Audit

Performed 2026-09-14 on `backend/wealthpilot/data/preprocessing.py`, in response to a direct review request. All numbers below are from real runs against the actual FAR-Trans data (`datasets/raw/FAR-Trans/`), not estimated.

## 1. Target-date definition

For a customer with at least one genuine `riskLevel` (Conservative/Income/Balanced/Aggressive), the target is their **most recent genuine-labeled row**. That single row supplies three things together, deliberately from the same row so they cannot drift apart:

- the label (`riskLevel`)
- the target date (that row's `timestamp`)
- `customer_type` / `investment_capacity` as of that date

`timestamp` was chosen over `lastQuestionnaireDate` as the temporal anchor because the two are inconsistent for a large share of rows: 12,501 of 32,468 `customer_information.csv` rows have `timestamp < lastQuestionnaireDate`, by up to several thousand days in some cases. `lastQuestionnaireDate` is not a reliable point-in-time anchor in this dataset; `timestamp` is what the row-selection logic already sorts on.

## 2. Exact date/time used for the target

`target_dates(customers)` in `preprocessing.py` — `customerID -> timestamp` of that customer's latest genuine-labeled row. 21,629 customers have one (matches Phase 2's genuine-label-customer count exactly).

## 3. Exact transaction/date cutoff used for customer features

**Before the fix:** none. Every behavioural feature (asset mix, trading intensity, position sizing, channel share, concentration/Herfindahl, top-sector share) was computed from a customer's **entire** transaction history through the dataset's end (2022-11-30), regardless of their target date.

**After the fix:** every behavioural feature is computed only from `transactions` rows with `timestamp <= target_date` for that customer (`_point_in_time_transactions`). A labeled customer with zero transactions at or before their own target date is dropped from the output entirely — there is nothing point-in-time-safe to compute for them.

`customer_type`/`investment_capacity` are also now taken from the target row itself (see section 1), not a separately-computed "latest row overall," which could reflect a change made after the target date.

## 4. Exact market-price cutoff used for market-derived features

**Before the fix:** none. `realized_volatility` and `max_drawdown` were computed once per ISIN over that ISIN's **entire** `close_prices.csv` history (2018-01-01 to 2022-11-29) and reused for every customer holding it, regardless of target date.

**After the fix:** volatility and drawdown are computed as *expanding* (point-in-time) statistics per ISIN — the running standard deviation of daily returns and the running max drawdown, both defined so that the value at each date uses only price data up to and including that date. Each customer's value is then looked up "as of" their own target date via `pandas.merge_asof(..., direction="backward")`, which returns the most recent available point-in-time statistic at or before that date — never after. An ISIN with no price history at all before a customer's target date contributes no value for that holding (excluded from the per-customer average, not zero-filled).

## 5. Whether any feature currently uses information after the target date

**Before the fix: YES**, severely, in both categories audited.

**After the fix: NO**, verified two ways:
- An automated test (`test_no_feature_uses_price_data_after_the_customers_target_date` in `tests/backend/data/test_preprocessing.py`) independently recomputes `realized_volatility`/`max_drawdown` for every labeled fixture customer using its own filtering logic (not the module's), and asserts an exact match.
- Every behavioural/market feature function now only ever receives a pre-filtered transactions frame or an explicit per-customer `as_of_date` used in a backward-only lookup; there is no code path left that reads a raw, unfiltered table for a labeled customer's feature computation.

## 6. Number of customers affected (real data, measured before the fix)

| Leak | Affected | Of | Share |
|---|---|---|---|
| Transaction-derived features (asset mix, trading intensity, position sizing, channel, concentration) | 16,539 customers | 21,629 labeled customers | 76.5% |
| Total transactions used that occurred after the customer's target date | 229,199 transactions | 349,615 transactions belonging to labeled customers | 65.5% |
| Market-derived features (volatility, drawdown) | 21,618 customers | 21,629 labeled customers | 99.95% |
| Customer-ISIN holding pairs whose price stats used post-target-date prices | 76,247 pairs | 76,286 total holding pairs | 99.9% |

`customer_type`/`investment_capacity`: checked directly — in the *current* FAR-Trans data, these never actually differ between a customer's latest-genuine-row and latest-row-overall (0 of 21,629 customers), so this specific leak did not affect real values today, but the original code had no structural guarantee of that, and now does (see section 1).

## 7. Which features are affected

**Behavioural (all 15 non-market numeric/categorical features):** `pct_value_stock`, `pct_value_bond`, `pct_value_mtf`, `equity_to_bond_ratio`, `trades_per_year`, `buy_sell_ratio`, `active_months`, `position_size_mean`, `position_size_median`, `position_size_std`, `largest_trade_pct_of_total`, `herfindahl_index`, `top_sector_share`, `pct_channel_internet`, `pct_channel_phone`, `pct_channel_branch`.

**Market-derived:** `realized_volatility`, `max_drawdown`.

**Not market-derived, checked separately:** `customer_type`, `investment_capacity` — structural risk noted in section 6, no actual leaked values found.

## 8. Concrete examples (real, anonymized FAR-Trans customerIDs — already-anonymized dataset identifiers, not personal data)

| customerID | target_date | Leak before fix |
|---|---|---|
| `00017496858921195E5A` | 2021-03-19 | 91 transactions after target_date used in features (latest: 2022-11-24) |
| `001270E70A4ECA1CD664` | 2018-01-02 | 10 transactions after target_date used (latest: 2022-10-25) |
| `002D8901556066EA2453` | 2020-05-14 | 13 transactions after target_date used (latest: 2022-05-23) |

For the market-feature leak specifically: a customer's `realized_volatility`/`max_drawdown` were, before the fix, computed identically regardless of whether their target date was 2018-01-02 or 2022-11-30 — both got the exact same ISIN-level statistic computed over the full 2018–2022 window.

## 9. Whether the current (fixed) feature table is safe for Phase 4 training

**YES**, with one honest caveat: 101 of 21,629 previously-labeled customers (0.5%) are now excluded because they have zero pre-target-date transactions — there is genuinely nothing point-in-time-safe to compute for them. The trainable set is 21,528 customers. Label distribution is essentially unchanged (Income 9,139 / Balanced 7,159 / Conservative 2,850 / Aggressive 2,380 vs. the pre-fix 9,179/7,194/2,857/2,399) — the fix removes leaked signal, not a meaningful chunk of the label distribution.

---

## Unrelated bug found during this audit (not temporal leakage, fixed anyway)

`asset_information.csv` has 28 ISINs with more than one row (Phase 2 finding); 3 of those (`IE00B66F4759`, `IE00BCRY6003`, `LU0055631609`) actually disagree on `assetCategory` between their duplicate rows. The original `_asset_mix_features` joined `transactions` against `assets` without deduplicating first, which **multiplies** every transaction row touching a duplicated ISIN (13,157 transaction rows) — a row-cardinality correctness bug, inflating summed values for affected customers. `ingestion.py`'s category lookup had the same underlying issue (non-deterministic `dict` overwrite instead of duplication, but still wrong for the 3 inconsistent ISINs). Both are now fixed by deduplicating `assets` on ISIN (keep latest by `timestamp`) before use. Checked against the already-ingested dev database: **zero** ingested transactions reference the 3 ISINs with genuinely inconsistent categories, so no re-ingestion was needed for already-loaded data.
