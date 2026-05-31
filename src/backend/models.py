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


class IndicatorMeta(BaseModel):
    """Catalog entry describing one available indicator."""

    key: str
    label: str
    description: str


class IndicatorCatalog(BaseModel):
    indicators: list[IndicatorMeta]


class IndicatorResult(BaseModel):
    """Uniform result shape shared by every indicator."""

    key: str
    label: str
    description: str
    latest: float | None
    reading: str
    # One or more named series (e.g. "acceleration" + "velocity").
    series: dict[str, list[IndicatorPoint]]
    # Scalar extras (e.g. "annualized", "mfi").
    extra: dict[str, float | None] = {}


class IndicatorsResponse(BaseModel):
    symbol: str
    timeframe: str
    start: str
    end: str
    period: int
    results_count: int
    # Keyed by indicator key; only requested indicators are present.
    indicators: dict[str, IndicatorResult]
