# Why We're Doing It

Stage 2 ended with an honest ~50% — raw next-bar OHLCV is nearly pure noise. Two ideas attack that:

**1. Hand-crafted features.** Indicators are decades of trader intuition compressed into formulas: trend (SMA/EMA/MACD/ADX), stretch (Bollinger, Stochastic, RSI), participation (VWAP, OBV), and turbulence (ATR). A neural net *could* learn these transforms from raw bars — but not from our CPU-sized slices. Computing them explicitly hands the model distilled signal it would otherwise need millions of examples to discover. Whether they actually help direction is an **experiment, not an assumption** — the runs table and the verdict will tell you.

**2. Multi-task learning.** The three heads share one trunk, so the representation must explain direction *and* magnitude *and* turbulence at once. The auxiliary tasks act as regularizers for each other — and volatility, unlike direction, is genuinely predictable (volatility clusters: rough markets stay rough). Expect the vol head to learn visibly while direction fights for scraps. That contrast is the lesson.

There's also an architecture lesson: **one source of truth**. The chart endpoint and the ML feature pipeline call the same `indicators.compute()`. And the computed feature matrix is cached in `feature_cache` keyed by a config hash — wired up now while it's cheap, because Stages 4–5 (FinBERT, GDELT) will cache features that take *minutes* to compute, not milliseconds.
