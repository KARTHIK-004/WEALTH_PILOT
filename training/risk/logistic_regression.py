"""Logistic Regression — the required baseline (PROJECT_PLAN.md section 2.1:
"Keep as baseline — always report a baseline"). Expected to lose to the
tree models; reported regardless.

Hyperparameter search per PROJECT_PLAN.md section 6.1: C in {0.01, 0.1, 1,
10}, L2 penalty, multinomial (the lbfgs solver's default when there are more
than two classes — `multi_class` is not set explicitly since it is
deprecated as of scikit-learn 1.5). Class imbalance handled via
`class_weight="balanced"`, not resampling, per CLAUDE.md's default
preference for weighting over SMOTE.
"""

from __future__ import annotations

import time

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV

from training.risk.common import (
    RANDOM_STATE,
    ModelEvaluation,
    build_pipeline,
    evaluate_out_of_fold,
    library_versions,
    make_cv_folds,
)


def train_and_evaluate(X, y) -> tuple[ModelEvaluation, object]:
    cv = make_cv_folds()
    pipeline = build_pipeline(
        LogisticRegression(
            penalty="l2",
            solver="lbfgs",
            max_iter=2000,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        )
    )
    param_grid = {"classifier__C": [0.01, 0.1, 1, 10]}

    search = GridSearchCV(pipeline, param_grid, cv=cv, scoring="f1_macro", n_jobs=-1, refit=True)

    t0 = time.time()
    search.fit(X, y)
    fit_time = time.time() - t0

    best_idx = search.best_index_
    per_fold_scores = [
        float(search.cv_results_[f"split{i}_test_score"][best_idx]) for i in range(cv.get_n_splits())
    ]

    evaluation = evaluate_out_of_fold(
        name="logistic_regression",
        fitted_search_or_pipeline=search.best_estimator_,
        X=X,
        y=y,
        cv=cv,
        best_params=search.best_params_,
        fit_time_seconds=fit_time,
        library_version=library_versions()["scikit-learn"],
        class_weight_strategy="class_weight='balanced'",
        macro_f1_per_fold=per_fold_scores,
    )
    return evaluation, search.best_estimator_
