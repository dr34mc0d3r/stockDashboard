## Why We're Doing It

A neural network is only as good as the data it learns from. Before we can teach a model
to predict anything, we need a **clean, local, reliable** store of price history:

- **Reproducibility** — training on a fixed local dataset means results don't change just
  because a remote API returned something different today.
- **Speed** — reading from our own database is far faster than re-fetching over the
  network every time we tweak a model.
- **Reuse** — one download feeds Stage 2's LSTM, Stage 3's indicators, and beyond.

Getting the data layer right now saves us from fighting data problems in every later stage.
