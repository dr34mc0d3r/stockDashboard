// The source files behind Stage 4, with what each one does.
// Rendered by FilesPanel in the page's "Files Behind This Stage" section —
// keep this in sync whenever files move or split.

export const STAGE_FILES = [
  {
    label: 'Backend — news & FinBERT',
    files: [
      {
        path: 'src/backend/services/sentiment/news_client.py',
        desc: "Alpaca News REST client — the Stage 1 bars client's twin: same credentials, same auth headers, same next_page_token pagination, pointed at /v1beta1/news. Headlines only (include_content=false), capped by max_articles, de-duped by Alpaca's stable article id.",
      },
      {
        path: 'src/backend/services/sentiment/scorer.py',
        desc: 'The lazy FinBERT batch scorer. ALL transformers imports live inside the function so the app boots without the optional sentiment dependency group; the model (ProsusAI/finbert, ~440MB one-time download) loads once per process and runs batches of 16 headlines on 2 CPU threads, mapping logits through its own id2label so positive/negative can never silently swap.',
      },
      {
        path: 'src/backend/services/sentiment/aggregate.py',
        desc: 'The leakage-critical pure module: daily_aggregate (per-day net = mean(pos) − mean(neg) + headline count) and align_to_bars (bars on day D read day D−lag; NaN before the first covered day, defined 0.0 on quiet days after it, never forward-filled). Numpy + stdlib only — loaded standalone by its tests, like datasets.py.',
      },
      {
        path: 'src/backend/services/sentiment/prep_service.py',
        desc: 'The run-once background job: fetch → upsert articles → FinBERT over still-unscored rows (resumable — an interrupted prep continues where it stopped) → daily aggregates → feature_cache under the finbert_daily set. Reports phases through a TrainingRun row (stage="finbert-prep") so the existing polling UI and orphan recovery apply.',
      },
      {
        path: 'src/backend/services/sentiment/sentiment_features.py',
        desc: 'The training-side reader: loads the cached daily aggregates and builds the two bar-aligned sentiment columns via align_to_bars, raising a clear "run sentiment prep first" error when the slice has no coverage.',
      },
      {
        path: 'src/backend/routers/sentiment.py',
        desc: 'POST /api/v1/sentiment/prepare (spawns the prep job, returns the run to poll), GET /api/v1/sentiment/headlines (the scored corpus for the browser), GET /api/v1/sentiment/coverage (per-day nets/counts for the timeline and slice checks).',
      },
      {
        path: 'src/backend/models.py',
        desc: 'Adds NewsArticle — composite PK (symbol, article id) for free dedupe, headline/source/url, and the three FinBERT score columns that stay NULL until scored.',
      },
    ],
  },
  {
    label: 'Backend — training (Stage 3 machinery, parameterized)',
    files: [
      {
        path: 'src/backend/routers/train.py',
        desc: 'Adds POST /api/v1/train/sentiment — the SAME multitask trainer with stage="sentiment" (clean runs-table separation), failing fast when sentiment is enabled with nothing cached. The predictions endpoint branches multitask|sentiment to the same overlay.',
      },
      {
        path: 'src/backend/services/training/trainer.py',
        desc: 'One addition in _train_multitask: when hyperparams.sentiment.enabled, hstack the two cached sentiment columns onto the indicator matrix. The dataset builder, loop, and scoring are untouched — a new data modality cost two columns.',
      },
      {
        path: 'src/backend/services/predict_service.py',
        desc: 'predict_overlay_multitask rebuilds the same sentiment columns for sentiment runs (same cache, same lag) — required, or n_features would not match the saved model.',
      },
      {
        path: 'src/backend/schemas.py',
        desc: 'Adds SentimentPrepRequest, HeadlineOut, CoverageOut, and SentimentConfig {enabled, lag_days} on MultiTaskHyperParams — the config is stored in the run row and the artifact, so inference reproduces training exactly.',
      },
      {
        path: 'pyproject.toml',
        desc: 'The optional [dependency-groups] sentiment: transformers <4.46 + tokenizers 0.19.x + safetensors — the combo with prebuilt wheels for torch 2.2.2 / Python 3.11 / Intel-mac. Install with: uv sync --group sentiment',
      },
    ],
  },
  {
    label: 'Frontend',
    files: [
      {
        path: 'src/frontend/src/pages/Stage4Sentiment.jsx',
        desc: 'This page — the thin shell on the 10-section template, wiring the prep panel, headline browser, coverage timeline, train form (with the sentiment toggle), results, and runs table.',
      },
      {
        path: 'src/frontend/src/pages/stage4/PrepPanel.jsx',
        desc: 'The fetch & score form with the live FinBERT progress bar (polls the finbert-prep run) and the corpus stats card on completion.',
      },
      {
        path: 'src/frontend/src/pages/stage4/HeadlineBrowser.jsx',
        desc: 'The teaching centerpiece: every stored headline with its pos/neutral/neg probabilities as a stacked score bar — read exactly what FinBERT read.',
      },
      {
        path: 'src/frontend/src/pages/stage4/CoverageTimeline.jsx',
        desc: 'Inline-SVG daily net-sentiment sparkline (green up / red down, height = strength) + covered-range readout — the "is my slice covered?" check.',
      },
      {
        path: 'src/frontend/src/pages/stage4/TrainForm.jsx',
        desc: "Stage 3's form plus the one new control: the news-sentiment toggle with a live slice-coverage hint; Train is disabled when sentiment is on but the slice has zero covered days.",
      },
      {
        path: 'src/frontend/src/pages/stage4/sentiment.js',
        desc: 'Pure helpers (vitest-covered): coverage → sparkline points, slice-coverage math for the train guard, net-value colors.',
      },
      {
        path: 'src/frontend/src/pages/stage4/examples.js · ExamplesPanel.jsx',
        desc: 'The A/B presets — Sentiment only, Indicators + sentiment, and the Stage 3 rematch (identical config, sentiment off) — each Apply loads hyperparams, indicators AND the toggle.',
      },
      {
        path: 'src/frontend/src/pages/stage4/hyperparams.js',
        desc: "Re-exports Stage 3's field spec and defaults — the model is the same three-headed net, so the form is too.",
      },
      {
        path: 'src/frontend/src/pages/stage4/stageFiles.js',
        desc: 'The data for this very section — the grouped file list FilesPanel renders.',
      },
      {
        path: 'src/frontend/src/components/Stage4FlowChart.jsx',
        desc: 'The "How It All Flows" diagram in section 3: the run-once prep phase (fetch → FinBERT → daily cache) and the train phase that reads it.',
      },
      {
        path: 'src/frontend/src/api/client.js',
        desc: 'Adds prepareSentiment, getHeadlines, getCoverage, and trainSentiment.',
      },
      {
        path: 'src/frontend/src/pages/stage3/ · components/ · hooks/',
        desc: "Reused unchanged: IndicatorPanel + indicators.js, RunResults (verdict + overlay), RunsTable, MetricsChart, TrainingProgress, HyperParamForm, the ui/ primitives, useInventory and usePolledRun — Stage 4's whole training UI is Stage 3's, plus one toggle.",
      },
    ],
  },
  {
    label: 'Tests — proving it works',
    files: [
      {
        path: 'src/backend/tests/test_news_client.py',
        desc: 'The Alpaca news client with urlopen monkeypatched: pagination via next_page_token, auth headers, include_content=false, the max_articles cap (and that it stops paging early), id dedupe and blank-headline skipping. Run with: uv run pytest src/backend/tests/test_news_client.py',
      },
      {
        path: 'src/backend/tests/test_sentiment_aggregate.py',
        desc: "The leakage rules, hard: lag-1 puts yesterday's news on today's bars (and same-day bars see nothing), NaN before the first covered day then defined values forever after, quiet days are 0.0 and never forward-filled, lag 0 exists for the comparison lesson. Standalone importlib like test_datasets.py. Run with: uv run pytest src/backend/tests/test_sentiment_aggregate.py",
      },
      {
        path: 'src/backend/tests/test_sentiment_router.py',
        desc: 'The prep pipeline with FinBERT replaced by a deterministic fake (tests never download the model): prepare creates a queued finbert-prep run; run_prep fetches/scores/aggregates/caches against the test DB; a second run skips already-scored rows; headlines + coverage endpoints. Run with: uv run pytest src/backend/tests/test_sentiment_router.py',
      },
      {
        path: 'src/backend/tests/test_train_router.py',
        desc: 'Stage 4 cases: /train/sentiment 400s with a "run sentiment prep first" message when nothing is cached, and creates a queued stage="sentiment" run echoing the sentiment config (worker monkeypatched). The real FinBERT path is verified manually: one prep run + one sentiment train through this page. Run with: uv run pytest src/backend/tests/test_train_router.py',
      },
      {
        path: 'src/frontend/src/pages/stage4/sentiment.test.js',
        desc: 'Vitest for the pure helpers: sparkline point/extent math, the slice-coverage calculation behind the Train guard, and the net-color mapping. Run from src/frontend with: npm test',
      },
    ],
  },
  {
    label: 'Lesson content',
    files: [
      {
        path: 'src/frontend/src/content/stage4.what.md',
        desc: 'The "What we\'re doing" lesson shown in section 1 — the two-phase pipeline and what FinBERT outputs.',
      },
      {
        path: 'src/frontend/src/content/stage4.why.md',
        desc: 'The "Why" lesson shown in section 2 — exogenous information, why a transformer beats word lists, run-once + cache, and the one-day-lag honesty.',
      },
      {
        path: 'src/frontend/src/content/stage4.understand.md',
        desc: 'The "What am I to see and learn" lesson shown in section 9 — reading FinBERT\'s calls, the lumpy coverage timeline, and how to read the A/B without fooling yourself.',
      },
      {
        path: 'src/frontend/src/content/stage4.writeup.md',
        desc: 'The full deep-dive shown in section 10: BERT → FinBERT, the prep pipeline, the three leakage rules, and what to try changing (including the lag-0 trap, demonstrated).',
      },
    ],
  },
]
