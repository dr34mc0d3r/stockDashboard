"""Stage 2 training endpoints: kick off an LSTM run and poll its progress.

`POST /train/lstm` creates a queued `training_runs` row, spawns a background
worker, and returns immediately. The frontend then polls `GET /runs/{id}` to
watch `status` and the per-epoch `progress` list update live.

Thin HTTP layer: run bookkeeping lives in services/training/run_service.py and
the actual training in services/training/trainer.py.
"""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from db import SessionDep
from models import TrainingRun
from schemas import PredictionsOut, TrainingRunOut, TrainLstmRequest
from services.predict_service import predict_overlay
from services.training import run_service
from services.training.trainer import start_training

router = APIRouter(prefix="/api/v1", tags=["train"])


@router.post("/train/lstm", response_model=TrainingRunOut)
def train_lstm(req: TrainLstmRequest, session: SessionDep) -> TrainingRun:
    # Fail fast if there's no stored data for this slice.
    if run_service.count_bars(session, req.symbol, req.timeframe) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No stored bars for {req.symbol} {req.timeframe}. Ingest data first.",
        )

    run = run_service.create_run(session, req)
    start_training(run.id, req.symbol, req.timeframe, run.hyperparams, req.start, req.end)
    return run


@router.get("/runs", response_model=list[TrainingRunOut])
def list_runs(session: SessionDep, stage: str | None = None, limit: int = 50) -> list[TrainingRun]:
    stmt = select(TrainingRun)
    if stage:
        stmt = stmt.where(TrainingRun.stage == stage)
    stmt = stmt.order_by(TrainingRun.id.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


@router.get("/runs/{run_id}", response_model=TrainingRunOut)
def get_run(run_id: int, session: SessionDep) -> TrainingRun:
    run = session.get(TrainingRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No training run {run_id}")
    return run


@router.get("/runs/{run_id}/predictions", response_model=PredictionsOut)
def run_predictions(
    run_id: int,
    session: SessionDep,
    limit: int = Query(default=200, ge=10, le=1000),
) -> PredictionsOut:
    """Run the saved model over recent bars for charting its per-candle calls."""
    run = session.get(TrainingRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No training run {run_id}")
    if run.status != "done" or not run.artifact_path:
        raise HTTPException(status_code=400, detail="Run has no saved model yet.")
    try:
        return predict_overlay(session, run, limit=limit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=410, detail="Model artifact is missing on disk.") from e
