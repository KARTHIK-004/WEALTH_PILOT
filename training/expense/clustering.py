"""K-Means, Gaussian Mixture, and Ward Hierarchical clustering sweeps for
expense segmentation, per PROJECT_PLAN.md section 6.2:

- K-Means: k in 2..10, selected by silhouette (elbow/inertia as supporting
  evidence)
- Gaussian Mixture: k in 2..10 x covariance_type in
  {full, tied, diag, spherical}, selected by BIC
- Ward Hierarchical: k in 2..10, selected by silhouette

Ward is evaluated on a random 5,000-row subsample of the ~32k-row
population, not the full set — PROJECT_PLAN.md section 2.2 itself notes
Ward is "slow above ~10k rows" (classic agglomerative clustering is
O(n^2)-O(n^3)); this is a documented accommodation of that known limitation,
not an arbitrary shortcut, and is called out wherever Ward's results are
reported.

All three run on the SAME standardized feature matrix (StandardScaler fit
on the full population) so their silhouette/Davies-Bouldin scores are
directly comparable when selecting the final method.
"""

from __future__ import annotations

import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture

from training.expense.common import RANDOM_STATE

K_RANGE = list(range(2, 11))
GMM_COVARIANCE_TYPES = ["full", "tied", "diag", "spherical"]
WARD_SUBSAMPLE_SIZE = 5000


def sweep_kmeans(X_scaled: np.ndarray) -> list[dict]:
    results = []
    for k in K_RANGE:
        model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = model.fit_predict(X_scaled)
        results.append(
            {
                "k": k,
                "silhouette": float(silhouette_score(X_scaled, labels)),
                "davies_bouldin": float(davies_bouldin_score(X_scaled, labels)),
                "inertia": float(model.inertia_),
            }
        )
    return results


def sweep_gmm(X_scaled: np.ndarray) -> list[dict]:
    results = []
    for k in K_RANGE:
        for cov_type in GMM_COVARIANCE_TYPES:
            model = GaussianMixture(n_components=k, covariance_type=cov_type, random_state=RANDOM_STATE)
            model.fit(X_scaled)
            labels = model.predict(X_scaled)
            n_unique = len(set(labels))
            sil = float(silhouette_score(X_scaled, labels)) if n_unique > 1 else float("nan")
            results.append(
                {
                    "k": k,
                    "covariance_type": cov_type,
                    "bic": float(model.bic(X_scaled)),
                    "silhouette": sil,
                }
            )
    return results


def sweep_ward(X_scaled: np.ndarray) -> tuple[list[dict], np.ndarray]:
    """Returns (results, subsample_indices) — the subsample indices are
    needed by callers that want to profile Ward's clusters against the
    original (unscaled) data for the same rows."""
    rng = np.random.default_rng(RANDOM_STATE)
    n = len(X_scaled)
    if n > WARD_SUBSAMPLE_SIZE:
        idx = rng.choice(n, size=WARD_SUBSAMPLE_SIZE, replace=False)
    else:
        idx = np.arange(n)
    X_sub = X_scaled[idx]

    results = []
    for k in K_RANGE:
        model = AgglomerativeClustering(n_clusters=k, linkage="ward")
        labels = model.fit_predict(X_sub)
        results.append(
            {
                "k": k,
                "silhouette": float(silhouette_score(X_sub, labels)),
                "davies_bouldin": float(davies_bouldin_score(X_sub, labels)),
                "subsample_size": len(idx),
            }
        )
    return results, idx


def best_kmeans_k(results: list[dict]) -> int:
    """Highest silhouette — elbow (inertia) is reported alongside as
    supporting evidence but silhouette is the deciding metric, per
    PROJECT_PLAN.md section 6.2."""
    return max(results, key=lambda r: r["silhouette"])["k"]


def best_gmm_config(results: list[dict]) -> tuple[int, str]:
    """Lowest BIC (ignoring NaN-silhouette rows only affects reporting, not
    BIC selection — BIC is always defined)."""
    best = min(results, key=lambda r: r["bic"])
    return best["k"], best["covariance_type"]


def best_ward_k(results: list[dict]) -> int:
    return max(results, key=lambda r: r["silhouette"])["k"]
