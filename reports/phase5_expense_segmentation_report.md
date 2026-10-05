# Phase 5 — Expense Segmentation Report

Population: 32424 Kaggle users (primary dataset). Characterizes the Kaggle population only — no FAR-Trans linkage.

## Method comparison (silhouette at each method's own best k)

| Method | Best k | Silhouette | Notes |
|---|---|---|---|
| K-Means | 2 | 0.4580 | full population |
| Ward | 2 | 0.4065 | 5,000-row subsample |
| GMM | 10 (cov=full) | 0.0129 | selected by BIC, not silhouette |

**Selected: kmeans, k=2**

## Cluster profiles (actual computed statistics)

### Cluster 0 — low-expense-high-leverage-higher-savings
- Size: 28542 (88.0% of population)
- Mean: {'expense_to_income_ratio': 0.6007888234580352, 'savings_to_income_ratio': 5.047390512227595, 'debt_to_income_ratio': 0.3101506551748301, 'emi_to_income_ratio': 0.19792810701056232}

### Cluster 1 — low-expense-high-leverage-lower-savings
- Size: 3882 (12.0% of population)
- Mean: {'expense_to_income_ratio': 0.5982297037801926, 'savings_to_income_ratio': 5.0310200927357025, 'debt_to_income_ratio': 7.699768160741885, 'emi_to_income_ratio': 1.941911064652165}
