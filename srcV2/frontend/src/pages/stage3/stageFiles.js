// The source files behind Stage 3, with what each one does.
// Rendered by FilesPanel in the page's "Files Behind This Stage" section —
// keep this in sync whenever files move or split.

export const STAGE_FILES = [
  {
    label: 'Backend — indicators & features',
    files: [
      {
        path: 'src/backend/services/features/indicators.py',
        desc: 'The 10 indicators (ported from srcV1) as pure stdlib functions in a self-registering catalog: Computation/Param dataclasses, shared window math (_ema, _wilder, _true_range), per-indicator placement ("overlay" vs "pane"), param resolution with defaults + clamping, and compute() — the single implementation feeding the chart AND the model.',
      },
      {
        path: 'src/backend/services/features/feature_pipeline.py',
        desc: "Bars → aligned (n, k) feature matrix: flattens every indicator line into named columns (NaN during warm-up), hashes the indicator config into a feature_set key, and caches the matrix in the feature_cache table (delete + bulk-insert, portable across MySQL/SQLite). Also estimate_warmup(), which measures a config's warm-up length on synthetic bars for the overlay's out-of-sample clamp.",
      },
      {
        path: 'src/backend/routers/features.py',
        desc: 'GET /api/v1/indicators/catalog (metadata the UI builds its panel from — params can never drift) and POST /api/v1/indicators (compute over stored bars; returns bars + aligned series so one request renders a chart preview).',
      },
    ],
  },
  {
    label: 'Backend — model & training',
    files: [
      {
        path: 'src/backend/ml/models/multitask.py',
        desc: "MultiTaskNet: Stage 2's LSTM trunk feeding three Linear(hidden, 1) heads — direction (logit → BCE), return and volatility (scalars → MSE on standardized targets) — plus build_model().",
      },
      {
        path: 'src/backend/services/datasets.py',
        desc: 'Gains build_multitask_dataset(): return features + indicator columns, warm-up trim (rows before every indicator is defined are dropped), time-ordered split with the scaler fit on train rows only, and three labels per window. TargetStats standardizes the regression targets with train-split stats. Deliberately never imports the indicator code — the matrix is passed in, keeping the module standalone-testable.',
      },
      {
        path: 'src/backend/services/training/trainer.py',
        desc: 'Gains the parallel multitask path: _build_loaders_mt (batches carry X + three labels), _multitask_loss (w_dir·BCE + w_ret·MSE + w_vol·MSE), _evaluate_mt (per-head metrics incl. the direction confusion matrix), _run_epochs_mt (scheduler + early stopping on the total val loss), and the _train_multitask wrapper that builds features → dataset → trains → saves.',
      },
      {
        path: 'src/backend/services/training/run_service.py',
        desc: 'create_run() now takes the stage ("lstm" or "multitask") instead of hardcoding it; same queued-row bookkeeping for both.',
      },
      {
        path: 'src/backend/services/predict_service.py',
        desc: "Gains predict_overlay_multitask(): rebuilds the run's exact features from its stored indicator config (saved scaler, no refit), clamps to the held-out test region accounting for indicator warm-up, and returns per-candle direction + predicted return + predicted volatility in natural units.",
      },
      {
        path: 'src/backend/routers/train.py',
        desc: 'Adds POST /api/v1/train/multitask; GET /runs/{id}/predictions now branches by run.stage to the right overlay function.',
      },
      {
        path: 'src/backend/schemas.py',
        desc: 'Adds IndicatorRequestItem / IndicatorsRequest / IndicatorsResponse, MultiTaskHyperParams (Stage 2 fields + w_dir/w_ret/w_vol, vol_window, indicators) and TrainMultiTaskRequest; PredictionPoint gains optional pred_return / pred_vol / actual_return.',
      },
      {
        path: 'src/backend/ml/registry.py',
        desc: 'The .pt bundle gains an extras dict — Stage 3 stores the regression-target scaling stats and feature column names there so inference reproduces training exactly.',
      },
      {
        path: 'src/backend/models.py',
        desc: 'FeatureCache — (symbol, timeframe, ts, feature_set) → payload JSON — goes from "defined for later" to actually used: one row per bar per indicator-config hash.',
      },
    ],
  },
  {
    label: 'Frontend',
    files: [
      {
        path: 'src/frontend/src/pages/Stage3MultiTask.jsx',
        desc: 'This page — the thin shell owning state and handlers, laying out the 10-section template. Indicator selection state drives both the live chart preview and the training request.',
      },
      {
        path: 'src/frontend/src/pages/stage3/IndicatorPanel.jsx',
        desc: "The toggle panel, built from the fetched catalog: grouped overlay vs own-pane, each toggle revealing that indicator's parameter inputs pre-filled with backend defaults.",
      },
      {
        path: 'src/frontend/src/pages/stage3/indicators.js',
        desc: 'Pure helpers (vitest-covered): defaultSelection (catalog → panel state), selectionToRequest (panel state → API items), toChartProps (API response → PriceChart overlays/panes with per-line colors).',
      },
      {
        path: 'src/frontend/src/pages/stage3/hyperparams.js',
        desc: 'The Stage 3 form spec: Stage 2 fields plus vol_window and the three per-task loss weights; defaults mirror MultiTaskHyperParams.',
      },
      {
        path: 'src/frontend/src/pages/stage3/examples.js',
        desc: 'Presets pairing hyperparameters WITH indicator selections: smoke test, trend pack, volatility focus, all-ten baseline.',
      },
      {
        path: 'src/frontend/src/pages/stage3/ExamplesPanel.jsx',
        desc: 'The preset cards — indicator chips + param chips + Apply, which loads both into the form.',
      },
      {
        path: 'src/frontend/src/pages/stage3/TrainForm.jsx',
        desc: 'The Parameter Config section: source/slice, the IndicatorPanel with its live chart preview ("what the model will see"), the hyperparameter grid, and Train/Reset.',
      },
      {
        path: 'src/frontend/src/pages/stage3/RunResults.jsx',
        desc: 'Run → Results: per-head live charts, the direction-head verdict (with a note on what it judges), and the overlay where each arrow carries its predicted return.',
      },
      {
        path: 'src/frontend/src/pages/stage3/stageFiles.js',
        desc: 'The data for this very section — the grouped file list FilesPanel renders.',
      },
      {
        path: 'src/frontend/src/components/Stage3FlowChart.jsx',
        desc: 'The "How It All Flows" diagram: indicator selection → preview → multitask train (feature pipeline + cache → dataset → three-headed net) → run row → out-of-sample overlay.',
      },
      {
        path: 'src/frontend/src/charts/PriceChart.jsx',
        desc: 'Gains two props: overlays (indicator lines drawn ON the price pane) and panes (own-scale indicators in stacked lightweight-charts v5 sub-panes sharing the time axis). The canvas grows ~90px per pane.',
      },
      {
        path: 'src/frontend/src/components/MetricsChart.jsx',
        desc: "Gains two conditional plots for multitask runs: the return head's and volatility head's validation MAE per epoch.",
      },
      {
        path: 'src/frontend/src/components/TrainingProgress.jsx',
        desc: 'Gains conditional rows for the multitask metrics: return MAE, volatility MAE, and the feature count.',
      },
      {
        path: 'src/frontend/src/lib/runStats.js',
        desc: "Gains multitaskParamCount (trunk + two extra heads); analyzeRun's capacity check now uses the run's real feature count and the right parameter formula per stage. The verdict itself works unchanged — Stage 3 keeps the direction-head metric keys.",
      },
      {
        path: 'src/frontend/src/api/client.js',
        desc: 'Adds getCatalog, computeIndicators, and trainMultiTask.',
      },
      {
        path: 'src/frontend/src/components/ui/ · RunsTable.jsx · RunVerdict.jsx · HyperParamForm.jsx · hooks/ · FilesPanel.jsx · LessonPanel.jsx',
        desc: 'Reused unchanged from Stages 1–2 (the point of keeping the direction-head metric keys stable): the shared primitives, the runs comparison table, the verdict, the param grid, the inventory + polling hooks.',
      },
    ],
  },
  {
    label: 'Tests — proving it works',
    files: [
      {
        path: 'src/backend/tests/test_indicators.py',
        desc: 'Golden values for all 10 indicators on hand-checkable series (SMA mean, EMA seeding, flat-price Bollinger collapse, RSI pinned at 100 on a pure uptrend, ATR on constant ranges…), parameter resolution/clamping, catalog schema incl. placement, and an alignment smoke test over the whole catalog. Run with: uv run pytest src/backend/tests/test_indicators.py',
      },
      {
        path: 'src/backend/tests/test_features_router.py',
        desc: 'The HTTP contract: catalog lists the 10 with params + placement; compute returns bars + 1:1-aligned series with warm-up nulls; unknown indicators 400; empty store returns empty. Run with: uv run pytest src/backend/tests/test_features_router.py',
      },
      {
        path: 'src/backend/tests/test_multitask_dataset.py',
        desc: 'The Stage 3 leakage and alignment guards: warm-up rows trimmed and counted, scaler fit on train rows only (a price jump in the test split must not move it), all three labels verified against hand-computed values, lookahead shrinking window counts, helpful errors. Loads datasets.py standalone like test_datasets.py. Run with: uv run pytest src/backend/tests/test_multitask_dataset.py',
      },
      {
        path: 'src/backend/tests/test_train_router.py',
        desc: 'Extended with the multitask endpoint: 400 without bars, queued run with the indicator config echoed in hyperparams (worker monkeypatched — the real loop is verified end-to-end through this page). Run with: uv run pytest src/backend/tests/test_train_router.py',
      },
      {
        path: 'src/frontend/src/pages/stage3/indicators.test.js',
        desc: 'Vitest for the pure selection helpers: catalog → default state, state → request array, API response → chart props (overlay/pane split, color assignment, timestamp normalization). Run from src/frontend with: npm test',
      },
    ],
  },
  {
    label: 'Lesson content',
    files: [
      {
        path: 'src/frontend/src/content/stage3.what.md',
        desc: 'The "What we\'re doing" lesson text shown in section 1.',
      },
      {
        path: 'src/frontend/src/content/stage3.why.md',
        desc: 'The "Why we\'re doing it" lesson shown in section 2 — hand-crafted features, multi-task learning, one source of truth, why cache now.',
      },
      {
        path: 'src/frontend/src/content/stage3.understand.md',
        desc: 'The "What am I to see and learn" lesson shown in section 8 — reading overlays/panes, the warm-up window, per-head metrics, and the volatility-vs-direction contrast.',
      },
      {
        path: 'src/frontend/src/content/stage3.writeup.md',
        desc: 'The full deep-dive shown in section 9: the 10 indicators, feature alignment + trimming, the three targets and why regression targets are standardized, the weighted loss, and what to try changing.',
      },
    ],
  },
]
