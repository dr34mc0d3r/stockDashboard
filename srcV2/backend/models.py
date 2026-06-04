"""ORM models for stored market data and ingestion bookkeeping."""

from datetime import datetime
from typing import Any

from sqlalchemy import DECIMAL, JSON, BigInteger, DateTime, Integer, String, Text, func
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


class TrainingRun(Base):
    """One model-training run: the hyperparams it used, how it scored, and
    where the saved artifact lives. Shared by every Lab stage from 2 on.

    `status` moves queued → running → done | error. `progress` (epoch JSON
    list) and `metrics` (final summary JSON) are filled as the run proceeds,
    so the frontend can poll a single row for live training progress.
    """

    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stage: Mapped[str] = mapped_column(String(32))  # e.g. "lstm"
    symbol: Mapped[str] = mapped_column(String(16))
    timeframe: Mapped[str] = mapped_column(String(8))
    # The data slice the run trained on (nullable; older rows predate this).
    start: Mapped[str | None] = mapped_column(String(40), nullable=True)
    end: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    hyperparams: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    progress: Mapped[list[Any]] = mapped_column(JSON, default=list)  # per-epoch metrics
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")  # error/trace if status=error
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class FeatureCache(Base):
    """Cache for expensive per-bar features (indicators, sentiment, GDELT tone).

    Keyed by (symbol, timeframe, ts, feature_set) so a named feature bundle is
    computed once and reused forever. Used from Stage 3 on.
    """

    __tablename__ = "feature_cache"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    feature_set: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
