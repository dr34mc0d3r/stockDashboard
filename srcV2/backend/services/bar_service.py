"""Query helpers for stored OHLCV bars.

The SQL behind the data router lives here so the router stays a thin HTTP
layer: parse the request, call one of these, shape the response. Symbols are
expected to be canonical already (see schemas.normalize_symbol).
"""

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from models import OhlcvBar


def inventory_rows(session: Session) -> list[Row]:
    """Per-(symbol, timeframe) summary: bar count and the stored time range."""
    return list(
        session.execute(
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
    )


def query_bars(
    session: Session,
    symbol: str,
    timeframe: str,
    start: str | None = None,
    end: str | None = None,
    limit: int = 5000,
) -> list[OhlcvBar]:
    """Stored bars for a symbol/timeframe, oldest first, optionally date-sliced."""
    stmt = select(OhlcvBar).where(OhlcvBar.symbol == symbol, OhlcvBar.timeframe == timeframe)
    if start:
        stmt = stmt.where(OhlcvBar.ts >= start)
    if end:
        stmt = stmt.where(OhlcvBar.ts <= end)
    stmt = stmt.order_by(OhlcvBar.ts.asc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def query_recent_bars(
    session: Session,
    symbol: str,
    timeframe: str,
    start: str | None = None,
    end: str | None = None,
    limit: int = 2000,
) -> list[OhlcvBar]:
    """The NEWEST ``limit`` bars in the slice, returned oldest-first.

    `query_bars` truncates from the front (oldest); chart previews want the
    most recent window instead, so this orders descending, limits, and flips.
    """
    stmt = select(OhlcvBar).where(OhlcvBar.symbol == symbol, OhlcvBar.timeframe == timeframe)
    if start:
        stmt = stmt.where(OhlcvBar.ts >= start)
    if end:
        stmt = stmt.where(OhlcvBar.ts <= end)
    stmt = stmt.order_by(OhlcvBar.ts.desc()).limit(limit)
    rows = list(session.execute(stmt).scalars().all())
    rows.reverse()
    return rows


def delete_bars(session: Session, symbol: str, timeframe: str) -> int:
    """Delete all stored bars for a (symbol, timeframe); returns rows removed."""
    result = session.execute(
        sa_delete(OhlcvBar).where(OhlcvBar.symbol == symbol, OhlcvBar.timeframe == timeframe)
    )
    session.commit()
    return result.rowcount
