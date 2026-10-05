"""Phase 5 expense-segmentation orchestrator.

Clusters the Kaggle primary dataset's own population (see common.py's
module docstring for why — FAR-Trans has no income/expense data, and no
synthetic FAR-Trans<->Kaggle linkage is created here). Runs the full
K-Means / GMM / Ward sweep, selects a final method by documented evidence,
profiles the resulting clusters with actual computed statistics, and
serializes the scaler + chosen model.

Run with: python -m training.expense.train
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from training.expense.clustering import (
    K_RANGE,
    best_gmm_config,
    best_kmeans_k,
    best_ward_k,
    sweep_gmm,
    sweep_kmeans,
    sweep_ward,
)
from training.expense.common import (
    FEATURE_COLUMNS,
    MODELS_DIR,
    METRICS_PATH,
    RANDOM_STATE,
    REPORTS_DIR,
    engineer_expense_features,
    library_versions,
    load_kaggle_primary,
)

MODEL_VERSION = "v1"


def profile_clusters(features, labels) -> dict:
    profiled = features.copy()
    profiled["cluster"] = labels
    sizes = profiled["cluster"].value_counts().sort_index()
    means = profiled.groupby("cluster")[FEATURE_COLUMNS].mean()
    medians = profiled.groupby("cluster")[FEATURE_COLUMNS].median()

    profiles = {}
    for cluster_id in sizes.index:
        m = means.loc[cluster_id]
        # Persona label derived from the ACTUAL measured cluster means,
        # relative to the population median for each feature — not decided
        # in advance. "high"/"low" = above/below the population median.
        pop_median = features[FEATURE_COLUMNS].median()
        descriptors = []
        if m["expense_to_income_ratio"] > pop_median["expense_to_income_ratio"]:
            descriptors.append("high-expense")
        else:
            descriptors.append("low-expense")
        if m["emi_to_income_ratio"] > pop_median["emi_to_income_ratio"]:
            descriptors.append("high-leverage")
        else:
            descriptors.append("low-leverage")
        if m["savings_to_income_ratio"] > pop_median["savings_to_income_ratio"]:
            descriptors.append("higher-savings")
        else:
            descriptors.append("lower-savings")

        profiles[str(cluster_id)] = {
            "size": int(sizes.loc[cluster_id]),
            "share_of_population": float(sizes.loc[cluster_id] / len(profiled)),
            "mean": {k: float(v) for k, v in m.items()},
            "median": {k: float(v) for k, v in medians.loc[cluster_id].items()},
            "descriptive_label": "-".join(descriptors),
        }
    return profiles


def main() -> None:
    t_start = time.time()
    raw = load_kaggle_primary()
    features, excluded_rows = engineer_expense_features(raw)
    print(f"population: {len(features)} (excluded {excluded_rows} non-positive-income rows)", flush=True)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    print("running K-Means sweep...", flush=True)
    t0 = time.time()
    kmeans_results = sweep_kmeans(X_scaled)
    kmeans_time = time.time() - t0
    kmeans_k = best_kmeans_k(kmeans_results)
    print(f"K-Means done in {kmeans_time:.1f}s, best k={kmeans_k}", flush=True)

    print("running GMM sweep...", flush=True)
    t0 = time.time()
    gmm_results = sweep_gmm(X_scaled)
    gmm_time = time.time() - t0
    gmm_k, gmm_cov = best_gmm_config(gmm_results)
    print(f"GMM done in {gmm_time:.1f}s, best k={gmm_k}, covariance_type={gmm_cov}", flush=True)

    print("running Ward sweep (5000-row subsample)...", flush=True)
    t0 = time.time()
    ward_results, ward_idx = sweep_ward(X_scaled)
    ward_time = time.time() - t0
    ward_k = best_ward_k(ward_results)
    print(f"Ward done in {ward_time:.1f}s, best k={ward_k}", flush=True)

    # Final method selection by evidence: compare silhouette at each
    # method's own best k. K-Means and Ward are directly comparable (both
    # silhouette-selected); GMM's BIC-selected k is reported for comparison
    # but silhouette at that k is also computed for a fair three-way look.
    kmeans_best = next(r for r in kmeans_results if r["k"] == kmeans_k)
    ward_best = next(r for r in ward_results if r["k"] == ward_k)
    gmm_best = next(r for r in gmm_results if r["k"] == gmm_k and r["covariance_type"] == gmm_cov)

    candidates = {
        "kmeans": kmeans_best["silhouette"],
        "ward": ward_best["silhouette"],
        "gmm": gmm_best["silhouette"] if not np.isnan(gmm_best["silhouette"]) else -1.0,
    }
    selected_method = max(candidates, key=candidates.get)
    print(f"selected method: {selected_method} (silhouette comparison: {candidates})", flush=True)

    # Fit and serialize the FINAL chosen model on the full population.
    if selected_method == "kmeans":
        final_model = KMeans(n_clusters=kmeans_k, random_state=RANDOM_STATE, n_init=10)
        labels = final_model.fit_predict(X_scaled)
        selected_k = kmeans_k
    elif selected_method == "ward":
        # Ward has no out-of-sample predict; refit on the FULL population
        # for the final artifact (subsampling was only for the k-selection
        # sweep, per PROJECT_PLAN.md's noted scaling limitation) is not
        # feasible at 32k rows for agglomerative clustering, so the final
        # Ward artifact is fit on the same subsample used for selection,
        # documented explicitly rather than silently extrapolated.
        final_model = AgglomerativeClustering(n_clusters=ward_k, linkage="ward")
        labels_sub = final_model.fit_predict(X_scaled[ward_idx])
        labels = np.full(len(X_scaled), -1)
        labels[ward_idx] = labels_sub
        selected_k = ward_k
    else:
        final_model = GaussianMixture(n_components=gmm_k, covariance_type=gmm_cov, random_state=RANDOM_STATE)
        final_model.fit(X_scaled)
        labels = final_model.predict(X_scaled)
        selected_k = gmm_k

    valid_mask = labels >= 0
    cluster_profiles = profile_clusters(features[valid_mask], labels[valid_mask])

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    scaler_path = MODELS_DIR / f"scaler_{MODEL_VERSION}.pkl"
    model_path = MODELS_DIR / f"{selected_method}_{MODEL_VERSION}.pkl"
    joblib.dump(scaler, scaler_path)
    joblib.dump(final_model, model_path)

    metrics_payload = {
        "expense": {
            "model_version": MODEL_VERSION,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "dataset_source": "Kaggle primary (miadul/personal-finance-ml-dataset) — "
            "datasets/raw/kaggle/synthetic_personal_finance_dataset.csv. Characterizes "
            "the Kaggle population only; NOT linked to any FAR-Trans customer "
            "(synthetic assembly remains deferred).",
            "population": int(len(features)),
            "excluded_non_positive_income_rows": excluded_rows,
            "random_state": RANDOM_STATE,
            "library_versions": library_versions(),
            "features": FEATURE_COLUMNS,
            "feature_note": "emi_to_income_ratio is log1p-transformed — see training/expense/common.py "
            "docstring for the investigation that led to this (raw ratio produced a "
            "587-row outlier-vs-rest split at k=2, not a genuine persona split).",
            "k_range_evaluated": K_RANGE,
            "kmeans": {"sweep": kmeans_results, "best_k": kmeans_k, "fit_time_seconds": kmeans_time},
            "gmm": {
                "sweep": gmm_results,
                "best_k": gmm_k,
                "best_covariance_type": gmm_cov,
                "fit_time_seconds": gmm_time,
            },
            "ward": {
                "sweep": ward_results,
                "best_k": ward_k,
                "fit_time_seconds": ward_time,
                "subsample_size": len(ward_idx),
                "note": "Ward evaluated (selection AND final artifact) on a "
                "random 5,000-row subsample — PROJECT_PLAN.md section 2.2 notes "
                "Ward is slow above ~10k rows.",
            },
            "selection_method": "silhouette comparison across each method's own best-k configuration",
            "selected_method": selected_method,
            "selected_k": selected_k,
            "cluster_profiles": cluster_profiles,
            "artifacts": {
                "scaler": str(scaler_path.relative_to(MODELS_DIR.parents[1])),
                "model": str(model_path.relative_to(MODELS_DIR.parents[1])),
            },
            "total_time_seconds": time.time() - t_start,
        }
    }

    existing = json.loads(METRICS_PATH.read_text(encoding="utf-8")) if METRICS_PATH.exists() else {}
    existing.update(metrics_payload)
    METRICS_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase 5 — Expense Segmentation Report",
        "",
        f"Population: {len(features)} Kaggle users (primary dataset). "
        "Characterizes the Kaggle population only — no FAR-Trans linkage.",
        "",
        "## Method comparison (silhouette at each method's own best k)",
        "",
        "| Method | Best k | Silhouette | Notes |",
        "|---|---|---|---|",
        f"| K-Means | {kmeans_k} | {kmeans_best['silhouette']:.4f} | full population |",
        f"| Ward | {ward_k} | {ward_best['silhouette']:.4f} | 5,000-row subsample |",
        f"| GMM | {gmm_k} (cov={gmm_cov}) | {gmm_best['silhouette']:.4f} | selected by BIC, not silhouette |",
        "",
        f"**Selected: {selected_method}, k={selected_k}**",
        "",
        "## Cluster profiles (actual computed statistics)",
        "",
    ]
    for cid, prof in cluster_profiles.items():
        lines.append(f"### Cluster {cid} — {prof['descriptive_label']}")
        lines.append(f"- Size: {prof['size']} ({prof['share_of_population']:.1%} of population)")
        lines.append(f"- Mean: {prof['mean']}")
        lines.append("")
    (REPORTS_DIR / "phase5_expense_segmentation_report.md").write_text("\n".join(lines), encoding="utf-8")

    print("done", flush=True)


if __name__ == "__main__":
    main()
