"""TensorFlow MLP — included to show it was tested; PROJECT_PLAN.md section
2.1 expects it to underperform the tree models at this sample size
(Grinsztajn, Oyallon & Varoquaux, NeurIPS 2022) — "the result is the point."

Architecture fixed at 2 hidden layers (PROJECT_PLAN.md section 6.1: "2
hidden layers, units, dropout, early stopping on val macro-F1"), not
grid-searched — PROJECT_PLAN.md only requires GridSearchCV/RandomizedSearchCV
"for the tree models" (Random Forest, XGBoost), not for MLP. Early stopping
is implemented against macro-F1 on an internal validation split carved out
of each fold's own training data (never the fold's held-out validation
rows), via a custom Keras callback — not val_loss, which is what
`EarlyStopping` monitors by default and is not what PROJECT_PLAN asks for.
Class imbalance handled via Keras' native per-sample `sample_weight`.
"""

from __future__ import annotations

import time

import numpy as np
import tensorflow as tf
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.metrics import f1_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder

from training.risk.common import (
    RANDOM_STATE,
    ModelEvaluation,
    balanced_sample_weight,
    build_pipeline,
    evaluate_out_of_fold,
    library_versions,
    make_cv_folds,
)


class _MacroF1EarlyStopping(tf.keras.callbacks.Callback):
    """Stops training when macro-F1 on an internal validation split stops
    improving, and restores the weights from the best epoch — PROJECT_PLAN's
    "early stopping on val macro-F1", which Keras has no built-in metric
    for (F1 is not decomposable per-batch the way accuracy/loss are)."""

    def __init__(self, X_val: np.ndarray, y_val_int: np.ndarray, patience: int = 10):
        super().__init__()
        self.X_val = X_val
        self.y_val_int = y_val_int
        self.patience = patience
        self.best_f1 = -1.0
        self.best_weights = None
        self.wait = 0
        self.history: list[float] = []

    def on_epoch_end(self, epoch, logs=None):
        proba = self.model.predict(self.X_val, verbose=0)
        preds = proba.argmax(axis=1)
        f1 = f1_score(self.y_val_int, preds, average="macro", zero_division=0)
        self.history.append(float(f1))
        if f1 > self.best_f1:
            self.best_f1 = f1
            self.wait = 0
            self.best_weights = self.model.get_weights()
        else:
            self.wait += 1
            if self.wait >= self.patience:
                self.model.stop_training = True

    def on_train_end(self, logs=None):
        if self.best_weights is not None:
            self.model.set_weights(self.best_weights)


class KerasMLPClassifier(BaseEstimator, ClassifierMixin):
    """2-hidden-layer Keras MLP, sklearn-compatible (fit/predict/predict_proba
    + get_params/set_params via BaseEstimator), so it slots into the same
    Pipeline/cross_val_predict machinery as the other three model families.
    """

    def __init__(
        self,
        units1: int = 64,
        units2: int = 32,
        dropout: float = 0.3,
        epochs: int = 100,
        batch_size: int = 64,
        patience: int = 10,
        val_fraction: float = 0.15,
        random_state: int = RANDOM_STATE,
    ):
        self.units1 = units1
        self.units2 = units2
        self.dropout = dropout
        self.epochs = epochs
        self.batch_size = batch_size
        self.patience = patience
        self.val_fraction = val_fraction
        self.random_state = random_state

    def fit(self, X, y, sample_weight=None):
        X = np.asarray(X, dtype="float32")
        self._label_encoder = LabelEncoder().fit(y)
        y_int = self._label_encoder.transform(y)
        self.classes_ = self._label_encoder.classes_
        n_classes = len(self.classes_)

        if sample_weight is None:
            sample_weight = np.ones(len(y_int), dtype="float32")

        tf.keras.utils.set_random_seed(self.random_state)

        X_train, X_val, y_train, y_val, w_train, _w_val = train_test_split(
            X, y_int, sample_weight,
            test_size=self.val_fraction, stratify=y_int, random_state=self.random_state,
        )

        model = tf.keras.Sequential(
            [
                tf.keras.layers.Input(shape=(X.shape[1],)),
                tf.keras.layers.Dense(self.units1, activation="relu"),
                tf.keras.layers.Dropout(self.dropout),
                tf.keras.layers.Dense(self.units2, activation="relu"),
                tf.keras.layers.Dropout(self.dropout),
                tf.keras.layers.Dense(n_classes, activation="softmax"),
            ]
        )
        model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])

        callback = _MacroF1EarlyStopping(X_val, y_val, patience=self.patience)
        model.fit(
            X_train,
            y_train,
            sample_weight=w_train,
            validation_data=(X_val, y_val),
            epochs=self.epochs,
            batch_size=self.batch_size,
            callbacks=[callback],
            verbose=0,
        )
        self._model = model
        self.val_f1_history_ = callback.history
        self.stopped_epoch_ = len(callback.history)
        return self

    def predict(self, X):
        proba = self.predict_proba(X)
        return self._label_encoder.inverse_transform(proba.argmax(axis=1))

    def predict_proba(self, X):
        X = np.asarray(X, dtype="float32")
        return self._model.predict(X, verbose=0)


def train_and_evaluate(X, y) -> tuple[ModelEvaluation, object]:
    cv = make_cv_folds()
    pipeline = build_pipeline(KerasMLPClassifier(random_state=RANDOM_STATE))
    fixed_params = {
        "units1": 64,
        "units2": 32,
        "dropout": 0.3,
        "epochs": 100,
        "batch_size": 64,
        "patience": 10,
    }
    sample_weight = balanced_sample_weight(y)
    fit_params = {"classifier__sample_weight": sample_weight}

    t0 = time.time()
    per_fold_scores = cross_val_score(
        pipeline, X, y, cv=cv, scoring="f1_macro", fit_params=fit_params
    )
    # Refit once more on the full training population for the final artifact
    # (the fit inside cross_val_score is per-fold and discarded).
    pipeline.fit(X, y, classifier__sample_weight=sample_weight)
    fit_time = time.time() - t0

    evaluation = evaluate_out_of_fold(
        name="mlp",
        fitted_search_or_pipeline=pipeline,
        X=X,
        y=y,
        cv=cv,
        best_params={f"classifier__{k}": v for k, v in fixed_params.items()},
        fit_time_seconds=fit_time,
        library_version=library_versions()["tensorflow"],
        class_weight_strategy="sample_weight=compute_sample_weight('balanced', y)",
        macro_f1_per_fold=[float(s) for s in per_fold_scores],
        fit_params=fit_params,
        extra={"stopped_epoch": pipeline.named_steps["classifier"].stopped_epoch_},
    )
    return evaluation, pipeline
