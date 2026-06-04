# What We're Doing

Stage 2 fed the model **raw OHLCV** and asked one question (up or down?). This stage upgrades both sides of that sentence.

**Better inputs:** we add up to **10 technical indicators** as features — SMA, EMA, Bollinger Bands, VWAP on the price scale; RSI, MACD, Stochastic, ATR, ADX, OBV on their own scales. You toggle each one on the chart, tune its parameters, and *see exactly what the model will see* — the chart preview and the training pipeline are fed by the **same backend functions**, so they can never disagree.

**Better outputs:** instead of one head, the model now has **three** sharing one LSTM trunk:

- **Direction** — will the next bar close higher? (same as Stage 2, so results stay comparable)
- **Return** — *how much* will price move over the horizon (a log return)?
- **Volatility** — how rough will the next `vol_window` bars be (realized volatility)?

Training runs in the background exactly like Stage 2 — live loss curves, early stopping, a saved artifact — but now you watch **per-head metrics**, and the prediction overlay shows each arrow's predicted return next to it.
