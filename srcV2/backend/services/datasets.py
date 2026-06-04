"""Dataset builder for the Lab stages.

Turns a time-ordered list of OHLCV bars into supervised sliding windows with a
**time-ordered** train/val/test split and feature scaling **fit on train only**.

Features are **returns, not raw price levels.** Feeding standardized price levels
to the model is a trap: a trending series has a large level variance, so dividing
by that std crushes the bar-to-bar changes (where direction signal lives) toward
zero — the model sees a smooth ramp and can only output the base rate (~0.5). We
instead derive per-bar features relative to the previous close
(``ln(open/prev_close)``, …, ``ln(close/prev_close)``) plus ``log1p(volume)``,
which are stationary and scale-free, so standardization behaves and real signal
survives. **Labels are still taken from the raw close price.**

Leakage guards (the cardinal sin in time-series forecasting):
  1. The split is by time, not random — train is the oldest slice, test the newest.
  2. The scaler's mean/std are computed on the training rows only, then applied to
     all splits. Windows are built *within* each contiguous segment, so no window
     ever straddles a split boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

# Raw OHLCV column order as loaded from the DB. Model features are *derived* from
# these (returns, below); CLOSE_IDX locates the price column used for labels.
FEATURE_COLS = ("open", "high", "low", "close", "volume")
CLOSE_IDX = FEATURE_COLS.index("close")
N_FEATURES = 5  # ln-returns of O/H/L/C vs prev close + log1p(volume)

# Std floor for the scaler. Kept local (not in constants.py) on purpose:
# tests/test_datasets.py loads this module standalone by file path, so it must
# not import sibling backend modules.
_STD_EPS = 1e-8


def _return_features(raw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert raw OHLCV levels into stationary per-bar return features.

    Returns ``(feats, aligned_closes)`` where row k of ``feats`` describes raw
    bar ``k+1`` (the first bar is dropped — it has no previous close), and
    ``aligned_closes[k]`` is that bar's raw close, so labels stay anchored to the
    real price. Both have length ``len(raw) - 1``.
    """
    closes = raw[:, CLOSE_IDX]
    prev_close = closes[:-1]  # denominators for bars 1..n-1
    o, h, low, c = raw[1:, 0], raw[1:, 1], raw[1:, 2], raw[1:, 3]
    v = raw[1:, 4]
    feats = np.column_stack(
        [
            np.log(o / prev_close),
            np.log(h / prev_close),
            np.log(low / prev_close),
            np.log(c / prev_close),  # the bar's return — the headline feature
            np.log1p(v),
        ]
    )
    return feats, closes[1:]


@dataclass
class Scaler:
    """Standardizes features using stats fit on the training split only."""

    mean: np.ndarray
    std: np.ndarray

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.std

    def to_dict(self) -> dict:
        return {"mean": self.mean.tolist(), "std": self.std.tolist()}

    @classmethod
    def from_dict(cls, d: dict) -> Scaler:
        return cls(
            mean=np.asarray(d["mean"], dtype=np.float64), std=np.asarray(d["std"], dtype=np.float64)
        )


@dataclass
class Dataset:
    """Windowed, scaled, split arrays ready for a torch DataLoader."""

    X_train: np.ndarray  # (n, seq_len, n_features)
    y_train: np.ndarray  # (n,)  binary direction labels
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    scaler: Scaler
    n_features: int

    @property
    def class_balance(self) -> dict:
        """Fraction of 'up' labels per split — a sanity check for skew."""

        def up(y: np.ndarray) -> float:
            return round(float(y.mean()), 4) if len(y) else 0.0

        return {"train": up(self.y_train), "val": up(self.y_val), "test": up(self.y_test)}


def load_bars(
    session: Session, symbol: str, timeframe: str, start: str | None = None, end: str | None = None
) -> np.ndarray:
    """Load OHLCV rows oldest-first as a float64 array, columns = FEATURE_COLS."""
    from models import OhlcvBar  # local import: keeps the pure logic DB-free

    # Symbols arrive canonical (schemas.normalize_symbol runs at the API edge).
    stmt = select(OhlcvBar).where(OhlcvBar.symbol == symbol, OhlcvBar.timeframe == timeframe)
    if start:
        stmt = stmt.where(OhlcvBar.ts >= start)
    if end:
        stmt = stmt.where(OhlcvBar.ts <= end)
    rows = session.execute(stmt.order_by(OhlcvBar.ts.asc())).scalars().all()
    return np.array(
        [
            [float(b.open), float(b.high), float(b.low), float(b.close), float(b.volume)]
            for b in rows
        ],
        dtype=np.float64,
    )


def _window_segment(
    feats: np.ndarray, closes: np.ndarray, seq_len: int, horizon: int
) -> tuple[np.ndarray, np.ndarray]:
    """Sliding windows over one contiguous segment.

    Window i = feats[i : i+seq_len]; label = 1 if the close `horizon` bars after
    the window's last bar is higher than that last bar's close, else 0.
    """
    n = len(feats)
    last = n - horizon  # last usable window-end index (exclusive bound below)
    xs, ys = [], []
    for i in range(0, last - seq_len + 1):
        end = i + seq_len  # one past the window's last bar
        ref_close = closes[end - 1]
        fut_close = closes[end - 1 + horizon]
        xs.append(feats[i:end])
        ys.append(1 if fut_close > ref_close else 0)
    if not xs:
        return (np.empty((0, seq_len, feats.shape[1])), np.empty((0,), dtype=np.int64))
    return np.stack(xs), np.asarray(ys, dtype=np.int64)


# ---------------------------------------------------------------------------
# Stage 3: multi-task dataset (direction + return + volatility)
# ---------------------------------------------------------------------------
# NOTE: this module deliberately never imports the indicator code — the caller
# (services/features/feature_pipeline.py) computes the indicator matrix and
# passes it in, so this file stays loadable standalone by its tests.


@dataclass
class TargetStats:
    """Train-split mean/std used to standardize one regression target."""

    mean: float
    std: float

    def standardize(self, y: np.ndarray) -> np.ndarray:
        return (y - self.mean) / self.std

    def unstandardize(self, y: np.ndarray) -> np.ndarray:
        return y * self.std + self.mean

    def to_dict(self) -> dict:
        return {"mean": self.mean, "std": self.std}

    @classmethod
    def fit(cls, y: np.ndarray) -> TargetStats:
        std = float(y.std()) if len(y) else 1.0
        return cls(mean=float(y.mean()) if len(y) else 0.0, std=std if std > _STD_EPS else 1.0)

    @classmethod
    def from_dict(cls, d: dict) -> TargetStats:
        return cls(mean=d["mean"], std=d["std"])


@dataclass
class MultiTaskDataset:
    """Windowed, scaled, split arrays with three label sets per window."""

    X_train: np.ndarray
    y_dir_train: np.ndarray  # binary direction (as Stage 2)
    y_ret_train: np.ndarray  # standardized log return over `horizon`
    y_vol_train: np.ndarray  # standardized log1p realized vol over `vol_window`
    X_val: np.ndarray
    y_dir_val: np.ndarray
    y_ret_val: np.ndarray
    y_vol_val: np.ndarray
    X_test: np.ndarray
    y_dir_test: np.ndarray
    y_ret_test: np.ndarray
    y_vol_test: np.ndarray
    scaler: Scaler
    n_features: int
    feature_names: list[str]
    ret_stats: TargetStats
    vol_stats: TargetStats
    warmup_rows: int  # rows dropped while indicators were still warming up

    @property
    def class_balance(self) -> dict:
        """Fraction of 'up' labels per split (direction head)."""

        def up(y: np.ndarray) -> float:
            return round(float(y.mean()), 4) if len(y) else 0.0

        return {
            "train": up(self.y_dir_train),
            "val": up(self.y_dir_val),
            "test": up(self.y_dir_test),
        }


def _window_segment_multitask(
    feats: np.ndarray, closes: np.ndarray, seq_len: int, horizon: int, vol_window: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sliding windows over one contiguous segment, with three labels each.

    For a window ending at bar e (= i + seq_len - 1):
      direction  = 1 if close[e + horizon] > close[e] else 0
      log return = ln(close[e + horizon] / close[e])
      volatility = population std of the next `vol_window` one-bar log returns
                   (bars e..e+vol_window), i.e. realized vol right after the window.
    """
    n = len(feats)
    lookahead = max(horizon, vol_window)  # bars needed beyond the window end
    xs, y_dir, y_ret, y_vol = [], [], [], []
    for i in range(0, n - seq_len - lookahead + 1):
        end = i + seq_len  # one past the window's last bar
        ref_close = closes[end - 1]
        fut_close = closes[end - 1 + horizon]
        next_rets = np.log(closes[end : end + vol_window] / closes[end - 1 : end + vol_window - 1])
        xs.append(feats[i:end])
        y_dir.append(1 if fut_close > ref_close else 0)
        y_ret.append(np.log(fut_close / ref_close))
        y_vol.append(float(next_rets.std()))
    if not xs:
        k = feats.shape[1] if feats.ndim == 2 else 0
        empty = np.empty((0,), dtype=np.float64)
        return np.empty((0, seq_len, k)), np.empty((0,), dtype=np.int64), empty, empty
    return (
        np.stack(xs),
        np.asarray(y_dir, dtype=np.int64),
        np.asarray(y_ret, dtype=np.float64),
        np.asarray(y_vol, dtype=np.float64),
    )


def build_multitask_dataset(
    raw: np.ndarray,
    indicator_feats: np.ndarray,
    feature_names: list[str],
    seq_len: int = 60,
    horizon: int = 1,
    vol_window: int = 5,
    split: tuple[float, float, float] = (0.7, 0.15, 0.15),
) -> MultiTaskDataset:
    """Leakage-safe multi-task dataset: return features + indicators, 3 labels.

    ``indicator_feats`` is (len(raw), k) aligned 1:1 with ``raw``, ``np.nan``
    during indicator warm-up. Steps: derive return features (drops bar 0) →
    align the indicator rows → trim the warm-up (rows before every indicator
    column is finite) → concat into one wide matrix → time split → scaler fit
    on train rows only → window each segment with direction/return/volatility
    labels → standardize the regression targets with train-split stats.
    """
    n = len(raw)
    if indicator_feats.shape[0] != n:
        raise ValueError(
            f"indicator_feats has {indicator_feats.shape[0]} rows but raw has {n} bars"
        )
    vol_window = max(2, int(vol_window))  # std needs at least 2 returns

    # Return features; row k describes raw bar k+1 — align indicators the same.
    feats5, aligned_closes = _return_features(raw)
    ind = indicator_feats[1:]

    # Warm-up trim: drop rows until EVERY indicator column has a value.
    if ind.shape[1]:
        valid = np.isfinite(ind).all(axis=1)
        if not valid.any():
            raise ValueError(
                "No rows where every indicator is warmed up — the slice is shorter "
                "than the longest indicator window. Pick a larger date range."
            )
        first_valid = int(np.argmax(valid))
    else:
        first_valid = 0

    feats = np.hstack([feats5, ind])[first_valid:]
    closes = aligned_closes[first_valid:]
    m = len(feats)

    min_needed = seq_len + max(horizon, vol_window)
    if m < min_needed + 11:
        raise ValueError(
            f"Not enough usable bars after indicator warm-up: have {m}, need > "
            f"{min_needed + 11} for seq_len={seq_len}, horizon={horizon}, "
            f"vol_window={vol_window}. Pick a larger date range."
        )

    f_train, f_val, _ = split
    i_train = int(m * f_train)
    i_val = int(m * (f_train + f_val))

    # Scaler fit on TRAIN feature rows only — the leakage guard.
    train_rows = feats[:i_train]
    mean = train_rows.mean(axis=0)
    std = train_rows.std(axis=0)
    std[std < _STD_EPS] = 1.0
    scaler = Scaler(mean=mean, std=std)
    scaled = scaler.transform(feats)

    segments = {
        "train": (scaled[:i_train], closes[:i_train]),
        "val": (scaled[i_train:i_val], closes[i_train:i_val]),
        "test": (scaled[i_val:], closes[i_val:]),
    }
    out = {
        name: _window_segment_multitask(seg_feats, seg_closes, seq_len, horizon, vol_window)
        for name, (seg_feats, seg_closes) in segments.items()
    }

    # Every split must yield at least one window — silent empties would make
    # validation (and early stopping) meaningless. Fail with the fix instead.
    if any(split_frac > 0 for split_frac in split):
        for name, frac in zip(("train", "val", "test"), split):
            if frac > 0 and len(out[name][0]) == 0:
                seg_rows = len(segments[name][0])
                raise ValueError(
                    f"The {name} split has {seg_rows} usable rows — too few for even one "
                    f"window of seq_len={seq_len} (+{max(horizon, vol_window)} lookahead). "
                    "Reduce seq_len, shrink vol_window, or widen the date range."
                )

    # Regression targets standardized by TRAIN stats (vol via log1p first —
    # it's non-negative and skewed; the log makes MSE behave).
    ret_stats = TargetStats.fit(out["train"][2])
    vol_stats = TargetStats.fit(np.log1p(out["train"][3]))

    def pack(name: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        X, y_dir, y_ret, y_vol = out[name]
        return X, y_dir, ret_stats.standardize(y_ret), vol_stats.standardize(np.log1p(y_vol))

    X_tr, d_tr, r_tr, v_tr = pack("train")
    X_va, d_va, r_va, v_va = pack("val")
    X_te, d_te, r_te, v_te = pack("test")

    n_features = feats.shape[1]
    return MultiTaskDataset(
        X_train=X_tr,
        y_dir_train=d_tr,
        y_ret_train=r_tr,
        y_vol_train=v_tr,
        X_val=X_va,
        y_dir_val=d_va,
        y_ret_val=r_va,
        y_vol_val=v_va,
        X_test=X_te,
        y_dir_test=d_te,
        y_ret_test=r_te,
        y_vol_test=v_te,
        scaler=scaler,
        n_features=n_features,
        feature_names=[
            "ret_open",
            "ret_high",
            "ret_low",
            "ret_close",
            "log_volume",
            *feature_names,
        ],
        ret_stats=ret_stats,
        vol_stats=vol_stats,
        warmup_rows=first_valid,
    )


def build_dataset(
    raw: np.ndarray,
    seq_len: int = 60,
    horizon: int = 1,
    split: tuple[float, float, float] = (0.7, 0.15, 0.15),
) -> Dataset:
    """Build a leakage-safe windowed dataset from a raw OHLCV array.

    Steps: derive return features (labels stay on raw price) → split by time →
    fit scaler on train rows only → transform all → window each segment.
    """
    n = len(raw)
    min_needed = seq_len + horizon
    if n < min_needed + 11:  # +1 for the return diff that drops the first bar
        raise ValueError(
            f"Not enough bars: have {n}, need > {min_needed + 11} for "
            f"seq_len={seq_len}, horizon={horizon}. Pick a larger date range."
        )

    # Return features; row k describes raw bar k+1, aligned_closes[k] is its price.
    feats, aligned_closes = _return_features(raw)
    m = len(feats)

    f_train, f_val, _ = split
    i_train = int(m * f_train)
    i_val = int(m * (f_train + f_val))

    # Scaler fit on TRAIN feature rows only — the leakage guard.
    train_rows = feats[:i_train]
    mean = train_rows.mean(axis=0)
    std = train_rows.std(axis=0)
    # Guard near-zero std (not just exact 0): a column that's constant over the
    # train window computes a tiny float residual (~1e-14), and dividing by it
    # would amplify noise into garbage features.
    std[std < _STD_EPS] = 1.0
    scaler = Scaler(mean=mean, std=std)
    scaled = scaler.transform(feats)

    segments = {
        "train": (scaled[:i_train], aligned_closes[:i_train]),
        "val": (scaled[i_train:i_val], aligned_closes[i_train:i_val]),
        "test": (scaled[i_val:], aligned_closes[i_val:]),
    }
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name, (seg_feats, seg_closes) in segments.items():
        out[name] = _window_segment(seg_feats, seg_closes, seq_len, horizon)

    return Dataset(
        X_train=out["train"][0],
        y_train=out["train"][1],
        X_val=out["val"][0],
        y_val=out["val"][1],
        X_test=out["test"][0],
        y_test=out["test"][1],
        scaler=scaler,
        n_features=N_FEATURES,
    )
