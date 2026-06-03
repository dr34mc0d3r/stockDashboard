"""Dataset builder for the Lab stages.

Turns a time-ordered list of OHLCV bars into supervised sliding windows with a
**time-ordered** train/val/test split and feature scaling **fit on train only**.

Why this shape: in time-series forecasting the cardinal sin is leakage — letting
information from the future (val/test) influence training. Two guards here:
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

from models import OhlcvBar

# OHLCV feature order — kept stable so a saved scaler lines up with inference.
FEATURE_COLS = ("open", "high", "low", "close", "volume")
CLOSE_IDX = FEATURE_COLS.index("close")


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

    Steps: split raw rows by time → fit scaler on train rows → transform all →
    window each segment independently.
    """
    n = len(raw)
    min_needed = seq_len + horizon
    if n < min_needed + 10:
        raise ValueError(
            f"Not enough bars: have {n}, need > {min_needed + 10} for "
            f"seq_len={seq_len}, horizon={horizon}. Pick a larger date range."
        )

    f_train, f_val, _ = split
    i_train = int(n * f_train)
    i_val = int(n * (f_train + f_val))

    closes = raw[:, CLOSE_IDX]

    # Scaler fit on TRAIN rows only — the leakage guard.
    train_rows = raw[:i_train]
    mean = train_rows.mean(axis=0)
    std = train_rows.std(axis=0)
    std[std == 0] = 1.0  # avoid divide-by-zero on flat columns
    scaler = Scaler(mean=mean, std=std)
    scaled = scaler.transform(raw)

    segments = {
        "train": (scaled[:i_train], closes[:i_train]),
        "val": (scaled[i_train:i_val], closes[i_train:i_val]),
        "test": (scaled[i_val:], closes[i_val:]),
    }
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name, (feats, seg_closes) in segments.items():
        out[name] = _window_segment(feats, seg_closes, seq_len, horizon)

    return Dataset(
        X_train=out["train"][0], y_train=out["train"][1],
        X_val=out["val"][0], y_val=out["val"][1],
        X_test=out["test"][0], y_test=out["test"][1],
        scaler=scaler, n_features=raw.shape[1],
    )
