"""Tests for the clustering sweep and evidence-based selection functions,
on a small synthetic dataset with a known, constructed cluster structure —
fast, and the "correct" answer is known in advance, unlike the real Kaggle
data where the correct k is discovered rather than verified."""

import numpy as np
from sklearn.preprocessing import StandardScaler

from training.expense.clustering import (
    best_gmm_config,
    best_kmeans_k,
    best_ward_k,
    sweep_gmm,
    sweep_kmeans,
    sweep_ward,
)


def _three_blob_fixture():
    rng = np.random.default_rng(42)
    blob_a = rng.normal(loc=[0, 0], scale=0.2, size=(100, 2))
    blob_b = rng.normal(loc=[5, 5], scale=0.2, size=(100, 2))
    blob_c = rng.normal(loc=[5, -5], scale=0.2, size=(100, 2))
    X = np.vstack([blob_a, blob_b, blob_c])
    return StandardScaler().fit_transform(X)


def test_kmeans_sweep_recovers_the_known_cluster_count():
    X_scaled = _three_blob_fixture()
    results = sweep_kmeans(X_scaled)
    assert best_kmeans_k(results) == 3


def test_ward_sweep_recovers_the_known_cluster_count():
    X_scaled = _three_blob_fixture()
    results, idx = sweep_ward(X_scaled)
    assert best_ward_k(results) == 3
    assert len(idx) == len(X_scaled)  # no subsampling needed below WARD_SUBSAMPLE_SIZE


def test_gmm_sweep_selects_by_bic_not_silhouette():
    X_scaled = _three_blob_fixture()
    results = sweep_gmm(X_scaled)
    k, cov_type = best_gmm_config(results)
    assert k == 3
    assert cov_type in {"full", "tied", "diag", "spherical"}


def test_kmeans_sweep_is_deterministic():
    X_scaled = _three_blob_fixture()
    results_1 = sweep_kmeans(X_scaled)
    results_2 = sweep_kmeans(X_scaled)
    assert results_1 == results_2
