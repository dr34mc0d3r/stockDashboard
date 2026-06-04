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
from schemas import PredictionsOut, TrainingRunOut, TrainLstmRequest, TrainMultiTaskRequest
from services.predict_service import predict_overlay, predict_overlay_multitask
from services.training import run_service
from services.training.trainer import start_training, start_training_multitask

router = APIRouter(prefix="/api/v1", tags=["train"])


@router.post("/train/lstm", response_model=TrainingRunOut)
def train_lstm(req: TrainLstmRequest, session: SessionDep) -> TrainingRun:
    # Fail fast if there's no stored data for this slice.
    if run_service.count_bars(session, req.symbol, req.timeframe) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No stored bars for {req.symbol} {req.timeframe}. Ingest data first.",
        )

    run = run_service.create_run(session, req, stage="lstm")
    start_training(run.id, req.symbol, req.timeframe, run.hyperparams, req.start, req.end)
    return run


@router.post("/train/multitask", response_model=TrainingRunOut)
def train_multitask(req: TrainMultiTaskRequest, session: SessionDep) -> TrainingRun:
    """Stage 3: indicators as features, three heads (direction/return/vol)."""
    if run_service.count_bars(session, req.symbol, req.timeframe) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No stored bars for {req.symbol} {req.timeframe}. Ingest data first.",
        )

    run = run_service.create_run(session, req, stage="multitask")
    start_training_multitask(run.id, req.symbol, req.timeframe, run.hyperparams, req.start, req.end)
    return run


@router.post("/train/sentiment", response_model=TrainingRunOut)
def train_sentiment(req: TrainMultiTaskRequest, session: SessionDep) -> TrainingRun:
    """Stage 4: the multitask model with cached FinBERT sentiment features.

    Same trainer as Stage 3 (sentiment is just two more feature columns); a
    separate stage name keeps each page's runs table clean. Fails fast if
    sentiment is enabled but nothing is cached for the symbol.
    """
    if run_service.count_bars(session, req.symbol, req.timeframe) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No stored bars for {req.symbol} {req.timeframe}. Ingest data first.",
        )
    if req.hyperparams.sentiment.enabled:
        from services.sentiment.sentiment_features import load_daily

        if not load_daily(session, req.symbol):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No FinBERT sentiment cached for {req.symbol}. "
                    "Run sentiment prep for this symbol and date range first."
                ),
            )

    run = run_service.create_run(session, req, stage="sentiment")
    start_training_multitask(run.id, req.symbol, req.timeframe, run.hyperparams, req.start, req.end)
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


@router.delete("/runs/{run_id}")
def delete_run(run_id: int, session: SessionDep) -> dict:
    """Delete a finished run (row + saved artifact). Active runs are refused —
    their worker thread is still writing to the row."""
    run = session.get(TrainingRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No training run {run_id}")
    if run.status in ("queued", "running"):
        raise HTTPException(
            status_code=409,
            detail="Run is still in progress — wait for it to finish (or fail) first.",
        )
    run_service.delete_run(session, run)
    return {"deleted": run_id}


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
    overlay = (
        predict_overlay_multitask if run.stage in ("multitask", "sentiment") else predict_overlay
    )
    try:
        return overlay(session, run, limit=limit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=410, detail="Model artifact is missing on disk.") from e
