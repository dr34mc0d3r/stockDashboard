"""Daily sentiment aggregation and bar alignment — pure functions.

This is the leakage-sensitive heart of Stage 4, so it is deliberately tiny,
dependency-free (numpy + stdlib only — its tests load it standalone by file
path, like datasets.py), and explicit about its two rules:

1. **Lag.** A bar on day D reads day (D − lag_days)'s aggregate. Scoring day
   D's *own* full-day news onto its earlier intraday bars would leak headlines
   published in the afternoon into the morning's features. Lag 1 is honest.
2. **Fill.** Before the first day that can see a covered day: NaN (the dataset
   builder trims those rows — we genuinely have no sentiment yet). From then
   on, a source day with no news yields net=0, count=0 — *defined* neutral,
   not NaN (so no in-corpus bar is dropped) and **not** forward-filled
   (yesterday's stale optimism is not today's news).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import numpy as np

# Column names follow the indicator "source.line" convention.
FEATURE_NAMES = ["sentiment.net", "sentiment.count"]


def daily_aggregate(articles: list[dict]) -> dict[date, dict]:
    """Collapse scored articles into per-calendar-day aggregates.

    ``articles``: dicts with ``ts`` (datetime) and FinBERT ``pos``/``neg``
    scores; unscored rows (pos is None) are skipped. Returns
    ``{day: {"net": mean(pos) − mean(neg), "count": n_articles}}``.
    """
    by_day: dict[date, list[dict]] = {}
    for a in articles:
        if a.get("pos") is None or a.get("neg") is None:
            continue
        by_day.setdefault(a["ts"].date(), []).append(a)

    return {
        d: {
            "net": float(np.mean([x["pos"] for x in rows]) - np.mean([x["neg"] for x in rows])),
            "count": len(rows),
        }
        for d, rows in by_day.items()
    }


def align_to_bars(
    bar_ts: list[datetime], daily: dict[date, dict], lag_days: int = 1
) -> tuple[np.ndarray, list[str]]:
    """Map daily aggregates onto bars: an (n_bars, 2) matrix aligned 1:1.

    Columns are ``sentiment.net`` and ``sentiment.count`` (= log1p of the
    article count, so 0 articles → 0.0 and the scale stays tame). See the
    module docstring for the lag and fill rules.
    """
    n = len(bar_ts)
    if not daily:
        return np.full((n, len(FEATURE_NAMES)), np.nan), list(FEATURE_NAMES)

    first_covered = min(daily)
    lag = timedelta(days=int(lag_days))
    rows = []
    for ts in bar_ts:
        source_day = ts.date() - lag
        if source_day < first_covered:
            rows.append([np.nan, np.nan])  # pre-corpus: trimmed by the dataset builder
        elif source_day in daily:
            agg = daily[source_day]
            rows.append([agg["net"], math.log1p(agg["count"])])
        else:
            rows.append([0.0, 0.0])  # covered era, quiet day: defined neutral
    return np.asarray(rows, dtype=np.float64), list(FEATURE_NAMES)
