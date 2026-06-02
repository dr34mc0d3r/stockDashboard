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
from dataclasses import asdict, dataclass, field
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
class Param:
    """One tunable parameter of an indicator.

    The catalog exposes these so the frontend can render the right input for
    each indicator, and the resolver (``_resolve_params``) uses ``default`` and
    the ``min``/``max`` bounds to fill in and clamp the values a request sends.
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
    params: list[Param]
    compute: Callable[[list[Bar], Params, str], Computation]


# The catalog. Ordered by registration.
REGISTRY: dict[str, IndicatorSpec] = {}


def register(key: str, label: str, description: str, params: list[Param] | None = None):
    """Decorator that adds an indicator function to the registry.

    ``params`` declares the indicator's tunable inputs (defaults shown if
    omitted: none). Each compute function receives the resolved values as a
    ``params`` dict, e.g. ``params["period"]``.
    """

    def decorator(fn: Callable[[list[Bar], Params, str], Computation]):
        REGISTRY[key] = IndicatorSpec(key, label, description, params or [], fn)
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
# Parkinson volatility — "Are participants panicking right now?"
# --------------------------------------------------------------------------- #
@register(
    "parkinson_volatility",
    "Parkinson Volatility",
    "<p><strong>Parkinson Volatility</strong> measures volatility using only high and low prices. It is more sensitive to intraday range expansion than standard deviation, making it useful for detecting 'panic' or explosive moves.</p><p><strong>Equation:</strong> <code>σ = √[ (1 / (4N ln(2))) * Σ (ln(H/L))² ]</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Spike well above the recent baseline</strong> (roughly 1.5×+ its own average) — a sharp vertical jump in the line flags a panic / explosive move; expect wide candles and slippage.</li><li><strong>Rising line</strong> above its average — expansion is underway; widen stops and size down.</li><li><strong>Flat, low line</strong> at or below average — calm/compression. Sustained lows often precede a breakout, so watch for the next expansion.</li></ul>",
    params=[Param("period", "Period", 14, min=2, max=500)],
)
def parkinson_volatility(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """sigma = sqrt( (1 / (4 * ln2 * N)) * sum( ln(H/L)^2 ) )."""
    period = params["period"]
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
    "<p><strong>Acceleration</strong> measures the rate of change of momentum. A positive value indicates that a trend is strengthening, while a negative value indicates that momentum is fading or exhausting.</p><p><strong>Equation:</strong> <code>Acc = (Close_t - Close_{t-N}) - (Close_{t-1} - Close_{t-N-1})</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Zero-line cross</strong> — the line crossing from negative to positive (above zero) confirms a move is building; crossing below zero warns momentum is exhausting even if price is still climbing.</li><li><strong>Divergence vs. price</strong> — price making new highs while acceleration is falling toward zero signals an aging trend; tighten profit targets.</li><li><strong>Bars growing taller</strong> on the same side of zero — momentum is still feeding the trend. Bars shrinking toward zero — the move is stalling.</li></ul>",
    params=[Param("period", "Period", 14, min=2, max=500)],
)
def acceleration(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """velocity_t = close_t - close_(t-N);  acceleration_t = velocity_t - velocity_(t-1)."""
    period = params["period"]
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
    "<p><strong>Money Flow Ratio</strong> evaluates buying vs. selling pressure by comparing the sum of positive money flows (typical price * volume on up days) to negative money flows (typical price * volume on down days) over a window.</p><p><strong>Equation:</strong> <code>Ratio = Σ(PositiveFlow) / Σ(NegativeFlow)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Line above 1.2</strong> — buyers are lifting the ask; volume confirms upside. <strong>Below 0.8</strong> — sellers are hitting the bid; volume confirms downside.</li><li><strong>The 1.0 level</strong> is the balance point — a cross above/below 1.0 marks a shift in who is in control.</li><li><strong>Divergence vs. price</strong> — price rising while the ratio falls (or vice versa) warns the move lacks volume support and may reverse.</li></ul>",
    params=[Param("period", "Period", 14, min=2, max=500)],
)
def money_flow_ratio(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """ratio = sum(positive flow) / sum(negative flow); flow = typical price * volume."""
    period = params["period"]
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
        reading = "buying — no selling pressure in window"
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
    "<p><strong>VWAP Z-Score</strong> measures how many standard deviations the current closing price is away from the Volume Weighted Average Price (VWAP). It is a statistical gauge of price overextension.</p><p><strong>Equation:</strong> <code>Z = (Close - VWAP) / StdDev(Close - VWAP)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Line pushing above +2</strong> — price is stretched well above VWAP (overextended high); watch for mean-reversion / fade setups. <strong>Below −2</strong> — stretched below VWAP; watch for a bounce back toward VWAP.</li><li><strong>Cross back through 0</strong> — price has returned to VWAP; the overextension has reset.</li><li><strong>Staying pinned beyond ±2</strong> rather than reverting signals a strong trend day — don't fight it; treat the extreme as continuation, not reversal.</li></ul>",
    params=[Param("period", "Period", 14, min=2, max=500)],
)
def vwap_zscore(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """z = (close - VWAP) / stddev(close - VWAP) over N bars."""
    period = params["period"]
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
# Simple Moving Average — "Where is fair value trending?"
# --------------------------------------------------------------------------- #
@register(
    "sma",
    "Simple Moving Average",
    "<p><strong>Simple Moving Average (SMA)</strong> is the unweighted mean of the closing price over the last N bars. It smooths price into a trend line and acts as dynamic support/resistance.</p><p><strong>Equation:</strong> <code>SMA = (Σ Close over N bars) / N</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Price crossing the line</strong> — close moving above the SMA is bullish; dropping below is bearish.</li><li><strong>Slope</strong> — a rising line confirms an uptrend, a falling line a downtrend, flat = no trend (chop).</li><li><strong>Pullbacks to the line</strong> — in a trend, price often bounces off the SMA; a clean break through it warns the trend is changing.</li></ul>",
    params=[Param("period", "Period", 20, min=2, max=500)],
)
def sma(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Rolling unweighted mean of the close over ``period`` bars."""
    period = params["period"]
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


# --------------------------------------------------------------------------- #
# MACD — "Is short-term momentum pulling away from the long-term trend?"
# --------------------------------------------------------------------------- #
@register(
    "macd",
    "MACD",
    "<p><strong>MACD (Moving Average Convergence Divergence)</strong> tracks the gap between a fast and a slow EMA. The signal line is an EMA of that gap, and the histogram is their difference — a read on momentum.</p><p><strong>Equation:</strong> <code>MACD = EMA(fast) − EMA(slow); Signal = EMA(MACD, signal); Hist = MACD − Signal</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Signal cross</strong> — MACD crossing above the signal line is a bullish trigger; crossing below is bearish.</li><li><strong>Zero-line cross</strong> — MACD above zero means the fast EMA leads (uptrend); below zero, downtrend.</li><li><strong>Histogram shrinking toward zero</strong> — momentum is fading and a cross may be near; growing bars confirm the move. Divergence vs. price warns of a reversal.</li></ul>",
    params=[
        Param("fast", "Fast EMA", 12, min=2, max=200),
        Param("slow", "Slow EMA", 26, min=2, max=200),
        Param("signal", "Signal EMA", 9, min=2, max=200),
    ],
)
def macd(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """MACD line, its signal EMA, and the histogram (MACD − signal)."""
    fast, slow, signal_period = params["fast"], params["slow"], params["signal"]
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


# --------------------------------------------------------------------------- #
# Bollinger Bands — "Is price stretched relative to its own recent range?"
# --------------------------------------------------------------------------- #
@register(
    "bollinger",
    "Bollinger Bands",
    "<p><strong>Bollinger Bands</strong> wrap a moving average with bands set a number of standard deviations above and below it. The bands widen when volatility rises and pinch in when it falls.</p><p><strong>Equation:</strong> <code>Mid = SMA(N); Upper/Lower = Mid ± k · StdDev(N)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Tag of the upper/lower band</strong> — price riding the upper band is strong (often continuation in a trend, overextension in a range); the lower band is the mirror.</li><li><strong>The squeeze</strong> — bands pinching tight signals low volatility and often precedes a sharp breakout; watch which band price breaks.</li><li><strong>Walking the band vs. snapping back</strong> — repeated closes outside a band = strong trend; a single poke that reverts = mean-reversion back toward the middle.</li></ul>",
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


# --------------------------------------------------------------------------- #
# EMA — "Where is fair value trending (recent bars weighted heavier)?"
# --------------------------------------------------------------------------- #
@register(
    "ema",
    "Exponential Moving Average",
    "<p><strong>Exponential Moving Average (EMA)</strong> is a moving average that weights recent prices more heavily, so it reacts to new moves faster than a simple average.</p><p><strong>Equation:</strong> <code>EMA_t = Close_t · k + EMA_{t-1} · (1 − k), k = 2 / (N + 1)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Price crossing the line</strong> — close above the EMA is bullish, below is bearish; the EMA turns faster than an SMA.</li><li><strong>Slope</strong> — a rising EMA confirms an uptrend, a falling one a downtrend.</li><li><strong>Dynamic support/resistance</strong> — in a trend, pullbacks often stall at the EMA; a decisive break through it warns of a change.</li></ul>",
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


# --------------------------------------------------------------------------- #
# RSI — "Is the move overbought or oversold?"
# --------------------------------------------------------------------------- #
@register(
    "rsi",
    "RSI",
    "<p><strong>Relative Strength Index (RSI)</strong> is a 0–100 momentum oscillator comparing the size of recent gains to recent losses, using Wilder's smoothing.</p><p><strong>Equation:</strong> <code>RSI = 100 − 100 / (1 + AvgGain / AvgLoss)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Above 70</strong> — overbought; the move is extended and may stall or pull back. <strong>Below 30</strong> — oversold; watch for a bounce.</li><li><strong>The 50 line</strong> — staying above 50 reflects bullish control, below 50 bearish.</li><li><strong>Divergence</strong> — price making a new high while RSI makes a lower high (or the reverse) often precedes a reversal.</li></ul>",
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


# --------------------------------------------------------------------------- #
# Stochastic Oscillator — "Where does the close sit in its recent range?"
# --------------------------------------------------------------------------- #
@register(
    "stochastic",
    "Stochastic Oscillator",
    "<p><strong>Stochastic Oscillator</strong> plots where the close sits within the high-low range of the last N bars. %K is the raw line (smoothed) and %D is a moving average of %K.</p><p><strong>Equation:</strong> <code>%K = 100 · (Close − LowestLow) / (HighestHigh − LowestLow); %D = SMA(%K)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Above 80 / below 20</strong> — overbought / oversold zones; extended moves often reverse from here.</li><li><strong>%K crossing %D</strong> — %K crossing above %D is a bullish trigger, below is bearish (strongest from the extremes).</li><li><strong>Divergence</strong> vs. price warns the current move is losing steam.</li></ul>",
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


# --------------------------------------------------------------------------- #
# CCI — "How far is price from its statistical average?"
# --------------------------------------------------------------------------- #
@register(
    "cci",
    "CCI",
    "<p><strong>Commodity Channel Index (CCI)</strong> measures how far the typical price has deviated from its average, scaled by mean deviation. It is unbounded but mostly oscillates within ±100.</p><p><strong>Equation:</strong> <code>CCI = (TP − SMA(TP)) / (0.015 · MeanDeviation)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Above +100</strong> — strong upside momentum (trend or overextension). <strong>Below −100</strong> — strong downside.</li><li><strong>Zero-line crosses</strong> mark momentum shifts.</li><li><strong>Snapping back inside ±100</strong> from an extreme can signal a mean-reversion trade.</li></ul>",
    params=[Param("period", "Period", 20, min=2, max=500)],
)
def cci(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Commodity Channel Index over ``period`` bars."""
    period = int(params["period"])
    tp = _typical_prices(bars)
    n = len(bars)
    series: Series = [None] * n
    for i in range(period - 1, n):
        window = tp[i - period + 1 : i + 1]
        mean = sum(window) / period
        mean_dev = sum(abs(x - mean) for x in window) / period
        series[i] = 0.0 if mean_dev == 0 else (tp[i] - mean) / (0.015 * mean_dev)

    latest = _last_non_none(series)
    if latest is None:
        reading = "insufficient data"
    elif latest > 100:
        reading = "bullish — strong upside (CCI > 100)"
    elif latest < -100:
        reading = "bearish — strong downside (CCI < -100)"
    else:
        reading = "neutral — within ±100"
    return Computation(latest=latest, reading=reading, lines={"cci": series})


# --------------------------------------------------------------------------- #
# Williams %R — "Where is the close vs the recent high-low range?"
# --------------------------------------------------------------------------- #
@register(
    "williams_r",
    "Williams %R",
    "<p><strong>Williams %R</strong> is a 0 to −100 momentum oscillator (the inverse of the Stochastic) showing where the close sits relative to the recent high-low range.</p><p><strong>Equation:</strong> <code>%R = −100 · (HighestHigh − Close) / (HighestHigh − LowestLow)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Above −20</strong> — overbought (near the top of the range). <strong>Below −80</strong> — oversold (near the bottom).</li><li><strong>Failure to reach an extreme</strong> on a new price swing hints momentum is fading.</li><li><strong>Crossing back out of an extreme</strong> is the typical trade trigger.</li></ul>",
    params=[Param("period", "Period", 14, min=2, max=500)],
)
def williams_r(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Williams %R over ``period`` bars."""
    period = int(params["period"])
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    n = len(bars)
    series: Series = [None] * n
    for i in range(period - 1, n):
        hh = max(highs[i - period + 1 : i + 1])
        ll = min(lows[i - period + 1 : i + 1])
        rng = hh - ll
        series[i] = 0.0 if rng == 0 else -100.0 * (hh - closes[i]) / rng

    latest = _last_non_none(series)
    if latest is None:
        reading = "insufficient data"
    elif latest > -20:
        reading = "overbought — near the top of its range"
    elif latest < -80:
        reading = "oversold — near the bottom of its range"
    else:
        reading = "neutral — mid-range"
    return Computation(latest=latest, reading=reading, lines={"williams_r": series})


# --------------------------------------------------------------------------- #
# ROC — "How fast is price changing in percent terms?"
# --------------------------------------------------------------------------- #
@register(
    "roc",
    "Rate of Change",
    "<p><strong>Rate of Change (ROC)</strong> is the percentage change in price over N bars — a pure momentum reading that oscillates around zero.</p><p><strong>Equation:</strong> <code>ROC = 100 · (Close_t − Close_{t−N}) / Close_{t−N}</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Zero-line crosses</strong> — rising above zero is bullish momentum, dropping below is bearish.</li><li><strong>Extreme readings</strong> — unusually high/low ROC flags an overextended move prone to reverting.</li><li><strong>Divergence</strong> vs. price warns the trend is tiring.</li></ul>",
    params=[Param("period", "Period", 12, min=1, max=500)],
)
def roc(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Percent rate of change over ``period`` bars."""
    period = int(params["period"])
    closes = [b["close"] for b in bars]
    n = len(closes)
    series: Series = [None] * n
    for i in range(period, n):
        prev = closes[i - period]
        series[i] = 0.0 if prev == 0 else 100.0 * (closes[i] - prev) / prev

    latest = _last_non_none(series)
    if latest is None:
        reading = "insufficient data"
    elif latest > 0:
        reading = "bullish — price rising vs N bars ago"
    elif latest < 0:
        reading = "bearish — price falling vs N bars ago"
    else:
        reading = "neutral — unchanged"
    return Computation(latest=latest, reading=reading, lines={"roc": series})


# --------------------------------------------------------------------------- #
# Momentum — "Absolute price change over N bars."
# --------------------------------------------------------------------------- #
@register(
    "momentum",
    "Momentum",
    "<p><strong>Momentum</strong> is the raw difference between the current close and the close N bars ago — the simplest measure of trend speed and direction.</p><p><strong>Equation:</strong> <code>MOM = Close_t − Close_{t−N}</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Zero-line crosses</strong> — above zero = upward momentum, below = downward.</li><li><strong>Rising magnitude</strong> on either side means the move is accelerating; shrinking toward zero means it is stalling.</li><li><strong>Divergence</strong> vs. price flags a weakening trend.</li></ul>",
    params=[Param("period", "Period", 10, min=1, max=500)],
)
def momentum(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Close minus the close ``period`` bars ago."""
    period = int(params["period"])
    closes = [b["close"] for b in bars]
    n = len(closes)
    series: Series = [None] * n
    for i in range(period, n):
        series[i] = closes[i] - closes[i - period]

    latest = _last_non_none(series)
    if latest is None:
        reading = "insufficient data"
    elif latest > 0:
        reading = "bullish — positive momentum"
    elif latest < 0:
        reading = "bearish — negative momentum"
    else:
        reading = "neutral — flat momentum"
    return Computation(latest=latest, reading=reading, lines={"momentum": series})


# --------------------------------------------------------------------------- #
# ATR — "How big is the typical bar's range right now?"
# --------------------------------------------------------------------------- #
@register(
    "atr",
    "ATR",
    "<p><strong>Average True Range (ATR)</strong> is the Wilder-smoothed average of the true range — a pure volatility gauge (in price units) that does not say anything about direction.</p><p><strong>Equation:</strong> <code>TR = max(H−L, |H−prevClose|, |L−prevClose|); ATR = Wilder(TR, N)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Rising ATR</strong> — volatility is expanding; widen stops and reduce size, breakouts are more likely to run.</li><li><strong>Falling / low ATR</strong> — compression; a quiet ATR often precedes a sharp expansion.</li><li><strong>Stop placement</strong> — many traders set stops a multiple of ATR away from entry.</li></ul>",
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


# --------------------------------------------------------------------------- #
# ADX — "How strong is the trend (regardless of direction)?"
# --------------------------------------------------------------------------- #
@register(
    "adx",
    "ADX",
    "<p><strong>Average Directional Index (ADX)</strong> measures trend strength on a 0–100 scale, with +DI and −DI showing direction. ADX itself is non-directional.</p><p><strong>Equation:</strong> <code>DX = 100 · |+DI − −DI| / (+DI + −DI); ADX = Wilder(DX, N)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>ADX above 25</strong> — a strong trend is in force; trend-following works. <strong>Below 20</strong> — weak/no trend (range, chop) — fade the edges instead.</li><li><strong>+DI above −DI</strong> = uptrend; −DI above +DI = downtrend. Their crosses signal direction changes.</li><li><strong>Rising ADX</strong> confirms a strengthening trend; a falling ADX warns it is losing power.</li></ul>",
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


# --------------------------------------------------------------------------- #
# Parabolic SAR — "Where is the trailing stop / trend flip?"
# --------------------------------------------------------------------------- #
@register(
    "parabolic_sar",
    "Parabolic SAR",
    "<p><strong>Parabolic SAR (Stop and Reverse)</strong> places a trailing dot that follows price; when price crosses it, the trend (and the dot's side) flips. It doubles as a trailing-stop level.</p><p><strong>Equation:</strong> <code>SAR_{t+1} = SAR_t + AF · (EP − SAR_t)</code>, AF rising each new extreme.</p><p><strong>What to Watch for:</strong></p><ul><li><strong>Dot below price</strong> — uptrend (use it as a trailing stop). <strong>Dot above price</strong> — downtrend.</li><li><strong>The flip</strong> — price crossing the SAR is the reversal signal and exit trigger.</li><li><strong>Best in trends</strong> — in choppy ranges it whipsaws, so pair it with a trend filter like ADX.</li></ul>",
    params=[
        Param("af_step", "AF Step", 0.02, min=0.001, max=0.5, type="float", step=0.01),
        Param("af_max", "AF Max", 0.2, min=0.05, max=1, type="float", step=0.05),
    ],
)
def parabolic_sar(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Classic Wilder Parabolic SAR."""
    step = params["af_step"]
    af_max = params["af_max"]
    n = len(bars)
    sar: Series = [None] * n
    if n < 2:
        return Computation(latest=None, reading="insufficient data", lines={"sar": sar})

    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]

    rising = highs[1] >= highs[0]
    af = step
    if rising:
        ep = highs[1]
        sar_val = lows[0]
    else:
        ep = lows[1]
        sar_val = highs[0]
    sar[1] = sar_val

    for i in range(2, n):
        sar_val = sar_val + af * (ep - sar_val)
        if rising:
            sar_val = min(sar_val, lows[i - 1], lows[i - 2])
            if highs[i] > ep:
                ep = highs[i]
                af = min(af + step, af_max)
            if lows[i] < sar_val:  # flip to downtrend
                rising = False
                sar_val = ep
                ep = lows[i]
                af = step
        else:
            sar_val = max(sar_val, highs[i - 1], highs[i - 2])
            if lows[i] < ep:
                ep = lows[i]
                af = min(af + step, af_max)
            if highs[i] > sar_val:  # flip to uptrend
                rising = True
                sar_val = ep
                ep = highs[i]
                af = step
        sar[i] = sar_val

    latest = _last_non_none(sar)
    last_close = bars[-1]["close"]
    if latest is None:
        reading = "insufficient data"
    elif last_close > latest:
        reading = "bullish — price above SAR (uptrend)"
    elif last_close < latest:
        reading = "bearish — price below SAR (downtrend)"
    else:
        reading = "neutral — price at SAR"
    return Computation(latest=latest, reading=reading, lines={"sar": sar})


# --------------------------------------------------------------------------- #
# Ichimoku Cloud — "What does the full trend system say?"
# --------------------------------------------------------------------------- #
@register(
    "ichimoku",
    "Ichimoku Cloud",
    "<p><strong>Ichimoku Cloud</strong> is a trend system: Tenkan (conversion) and Kijun (base) are midpoints of recent ranges, and the two Senkou spans form the 'cloud'. <em>Spans are shown aligned to the current bar (without the traditional forward displacement).</em></p><p><strong>Equation:</strong> <code>Line = (HighestHigh + LowestLow) / 2; SenkouA = (Tenkan + Kijun) / 2</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Price above the cloud</strong> — bullish; below the cloud — bearish; inside — no clear trend.</li><li><strong>Tenkan crossing Kijun</strong> — a momentum trigger (above = bullish, below = bearish).</li><li><strong>Cloud thickness</strong> — a thick cloud is strong support/resistance; a thin cloud is easier to break.</li></ul>",
    params=[
        Param("tenkan", "Tenkan", 9, min=2, max=200),
        Param("kijun", "Kijun", 26, min=2, max=200),
        Param("senkou_b", "Senkou B", 52, min=2, max=400),
    ],
)
def ichimoku(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Tenkan, Kijun and the two Senkou spans (aligned, no displacement)."""
    n = len(bars)
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]

    def midline(period: int) -> Series:
        out: Series = [None] * n
        for i in range(period - 1, n):
            hh = max(highs[i - period + 1 : i + 1])
            ll = min(lows[i - period + 1 : i + 1])
            out[i] = (hh + ll) / 2
        return out

    tenkan = midline(int(params["tenkan"]))
    kijun = midline(int(params["kijun"]))
    senkou_b = midline(int(params["senkou_b"]))
    senkou_a: Series = [None] * n
    for i in range(n):
        if tenkan[i] is not None and kijun[i] is not None:
            senkou_a[i] = (tenkan[i] + kijun[i]) / 2

    last_close = bars[-1]["close"] if bars else None
    la = _last_non_none(senkou_a)
    lb = _last_non_none(senkou_b)
    if last_close is None or la is None or lb is None:
        reading = "insufficient data"
    elif last_close > max(la, lb):
        reading = "bullish — price above the cloud"
    elif last_close < min(la, lb):
        reading = "bearish — price below the cloud"
    else:
        reading = "neutral — price inside the cloud"
    return Computation(
        latest=_last_non_none(tenkan),
        reading=reading,
        lines={
            "tenkan": tenkan,
            "kijun": kijun,
            "senkou_a": senkou_a,
            "senkou_b": senkou_b,
        },
    )


# --------------------------------------------------------------------------- #
# Keltner Channels — "EMA envelope sized by ATR."
# --------------------------------------------------------------------------- #
@register(
    "keltner",
    "Keltner Channels",
    "<p><strong>Keltner Channels</strong> wrap an EMA with bands set a multiple of ATR above and below it. Because they use ATR (not standard deviation), they are smoother than Bollinger Bands.</p><p><strong>Equation:</strong> <code>Mid = EMA(N); Upper/Lower = Mid ± mult · ATR</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Close above the upper channel</strong> — strong bullish momentum (often continuation). <strong>Below the lower channel</strong> — strong bearish momentum.</li><li><strong>Riding a band</strong> signals a powerful trend; a snap back to the middle is mean reversion.</li><li><strong>Squeeze vs. Bollinger</strong> — Bollinger Bands inside Keltner is the classic low-volatility 'squeeze' setup.</li></ul>",
    params=[
        Param("ema_period", "EMA Period", 20, min=2, max=500),
        Param("atr_period", "ATR Period", 10, min=2, max=500),
        Param("mult", "ATR Mult", 2, min=0.5, max=5, type="float", step=0.5),
    ],
)
def keltner(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """EMA midline with ATR-scaled upper/lower channels."""
    mult = params["mult"]
    closes = [b["close"] for b in bars]
    n = len(bars)
    middle = _ema(closes, int(params["ema_period"]))
    atr_s = _wilder(_true_range(bars), int(params["atr_period"]))

    upper: Series = [None] * n
    lower: Series = [None] * n
    for i in range(n):
        if middle[i] is not None and atr_s[i] is not None:
            upper[i] = middle[i] + mult * atr_s[i]
            lower[i] = middle[i] - mult * atr_s[i]

    last_close = closes[-1] if closes else None
    lu = _last_non_none(upper)
    ll = _last_non_none(lower)
    if last_close is None or lu is None or ll is None:
        reading = "insufficient data"
    elif last_close > lu:
        reading = "bullish — price above the upper channel"
    elif last_close < ll:
        reading = "bearish — price below the lower channel"
    else:
        reading = "neutral — price inside the channel"
    return Computation(
        latest=_last_non_none(middle),
        reading=reading,
        lines={"upper": upper, "middle": middle, "lower": lower},
    )


# --------------------------------------------------------------------------- #
# Donchian Channels — "Highest high / lowest low envelope."
# --------------------------------------------------------------------------- #
@register(
    "donchian",
    "Donchian Channels",
    "<p><strong>Donchian Channels</strong> plot the highest high and lowest low over the last N bars, with a midline between them. They are the basis of classic breakout systems.</p><p><strong>Equation:</strong> <code>Upper = max(High, N); Lower = min(Low, N); Mid = (Upper + Lower) / 2</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Close at the upper channel</strong> — a breakout to a new N-bar high (bullish trigger). <strong>At the lower channel</strong> — a breakdown to a new low.</li><li><strong>Channel width</strong> — narrowing channels show consolidation that often precedes a breakout.</li><li><strong>The midline</strong> acts as a trailing exit / mean for trend trades.</li></ul>",
    params=[Param("period", "Period", 20, min=2, max=500)],
)
def donchian(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Highest-high / lowest-low channel with a midline."""
    period = int(params["period"])
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    n = len(bars)
    upper: Series = [None] * n
    lower: Series = [None] * n
    middle: Series = [None] * n
    for i in range(period - 1, n):
        hh = max(highs[i - period + 1 : i + 1])
        ll = min(lows[i - period + 1 : i + 1])
        upper[i] = hh
        lower[i] = ll
        middle[i] = (hh + ll) / 2

    # Breakout = close clearing the channel built from the *prior* N bars
    # (excluding the current bar); comparing against the inclusive band would
    # never trigger since each bar's high is >= its close.
    last_close = bars[-1]["close"] if bars else None
    if last_close is None or n <= period:
        reading = "insufficient data"
    else:
        prior_upper = max(highs[n - 1 - period : n - 1])
        prior_lower = min(lows[n - 1 - period : n - 1])
        if last_close > prior_upper:
            reading = "bullish — breakout to a new high"
        elif last_close < prior_lower:
            reading = "bearish — breakdown to a new low"
        else:
            reading = "neutral — inside the channel"
    return Computation(
        latest=_last_non_none(middle),
        reading=reading,
        lines={"upper": upper, "middle": middle, "lower": lower},
    )


# --------------------------------------------------------------------------- #
# OBV — "Is volume confirming the price move?"
# --------------------------------------------------------------------------- #
@register(
    "obv",
    "On-Balance Volume",
    "<p><strong>On-Balance Volume (OBV)</strong> is a running total that adds the bar's volume on up closes and subtracts it on down closes — a cumulative read on whether volume backs the move.</p><p><strong>Equation:</strong> <code>OBV_t = OBV_{t−1} ± Volume_t (sign of the close change)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>OBV trending up</strong> with price — accumulation confirms the rally. <strong>Trending down</strong> — distribution confirms the decline.</li><li><strong>Divergence</strong> — price making new highs while OBV does not (or vice versa) warns the move lacks volume and may reverse.</li><li><strong>Breakouts</strong> backed by a sharp OBV move are more trustworthy.</li></ul>",
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
# VWAP — "What is the volume-weighted fair price?"
# --------------------------------------------------------------------------- #
@register(
    "vwap",
    "VWAP",
    "<p><strong>Volume Weighted Average Price (VWAP)</strong> is the average price weighted by volume over the last N bars — the level where most of the volume actually traded.</p><p><strong>Equation:</strong> <code>VWAP = Σ(TypicalPrice · Volume) / Σ(Volume)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Price above VWAP</strong> — buyers in control (bullish bias); below — sellers in control.</li><li><strong>VWAP as support/resistance</strong> — intraday, price often reverts to VWAP; reactions there are common entry points.</li><li><strong>Reclaiming or losing VWAP</strong> after a test signals which side won.</li></ul>",
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
# MFI — "Volume-weighted RSI: overbought/oversold with volume."
# --------------------------------------------------------------------------- #
@register(
    "mfi",
    "Money Flow Index",
    "<p><strong>Money Flow Index (MFI)</strong> is a volume-weighted RSI: a 0–100 oscillator comparing positive and negative money flow (typical price × volume) over N bars.</p><p><strong>Equation:</strong> <code>MFI = 100 − 100 / (1 + PositiveFlow / NegativeFlow)</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Above 80</strong> — overbought with volume behind it. <strong>Below 20</strong> — oversold.</li><li><strong>Divergence</strong> — because it includes volume, MFI divergences are often a stronger reversal warning than RSI's.</li><li><strong>Failure swings</strong> around the extremes can mark turning points.</li></ul>",
    params=[Param("period", "Period", 14, min=2, max=500)],
)
def mfi(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Money Flow Index over ``period`` bars."""
    period = int(params["period"])
    tp = _typical_prices(bars)
    n = len(bars)
    pos = [0.0] * n
    neg = [0.0] * n
    for i in range(1, n):
        raw = tp[i] * bars[i]["volume"]
        if tp[i] > tp[i - 1]:
            pos[i] = raw
        elif tp[i] < tp[i - 1]:
            neg[i] = raw

    series: Series = [None] * n
    for i in range(period, n):
        pos_sum = sum(pos[i - period + 1 : i + 1])
        neg_sum = sum(neg[i - period + 1 : i + 1])
        if neg_sum == 0:
            series[i] = 100.0 if pos_sum > 0 else None
        else:
            series[i] = 100.0 - 100.0 / (1.0 + pos_sum / neg_sum)

    latest = _last_non_none(series)
    if latest is None:
        reading = "insufficient data"
    elif latest > 80:
        reading = "overbought — money flow stretched high"
    elif latest < 20:
        reading = "oversold — money flow stretched low"
    else:
        reading = "neutral — money flow balanced"
    return Computation(latest=latest, reading=reading, lines={"mfi": series})


# --------------------------------------------------------------------------- #
# CMF — "Net buying vs selling pressure inside each bar."
# --------------------------------------------------------------------------- #
@register(
    "cmf",
    "Chaikin Money Flow",
    "<p><strong>Chaikin Money Flow (CMF)</strong> sums the Money Flow Volume over N bars and divides by total volume. It weights each bar by where the close finished within its range.</p><p><strong>Equation:</strong> <code>MFV = ((C−L) − (H−C)) / (H−L) · Volume; CMF = ΣMFV / ΣVolume</code></p><p><strong>What to Watch for:</strong></p><ul><li><strong>Above 0</strong> (esp. > 0.05) — net buying pressure; closes finishing in the upper part of their range. <strong>Below 0</strong> (< −0.05) — net selling.</li><li><strong>Zero-line crosses</strong> mark shifts between accumulation and distribution.</li><li><strong>Divergence</strong> vs. price warns the move is not backed by money flow.</li></ul>",
    params=[Param("period", "Period", 20, min=2, max=500)],
)
def cmf(bars: list[Bar], params: Params, timeframe: str) -> Computation:
    """Chaikin Money Flow over ``period`` bars."""
    period = int(params["period"])
    n = len(bars)
    mfv = [0.0] * n
    for i in range(n):
        high, low, close = bars[i]["high"], bars[i]["low"], bars[i]["close"]
        rng = high - low
        mult = ((close - low) - (high - close)) / rng if rng != 0 else 0.0
        mfv[i] = mult * bars[i]["volume"]

    series: Series = [None] * n
    for i in range(period - 1, n):
        vol_sum = sum(bars[j]["volume"] for j in range(i - period + 1, i + 1))
        if vol_sum == 0:
            continue
        series[i] = sum(mfv[i - period + 1 : i + 1]) / vol_sum

    latest = _last_non_none(series)
    if latest is None:
        reading = "insufficient data"
    elif latest > 0.05:
        reading = "buying — positive money flow"
    elif latest < -0.05:
        reading = "selling — negative money flow"
    else:
        reading = "neutral — flat money flow"
    return Computation(latest=latest, reading=reading, lines={"cmf": series})


# --------------------------------------------------------------------------- #
# Public API used by the router
# --------------------------------------------------------------------------- #
def available() -> list[dict]:
    """Catalog metadata for every registered indicator, including param schema."""
    return [
        {
            "key": s.key,
            "label": s.label,
            "description": s.description,
            "params": [asdict(p) for p in s.params],
        }
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
            "params": params,
            "latest": comp.latest,
            "reading": comp.reading,
            "series": {
                name: _to_points(bars, line) for name, line in comp.lines.items()
            },
            "extra": comp.extra,
        }
    return results
