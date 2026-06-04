## What We're Doing

This stage trains our **first model**: a small **LSTM** (a type of recurrent neural
network) that looks at a window of recent bars and predicts a single yes/no question —
**will the next bar close higher than this one?**

You pick a stored `(symbol, timeframe)` from Stage 1, optionally narrow it to a date
slice, set a few hyperparameters, and hit **Train**. The backend slices your data into
overlapping **windows** (e.g. 60 bars each), labels each window by what the price did
*next*, and trains the LSTM to tell "up" windows from "down" windows.

Training runs in the background. You'll watch the **loss curves** fall epoch by epoch,
then see how the finished model scores on data it never trained on — its **test
accuracy** and a **confusion matrix** of right vs. wrong calls.
