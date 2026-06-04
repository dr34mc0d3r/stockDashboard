# Why We're Doing It

**Why news?** Indicators are transformations of price — they can only re-describe what the market already did. Headlines are *exogenous*: information arriving from outside the price series. If anything can add signal that price history doesn't already contain, it's this category. Whether a daily average of headline tone actually does, at next-bar resolution, is the experiment — and the runs table will give you an honest answer.

**Why FinBERT instead of a word list?** "Tesla *crushes* delivery estimates" is good news; "Tesla *crushed* by delivery miss" is not. Keyword counting can't tell them apart; a transformer reading the whole sentence can. FinBERT is BERT fine-tuned on financial text, so it also knows that "beats estimates" is positive even though "beats" sounds violent. This is the lab's first encounter with a *pretrained* model — we don't train it, we just run it.

**Why run-once + cache?** Scoring 300 headlines costs about a minute of CPU. Scoring them on every training run would make experimentation miserable — and the scores never change. So: score once, aggregate per day, cache in `feature_cache` (the table built for exactly this in Stage 3), and training reads cached numbers forever after. Stage 5 (GDELT) reuses this identical pattern.

**Why the one-day lag?** A bar at 10:00 must not know about a headline published at 15:00 the same day — but a naive "average the day's news onto the day's bars" does exactly that. So every bar reads **yesterday's** aggregate. It costs freshness; it buys honesty. In a lab whose core lesson is leakage discipline, that trade is not optional.
