// The source files behind Stage 2, with what each one does.
// Rendered by FilesPanel in the page's "Files Behind This Stage" section —
// keep this in sync whenever files move or split.

export const STAGE_FILES = [
  {
    label: 'Backend — model & training',
    files: [
      {
        path: 'src/backend/ml/models/lstm.py',
        desc: 'Defines LSTMClassifier — an nn.LSTM whose final-timestep hidden state passes through a dropout + linear head to a single logit (probability of "up") — plus build_model(), which constructs it from a hyperparameter dict.',
      },
      {
        path: 'src/backend/services/datasets.py',
        desc: 'Turns raw OHLCV into supervised windows. Derives stationary return features (ln(O/H/L/C / prev_close) + log1p(volume)) so price-level scale never crushes the signal, labels each window from the real close price, splits 70/15/15 by time, and fits the scaler on training rows only (leakage-safe).',
      },
      {
        path: 'src/backend/services/training/trainer.py',
        desc: "The background training loop, run in a daemon thread so the API stays responsive. Split into focused functions: _build_loaders (DataLoaders), _train_epoch (one optimizer pass), _run_epochs (epoch loop + ReduceLROnPlateau + early stopping, persisting per-epoch metrics through a callback), _score_and_save (test scoring + artifact), and a thin _train wrapper that owns the run row's status.",
      },
      {
        path: 'src/backend/services/training/run_service.py',
        desc: 'TrainingRun bookkeeping for the train router: count_bars validates that stored data exists for the requested slice, create_run inserts the queued run row the worker will update.',
      },
      {
        path: 'src/backend/ml/registry.py',
        desc: 'Saves/loads a trained model as one self-contained .pt bundle = weights + hyperparams + scaler stats + metrics, under src/backend/artifacts/ (gitignored). Lets a run be reloaded later with identical preprocessing.',
      },
      {
        path: 'src/backend/services/predict_service.py',
        desc: "Overlay inference: loads a saved run and runs it (return features + the saved scaler, no refit) over the most-recent bars within the run's stored slice, clamped to the held-out test region so the overlay is strictly out-of-sample. Returns each candle's predicted direction + actual outcome.",
      },
      {
        path: 'src/backend/routers/train.py',
        desc: 'Defines POST /api/v1/train/lstm (delegates run creation to run_service, then spawns the worker), GET /api/v1/runs (list), GET /api/v1/runs/{id} (poll live progress), and GET /api/v1/runs/{id}/predictions (per-candle calls for the overlay chart). A thin HTTP layer: status codes here, DB work in the services.',
      },
      {
        path: 'src/backend/constants.py',
        desc: 'Named constants shared across the backend — the sigmoid decision threshold (PROB_THRESHOLD) and the early-stopping improvement floor (EARLY_STOP_DELTA) — replacing scattered magic numbers.',
      },
    ],
  },
  {
    label: 'Backend — shared infrastructure',
    files: [
      {
        path: 'src/backend/models.py',
        desc: 'Adds TrainingRun (stage, data slice start/end, hyperparams/metrics/progress JSON, status, artifact path) — the row the UI polls during training — and FeatureCache (used from Stage 3 on).',
      },
      {
        path: 'src/backend/schemas.py',
        desc: 'Adds LstmHyperParams (defaults and bounds for seq_len, horizon, hidden, layers, dropout, lr, batch, epochs, patience, lr_factor, lr_patience), TrainLstmRequest, and TrainingRunOut. Also home to normalize_symbol(), the single place ticker symbols are canonicalized.',
      },
      {
        path: 'src/backend/main.py · db.py · config.py · db_startup.py',
        desc: 'The shared FastAPI app, SQLAlchemy engine/session (db.py also defines SessionDep, the dependency every handler uses), config, and the startup migrate-and-recover housekeeping (see Stage 1 for detail). The training router is registered in main.py; the trainer opens its own DB session via SessionLocal.',
      },
    ],
  },
  {
    label: 'Frontend',
    files: [
      {
        path: 'src/frontend/src/pages/Stage2Lstm.jsx',
        desc: 'This page — a thin shell that owns the state and handlers, and wires together the examples panel, training form, results panel, and runs table. The heavyweight pieces live in pages/stage2/ and hooks/.',
      },
      {
        path: 'src/frontend/src/pages/stage2/hyperparams.js',
        desc: 'The hyperparameter form spec (HP_FIELDS), the defaults (HP_DEFAULTS), and which params appear as chips on example cards (CHIP_KEYS).',
      },
      {
        path: 'src/frontend/src/pages/stage2/examples.js',
        desc: 'The one-click example presets (smoke test, LR steps, overfit, honest baseline), each tuned to surface a specific lesson.',
      },
      {
        path: 'src/frontend/src/pages/stage2/stageFiles.js',
        desc: 'The data for this very section — the grouped file list FilesPanel renders.',
      },
      {
        path: 'src/frontend/src/pages/stage2/ExamplesPanel.jsx',
        desc: 'The Examples section UI: the preset cards with their expected outcomes, parameter chips, and Apply buttons.',
      },
      {
        path: 'src/frontend/src/pages/stage2/TrainForm.jsx',
        desc: 'The Parameter Config section UI: data-source + date-slice selectors, the hyperparameter grid, and the Train/Reset buttons.',
      },
      {
        path: 'src/frontend/src/pages/stage2/RunResults.jsx',
        desc: 'The Run → Results section UI: training progress, live metric charts, the run verdict, and the on-candle prediction overlay.',
      },
      {
        path: 'src/frontend/src/hooks/usePolledRun.js',
        desc: 'Custom hook that owns the live-watch loop: while the run is queued/running it re-fetches GET /runs/{id} every 1.5s so the page re-renders with fresh progress.',
      },
      {
        path: 'src/frontend/src/hooks/useInventory.js',
        desc: 'Custom hook that fetches the stored-data inventory on mount — shared with Stage 1.',
      },
      {
        path: 'src/frontend/src/components/Stage2FlowChart.jsx',
        desc: 'The "How It All Flows" diagram in section 3 — every box colour-coded by where it runs (browser, FastAPI, training thread, DB row, artifact on disk), showing how a run moves from the Train click to the out-of-sample overlay.',
      },
      {
        path: 'src/frontend/src/components/HyperParamForm.jsx',
        desc: 'Reusable numeric hyperparameter grid driven by a field spec — used here for the LSTM params, and by later stages for theirs.',
      },
      {
        path: 'src/frontend/src/components/MetricsChart.jsx',
        desc: 'Reusable inline-SVG charts that update live: Loss (train vs val), Learning rate, and Validation accuracy across epochs — with a dashed majority-class baseline line on the accuracy plot once the run finishes.',
      },
      {
        path: 'src/frontend/src/components/TrainingProgress.jsx',
        desc: 'Reusable status panel: status badge, live epoch counter, final test metrics, and the 2×2 confusion matrix.',
      },
      {
        path: 'src/frontend/src/components/RunVerdict.jsx',
        desc: 'The "Run verdict" panel after a run finishes: a plain-English diagnosis (edge over the majority baseline, overfitting, under-training, data size, label skew/shift), each finding ending in a concrete knob to turn.',
      },
      {
        path: 'src/frontend/src/components/RunsTable.jsx',
        desc: 'The "Past Runs — Compare" table: every run\'s key params, test accuracy and baseline edge side by side, with View (reload its results), Use params (load its config into the form) and Delete (remove the run + its saved artifact; failed runs show their error inline) actions.',
      },
      {
        path: 'src/frontend/src/lib/runStats.js',
        desc: 'The run-quality math shared by RunVerdict and RunsTable: majority-class baseline, binomial standard error for "real edge vs noise", LSTM parameter count, and the full analyzeRun() diagnosis. Unit-tested in runStats.test.js.',
      },
      {
        path: 'src/frontend/src/lib/statusStyles.js',
        desc: 'The run-status → Tailwind badge color map, shared by TrainingProgress and RunsTable.',
      },
      {
        path: 'src/frontend/src/lib/types.js',
        desc: 'JSDoc typedefs for the shapes crossing the API boundary (Run, EpochProgress, RunMetrics, Bar, …) — editor autocomplete and shape-checking without TypeScript.',
      },
      {
        path: 'src/frontend/src/constants.js',
        desc: 'App-wide named constants: POLL_INTERVAL_MS (the 1.5s run-polling cadence used by usePolledRun) and CHART_HEIGHT_PX (the candlestick chart height).',
      },
      {
        path: 'src/frontend/src/charts/PriceChart.jsx',
        desc: "The Stage 1 candlestick + volume chart, reused here with a markers prop to overlay the model's per-candle ▲/▼ direction predictions.",
      },
      {
        path: 'src/frontend/src/api/client.js',
        desc: 'Adds the training calls: trainLstm (start a run), getRun (poll one), getRuns (list), and getRunPredictions (fetch the overlay markers). Return shapes documented via lib/types.js.',
      },
      {
        path: 'src/frontend/src/components/ui/ · FilesPanel.jsx · LessonPanel.jsx · Stepper.jsx · App.jsx · main.jsx',
        desc: 'Shared UI primitives (Section, Field, Table, ErrorNote), this files section, the markdown lesson renderer, the stage stepper, the app layout, and the router (see Stage 1).',
      },
    ],
  },
  {
    label: 'Tests — proving it works',
    files: [
      {
        path: 'src/backend/tests/conftest.py',
        desc: 'Shared test fixtures: the FastAPI app wired to an in-memory SQLite database by overriding the get_session dependency, with tables dropped and recreated per test (see Stage 1). Run the whole backend suite from the repo root with: uv run pytest',
      },
      {
        path: 'src/backend/tests/test_datasets.py',
        desc: "The leakage guards, under test: the scaler's mean/std come from the training split only, windows never cross a split boundary, labels track the real close price through the return-feature transform, and too-few bars fails with a helpful error. These tests are why you can trust the test accuracy is honest. Run with: uv run pytest src/backend/tests/test_datasets.py",
      },
      {
        path: 'src/backend/tests/test_train_router.py',
        desc: 'The training API contract: POST /train/lstm returns 400 with no stored bars and otherwise creates a queued run (the worker thread is monkeypatched to a no-op — the real training loop is verified end-to-end through this page); runs list newest-first with stage/limit filters; missing runs 404; predictions require a finished run with a saved artifact. Run with: uv run pytest src/backend/tests/test_train_router.py',
      },
      {
        path: 'src/frontend/src/lib/runStats.test.js',
        desc: "Vitest suite for the verdict math: majority baseline, edge-vs-noise significance (2 standard errors), the LSTM parameter count formula, and analyzeRun's findings (no-edge, overfitting, tiny dataset, collapsed predictions) against hand-crafted runs. Run from src/frontend with: npm test",
      },
    ],
  },
  {
    label: 'Lesson content',
    files: [
      {
        path: 'src/frontend/src/content/stage2.what.md',
        desc: 'The "What we\'re doing" lesson text shown in section 1.',
      },
      {
        path: 'src/frontend/src/content/stage2.why.md',
        desc: 'The "Why we\'re doing it" lesson text shown in section 2.',
      },
      {
        path: 'src/frontend/src/content/stage2.understand.md',
        desc: 'The "What am I to see and learn" lesson shown in section 8 — maps the loss/accuracy/confusion outputs back to reading a candlestick chart.',
      },
      {
        path: 'src/frontend/src/content/stage2.writeup.md',
        desc: 'The full deep-dive writeup shown in section 9 (windows, why an LSTM, return features, the time-ordered split, reading the loss/LR/accuracy charts).',
      },
    ],
  },
]
