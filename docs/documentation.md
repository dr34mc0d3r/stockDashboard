# Market ML Lab — Project Documentation

A guided, multi-page web app that **builds up a PyTorch market-forecasting engine one
stage at a time**. It is an educational tool, scoped to run on modest hardware (CPU, no
GPU): small models, daily/intraday bars, cached features. Each page is a *lesson* with a
fixed five-part layout, all backed by a Python FastAPI service and a MariaDB database.

> The previous single-page charting dashboard (V1) is preserved under `srcV1/` for
> reference. The full design outline lives in [`src/README.md`](../src/README.md).

## The Stages

| # | Stage | Adds | Status |
|---|-------|------|--------|
| 1 | **Data Acquisition** | Alpaca OHLCV → MariaDB, with a stored-data inventory | ✅ built |
| 2 | LSTM Direction | OHLCV → next-bar up/down | planned |
| 3 | Multi-Task Model | + technical indicators; direction + return + volatility | planned |
| 4 | FinBERT Sentiment | + news-headline sentiment features | planned |
| 5 | GDELT News | + global news tone/volume features | planned |
| 6 | Transformer Core | swap LSTM → time-series Transformer | planned |
| 7 | Regime Detection | market-regime layer that conditions the model | planned |
| 8 | Unified Engine | one model → direction, volatility, confidence, expected return | planned |

Each stage page follows the same template: **What We're Doing · Why We're Doing It ·
Parameter Config · Run → Results (charts/loss) · Full Writeup**.

## Directory Structure

```text
/
├── src/
│   ├── .env                  # secrets: Alpaca keys + MariaDB connection (gitignored)
│   ├── README.md             # the living design outline
│   ├── backend/              # FastAPI + (later) PyTorch
│   │   ├── main.py           # app, CORS, auto-creates tables on startup
│   │   ├── config.py         # loads src/.env; builds the MariaDB URL
│   │   ├── db.py             # SQLAlchemy engine/session, declarative Base
│   │   ├── models.py         # ORM: OhlcvBar, IngestionRun
│   │   ├── schemas.py        # Pydantic request/response models
│   │   ├── routers/          # ingest.py, data.py
│   │   └── services/         # alpaca_client.py (paginated), ingest_service.py (UPSERT)
│   └── frontend/             # React 19 + Vite + Tailwind v4 + lightweight-charts v5
│       └── src/
│           ├── api/client.js         # fetch wrappers
│           ├── App.jsx               # layout + sidebar stepper
│           ├── components/           # Stepper, LessonPanel (markdown)
│           ├── charts/PriceChart.jsx # candles + volume pane, legend, pan/zoom
│           ├── pages/Stage1Data.jsx  # the Stage 1 page
│           └── content/*.md          # lesson text (imported via ?raw)
├── mysql/                    # MariaDB Docker setup for the remote DB host
└── docs/                     # this documentation
```

## How To

### Prerequisites

- Python 3.14 with [`uv`](https://docs.astral.sh/uv/) for dependency management.
- Node.js + npm for the frontend.
- A reachable MariaDB instance with a `stock_app` database and a granted `stock_app` user
  (see `mysql/` and `src/.env`).

### Running the Application

Run two servers in separate terminals.

**Backend** (FastAPI on :8000):
```bash
cd src/backend
../../.venv/bin/python -m uvicorn main:app --reload --port 8000
# or: uv run uvicorn main:app --reload --port 8000
```
Tables (`ohlcv_bars`, `ingestion_runs`) are created automatically on startup.

**Frontend** (Vite on :5173, proxies `/api` → :8000):
```bash
cd src/frontend
npm install   # first time only
npm run dev
```
Open http://localhost:5173.

### Configuration (`src/.env`, gitignored)

```
ALPACA_API_KEY=...        ALPACA_SECRET_KEY=...
DB_HOST=192.168.142.174   DB_PORT=3306 (optional)
DB_USER=stock_app         DB_PASSWORD=...        DB_NAME=stock_app
```

## Database Schema

**`ohlcv_bars`** — one row per bar. Primary key `(symbol, timeframe, ts)` clusters rows
for fast per-symbol range scans and makes inserts idempotent (re-downloading a range
updates rather than duplicates).

| Column | Type | Notes |
|--------|------|-------|
| symbol | VARCHAR(16) | uppercased |
| timeframe | VARCHAR(8) | `1m`, `5m`, `1h`, `1d` |
| ts | DATETIME | bar timestamp, UTC |
| open / high / low / close | DECIMAL(18,6) | exact, no float drift |
| volume | BIGINT | |

**`ingestion_runs`** — audit record per download: `id, symbol, timeframe, start, end,
bars_fetched, bars_written, status, detail, created_at`.

## API Routes

All routes are prefixed `/api/v1`.

### `POST /api/v1/ingest`
Download historical bars from Alpaca (following pagination) and UPSERT them into MariaDB.

*Body (JSON):*
- `symbol` (string) — ticker, e.g. `AAPL` (uppercased server-side)
- `start` (string) — `YYYY-MM-DD` or RFC3339
- `end` (string) — `YYYY-MM-DD` or RFC3339
- `timeframe` (string) — one of `1m`, `5m`, `1h`, `1d` (default `1m`)

*Returns:* `{ symbol, timeframe, start, end, bars_fetched, bars_written, first_ts, last_ts, status }`

### `GET /api/v1/inventory`
List what's already stored, grouped by `(symbol, timeframe)`.

*Returns:* array of `{ symbol, timeframe, bar_count, earliest, latest }`

### `GET /api/v1/bars`
Return stored bars for a symbol/timeframe, oldest first. Used by the chart and (later) by
Lab stages selecting a data slice.

*Query params:* `symbol`, `timeframe` (default `1m`), `start` (optional), `end` (optional),
`limit` (default 5000, max 50000).

*Returns:* array of `{ ts, open, high, low, close, volume }`

### `DELETE /api/v1/bars`
Delete all stored bars for a `(symbol, timeframe)`.

*Query params:* `symbol`, `timeframe`.

*Returns:* `{ symbol, timeframe, deleted }`

### `GET /health`
Liveness check → `{ "status": "ok" }`.

## Notes & Conventions

- **Pagination:** the Alpaca client loops on `next_page_token`, so large pulls (e.g. months
  of 1-minute bars) arrive complete instead of being truncated at the first ~10k bars.
- **Idempotency:** ingest uses `INSERT … ON DUPLICATE KEY UPDATE`; re-downloading an
  overlapping range never duplicates rows.
- **Charting:** built on lightweight-charts (TradingView's library). Price-scale indicators
  will overlay the candle chart; other indicators get their own stacked pane. Every chart
  has pan/zoom and a crosshair legend.
- **Lesson content** is authored as markdown under `src/frontend/src/content/` and rendered
  in the page, so the teaching material is version-controlled.
- **Compute note:** the dev machine is CPU-only (Intel, no GPU/MPS). ML stages keep models
  small and select a subset of stored data; heavy NLP (FinBERT/GDELT) is precomputed once
  and cached.
