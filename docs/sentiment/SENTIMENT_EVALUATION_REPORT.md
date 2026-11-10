# Sentiment Evaluation Report (2026-11-05)

Written for: the project owner and examiners. **Headline: no accuracy, calibration, fairness or human-agreement metric exists for any sentiment method in this project, and none is claimed.** This report separates what *was* checked (engineering behaviour) from what *cannot* be checked (quality), and lists the evidence required before a quality claim could be made.

## 1. Evaluation status

| Question | Status | Why |
|---|---|---|
| Does the rules baseline behave as designed (deterministic, abstains correctly, safeguards fire)? | **VERIFIED** (characterization) | 42 regression tests over 30 fictional sentences (`tests/backend/core/test_user_text_rules_regression.py`, generated from `rules_golden.json`). This pins current behaviour; it is **not** a measure of correctness. |
| Does the Transformer path behave safely (gates, abstention, fault handling, privacy)? | **VERIFIED with mocks / fault injection** | `tests/backend/core/test_sentiment_research_slots.py`, `tests/backend/api/test_sentiment_research_api.py` |
| Can the model run? | **VERIFIED by direct loading** (Stage A, B2.1); **NOT VERIFIED through the application adapter** | opt-in smoke test not run |
| Is any method accurate on personal-finance text? | **NOT AVAILABLE** | No human-labelled evaluation set; D20 (permission to generate/collect/label) is rejected; D1, D2, D5, D14, D16, D19, E3 unresolved |
| Is any probability calibrated? | **NOT AVAILABLE** | probabilities are one uncalibrated softmax (`raw_softmax_uncalibrated`) |
| Is the Transformer better or worse than the rules? | **NOT AVAILABLE** | needs ground truth |
| Subgroup / fairness analysis | **NOT AVAILABLE** | no labelled data, no group definitions in use |
| Human validation | **NOT AVAILABLE** | no annotators engaged (A/D-series approvals not granted for generation) |

## 2. Metrics are unavailable, never zero

No accuracy, macro-F1, per-class precision/recall, calibration error, Brier score, human-agreement (kappa) or subgroup gap has been computed, and the product displays none of them. The offline evaluation package (`training/sentiment/metrics.py`, `evaluate_sentiment_model.py`, `frozen_evaluation.py`) is a framework only: where a quantity is undefined it reports `value: null` with an `unavailable_reason` (for example "no examples in the denominator", "no calibration-split record carries probabilities", "no item was labelled by both annotators"), and it needs an approved frozen manifest (E3 unresolved) that does not exist. It was not run on any real or invented labels in this work.

## 3. What the Stage A smoke run is — and is not

Eight invented sentences (positive, negative, neutral, mixed, ambiguous, negation, hypothetical, Spanish) were run through the model in isolation to confirm it loads and returns three logits in the expected order. Comparison with the rules baseline:

| Case | Rules (label / state) | Model native label |
|---|---|---|
| positive | positive / valid | positive |
| negative | negative / valid | negative |
| neutral | neutral / weak | neutral |
| mixed | negative / valid | neutral |
| ambiguous | insufficient_evidence / abstained | neutral |
| negation ("not worried…") | uncertain / weak | positive |
| hypothetical ("if I lost my job…") | uncertain / weak | negative |
| other language (Spanish) | insufficient_evidence / abstained | positive |

Agreement on 3 of 8 says nothing about accuracy: the sentences were written by the project, there is no ground truth, and the sample is far too small. The rows are useful for one engineering conclusion only — the model and the rules can differ exactly where context matters, so the combined reading marks "model differs from rules" and rules-safeguard cases as **uncertain** rather than choosing a winner.

## 4. Evidence required before any quality claim

1. An approved, frozen evaluation set with documented provenance, consent/de-identification, licence and a split policy (D1, D2, D5, D9–D11, E3).
2. Independent human annotation under a frozen rubric with agreement and adjudication (D6–D8, D19).
3. Pre-registered metrics with confidence intervals, an abstention/coverage report (D15), subgroup reporting (D12) and, if probabilities are ever shown, a calibration study on a separate calibration split (D13).
4. A comparison with the rules baseline on the same held-out set, and an owner decision on activation (F1/R14).

None of the above is authorised or performed. Creating or labelling any dataset requires reversing D20; this report does not do that.

## 5. How to run what can be run

- Rules regression: `python -m pytest tests/backend/core/test_user_text_rules_regression.py` (DB-free).
- Research path: `python -m pytest tests/backend/core/test_sentiment_research_slots.py tests/backend/api/test_sentiment_research_api.py`.
- Real-weights adapter smoke (opt-in, currently skipped): set `WEALTHPILOT_REAL_WEIGHTS_SMOKE=1` after the owner approves placing the verified files and writing the manifest with `scripts/write_pretrained_manifest.py --candidate horizon --tokenizer-length <len(tokenizer)>`. It also requires Horizon to be registered in a test via `dataclasses.replace` (the real constant stays pending).
