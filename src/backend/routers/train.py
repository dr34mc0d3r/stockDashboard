"""Stage 2 training endpoints: kick off an LSTM run and poll its progress.

`POST /train/lstm` creates a queued `training_runs` row, spawns a background
worker, and returns immediately. The frontend then polls `GET /runs/{id}` to
watch `status` and the per-epoch `progress` list update live.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import get_session
from models import OhlcvBar, TrainingRun
from schemas import PredictionsOut, TrainingRunOut, TrainLstmRequest
from services.predict_service import predict_overlay
from services.training.trainer import start_training

router = APIRouter(prefix="/api/v1", tags=["train"])


@router.post("/train/lstm", response_model=TrainingRunOut)
def train_lstm(req: TrainLstmRequest, session: Session = Depends(get_session)):
    # Fail fast if there's no stored data for this slice.
    bar_count = session.execute(
        select(func.count())
        .select_from(OhlcvBar)
        .where(OhlcvBar.symbol == req.symbol, OhlcvBar.timeframe == req.timeframe)
    ).scalar_one()
    if bar_count == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No stored bars for {req.symbol} {req.timeframe}. Ingest data first.",
        )

    hp = req.hyperparams.model_dump()
    run = TrainingRun(
        stage="lstm",
        symbol=req.symbol,
        timeframe=req.timeframe,
        start=req.start,
        end=req.end,
        status="queued",
        hyperparams=hp,
        progress=[],
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    start_training(run.id, req.symbol, req.timeframe, hp, req.start, req.end)
    return run


@router.get("/runs", response_model=list[TrainingRunOut])
def list_runs(stage: str | None = None, limit: int = 50,
              session: Session = Depends(get_session)):
    stmt = select(TrainingRun)
    if stage:
        stmt = stmt.where(TrainingRun.stage == stage)
    stmt = stmt.order_by(TrainingRun.id.desc()).limit(limit)
    return session.execute(stmt).scalars().all()


@router.get("/runs/{run_id}", response_model=TrainingRunOut)
def get_run(run_id: int, session: Session = Depends(get_session)):
    run = session.get(TrainingRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No training run {run_id}")
    return run


@router.get("/runs/{run_id}/predictions", response_model=PredictionsOut)
def run_predictions(run_id: int, limit: int = Query(default=200, ge=10, le=1000),
                    session: Session = Depends(get_session)):
    """Run the saved model over recent bars for charting its per-candle calls."""
    run = session.get(TrainingRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No training run {run_id}")
    if run.status != "done" or not run.artifact_path:
        raise HTTPException(status_code=400, detail="Run has no saved model yet.")
    try:
        return predict_overlay(session, run, limit=limit)
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Model artifact is missing on disk.")
