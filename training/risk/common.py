"""Shared utilities for Phase 4 risk-classification training scripts.

Every model-family script (logistic_regression.py, random_forest.py,
xgboost_model.py, mlp.py) imports from here rather than duplicating data
loading, CV-fold definition, or metric computation — so all four models are
evaluated on byte-identical folds and byte-identical metric definitions,
which is what makes the model comparison in Phase 4's report fair.

Training reads raw FAR-Trans CSVs directly and calls the Phase 3
leakage-safe `engineer_features()` — never the application database — per
CLAUDE.md rule 5 ("train offline, serve online"). Nothing in this package
is imported by the FastAPI app.
"""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.calibration import calibration_curve
from sklearn.metrics import confusion_matrix, f1_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.utils.class_weight import compute_sample_weight

from wealthpilot.data.preprocessing import (
    ALL_FEATURES,
    build_preprocessing_pipeline,
    engineer_features,
    load_far_trans_tables,
)

# common.py -> risk/ -> training/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "models" / "risk"
METRICS_PATH = REPO_ROOT / "models" / "metrics.json"
REPORTS_DIR = REPO_ROOT / "reports"

RANDOM_STATE = 42
N_SPLITS = 5
GENUINE_RISK_LEVELS = ["Conservative", "Income", "Balanced", "Aggressive"]


def load_training_table() -> tuple[pd.DataFrame, pd.Series]:
    """(X, y) — the Phase 3 leakage-safe feature table, genuine labels only.

    Reused verbatim from backend/wealthpilot/data/preprocessing.py — this
    function does not recompute or reimplement feature engineering, so
    training can never silently drift from what Phase 3 built and tested.
    """
    tables = load_far_trans_tables()
    features = engineer_features(
        tables["customers"], tables["transactions"], tables["assets"], tables["close_prices"]
    )
    labeled = features[features["risk_level"].notna()].copy()

    non_genuine = set(labeled["risk_level"].unique()) - set(GENUINE_RISK_LEVELS)
    if non_genuine:
        raise AssertionError(
            f"Non-genuine risk_level value(s) reached the training table: {non_genuine}. "
            "This must never happen — engineer_features() only returns genuine labels "
            "for its 'risk_level' column (CLAUDE.md rule 7)."
        )

    X = labeled[ALL_FEATURES]
    y = labeled["risk_level"]
    return X, y


def make_cv_folds() -> StratifiedKFold:
    """The one, shared set of folds every model family is evaluated on."""
    return StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)


def build_pipeline(classifier: Any) -> Pipeline:
    """preprocessor + classifier as one Pipeline.

    This is what makes "fit preprocessing only on the training fold" hold
    automatically: sklearn's GridSearchCV/cross_val_predict clone and fit
    the WHOLE pipeline fresh on each fold's training data, so the
    preprocessor (impute/scale/encode) never sees a validation fold's rows
    until after it was fit without them.
    """
    return Pipeline(steps=[("preprocess", build_preprocessing_pipeline()), ("classifier", classifier)])


def balanced_sample_weight(y: pd.Series) -> np.ndarray:
    return compute_sample_weight("balanced", y)


@dataclass
class ModelEvaluation:
    """Everything Phase 4's report needs for one model family, from one
    identical 5-fold CV run."""

    name: str
    best_params: dict[str, Any]
    macro_f1_per_fold: list[float]
    per_class_recall: dict[str, float]
    confusion: list[list[int]]
    confusion_labels: list[str]
    calibration: dict[str, dict[str, list[float]]]
    fit_time_seconds: float
    library_version: str
    class_weight_strategy: str
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def macro_f1_mean(self) -> float:
        return float(np.mean(self.macro_f1_per_fold))

    @property
    def macro_f1_std(self) -> float:
        return float(np.std(self.macro_f1_per_fold))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "best_params": self.best_params,
            "macro_f1_per_fold": self.macro_f1_per_fold,
            "macro_f1_mean": self.macro_f1_mean,
            "macro_f1_std": self.macro_f1_std,
            "per_class_recall": self.per_class_recall,
            "confusion_matrix": self.confusion,
            "confusion_matrix_labels": self.confusion_labels,
            "calibration": self.calibration,
            "fit_time_seconds": self.fit_time_seconds,
            "library_version": self.library_version,
            "class_weight_strategy": self.class_weight_strategy,
            "extra": self.extra,
        }


def evaluate_out_of_fold(
    name: str,
    fitted_search_or_pipeline: Any,
    X: pd.DataFrame,
    y: pd.Series,
    cv: StratifiedKFold,
    best_params: dict[str, Any],
    fit_time_seconds: float,
    library_version: str,
    class_weight_strategy: str,
    macro_f1_per_fold: list[float],
    fit_params: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> ModelEvaluation:
    """Compute per-class recall, confusion matrix, and calibration from
    genuine out-of-fold predictions (cross_val_predict), which — like
    GridSearchCV — fits a fresh pipeline per fold on that fold's training
    data only, so these metrics are never computed on a model that has
    seen the row being predicted.

    Only `predict_proba` is requested from cross_val_predict (not also
    `predict`, which would silently double every fold's fit cost) —
    `y_pred` is derived as argmax(y_proba), which is exactly what every
    model family's own `.predict()` does internally for these standard
    softmax/probability classifiers (LogReg, RF, XGBoost, and the Keras
    MLP all predict the highest-probability class).
    """
    y_proba = cross_val_predict(
        fitted_search_or_pipeline, X, y, cv=cv, method="predict_proba", fit_params=fit_params
    )
    classes = list(fitted_search_or_pipeline.classes_) if hasattr(
        fitted_search_or_pipeline, "classes_"
    ) else GENUINE_RISK_LEVELS
    y_pred = np.array([classes[i] for i in y_proba.argmax(axis=1)])

    per_class_recall = dict(
        zip(
            GENUINE_RISK_LEVELS,
            recall_score(y, y_pred, labels=GENUINE_RISK_LEVELS, average=None, zero_division=0),
            strict=True,
        )
    )
    cm = confusion_matrix(y, y_pred, labels=GENUINE_RISK_LEVELS)

    calibration: dict[str, dict[str, list[float]]] = {}
    for cls in GENUINE_RISK_LEVELS:
        cls_idx = classes.index(cls)
        y_true_binary = (y == cls).astype(int)
        prob_true, prob_pred = calibration_curve(
            y_true_binary, y_proba[:, cls_idx], n_bins=10, strategy="quantile"
        )
        calibration[cls] = {"prob_true": prob_true.tolist(), "prob_pred": prob_pred.tolist()}

    return ModelEvaluation(
        name=name,
        best_params=best_params,
        macro_f1_per_fold=macro_f1_per_fold,
        per_class_recall={k: float(v) for k, v in per_class_recall.items()},
        confusion=cm.tolist(),
        confusion_labels=GENUINE_RISK_LEVELS,
        calibration=calibration,
        fit_time_seconds=fit_time_seconds,
        library_version=library_version,
        class_weight_strategy=class_weight_strategy,
        extra=extra or {},
    )


def library_versions() -> dict[str, str]:
    import tensorflow as tf

    return {
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "xgboost": xgboost.__version__,
        "tensorflow": tf.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }
