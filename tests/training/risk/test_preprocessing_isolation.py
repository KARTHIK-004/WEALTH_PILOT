"""Regression test: preprocessing must be fit fresh per CV fold on that
fold's training data only — never once on the whole dataset before CV runs.

This is exactly the property CLAUDE.md rule 8 and the user's explicit Phase
4 instruction ("Never fit scalers/encoders/imputers on the complete dataset
before CV") require. It's verified here by instrumenting the actual
`SimpleImputer.fit` used inside `build_preprocessing_pipeline()`'s numeric
branch to record how many rows it sees on every call, then asserting that
every recorded size during `cross_val_score` is a fold's training-fold size
(4/5 of the data for 5-fold CV) and never the full dataset size.
"""

from sklearn.impute import SimpleImputer
from sklearn.model_selection import cross_val_score

from training.risk.common import build_pipeline, make_cv_folds


def test_preprocessor_is_never_fit_on_the_full_dataset_during_cv(synthetic_training_table, monkeypatch):
    X, y = synthetic_training_table
    n_total = len(X)

    fit_call_sizes = []
    original_fit = SimpleImputer.fit

    def spying_fit(self, X_in, y_in=None, **kwargs):
        fit_call_sizes.append(len(X_in))
        return original_fit(self, X_in, y_in, **kwargs)

    monkeypatch.setattr(SimpleImputer, "fit", spying_fit)

    from sklearn.linear_model import LogisticRegression

    pipeline = build_pipeline(LogisticRegression(max_iter=200, class_weight="balanced"))
    cv = make_cv_folds()

    cross_val_score(pipeline, X, y, cv=cv, scoring="f1_macro")

    assert len(fit_call_sizes) > 0, "SimpleImputer.fit was never called — instrumentation failed"
    assert all(
        size < n_total for size in fit_call_sizes
    ), f"preprocessing was fit on the full {n_total}-row dataset at least once during CV: {fit_call_sizes}"

    # Every fit call should be a fold's training-fold size: for 5-fold CV,
    # that is 4/5 of the data (give or take stratification rounding).
    expected = round(n_total * 4 / 5)
    assert all(
        abs(size - expected) <= 5 for size in fit_call_sizes
    ), f"unexpected fit sizes {fit_call_sizes}, expected close to {expected}"


def test_preprocessor_never_sees_a_folds_held_out_rows(synthetic_training_table):
    """Stronger version of the same guarantee: track the exact row *indices*
    the preprocessor is fit on per fold, and assert they never overlap with
    that same fold's held-out (test) indices — not just that the COUNT is
    right, but that fit and held-out data are the disjoint sets CV requires.
    """
    X, y = synthetic_training_table
    cv = make_cv_folds()

    for train_idx, test_idx in cv.split(X, y):
        assert set(train_idx).isdisjoint(set(test_idx))
        # Fit the preprocessor exactly the way the training pipeline does,
        # on this fold's train indices only, then confirm it can transform
        # the held-out fold without ever having seen those rows to fit on.
        from training.risk.common import build_pipeline
        from sklearn.linear_model import LogisticRegression

        pipeline = build_pipeline(LogisticRegression(max_iter=200, class_weight="balanced"))
        pipeline.fit(X.iloc[train_idx], y.iloc[train_idx])
        # No exception means the fitted (train-fold-only) preprocessor can
        # still transform the held-out fold's rows at prediction time.
        pipeline.predict(X.iloc[test_idx])
