"""Offline sentiment scaffold for the GDELT track (S2). **No real sentiment inference exists here.**

This package defines the article-level schema, a deterministic TEST-ONLY fake scorer, and the daily feature aggregation, so
the plumbing (schema validation, point-in-time cutoffs, deduplication, coverage and missing-data handling) can be tested before
any real model is approved. It loads no model, calls no API, downloads nothing, reads no sealed key or annotation label, and is
connected to no forecasting model, optimizer or recommendation.

**Not production-ready.** The deduplication policy, the coverage threshold and the early-close calendar it uses are PROPOSED
(B2-H), not approved; every feature row says so (``rules_status``). Nothing here changes a threshold, a target or an approval.

S2.2 corrected the scaffold after an independent review: inputs are validated (calendar, source-slot grid, slot/article
reconciliation), partial scoring and unresolved duplicate handling are exposed instead of hidden, and the fake scorer refuses to
run outside a test session. Theme-specific calendars remain BLOCKED on an approved forecast target.

The fake scorer is deliberately NOT exported from this package: import it from ``sentiment.fake_scorer`` in a test only.
"""
