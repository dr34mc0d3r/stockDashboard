"""ORM models for stored market data and ingestion bookkeeping."""

from datetime import datetime

from sqlalchemy import DECIMAL, BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db import Base

# Prices stored as DECIMAL(18,6) — exact, no float drift.
Price = DECIMAL(18, 6)


class OhlcvBar(Base):
    """A single OHLCV bar.

    Composite primary key (symbol, timeframe, ts) clusters rows for fast
    per-symbol range scans and gives free dedupe for idempotent UPSERTs.
    """

    __tablename__ = "ohlcv_bars"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    open: Mapped[float] = mapped_column(Price)
    high: Mapped[float] = mapped_column(Price)
    low: Mapped[float] = mapped_column(Price)
    close: Mapped[float] = mapped_column(Price)
    volume: Mapped[int] = mapped_column(BigInteger)


class IngestionRun(Base):
    """Audit record for one data-acquisition request."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16))
    timeframe: Mapped[str] = mapped_column(String(8))
    start: Mapped[str] = mapped_column(String(40))
    end: Mapped[str] = mapped_column(String(40))
    bars_fetched: Mapped[int] = mapped_column(Integer, default=0)
    bars_written: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    detail: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
