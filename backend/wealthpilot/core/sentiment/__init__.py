"""Research-only comparison of two PRETRAINED sentiment classifiers (ADR-053).

Nothing here trains, fine-tunes, downloads, or decides a financial outcome. It runs two independent, locally stored, pretrained classifiers on text the user chose to write, normalises
their native labels, compares them with each other and with the rules baseline (`core/user_text_sentiment.py`), and reports every result separately. The rules baseline stays the production
method; this package is display-only, off by default, and exercised today only with stand-in backends (no package, weight file or licence approval exists).
"""
