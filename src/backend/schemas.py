"""Pydantic request/response schemas for the data + training APIs."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Timeframe = Literal["1m", "5m", "1h", "1d"]


class IngestRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16, examples=["AAPL"])
    start: str = Field(..., description="ISO date YYYY-MM-DD or RFC3339")
    end: str = Field(..., description="ISO date YYYY-MM-DD or RFC3339")
    timeframe: Timeframe = "1m"

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


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
    split: tuple[float, float, float] = (0.7, 0.15, 0.15)


class TrainLstmRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16, examples=["AAPL"])
    timeframe: Timeframe = "1m"
    start: str | None = Field(default=None, description="ISO date; optional slice start")
    end: str | None = Field(default=None, description="ISO date; optional slice end")
    hyperparams: LstmHyperParams = Field(default_factory=LstmHyperParams)

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class TrainingRunOut(BaseModel):
    id: int
    stage: str
    symbol: str
    timeframe: str
    status: str
    hyperparams: dict[str, Any]
    progress: list[Any]
    metrics: dict[str, Any] | None
    artifact_path: str | None
    detail: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
