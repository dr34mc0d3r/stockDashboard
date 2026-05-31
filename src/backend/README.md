# Backend (FastAPI)

REST service for the stock OHLCV data. Consumed by the React app in `src/frontend`.

## Run (dev)

From the `src/` directory:

```bash
uv run uvicorn backend.main:app --reload
```

- API root: http://localhost:8000
- Interactive docs: http://localhost:8000/docs

## Endpoints

| Method | Path                      | Description                              |
|--------|---------------------------|------------------------------------------|
| GET    | `/health`                 | Liveness check.                          |
| GET    | `/api/ohlcv`              | Historical OHLCV bars for a symbol.      |
| GET    | `/api/indicators/catalog` | List available indicators (for the UI).  |
| GET    | `/api/indicators`         | Computed indicators over the OHLCV bars. |

### `GET /api/ohlcv`

Query params: `symbol`, `start` (YYYY-MM-DD), `end` (YYYY-MM-DD), `timeframe` (`1m`, `5m`, `1h`, `1d`; default `1d`).

```bash
curl "http://localhost:8000/api/ohlcv?symbol=AAPL&start=2026-05-15&end=2026-05-20&timeframe=1h"
```

### `GET /api/indicators`

Same params as `/api/ohlcv`, plus `period` (lookback, default 14) and
`include` (comma-separated indicator keys, or `all`; default `all`). The
response is keyed by indicator key, so only the requested ones are present.

```bash
# all indicators
curl "http://localhost:8000/api/indicators?symbol=AAPL&start=2026-05-15&end=2026-05-20&timeframe=1h&period=14"
# just two
curl "http://localhost:8000/api/indicators?symbol=AAPL&start=2026-05-15&end=2026-05-20&include=vwap_zscore,acceleration"
```

### Adding a new indicator

Write a function `(bars, period, timeframe) -> Computation` in
`services/indicators.py` and decorate it with `@register("key", "Label", "…")`.
It then appears in the catalog, is selectable via `include`, and renders in the
frontend automatically — no endpoint, model, or frontend change needed.

## Layout

```
backend/
  main.py                  # app + CORS + router wiring
  config.py                # env loading (src/.env) and CORS origins
  models.py                # Pydantic response models
  routers/ohlcv.py         # OHLCV endpoint
  routers/indicators.py    # indicators + catalog endpoints
  services/alpaca_client.py# Alpaca data fetching
  services/indicators.py   # indicator registry + calculations
  tests/test_indicators.py # indicator unit tests (uv run pytest)
```
