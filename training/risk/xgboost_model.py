"""XGBoost — expected macro-F1 winner per PROJECT_PLAN.md section 2.1.

Hyperparameter search per PROJECT_PLAN.md section 6.1 (learning_rate,
max_depth, subsample, colsample_bytree, n_estimators), via RandomizedSearchCV
(PROJECT_PLAN allows either GridSearchCV or RandomizedSearchCV "for the tree
models" — a full grid over 5 parameters here is 32 combinations; randomized
search bounds runtime while still searching the same space). Class imbalance
handled via `sample_weight` (PROJECT_PLAN: "sample_weight for imbalance"),
computed with `compute_sample_weight("balanced", y)` — XGBoost's sklearn API
has no native multiclass `class_weight`.

`XGBClassifier` requires integer-encoded labels (verified directly: it
raises `ValueError: Invalid classes inferred...` on string `y`), unlike the
other three model families here, which all accept the genuine string labels
natively. `_StringLabelXGBClassifier` wraps `XGBClassifier` to encode on fit
and decode on predict, so this model can be evaluated with the exact same
`evaluate_out_of_fold` / confusion-matrix / calibration code as the others,
and so its output stays labeled with genuine risk-category names rather than
opaque integers.
"""

from __future__ import annotations

import time

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.model_selection import RandomizedSearchCV
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from training.risk.common import (
    RANDOM_STATE,
    ModelEvaluation,
    balanced_sample_weight,
    build_pipeline,
    evaluate_out_of_fold,
    library_versions,
    make_cv_folds,
)


class StringLabelXGBClassifier(BaseEstimator, ClassifierMixin):
    """XGBClassifier that accepts and returns genuine string labels."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        subsample: float = 1.0,
        colsample_bytree: float = 1.0,
        random_state: int = RANDOM_STATE,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.random_state = random_state

    def _build(self) -> XGBClassifier:
        return XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            objective="multi:softprob",
            random_state=self.random_state,
            eval_metric="mlogloss",
        )

    def fit(self, X, y, sample_weight=None):
        self._label_encoder = LabelEncoder().fit(y)
        y_encoded = self._label_encoder.transform(y)
        self.classes_ = self._label_encoder.classes_
        self._model = self._build()
        self._model.fit(X, y_encoded, sample_weight=sample_weight)
        return self

    def predict(self, X):
        return self._label_encoder.inverse_transform(self._model.predict(X))

    def predict_proba(self, X):
        return self._model.predict_proba(X)


def train_and_evaluate(X, y) -> tuple[ModelEvaluation, object]:
    cv = make_cv_folds()
    pipeline = build_pipeline(StringLabelXGBClassifier(random_state=RANDOM_STATE))
    param_distributions = {
        "classifier__n_estimators": [100, 200, 300],
        "classifier__max_depth": [3, 4, 6],
        "classifier__learning_rate": [0.05, 0.1, 0.2],
        "classifier__subsample": [0.8, 0.9, 1.0],
        "classifier__colsample_bytree": [0.8, 0.9, 1.0],
    }

    sample_weight = balanced_sample_weight(y)
    fit_params = {"classifier__sample_weight": sample_weight}

    search = RandomizedSearchCV(
        pipeline,
        param_distributions,
        n_iter=20,
        cv=cv,
        scoring="f1_macro",
        n_jobs=-1,
        refit=True,
        random_state=RANDOM_STATE,
    )

    t0 = time.time()
    search.fit(X, y, **fit_params)
    fit_time = time.time() - t0

    best_idx = search.best_index_
    per_fold_scores = [
        float(search.cv_results_[f"split{i}_test_score"][best_idx]) for i in range(cv.get_n_splits())
    ]

    evaluation = evaluate_out_of_fold(
        name="xgboost",
        fitted_search_or_pipeline=search.best_estimator_,
        X=X,
        y=y,
        cv=cv,
        best_params=search.best_params_,
        fit_time_seconds=fit_time,
        library_version=library_versions()["xgboost"],
        class_weight_strategy="sample_weight=compute_sample_weight('balanced', y)",
        macro_f1_per_fold=per_fold_scores,
        fit_params=fit_params,
    )
    return evaluation, search.best_estimator_
