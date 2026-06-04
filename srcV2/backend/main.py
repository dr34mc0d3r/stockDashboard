"""Market ML Lab — FastAPI application entry point.

This file does exactly three things: build the app, attach middleware, and
register the routers. Startup database housekeeping lives in db_startup.py.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from config import CORS_ORIGINS
from db_startup import migrate_and_recover
from routers import data, ingest, train

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup housekeeping. If the remote MariaDB is unreachable, warn and start
    # anyway rather than failing startup: a failed startup leaves the --reload
    # supervisor lingering and unresponsive to Ctrl+C. The DB connect is bounded
    # by connect_timeout (see db.py), so this can't hang; endpoints will surface
    # the DB error per-request instead.
    try:
        migrate_and_recover()
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
def health() -> dict[str, str]:
    return {"status": "ok"}
