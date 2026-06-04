"""Overlay inference: run a saved model over recent bars to get its per-candle
direction calls, for plotting as markers on the candlestick chart.

Reuses the exact training-time feature pipeline (return features + the *saved*
scaler, not a refit one) so predictions are consistent with how the model was
trained. Each prediction is anchored to the window's last candle — the bar from
which the model calls the next one.
"""

from __future__ import annotations

import numpy as np
import torch
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constants import PROB_THRESHOLD
from ml import registry
from ml.models.lstm import build_model
from models import OhlcvBar, TrainingRun
from services.datasets import Scaler, _return_features, _window_segment


def predict_overlay(session: Session, run: TrainingRun, limit: int = 200) -> dict:
    """Return bars + the model's per-candle predictions, for charting.

    When the run recorded its data slice (start/end), we overlay the most-recent
    bars *within that slice*, clamped so they fall inside the test segment — the
    split is time-ordered, so the newest 15% of the slice is exactly the held-out
    test set, making the overlay strictly out-of-sample. Older runs without a
    stored slice fall back to the most recent stored bars (out_of_sample=False).
    """
    bundle = registry.load(run.artifact_path)
    hp = bundle["hyperparams"]
    seq_len = int(hp.get("seq_len", 60))
    horizon = int(hp.get("horizon", 1))

    base = select(OhlcvBar).where(
        OhlcvBar.symbol == run.symbol, OhlcvBar.timeframe == run.timeframe
    )
    out_of_sample = bool(run.start and run.end)
    eff_limit = limit
    if out_of_sample:
        base = base.where(OhlcvBar.ts >= run.start, OhlcvBar.ts <= run.end)
        # Clamp to the test region so we never spill into val/train data.
        count = session.execute(
            select(func.count())
            .select_from(OhlcvBar)
            .where(
                OhlcvBar.symbol == run.symbol,
                OhlcvBar.timeframe == run.timeframe,
                OhlcvBar.ts >= run.start,
                OhlcvBar.ts <= run.end,
            )
        ).scalar_one()
        split = hp.get("split", [0.7, 0.15, 0.15])
        i_val = int(max(count - 1, 0) * (split[0] + split[1]))
        test_capacity = max(0, (count - i_val) - seq_len - horizon)
        eff_limit = min(limit, test_capacity)

    empty = {
        "symbol": run.symbol,
        "timeframe": run.timeframe,
        "seq_len": seq_len,
        "horizon": horizon,
        "out_of_sample": out_of_sample,
        "bars": [],
        "predictions": [],
    }
    if eff_limit <= 0:
        return empty

    # Pull the most-recent (eff_limit + window + horizon) bars, re-sort ascending.
    need = eff_limit + seq_len + horizon + 1
    rows = session.execute(base.order_by(OhlcvBar.ts.desc()).limit(need)).scalars().all()
    rows = list(reversed(rows))
    if len(rows) < seq_len + horizon + 2:
        return empty

    ts = [r.ts for r in rows]
    raw = np.array(
        [
            [float(r.open), float(r.high), float(r.low), float(r.close), float(r.volume)]
            for r in rows
        ],
        dtype=np.float64,
    )

    # Same features as training; apply the SAVED scaler (no refit).
    feats, aligned_closes = _return_features(raw)
    scaler = Scaler.from_dict(bundle["scaler"])
    scaled = scaler.transform(feats)
    X, y = _window_segment(scaled, aligned_closes, seq_len, horizon)
    if len(X) == 0:
        return empty

    model = build_model(bundle["n_features"], hp)
    model.load_state_dict(bundle["state_dict"])
    model.eval()
    with torch.no_grad():
        probs = torch.sigmoid(model(torch.from_numpy(X).float())).numpy()

    # Window i's decision candle is raw bar (i + seq_len); ts[i + seq_len].
    predictions = [
        {
            "ts": ts[i + seq_len],
            "prob": round(float(probs[i]), 4),
            "pred": int(probs[i] >= PROB_THRESHOLD),
            "actual": int(y[i]),
        }
        for i in range(len(X))
    ][-eff_limit:]

    bars = [
        {
            "ts": r.ts,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": int(r.volume),
        }
        for r in rows
    ]
    return {
        "symbol": run.symbol,
        "timeframe": run.timeframe,
        "seq_len": seq_len,
        "horizon": horizon,
        "out_of_sample": out_of_sample,
        "bars": bars,
        "predictions": predictions,
    }
