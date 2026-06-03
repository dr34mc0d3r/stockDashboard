"""Market ML Lab — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, update
from sqlalchemy.exc import SQLAlchemyError

import models  # noqa: F401  (register ORM models on Base before create_all)
from config import CORS_ORIGINS
from db import Base, SessionLocal, engine
from models import TrainingRun
from routers import data, ingest, train

logger = logging.getLogger("uvicorn.error")


def _migrate_and_recover() -> None:
    """Idempotent startup housekeeping against the live DB.

    1. create_all makes any *missing* tables — but it won't add new columns to a
       table that already exists, so we add training_runs.start/end explicitly
       (MariaDB's ADD COLUMN IF NOT EXISTS makes this a no-op once applied).
    2. Any run still 'running'/'queued' at startup is orphaned — its training
       thread died with the previous process — so we mark those rows 'error'.
    """
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for col in ("start", "end"):
            conn.execute(
                text(f"ALTER TABLE training_runs ADD COLUMN IF NOT EXISTS `{col}` VARCHAR(40)")
            )
    with SessionLocal() as session:
        result = session.execute(
            update(TrainingRun)
            .where(TrainingRun.status.in_(["running", "queued"]))
            .values(status="error", detail="Interrupted by a server restart.")
        )
        session.commit()
        if result.rowcount:
            logger.warning("Marked %d orphaned training run(s) as error.", result.rowcount)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup housekeeping. If the remote MariaDB is unreachable, warn and start
    # anyway rather than failing startup: a failed startup leaves the --reload
    # supervisor lingering and unresponsive to Ctrl+C. The DB connect is bounded
    # by connect_timeout (see db.py), so this can't hang; endpoints will surface
    # the DB error per-request instead.
    try:
        _migrate_and_recover()
    except SQLAlchemyError as exc:
        logger.warning(
            "Database unreachable at startup; serving without table check. (%s)",
            exc.__class__.__name__,
        )
    yield


app = FastAPI(title="Market ML Lab API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(data.router)
app.include_router(train.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
