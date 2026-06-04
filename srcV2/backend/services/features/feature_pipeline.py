"""Bars → aligned indicator feature matrix, with feature_cache support.

The bridge between the indicator functions and the dataset builder: it runs
``indicators.compute`` over a bar slice and flattens every indicator line into
one numeric matrix aligned 1:1 with the bars (``np.nan`` during warm-up — the
dataset builder trims those rows).

Caching: the matrix for a given indicator config is deterministic, so it is
stored in the ``feature_cache`` table keyed by a short hash of the config
(``feature_set``). On a repeat run with the same config + slice the matrix is
read back instead of recomputed. Honest note: stdlib indicators are fast — the
cache matters little here and a lot at Stages 4/5 (FinBERT/GDELT), where the
same table will hold genuinely expensive features. This wires up the pattern.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

import numpy as np
from sqlalchemy import delete as sa_delete
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from models import FeatureCache
from services.features import indicators

# Cache writes go in chunks to stay under the DB's packet limits.
_CHUNK = 2000


def config_hash(items: list[dict]) -> str:
    """Deterministic short id for an indicator config (the feature_set key).

    Same indicators + same params -> same hash; any change -> a new key, which
    is the whole invalidation story (old rows are simply never read again).
    """
    canon = sorted(
        (
            {"name": item["name"], "params": dict(sorted(dict(item.get("params") or {}).items()))}
            for item in items
        ),
        key=lambda d: d["name"],
    )
    digest = hashlib.sha1(json.dumps(canon, sort_keys=True).encode()).hexdigest()
    return f"ind_{digest[:12]}"


def compute_feature_matrix(
    bars: list[dict], timeframe: str, items: list[dict]
) -> tuple[np.ndarray, list[str]]:
    """Run the indicators and flatten every line into an (n_bars, k) matrix.

    Columns are named "indicator.line" (e.g. "bollinger.upper") and ordered
    alphabetically so the layout is reproducible no matter how the request
    listed the indicators. Warm-up values become ``np.nan``.
    """
    keys = indicators.resolve_keys([item["name"] for item in items])
    params_by_key = {item["name"]: dict(item.get("params") or {}) for item in items}
    results = indicators.compute(bars, timeframe, keys, params_by_key)

    columns: dict[str, list[float]] = {}
    for key, result in results.items():
        for line_name, points in result["series"].items():
            columns[f"{key}.{line_name}"] = [
                p["value"] if p["value"] is not None else np.nan for p in points
            ]

    names = sorted(columns)
    if not names:
        return np.empty((len(bars), 0)), []
    matrix = np.column_stack([columns[name] for name in names]).astype(np.float64)
    return matrix, names


def _read_cache(
    session: Session, symbol: str, timeframe: str, feature_set: str, ts_list: list[datetime]
) -> tuple[np.ndarray, list[str]] | None:
    """Rebuild the matrix from cached rows, or None on any mismatch."""
    rows = (
        session.execute(
            select(FeatureCache)
            .where(
                FeatureCache.symbol == symbol,
                FeatureCache.timeframe == timeframe,
                FeatureCache.feature_set == feature_set,
                FeatureCache.ts >= ts_list[0],
                FeatureCache.ts <= ts_list[-1],
            )
            .order_by(FeatureCache.ts.asc())
        )
        .scalars()
        .all()
    )
    if len(rows) != len(ts_list):
        return None
    names = sorted(rows[0].payload)
    matrix = np.array(
        [
            [
                row.payload.get(name) if row.payload.get(name) is not None else np.nan
                for name in names
            ]
            for row in rows
        ],
        dtype=np.float64,
    )
    return matrix, names


def _write_cache(
    session: Session,
    symbol: str,
    timeframe: str,
    feature_set: str,
    ts_list: list[datetime],
    matrix: np.ndarray,
    names: list[str],
) -> None:
    """Replace cached rows for this slice: delete + bulk insert (idempotent,
    portable across MySQL and SQLite — no dialect-specific upsert needed)."""
    session.execute(
        sa_delete(FeatureCache).where(
            FeatureCache.symbol == symbol,
            FeatureCache.timeframe == timeframe,
            FeatureCache.feature_set == feature_set,
            FeatureCache.ts >= ts_list[0],
            FeatureCache.ts <= ts_list[-1],
        )
    )
    payloads = [
        {
            "symbol": symbol,
            "timeframe": timeframe,
            "ts": ts,
            "feature_set": feature_set,
            "payload": {
                name: (None if np.isnan(matrix[i, j]) else float(matrix[i, j]))
                for j, name in enumerate(names)
            },
        }
        for i, ts in enumerate(ts_list)
    ]
    for lo in range(0, len(payloads), _CHUNK):
        session.execute(insert(FeatureCache), payloads[lo : lo + _CHUNK])
    session.commit()


def estimate_warmup(items: list[dict], timeframe: str = "1d") -> int:
    """How many leading bars this indicator config leaves undefined.

    Warm-up depends only on the config (params), never on the data, so we
    measure it empirically on a synthetic ramp — simpler and safer than
    deriving per-indicator formulas. Returns the index of the first row where
    every column is defined.
    """
    if not items:
        return 0
    longest = max(
        (int(v) for item in items for v in (item.get("params") or {}).values()), default=0
    )
    # Generous synthetic length: chained windows (e.g. MACD slow+signal,
    # ADX's double smoothing) stay well inside 4x the longest single param.
    n = max(200, longest * 4 + 50)
    bars = [
        {
            "timestamp": f"2000-01-01T00:{i // 60:02d}:{i % 60:02d}",
            "open": 100 + i * 0.1,
            "high": 101 + i * 0.1,
            "low": 99 + i * 0.1,
            "close": 100.5 + i * 0.1,
            "volume": 1000 + i,
        }
        for i in range(n)
    ]
    matrix, _ = compute_feature_matrix(bars, timeframe, items)
    valid = np.isfinite(matrix).all(axis=1)
    if not valid.any():
        return n  # config never warms up within n bars — caller will error out
    return int(np.argmax(valid))


def build_features(
    session: Session,
    symbol: str,
    timeframe: str,
    bars: list[dict],
    items: list[dict],
    use_cache: bool = True,
) -> tuple[np.ndarray, list[str], str]:
    """The ML-pipeline entry point: (matrix aligned to bars, column names, feature_set).

    With ``use_cache`` the matrix is served from feature_cache when a complete
    set of rows exists for this config + slice, and written back after a fresh
    compute. ``items`` may be empty -> a (n, 0) matrix (OHLCV-only training).
    """
    feature_set = config_hash(items)
    if not items:
        return np.empty((len(bars), 0)), [], feature_set

    ts_list = [datetime.fromisoformat(b["timestamp"]) for b in bars]
    if use_cache and ts_list:
        cached = _read_cache(session, symbol, timeframe, feature_set, ts_list)
        if cached is not None:
            return cached[0], cached[1], feature_set

    matrix, names = compute_feature_matrix(bars, timeframe, items)
    if use_cache and ts_list:
        _write_cache(session, symbol, timeframe, feature_set, ts_list, matrix, names)
    return matrix, names, feature_set
