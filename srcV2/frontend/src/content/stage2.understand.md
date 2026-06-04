## What Am I to See — and How to Read It on a Candlestick Chart

You trained a model and got a loss curve, an accuracy number, and a confusion matrix.
Here is how every one of those connects back to the candlestick chart from Stage 1.

### The model's prediction *is* a call on the next candle
Each candle is one bar (open/high/low/close). The model reads the last `seq_len` candles
and answers exactly one yes/no question: **will the next candle close higher than this one?**
So a single prediction is an arrow you could draw on the boundary between two candles —
a green ▲ ("next close is higher") or a red ▼ ("next close is lower"). Nothing more.

That's deliberately humble. It does **not** predict the price, the size of the move, or
where the high/low will be — just the *sign* of the next close-to-close change.

### Reading your results as marks on the chart
Imagine drawing the model's arrow on every candle, then checking it against the candle that
actually came next:

- **Test accuracy** = the fraction of those arrows that pointed the right way. **52%** means
  that out of 100 candles, it called 52 directions correctly — barely better than flipping a
  coin at each candle.
- **Confusion matrix**, in candle terms:
  - **TP** — drew ▲ and the next candle *did* close higher (a correct up-call).
  - **TN** — drew ▼ and it *did* close lower (a correct down-call).
  - **FP** — drew ▲ but the candle fell (a wrong green arrow).
  - **FN** — drew ▼ but it rose (a missed up-move).
  - A model that just paints ▲ on **every** candle shows up as one full column — that's why
    we compare its accuracy to the **up-label balance**. If 50% of candles close up and the
    model scores 50%, it learned nothing beyond "guess up."
- **Loss** measures *confidence-weighted* correctness. A model that outputs 0.5 on every
  candle ("no opinion") sits at loss `ln(2) ≈ 0.693`. When loss drops, the model is starting
  to *lean* — say 0.55 toward up — on some candles. Whether that lean is right out-of-sample
  is what validation loss tells you.

### Why ~50% *looks like noise* on the chart
Pull up the same symbol on the Stage 1 chart and eyeball it: on a 1-minute chart, whether the
next candle is green or red is almost independent of the recent candles. The arrows would
scatter with no visible pattern. That isn't a bug — it's the efficient-market reality at this
timescale, and it's exactly why the honest baseline is ~50%.

### How to actually *use* this
- **Don't trade a 50% single-candle call.** With the bid/ask spread and fees, a coin-flip edge
  is negative expectancy. The lesson here is the *method*, not a signal.
- **Change what makes a chart predictable, and watch the number move:**
  - **Coarser candles** — train on a 1h or 1d series (if stored). Daily candles carry more
    trend/structure than 1-minute noise, so any real edge is easier to find.
  - **Longer horizon** — predict the candle 5 or 10 bars ahead instead of 1. You're now asking
    about a *swing* rather than the next flicker.
  - **More signal per candle** — that's Stage 3: technical indicators (moving averages, RSI,
    MACD…) feed the model the same context a chart-reader uses, instead of raw OHLC alone.
- **Tie it to candlestick patterns.** Classic patterns (engulfing, doji, three-soldiers) are
  just *local candle shapes*. An LSTM over returns is literally trying to learn whether such
  shapes predict the next candle. When you see ~50%, you're watching the model conclude that,
  at 1-minute resolution, they mostly don't.

### Try this to feel it
Run a model, note its test accuracy, then open the **Stage 1 chart** for the same symbol.
Walk a few candles forward and ask, candle by candle, "did the next one close higher?" After a
dozen, you'll have an intuition for why a ~52% score is both *real* (the plumbing works) and
*useless for trading* (the edge is inside the noise). Then come back, switch to a coarser
timeframe or longer horizon, and see whether the chart — and the accuracy — tell a different story.
