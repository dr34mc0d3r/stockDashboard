"""Pydantic request/response schemas for the data + training APIs."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Timeframe = Literal["1m", "5m", "1h", "1d"]


def normalize_symbol(value: str) -> str:
    """Canonical ticker form: trimmed and uppercased.

    The single place symbol normalization happens. Request schemas apply it via
    their validators; the data router applies it to raw query params. Code past
    those entry points can assume symbols are already canonical.
    """
    return value.strip().upper()


class IngestRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16, examples=["AAPL"])
    start: str = Field(..., description="ISO date YYYY-MM-DD or RFC3339")
    end: str = Field(..., description="ISO date YYYY-MM-DD or RFC3339")
    timeframe: Timeframe = "1m"

    @field_validator("symbol")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_symbol(v)


class IngestResponse(BaseModel):
    symbol: str
    timeframe: str
    start: str
    end: str
    bars_fetched: int
    bars_written: int
    first_ts: datetime | None
    last_ts: datetime | None
    status: str


class InventoryItem(BaseModel):
    symbol: str
    timeframe: str
    bar_count: int
    earliest: datetime
    latest: datetime


class BarOut(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class IndicatorRequestItem(BaseModel):
    """One requested indicator: its registry key plus any param overrides."""

    name: str = Field(..., min_length=1, max_length=32, examples=["rsi"])
    params: dict[str, float] = Field(default_factory=dict)


class IndicatorsRequest(BaseModel):
    """Compute indicators over a stored bar slice (for charts and previews)."""

    symbol: str = Field(..., min_length=1, max_length=16, examples=["AAPL"])
    timeframe: Timeframe = "1m"
    start: str | None = Field(default=None, description="ISO date; optional slice start")
    end: str | None = Field(default=None, description="ISO date; optional slice end")
    limit: int = Field(default=2000, ge=10, le=20000)
    indicators: list[IndicatorRequestItem] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_symbol(v)


class IndicatorsResponse(BaseModel):
    """Bars plus the computed indicator series — one request renders a chart.

    Each indicator payload is dynamic (named series, params, reading), so it
    stays a plain dict; see services/features/indicators.compute for the shape.
    """

    symbol: str
    timeframe: str
    bar_count: int
    bars: list[BarOut]
    indicators: dict[str, Any]


class SentimentPrepRequest(BaseModel):
    """Stage 4: fetch + FinBERT-score a headline corpus for a symbol/range."""

    symbol: str = Field(..., min_length=1, max_length=16, examples=["TSLA"])
    start: str = Field(..., description="ISO date; corpus range start")
    end: str = Field(..., description="ISO date; corpus range end")
    max_articles: int = Field(default=300, ge=10, le=1000)

    @field_validator("symbol")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_symbol(v)


class HeadlineOut(BaseModel):
    ts: datetime
    headline: str
    source: str
    url: str
    pos: float | None
    neg: float | None
    neutral: float | None

    model_config = {"from_attributes": True}


class CoverageDay(BaseModel):
    day: str  # ISO date
    count: int
    net: float


class CoverageOut(BaseModel):
    symbol: str
    days_with_news: int
    first_day: str | None
    last_day: str | None
    daily: list[CoverageDay]


class LstmHyperParams(BaseModel):
    """Stage 2 defaults — CPU-friendly small LSTM (see PLAN.md)."""

    seq_len: int = Field(default=60, ge=5, le=240)
    horizon: int = Field(default=1, ge=1, le=20)
    hidden: int = Field(default=64, ge=8, le=128)
    layers: int = Field(default=2, ge=1, le=3)
    dropout: float = Field(default=0.2, ge=0.0, le=0.8)
    lr: float = Field(default=1e-3, gt=0, le=1.0)
    batch: int = Field(default=64, ge=8, le=512)
    epochs: int = Field(default=30, ge=1, le=200)
    patience: int = Field(default=5, ge=1, le=50)
    lr_factor: float = Field(default=0.5, gt=0, lt=1, description="LR multiplier on plateau")
    lr_patience: int = Field(default=2, ge=1, le=20, description="epochs before LR drop")
    split: tuple[float, float, float] = (0.7, 0.15, 0.15)


class TrainLstmRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16, examples=["AAPL"])
    timeframe: Timeframe = "1m"
    start: str | None = Field(default=None, description="ISO date; optional slice start")
    end: str | None = Field(default=None, description="ISO date; optional slice end")
    hyperparams: LstmHyperParams = Field(default_factory=LstmHyperParams)

    @field_validator("symbol")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_symbol(v)


class SentimentConfig(BaseModel):
    """Stage 4: attach cached FinBERT daily sentiment as features."""

    enabled: bool = False
    lag_days: int = Field(default=1, ge=0, le=5, description="bars on day D read day D-lag")


class MultiTaskHyperParams(LstmHyperParams):
    """Stage 3: the Stage 2 knobs plus per-task loss weights, the volatility
    target window, and the indicator feature config. Stage 4 adds the optional
    sentiment block."""

    w_dir: float = Field(default=1.0, ge=0.0, le=10.0, description="direction loss weight")
    w_ret: float = Field(default=1.0, ge=0.0, le=10.0, description="return loss weight")
    w_vol: float = Field(default=1.0, ge=0.0, le=10.0, description="volatility loss weight")
    vol_window: int = Field(default=5, ge=2, le=60, description="bars of realized vol to predict")
    indicators: list[IndicatorRequestItem] = Field(default_factory=list)
    sentiment: SentimentConfig = Field(default_factory=SentimentConfig)


class TrainMultiTaskRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16, examples=["TSLA"])
    timeframe: Timeframe = "1m"
    start: str | None = Field(default=None, description="ISO date; optional slice start")
    end: str | None = Field(default=None, description="ISO date; optional slice end")
    hyperparams: MultiTaskHyperParams = Field(default_factory=MultiTaskHyperParams)

    @field_validator("symbol")
    @classmethod
    def _normalize(cls, v: str) -> str:
        return normalize_symbol(v)


class PredictionPoint(BaseModel):
    ts: datetime
    prob: float  # model's P(up) for the next bar
    pred: int  # 1 = predicted up, 0 = predicted down
    actual: int  # what actually happened (1 up / 0 down)
    # Stage 3 extras (multitask runs only):
    pred_return: float | None = None  # predicted log return over the horizon
    pred_vol: float | None = None  # predicted realized vol over vol_window bars
    actual_return: float | None = None


class PredictionsOut(BaseModel):
    symbol: str
    timeframe: str
    seq_len: int
    horizon: int
    out_of_sample: bool  # True when markers are confined to the held-out test region
    bars: list[BarOut]
    predictions: list[PredictionPoint]


class TrainingRunOut(BaseModel):
    id: int
    stage: str
    symbol: str
    timeframe: str
    start: str | None
    end: str | None
    status: str
    hyperparams: dict[str, Any]
    progress: list[Any]
    metrics: dict[str, Any] | None
    artifact_path: str | None
    detail: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
