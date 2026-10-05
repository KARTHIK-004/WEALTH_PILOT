"""Phase 8 — deterministic portfolio optimizer.

Pure, DB-free calculation module (same design as `core/goals.py` in Phase 7):
every function here takes a plain `pandas`/`numpy` return matrix and returns
plain weights/numbers. No FastAPI, LangGraph, AutoGen, or Gemini code may
compute a portfolio number anywhere else — CLAUDE.md rule 1. Reading
`market_data` from PostgreSQL and driving a real run lives in
`training/portfolio/`, mirroring Phases 4-6's `training/<phase>/` pattern.

Documented methodology decisions (every one was either explicit in
PROJECT_PLAN.md/MASTER_PROMPT.md/BUILD_PLAN.md, or approved via
AskUserQuestion on 2026-09-14 before any code was written):

- **Investable asset universe**: `QQQ, AGG, GLD` only. `^IXIC` and `^NDX`
  (Phase 6's two index instruments) are excluded — an index is not directly
  tradable, and Phase 6 itself already described QQQ as "a tradable proxy
  for ^NDX." The two indices remain valid Phase 6 regime-classification
  inputs; they are simply not portfolio assets.
- **No synthetic cash instrument.** AGG (bonds — by a wide margin the
  lowest-volatility of the three real instruments, Phase 6 RMSE ~0.003 vs
  ~0.013+ for QQQ/GLD) plays the defensive/"cash-floor" role. There is no
  4th zero-volatility pseudo-asset.
- **Expected returns**: annualized historical mean of daily simple returns
  (`mean(daily_return) * TRADING_DAYS_PER_YEAR`) — PROJECT_PLAN.md section
  2.5 explicitly requires the deliverable to note "expected returns are
  historical estimates and not forecasts," and separately forbids feeding
  Phase 6's LSTM/GRU/ARIMA point forecasts into the optimizer as expected
  returns (they may only ever inform a regime label that adjusts
  constraint *bounds*, never the return estimates themselves).
- **Covariance**: Ledoit-Wolf shrinkage (`sklearn.covariance.LedoitWolf`,
  CLAUDE.md's explicitly approved dependency) on annualized covariance —
  mandatory for the actual MVO/HRP/frontier computations. The plain sample
  covariance (`sample_covariance`) exists only for side-by-side comparison/
  documentation, per PROJECT_PLAN.md's "compare against ... if required" —
  it is never silently substituted for Ledoit-Wolf in a real result.
- **MVO objective**: maximize Sharpe ratio (the classical Markowitz
  tangency portfolio). Approved 2026-09-14.
- **Risk-free rate**: 0%. Approved 2026-09-14 — avoids an arbitrary,
  unsourced point-in-time T-bill/SGB snapshot.
- **Box constraints**: PROJECT_PLAN.md section 2.5 names four constraint
  *categories* (equity share bounded by risk category, single-asset cap,
  Nasdaq/tech concentration cap, minimum cash floor tied to emergency-fund
  status) without numbers. In our 3-asset universe, QQQ is simultaneously
  "the equity share" and "the only Nasdaq/tech asset," so those two
  categories collapse into one number per risk level (`RISK_LEVEL_QQQ_BANDS`,
  approved 2026-09-14). `GENERAL_SINGLE_ASSET_CAP` (0.70, approved
  2026-09-14) applies uniformly to all three assets on top of that band —
  the two constraints are INTERSECTED (the tighter bound always wins), not
  one overriding the other, which is why Aggressive's nominal 80% QQQ
  ceiling is effectively 70% once the general cap is applied (see
  `effective_bounds`). `min_cash_allocation` (the minimum-cash-floor /
  emergency-fund constraint) is a plain function parameter with NO default
  — approved 2026-09-14 to stay a bare optimizer input rather than have
  this module read Phase 7 state itself: Phase 7 already fully owns the
  "insufficient EF -> skip optimization entirely" short-circuit at the
  agent-orchestration level (a later phase), and duplicating that decision
  here would violate this phase's own instruction not to duplicate Goal
  Engine logic.
- **HRP methodology**: the standard López de Prado (2016) algorithm —
  single-linkage hierarchical clustering on a correlation-distance matrix,
  quasi-diagonalization (seriating assets by the dendrogram leaf order),
  then recursive bisection allocating inverse-variance-weighted risk
  contributions top-down. Not tied to Phase 5's Ward clustering, which is
  an unrelated use of hierarchical clustering for expense-persona
  segmentation. There is no competing HRP convention named anywhere in the
  project documents, and this is the algorithm "Hierarchical Risk Parity"
  unambiguously refers to in the literature PROJECT_PLAN.md itself cites,
  so it was implemented directly rather than put to a question.
- **1/N benchmark**: always exactly equal-weight across the full 3-asset
  universe, deliberately UNCONSTRAINED by any risk-level box constraint —
  it is the naive, unoptimized DeMiguel/Garlappi/Uppal (2009) benchmark
  PROJECT_PLAN.md names explicitly, and constraining it would defeat its
  purpose as a baseline.
- **Trading-days-per-year (252)**: a unit-conversion constant, not a
  financial assumption — the universal standard for annualizing a daily
  return/volatility series, not a contested convention, so it was not put
  to a question (unlike the genuinely consequential numbers above).
- **random_state = 42** throughout (CLAUDE.md rule 9), though MVO/HRP/
  covariance are deterministic by construction here (SLSQP from a fixed,
  non-random starting point; Ledoit-Wolf and single-linkage clustering have
  no stochastic step) — the seed is recorded for completeness and to keep
  the convention uniform across phases.

No trade execution, brokerage integration, or fund transfer anywhere in
this module (CLAUDE.md rule 10) — every function here returns weights and
numbers only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

RANDOM_STATE = 42
TRADING_DAYS_PER_YEAR = 252

ASSET_UNIVERSE = ["QQQ", "AGG", "GLD"]
RISK_FREE_RATE = 0.0
GENERAL_SINGLE_ASSET_CAP = 0.70

RISK_LEVEL_QQQ_BANDS: dict[str, tuple[float, float]] = {
    "Conservative": (0.10, 0.30),
    "Income": (0.20, 0.40),
    "Balanced": (0.35, 0.55),
    "Aggressive": (0.55, 0.80),
}


# ---------------------------------------------------------------------------
# Expected returns / covariance
# ---------------------------------------------------------------------------


def expected_returns_historical(returns: pd.DataFrame) -> pd.Series:
    """Annualized historical mean of daily simple returns. Never a Phase 6
    model forecast — see the module docstring."""
    return returns.mean() * TRADING_DAYS_PER_YEAR


def covariance_ledoit_wolf(returns: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Ledoit-Wolf shrinkage covariance, annualized. Returns
    (annualized_covariance, shrinkage_constant) — the shrinkage constant is
    recorded for reproducibility/documentation."""
    estimator = LedoitWolf().fit(returns.to_numpy())
    cov = pd.DataFrame(estimator.covariance_, index=returns.columns, columns=returns.columns)
    return cov * TRADING_DAYS_PER_YEAR, float(estimator.shrinkage_)


def sample_covariance(returns: pd.DataFrame) -> pd.DataFrame:
    """Plain sample covariance, annualized — comparison/documentation only,
    never used to compute a real MVO/HRP/frontier result."""
    return returns.cov() * TRADING_DAYS_PER_YEAR


# ---------------------------------------------------------------------------
# Box constraints
# ---------------------------------------------------------------------------


def effective_bounds(
    risk_level: str,
    assets: list[str] = ASSET_UNIVERSE,
    general_cap: float = GENERAL_SINGLE_ASSET_CAP,
    min_cash_allocation: float = 0.0,
) -> dict[str, tuple[float, float]]:
    """Per-asset (lower, upper) box constraints. QQQ's risk-category band
    and the general single-asset cap are INTERSECTED (tighter bound wins).
    AGG additionally receives `min_cash_allocation` as its lower bound (the
    emergency-fund minimum-cash-floor hook — a bare parameter, see the
    module docstring). GLD has no dedicated bound beyond the general cap.
    """
    if risk_level not in RISK_LEVEL_QQQ_BANDS:
        raise ValueError(f"unknown risk_level {risk_level!r}; expected one of {list(RISK_LEVEL_QQQ_BANDS)}")
    if not 0.0 <= general_cap <= 1.0:
        raise ValueError("general_cap must be within [0, 1]")
    if not 0.0 <= min_cash_allocation <= 1.0:
        raise ValueError("min_cash_allocation must be within [0, 1]")
    if min_cash_allocation > 0.0 and "AGG" not in assets:
        raise ValueError("a positive min_cash_allocation requires AGG to be part of the asset universe")

    bounds: dict[str, tuple[float, float]] = {}
    for asset in assets:
        if asset == "QQQ":
            band_lower, band_upper = RISK_LEVEL_QQQ_BANDS[risk_level]
            bounds[asset] = (min(band_lower, general_cap), min(band_upper, general_cap))
        elif asset == "AGG":
            bounds[asset] = (min(min_cash_allocation, general_cap), general_cap)
        else:
            bounds[asset] = (0.0, general_cap)

    lower_sum = sum(b[0] for b in bounds.values())
    upper_sum = sum(b[1] for b in bounds.values())
    if lower_sum > 1.0 + 1e-9:
        raise ValueError(f"infeasible bounds: sum of lower bounds ({lower_sum:.4f}) exceeds 1")
    if upper_sum < 1.0 - 1e-9:
        raise ValueError(f"infeasible bounds: sum of upper bounds ({upper_sum:.4f}) is below 1")
    return bounds


# ---------------------------------------------------------------------------
# Shared portfolio math
# ---------------------------------------------------------------------------


def portfolio_return(weights: pd.Series, expected_returns: pd.Series) -> float:
    return float(np.dot(weights.reindex(expected_returns.index), expected_returns))


def portfolio_volatility(weights: pd.Series, cov_matrix: pd.DataFrame) -> float:
    w = weights.reindex(cov_matrix.index).to_numpy()
    return float(np.sqrt(w @ cov_matrix.to_numpy() @ w))


def sharpe_ratio(annualized_return: float, annualized_volatility: float, risk_free_rate: float = RISK_FREE_RATE) -> float:
    if annualized_volatility == 0.0:
        return 0.0 if annualized_return == risk_free_rate else float("inf") * np.sign(annualized_return - risk_free_rate)
    return (annualized_return - risk_free_rate) / annualized_volatility


def _initial_guess(bounds: dict[str, tuple[float, float]], assets: list[str]) -> np.ndarray:
    """Deterministic, non-random starting point for SLSQP: the midpoint of
    each asset's box, renormalized to sum to 1."""
    mids = np.array([(bounds[a][0] + bounds[a][1]) / 2.0 for a in assets])
    total = mids.sum()
    if total <= 0:
        return np.full(len(assets), 1.0 / len(assets))
    return mids / total


# ---------------------------------------------------------------------------
# Mean-Variance Optimization (maximize Sharpe ratio)
# ---------------------------------------------------------------------------


def mvo_max_sharpe(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    bounds: dict[str, tuple[float, float]],
    risk_free_rate: float = RISK_FREE_RATE,
) -> pd.Series:
    """Maximize Sharpe ratio subject to sum(weights) = 1 and the given box
    constraints (no short-selling: every lower bound is >= 0 by
    construction of `effective_bounds`). Deterministic: SLSQP from a fixed,
    non-random starting point (see `_initial_guess`)."""
    assets = list(expected_returns.index)
    mu = expected_returns.to_numpy()
    cov = cov_matrix.reindex(index=assets, columns=assets).to_numpy()

    def neg_sharpe(w: np.ndarray) -> float:
        ret = float(w @ mu)
        vol = float(np.sqrt(w @ cov @ w))
        if vol == 0.0:
            return 0.0
        return -(ret - risk_free_rate) / vol

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    box = [bounds[a] for a in assets]
    x0 = _initial_guess(bounds, assets)

    result = minimize(neg_sharpe, x0, method="SLSQP", bounds=box, constraints=constraints, options={"maxiter": 1000, "ftol": 1e-12})
    if not result.success:
        raise RuntimeError(f"MVO optimization failed to converge: {result.message}")
    return pd.Series(result.x, index=assets)


def min_variance_for_target_return(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    bounds: dict[str, tuple[float, float]],
    target_return: float,
) -> pd.Series:
    """Minimize portfolio variance subject to sum(weights) = 1, the box
    constraints, and w . mu = target_return. Used both to trace the
    efficient frontier and to locate the global minimum-variance portfolio.
    """
    assets = list(expected_returns.index)
    mu = expected_returns.to_numpy()
    cov = cov_matrix.reindex(index=assets, columns=assets).to_numpy()

    def variance(w: np.ndarray) -> float:
        return float(w @ cov @ w)

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "eq", "fun": lambda w: float(w @ mu) - target_return},
    ]
    box = [bounds[a] for a in assets]
    x0 = _initial_guess(bounds, assets)

    result = minimize(variance, x0, method="SLSQP", bounds=box, constraints=constraints, options={"maxiter": 1000, "ftol": 1e-14})
    if not result.success:
        raise RuntimeError(f"min-variance optimization failed to converge for target_return={target_return}: {result.message}")
    return pd.Series(result.x, index=assets)


# ---------------------------------------------------------------------------
# 1/N benchmark
# ---------------------------------------------------------------------------


def equal_weight_portfolio(assets: list[str] = ASSET_UNIVERSE) -> pd.Series:
    """Naive 1/N — deliberately unconstrained by any risk-level box
    constraint (DeMiguel, Garlappi & Uppal, 2009)."""
    if len(assets) == 0:
        raise ValueError("assets must be non-empty")
    return pd.Series(1.0 / len(assets), index=assets)


# ---------------------------------------------------------------------------
# Hierarchical Risk Parity (López de Prado, 2016)
# ---------------------------------------------------------------------------


def _cluster_variance(cov: pd.DataFrame, cluster_items: list[str]) -> float:
    sub_cov = cov.loc[cluster_items, cluster_items].to_numpy()
    inv_diag = 1.0 / np.diag(sub_cov)
    ivp = inv_diag / inv_diag.sum()
    return float(ivp @ sub_cov @ ivp)


def _quasi_diagonal_order(link: np.ndarray, n_items: int) -> list[int]:
    """Seriates leaves by the dendrogram merge order (López de Prado 2016,
    ch. 16) so that similar assets end up adjacent before recursive
    bisection."""
    link = link.astype(int)
    sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
    while sort_ix.max() >= n_items:
        sort_ix.index = range(0, sort_ix.shape[0] * 2, 2)
        clusters = sort_ix[sort_ix >= n_items]
        i = clusters.index
        j = clusters.values - n_items
        sort_ix[i] = link[j, 0]
        df1 = pd.Series(link[j, 1], index=i + 1)
        sort_ix = pd.concat([sort_ix, df1])
        sort_ix = sort_ix.sort_index()
        sort_ix.index = range(sort_ix.shape[0])
    return sort_ix.tolist()


def _recursive_bisection(cov: pd.DataFrame, sorted_items: list[str]) -> pd.Series:
    weights = pd.Series(1.0, index=sorted_items)
    clusters = [sorted_items]
    while len(clusters) > 0:
        clusters = [
            c[start:stop]
            for c in clusters
            for start, stop in ((0, len(c) // 2), (len(c) // 2, len(c)))
            if len(c) > 1
        ]
        for i in range(0, len(clusters), 2):
            cluster_0 = clusters[i]
            cluster_1 = clusters[i + 1]
            var_0 = _cluster_variance(cov, cluster_0)
            var_1 = _cluster_variance(cov, cluster_1)
            alpha = 1.0 - var_0 / (var_0 + var_1)
            weights[cluster_0] *= alpha
            weights[cluster_1] *= 1.0 - alpha
    return weights


def hrp_weights(returns: pd.DataFrame) -> pd.Series:
    """Standard HRP: single-linkage clustering on a correlation-distance
    matrix, quasi-diagonalization, recursive bisection. Deterministic (no
    random step). A single-asset universe returns weight 1.0 trivially —
    `scipy.cluster.hierarchy.linkage` requires at least 2 observations."""
    assets = list(returns.columns)
    if len(assets) == 0:
        raise ValueError("returns must have at least one asset column")
    if len(assets) == 1:
        return pd.Series([1.0], index=assets)

    corr = returns.corr()
    cov = returns.cov()
    distance = np.sqrt(0.5 * (1.0 - corr))
    condensed = distance.to_numpy()[np.triu_indices(len(assets), k=1)]
    link = linkage(condensed, method="single")
    order = _quasi_diagonal_order(link, len(assets))
    sorted_assets = [assets[i] for i in order]
    weights = _recursive_bisection(cov, sorted_assets)
    return weights.reindex(assets)


# ---------------------------------------------------------------------------
# Efficient frontier
# ---------------------------------------------------------------------------


N_FRONTIER_POINTS = 25


def efficient_frontier(
    expected_returns: pd.Series,
    cov_matrix: pd.DataFrame,
    bounds: dict[str, tuple[float, float]],
    risk_free_rate: float = RISK_FREE_RATE,
    n_points: int = N_FRONTIER_POINTS,
) -> pd.DataFrame:
    """Traces the frontier from the global minimum-variance portfolio's
    return up to the highest return any single feasible asset offers,
    using the SAME Ledoit-Wolf covariance and historical expected returns
    MVO uses (never a separately-fabricated set of points). The max-Sharpe
    MVO point is included as its own explicitly marked row.
    """
    assets = list(expected_returns.index)
    min_var_weights = min_variance_for_target_return(
        expected_returns, cov_matrix, bounds, target_return=_min_feasible_return(expected_returns, bounds)
    )
    min_return = portfolio_return(min_var_weights, expected_returns)
    max_return = float(expected_returns.max())
    if max_return <= min_return:
        max_return = min_return + 1e-6

    target_returns = np.linspace(min_return, max_return, n_points)
    rows = []
    for target in target_returns:
        try:
            w = min_variance_for_target_return(expected_returns, cov_matrix, bounds, float(target))
        except RuntimeError:
            continue
        vol = portfolio_volatility(w, cov_matrix)
        ret = portfolio_return(w, expected_returns)
        rows.append(
            {
                "target_return": float(target),
                "return": ret,
                "volatility": vol,
                "sharpe": sharpe_ratio(ret, vol, risk_free_rate),
                "weights": w.to_dict(),
                "is_max_sharpe": False,
            }
        )

    frontier = pd.DataFrame(rows)
    max_sharpe_weights = mvo_max_sharpe(expected_returns, cov_matrix, bounds, risk_free_rate)
    max_sharpe_ret = portfolio_return(max_sharpe_weights, expected_returns)
    max_sharpe_vol = portfolio_volatility(max_sharpe_weights, cov_matrix)
    max_sharpe_row = {
        "target_return": max_sharpe_ret,
        "return": max_sharpe_ret,
        "volatility": max_sharpe_vol,
        "sharpe": sharpe_ratio(max_sharpe_ret, max_sharpe_vol, risk_free_rate),
        "weights": max_sharpe_weights.to_dict(),
        "is_max_sharpe": True,
    }
    frontier = pd.concat([frontier, pd.DataFrame([max_sharpe_row])], ignore_index=True)
    return frontier.sort_values("volatility").reset_index(drop=True)


def _min_feasible_return(expected_returns: pd.Series, bounds: dict[str, tuple[float, float]]) -> float:
    """A cheap, deterministic lower bound for the frontier's return sweep:
    the weighted return of whichever feasible corner minimizes expected
    return (used only as a starting point for `min_variance_for_target_return`'s
    own search, not as a claimed optimum)."""
    assets = list(expected_returns.index)
    order = expected_returns.sort_values().index.tolist()
    remaining = 1.0 - sum(bounds[a][0] for a in assets)
    weights = {a: bounds[a][0] for a in assets}
    for a in order:
        capacity = bounds[a][1] - weights[a]
        take = min(capacity, remaining)
        weights[a] += take
        remaining -= take
        if remaining <= 1e-12:
            break
    w = pd.Series(weights).reindex(assets)
    return portfolio_return(w, expected_returns)
