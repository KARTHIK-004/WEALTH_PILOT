"""Phase 4 orchestrator: trains and evaluates all four risk-classification
model families on identical data and identical CV folds, selects the best
by macro-F1 (never accuracy), serializes all four (not just the winner —
PROJECT_PLAN.md section 6.1: "the report needs them, and a reviewer may ask
to see the loser's confusion matrix"), runs SHAP on the winner, and writes
models/metrics.json + a Phase 4 evaluation report.

Run with:  python -m training.risk.train
Offline only — never imported by the FastAPI app (CLAUDE.md rule 5).
"""

from __future__ import annotations

import json
import platform
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf

from training.risk import logistic_regression, mlp, random_forest, xgboost_model
from training.risk.common import (
    GENUINE_RISK_LEVELS,
    MODELS_DIR,
    METRICS_PATH,
    N_SPLITS,
    RANDOM_STATE,
    REPORTS_DIR,
    library_versions,
    load_training_table,
)
from training.risk.explain import compute_shap
from wealthpilot.data.preprocessing import ALL_FEATURES, build_preprocessing_pipeline

MODEL_VERSION = "v1"

TRAINERS = {
    "logistic_regression": logistic_regression.train_and_evaluate,
    "random_forest": random_forest.train_and_evaluate,
    "xgboost": xgboost_model.train_and_evaluate,
    "mlp": mlp.train_and_evaluate,
}

ARTIFACT_FILENAMES = {
    "logistic_regression": f"logreg_{MODEL_VERSION}.pkl",
    "random_forest": f"rf_{MODEL_VERSION}.pkl",
    "xgboost": f"xgb_{MODEL_VERSION}.pkl",
    "mlp": f"mlp_{MODEL_VERSION}.keras",
}


def run_all(X: pd.DataFrame, y: pd.Series) -> dict[str, tuple]:
    results = {}
    for name, trainer in TRAINERS.items():
        print(f"=== training {name} ===", flush=True)
        t0 = time.time()
        evaluation, estimator = trainer(X, y)
        print(f"=== {name} done in {time.time() - t0:.1f}s, macro_f1_mean={evaluation.macro_f1_mean:.4f} ===", flush=True)
        results[name] = (evaluation, estimator)
    return results


def select_best(results: dict[str, tuple]) -> str:
    """Best by mean macro-F1 across the shared 5 folds — never accuracy."""
    return max(results, key=lambda name: results[name][0].macro_f1_mean)


def save_artifacts(results: dict[str, tuple], X: pd.DataFrame) -> dict[str, str]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}

    # One canonical, shared preprocessor. Every model's own pipeline fit an
    # equivalent preprocessor on the same full X (deterministic transforms —
    # SimpleImputer/StandardScaler/OneHotEncoder have no randomness), so
    # fitting one fresh instance here for the shared artifact is exact, not
    # an approximation, and avoids saving four redundant near-duplicates.
    preprocessor = build_preprocessing_pipeline().fit(X)
    preprocessor_path = MODELS_DIR / f"preprocessor_{MODEL_VERSION}.pkl"
    joblib.dump(preprocessor, preprocessor_path)
    saved["preprocessor"] = str(preprocessor_path.relative_to(MODELS_DIR.parents[1]))

    for name, (_evaluation, estimator) in results.items():
        classifier = estimator.named_steps["classifier"]
        filename = ARTIFACT_FILENAMES[name]
        path = MODELS_DIR / filename
        if name == "mlp":
            classifier._model.save(path)
            classes_path = MODELS_DIR / f"mlp_classes_{MODEL_VERSION}.json"
            classes_path.write_text(json.dumps(list(classifier.classes_)), encoding="utf-8")
            saved["mlp_classes"] = str(classes_path.relative_to(MODELS_DIR.parents[1]))
        else:
            joblib.dump(classifier, path)
        saved[name] = str(path.relative_to(MODELS_DIR.parents[1]))

    return saved


def write_metrics_json(
    results: dict[str, tuple],
    best_name: str,
    shap_result: dict,
    saved_paths: dict[str, str],
    training_population: int,
) -> None:
    payload = {
        "risk": {
            "model_version": MODEL_VERSION,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "dataset_source": "FAR-Trans customer_information.csv + transactions.csv + "
            "asset_information.csv + close_prices.csv (datasets/raw/FAR-Trans/)",
            "training_population": training_population,
            "random_state": RANDOM_STATE,
            "cv_folds": N_SPLITS,
            "library_versions": library_versions(),
            "features": ALL_FEATURES,
            "genuine_labels_only": GENUINE_RISK_LEVELS,
            "best_model": best_name,
            "artifacts": saved_paths,
            "shap": shap_result,
            "models": {name: evaluation.to_dict() for name, (evaluation, _est) in results.items()},
        }
    }

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if METRICS_PATH.exists():
        existing = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    existing.update(payload)
    METRICS_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def write_report(results: dict[str, tuple], best_name: str, shap_result: dict, training_population: int) -> None:
    lines = [
        "# Phase 4 — Risk Classification Evaluation Report",
        "",
        f"Trained {datetime.now(timezone.utc).isoformat()}. Dataset: FAR-Trans "
        f"(`datasets/raw/FAR-Trans/`), leakage-safe feature table from Phase 3 "
        f"(`backend/wealthpilot/data/preprocessing.py`). Training population: "
        f"{training_population} customers with a genuine risk label "
        f"(Conservative/Income/Balanced/Aggressive) — Predicted_*/Not_Available excluded.",
        "",
        "## Model comparison (identical stratified 5-fold CV, random_state=42)",
        "",
        "| Model | Macro-F1 (mean ± std) | Fit time (s) | Class-imbalance strategy |",
        "|---|---|---|---|",
    ]
    for name, (ev, _est) in results.items():
        marker = " **(best)**" if name == best_name else ""
        lines.append(
            f"| {name}{marker} | {ev.macro_f1_mean:.4f} ± {ev.macro_f1_std:.4f} | "
            f"{ev.fit_time_seconds:.1f} | {ev.class_weight_strategy} |"
        )
    lines.append("")

    for name, (ev, _est) in results.items():
        lines.append(f"### {name}")
        lines.append("")
        lines.append(f"- Best params: `{ev.best_params}`")
        lines.append(f"- Per-class recall: {ev.per_class_recall}")
        lines.append(f"- Confusion matrix (rows=true, cols=predicted, labels={ev.confusion_labels}):")
        for row in ev.confusion:
            lines.append(f"  - {row}")
        if ev.extra:
            lines.append(f"- Extra: {ev.extra}")
        lines.append("")

    lines.append(f"## Selected best model: {best_name}")
    lines.append("")
    lines.append(
        "Selected by highest mean macro-F1 across the shared 5 folds — not accuracy "
        "(PROJECT_PLAN.md section 2.1: class distribution skews toward intermediate "
        "profiles, so accuracy alone would favor a model that never predicts a minority class)."
    )
    lines.append("")
    lines.append("## SHAP explainability")
    lines.append("")
    lines.append(f"Method: {shap_result['method']}. Sample size: {shap_result['sample_size']}.")
    lines.append("")
    lines.append("Top 10 features by mean |SHAP value| (averaged across classes):")
    for entry in shap_result["overall_feature_ranking"][:10]:
        lines.append(f"- {entry['feature']}: {entry['mean_abs_shap']:.4f}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "phase4_risk_classification_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    X, y = load_training_table()
    print(f"training population: {len(X)}", flush=True)

    results = run_all(X, y)
    best_name = select_best(results)
    print(f"best model: {best_name}", flush=True)

    saved_paths = save_artifacts(results, X)

    best_estimator = results[best_name][1]
    feature_names = list(
        build_preprocessing_pipeline().fit(X).get_feature_names_out()
    )
    shap_result = compute_shap(best_name, best_estimator, X, feature_names, random_state=RANDOM_STATE)

    write_metrics_json(results, best_name, shap_result, saved_paths, len(X))
    write_report(results, best_name, shap_result, len(X))
    print("done", flush=True)


if __name__ == "__main__":
    main()
