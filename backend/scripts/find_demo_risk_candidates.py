"""Demo Data phase — read-only discovery tool, kept for reproducibility.

Not part of the application; not imported by anything under `wealthpilot/`.
This is how the three real FAR-Trans `customerID` values used by
`scripts/seed_demo_data.py` (`DEMO_PERSONAS[*]["external_customer_id"]`)
were chosen. Re-running it reproduces the same candidate lists (the
underlying raw data and trained artifacts are immutable and unchanged).

Uses ONLY the existing, unmodified Phase 3 feature-engineering function
(`wealthpilot.data.preprocessing.engineer_features`) and the existing,
unmodified Phase 4 trained artifacts (`models/risk/{preprocessor,rf}_v1.pkl`)
— run in the SAME batch shape `engineer_features()`'s own docstring
describes it for, not the single-customer wrapper
`agents/nodes.py::engineer_features_for_customer` uses per live request
(mathematically identical, just far more efficient for scanning ~29,000
customers at once than calling the single-customer path in a loop).

Touches NO database, NO raw file, NO model artifact. Read-only.
"""
from __future__ import annotations

import joblib
import pandas as pd

from training.behaviour.common import build_monthly_panel
from wealthpilot.data.preprocessing import ALL_FEATURES, engineer_features, load_far_trans_tables

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
RISK_MODELS_DIR = REPO_ROOT / "models" / "risk"


def find_candidates(min_confidence: float = 0.50, min_months: int = 4) -> pd.DataFrame:
    tables = load_far_trans_tables()
    customers, transactions, assets, close_prices = (
        tables["customers"], tables["transactions"], tables["assets"], tables["close_prices"],
    )

    features = engineer_features(customers, transactions, assets, close_prices)

    preprocessor = joblib.load(RISK_MODELS_DIR / "preprocessor_v1.pkl")
    classifier = joblib.load(RISK_MODELS_DIR / "rf_v1.pkl")
    X_t = preprocessor.transform(features[ALL_FEATURES])
    proba = classifier.predict_proba(X_t)
    predicted = classifier.classes_[proba.argmax(axis=1)]
    confidence = proba.max(axis=1)

    result = pd.DataFrame(
        {"customerID": features.index, "predicted_risk_category": predicted, "confidence": confidence}
    ).set_index("customerID")

    panel = build_monthly_panel(transactions, assets)
    month_counts = panel.groupby("customerID").size().rename("n_months")
    result = result.join(month_counts, how="left")
    result["n_months"] = result["n_months"].fillna(0).astype(int)

    return result[(result["confidence"] >= min_confidence) & (result["n_months"] >= min_months)]


if __name__ == "__main__":
    candidates = find_candidates()
    for category in ["Conservative", "Income", "Balanced", "Aggressive"]:
        subset = candidates[candidates["predicted_risk_category"] == category].sort_values(
            ["confidence", "n_months"], ascending=[False, False]
        )
        print(f"\n--- {category}: {len(subset)} candidates (top 5) ---")
        print(subset.head(5))
