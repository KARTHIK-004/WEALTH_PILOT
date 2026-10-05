"""Artifact save/load round-trip tests — on fast synthetic data, structurally
identical to what train.py does for the real run, but never merely checking
that a file exists. Every test here actually reloads the saved artifact and
uses it to predict, proving the file is a working model, not just bytes.
"""

import json

import joblib
import numpy as np
import tensorflow as tf
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

from training.risk.common import build_pipeline
from training.risk.mlp import KerasMLPClassifier
from training.risk.xgboost_model import StringLabelXGBClassifier
from wealthpilot.data.preprocessing import ALL_FEATURES, build_preprocessing_pipeline


def test_preprocessor_and_sklearn_model_round_trip(tmp_path, synthetic_training_table):
    X, y = synthetic_training_table

    preprocessor = build_preprocessing_pipeline().fit(X)
    pipeline = build_pipeline(LogisticRegression(max_iter=200, class_weight="balanced"))
    pipeline.fit(X, y)
    classifier = pipeline.named_steps["classifier"]

    preprocessor_path = tmp_path / "preprocessor.pkl"
    model_path = tmp_path / "logreg.pkl"
    joblib.dump(preprocessor, preprocessor_path)
    joblib.dump(classifier, model_path)

    loaded_preprocessor = joblib.load(preprocessor_path)
    loaded_classifier = joblib.load(model_path)

    X_transformed = loaded_preprocessor.transform(X)
    predictions = loaded_classifier.predict(X_transformed)

    assert len(predictions) == len(X)
    assert set(predictions) <= set(y.unique())

    # The loaded artifacts must produce IDENTICAL predictions to the
    # original in-memory pipeline, not just "some" predictions.
    original_predictions = pipeline.predict(X)
    assert list(predictions) == list(original_predictions)


def test_random_forest_round_trip(tmp_path, synthetic_training_table):
    X, y = synthetic_training_table
    preprocessor = build_preprocessing_pipeline().fit(X)
    pipeline = build_pipeline(RandomForestClassifier(n_estimators=20, class_weight="balanced", random_state=42))
    pipeline.fit(X, y)

    model_path = tmp_path / "rf.pkl"
    joblib.dump(pipeline.named_steps["classifier"], model_path)
    loaded = joblib.load(model_path)

    X_t = preprocessor.transform(X)
    assert list(loaded.predict(X_t)) == list(pipeline.named_steps["classifier"].predict(X_t))


def test_xgboost_wrapper_round_trip(tmp_path, synthetic_training_table):
    X, y = synthetic_training_table
    preprocessor = build_preprocessing_pipeline().fit(X)
    pipeline = build_pipeline(StringLabelXGBClassifier(n_estimators=20, random_state=42))
    pipeline.fit(X, y)

    model_path = tmp_path / "xgb.pkl"
    joblib.dump(pipeline.named_steps["classifier"], model_path)
    loaded = joblib.load(model_path)

    X_t = preprocessor.transform(X)
    predictions = loaded.predict(X_t)
    assert set(predictions) <= set(y.unique())
    assert list(predictions) == list(pipeline.named_steps["classifier"].predict(X_t))


def test_mlp_keras_native_save_round_trip(tmp_path, synthetic_training_table):
    X, y = synthetic_training_table
    preprocessor = build_preprocessing_pipeline().fit(X)
    pipeline = build_pipeline(
        KerasMLPClassifier(units1=8, units2=4, epochs=3, batch_size=32, patience=2, random_state=42)
    )
    pipeline.fit(X, y)
    classifier = pipeline.named_steps["classifier"]

    model_path = tmp_path / "mlp.keras"
    classes_path = tmp_path / "mlp_classes.json"
    classifier._model.save(model_path)
    classes_path.write_text(json.dumps(list(classifier.classes_)), encoding="utf-8")

    loaded_model = tf.keras.models.load_model(model_path)
    loaded_classes = json.loads(classes_path.read_text(encoding="utf-8"))

    X_t = preprocessor.transform(X)
    X_t = np.asarray(X_t, dtype="float32")
    proba = loaded_model.predict(X_t, verbose=0)
    predictions = [loaded_classes[i] for i in proba.argmax(axis=1)]

    assert len(predictions) == len(X)
    assert set(predictions) <= set(y.unique())
    # Loaded model's raw probability output must match the original.
    original_proba = classifier.predict_proba(X_t)
    np.testing.assert_allclose(proba, original_proba, atol=1e-5)
