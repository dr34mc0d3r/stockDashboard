"""Technical indicators with a self-registering catalog (ported from srcV1).

Pure functions over a bar list (each bar a dict with ``timestamp, open, high,
low, close, volume``). Standard library only, so the math stays easy to
unit-test — and the same functions feed BOTH the chart endpoints and the ML
feature pipeline, so model and chart can never disagree.

Stage 3 ports the 10 indicators from the build plan; srcV1 has 15 more, and
adding one here is a one-step change: write a function with the
``(bars, params, timeframe) -> Computation`` signature and decorate it with
``@register(...)``. It then shows up in the catalog, the UI panel, and the
feature pipeline automatically.

Conventions:
- Every series is aligned 1:1 with the input bars; values are ``None`` until
  the indicator's warm-up window is filled. The ML pipeline trims those rows.
- ``placement`` says where the chart should draw it: "overlay" = on the price
  pane (same scale as price), "pane" = its own stacked sub-pane.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from statistics import pstdev

Bar = dict
Series = list[float | None]


@dataclass
class Computation:
    """Raw output of an indicator before timestamps are attached."""

    latest: float | None
    reading: str
    # One or more named float series (e.g. {"macd": [...], "signal": [...]}).
    lines: dict[str, Series]
    # Scalar extras (e.g. {"histogram": 0.31}). JSON-serializable values only.
    extra: dict[str, float | None] = field(default_factory=dict)


@dataclass
class Param:
    """One tunable parameter of an indicator.

    The catalog exposes these so the frontend can render the right input for
    each indicator, and ``_resolve_params`` uses ``default`` plus the
    ``min``/``max`` bounds to fill in and clamp the values a request sends.
    """

    name: str
    label: str
    default: float
    min: float | None = None
    max: float | None = None
    type: str = "int"  # "int" or "float"
    step: float | None = None


# Resolved parameter values for one indicator, e.g. {"fast": 12, "slow": 26}.
Params = dict[str, float]


@dataclass
class IndicatorSpec:
    key: str
    label: str
    description: str
    placement: str  # "overlay" (price pane) or "pane" (own sub-pane)
    params: list[Param]
    compute: Callable[[list[Bar], Params, str], Computation]


# The catalog. Ordered by registration (overlays first, then panes).
REGISTRY: dict[str, IndicatorSpec] = {}


def register(
    key: str,
    label: str,
    description: str,
    placement: str = "pane",
    params: list[Param] | None = None,
):
    """Decorator that adds an indicator function to the registry."""

    def decorator(fn: Callable[[list[Bar], Params, str], Computation]):
        REGISTRY[key] = IndicatorSpec(key, label, description, placement, params or [], fn)
        return fn

    return decorator


def _resolve_params(spec: IndicatorSpec, raw: dict | None) -> Params:
    """Fill defaults, coerce types, and clamp to bounds for one indicator.

    Anything the request omits falls back to the declared default; unparseable
    values fall back too. This is the single place parameters are validated, so
    every compute function can trust ``params[name]`` to be a sane number.
    """
    raw = raw or {}
    resolved: Params = {}
    for p in spec.params:
        value = raw.get(p.name, p.default)
        try:
            value = int(value) if p.type == "int" else float(value)
        except (TypeError, ValueError):
            value = p.default
        if p.min is not None:
            value = max(value, p.min)
        if p.max is not None:
            value = min(value, p.max)
        resolved[p.name] = value
    return resolved


# --------------------------------------------------------------------------- #
# Shared window math
# --------------------------------------------------------------------------- #
def _ema(values: list[float], period: int) -> Series:
    """Exponential moving average aligned to ``values``.

    ``None`` until the first full window, which is seeded with the simple
    average of the first ``period`` values (the common EMA convention).
    """
    n = len(values)
    out: Series = [None] * n
    if period < 1 or n < period:
        return out
    k = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, n):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def _wilder(values: list[float], period: int) -> Series:
    """Wilder's smoothing (a.k.a. RMA), used by RSI, ATR and ADX.

    Like an EMA but with smoothing factor 1/period; seeded with the simple
    mean of the first ``period`` values. ``None`` until that first window.
    """
    n = len(values)
    out: Series = [None] * n
    if period < 1 or n < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, n):
        prev = (prev * (period - 1) + values[i]) / period
        out[i] = prev
    return out


def _true_range(bars: list[Bar]) -> list[float]:
    """True range per bar: max(H−L, |H−prevClose|, |L−prevClose|)."""
    n = len(bars)
    tr = [0.0] * n
    if n:
        tr[0] = bars[0]["high"] - bars[0]["low"]
    for i in range(1, n):
        h, low, prev_close = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        tr[i] = max(h - low, abs(h - prev_close), abs(low - prev_close))
    return tr


def _typical_prices(bars: list[Bar]) -> list[float]:
    """(high + low + close) / 3 for each bar."""
    return [(b["high"] + b["low"] + b["close"]) / 3 for b in bars]


def _last_non_none(series: Series) -> float | None:
    for value in reversed(series):
        if value is not None:
            return value
    return None


# --------------------------------------------------------------------------- #
# Price-scale indicators → overlaid on the candlestick pane
# --------------------------------------------------------------------------- #
@register(
    "sma",
    "Simple Moving Average",
    "Unweighted mean of the close over the last N bars — smooths price into a "
    "trend line that acts as dynamic support/resistance.",
    placement="overlay",
    params=[Param("period", "Period", 20, min=2, max=500)],
)
def sma(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Rolling unweighted mean of the close over ``period`` bars."""
    period = int(params["period"])
    closes = [b["close"] for b in bars]
    n = len(closes)

    series: Series = [None] * n
    for i in range(period - 1, n):
        series[i] = sum(closes[i - period + 1 : i + 1]) / period

    latest = _last_non_none(series)
    last_close = closes[-1] if closes else None
    if latest is None or last_close is None:
        reading = "insufficient data"
    elif last_close > latest:
        reading = "bullish — price above its moving average"
    elif last_close < latest:
        reading = "bearish — price below its moving average"
    else:
        reading = "neutral — price at its moving average"

    return Computation(latest=latest, reading=reading, lines={"sma": series})


@register(
    "ema",
    "Exponential Moving Average",
    "Moving average that weights recent prices more heavily, so it reacts to "
    "new moves faster than an SMA.",
    placement="overlay",
    params=[Param("period", "Period", 20, min=2, max=500)],
)
def ema(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Exponential moving average of the close."""
    closes = [b["close"] for b in bars]
    series = _ema(closes, int(params["period"]))
    latest = _last_non_none(series)
    last_close = closes[-1] if closes else None
    if latest is None or last_close is None:
        reading = "insufficient data"
    elif last_close > latest:
        reading = "bullish — price above its EMA"
    elif last_close < latest:
        reading = "bearish — price below its EMA"
    else:
        reading = "neutral — price at its EMA"
    return Computation(latest=latest, reading=reading, lines={"ema": series})


@register(
    "bollinger",
    "Bollinger Bands",
    "A moving average wrapped by bands ±k standard deviations away. Bands "
    "widen when volatility rises and pinch when it falls.",
    placement="overlay",
    params=[
        Param("period", "Period", 20, min=2, max=500),
        Param("std_mult", "Std-Dev Mult", 2, min=0.5, max=5, type="float", step=0.5),
    ],
)
def bollinger(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Middle SMA band plus upper/lower bands at ±k standard deviations."""
    period = int(params["period"])
    mult = params["std_mult"]
    closes = [b["close"] for b in bars]
    n = len(closes)

    upper: Series = [None] * n
    middle: Series = [None] * n
    lower: Series = [None] * n
    for i in range(period - 1, n):
        window = closes[i - period + 1 : i + 1]
        mean = sum(window) / period
        sd = pstdev(window)
        middle[i] = mean
        upper[i] = mean + mult * sd
        lower[i] = mean - mult * sd

    last_close = closes[-1] if closes else None
    latest_upper = _last_non_none(upper)
    latest_lower = _last_non_none(lower)
    if last_close is None or latest_upper is None or latest_lower is None:
        reading = "insufficient data"
    elif last_close > latest_upper:
        reading = "overextended high — price above the upper band"
    elif last_close < latest_lower:
        reading = "overextended low — price below the lower band"
    else:
        reading = "within bands — price inside its normal range"

    return Computation(
        latest=_last_non_none(middle),
        reading=reading,
        lines={"upper": upper, "middle": middle, "lower": lower},
    )


@register(
    "vwap",
    "VWAP",
    "Average price weighted by volume over the last N bars — the level where "
    "most volume actually traded. (Rolling window, not session-anchored — a "
    "deliberate Stage 3 simplification.)",
    placement="overlay",
    params=[Param("period", "Period", 20, min=2, max=500)],
)
def vwap(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Rolling volume-weighted average price over ``period`` bars."""
    period = int(params["period"])
    tp = _typical_prices(bars)
    vols = [b["volume"] for b in bars]
    n = len(bars)
    series: Series = [None] * n
    for i in range(period - 1, n):
        lo = i - period + 1
        vol_sum = sum(vols[lo : i + 1])
        if vol_sum == 0:
            continue
        series[i] = sum(tp[j] * vols[j] for j in range(lo, i + 1)) / vol_sum

    latest = _last_non_none(series)
    last_close = bars[-1]["close"] if bars else None
    if latest is None or last_close is None:
        reading = "insufficient data"
    elif last_close > latest:
        reading = "bullish — price above VWAP"
    elif last_close < latest:
        reading = "bearish — price below VWAP"
    else:
        reading = "neutral — price at VWAP"
    return Computation(latest=latest, reading=reading, lines={"vwap": series})


# --------------------------------------------------------------------------- #
# Own-scale indicators → each in its own stacked sub-pane
# --------------------------------------------------------------------------- #
@register(
    "rsi",
    "RSI",
    "0–100 momentum oscillator comparing recent gains to recent losses "
    "(Wilder's smoothing). >70 overbought, <30 oversold.",
    placement="pane",
    params=[Param("period", "Period", 14, min=2, max=500)],
)
def rsi(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Wilder's RSI over ``period`` bars."""
    period = int(params["period"])
    closes = [b["close"] for b in bars]
    n = len(closes)
    series: Series = [None] * n

    if n > period:
        gains = [0.0] * n
        losses = [0.0] * n
        for i in range(1, n):
            change = closes[i] - closes[i - 1]
            gains[i] = max(change, 0.0)
            losses[i] = max(-change, 0.0)

        avg_gain = sum(gains[1 : period + 1]) / period
        avg_loss = sum(losses[1 : period + 1]) / period

        def rsi_value(ag: float, al: float) -> float:
            if al == 0:
                return 100.0
            return 100.0 - 100.0 / (1.0 + ag / al)

        series[period] = rsi_value(avg_gain, avg_loss)
        for i in range(period + 1, n):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            series[i] = rsi_value(avg_gain, avg_loss)

    latest = _last_non_none(series)
    if latest is None:
        reading = "insufficient data"
    elif latest > 70:
        reading = "overbought — RSI above 70"
    elif latest < 30:
        reading = "oversold — RSI below 30"
    else:
        reading = "neutral — RSI mid-range"
    return Computation(latest=latest, reading=reading, lines={"rsi": series})


@register(
    "macd",
    "MACD",
    "Gap between a fast and slow EMA, plus a signal EMA of that gap — a read "
    "on whether short-term momentum is pulling away from the longer trend.",
    placement="pane",
    params=[
        Param("fast", "Fast EMA", 12, min=2, max=200),
        Param("slow", "Slow EMA", 26, min=2, max=200),
        Param("signal", "Signal EMA", 9, min=2, max=200),
    ],
)
def macd(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """MACD line, its signal EMA, and the histogram (MACD − signal)."""
    fast, slow, signal_period = int(params["fast"]), int(params["slow"]), int(params["signal"])
    closes = [b["close"] for b in bars]
    n = len(closes)

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line: Series = [None] * n
    for i in range(n):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    # The signal EMA runs over the defined (non-None) stretch of the MACD line,
    # then is mapped back onto the original bar positions.
    defined_idx = [i for i, v in enumerate(macd_line) if v is not None]
    signal_line: Series = [None] * n
    if len(defined_idx) >= signal_period:
        sig = _ema([macd_line[i] for i in defined_idx], signal_period)
        for j, i in enumerate(defined_idx):
            signal_line[i] = sig[j]

    hist: Series = [None] * n
    for i in range(n):
        if macd_line[i] is not None and signal_line[i] is not None:
            hist[i] = macd_line[i] - signal_line[i]

    latest = _last_non_none(macd_line)
    latest_signal = _last_non_none(signal_line)
    if latest is None or latest_signal is None:
        reading = "insufficient data"
    elif latest > latest_signal:
        reading = "bullish — MACD above its signal line"
    elif latest < latest_signal:
        reading = "bearish — MACD below its signal line"
    else:
        reading = "neutral — MACD at its signal line"

    return Computation(
        latest=latest,
        reading=reading,
        lines={"macd": macd_line, "signal": signal_line},
        extra={"histogram": _last_non_none(hist)},
    )


@register(
    "stochastic",
    "Stochastic Oscillator",
    "Where the close sits within the high–low range of the last N bars "
    "(0–100). %K is the smoothed raw line; %D is a moving average of %K.",
    placement="pane",
    params=[
        Param("k_period", "%K Period", 14, min=2, max=200),
        Param("d_period", "%D Period", 3, min=1, max=100),
        Param("smooth", "Smoothing", 3, min=1, max=100),
    ],
)
def stochastic(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Smoothed %K line plus its %D moving average."""
    k_period = int(params["k_period"])
    d_period = int(params["d_period"])
    smooth = int(params["smooth"])
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    n = len(bars)

    raw: Series = [None] * n
    for i in range(k_period - 1, n):
        hh = max(highs[i - k_period + 1 : i + 1])
        ll = min(lows[i - k_period + 1 : i + 1])
        rng = hh - ll
        raw[i] = 0.0 if rng == 0 else 100.0 * (closes[i] - ll) / rng

    def sma_of(src: Series, window: int) -> Series:
        out: Series = [None] * n
        for i in range(n):
            lo = i - window + 1
            if lo >= 0 and all(x is not None for x in src[lo : i + 1]):
                out[i] = sum(src[lo : i + 1]) / window
        return out

    k = sma_of(raw, smooth)
    d = sma_of(k, d_period)

    latest = _last_non_none(k)
    if latest is None:
        reading = "insufficient data"
    elif latest > 80:
        reading = "overbought — %K above 80"
    elif latest < 20:
        reading = "oversold — %K below 20"
    else:
        reading = "neutral — %K mid-range"
    return Computation(latest=latest, reading=reading, lines={"k": k, "d": d})


@register(
    "atr",
    "ATR",
    "Wilder-smoothed average of the true range — a pure volatility gauge in "
    "price units; says nothing about direction.",
    placement="pane",
    params=[Param("period", "Period", 14, min=2, max=500)],
)
def atr(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Wilder's Average True Range."""
    period = int(params["period"])
    series = _wilder(_true_range(bars), period)
    latest = _last_non_none(series)
    observed = [x for x in series if x is not None]
    if latest is None or not observed:
        reading = "insufficient data"
    else:
        avg = sum(observed) / len(observed)
        if latest > avg * 1.25:
            reading = "expanding — range wider than its average"
        elif latest < avg * 0.8:
            reading = "contracting — range tighter than its average"
        else:
            reading = "steady — range near its average"
    return Computation(latest=latest, reading=reading, lines={"atr": series})


@register(
    "adx",
    "ADX",
    "Trend strength on a 0–100 scale (non-directional), with +DI/−DI lines "
    "showing direction. ADX ≥ 25 = strong trend; < 20 = chop.",
    placement="pane",
    params=[Param("period", "Period", 14, min=2, max=500)],
)
def adx(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """ADX trend strength with +DI / −DI direction lines (Wilder)."""
    period = int(params["period"])
    n = len(bars)
    empty = {"adx": [None] * n, "plus_di": [None] * n, "minus_di": [None] * n}
    if n < 2:
        return Computation(latest=None, reading="insufficient data", lines=empty)

    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = bars[i]["high"] - bars[i - 1]["high"]
        down = bars[i - 1]["low"] - bars[i]["low"]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0

    atr_s = _wilder(_true_range(bars), period)
    plus_dm_s = _wilder(plus_dm, period)
    minus_dm_s = _wilder(minus_dm, period)

    plus_di: Series = [None] * n
    minus_di: Series = [None] * n
    dx: Series = [None] * n
    for i in range(n):
        if atr_s[i] and atr_s[i] != 0 and plus_dm_s[i] is not None:
            pdi = 100.0 * plus_dm_s[i] / atr_s[i]
            mdi = 100.0 * minus_dm_s[i] / atr_s[i]
            plus_di[i] = pdi
            minus_di[i] = mdi
            denom = pdi + mdi
            dx[i] = 100.0 * abs(pdi - mdi) / denom if denom != 0 else 0.0

    # ADX is the Wilder average of DX over its defined (non-None) region.
    defined = [i for i, v in enumerate(dx) if v is not None]
    adx_series: Series = [None] * n
    if len(defined) >= period:
        smoothed = _wilder([dx[i] for i in defined], period)
        for j, i in enumerate(defined):
            adx_series[i] = smoothed[j]

    latest = _last_non_none(adx_series)
    last_pdi = _last_non_none(plus_di)
    last_mdi = _last_non_none(minus_di)
    if latest is None:
        reading = "insufficient data"
    elif latest >= 25:
        if last_pdi is not None and last_mdi is not None and last_pdi >= last_mdi:
            reading = "bullish — strong uptrend (ADX ≥ 25)"
        else:
            reading = "bearish — strong downtrend (ADX ≥ 25)"
    elif latest < 20:
        reading = "neutral — weak or no trend (ADX < 20)"
    else:
        reading = "neutral — trend developing"
    return Computation(
        latest=latest,
        reading=reading,
        lines={"adx": adx_series, "plus_di": plus_di, "minus_di": minus_di},
    )


@register(
    "obv",
    "On-Balance Volume",
    "Running total that adds volume on up closes and subtracts it on down "
    "closes — does volume back the price move?",
    placement="pane",
    params=[Param("period", "Trend Lookback", 20, min=2, max=500)],
)
def obv(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Cumulative on-balance volume; reading gauges its trend over the lookback."""
    period = int(params["period"])
    n = len(bars)
    series: Series = [None] * n
    if n == 0:
        return Computation(latest=None, reading="insufficient data", lines={"obv": series})

    closes = [b["close"] for b in bars]
    vols = [b["volume"] for b in bars]
    running = 0.0
    series[0] = 0.0
    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            running += vols[i]
        elif closes[i] < closes[i - 1]:
            running -= vols[i]
        series[i] = running

    latest = series[-1]
    ref_idx = n - 1 - period
    if ref_idx >= 0 and series[ref_idx] is not None and latest > series[ref_idx]:
        reading = "accumulation — OBV trending up"
    elif ref_idx >= 0 and series[ref_idx] is not None and latest < series[ref_idx]:
        reading = "distribution — OBV trending down"
    else:
        reading = "neutral — OBV flat"
    return Computation(latest=latest, reading=reading, lines={"obv": series})


# --------------------------------------------------------------------------- #
# Public API used by the router and the feature pipeline
# --------------------------------------------------------------------------- #
def available() -> list[dict]:
    """Catalog metadata for every registered indicator, including param schema."""
    return [
        {
            "key": s.key,
            "label": s.label,
            "description": s.description,
            "placement": s.placement,
            "params": [asdict(p) for p in s.params],
        }
        for s in REGISTRY.values()
    ]


def resolve_keys(requested: list[str] | None) -> list[str]:
    """Validate a list of indicator keys against the registry.

    ``None``/empty -> every registered indicator, in registry order.
    Raises ValueError naming any unknown keys.
    """
    if not requested:
        return list(REGISTRY.keys())
    unknown = [k for k in requested if k not in REGISTRY]
    if unknown:
        valid = ", ".join(REGISTRY.keys())
        raise ValueError(f"Unknown indicator(s): {', '.join(unknown)}. Valid: {valid}")
    # De-dupe while preserving order.
    return list(dict.fromkeys(requested))


def _to_points(bars: list[Bar], series: Series) -> list[dict]:
    """Pair each series value with its bar timestamp."""
    return [{"timestamp": bars[i]["timestamp"], "value": series[i]} for i in range(len(bars))]


def compute(
    bars: list[Bar],
    timeframe: str,
    keys: list[str],
    params_by_key: dict[str, dict] | None = None,
) -> dict[str, dict]:
    """Compute the requested indicators, keyed by indicator key.

    ``params_by_key`` maps an indicator key to the raw parameter values the
    request supplied (e.g. ``{"macd": {"fast": 12}}``). Missing keys/params
    fall back to each indicator's declared defaults via ``_resolve_params``.
    """
    params_by_key = params_by_key or {}
    results: dict[str, dict] = {}
    for key in keys:
        spec = REGISTRY[key]
        params = _resolve_params(spec, params_by_key.get(key))
        comp = spec.compute(bars, params, timeframe)
        results[key] = {
            "key": spec.key,
            "label": spec.label,
            "description": spec.description,
            "placement": spec.placement,
            "params": params,
            "latest": comp.latest,
            "reading": comp.reading,
            "series": {name: _to_points(bars, line) for name, line in comp.lines.items()},
            "extra": comp.extra,
        }
    return results
