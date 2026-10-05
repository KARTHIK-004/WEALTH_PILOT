"""Random Forest — a tree-based contender.

Hyperparameter search per PROJECT_PLAN.md section 6.1 (n_estimators,
max_depth, min_samples_leaf, max_features), via GridSearchCV as PROJECT_PLAN
requires "for the tree models". `class_weight="balanced"` is fixed (not
searched) per PROJECT_PLAN's explicit instruction for this model family.
"""

from __future__ import annotations

import time

from sklearn.ensemble import RandomForestClassifier
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
        RandomForestClassifier(class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1)
    )
    param_grid = {
        "classifier__n_estimators": [100, 300],
        "classifier__max_depth": [None, 10, 20],
        "classifier__min_samples_leaf": [1, 5],
        "classifier__max_features": ["sqrt", "log2"],
    }

    search = GridSearchCV(pipeline, param_grid, cv=cv, scoring="f1_macro", n_jobs=-1, refit=True)

    t0 = time.time()
    search.fit(X, y)
    fit_time = time.time() - t0

    best_idx = search.best_index_
    per_fold_scores = [
        float(search.cv_results_[f"split{i}_test_score"][best_idx]) for i in range(cv.get_n_splits())
    ]

    evaluation = evaluate_out_of_fold(
        name="random_forest",
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
