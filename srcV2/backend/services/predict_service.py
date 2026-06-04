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
from services.datasets import (
    Scaler,
    TargetStats,
    _return_features,
    _window_segment,
    _window_segment_multitask,
)


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


# ---------------------------------------------------------------------------
# Stage 3: multi-task overlay (direction arrows + predicted return/vol)
# ---------------------------------------------------------------------------
def predict_overlay_multitask(session: Session, run: TrainingRun, limit: int = 200) -> dict:
    """Like `predict_overlay`, for a multitask run.

    Differences from Stage 2: the feature matrix is rebuilt with the run's
    stored indicator config (same functions, SAVED scaler — no refit), the
    indicator warm-up consumes extra leading bars (estimated up front so the
    out-of-sample clamp stays honest), and each prediction also carries the
    return/volatility heads' outputs in natural units.
    """
    from ml.models.multitask import build_model as build_multitask_model
    from services.features import feature_pipeline

    bundle = registry.load(run.artifact_path)
    hp = bundle["hyperparams"]
    extras = bundle.get("extras", {})
    seq_len = int(hp.get("seq_len", 60))
    horizon = int(hp.get("horizon", 1))
    vol_window = max(2, int(hp.get("vol_window", 5)))
    lookahead = max(horizon, vol_window)
    items = hp.get("indicators", [])
    warmup = feature_pipeline.estimate_warmup(items, run.timeframe)

    base = select(OhlcvBar).where(
        OhlcvBar.symbol == run.symbol, OhlcvBar.timeframe == run.timeframe
    )
    out_of_sample = bool(run.start and run.end)
    eff_limit = limit
    if out_of_sample:
        base = base.where(OhlcvBar.ts >= run.start, OhlcvBar.ts <= run.end)
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
        # Training trimmed warm-up + the return-feature row before splitting.
        m = max(count - 1 - warmup, 0)
        i_val = int(m * (split[0] + split[1]))
        test_capacity = max(0, (m - i_val) - seq_len - lookahead)
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

    # The newest bars, plus enough history for windows, lookahead and warm-up.
    need = eff_limit + seq_len + lookahead + warmup + 1
    rows = session.execute(base.order_by(OhlcvBar.ts.desc()).limit(need)).scalars().all()
    rows = list(reversed(rows))
    if len(rows) < seq_len + lookahead + warmup + 2:
        return empty

    bar_dicts = [
        {
            "timestamp": r.ts.isoformat(),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": int(r.volume),
        }
        for r in rows
    ]
    raw = np.array(
        [[b["open"], b["high"], b["low"], b["close"], b["volume"]] for b in bar_dicts],
        dtype=np.float64,
    )

    # Same features as training (cache off: this small slice is instant).
    matrix, _names, _fs = feature_pipeline.build_features(
        session, run.symbol, run.timeframe, bar_dicts, items, use_cache=False
    )

    # Stage 4 runs trained with sentiment columns — rebuild them identically
    # (same cached daily aggregates, same lag) or n_features won't match.
    sent_cfg = hp.get("sentiment") or {}
    if sent_cfg.get("enabled"):
        from services.sentiment.sentiment_features import build_sentiment_matrix

        sent_matrix, _sent_names = build_sentiment_matrix(
            session, run.symbol, [r.ts for r in rows], lag_days=int(sent_cfg.get("lag_days", 1))
        )
        matrix = np.hstack([matrix, sent_matrix])

    feats5, aligned_closes = _return_features(raw)
    ind = matrix[1:]
    if ind.shape[1]:
        valid = np.isfinite(ind).all(axis=1)
        if not valid.any():
            return empty
        first_valid = int(np.argmax(valid))
    else:
        first_valid = 0
    feats = np.hstack([feats5, ind])[first_valid:]
    closes = aligned_closes[first_valid:]

    scaler = Scaler.from_dict(bundle["scaler"])
    scaled = scaler.transform(feats)
    X, y_dir, y_ret, _y_vol = _window_segment_multitask(
        scaled, closes, seq_len, horizon, vol_window
    )
    if len(X) == 0:
        return empty

    model = build_multitask_model(bundle["n_features"], hp)
    model.load_state_dict(bundle["state_dict"])
    model.eval()
    with torch.no_grad():
        dir_logit, ret_pred, vol_pred = model(torch.from_numpy(X).float())
        probs = torch.sigmoid(dir_logit).numpy()
        ret_pred = ret_pred.numpy()
        vol_pred = vol_pred.numpy()

    ret_stats = TargetStats.from_dict(extras["ret_stats"])
    vol_stats = TargetStats.from_dict(extras["vol_stats"])
    pred_returns = ret_stats.unstandardize(ret_pred)
    pred_vols = np.expm1(vol_stats.unstandardize(vol_pred))

    # Window i's decision candle: raw bar (1 + first_valid + i + seq_len - 1).
    ts = [r.ts for r in rows]
    offset = first_valid + seq_len  # +1 from _return_features, -1 for "last bar"
    predictions = [
        {
            "ts": ts[offset + i],
            "prob": round(float(probs[i]), 4),
            "pred": int(probs[i] >= PROB_THRESHOLD),
            "actual": int(y_dir[i]),
            "pred_return": round(float(pred_returns[i]), 6),
            "pred_vol": round(float(pred_vols[i]), 6),
            "actual_return": round(float(y_ret[i]), 6),
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
