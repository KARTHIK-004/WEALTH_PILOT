# Phase 4 — Risk Classification Evaluation Report

Trained 2026-09-13T19:53:51.115725+00:00. Dataset: FAR-Trans (`datasets/raw/FAR-Trans/`), leakage-safe feature table from Phase 3 (`backend/wealthpilot/data/preprocessing.py`). Training population: 21528 customers with a genuine risk label (Conservative/Income/Balanced/Aggressive) — Predicted\_\*/Not_Available excluded.

## Model comparison (identical stratified 5-fold CV, random_state=42)

| Model                    | Macro-F1 (mean ± std) | Fit time (s) | Class-imbalance strategy                           |
| ------------------------ | --------------------- | ------------ | -------------------------------------------------- |
| logistic_regression      | 0.3527 ± 0.0050       | 6.2          | class_weight='balanced'                            |
| random_forest **(best)** | 0.4075 ± 0.0048       | 170.9        | class_weight='balanced'                            |
| xgboost                  | 0.3969 ± 0.0075       | 155.7        | sample_weight=compute_sample_weight('balanced', y) |
| mlp                      | 0.3545 ± 0.0094       | 139.6        | sample_weight=compute_sample_weight('balanced', y) |

### logistic_regression

- Best params: `{'classifier__C': 10}`
- Per-class recall: {'Conservative': 0.7512280701754386, 'Income': 0.21129226392384287, 'Balanced': 0.274759044559296, 'Aggressive': 0.6079831932773109}
- Confusion matrix (rows=true, cols=predicted, labels=['Conservative', 'Income', 'Balanced', 'Aggressive']):
  - [2141, 376, 195, 138]
  - [3537, 1931, 1934, 1737]
  - [1282, 1279, 1967, 2631]
  - [189, 240, 504, 1447]

### random_forest

- Best params: `{'classifier__max_depth': None, 'classifier__max_features': 'sqrt', 'classifier__min_samples_leaf': 5, 'classifier__n_estimators': 300}`
- Per-class recall: {'Conservative': 0.6378947368421053, 'Income': 0.32279242805558594, 'Balanced': 0.4379103226707641, 'Aggressive': 0.42478991596638654}
- Confusion matrix (rows=true, cols=predicted, labels=['Conservative', 'Income', 'Balanced', 'Aggressive']):
  - [1818, 705, 262, 65]
  - [2534, 2950, 2717, 938]
  - [763, 1702, 3135, 1559]
  - [84, 335, 950, 1011]

### xgboost

- Best params: `{'classifier__subsample': 0.8, 'classifier__n_estimators': 300, 'classifier__max_depth': 6, 'classifier__learning_rate': 0.05, 'classifier__colsample_bytree': 0.8}`
- Per-class recall: {'Conservative': 0.7003508771929825, 'Income': 0.27639785534522376, 'Balanced': 0.404106718815477, 'Aggressive': 0.4831932773109244}
- Confusion matrix (rows=true, cols=predicted, labels=['Conservative', 'Income', 'Balanced', 'Aggressive']):
  - [1996, 535, 235, 84]
  - [2959, 2526, 2539, 1115]
  - [964, 1527, 2893, 1775]
  - [128, 276, 826, 1150]

### mlp

- Best params: `{'classifier__units1': 64, 'classifier__units2': 32, 'classifier__dropout': 0.3, 'classifier__epochs': 100, 'classifier__batch_size': 64, 'classifier__patience': 10}`
- Per-class recall: {'Conservative': 0.7642105263157895, 'Income': 0.1921435605646132, 'Balanced': 0.30674675233971227, 'Aggressive': 0.5987394957983193}
- Confusion matrix (rows=true, cols=predicted, labels=['Conservative', 'Income', 'Balanced', 'Aggressive']):
  - [2178, 349, 208, 115]
  - [3661, 1756, 2209, 1513]
  - [1323, 1087, 2196, 2553]
  - [196, 213, 546, 1425]
- Extra: {'stopped_epoch': 40}

## Selected best model: random_forest

Selected by highest mean macro-F1 across the shared 5 folds — not accuracy (PROJECT_PLAN.md section 2.1: class distribution skews toward intermediate profiles, so accuracy alone would favor a model that never predicts a minority class).

## SHAP explainability

Method: TreeExplainer (exact). Sample size: 1000.

Top 10 features by mean |SHAP value| (averaged across classes):

- categorical\_\_investment_capacity_CAP_LT30K: 0.0408
- numeric\_\_pct_channel_internet: 0.0280
- categorical\_\_customer_type_Mass: 0.0241
- numeric\_\_max_drawdown: 0.0224
- numeric\_\_realized_volatility: 0.0198
- numeric\_\_pct_channel_branch: 0.0171
- numeric\_\_pct_value_bond: 0.0141
- categorical\_\_customer_type_Premium: 0.0107
- categorical\_\_investment_capacity_CAP_80K_300K: 0.0101
- numeric\_\_equity_to_bond_ratio: 0.0094

## Predicted vs. real class distribution (best model: random_forest)

PROJECT_PLAN.md section 2.1: "Compare your predicted class distribution
against FAR-Trans's real distribution. Over-prediction of Aggressive is a
bias finding, and reporting it is stronger than hiding it." Computed from
the out-of-fold confusion matrix above (column sums = predicted counts).

| Class        | Real count | Predicted count | Predicted / real            |
| ------------ | ---------- | --------------- | --------------------------- |
| Conservative | 2,850      | 5,199           | 1.82x — over-predicted      |
| Income       | 9,139      | 5,692           | 0.62x — under-predicted     |
| Balanced     | 7,159      | 7,064           | 0.99x — essentially matched |
| Aggressive   | 2,380      | 3,573           | 1.50x — over-predicted      |

The model over-predicts both minority classes (Conservative, Aggressive)
and correspondingly under-predicts the majority Income class — a direct,
expected consequence of `class_weight="balanced"` up-weighting minority
classes during training. This is the honest trade-off of the chosen
class-imbalance strategy: better minority-class recall (Conservative 0.64,
Aggressive 0.42 — both far above what an unweighted model achieves) at the
cost of over-predicting those classes overall. Reported here rather than
hidden.
