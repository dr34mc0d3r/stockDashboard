# What Am I to See and Learn

**On the chart preview (Parameter Config).** Price-scale indicators draw *on* the candles — watch how price respects or ignores an SMA, how Bollinger bands pinch before expansions. Own-scale indicators stack below sharing the time axis — see RSI hit 70 as candles go vertical, ATR swell exactly where candles get tall. The early candles with *no* indicator line are the **warm-up window**: an SMA(20) needs 20 bars before its first value. The training pipeline drops those rows (`warmup_rows` in the metrics) for the same reason the chart can't draw them.

**While training.** The Loss plot now shows the *total weighted* loss across all three heads. The accuracy plot is the direction head alone (with its majority baseline line — same yardstick as Stage 2). The two new MAE plots are the regression heads:

- **Return MAE** in log-return units — divide by ~0.01 to think in percent. If it stalls at roughly the average absolute bar move, the head has learned "predict ≈ 0", the regression version of guessing the majority class.
- **Volatility MAE** (standardized) — this one usually *falls convincingly*. Volatility clusters, so the recent past genuinely predicts it. Watching one head learn while another flatlines, off the same trunk, is multi-task learning made visible.

**After training.** The verdict judges the **direction head** — the cross-stage comparable. The honest question for Stage 3: *did the indicators buy a real edge over the majority baseline, or just noise?* Use the runs table to compare against your Stage 2 runs on the same slice. On the overlay, each arrow now carries a predicted return — note how tiny they all are. That's not the model being shy; that's what honest next-bar expectations look like.
