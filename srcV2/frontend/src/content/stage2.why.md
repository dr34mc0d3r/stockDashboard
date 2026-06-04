## Why We're Doing It

Stage 1 gave us clean, time-ordered data. The natural next question is: **can a model
learn anything predictive from it?** Direction (up/down) is the simplest honest target —
a single binary label — so it's the right place to start before we attempt harder things
like predicting returns or volatility.

We use an **LSTM** because price history is a *sequence*: the order of bars matters, and
recent bars matter more than distant ones. An LSTM reads the window one bar at a time and
carries a memory of what it has seen, which suits time series far better than a model that
treats the 60 bars as an unordered bag of numbers.

Just as important, this stage builds the **machinery every later stage reuses**: the
windowing + leakage-safe split, feature scaling, the background training loop with live
progress, and saving the trained model so it can be loaded again. Stages 3–8 swap in
richer features and bigger models, but the scaffolding is what we lay down here.

A fair warning, and part of the lesson: **next-bar direction on raw price is genuinely
hard**. Accuracy near 50% is normal and *expected* — that's the honest baseline. The goal
here is to understand the technique, not to find a money printer.
