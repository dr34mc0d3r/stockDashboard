"""Stage 3 feature endpoints: the indicator catalog and on-demand computation.

`GET /indicators/catalog` returns every registered indicator's metadata (label,
description, placement, param schema) so the UI builds its toggle panel from
the backend — params can never drift between the two.

`POST /indicators` computes the requested indicators over a STORED bar slice
(this lab never recomputes from a live feed) and returns the bars alongside the
aligned series, so one request renders a complete chart preview. The exact same
`indicators.compute()` feeds the ML feature pipeline.
"""

from fastapi import APIRouter, HTTPException

from db import SessionDep
from schemas import BarOut, IndicatorsRequest, IndicatorsResponse
from services import bar_service
from services.features import indicators

router = APIRouter(prefix="/api/v1", tags=["features"])


@router.get("/indicators/catalog")
def indicator_catalog() -> dict:
    """Metadata for every registered indicator, including its param schema."""
    return {"indicators": indicators.available()}


@router.post("/indicators", response_model=IndicatorsResponse)
def compute_indicators(req: IndicatorsRequest, session: SessionDep) -> IndicatorsResponse:
    """Compute the requested indicators over stored bars, oldest first."""
    try:
        keys = indicators.resolve_keys([item.name for item in req.indicators])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    rows = bar_service.query_recent_bars(
        session, req.symbol, req.timeframe, req.start, req.end, req.limit
    )
    # The indicator functions take plain bar dicts (the srcV1 contract).
    bars = [
        {
            "timestamp": r.ts.isoformat(),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": int(r.volume),
        }
        for r in rows
    ]
    params_by_key = {item.name: item.params for item in req.indicators}
    results = indicators.compute(bars, req.timeframe, keys, params_by_key)

    return IndicatorsResponse(
        symbol=req.symbol,
        timeframe=req.timeframe,
        bar_count=len(bars),
        bars=[
            BarOut(
                ts=b["timestamp"],
                open=b["open"],
                high=b["high"],
                low=b["low"],
                close=b["close"],
                volume=b["volume"],
            )
            for b in bars
        ],
        indicators=results,
    )
