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
from sqlalchemy import select
from sqlalchemy.orm import Session

from ml import registry
from ml.models.lstm import build_model
from models import OhlcvBar, TrainingRun
from services.datasets import Scaler, _return_features, _window_segment


def predict_overlay(session: Session, run: TrainingRun, limit: int = 200) -> dict:
    """Return recent bars + the model's per-candle predictions for them."""
    bundle = registry.load(run.artifact_path)
    hp = bundle["hyperparams"]
    seq_len = int(hp.get("seq_len", 60))
    horizon = int(hp.get("horizon", 1))

    empty = {"symbol": run.symbol, "timeframe": run.timeframe,
             "seq_len": seq_len, "horizon": horizon, "bars": [], "predictions": []}

    # Pull the most-recent (limit + window + horizon) bars, then re-sort ascending.
    need = limit + seq_len + horizon + 1
    rows = session.execute(
        select(OhlcvBar)
        .where(OhlcvBar.symbol == run.symbol, OhlcvBar.timeframe == run.timeframe)
        .order_by(OhlcvBar.ts.desc())
        .limit(need)
    ).scalars().all()
    rows = list(reversed(rows))
    if len(rows) < seq_len + horizon + 2:
        return empty

    ts = [r.ts for r in rows]
    raw = np.array(
        [[float(r.open), float(r.high), float(r.low), float(r.close), float(r.volume)]
         for r in rows],
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
            "pred": int(probs[i] >= 0.5),
            "actual": int(y[i]),
        }
        for i in range(len(X))
    ][-limit:]

    bars = [
        {"ts": r.ts, "open": float(r.open), "high": float(r.high),
         "low": float(r.low), "close": float(r.close), "volume": int(r.volume)}
        for r in rows
    ]
    return {"symbol": run.symbol, "timeframe": run.timeframe,
            "seq_len": seq_len, "horizon": horizon,
            "bars": bars, "predictions": predictions}
