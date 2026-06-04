"""Tests for the Stage 4 sentiment aggregation — the leakage rules, hard.

Standalone-importlib load (like test_datasets.py): pure logic, no DB, no app.
"""

import importlib.util
import math
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np

_PATH = Path(__file__).resolve().parent.parent / "services" / "sentiment" / "aggregate.py"
_spec = importlib.util.spec_from_file_location("aggregate_under_test", _PATH)
aggregate = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = aggregate
_spec.loader.exec_module(aggregate)

daily_aggregate = aggregate.daily_aggregate
align_to_bars = aggregate.align_to_bars


def art(day, hour, pos, neg):
    return {"ts": datetime(2025, 6, day, hour), "pos": pos, "neg": neg, "neutral": 0.0}


def bars_on(days, per_day=3):
    """A few intraday bar timestamps on each given June-2025 day."""
    return [datetime(2025, 6, d, 9 + i) for d in days for i in range(per_day)]


def test_daily_aggregate_means_and_counts():
    daily = daily_aggregate([art(2, 9, 0.9, 0.0), art(2, 15, 0.1, 0.5), art(3, 10, 0.0, 0.8)])
    # Day 2: mean(pos)=0.5, mean(neg)=0.25 -> net 0.25, count 2.
    assert math.isclose(daily[date(2025, 6, 2)]["net"], 0.25, rel_tol=1e-9)
    assert daily[date(2025, 6, 2)]["count"] == 2
    assert math.isclose(daily[date(2025, 6, 3)]["net"], -0.8, rel_tol=1e-9)


def test_unscored_articles_are_skipped():
    daily = daily_aggregate([{"ts": datetime(2025, 6, 2, 9), "pos": None, "neg": None}])
    assert daily == {}


def test_lag_one_maps_yesterdays_news_onto_today():
    # News only on June 2. With lag 1, June 3's bars read June 2's aggregate;
    # June 2's own bars must NOT see it (that would be intraday leakage).
    daily = daily_aggregate([art(2, 9, 1.0, 0.0)])
    matrix, names = align_to_bars(bars_on([2, 3]), daily, lag_days=1)

    assert names == ["sentiment.net", "sentiment.count"]
    june2_rows, june3_rows = matrix[:3], matrix[3:]
    # June 2 bars look at June 1 (pre-corpus) -> NaN.
    assert np.isnan(june2_rows).all()
    # June 3 bars read June 2: net=1.0, count=log1p(1).
    assert np.allclose(june3_rows[:, 0], 1.0)
    assert np.allclose(june3_rows[:, 1], math.log1p(1))


def test_nan_before_first_covered_day_then_defined_forever():
    # Coverage starts June 2. June 5 has no news.
    daily = daily_aggregate([art(2, 9, 0.6, 0.2), art(3, 9, 0.1, 0.1)])
    matrix, _ = align_to_bars(bars_on([2, 3, 4, 5, 6]), daily, lag_days=1)

    by_day = matrix.reshape(5, 3, 2)  # (day, bars-per-day, cols)
    assert np.isnan(by_day[0]).all()  # June 2 sees June 1: pre-corpus
    assert np.isfinite(by_day[1:]).all()  # everything after is DEFINED
    # June 5 + June 6 read uncovered days (4, 5): exactly neutral zero...
    assert np.allclose(by_day[3], 0.0)


def test_no_forward_fill_on_quiet_days():
    # Strong positive news June 2, silence June 3. June 4 must read 0.0 —
    # NOT June 2's stale +0.8 (forward-filling would overstate signal).
    daily = daily_aggregate([art(2, 9, 0.9, 0.1)])
    matrix, _ = align_to_bars(bars_on([3, 4]), daily, lag_days=1)

    june3 = matrix[:3]  # reads June 2 -> the real aggregate
    june4 = matrix[3:]  # reads June 3 -> quiet -> zeros
    assert np.allclose(june3[:, 0], 0.8)
    assert np.allclose(june4, 0.0)


def test_lag_zero_is_possible_but_distinct():
    # lag_days=0 exists for comparison runs; the same-day bars then see the
    # aggregate directly (the lesson explains why that's a leak).
    daily = daily_aggregate([art(2, 9, 1.0, 0.0)])
    matrix, _ = align_to_bars(bars_on([2]), daily, lag_days=0)
    assert np.allclose(matrix[:, 0], 1.0)


def test_empty_corpus_is_all_nan():
    matrix, names = align_to_bars(bars_on([2, 3]), {}, lag_days=1)
    assert np.isnan(matrix).all()
    assert matrix.shape == (6, 2)
    assert names == ["sentiment.net", "sentiment.count"]
