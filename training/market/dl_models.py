"""LSTM and GRU return-direction models.

**Sequence construction**: strictly chronological. Sequence i uses returns
[i : i+window_length) to predict the return at [i+window_length] — never a
future value inside its own input window. Sequences are never shuffled.

**Scaling**: a `StandardScaler` is fit on the TRAINING window's returns
only, then applied to both training and test-window inputs — the test
period never influences the scaler's fitted mean/std (PROJECT_PLAN.md
section 6.4: "Fit the scaler on each training window only and refit it per
fold").

**Rolling evaluation** (different from ARIMA/GARCH's single multi-step
forecast — see models.py's module docstring for why): fit once per
walk-forward window on that window's training sequences, then predict each
day of the test window by sliding the REAL (realized) trailing
`window_length`-day return sequence forward one day at a time — every
prediction conditions on genuine historical data, never on the model's own
prior forecast, and never on a future value. This is natural for a sequence
model (cheap repeated inference, no retraining needed) and gives a much
larger, more informative sample within each window than a single point
forecast would.

**Sequence length**: PROJECT_PLAN.md section 6.4 specifies window length in
{20, 40, 60} as a hyperparameter to sweep. All three are tried per window;
the one with the lowest training-window validation loss is used for that
window's test-period evaluation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import StandardScaler

from training.market.common import RANDOM_STATE

SEQUENCE_LENGTHS = [20, 40, 60]
DROPOUT = 0.2
UNITS = 32
EPOCHS = 30
BATCH_SIZE = 16
PATIENCE = 5
VAL_FRACTION = 0.15


def _make_sequences(values: np.ndarray, window_length: int) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for i in range(len(values) - window_length):
        X.append(values[i : i + window_length])
        y.append(values[i + window_length])
    return np.array(X), np.array(y)


def _build_model(cell_type: str, window_length: int) -> tf.keras.Model:
    layer_cls = tf.keras.layers.LSTM if cell_type == "lstm" else tf.keras.layers.GRU
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(window_length, 1)),
            layer_cls(UNITS, dropout=DROPOUT),
            tf.keras.layers.Dense(1),
        ]
    )
    model.compile(optimizer="adam", loss="mse")
    return model


def fit_and_forecast(
    cell_type: str, train_returns: pd.Series, test_returns_context: pd.Series, n_steps: int
) -> dict:
    """`train_returns`: this window's training slice only.
    `test_returns_context`: the REAL returns immediately preceding AND
    spanning the test window (train tail + test period) — used only to
    supply real trailing values for the rolling sequence input, never to
    fit anything. `n_steps` must equal the test window's length.

    Returns dict with forecast array, chosen window_length, and val_loss
    used for selection (so the caller can report why that length was picked).
    """
    tf.keras.utils.set_random_seed(RANDOM_STATE)

    train_values = train_returns.to_numpy()
    best = None

    for window_length in SEQUENCE_LENGTHS:
        if len(train_values) <= window_length + 10:
            continue  # not enough training data for this sequence length

        scaler = StandardScaler().fit(train_values.reshape(-1, 1))
        scaled_train = scaler.transform(train_values.reshape(-1, 1)).flatten()

        X, y = _make_sequences(scaled_train, window_length)
        n_val = max(1, int(len(X) * VAL_FRACTION))
        X_train, y_train = X[:-n_val], y[:-n_val]
        X_val, y_val = X[-n_val:], y[-n_val:]

        model = _build_model(cell_type, window_length)
        history = model.fit(
            X_train.reshape(-1, window_length, 1),
            y_train,
            validation_data=(X_val.reshape(-1, window_length, 1), y_val),
            epochs=EPOCHS,
            batch_size=BATCH_SIZE,
            callbacks=[tf.keras.callbacks.EarlyStopping(patience=PATIENCE, restore_best_weights=True)],
            verbose=0,
        )
        val_loss = min(history.history["val_loss"])

        if best is None or val_loss < best["val_loss"]:
            best = {
                "window_length": window_length,
                "val_loss": val_loss,
                "model": model,
                "scaler": scaler,
            }

    if best is None:
        # Every sequence length required more data than this window has —
        # honestly report "no forecast", never fabricate one.
        return {"forecast": np.full(n_steps, np.nan), "window_length": None, "val_loss": None}

    window_length = best["window_length"]
    scaler = best["scaler"]
    model = best["model"]

    # Rolling 1-step-ahead using REAL trailing values only.
    context_scaled = scaler.transform(test_returns_context.to_numpy().reshape(-1, 1)).flatten()
    train_len = len(train_values)
    forecasts_scaled = []
    for step in range(n_steps):
        end = train_len + step
        window_vals = context_scaled[end - window_length : end]
        pred_scaled = model.predict(window_vals.reshape(1, window_length, 1), verbose=0)[0, 0]
        forecasts_scaled.append(pred_scaled)

    forecasts = scaler.inverse_transform(np.array(forecasts_scaled).reshape(-1, 1)).flatten()
    return {"forecast": forecasts, "window_length": window_length, "val_loss": float(best["val_loss"]), "model": model, "scaler": scaler}
