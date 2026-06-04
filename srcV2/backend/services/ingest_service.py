"""Fetch bars from Alpaca and UPSERT them into MariaDB."""

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from models import IngestionRun, OhlcvBar
from services.alpaca_client import AlpacaError, fetch_bars

# Insert in chunks so a single huge statement (e.g. months of 1-min bars)
# doesn't exceed max_allowed_packet on the modest remote server.
CHUNK_SIZE = 2000


def _upsert_bars(session: Session, symbol: str, timeframe: str, bars: list[dict]) -> None:
    """Idempotent bulk insert: on PK conflict, refresh OHLCV values."""
    for i in range(0, len(bars), CHUNK_SIZE):
        chunk = bars[i : i + CHUNK_SIZE]
        rows = [{"symbol": symbol, "timeframe": timeframe, **bar} for bar in chunk]
        stmt = mysql_insert(OhlcvBar).values(rows)
        stmt = stmt.on_duplicate_key_update(
            open=stmt.inserted.open,
            high=stmt.inserted.high,
            low=stmt.inserted.low,
            close=stmt.inserted.close,
            volume=stmt.inserted.volume,
        )
        session.execute(stmt)


def ingest(session: Session, symbol: str, timeframe: str, start: str, end: str) -> dict:
    """Download a range and store it. Returns a summary dict.

    Records an IngestionRun either way (status 'ok' or 'error').
    """
    run = IngestionRun(symbol=symbol, timeframe=timeframe, start=start, end=end)

    try:
        bars = fetch_bars(symbol, timeframe, start, end)
    except AlpacaError as e:
        run.status = "error"
        run.detail = str(e)[:512]
        session.add(run)
        session.commit()
        raise

    if bars:
        _upsert_bars(session, symbol, timeframe, bars)

    run.bars_fetched = len(bars)
    run.bars_written = len(bars)
    run.status = "ok"
    session.add(run)
    session.commit()

    # Report the actual stored range for this symbol/timeframe.
    first_ts, last_ts = session.execute(
        select(func.min(OhlcvBar.ts), func.max(OhlcvBar.ts)).where(
            OhlcvBar.symbol == symbol, OhlcvBar.timeframe == timeframe
        )
    ).one()

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "start": start,
        "end": end,
        "bars_fetched": len(bars),
        "bars_written": len(bars),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "status": "ok",
    }
