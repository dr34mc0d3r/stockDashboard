# Full Writeup — Understanding Stage 4

## What FinBERT is

BERT is a transformer encoder pretrained to fill in masked words across billions of sentences — in doing so it learns grammar, context, and a lot of world knowledge. **FinBERT** (ProsusAI/finbert) takes that pretrained core and *fine-tunes* it on financial text labeled positive/negative/neutral. The result reads a headline as a whole sentence: "crushes estimates" scores positive, "crushed by estimates" negative — distinctions a keyword counter cannot make. We run it frozen: no training, just inference. One forward pass per headline → softmax over three classes → the three probabilities you see in the browser.

## The prep pipeline, step by step

1. **Fetch** — Alpaca's news endpoint, with the same auth and `next_page_token` pagination as the Stage 1 bars client. Headlines only; capped (default 300) because inference costs real CPU time. Articles store under their stable Alpaca id, so re-fetching is a no-op.
2. **Score** — batches of 16 headlines, truncated to 64 tokens, through FinBERT on 2 CPU threads. Scores write back onto each article row; already-scored rows are skipped, which makes prep *resumable* — an interrupted run continues where it left off.
3. **Aggregate** — per calendar day: `net = mean(pos) − mean(neg)` (≈ −1…+1) and the headline count. Cached in `feature_cache` under `finbert_daily`.

## The leakage rules (the heart of the stage)

- **Lag 1.** A bar on day D reads day D−1's aggregate. Same-day news would leak afternoon headlines into morning bars.
- **NaN before, zero after.** Bars before the corpus's first covered day get NaN — the dataset builder's warm-up trim drops them, exactly as it drops indicator warm-up. After that, a quiet day is a *defined* `net=0, count=0` — neutral, "no news today".
- **No forward-fill.** Monday's euphoria is not Wednesday's feature. Forward-filling stale sentiment looks harmless and quietly overstates how much information the model has.

These three rules live in one tiny pure module (`aggregate.py`) with the hardest tests in the stage pointed at them.

## Why the regression heads see it too

The two sentiment columns enter the shared trunk, so all three heads can use them. Plausibly volatility benefits most — headline *count* is a decent proxy for "something is happening" — which you can check directly in the vol head's MAE.

## Reading the A/B honestly

Train the same configuration twice — sentiment on, sentiment off — on the same slice. The runs table's edge column difference is the entire result. Three sober expectations: the corpus is small (a few hundred headlines); the aggregate is daily and lagged while the target is next-bar; and one symbol's slice is one sample. A ±1–2pt difference within the noise band is the *normal* outcome. What you're learning is the method: isolate one variable, control everything else, and respect the significance test — the discipline that separates a measurement from a wish.

## What to try changing

- `lag_days: 0` vs `1` on the same slice — the leaky version often scores *better*. That's the trap, demonstrated.
- Sentiment-only vs indicators-only vs both: which two combine best?
- A bigger corpus cap on a longer slice — does coverage density change the result?
- Check `feature_set` in two identical preps: the second run does no FinBERT work at all.
