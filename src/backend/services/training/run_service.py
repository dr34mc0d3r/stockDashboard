"""TrainingRun bookkeeping for the train endpoints.

The router decides *what HTTP to speak* (status codes, error details); this
module owns the DB work: checking that data exists and creating the run row
the background trainer will update.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import OhlcvBar, TrainingRun
from schemas import TrainLstmRequest


def count_bars(session: Session, symbol: str, timeframe: str) -> int:
    """How many bars are stored for this (symbol, timeframe)."""
    return session.execute(
        select(func.count())
        .select_from(OhlcvBar)
        .where(OhlcvBar.symbol == symbol, OhlcvBar.timeframe == timeframe)
    ).scalar_one()


def create_run(session: Session, req: TrainLstmRequest) -> TrainingRun:
    """Insert a queued TrainingRun row for this request and return it."""
    run = TrainingRun(
        stage="lstm",
        symbol=req.symbol,
        timeframe=req.timeframe,
        start=req.start,
        end=req.end,
        status="queued",
        hyperparams=req.hyperparams.model_dump(),
        progress=[],
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
