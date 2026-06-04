# What We're Doing

Stages 2–3 fed the model numbers derived from **price**. This stage feeds it something genuinely new: **what the news said**.

The pipeline has two phases:

**Phase 1 — prep, run once.** We fetch a small corpus of headlines (a few hundred) for a symbol and date range from the Alpaca News API, then score every headline with **FinBERT** — a BERT transformer fine-tuned on financial text that outputs three probabilities per headline: *positive*, *negative*, *neutral*. You can read every headline and its scores in the browser below — nothing is hidden. The per-day aggregate (mean positive minus mean negative, plus headline count) is cached, so this expensive step never runs twice.

**Phase 2 — train, as often as you like.** The Stage 3 multi-task model gets **two extra feature columns**: *yesterday's* net sentiment and headline count. Everything else — indicators, the three heads, the training loop — is unchanged, which is exactly the point: one new variable, so the comparison against Stage 3 is clean.

FinBERT inference takes ~0.1–0.3 seconds per headline on this CPU (and the model itself is a one-time ~440MB download), which is why prep is a background job with a progress bar — and why the cache exists.
