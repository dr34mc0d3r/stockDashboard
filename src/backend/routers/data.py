"""Stage 1 data endpoints: stored-data inventory."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_session
from models import OhlcvBar
from schemas import BarOut, InventoryItem

router = APIRouter(prefix="/api/v1", tags=["data"])


@router.get("/inventory", response_model=list[InventoryItem])
def inventory(session: Session = Depends(get_session)):
    """What's already stored, per (symbol, timeframe)."""
    rows = session.execute(
        select(
            OhlcvBar.symbol,
            OhlcvBar.timeframe,
            func.count().label("bar_count"),
            func.min(OhlcvBar.ts).label("earliest"),
            func.max(OhlcvBar.ts).label("latest"),
        )
        .group_by(OhlcvBar.symbol, OhlcvBar.timeframe)
        .order_by(OhlcvBar.symbol, OhlcvBar.timeframe)
    ).all()
    return [
        InventoryItem(
            symbol=r.symbol,
            timeframe=r.timeframe,
            bar_count=r.bar_count,
            earliest=r.earliest,
            latest=r.latest,
        )
        for r in rows
    ]


@router.get("/bars", response_model=list[BarOut])
def bars(
    symbol: str,
    timeframe: str = "1m",
    start: str | None = None,
    end: str | None = None,
    limit: int = Query(default=5000, le=50000),
    session: Session = Depends(get_session),
):
    """Return stored bars for a symbol/timeframe, oldest first.

    Used by the chart and (later) by Lab stages selecting a data slice.
    """
    stmt = select(OhlcvBar).where(
        OhlcvBar.symbol == symbol.upper(), OhlcvBar.timeframe == timeframe
    )
    if start:
        stmt = stmt.where(OhlcvBar.ts >= start)
    if end:
        stmt = stmt.where(OhlcvBar.ts <= end)
    stmt = stmt.order_by(OhlcvBar.ts.asc()).limit(limit)
    rows = session.execute(stmt).scalars().all()
    return [
        BarOut(
            ts=b.ts,
            open=float(b.open),
            high=float(b.high),
            low=float(b.low),
            close=float(b.close),
            volume=b.volume,
        )
        for b in rows
    ]


@router.delete("/bars")
def delete_bars(
    symbol: str,
    timeframe: str,
    session: Session = Depends(get_session),
):
    """Delete all stored bars for a (symbol, timeframe). Returns rows removed."""
    result = session.execute(
        sa_delete(OhlcvBar).where(
            OhlcvBar.symbol == symbol.upper(), OhlcvBar.timeframe == timeframe
        )
    )
    session.commit()
    return {"symbol": symbol.upper(), "timeframe": timeframe, "deleted": result.rowcount}
