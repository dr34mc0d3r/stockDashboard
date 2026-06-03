"""Tests for the Stage 2 dataset builder — focused on the leakage guards.

The dataset module is loaded directly by file path so these stay pure-logic:
no DB, no config/.env, no sys.path changes (so the srcV1 suite is untouched).
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

# Load services/datasets.py as a standalone module (its pure functions don't
# import the DB layer — that lives behind a local import in load_bars).
_PATH = Path(__file__).resolve().parent.parent / "services" / "datasets.py"
_spec = importlib.util.spec_from_file_location("datasets_under_test", _PATH)
datasets = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass can resolve cls.__module__ during the load.
sys.modules[_spec.name] = datasets
_spec.loader.exec_module(datasets)

build_dataset = datasets.build_dataset
Scaler = datasets.Scaler
_window_segment = datasets._window_segment


def _ramp(n, start=100.0, step=1.0, vol=1000):
    """Monotonic-rising OHLCV array of n bars (close strictly increasing)."""
    close = start + step * np.arange(n)
    return np.column_stack(
        [close, close + 0.5, close - 0.5, close, np.full(n, vol)]
    ).astype("float64")


# --- the core leakage guard: scaler fit on TRAIN feature rows only ---

def test_scaler_uses_train_feature_rows_only_not_whole_series():
    # Features are returns. Train region = low volatility; val/test = high
    # volatility. If the scaler peeked at val/test, its return std would balloon.
    rng = np.random.default_rng(0)
    n = 400
    rets = np.empty(n)
    rets[:280] = rng.normal(0, 0.001, 280)        # train: low-vol returns
    rets[280:] = rng.normal(0, 0.05, n - 280)     # val+test: high-vol returns
    close = 100.0 * np.exp(np.cumsum(rets))
    raw = np.column_stack([close, close, close, close, np.full(n, 1000.0)]).astype("float64")

    ds = build_dataset(raw, seq_len=20, horizon=1, split=(0.7, 0.15, 0.15))

    feats, _ = datasets._return_features(raw)      # the actual model features
    m = len(feats)                                  # n - 1
    i_train = int(m * 0.7)
    expected_mean = feats[:i_train].mean(axis=0)
    expected_std = feats[:i_train].std(axis=0)
    expected_std[expected_std < 1e-8] = 1.0         # mirror the near-zero guard

    np.testing.assert_allclose(ds.scaler.mean, expected_mean)
    np.testing.assert_allclose(ds.scaler.std, expected_std)

    # And crucially NOT the whole-series stats (that would be leakage): the
    # close-return std fit on train must be far below the whole-series std.
    whole_std = feats.std(axis=0)
    assert ds.scaler.std[3] < whole_std[3] * 0.5


def test_scaler_standardizes_train_features_to_zero_mean_unit_std():
    raw = _ramp(400)
    ds = build_dataset(raw, seq_len=20, horizon=1)
    feats, _ = datasets._return_features(raw)
    i_train = int(len(feats) * 0.7)
    scaled_train = ds.scaler.transform(feats[:i_train])
    np.testing.assert_allclose(scaled_train.mean(axis=0), 0, atol=1e-9)
    # O/H/L/C return columns vary -> unit std; volume is constant -> guarded to 0.
    np.testing.assert_allclose(scaled_train[:, :4].std(axis=0), 1, atol=1e-6)


# --- time-ordered, per-segment windowing (no cross-boundary leakage) ---

def test_windows_are_built_within_each_segment():
    n, seq_len, horizon = 500, 60, 1
    ds = build_dataset(raw=_ramp(n), seq_len=seq_len, horizon=horizon, split=(0.7, 0.15, 0.15))

    m = n - 1  # the return diff drops the first bar
    i_train = int(m * 0.7)
    i_val = int(m * 0.85)
    seg_lens = {"train": i_train, "val": i_val - i_train, "test": m - i_val}

    def expected(seg_len):
        return max(0, seg_len - seq_len - horizon + 1)

    assert ds.X_train.shape[0] == expected(seg_lens["train"])
    assert ds.X_val.shape[0] == expected(seg_lens["val"])
    assert ds.X_test.shape[0] == expected(seg_lens["test"])

    # Per-segment count is strictly fewer than naive whole-series windowing,
    # because each split boundary drops (seq_len + horizon - 1) windows.
    naive = expected(m)
    total = ds.X_train.shape[0] + ds.X_val.shape[0] + ds.X_test.shape[0]
    assert total < naive


def test_build_dataset_labels_track_real_price_after_returns_refactor():
    # Features are returns, but labels must stay anchored to the *raw price*:
    # a strictly rising series is all "up", a strictly falling one all "down".
    up = build_dataset(_ramp(300), seq_len=20, horizon=1)
    assert (up.y_train == 1).all() and (up.y_val == 1).all() and (up.y_test == 1).all()

    down = build_dataset(_ramp(300)[::-1].copy(), seq_len=20, horizon=1)
    assert (down.y_train == 0).all() and (down.y_val == 0).all() and (down.y_test == 0).all()


def test_window_shapes_and_feature_count():
    ds = build_dataset(_ramp(300), seq_len=30, horizon=1)
    assert ds.n_features == 5
    assert ds.X_train.shape[1:] == (30, 5)
    assert ds.X_train.shape[0] == ds.y_train.shape[0]


# --- label correctness (direction over the horizon) ---

def test_labels_all_up_for_rising_series():
    feats = _ramp(100)
    closes = feats[:, datasets.CLOSE_IDX]
    X, y = _window_segment(feats, closes, seq_len=10, horizon=1)
    assert len(y) > 0
    assert (y == 1).all()  # strictly rising -> every next bar is "up"


def test_labels_all_down_for_falling_series():
    feats = _ramp(100)[::-1].copy()  # strictly falling
    closes = feats[:, datasets.CLOSE_IDX]
    X, y = _window_segment(feats, closes, seq_len=10, horizon=1)
    assert len(y) > 0
    assert (y == 0).all()


def test_horizon_shifts_the_label_target():
    # close = [0,1,2,...]; with horizon h, label compares close[end-1+h] vs close[end-1],
    # always rising here, so labels stay 1 but the window count shrinks with horizon.
    feats = _ramp(80)
    closes = feats[:, datasets.CLOSE_IDX]
    _, y1 = _window_segment(feats, closes, seq_len=10, horizon=1)
    _, y5 = _window_segment(feats, closes, seq_len=10, horizon=5)
    assert len(y5) == len(y1) - 4  # larger horizon consumes more tail bars


# --- guards ---

def test_too_few_bars_raises():
    with pytest.raises(ValueError, match="Not enough bars"):
        build_dataset(_ramp(40), seq_len=60, horizon=1)
