## Full Writeup — Understanding Stage 2

### From bars to supervised windows
A model needs `(input, label)` pairs. We create them by sliding a fixed-length window over
the time series: window *i* is bars `[i … i+seq_len)`, and its label is **1 if the close
`horizon` bars later is higher** than the window's last close, else **0**. Slide forward one
bar and repeat. A few thousand bars becomes a few thousand training examples.

### Why an LSTM
A plain feed-forward network would see the window as a flat list of numbers with no notion
of order. An **LSTM** (Long Short-Term Memory) instead reads the bars *in sequence*, updating
an internal memory at each step through learned "gates" that decide what to keep and what to
forget. We take the memory after the final bar, pass it through one linear layer to a single
number (a **logit**), and interpret `sigmoid(logit)` as the probability of "up".

### Scaling — and fitting it on train only
Raw prices and volume live on wildly different scales (a $400 close next to 2,000,000 shares),
which makes optimization unstable. We **standardize** each feature to roughly mean 0,
variance 1. Crucially, the mean and standard deviation are computed on the **training rows
only**, then applied to validation and test. Computing them over the whole dataset would let
test-set statistics seep into training — a subtle but real **leakage**.

### The time-ordered split
We never shuffle. The oldest 70% of bars is training, the next 15% validation, the final 15%
test — and windows are built **within** each segment so none straddles a boundary. This
mimics reality: you train on the past and are judged on the future. A random split would let
the model peek at tomorrow while learning today, inflating its score dishonestly.

### Reading the charts
- **Loss curves:** training loss should fall steadily. Watch the **validation** loss — when
  it flattens or turns *up* while training loss keeps dropping, the model is **overfitting**.
- **Early stopping** watches validation loss and halts after `patience` epochs without
  improvement, then restores the best weights — so the saved model is the best one seen, not
  the last one.
- **Confusion matrix:** the green diagonal (correct up / correct down) vs. the red off-diagonal
  (misses). A model that just predicts "up" every time shows up as one full column — compare
  its accuracy against the **up-label balance** to know if it actually learned anything.

### What to try
- Raise **hidden units** or **layers** and watch the train/val gap — more capacity overfits
  faster on this much data.
- Lengthen **sequence length**: does more history help, or just slow training?
- Push the **horizon** out (predict 5 bars ahead instead of 1) and see how accuracy moves.
- Train on a **different symbol or a narrower date slice** and compare. Is any edge stable,
  or does it vanish out of sample? That instability *is* the lesson.
