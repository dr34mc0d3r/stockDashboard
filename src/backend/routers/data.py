"""Stage 1 data endpoints: stored-data inventory, bar fetch, bar delete.

Thin HTTP layer: normalize inputs, call services/bar_service.py, shape the
response models.
"""

from fastapi import APIRouter, Query

from db import SessionDep
from schemas import BarOut, InventoryItem, normalize_symbol
from services import bar_service

router = APIRouter(prefix="/api/v1", tags=["data"])


@router.get("/inventory", response_model=list[InventoryItem])
def inventory(session: SessionDep) -> list[InventoryItem]:
    """What's already stored, per (symbol, timeframe)."""
    return [
        InventoryItem(
            symbol=r.symbol,
            timeframe=r.timeframe,
            bar_count=r.bar_count,
            earliest=r.earliest,
            latest=r.latest,
        )
        for r in bar_service.inventory_rows(session)
    ]


@router.get("/bars", response_model=list[BarOut])
def bars(
    symbol: str,
    session: SessionDep,
    timeframe: str = "1m",
    start: str | None = None,
    end: str | None = None,
    limit: int = Query(default=5000, le=50000),
) -> list[BarOut]:
    """Return stored bars for a symbol/timeframe, oldest first.

    Used by the chart and (later) by Lab stages selecting a data slice.
    """
    rows = bar_service.query_bars(session, normalize_symbol(symbol), timeframe, start, end, limit)
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
def delete_bars(symbol: str, timeframe: str, session: SessionDep) -> dict:
    """Delete all stored bars for a (symbol, timeframe). Returns rows removed."""
    canonical = normalize_symbol(symbol)
    deleted = bar_service.delete_bars(session, canonical, timeframe)
    return {"symbol": canonical, "timeframe": timeframe, "deleted": deleted}
