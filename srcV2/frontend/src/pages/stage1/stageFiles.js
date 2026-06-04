// The source files behind Stage 1, with what each one does.
// Rendered by FilesPanel in the page's "Files Behind This Stage" section —
// keep this in sync whenever files move or split.

export const STAGE_FILES = [
  {
    label: 'Backend — API & ingest',
    files: [
      {
        path: 'src/backend/main.py',
        desc: 'FastAPI entry point. Builds the app, configures CORS, and registers the routers. Startup database housekeeping is delegated to db_startup.py (tolerant of an unreachable DB so the server still boots and stays Ctrl+C-able).',
      },
      {
        path: 'src/backend/db_startup.py',
        desc: 'Idempotent startup housekeeping called from the FastAPI lifespan: creates missing tables, adds newer training_runs columns, and marks runs left "running"/"queued" by a crashed process as errors.',
      },
      {
        path: 'src/backend/config.py',
        desc: 'Loads secrets from src/.env (Alpaca keys, DB credentials) and assembles the SQLAlchemy DATABASE_URL via URL.create so special characters in the password are escaped. Defines the allowed CORS origins.',
      },
      {
        path: 'src/backend/db.py',
        desc: 'Creates the SQLAlchemy engine (pool_pre_ping + a 5s connect_timeout so a down DB never hangs startup), the SessionLocal factory, the declarative Base, the get_session dependency, and SessionDep — the annotated session type every router handler uses.',
      },
      {
        path: 'src/backend/models.py',
        desc: 'ORM table definitions. For this stage: OhlcvBar (composite primary key symbol/timeframe/ts, DECIMAL(18,6) prices) and IngestionRun (one audit row per download with counts and status).',
      },
      {
        path: 'src/backend/schemas.py',
        desc: 'Pydantic request/response models: IngestRequest (validates dates), IngestResponse, InventoryItem, and BarOut. Also home to normalize_symbol(), the single place ticker symbols are trimmed and uppercased.',
      },
      {
        path: 'src/backend/services/alpaca_client.py',
        desc: 'Thin REST client for Alpaca market data. Follows the next_page_token cursor in a loop so large multi-page 1-minute pulls download completely instead of silently truncating at ~10k bars.',
      },
      {
        path: 'src/backend/services/ingest_service.py',
        desc: 'Orchestrates a download: fetches bars, normalizes them, and bulk-UPSERTs into ohlcv_bars (INSERT … ON DUPLICATE KEY UPDATE) so re-downloading an overlapping range is idempotent. Records an IngestionRun summary.',
      },
      {
        path: 'src/backend/services/bar_service.py',
        desc: 'Query helpers behind the data router: per-(symbol, timeframe) inventory aggregation, the date-sliced bar fetch, and the bulk delete — keeps the router a thin HTTP layer.',
      },
      {
        path: 'src/backend/routers/ingest.py',
        desc: 'Defines POST /api/v1/ingest. Validates start < end and delegates to the ingest service, translating Alpaca errors into HTTP error responses.',
      },
      {
        path: 'src/backend/routers/data.py',
        desc: 'Defines GET /api/v1/inventory (per symbol/timeframe bar counts + date span), GET /api/v1/bars (stored bars for the chart and later slicing), and DELETE /api/v1/bars. Delegates its SQL to services/bar_service.py.',
      },
    ],
  },
  {
    label: 'Frontend',
    files: [
      {
        path: 'src/frontend/src/pages/Stage1Data.jsx',
        desc: 'This page. Renders the download form, the stored-data inventory table with per-row Chart and Delete actions, and the price chart — composed from the shared ui/ primitives.',
      },
      {
        path: 'src/frontend/src/pages/stage1/stageFiles.js',
        desc: 'The data for this very section — the grouped file list FilesPanel renders.',
      },
      {
        path: 'src/frontend/src/hooks/useInventory.js',
        desc: 'Custom hook that fetches the stored-data inventory on mount and exposes a refresh function — shared with Stage 2.',
      },
      {
        path: 'src/frontend/src/api/client.js',
        desc: 'Fetch wrappers over the backend API. For this stage: getInventory, ingest, getBars, and deleteBars. Return shapes documented via lib/types.js.',
      },
      {
        path: 'src/frontend/src/charts/PriceChart.jsx',
        desc: 'Renders a TradingView-style candlestick + volume chart with lightweight-charts, including a legend and pan/zoom.',
      },
      {
        path: 'src/frontend/src/components/ui/Section.jsx · Field.jsx · Table.jsx · ErrorNote.jsx',
        desc: 'The shared UI primitives every stage page is built from: the numbered section card, the labeled form field, table cells, and the standard inline error message.',
      },
      {
        path: 'src/frontend/src/components/LessonPanel.jsx',
        desc: 'Renders the lesson markdown (What / Why / Writeup) using react-markdown + remark-gfm.',
      },
      {
        path: 'src/frontend/src/components/Stepper.jsx',
        desc: 'The left-nav stage stepper: defines the ordered stage list and which stages are unlocked.',
      },
      {
        path: 'src/frontend/src/components/FilesPanel.jsx',
        desc: 'Renders this very section — the grouped list of files and their descriptions, reused by every stage.',
      },
      {
        path: 'src/frontend/src/App.jsx',
        desc: 'App shell: the sidebar (title + stepper) and the routed content outlet.',
      },
      {
        path: 'src/frontend/src/main.jsx',
        desc: 'React entry point. Sets up the router and maps each /stage/N path to its page.',
      },
    ],
  },
  {
    label: 'Tests — proving it works',
    files: [
      {
        path: 'src/backend/tests/conftest.py',
        desc: 'Shared test fixtures: the FastAPI app wired to an in-memory SQLite database by overriding the get_session dependency — the one seam every router goes through. Tables are dropped and recreated per test, so every test starts truly empty. Run the whole backend suite from the repo root with: uv run pytest',
      },
      {
        path: 'src/backend/tests/test_data_router.py',
        desc: "Tests this stage's endpoints against seeded bars: inventory grouping and counts, bar ordering / limit / date filtering / case-insensitive symbols, and that delete removes exactly the right rows. (/ingest itself is not router-tested: its UPSERT is MySQL-only and the Alpaca call is external.) Run just this file with: uv run pytest src/backend/tests/test_data_router.py",
      },
    ],
  },
  {
    label: 'Lesson content',
    files: [
      {
        path: 'src/frontend/src/content/stage1.what.md',
        desc: 'The "What we\'re doing" lesson text shown in section 1.',
      },
      {
        path: 'src/frontend/src/content/stage1.why.md',
        desc: 'The "Why we\'re doing it" lesson text shown in section 2.',
      },
      {
        path: 'src/frontend/src/content/stage1.writeup.md',
        desc: 'The full deep-dive writeup shown in section 5 (OHLCV, timeframes, pagination, idempotent UPSERT, leakage).',
      },
    ],
  },
]
