## Full Writeup — Understanding Stage 1

### OHLCV, the atom of market data
Every bar summarises trading over one interval with five numbers: **Open** (first trade),
**High** and **Low** (the extremes), **Close** (last trade), and **Volume** (shares traded).
The Close is the value models usually try to predict; the High/Low capture volatility; and
Volume hints at conviction behind a move.

### Timeframe matters a lot
A `1m` (one-minute) bar and a `1d` (one-day) bar describe the same stock at wildly different
resolutions. One trading day is roughly **390 one-minute bars** but a **single** daily bar.
We default to `1m` here to capture rich detail — but that means a year of one symbol is
~100k rows. Later stages therefore **select a slice** of this data rather than training on
all of it, which keeps things fast on modest hardware.

### Pagination — why downloads don't silently truncate
Alpaca returns at most ~10,000 bars per response and hands back a `next_page_token` when
there's more. Our client **loops on that token** until it's exhausted, so a multi-month
1-minute pull arrives complete instead of being quietly cut off at the first page.

### Idempotent storage (UPSERT)
The `ohlcv_bars` table uses a composite primary key of `(symbol, timeframe, timestamp)`.
When we insert, a duplicate key triggers an **update** instead of an error
(`INSERT … ON DUPLICATE KEY UPDATE`). The practical payoff: you can re-download an
overlapping date range as many times as you like and the row count won't balloon — each
bar exists exactly once.

### A note on time-series leakage
When we start modeling, we must respect the arrow of time: the validation/test data has to
come **after** the training data, never shuffled in. A model that "sees the future" during
training looks brilliant and then fails in the real world. We store bars in strict time
order now precisely so we can split them cleanly later.

### What to try
- Download a few different symbols and timeframes and watch the inventory grow.
- Re-run the same range and confirm the bar count stays the same (idempotency in action).
- Click an inventory row to chart it — pan with drag, zoom with the scroll wheel.
