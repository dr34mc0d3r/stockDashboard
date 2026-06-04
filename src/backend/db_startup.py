"""Idempotent database housekeeping run once at app startup.

Kept out of main.py so the FastAPI entry point stays about *serving* and this
module stays about the *database*. Called from the lifespan handler; safe to
run on every boot.
"""

import logging

from sqlalchemy import text, update

import models  # noqa: F401  (register ORM models on Base before create_all)
from db import Base, SessionLocal, engine
from models import TrainingRun

logger = logging.getLogger("uvicorn.error")


def migrate_and_recover() -> None:
    """Bring the schema up to date and clean up after any previous crash.

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
