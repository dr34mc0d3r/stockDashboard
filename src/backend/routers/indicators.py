from fastapi import APIRouter, HTTPException, Query

from models import IndicatorCatalog, IndicatorsResponse
from services import indicators as ind
from services.alpaca_client import (
    TIMEFRAME_MAP,
    AlpacaError,
    fetch_historical_ohlcv,
)

router = APIRouter(prefix="/api", tags=["indicators"])


@router.get("/indicators/catalog", response_model=IndicatorCatalog)
def get_catalog():
    """List every available indicator so the client can build its UI."""
    return {"indicators": ind.available()}


@router.get("/indicators", response_model=IndicatorsResponse)
def get_indicators(
    symbol: str = Query(..., description="Ticker symbol, e.g. AAPL"),
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    timeframe: str = Query("1d", description=f"One of {list(TIMEFRAME_MAP)}"),
    period: int = Query(14, ge=2, description="Lookback window in bars"),
    include: str = Query(
        "all",
        description="Comma-separated indicator keys, or 'all'. See /api/indicators/catalog.",
    ),
):
    """Compute the requested indicators over the OHLCV bars for a symbol."""
    if timeframe not in TIMEFRAME_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Choose from: {list(TIMEFRAME_MAP)}",
        )
    try:
        keys = ind.resolve_keys(include)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        data = fetch_historical_ohlcv(symbol, timeframe, start, end)
    except AlpacaError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    return {
        "symbol": data["symbol"],
        "timeframe": data["timeframe"],
        "start": data["start"],
        "end": data["end"],
        "period": period,
        "results_count": len(data["bars"]),
        "indicators": ind.compute(data["bars"], period, data["timeframe"], keys),
    }
