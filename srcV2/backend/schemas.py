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


class PredictionPoint(BaseModel):
    ts: datetime
    prob: float  # model's P(up) for the next bar
    pred: int  # 1 = predicted up, 0 = predicted down
    actual: int  # what actually happened (1 up / 0 down)


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
