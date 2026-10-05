"""SHAP explainability for the selected best risk model.

`shap.TreeExplainer` is used when the best model is tree-based (Random
Forest or XGBoost) — PROJECT_PLAN.md section 2.1's stated reason SHAP was
chosen as the risk model's explainability tool in the first place: it
computes *exact* Shapley values for tree models in polynomial time, unlike
a neural net or a linear model, which need a sampling-based approximation.

If the selected best model is not tree-based (Logistic Regression or the
MLP), `shap.KernelExplainer` is used instead — model-agnostic but not exact,
so it runs on a bounded background/sample size rather than the full
21,528-row table, and this is documented in the output rather than
presented as if it were the same kind of computation as TreeExplainer's.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shap

SHAP_SAMPLE_SIZE = 1000
KERNEL_BACKGROUND_SIZE = 50


def compute_shap(
    model_name: str,
    fitted_pipeline: Any,
    X: pd.DataFrame,
    feature_names: list[str],
    random_state: int = 42,
) -> dict[str, Any]:
    preprocessor = fitted_pipeline.named_steps["preprocess"]
    classifier = fitted_pipeline.named_steps["classifier"]

    rng = np.random.default_rng(random_state)
    sample_idx = rng.choice(len(X), size=min(SHAP_SAMPLE_SIZE, len(X)), replace=False)
    X_sample = X.iloc[sample_idx]
    X_transformed = preprocessor.transform(X_sample)
    if hasattr(X_transformed, "toarray"):
        X_transformed = X_transformed.toarray()

    if model_name == "random_forest":
        explainer = shap.TreeExplainer(classifier)
        shap_values = explainer.shap_values(X_transformed)
        method = "TreeExplainer (exact)"
    elif model_name == "xgboost":
        explainer = shap.TreeExplainer(classifier._model)
        shap_values = explainer.shap_values(X_transformed)
        method = "TreeExplainer (exact)"
    else:
        background_idx = rng.choice(len(X_transformed), size=min(KERNEL_BACKGROUND_SIZE, len(X_transformed)), replace=False)
        background = X_transformed[background_idx]
        kernel_sample_idx = rng.choice(len(X_transformed), size=min(200, len(X_transformed)), replace=False)
        kernel_sample = X_transformed[kernel_sample_idx]
        explainer = shap.KernelExplainer(classifier.predict_proba, background)
        shap_values = explainer.shap_values(kernel_sample, nsamples=100)
        method = f"KernelExplainer (approximate, {KERNEL_BACKGROUND_SIZE}-row background, 200-row sample) — {model_name} is not tree-based"

    # shap_values is either a list-of-arrays (one per class) or a single
    # 3D array (n_samples, n_features, n_classes) depending on shap/model
    # version; normalize to a per-class mean-|SHAP| feature ranking either way.
    if isinstance(shap_values, list):
        per_class_mean_abs = [np.abs(sv).mean(axis=0) for sv in shap_values]
    elif shap_values.ndim == 3:
        per_class_mean_abs = [np.abs(shap_values[:, :, c]).mean(axis=0) for c in range(shap_values.shape[2])]
    else:
        per_class_mean_abs = [np.abs(shap_values).mean(axis=0)]

    classes = list(getattr(classifier, "classes_", range(len(per_class_mean_abs))))
    overall_importance = np.mean(per_class_mean_abs, axis=0)
    ranking = sorted(zip(feature_names, overall_importance, strict=True), key=lambda t: -t[1])

    return {
        "method": method,
        "sample_size": int(len(X_sample)),
        "per_class_mean_abs_shap": {
            str(cls): {name: float(val) for name, val in zip(feature_names, per_class_mean_abs[i], strict=True)}
            for i, cls in enumerate(classes)
        },
        "overall_feature_ranking": [{"feature": name, "mean_abs_shap": float(val)} for name, val in ranking],
    }
