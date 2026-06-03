import { useEffect, useState } from 'react'
import LessonPanel from '../components/LessonPanel.jsx'
import PriceChart from '../charts/PriceChart.jsx'
import FilesPanel from '../components/FilesPanel.jsx'
import { getInventory, ingest, getBars, deleteBars } from '../api/client.js'

import whatMd from '../content/stage1.what.md?raw'
import whyMd from '../content/stage1.why.md?raw'
import writeupMd from '../content/stage1.writeup.md?raw'

const TIMEFRAMES = ['1m', '5m', '1h', '1d']

// The source files behind this stage, with what each one does.
const STAGE_FILES = [
  {
    label: 'Backend — API & ingest',
    files: [
      { path: 'src/backend/main.py', desc: 'FastAPI entry point. Builds the app, configures CORS, and on startup runs Base.metadata.create_all to auto-create tables (tolerant of an unreachable DB so the server still boots and stays Ctrl+C-able). Registers the ingest and data routers.' },
      { path: 'src/backend/config.py', desc: 'Loads secrets from src/.env (Alpaca keys, DB credentials) and assembles the SQLAlchemy DATABASE_URL via URL.create so special characters in the password are escaped. Defines the allowed CORS origins.' },
      { path: 'src/backend/db.py', desc: 'Creates the SQLAlchemy engine (pool_pre_ping + a 5s connect_timeout so a down DB never hangs startup), the SessionLocal factory, the declarative Base, and the get_session dependency that yields then closes a session per request.' },
      { path: 'src/backend/models.py', desc: 'ORM table definitions. For this stage: OhlcvBar (composite primary key symbol/timeframe/ts, DECIMAL(18,6) prices) and IngestionRun (one audit row per download with counts and status).' },
      { path: 'src/backend/schemas.py', desc: 'Pydantic request/response models: IngestRequest (validates dates and uppercases the symbol), IngestResponse, InventoryItem, and BarOut.' },
      { path: 'src/backend/services/alpaca_client.py', desc: 'Thin REST client for Alpaca market data. Follows the next_page_token cursor in a loop so large multi-page 1-minute pulls download completely instead of silently truncating at ~10k bars.' },
      { path: 'src/backend/services/ingest_service.py', desc: 'Orchestrates a download: fetches bars, normalizes them, and bulk-UPSERTs into ohlcv_bars (INSERT … ON DUPLICATE KEY UPDATE) so re-downloading an overlapping range is idempotent. Records an IngestionRun summary.' },
      { path: 'src/backend/routers/ingest.py', desc: 'Defines POST /api/v1/ingest. Validates start < end and delegates to the ingest service, translating Alpaca errors into HTTP error responses.' },
      { path: 'src/backend/routers/data.py', desc: 'Defines GET /api/v1/inventory (per symbol/timeframe bar counts + date span), GET /api/v1/bars (stored bars for the chart and later slicing), and DELETE /api/v1/bars.' },
    ],
  },
  {
    label: 'Frontend',
    files: [
      { path: 'src/frontend/src/pages/Stage1Data.jsx', desc: 'This page. Renders the 5-part template: the download form, the stored-data inventory table with per-row Chart and Delete actions, and the price chart.' },
      { path: 'src/frontend/src/api/client.js', desc: 'Fetch wrappers over the backend API. For this stage: getInventory, ingest, getBars, and deleteBars.' },
      { path: 'src/frontend/src/charts/PriceChart.jsx', desc: 'Renders a TradingView-style candlestick + volume chart with lightweight-charts, including a legend and pan/zoom.' },
      { path: 'src/frontend/src/components/LessonPanel.jsx', desc: 'Renders the lesson markdown (What / Why / Writeup) using react-markdown + remark-gfm.' },
      { path: 'src/frontend/src/components/Stepper.jsx', desc: 'The left-nav stage stepper: defines the ordered stage list and which stages are unlocked.' },
      { path: 'src/frontend/src/components/FilesPanel.jsx', desc: 'Renders this very section — the grouped list of files and their descriptions, reused by every stage.' },
      { path: 'src/frontend/src/App.jsx', desc: 'App shell: the sidebar (title + stepper) and the routed content outlet.' },
      { path: 'src/frontend/src/main.jsx', desc: 'React entry point. Sets up the router and maps each /stage/N path to its page.' },
    ],
  },
  {
    label: 'Lesson content',
    files: [
      { path: 'src/frontend/src/content/stage1.what.md', desc: 'The "What we\'re doing" lesson text shown in section 1.' },
      { path: 'src/frontend/src/content/stage1.why.md', desc: 'The "Why we\'re doing it" lesson text shown in section 2.' },
      { path: 'src/frontend/src/content/stage1.writeup.md', desc: 'The full deep-dive writeup shown in section 5 (OHLCV, timeframes, pagination, idempotent UPSERT, leakage).' },
    ],
  },
]

export default function Stage1Data() {
  const [form, setForm] = useState({
    symbol: 'AAPL',
    start: '2025-05-01',
    end: '2025-05-02',
    timeframe: '1m',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [inventory, setInventory] = useState([])
  const [chart, setChart] = useState(null) // { symbol, timeframe, bars }
  const [chartLoading, setChartLoading] = useState(false)

  const refreshInventory = () => getInventory().then(setInventory).catch(() => {})
  useEffect(() => {
    refreshInventory()
  }, [])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function loadChart(symbol, timeframe) {
    setChartLoading(true)
    try {
      const bars = await getBars(symbol, timeframe)
      setChart({ symbol, timeframe, bars })
    } catch (e) {
      setError(e.message)
    } finally {
      setChartLoading(false)
    }
  }

  async function onDelete(symbol, timeframe) {
    if (
      !window.confirm(
        `Delete all stored ${symbol} ${timeframe} bars? This cannot be undone.`,
      )
    )
      return
    setError('')
    try {
      await deleteBars(symbol, timeframe)
      // Clear the chart if it was showing the deleted series.
      if (chart && chart.symbol === symbol && chart.timeframe === timeframe)
        setChart(null)
      await refreshInventory()
    } catch (e) {
      setError(e.message)
    }
  }

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const res = await ingest(form)
      setResult(res)
      await refreshInventory()
      await loadChart(res.symbol, res.timeframe)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="text-sm font-medium text-sky-400">Stage 1</p>
        <h2 className="text-2xl font-bold text-white">Data Acquisition</h2>
      </header>

      <Section n={1} title="What We're Doing">
        <LessonPanel source={whatMd} />
      </Section>

      <Section n={2} title="Why We're Doing It">
        <LessonPanel source={whyMd} />
      </Section>

      <Section n={3} title="Parameter Config">
        <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-4">
          <Field label="Symbol">
            <input
              value={form.symbol}
              onChange={set('symbol')}
              className="w-28 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 uppercase"
            />
          </Field>
          <Field label="Start">
            <input
              type="date"
              value={form.start}
              onChange={set('start')}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
            />
          </Field>
          <Field label="End">
            <input
              type="date"
              value={form.end}
              onChange={set('end')}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
            />
          </Field>
          <Field label="Timeframe">
            <select
              value={form.timeframe}
              onChange={set('timeframe')}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
            >
              {TIMEFRAMES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-sky-500 px-5 py-2 font-semibold text-white hover:bg-sky-400 disabled:opacity-50"
          >
            {busy ? 'Downloading…' : 'Download'}
          </button>
        </form>

        {error && (
          <p className="mt-3 rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}
        {result && (
          <p className="mt-3 rounded-md bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
            Stored {result.bars_written.toLocaleString()} {result.symbol}{' '}
            {result.timeframe} bars
            {result.first_ts && (
              <>
                {' '}
                ({result.first_ts.replace('T', ' ')} →{' '}
                {result.last_ts.replace('T', ' ')})
              </>
            )}
            .
          </p>
        )}
      </Section>

      <Section n={4} title="Run → Results">
        <h3 className="mb-2 text-sm font-semibold text-slate-300">
          Stored data inventory
        </h3>
        {inventory.length === 0 ? (
          <p className="text-sm text-slate-500">
            Nothing stored yet — download something above.
          </p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900 text-slate-400">
                <tr>
                  <Th>Symbol</Th>
                  <Th>Timeframe</Th>
                  <Th className="text-right">Bars</Th>
                  <Th>Earliest</Th>
                  <Th>Latest</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {inventory.map((row) => (
                  <tr
                    key={`${row.symbol}-${row.timeframe}`}
                    className="border-t border-slate-800 hover:bg-slate-900/50"
                  >
                    <Td className="font-semibold text-slate-100">{row.symbol}</Td>
                    <Td>{row.timeframe}</Td>
                    <Td className="text-right tabular-nums">
                      {row.bar_count.toLocaleString()}
                    </Td>
                    <Td className="text-slate-400">
                      {row.earliest.replace('T', ' ')}
                    </Td>
                    <Td className="text-slate-400">
                      {row.latest.replace('T', ' ')}
                    </Td>
                    <Td className="text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => loadChart(row.symbol, row.timeframe)}
                          className="rounded bg-slate-700 px-3 py-1 text-xs hover:bg-slate-600"
                        >
                          Chart
                        </button>
                        <button
                          onClick={() => onDelete(row.symbol, row.timeframe)}
                          className="rounded bg-red-500/20 px-3 py-1 text-xs text-red-300 hover:bg-red-500/30"
                        >
                          Delete
                        </button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4">
          {chartLoading && <p className="text-sm text-slate-500">Loading chart…</p>}
          {chart && !chartLoading && (
            <PriceChart
              bars={chart.bars}
              symbol={chart.symbol}
              timeframe={chart.timeframe}
            />
          )}
        </div>
      </Section>

      <Section n={5} title="Full Writeup">
        <LessonPanel source={writeupMd} />
      </Section>

      <Section n={6} title="Files Behind This Stage">
        <p className="mb-4 text-sm text-slate-400">
          Every source file involved in this stage, and what each one does.
        </p>
        <FilesPanel groups={STAGE_FILES} />
      </Section>
    </div>
  )
}

function Section({ n, title, children }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/30 p-6">
      <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-500/20 text-sm text-sky-300">
          {n}
        </span>
        {title}
      </h3>
      {children}
    </section>
  )
}

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-slate-400">
      <span>{label}</span>
      {children}
    </label>
  )
}

const Th = ({ children, className = '' }) => (
  <th className={`px-3 py-2 text-left font-medium ${className}`}>{children}</th>
)
const Td = ({ children, className = '' }) => (
  <td className={`px-3 py-2 ${className}`}>{children}</td>
)
