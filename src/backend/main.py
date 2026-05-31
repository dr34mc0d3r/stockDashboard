from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .routers import alpaca_stream, indicators, ohlcv

app = FastAPI(title="Stock OHLCV API", version="0.1.0")

# Allow the React frontend (served from a different origin in dev) to call us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ohlcv.router)
app.include_router(indicators.router)
app.include_router(alpaca_stream.router)


@app.get("/health", tags=["health"])
def health():
    """Liveness check."""
    return {"status": "ok"}
