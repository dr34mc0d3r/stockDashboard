from fastapi import APIRouter, HTTPException

from models import IndicatorCatalog, IndicatorsRequest, IndicatorsResponse
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


@router.post("/indicators", response_model=IndicatorsResponse)
def get_indicators(req: IndicatorsRequest):
    """Compute the requested indicators over the OHLCV bars for a symbol.

    Indicators are POSTed with per-indicator params because different
    indicators take different tunables (MACD's fast/slow/signal, Bollinger's
    period + std-dev multiplier, …) that don't fit a single query parameter.
    """
    if req.timeframe not in TIMEFRAME_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe. Choose from: {list(TIMEFRAME_MAP)}",
        )
    try:
        # resolve_keys takes the legacy comma-string form; "all" when unset.
        keys = ind.resolve_keys(",".join(req.include) if req.include else "all")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        data = fetch_historical_ohlcv(req.symbol, req.timeframe, req.start, req.end)
    except AlpacaError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    return {
        "symbol": data["symbol"],
        "timeframe": data["timeframe"],
        "start": data["start"],
        "end": data["end"],
        "results_count": len(data["bars"]),
        "indicators": ind.compute(
            data["bars"], data["timeframe"], keys, req.params
        ),
    }
