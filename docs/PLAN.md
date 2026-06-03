# Market ML Lab — Build Plan & Status

A living build plan for the staged forecasting pipeline. Update the status markers as work
progresses. Companion docs: design outline in [`src/README.md`](../src/README.md), reference
docs in [`documentation.md`](./documentation.md).

**Last updated:** 2026-06-03

## Status Legend
- ✅ **done** — built and verified
- 🔨 **in progress**
- 🔲 **planned** — not started
- ⚠ **blocked / needs decision**

---

## Guiding Constraints (apply to every stage)
- **CPU-only dev machine** (Intel i5-5250U, 2 cores, no GPU/MPS). Keep models small; train
  on a *selected subset* of stored data; precompute + cache anything expensive.
- **Stack:** FastAPI + SQLAlchemy (PyMySQL) + PyTorch (CPU) · React 19 + Vite + Tailwind v4
  + lightweight-charts v5.
- **DB:** MariaDB `stock_app` @ 192.168.142.174 (creds in `src/.env`).
- **Every stage page** uses the 5-part template: What · Why · Parameter Config · Run→Results
  · Full Writeup. Lesson text lives as markdown in `src/frontend/src/content/`.

---

## Cross-Cutting Infrastructure

| Item | Status | Notes |
|------|--------|-------|
| FastAPI app + CORS + health | ✅ | `src/backend/main.py` |
| Config from `src/.env` | ✅ | Alpaca keys + DB URL (escaped) |
| MariaDB connection + auto-create tables | ✅ | `db.py`; `Base.metadata.create_all` on startup |
| `ohlcv_bars`, `ingestion_runs` tables | ✅ | composite PK, DECIMAL(18,6) |
| Frontend shell + ordered stage stepper | ✅ | `App.jsx`, `components/Stepper.jsx` |
| Markdown lesson panel | ✅ | `components/LessonPanel.jsx` (`?raw` import) |
| Price chart (candles + volume, legend, pan/zoom) | ✅ | `charts/PriceChart.jsx` |
| **`training_runs` table** (stage, hyperparams JSON, metrics JSON, artifact path, status) | 🔲 | needed from Stage 2 on |
| **`feature_cache` table** (symbol, timeframe, ts, feature_set, payload JSON) | 🔲 | needed from Stage 3 on |
| **Model registry** (save/load `.pt` + config + scaler) | 🔲 | `ml/registry.py` |
| **Background training jobs + progress streaming** (WS or polling) | 🔲 | so UI stays responsive during training |
| **Dataset builder** (windowing, time-ordered splits, scaling) | 🔲 | `services/datasets.py`; guard against leakage |
| **PyTorch installable** | ✅ | project pinned to **Python 3.11** (`.python-version`, `requires-python>=3.11,<3.13`); `torch==2.2.2` resolves with an Intel-Mac wheel (last x86_64 build). Not yet added to deps — added at Stage 2 start. |
| **Indicator module** (the 10 indicators, params, toggles) | 🔲 | `services/features/indicators.py`; reuse srcV1 logic |
| **MetricsChart / TrainingProgress / HyperParamForm components** | 🔲 | reusable across stages |

---

## Stage 1 — Data Acquisition ✅ DONE

**Goal:** download historical OHLCV from Alpaca into MariaDB; show a stored-data inventory;
make stored data reusable by later stages.

**Built & verified:**
- Paginated Alpaca REST client (`services/alpaca_client.py`) — follows `next_page_token`.
- Ingest service with idempotent UPSERT (`services/ingest_service.py`).
- Endpoints: `POST /api/v1/ingest`, `GET /api/v1/inventory`, `GET /api/v1/bars`,
  `DELETE /api/v1/bars`.
- Stage 1 page (`pages/Stage1Data.jsx`): download form (symbol/start/end/timeframe, default
  `1m`), inventory table with **Chart** + **Delete** per row, candlestick+volume chart.
- Lesson markdown: `content/stage1.{what,why,writeup}.md`.

**Possible follow-ups (optional):** delete a specific date range; gap detection/reporting;
progress indicator for very large 1-min pulls; resample endpoint (1m → 5m/1h) for reuse.

---

## Stage 2 — LSTM Direction Model 🔲 PLANNED

**Goal:** train a small LSTM on OHLCV sequences to predict next-bar direction (up/down).

**To build:**
- Confirm/installation of PyTorch (see ⚠ above).
- `services/datasets.py`: windowing (`seq_len`), time-ordered train/val/test split, feature
  scaling fit on train only (no leakage).
- `ml/models/lstm.py`: LSTM classifier.
- `services/training/`: train loop with early stopping; emit per-epoch loss/metrics.
- `training_runs` table + model registry (`ml/registry.py`).
- Router `train.py`: `POST /api/v1/train/lstm`, `GET /api/v1/runs`, progress stream.
- Frontend `pages/Stage2Lstm.jsx`: HyperParamForm + MetricsChart (loss curve, accuracy,
  confusion matrix) + data-source selector (from inventory).
- Lesson markdown.

**Default hyperparameters:** seq_len=60, horizon=1, features=OHLCV, target=direction,
hidden=64, layers=2, dropout=0.2, lr=1e-3, batch=64, epochs=30, optimizer=Adam,
split=70/15/15, early-stop patience=5.

---

## Stage 3 — Multi-Task Model 🔲 PLANNED

**Goal:** add technical indicators as features; predict direction + return + volatility from
shared representation.

**To build:**
- `services/features/indicators.py`: the 10 indicators with editable params; `feature_cache`.
- Indicators endpoint (`indicators=[{name, params}, ...]`) feeding chart overlays/panes AND
  the ML feature pipeline.
- `ml/models/multitask.py`: shared trunk + 3 heads.
- Frontend: indicator toggle panel (each toggle reveals its param inputs); chart overlays
  (SMA/EMA/Bollinger/VWAP on price pane) and sub-panes (RSI/MACD/Stochastic/ATR/ADX/OBV).
- Lesson markdown.

**The 10 indicators:** SMA(20), EMA(20), Bollinger(20,2σ), VWAP — *overlay*; RSI(14),
MACD(12/26/9), Stochastic(14,3,3), ATR(14), ADX(14), OBV — *own pane*.

**Defaults:** heads {direction, return, volatility}; per-task loss weights = 1.0.

---

## Stage 4 — FinBERT News Sentiment 🔲 PLANNED ⚠ decision pending

**Goal:** add news-headline sentiment as features.

**To build / decide:**
- ⚠ **News source:** Finnhub / Alpaca news / yfinance (srcV1 has finnhub + yfinance dirs).
- FinBERT (`ProsusAI/finbert`) inference, **run once** over a small corpus, aggregate per
  bar/day, cache to `feature_cache`.
- Add sentiment features to the dataset builder.
- Lesson markdown (transformer-based sentiment, why cache).

**Default:** daily sentiment aggregate; small corpus.

---

## Stage 5 — GDELT Historical News 🔲 PLANNED

**Goal:** add global news tone/volume features.

**To build:**
- GDELT 2.0 GKG tone/volume by keyword/entity; small date range; daily aggregation; cache.
- Join aggregates to bars in the dataset builder.
- Lesson markdown.

---

## Stage 6 — Transformer Core 🔲 PLANNED

**Goal:** swap the LSTM for a small time-series Transformer encoder; keep multi-task heads.

**To build:**
- `ml/models/transformer.py`: positional encoding + encoder; reuse training/dataset infra.
- Frontend hyperparam form for transformer params.
- Lesson markdown (attention vs recurrence).

**Defaults:** d_model=64, n_heads=4, layers=2, ff_dim=128, dropout=0.1.

---

## Stage 7 — Regime Detection 🔲 PLANNED

**Goal:** detect market regimes (trend/range, high/low vol) and condition the predictor.

**To build:**
- `ml/models/regime.py`: k-means / GMM / HMM (all CPU-trivial). n_regimes=3.
- Regime label as context fed to the prediction model.
- Lesson markdown.

---

## Stage 8 — Unified Engine 🔲 PLANNED

**Goal:** combine all features + transformer + regime gating into one model producing
{direction, volatility, confidence, expected return}.

**To build:**
- `ml/models/engine.py`: unify the parts.
- `router predict.py`: `POST /api/v1/predict/engine`; single inference + summary view.
- Frontend dashboard view of the four outputs.
- Lesson markdown.

---

## Known Risks / Open Items
- ✅ **PyTorch / Python version** — RESOLVED 2026-06-03. Root cause was Intel macOS, not
  Python: PyTorch dropped x86_64 macOS wheels after `2.2.2` (cp38–cp312). Project pinned to
  Python 3.11 so `torch==2.2.2` installs from a prebuilt wheel. Capped at torch 2.2.2 on this
  machine — fine for the small CPU models.
- ⚠ **Stage 4 news source** — choose Finnhub / Alpaca / yfinance.
- 1-minute data volume grows fast; rely on slice-selection + caching to stay CPU-sized.
- Remote DB host is modest hardware; keep queries indexed by the composite PK.

## Resume Checklist (when picking this back up)
1. Start backend (:8000) and frontend (:5173); confirm Stage 1 still works.
2. Build the cross-cutting infra needed by the next stage (`training_runs`, dataset builder,
   registry, training-job/progress, reusable frontend components) — these are shared.
3. Resolve the ⚠ for that stage (e.g. PyTorch install for Stage 2).
4. Implement model + router + page + lesson markdown.
5. Verify a real end-to-end run; update this file's status markers.
