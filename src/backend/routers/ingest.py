"""Stage 1 ingest endpoint: download Alpaca bars into MariaDB."""

from fastapi import APIRouter, HTTPException

from db import SessionDep
from schemas import IngestRequest, IngestResponse
from services.alpaca_client import AlpacaError
from services.ingest_service import ingest

router = APIRouter(prefix="/api/v1", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
def ingest_data(req: IngestRequest, session: SessionDep):
    if req.start >= req.end:
        raise HTTPException(status_code=400, detail="start must be before end")
    try:
        return ingest(session, req.symbol, req.timeframe, req.start, req.end)
    except AlpacaError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
