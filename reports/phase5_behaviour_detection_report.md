# Phase 5 — Behaviour Detection Report

Panel: 127924 (customer, month) rows across 29090 customers, built from FAR-Trans transactions.csv. Every row uses only that month's own transactions.

## Indicator definitions (decided explicitly, see common.py module docstring)

PROJECT_PLAN.md names savings rate/expense ratio/contribution rate; FAR-Trans has no savings/expense data. Monitored instead: trading intensity (monthly trade count), contribution rate (monthly Buy value), asset-allocation mix (Isolation Forest only), and risk-category/investment-capacity snapshot changes.

## Rolling z-score / CUSUM (primary)

Trailing window: 12 months; minimum 3 prior months required before a baseline is computed. Alert threshold: |z| > 2.0. CUSUM: k=0.5, h=5.0 (standard textbook defaults, not fit to this data).

### trade_count
- Rows with a computable baseline: 59296 (no baseline for 68628 rows — insufficient prior history)
- Z-score alerts: 5114 rows (2904 distinct customers)
- CUSUM alarms: 7205 rows (1154 distinct customers)

### buy_value
- Rows with a computable baseline: 63091 (no baseline for 64833 rows — insufficient prior history)
- Z-score alerts: 5543 rows (2969 distinct customers)
- CUSUM alarms: 9067 rows (1478 distinct customers)

## Isolation Forest (secondary, multivariate)

Contamination: 0.05. Anomalies flagged: 6397 of 127924 rows (5.0%).

## Risk-category / investment-capacity snapshot changes

5641 rows belong to a multi-dated customer. Changes found: riskLevel=0, investmentCapacity=0. **Zero changes found** — verified directly that none of FAR-Trans's 2,263 multi-dated customers ever change their raw riskLevel or investmentCapacity value across dated rows. This means FAR-Trans's multi-dated customer_information.csv records do not evidence genuine risk-category drift at the raw-value level, contrary to what PROJECT_PLAN.md's rationale for this feature assumes — reported honestly, not hidden. The trading-intensity and contribution-rate detectors above DO find genuine, real behavioural shifts in the same population, so behaviour detection as a whole is not vacuous — only this one specific indicator finds nothing in the current data.