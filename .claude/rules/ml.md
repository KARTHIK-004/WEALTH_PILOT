# ML Rules

Quick-reference for `training/`, `models/`, and model-serving code in
`backend/wealthpilot/agents/nodes.py`. Full detail: `docs/RULES.md`,
`docs/ARCHITECTURE.md` §8-9, `docs/DECISIONS.md` ADR-007/008/009/010.

- Training happens offline only, in `training/<family>/`, invoked
  explicitly by a human. Never inside a FastAPI request, a LangGraph
  node, an agent, or as a test side effect.
- Serialized artifacts live under `models/<family>/` plus
  `models/metrics.json`; loaded once at startup and cached in-process.
  Do not replace an artifact unless explicitly asked to retrain.
- No shuffled splits on time-ordered data. Expanding-window walk-forward
  with an embargo gap. Market models target returns/volatility, never
  price levels.
- Filter FAR-Trans's `Predicted_*`/`Not_Available` rows before training —
  they are another model's output, not ground truth.
- Fit every preprocessor on training data only; serialize it with the
  model (never fit-then-discard, never fit on data that includes the
  held-out fold).
- `random_state=42` (or the numpy-`default_rng` equivalent) in every
  stochastic step. Log library versions where a training script already
  does.
- FAR-Trans (risk/behaviour) and the Kaggle personal-finance dataset
  (expense segmentation) are separate, unlinked populations. Never invent
  a linkage between them, and never apply the expense model to a
  FAR-Trans customer's own data.
- No frontend ML, no API-time training, no live retraining triggered by
  any user action.
- A "static" per-entity classification framing does not exempt features
  from point-in-time correctness — leakage rules apply even when the
  target looks like a fixed, non-time-series label.
