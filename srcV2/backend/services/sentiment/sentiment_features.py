"""Sentiment feature matrix for training: cached daily aggregates → bar columns.

The read-side counterpart of prep_service: loads the `finbert_daily` rows the
prep job cached, applies the lag + fill rules (aggregate.align_to_bars), and
returns a matrix aligned 1:1 with the training bars — ready to hstack onto the
indicator matrix before build_multitask_dataset.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import FeatureCache
from services.sentiment.aggregate import align_to_bars
from services.sentiment.prep_service import FEATURE_SET


class SentimentNotPrepared(Exception):
    """Raised when a training slice has no cached sentiment coverage."""


def load_daily(session: Session, symbol: str) -> dict:
    """The cached per-day aggregates for a symbol: {date: {net, count}}."""
    rows = session.execute(
        select(FeatureCache).where(
            FeatureCache.symbol == symbol,
            FeatureCache.timeframe == "1d",
            FeatureCache.feature_set == FEATURE_SET,
        )
    ).scalars()
    return {r.ts.date(): {"net": r.payload["net"], "count": r.payload["count"]} for r in rows}


def build_sentiment_matrix(
    session: Session, symbol: str, bar_ts: list[datetime], lag_days: int = 1
) -> tuple[np.ndarray, list[str]]:
    """An (n_bars, 2) sentiment matrix aligned to the given bar timestamps.

    Raises SentimentNotPrepared (with an actionable message) when the cache
    holds nothing for this symbol, or when no bar in the slice can see a
    covered day — both mean "run sentiment prep first".
    """
    daily = load_daily(session, symbol)
    if not daily:
        raise SentimentNotPrepared(
            f"No FinBERT sentiment cached for {symbol}. Run sentiment prep "
            "(section 5 on the Stage 4 page) for this symbol and date range first."
        )
    matrix, names = align_to_bars(bar_ts, daily, lag_days=lag_days)
    if not np.isfinite(matrix).any():
        first = min(daily).isoformat()
        raise SentimentNotPrepared(
            f"The cached sentiment for {symbol} starts {first}, after this "
            "training slice ends. Run sentiment prep covering the slice's dates."
        )
    return matrix, names
