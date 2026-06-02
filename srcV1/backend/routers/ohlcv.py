from fastapi import APIRouter, HTTPException, Query

from models import OHLCVResponse
from services.alpaca_client import (
    TIMEFRAME_MAP,
    AlpacaError,
    fetch_historical_ohlcv,
)

router = APIRouter(prefix="/api", tags=["ohlcv"])


@router.get("/ohlcv", response_model=OHLCVResponse)
def get_ohlcv(
    symbol: str = Query(..., description="Ticker symbol, e.g. AAPL"),
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end: str = Query(..., description="End date (YYYY-MM-DD)"),
    timeframe: str = Query("1d", description=f"One of {list(TIMEFRAME_MAP)}"),
):
    """Return historical OHLCV bars for a symbol over a date range."""
    if timeframe not in TIMEFRAME_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Choose from: {list(TIMEFRAME_MAP)}",
        )
    try:
        return fetch_historical_ohlcv(symbol, timeframe, start, end)
    except AlpacaError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
