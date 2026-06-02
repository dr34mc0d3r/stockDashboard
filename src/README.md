# Market ML Lab — V2

*(working title — see "Naming")*

A **personal, hands-on course** that teaches deep learning on market data by building a
forecasting engine one stage at a time. It is **scoped to run on this machine**
(Intel i5-5250U, 2 cores, no GPU) — small models, daily bars, cached features — so the
focus is *understanding each technique*, not production performance.

Each stage is a **page = a lesson**, all backed by a Python **FastAPI** service.

> V1 (the old charting dashboard) lives in `../srcV1/` — we'll lift its indicator and
> Alpaca code.

---

## The Page Template (every stage page has this shape)

1. **What We're Doing** — plain-language description of this stage.
2. **Why We're Doing It** — the motivation; what it adds over the previous stage.
3. **Parameter Config** — input form, pre-filled with sensible CPU-friendly defaults.
4. **Run → Results** — kick off the job; show live loss curve + the stage's charts
   (accuracy, confusion matrix, predictions-vs-actual, etc.).
5. **Full Writeup** — the deep-dive lesson: the math/intuition, what the charts mean,
   and what to try changing — written so you can actually *learn* the step.

Lesson text (parts 1, 2, 5) is authored as **markdown files in the repo** and rendered
in the page, so the teaching content is version-controlled and easy to edit.

---

## The Stages (each scoped to fit this CPU)

| # | Stage | What it adds | CPU-fit scope | Status |
|---|-------|--------------|---------------|--------|
| 1 | **Data Acquisition** | Alpaca OHLCV → MariaDB (+ stored-data inventory) | 1-min bars, few symbols | ✅ built |
| 2 | **LSTM Direction** | OHLCV → next-bar up/down | hidden≤64, seq≤60, 1 symbol | 🔲 |
| 3 | **Multi-Task** | + indicators; predict direction+return+volatility | reuse srcV1 indicators | 🔲 |
| 4 | **FinBERT Sentiment** | + news-headline sentiment | run **once** on a few hundred headlines, cache | 🔲 |
| 5 | **GDELT News** | + global news tone/volume | small date range, pre-aggregated tone, cache | 🔲 |
| 6 | **Transformer Core** | swap LSTM → time-series Transformer | tiny: d_model≤64, ≤2 layers | 🔲 |
| 7 | **Regime Detection** | market-regime layer | k-means / GMM / HMM — CPU-trivial | 🔲 |
| 8 | **Unified Engine** | one model → direction, volatility, confidence, expected return | combine small parts | 🔲 |

Later stages are sketched, not locked — we refine each as we reach it. The heavy NLP
stages (4, 5) are **precompute-once-and-cache**, so they cost CPU time only on first run.

---

## Stage 1 — Data Acquisition (detailed spec)

This page does two jobs: **download new data** and **show what's already stored** so you
never re-download. Stored data becomes the reusable source for every later Lab stage.

**A. Download form:** `symbol`, `start`, `end`, `timeframe` (`1m`/`5m`/`1h`/`1d`, **default `1m`**).
Submit → `POST /api/v1/ingest`.

**B. Stored-data inventory** (always visible on the page): a table of what's in the DB —
per `(symbol, timeframe)`: earliest bar, latest bar, bar count, last updated.
Fed by `GET /api/v1/inventory`.

**Ingest backend flow:**
1. Validate (symbol uppercased, ISO dates, `start < end`).
2. Fetch from Alpaca REST **with pagination** (`next_page_token` loop — Alpaca caps
   ~10k bars/response; V1 examples don't handle this and silently truncate). 1-min data
   spans many pages, so this matters.
3. Normalize → `(symbol, timeframe, ts, o, h, l, c, v)`.
4. Bulk **UPSERT** into MariaDB (`INSERT ... ON DUPLICATE KEY UPDATE`) → idempotent.
5. Log run, return summary (fetched / inserted / updated / range / gaps).

*Lesson angle:* what OHLCV is, why we index by time, train/test leakage in time series.

**Reuse pattern:** every later stage starts with a **data-source selector** populated from
the same inventory — pick a stored `(symbol, timeframe, date-range)` and (for 1-min)
optionally a subset/resample, so training stays CPU-sized without re-fetching.

---

## Indicators & Charting

**Indicators are computed on the Python backend** (`services/features/indicators.py`, pure
functions over the bars) and added into the JSON **only when requested** — the data endpoint
takes an `indicators=[...]` list. The same functions feed the ML feature pipeline (cached in
`feature_cache`), so chart and model share one source of truth.

**Each indicator is individually selectable / toggleable, with its own parameter inputs.**
The UI shows a control panel where every indicator can be turned on/off; toggling one on
reveals form inputs for *that indicator's parameters*, pre-filled with the defaults below
and editable. On a chart page the toggle/params update the overlay or pane live; on a Lab
stage the same controls choose which indicators (and at what params) become model features.
The selected set + params is what gets sent as `indicators=[{name, params}, ...]`.

**The 10 indicators** (commonly used + good ML features), grouped by chart placement:

Each indicator's editable params (and their defaults) are shown below — these become the
form inputs revealed when the indicator is toggled on.

*Price-scale → overlaid on the candlestick chart (same pane):*
| Indicator | Editable params (defaults) | Notes |
|-----------|----------------------------|-------|
| SMA | `period`=20, `source`=close | simple moving average |
| EMA | `period`=20, `source`=close | exponential moving average |
| Bollinger Bands | `period`=20, `std_dev`=2.0, `source`=close | upper / middle / lower |
| VWAP | `anchor`=session | volume-weighted average price |

*Own-scale → separate stacked pane (different units):*
| Indicator | Editable params (defaults) | Pane scale |
|-----------|----------------------------|-----------|
| RSI | `period`=14 | 0–100 oscillator |
| MACD | `fast`=12, `slow`=26, `signal`=9 | line + signal + histogram |
| Stochastic | `k_period`=14, `k_smooth`=3, `d_period`=3 | %K / %D, 0–100 |
| ATR | `period`=14 | volatility (price units) |
| ADX | `period`=14 | 0–100 trend strength |
| OBV | *(none)* | cumulative volume |

**Charting rules (all charts):**
- Library: **lightweight-charts** (TradingView's own) → TradingView-like look & feel.
- **Pan + zoom enabled** on every chart (built in).
- **Legend** on every chart (series names + live crosshair values).
- Price-scale indicators **overlay the price chart** — never a separate chart.
- Indicators that don't fit the price scale go in a **stacked sub-pane** that shares the
  x-axis/time scale with price. We add new panes only as needed (e.g. RSI, MACD).
- Volume can render as a histogram in its own thin pane.

---

## CPU-Fit Principles (how we keep it runnable here)

- **Collect 1-min granular, train on a subset.** We store rich 1-min data, but each Lab
  stage selects a slice (date range / sample / optional resample) so training stays small.
- **Small nets**: LSTM hidden ≤64 / Transformer d_model ≤64 → train in seconds–minutes.
- **Cache everything expensive**: indicators, FinBERT scores, GDELT tone live in a
  `feature_cache` table; computed once, reused forever.
- **Background jobs + progress stream** so the UI stays responsive while a run trains.
- Stage 4/5 process a deliberately **small** corpus — enough to learn the technique.

---

## Architecture

```
src/
├── backend/                       # FastAPI + PyTorch (CPU)
│   ├── main.py · config.py · db.py · models.py · schemas.py
│   ├── routers/   ingest · data (inventory + slice + indicators=[...]) · train · predict
│   ├── services/  alpaca_client · ingest_service · datasets · features/(indicators.py …) · training/
│   ├── ml/        models/(lstm, multitask, transformer, regime, engine) · registry
│   ├── content/   stage1.md … stage8.md   # the lesson text (parts 1/2/5)
│   └── artifacts/ # saved .pt models (gitignored)
└── frontend/                      # React + Vite + React Router + Tailwind v4
    └── src/
        ├── api/client.js
        ├── charts/      PriceChart (candles + overlays) · IndicatorPane · legend/panZoom helpers (lightweight-charts)
        ├── components/  Stepper · LessonPanel(md) · HyperParamForm · MetricsChart · TrainingProgress
        ├── pages/       Stage1Data … Stage8Engine   (each uses the 5-part template)
        └── App.jsx      # ordered routes; a stage unlocks when its prereq is satisfied
```

**Shared infra (built early, reused by every stage):** `training_runs` registry, model
registry (versioned `.pt` + config + scaler), `feature_cache`, live progress streaming.

---

## Database Schema (MariaDB @ 192.168.142.174, db `stock_app`)

**`ohlcv_bars`** — `PRIMARY KEY (symbol, timeframe, ts)`
`symbol VARCHAR(16) · timeframe VARCHAR(8) · ts DATETIME(UTC) · open/high/low/close DECIMAL(18,6) · volume BIGINT`
→ composite PK = fast per-symbol range scans + free dedupe for idempotent UPSERT.

**`ingestion_runs`** — `id, symbol, timeframe, start, end, bars_written, status, created_at`
**`training_runs`** — `id, stage, symbol, hyperparams JSON, status, metrics JSON, artifact_path, created_at`
**`feature_cache`** — `symbol, timeframe, ts, feature_set, payload JSON`

---

## Default Hyperparameters (pre-filled in each form)

- **Stage 2 LSTM:** seq_len=60, horizon=1, features=OHLCV, target=direction, hidden=64, layers=2, dropout=0.2, lr=1e-3, batch=64, epochs=30, Adam, split 70/15/15, early-stop=5.
- **Stage 3 Multi-Task:** + indicator features (from the 10 above); heads {direction, return, volatility}; loss weights=1.0.
- **Stage 4 FinBERT:** ProsusAI/finbert; daily sentiment aggregate; precompute+cache.
- **Stage 5 GDELT:** GKG tone/volume by keyword; daily; small range; cache.
- **Stage 6 Transformer:** d_model=64, heads=4, layers=2, ff=128, dropout=0.1.
- **Stage 7 Regime:** k-means, n_regimes=3 (alt: GMM/HMM).
- **Stage 8 Engine:** all features + transformer + regime gating → 4 outputs.

---

## Naming
"Learning Path" → candidates: **Market ML Lab**, **Forecasting Lab**, **Prediction
Workbench**, **DL Trading Tutor**, **Quant ML Studio**. Pick one for titles/nav.

---

## Decisions
- ✅ Name: **Market ML Lab** · timeframe default **1m** · prices **DECIMAL(18,6)**
- ✅ Page 1 shows stored-data inventory; later stages reuse stored data via a selector.
- 🔲 **News source for Stage 4** (Finnhub / Alpaca / yfinance) — decide at Stage 4.

---

## Running locally

Two servers. Backend (FastAPI on :8000):
```
cd src/backend && ../../.venv/bin/python -m uvicorn main:app --reload --port 8000
```
Frontend (Vite on :5173, proxies `/api` → :8000):
```
cd src/frontend && npm run dev
```
Then open http://localhost:5173. The DB `stock_app` must have the `stock_app` user grant
(done); tables auto-create on backend startup.

---

## Config / Secrets (`src/.env`, gitignored — confirmed working)
```
ALPACA_API_KEY · ALPACA_SECRET_KEY
DB_HOST=192.168.142.174 · DB_USER=stock_app · DB_PASSWORD=… · DB_NAME=stock_app   (DB_PORT defaults 3306)
```
```
