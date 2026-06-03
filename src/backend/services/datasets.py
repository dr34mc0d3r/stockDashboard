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


def _return_features(raw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert raw OHLCV levels into stationary per-bar return features.

    Returns ``(feats, aligned_closes)`` where row k of ``feats`` describes raw
    bar ``k+1`` (the first bar is dropped — it has no previous close), and
    ``aligned_closes[k]`` is that bar's raw close, so labels stay anchored to the
    real price. Both have length ``len(raw) - 1``.
    """
    closes = raw[:, CLOSE_IDX]
    prev_close = closes[:-1]                     # denominators for bars 1..n-1
    o, h, l, c = raw[1:, 0], raw[1:, 1], raw[1:, 2], raw[1:, 3]
    v = raw[1:, 4]
    feats = np.column_stack([
        np.log(o / prev_close),
        np.log(h / prev_close),
        np.log(l / prev_close),
        np.log(c / prev_close),  # the bar's return — the headline feature
        np.log1p(v),
    ])
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
    def from_dict(cls, d: dict) -> "Scaler":
        return cls(mean=np.asarray(d["mean"], dtype=np.float64),
                   std=np.asarray(d["std"], dtype=np.float64))


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


def load_bars(session: Session, symbol: str, timeframe: str,
              start: str | None = None, end: str | None = None) -> np.ndarray:
    """Load OHLCV rows oldest-first as a float64 array, columns = FEATURE_COLS."""
    from models import OhlcvBar  # local import: keeps the pure logic DB-free

    stmt = select(OhlcvBar).where(
        OhlcvBar.symbol == symbol.upper(), OhlcvBar.timeframe == timeframe
    )
    if start:
        stmt = stmt.where(OhlcvBar.ts >= start)
    if end:
        stmt = stmt.where(OhlcvBar.ts <= end)
    rows = session.execute(stmt.order_by(OhlcvBar.ts.asc())).scalars().all()
    return np.array(
        [[float(b.open), float(b.high), float(b.low), float(b.close), float(b.volume)]
         for b in rows],
        dtype=np.float64,
    )


def _window_segment(feats: np.ndarray, closes: np.ndarray, seq_len: int,
                    horizon: int) -> tuple[np.ndarray, np.ndarray]:
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


def build_dataset(raw: np.ndarray, seq_len: int = 60, horizon: int = 1,
                  split: tuple[float, float, float] = (0.7, 0.15, 0.15)) -> Dataset:
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
    std[std < 1e-8] = 1.0
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
        X_train=out["train"][0], y_train=out["train"][1],
        X_val=out["val"][0], y_val=out["val"][1],
        X_test=out["test"][0], y_test=out["test"][1],
        scaler=scaler, n_features=N_FEATURES,
    )
