"""Pydantic request/response schemas for the Stage 1 data API."""

from datetime import datetime
from typing import Literal

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
