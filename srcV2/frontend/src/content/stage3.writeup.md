# Full Writeup — Understanding Stage 3

## The 10 indicators, in one breath each

**Price-scale (drawn on the candles):** **SMA** — the plain N-bar average; price above it = uptrend bias. **EMA** — same idea, recent bars weighted heavier, turns faster. **Bollinger Bands** — an SMA ± k standard deviations; width *is* volatility. **VWAP** — the volume-weighted average price; where the money actually traded (we use a rolling window, not the session-anchored variant — a deliberate simplification).

**Own-scale (stacked panes):** **RSI** — 0–100; how one-sided recent gains vs losses are. **MACD** — fast EMA minus slow EMA, plus a signal EMA of that gap; momentum and its turning points. **Stochastic** — where the close sits in the recent high–low range. **ATR** — the average true range; bar size in price units. **ADX** — trend *strength* regardless of direction (±DI carry the direction). **OBV** — volume added on up closes, subtracted on down ones; is volume confirming the move?

## One source of truth

Each indicator is a pure function `(bars, params, timeframe) → series` in a registry on the backend. The catalog endpoint serves the UI its toggles and parameter bounds; the compute endpoint serves the chart; `feature_pipeline` serves the model. One implementation, three consumers — the chart preview is not an illustration of the features, it **is** the features.

## From series to training matrix

Indicator series start with `None`s (warm-up). The pipeline flattens every line into columns (`bollinger.upper`, `macd.signal`, …), and the dataset builder:

1. derives the five stationary **return features** from raw OHLCV (as Stage 2 — price *levels* would crush the signal),
2. **trims** every row until all indicator columns are defined — no imputation, no NaNs, just honest deletion of the warm-up,
3. splits 70/15/15 **by time** and fits the scaler on **training rows only** — the same leakage guards as Stage 2, now over a wider matrix (indicator columns like RSI≈50 or OBV in the millions all become comparable z-scores).

## Three targets, and why two get standardized

- **Direction**: `1 if close[t+h] > close[t]` — binary, as Stage 2.
- **Return**: `ln(close[t+h] / close[t])`. Raw log returns live at the 1e-4 scale; an MSE on them would be ≈0 from the start and gradients would vanish next to the BCE term. So we standardize by the train split's mean/std — now "predict zero always" costs MSE ≈ 1.0, the same scale as the other losses. The saved artifact carries the stats so predictions convert back to real returns.
- **Volatility**: the standard deviation of the next `vol_window` one-bar log returns — *realized* volatility right after the window. It's non-negative and skewed, so it trains as standardized `log1p(vol)`.

## The multi-task loss

`L = w_dir·BCE + w_ret·MSE + w_vol·MSE`, weights from the form (default 1.0 each). One trunk, three gradients flowing into it. Raising a weight makes the trunk care more about that head — the *Volatility focus* preset demonstrates it. Early stopping and the LR scheduler watch the **total** validation loss, so a head you've weighted to zero can't stop training on its own.

## Reading the results honestly

The direction head keeps Stage 2's full toolkit — confusion matrix, majority baseline, the verdict's significance test. Indicators *sometimes* buy a point or two of direction accuracy; the verdict will tell you whether it's signal or sampling luck. The regression heads report MAE: return MAE hovering near the average absolute move means "no skill beyond zero"; volatility MAE falling well below its starting point is real, learnable structure. If you take one thing from Stage 3: **predictability is not one thing** — the same trunk, the same data, and three very different verdicts per head.

## What to try changing

- The *Trend pack* vs *Volatility focus* presets on the same slice — compare per-head metrics.
- `w_dir=0`: train return+vol only, then look at direction accuracy anyway (the trunk still encodes *some* directional info — or does it?).
- A 5-period RSI vs a 30-period RSI — watch the warm-up row count and the feature's usefulness move in opposite directions.
- The same config twice — the second run reads `feature_cache` instead of recomputing (check `feature_set` in the metrics).
