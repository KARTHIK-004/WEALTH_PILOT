# Limitations of the pretrained comparison (ADR-053)

- **No model has been run.** Neither candidate is permitted (licence / format findings in `model_licence_review.md`), no package is installed, no weight file exists. Everything about their behaviour is untested against real weights.
- **No accuracy, calibration or superiority claim can be made — now or after a model runs.** There is no human-labelled evaluation set for personal-finance language, none is being created (D20 stays rejected), and AI-generated or invented labels are not ground truth. Any agreement between the two models shows only that two classifiers produced the same label.
- **The fixtures are functional, not evidence.** `synthetic_functional_test_examples` (fictional sentences and stand-in logits in the tests) check wording and policy. They say nothing about model quality.
- **Domain mismatch.** FinBERT was built on financial news about companies; Twitter-RoBERTa on social-media posts. Neither was built for a person's statements about their own savings, debts and goals.
- **Three classes only.** The models cannot express `mixed`, `uncertain` or `insufficient evidence`; those come from the comparison and the rules safeguards. Negation, hypotheticals, past feelings, third-person and quoted speech are handled by the existing rules safeguards, not by the models.
- **Scores are not confidence.** The softmax is uncalibrated and valid only within one model. The two models' scores are never compared or combined, and there is no confidence or intensity field.
- **English text only**, up to the existing length limit and the configured token limit (longer text is truncated by the tokenizer).
- **Display only.** The result never changes the risk profile, risk appetite, investment capacity, goal priority, portfolio, recommendation, compliance decision or savings-first routing, and is not financial advice. It is not stored, logged, anchored or sent anywhere; the text lives only in memory for the request.
- **Not production.** `user_text_rules_v1` remains the production method. A pretrained model is never promoted automatically; promotion would be a new decision with validation evidence that does not exist.

## Why fine-tuning and regression are deferred

Fine-tuning needs a labelled training set and a separate held-out set with documented provenance, consent and licensing; none is approved. A sentiment-intensity regression needs human intensity labels and
its own evaluation protocol; none exist. Turning a class probability into an "intensity" would invent a number, so intensity stays `null` and the API has no such field in the research object.

---

## Domain limits of the proposed replacements (ADR-054)

- **Financial DistilBERT** was trained on short finance-related tweets labelled Bullish / Bearish / Neutral. That is market-oriented tone, not a person's feelings about debt, EMI pressure, savings anxiety, retirement or household finances. Its card says it is not for trading decisions, non-English text, long-form news or high-stakes use, and that it may misread sarcasm and mixed-signal posts.
- **Horizon multilingual** was trained on web-crawl snippets and LLM-written synthetic text, with labels produced by an LLM. It inherits that teacher's judgement, is weaker on sarcasm, very short or context-dependent messages and low-resource languages, and its card says not to use it to make decisions about individuals. Its multilingual ability is unused here because WealthPilot passes only English text to a model.
- Neither model was built to infer risk appetite, investment capacity, financial suitability, psychological state or actual behaviour, and WealthPilot never uses them for that. Sentiment stays explanatory context only; the self-reported card metrics are not WealthPilot evidence and no accuracy claim is made.

---

## What the Horizon research approval accepts, and what it does not (2026-11-04)

Accepted for research inference only: web-crawl (FineWeb / FineWeb-2) and LLM-written training text, labels produced by an LLM teacher, and no human-validated labels. Therefore: the model cannot be described as human-validated; no accuracy, calibration or superiority claim is permitted without an appropriate evaluation that does not exist; its multilingual ability is not used (only English text reaches a model); it is not a personal-finance classifier; it must not be used to make decisions about individuals, so its output stays display-only context. Self-reported card metrics are not WealthPilot evidence.
