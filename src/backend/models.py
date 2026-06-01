from pydantic import BaseModel


class Bar(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class OHLCVResponse(BaseModel):
    symbol: str
    timeframe: str
    start: str
    end: str
    results_count: int
    bars: list[Bar]


class IndicatorPoint(BaseModel):
    timestamp: str
    value: float | None


class ParamMeta(BaseModel):
    """One tunable parameter of an indicator, used to render its UI control."""

    name: str
    label: str
    default: float
    min: float | None = None
    max: float | None = None
    type: str = "int"
    step: float | None = None


class IndicatorMeta(BaseModel):
    """Catalog entry describing one available indicator."""

    key: str
    label: str
    description: str
    params: list[ParamMeta] = []


class IndicatorCatalog(BaseModel):
    indicators: list[IndicatorMeta]


class IndicatorResult(BaseModel):
    """Uniform result shape shared by every indicator."""

    key: str
    label: str
    description: str
    # The resolved parameter values actually used for this computation.
    params: dict[str, float] = {}
    latest: float | None
    reading: str
    # One or more named series (e.g. "acceleration" + "velocity").
    series: dict[str, list[IndicatorPoint]]
    # Scalar extras (e.g. "annualized", "mfi").
    extra: dict[str, float | None] = {}


class IndicatorsRequest(BaseModel):
    """Body for POST /api/indicators."""

    symbol: str
    start: str
    end: str
    timeframe: str = "1d"
    # Indicator keys to compute; None or empty means "all".
    include: list[str] | None = None
    # Per-indicator raw params, e.g. {"macd": {"fast": 12, "slow": 26}}.
    # Anything omitted falls back to each indicator's declared defaults.
    params: dict[str, dict[str, float]] = {}


class IndicatorsResponse(BaseModel):
    symbol: str
    timeframe: str
    start: str
    end: str
    results_count: int
    # Keyed by indicator key; only requested indicators are present.
    indicators: dict[str, IndicatorResult]
