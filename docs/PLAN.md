# Market ML Lab — Build Plan & Status

A living build plan for the staged forecasting pipeline. Update the status markers as work
progresses. Companion docs: design outline in [`src/README.md`](../src/README.md), reference
docs in [`documentation.md`](./documentation.md).

**Last updated:** 2026-06-04

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
| **`training_runs` table** (stage, hyperparams JSON, metrics JSON, artifact path, status) | ✅ | `models.py` `TrainingRun` (+ `progress` JSON for live polling) |
| **`feature_cache` table** (symbol, timeframe, ts, feature_set, payload JSON) | ✅ | `models.py` `FeatureCache`; wired in from Stage 3 |
| **Model registry** (save/load `.pt` + config + scaler) | ✅ | `ml/registry.py`; bundles weights + hyperparams + scaler |
| **Background training jobs + progress streaming** (WS or polling) | ✅ | threaded worker writes per-epoch progress to the run row; UI polls `GET /runs/{id}` |
| **Dataset builder** (windowing, time-ordered splits, scaling) | ✅ | `services/datasets.py`; per-segment windowing + train-only scaler (leakage-safe) |
| **PyTorch installed** | ✅ | `torch==2.2.2` (last Intel-Mac wheel) on Python 3.11; **pinned `numpy<2`** (1.26.4) — torch 2.2.2 can't run against NumPy 2.x |
| **Indicator module** (the 10 indicators, params, toggles) | ✅ | `services/features/indicators.py`; framework + 10 functions ported from srcV1 (pure stdlib, registry pattern, `placement` metadata) |
| **MetricsChart / TrainingProgress / HyperParamForm components** | ✅ | `frontend/src/components/`; reusable across stages |

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

## Stage 2 — LSTM Direction Model ✅ DONE

**Goal:** train a small LSTM on OHLCV sequences to predict next-bar direction (up/down).

**Built & verified (end-to-end against the live DB):**
- `services/datasets.py`: per-segment windowing (`seq_len`), time-ordered 70/15/15 split,
  scaler fit on train rows only (leakage-safe).
- `ml/models/lstm.py`: LSTM classifier (single logit → BCEWithLogitsLoss).
- `services/training/trainer.py`: threaded train loop, early stopping, per-epoch metrics
  written to the run row for polling. (Note: JSON `progress` must be reassigned a new list
  each epoch — SQLAlchemy ignores in-place list mutation.)
- `models.py` `TrainingRun` + `ml/registry.py` (`.pt` = weights + hyperparams + scaler).
- `routers/train.py`: `POST /api/v1/train/lstm`, `GET /api/v1/runs`, `GET /api/v1/runs/{id}`.
- Frontend `pages/Stage2Lstm.jsx` (5-part template) + reusable `HyperParamForm` /
  `MetricsChart` (SVG loss + accuracy curves) / `TrainingProgress` (confusion matrix);
  inventory-backed data-source selector + optional date slice; polls the run live.
- Lesson markdown: `content/stage2.{what,why,writeup}.md`.

**Verified:** trained AAPL 1m against MariaDB — runs complete, progress persists per-epoch,
metrics + confusion matrix + saved artifact all correct. (Accuracy ~50%, the honest baseline
for next-bar direction on raw OHLCV — by design; Stage 3 adds indicator features.)

**Default hyperparameters:** seq_len=60, horizon=1, features=OHLCV, target=direction,
hidden=64, layers=2, dropout=0.2, lr=1e-3, batch=64, epochs=30, optimizer=Adam,
split=70/15/15, early-stop patience=5.

---

## Stage 3 — Multi-Task Model ✅ DONE

**Goal:** add technical indicators as features; predict direction + return + volatility from
shared representation.

**Built & verified (end-to-end against the live DB):**
- `services/features/indicators.py`: the 10 indicators (ported from srcV1: framework + the 10
  functions, pure stdlib, `placement` metadata) + `routers/features.py`
  (`GET /indicators/catalog`, `POST /indicators` over **stored** bars, returns bars + series).
- `services/features/feature_pipeline.py`: bars → aligned feature matrix; **feature_cache wired
  in** (config-hash `feature_set` key, delete+bulk-insert, verified cache hit on re-run);
  `estimate_warmup()` for the overlay clamp.
- `services/datasets.py` `build_multitask_dataset`: warm-up trim, leakage-safe wide-matrix
  scaling, three labels (direction; standardized log return; standardized log1p realized vol
  over `vol_window`); `TargetStats` saved in the artifact.
- `ml/models/multitask.py`: shared LSTM trunk + 3 heads; trainer `_*_mt` path (loss =
  w_dir·BCE + w_ret·MSE + w_vol·MSE, scheduler/early-stop on total val loss, per-head progress);
  `POST /api/v1/train/multitask`; `predict_overlay_multitask` (OOS clamp accounts for warm-up;
  arrows + predicted return/vol).
- Frontend `pages/Stage3MultiTask.jsx` (full 10-section template): catalog-driven
  IndicatorPanel (toggle reveals params) + **live chart preview** (PriceChart `overlays` +
  native v5 `panes`), presets pairing params+indicators, per-head MetricsChart plots, verdict
  (direction head), runs table, Stage3FlowChart, stageFiles incl. Tests group.
- Lesson markdown: `content/stage3.{what,why,understand,writeup}.md`.
- Tests: `test_indicators.py` (19), `test_features_router.py`, `test_multitask_dataset.py`
  (standalone like test_datasets), train-router multitask cases; vitest for the selection
  helpers. (Rolling VWAP, not session-anchored — noted in the lesson.)

**The 10 indicators:** SMA(20), EMA(20), Bollinger(20,2σ), VWAP — *overlay*; RSI(14),
MACD(12/26/9), Stochastic(14,3,3), ATR(14), ADX(14), OBV — *own pane*.

**Defaults:** heads {direction, return, volatility}; per-task loss weights = 1.0; vol_window=5.

---

## Stage 4 — FinBERT News Sentiment ✅ DONE

**Goal:** add news-headline sentiment as features.

**Decision made:** news source = **Alpaca News API** (`/v1beta1/news`) — existing keys, same
auth/pagination pattern as the bars client, history to 2015. (Finnhub would have needed a new
API key; yfinance has no historical news.)

**Built & verified (real FinBERT run against the live DB):**
- Optional `[dependency-groups] sentiment`: transformers 4.44 + tokenizers 0.19.1 (Intel-mac
  wheels, torch 2.2.2-compatible); ALL transformers imports lazy — app boots without the group.
- `services/sentiment/`: `news_client.py` (paginated, headline-only, capped, id-dedupe),
  `scorer.py` (lazy FinBERT, batches of 16, 2 threads), `aggregate.py` (PURE: daily net+count,
  **lag-1 bar alignment**, NaN-before/0-after fill, no forward-fill — the leakage rules, with
  the hardest tests in the stage), `prep_service.py` (resumable background job on a
  TrainingRun stage="finbert-prep"; daily aggregates → feature_cache `finbert_daily`),
  `sentiment_features.py` (training-side cache reader).
- `models.py` `NewsArticle` (composite PK symbol+id, scores nullable until scored).
- Endpoints: `POST /sentiment/prepare`, `GET /sentiment/headlines`, `GET /sentiment/coverage`;
  `POST /train/sentiment` = the Stage 3 multitask trainer with stage="sentiment" + two
  hstacked sentiment columns (datasets.py untouched); overlay rebuilds the same columns.
- Frontend `pages/Stage4Sentiment.jsx` (template + a "Prepare the Corpus" section): PrepPanel
  with live FinBERT progress, **HeadlineBrowser** (per-headline pos/neu/neg score bars),
  CoverageTimeline (SVG daily-net sparkline), TrainForm = Stage 3's + the sentiment toggle
  with slice-coverage guard; A/B presets incl. the Stage 3 rematch control.
- Verified: real prep run (300 TSLA headlines scored, resumable after interruption, sane
  scores), sentiment train n_features = 5+indicators+2, overlay loads with no n_features
  mismatch, rematch run comparable in the runs table. Tests: news client (mocked urlopen),
  aggregate (standalone), prep/router (fake scorer — FinBERT never runs in CI), train router.

**Default:** daily sentiment aggregate (net = mean pos − mean neg, log1p count); lag 1 day;
small corpus (max_articles default 300).

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
