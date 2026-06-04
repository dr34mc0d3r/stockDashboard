"""Tests for the Stage 3 multi-task dataset builder.

Same standalone-import pattern as test_datasets.py: pure logic, no DB. The
indicator matrix is passed in as a plain numpy fixture, exactly as the feature
pipeline would supply it (np.nan during warm-up).
"""

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

_PATH = Path(__file__).resolve().parent.parent / "services" / "datasets.py"
_spec = importlib.util.spec_from_file_location("mt_datasets_under_test", _PATH)
datasets = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = datasets
_spec.loader.exec_module(datasets)

build_multitask_dataset = datasets.build_multitask_dataset
TargetStats = datasets.TargetStats


def _ramp(n, start=100.0, step=1.0, vol=1000):
    """Monotonic-rising OHLCV array of n bars (close strictly increasing)."""
    close = start + step * np.arange(n)
    return np.column_stack([close - 0.5, close + 1.0, close - 1.0, close, np.full(n, float(vol))])


def _fake_indicators(n, k=2, warmup=10):
    """A (n, k) indicator matrix: NaN for the first `warmup` rows, then values."""
    m = np.tile(np.linspace(1.0, 2.0, n).reshape(-1, 1), (1, k))
    m[:warmup] = np.nan
    return m


def test_warmup_rows_are_trimmed_and_counted():
    raw = _ramp(120)
    ind = _fake_indicators(120, k=3, warmup=15)
    ds = build_multitask_dataset(raw, ind, ["a", "b", "c"], seq_len=10, horizon=1, vol_window=2)

    # _return_features drops bar 0, then trim starts at the first row where all
    # indicator columns (aligned to bars 1..n-1) are finite: index 15-1 = 14.
    assert ds.warmup_rows == 14
    assert ds.n_features == 5 + 3
    assert ds.feature_names[:5] == ["ret_open", "ret_high", "ret_low", "ret_close", "log_volume"]
    # No NaN anywhere in the model inputs.
    for X in (ds.X_train, ds.X_val, ds.X_test):
        assert np.isfinite(X).all()


def test_works_with_zero_indicators():
    raw = _ramp(120)
    ds = build_multitask_dataset(raw, np.empty((120, 0)), [], seq_len=10, horizon=1, vol_window=2)
    assert ds.n_features == 5
    assert ds.warmup_rows == 0
    assert len(ds.X_train) > 0


def test_scaler_fit_on_train_rows_only():
    # A level jump late in the series (inside the test split) must not leak
    # into the scaler stats.
    raw = _ramp(200)
    raw[180:, :4] += 500.0  # price jump in the last 10%
    ind = _fake_indicators(200, k=1, warmup=5)
    ds = build_multitask_dataset(raw, ind, ["x"], seq_len=10, horizon=1, vol_window=2)

    raw_no_jump = _ramp(200)
    ds_clean = build_multitask_dataset(raw_no_jump, ind, ["x"], seq_len=10, horizon=1, vol_window=2)
    # Train split ends well before the jump, so the scaler stats match exactly.
    assert np.allclose(ds.scaler.mean, ds_clean.scaler.mean)
    assert np.allclose(ds.scaler.std, ds_clean.scaler.std)


def test_three_targets_on_a_steady_ramp():
    # Strictly rising closes: direction all 1; the standardized return and the
    # realized vol are recoverable through the stored TargetStats.
    raw = _ramp(150, step=1.0)
    ds = build_multitask_dataset(raw, np.empty((150, 0)), [], seq_len=10, horizon=1, vol_window=2)

    assert (ds.y_dir_train == 1).all() and (ds.y_dir_test == 1).all()

    # Un-standardize a train return and check it equals ln(close[e+1]/close[e]).
    rets = ds.ret_stats.unstandardize(ds.y_ret_train)
    assert (rets > 0).all()
    # First train window ends at the segment's bar index seq_len-1.
    # Its return is one of the ramp's ln((c+1)/c) values — small and positive.
    assert rets.max() < math.log(1.05)

    # Realized vol on an exact ramp is the std of near-equal log returns — tiny.
    vols = np.expm1(ds.vol_stats.unstandardize(ds.y_vol_train))
    assert (vols >= 0).all()
    assert vols.max() < 1e-3


def test_direction_label_matches_future_close():
    # A zig-zag series: label must equal "did close rise `horizon` bars later".
    n = 80
    close = 100 + np.sin(np.arange(n) * 1.3) * 5
    raw = np.column_stack([close, close + 1, close - 1, close, np.full(n, 1000.0)])
    ds = build_multitask_dataset(
        raw, np.empty((n, 0)), [], seq_len=5, horizon=2, vol_window=2, split=(1.0, 0.0, 0.0)
    )
    closes = close[1:]  # aligned closes after the return-feature drop
    for w in range(len(ds.y_dir_train)):
        e = w + 5 - 1  # window end index in the (single) train segment
        expected = 1 if closes[e + 2] > closes[e] else 0
        assert ds.y_dir_train[w] == expected


def test_lookahead_shrinks_window_count():
    raw = _ramp(100)
    small = build_multitask_dataset(
        raw, np.empty((100, 0)), [], seq_len=10, horizon=1, vol_window=2, split=(1.0, 0.0, 0.0)
    )
    big = build_multitask_dataset(
        raw, np.empty((100, 0)), [], seq_len=10, horizon=1, vol_window=10, split=(1.0, 0.0, 0.0)
    )
    # A longer vol window needs more future bars per window -> fewer windows.
    assert len(big.X_train) == len(small.X_train) - 8  # lookahead 10 vs 2


def test_empty_split_raises_helpful_error():
    # Enough bars to pass the global guard, but the 15% val split is too short
    # to fit even one (seq_len + lookahead) window -> a clear error, not a
    # silently empty validation set.
    raw = _ramp(140)
    with pytest.raises(ValueError, match="val split"):
        build_multitask_dataset(raw, np.empty((140, 0)), [], seq_len=20, horizon=1, vol_window=2)


def test_too_few_bars_raises_helpful_error():
    raw = _ramp(30)
    with pytest.raises(ValueError, match="Not enough usable bars"):
        build_multitask_dataset(raw, np.empty((30, 0)), [], seq_len=20, horizon=1, vol_window=5)


def test_all_nan_indicators_raise():
    raw = _ramp(60)
    ind = np.full((60, 2), np.nan)
    with pytest.raises(ValueError, match="warmed up"):
        build_multitask_dataset(raw, ind, ["a", "b"], seq_len=10, horizon=1, vol_window=2)


def test_target_stats_roundtrip():
    y = np.array([0.1, -0.2, 0.3, 0.0])
    stats = TargetStats.fit(y)
    z = stats.standardize(y)
    assert math.isclose(z.mean(), 0.0, abs_tol=1e-12)
    assert np.allclose(stats.unstandardize(z), y)
    # Degenerate (constant) targets fall back to std=1 instead of exploding.
    flat = TargetStats.fit(np.zeros(5))
    assert flat.std == 1.0
