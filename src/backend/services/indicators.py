"""Custom OHLCV indicators with a self-registering catalog.

Pure functions operating on the bar list produced by ``alpaca_client`` (each
bar is a dict with ``timestamp, open, high, low, close, volume``). They depend
only on the standard library so the math stays easy to unit-test.

Adding a new indicator is a one-step change: write a function with the
``(bars, period, timeframe) -> Computation`` signature and decorate it with
``@register(...)``. It then automatically shows up in the catalog, becomes
selectable via the ``include`` query param, and renders in the frontend.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from statistics import pstdev

# Approximate number of bars per trading year, used to annualize volatility.
# Based on ~252 trading days and a 6.5h (390 min) US equity session.
PERIODS_PER_YEAR = {
    "1m": 252 * 390,
    "5m": 252 * 78,
    "1h": 252 * 7,
    "1d": 252,
}

Bar = dict
Series = list[float | None]


@dataclass
class Computation:
    """Raw output of an indicator before timestamps are attached."""

    latest: float | None
    reading: str
    # One or more named float series (e.g. {"acceleration": [...], "velocity": [...]}).
    lines: dict[str, Series]
    # Scalar extras (e.g. {"annualized": 0.31}). JSON-serializable values only.
    extra: dict[str, float | None] = field(default_factory=dict)


@dataclass
class IndicatorSpec:
    key: str
    label: str
    description: str
    compute: Callable[[list[Bar], int, str], Computation]


# The catalog. Ordered by registration.
REGISTRY: dict[str, IndicatorSpec] = {}


def register(key: str, label: str, description: str):
    """Decorator that adds an indicator function to the registry."""

    def decorator(fn: Callable[[list[Bar], int, str], Computation]):
        REGISTRY[key] = IndicatorSpec(key, label, description, fn)
        return fn

    return decorator


def _typical_prices(bars: list[Bar]) -> list[float]:
    """(high + low + close) / 3 for each bar."""
    return [(b["high"] + b["low"] + b["close"]) / 3 for b in bars]


def _last_non_none(series: Series) -> float | None:
    for value in reversed(series):
        if value is not None:
            return value
    return None


# --------------------------------------------------------------------------- #
# Parkinson volatility — "Are participants panicking right now?"
# --------------------------------------------------------------------------- #
@register(
    "parkinson_volatility",
    "Parkinson Volatility",
    "<p><strong>Parkinson Volatility</strong> measures volatility using only high and low prices. It is more sensitive to intraday range expansion than standard deviation, making it useful for detecting 'panic' or explosive moves.</p><p><strong>Equation:</strong> <code>σ = √[ (1 / (4N ln(2))) * Σ (ln(H/L))² ]</code></p>",
)
def parkinson_volatility(bars: list[Bar], period: int, timeframe: str) -> Computation:
    """sigma = sqrt( (1 / (4 * ln2 * N)) * sum( ln(H/L)^2 ) )."""
    factor = 1.0 / (4.0 * math.log(2.0) * period)
    log_hl_sq: Series = []
    for b in bars:
        high, low = b["high"], b["low"]
        log_hl_sq.append(math.log(high / low) ** 2 if high > 0 and low > 0 else None)

    series: Series = []
    for i in range(len(bars)):
        window = log_hl_sq[i - period + 1 : i + 1]
        if i + 1 < period or any(x is None for x in window):
            series.append(None)
        else:
            series.append(math.sqrt(factor * sum(x for x in window if x is not None)))

    latest = _last_non_none(series)
    per_year = PERIODS_PER_YEAR.get(timeframe, 252)
    annualized = latest * math.sqrt(per_year) if latest is not None else None

    observed = [x for x in series if x is not None]
    reading = "insufficient data"
    if latest is not None and observed:
        avg = sum(observed) / len(observed)
        if latest > avg * 1.5:
            reading = "panic — volatility spiking well above its own average"
        elif latest > avg:
            reading = "elevated — above its recent average"
        else:
            reading = "calm — at or below its recent average"

    return Computation(
        latest=latest,
        reading=reading,
        lines={"parkinson_volatility": series},
        extra={"annualized": annualized},
    )


# --------------------------------------------------------------------------- #
# Acceleration — "Is this move sustainable or exhausting?"
# --------------------------------------------------------------------------- #
@register(
    "acceleration",
    "Acceleration",
    "<p><strong>Acceleration</strong> measures the rate of change of momentum. A positive value indicates that a trend is strengthening, while a negative value indicates that momentum is fading or exhausting.</p><p><strong>Equation:</strong> <code>Acc = (Close_t - Close_{t-N}) - (Close_{t-1} - Close_{t-N-1})</code></p>",
)
def acceleration(bars: list[Bar], period: int, *_) -> Computation:
    """velocity_t = close_t - close_(t-N);  acceleration_t = velocity_t - velocity_(t-1)."""
    closes = [b["close"] for b in bars]
    n = len(closes)

    velocity: Series = [None] * n
    for i in range(period, n):
        velocity[i] = closes[i] - closes[i - period]

    accel: Series = [None] * n
    for i in range(1, n):
        prev, cur = velocity[i - 1], velocity[i]
        if prev is not None and cur is not None:
            accel[i] = cur - prev

    latest = _last_non_none(accel)
    if latest is None:
        reading = "insufficient data"
    elif latest > 0:
        reading = "sustainable — momentum is still building"
    elif latest < 0:
        reading = "exhausting — momentum is fading"
    else:
        reading = "steady — momentum unchanged"

    return Computation(
        latest=latest,
        reading=reading,
        lines={"acceleration": accel, "velocity": velocity},
    )


# --------------------------------------------------------------------------- #
# Money Flow Ratio — "Buying the ask or dumping into the bid?"
# --------------------------------------------------------------------------- #
@register(
    "money_flow_ratio",
    "Money Flow Ratio",
    "<p><strong>Money Flow Ratio</strong> evaluates buying vs. selling pressure by comparing the sum of positive money flows (typical price * volume on up days) to negative money flows (typical price * volume on down days) over a window.</p><p><strong>Equation:</strong> <code>Ratio = Σ(PositiveFlow) / Σ(NegativeFlow)</code></p>",
)
def money_flow_ratio(bars: list[Bar], period: int, *_) -> Computation:
    """ratio = sum(positive flow) / sum(negative flow); flow = typical price * volume."""
    tp = _typical_prices(bars)
    n = len(bars)

    signed: list[float] = [0.0] * n
    for i in range(1, n):
        raw = tp[i] * bars[i]["volume"]
        if tp[i] > tp[i - 1]:
            signed[i] = raw
        elif tp[i] < tp[i - 1]:
            signed[i] = -raw

    series: Series = [None] * n
    mfi: Series = [None] * n
    for i in range(period, n):
        window = signed[i - period + 1 : i + 1]
        pos = sum(x for x in window if x > 0)
        neg = -sum(x for x in window if x < 0)
        if neg == 0:
            series[i] = None
            mfi[i] = 100.0 if pos > 0 else None
        else:
            ratio = pos / neg
            series[i] = ratio
            mfi[i] = 100.0 - 100.0 / (1.0 + ratio)

    latest = _last_non_none(series)
    if latest is None:
        reading = "no selling pressure in window — heavy buying"
    elif latest > 1.2:
        reading = "buying — money flow favors the ask"
    elif latest < 0.8:
        reading = "selling — money flow favors the bid"
    else:
        reading = "balanced — buyers and sellers roughly even"

    return Computation(
        latest=latest,
        reading=reading,
        lines={"money_flow_ratio": series},
        extra={"mfi": _last_non_none(mfi)},
    )


# --------------------------------------------------------------------------- #
# VWAP Z-Score — "Is price historically overextended?"
# --------------------------------------------------------------------------- #
@register(
    "vwap_zscore",
    "VWAP Z-Score",
    "<p><strong>VWAP Z-Score</strong> measures how many standard deviations the current closing price is away from the Volume Weighted Average Price (VWAP). It is a statistical gauge of price overextension.</p><p><strong>Equation:</strong> <code>Z = (Close - VWAP) / StdDev(Close - VWAP)</code></p>",
)
def vwap_zscore(bars: list[Bar], period: int, *_) -> Computation:
    """z = (close - VWAP) / stddev(close - VWAP) over N bars."""
    tp = _typical_prices(bars)
    closes = [b["close"] for b in bars]
    vols = [b["volume"] for b in bars]
    n = len(bars)

    series: Series = [None] * n
    for i in range(period - 1, n):
        lo = i - period + 1
        vol_sum = sum(vols[lo : i + 1])
        if vol_sum == 0:
            continue
        vwap = sum(tp[j] * vols[j] for j in range(lo, i + 1)) / vol_sum
        deviations = [closes[j] - vwap for j in range(lo, i + 1)]
        sd = pstdev(deviations)
        series[i] = 0.0 if sd == 0 else (closes[i] - vwap) / sd

    latest = _last_non_none(series)
    if latest is None:
        reading = "insufficient data"
    elif latest > 2:
        reading = "overextended high — stretched above VWAP"
    elif latest < -2:
        reading = "overextended low — stretched below VWAP"
    else:
        reading = "fair — within normal range of VWAP"

    return Computation(latest=latest, reading=reading, lines={"vwap_zscore": series})


# --------------------------------------------------------------------------- #
# Public API used by the router
# --------------------------------------------------------------------------- #
def available() -> list[dict]:
    """Catalog metadata for every registered indicator."""
    return [
        {"key": s.key, "label": s.label, "description": s.description}
        for s in REGISTRY.values()
    ]


def resolve_keys(include: str) -> list[str]:
    """Turn an ``include`` query value into a validated list of keys.

    ``"all"`` (or empty) -> every registered indicator, in registry order.
    Otherwise a comma-separated list, validated against the registry.
    """
    if not include or include.strip().lower() == "all":
        return list(REGISTRY.keys())

    requested = [k.strip() for k in include.split(",") if k.strip()]
    unknown = [k for k in requested if k not in REGISTRY]
    if unknown:
        valid = ", ".join(REGISTRY.keys())
        raise ValueError(f"Unknown indicator(s): {', '.join(unknown)}. Valid: {valid}")
    # De-dupe while preserving order.
    return list(dict.fromkeys(requested))


def _to_points(bars: list[Bar], series: Series) -> list[dict]:
    """Pair each series value with its bar timestamp."""
    return [
        {"timestamp": bars[i]["timestamp"], "value": series[i]}
        for i in range(len(bars))
    ]


def compute(
    bars: list[Bar], period: int, timeframe: str, keys: list[str]
) -> dict[str, dict]:
    """Compute the requested indicators, keyed by indicator key."""
    results: dict[str, dict] = {}
    for key in keys:
        spec = REGISTRY[key]
        comp = spec.compute(bars, period, timeframe)
        results[key] = {
            "key": spec.key,
            "label": spec.label,
            "description": spec.description,
            "latest": comp.latest,
            "reading": comp.reading,
            "series": {
                name: _to_points(bars, line) for name, line in comp.lines.items()
            },
            "extra": comp.extra,
        }
    return results
