"""random_state=42 must make training reproducible: the same data run
through the same training function twice must give identical CV scores and
identical predictions, not just "close" ones."""

import numpy as np

from training.risk.logistic_regression import train_and_evaluate as train_logreg
from training.risk.random_forest import train_and_evaluate as train_rf


def test_logistic_regression_is_deterministic(synthetic_training_table):
    X, y = synthetic_training_table
    evaluation_1, estimator_1 = train_logreg(X, y)
    evaluation_2, estimator_2 = train_logreg(X, y)

    assert evaluation_1.macro_f1_per_fold == evaluation_2.macro_f1_per_fold
    assert evaluation_1.best_params == evaluation_2.best_params
    assert list(estimator_1.predict(X)) == list(estimator_2.predict(X))


def test_random_forest_is_deterministic(synthetic_training_table):
    X, y = synthetic_training_table
    evaluation_1, estimator_1 = train_rf(X, y)
    evaluation_2, estimator_2 = train_rf(X, y)

    assert evaluation_1.macro_f1_per_fold == evaluation_2.macro_f1_per_fold
    assert evaluation_1.best_params == evaluation_2.best_params
    # atol=1e-9, not exact equality: RandomForestClassifier's n_jobs=-1
    # parallelizes tree aggregation, and floating-point summation order can
    # differ by ~1e-16 between runs (machine-epsilon noise, not a real
    # nondeterminism in which trees are grown or what they predict).
    np.testing.assert_allclose(
        estimator_1.predict_proba(X), estimator_2.predict_proba(X), atol=1e-9
    )
    assert list(estimator_1.predict(X)) == list(estimator_2.predict(X))
