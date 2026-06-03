"""Market ML Lab — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import models  # noqa: F401  (register ORM models on Base before create_all)
from config import CORS_ORIGINS
from db import Base, engine
from routers import data, ingest, train


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup if they don't exist yet.
    Base.metadata.create_all(bind=engine)
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
