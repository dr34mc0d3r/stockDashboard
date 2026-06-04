# What Am I to See and Learn

**In the headline browser.** Read FinBERT's calls. Most are good ("Disappointed… Undermines" → strongly negative), some are instructively wrong or ambiguous — a headline mentioning five tickers gets one score that applies to all of them, sarcasm misfires, and "demand slides, but police fleet buys" is genuinely mixed. Per-headline noise is *why* we aggregate per day: averages wash out individual mistakes.

**In the coverage timeline.** News is lumpy — clusters of red around bad weeks, quiet stretches with no bars at all. Two practical reads: (1) your training slice must overlap the covered range or the sentiment columns are useless; (2) notice the cap behavior — fetching is oldest-first up to the headline cap, so a 300-headline budget may cover only the first month of the range you asked for. The prep stats tell you the real covered span.

**While training.** Watch the same per-head charts as Stage 3. The honest question is *relative*: run the **Indicators + sentiment** preset, then the **Stage 3 rematch** (identical, sentiment off), and compare the two rows in the runs table. The edge column difference *is* the value of news for this slice. Expect it to be small and often within noise — daily-averaged, day-lagged sentiment at next-bar resolution is a blunt instrument. A real effect, when published research finds one, tends to live at longer horizons.

**The architecture lesson.** Look at how little changed to add a whole new data modality: a fetch client, a scorer, an aggregation, and *two more columns* in the feature matrix. The dataset builder, model, trainer, verdict and overlay are untouched. That's what the Stage 3 refactor bought — and Stage 5 (GDELT) will ride the same rails.
