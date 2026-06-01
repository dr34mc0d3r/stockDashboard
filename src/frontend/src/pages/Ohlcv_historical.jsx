import { useEffect, useState } from 'react'
import CandlestickChart from '../components/CandlestickChart.jsx'
import IndicatorChart from '../components/IndicatorChart.jsx'
import { ChartSyncProvider } from '../lib/chartSync.js'

const TIMEFRAMES = ['1m', '5m', '1h', '1d']

// Distinct colors for indicator line charts, assigned by order.
const LINE_COLORS = ['#2563eb', '#16a34a', '#d97706', '#9333ea', '#dc2626', '#0891b2']

function formatNumber(value) {
  if (value == null) return '—'
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 })
}

// Color a reading by its leading keyword (each reading starts with a tone
// word, e.g. "bullish — …", "overbought — …"). Anything unrecognized — and
// non-directional readings like "expanding"/"steady" — stays neutral gray.
const RED_WORDS = new Set([
  'panic', 'exhausting', 'selling', 'overextended', 'bearish',
  'overbought', 'distribution',
])
const GREEN_WORDS = new Set([
  'buying', 'sustainable', 'calm', 'bullish', 'oversold', 'accumulation',
])
function readingTone(reading) {
  const first = reading.toLowerCase().split(/\s+/)[0]
  if (RED_WORDS.has(first)) return 'bg-red-50 text-red-700'
  if (GREEN_WORDS.has(first)) return 'bg-green-50 text-green-700'
  return 'bg-gray-100 text-gray-600'
}

function Understanding({ description }) {
  const [isOpen, setIsOpen] = useState(false)
  return (
    <div className="mt-2 text-sm text-gray-600">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-xs text-blue-600 underline"
      >
        {isOpen ? 'Hide Understanding' : 'Show Understanding'}
      </button>
      {isOpen && (
        <div
          className="mt-1 space-y-1 rounded bg-gray-50 p-2 text-xs text-gray-700 [&_li]:mt-1 [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5"
          dangerouslySetInnerHTML={{ __html: description }}
        />
      )}
    </div>
  )
}

export default function Ohlcv() {
  const [form, setForm] = useState({
    symbol: 'AAPL',
    start: '2026-05-15',
    end: '2026-05-20',
    timeframe: '1h',
  })
  // The form values from the last successful submit (drives indicator fetches).
  const [query, setQuery] = useState(null)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [showTable, setShowTable] = useState(true)

  // Indicator catalog + selection + results.
  const [catalog, setCatalog] = useState([])
  const [selected, setSelected] = useState(new Set())
  // Per-indicator param overrides, e.g. { macd: { fast: 12 } }. Anything not
  // set here falls back to the catalog default via paramsForKey().
  const [paramValues, setParamValues] = useState({})
  const [indicators, setIndicators] = useState({})
  const [indError, setIndError] = useState(null)

  const update = (key) => (e) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))

  // Effective params for an indicator: catalog defaults merged with any
  // user overrides. Always returns a value for every declared param.
  function paramsForKey(key) {
    const meta = catalog.find((c) => c.key === key)
    const defaults = Object.fromEntries(
      (meta?.params ?? []).map((p) => [p.name, p.default]),
    )
    return { ...defaults, ...(paramValues[key] ?? {}) }
  }

  function setParam(key, name, value) {
    setParamValues((prev) => ({
      ...prev,
      [key]: { ...(prev[key] ?? {}), [name]: value },
    }))
  }

  // Load the available indicators once so the UI is driven by the backend.
  useEffect(() => {
    fetch('/api/indicators/catalog')
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((body) => setCatalog(body.indicators))
      .catch(() => setCatalog([]))
  }, [])

  function toggleIndicator(key) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setData(null)
    try {
      const params = new URLSearchParams({
        symbol: form.symbol,
        start: form.start,
        end: form.end,
        timeframe: form.timeframe,
      })
      const res = await fetch(`/api/ohlcv?${params}`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Request failed (${res.status})`)
      }
      setData(await res.json())
      setQuery({ ...form })
      setIndicators({}) // drop indicators from the previous query
      setShowTable(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Fetch indicators whenever the submitted query, the selection, or any
  // indicator's params change. Debounced so dragging a param input doesn't
  // fire a request per keystroke. Stale requests are ignored via `cancelled`.
  useEffect(() => {
    if (!query || selected.size === 0) return
    let cancelled = false
    const keys = [...selected]
    const body = {
      symbol: query.symbol,
      start: query.start,
      end: query.end,
      timeframe: query.timeframe,
      include: keys,
      params: Object.fromEntries(keys.map((k) => [k, paramsForKey(k)])),
    }
    const handle = setTimeout(() => {
      fetch('/api/indicators', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
        .then(async (res) => {
          if (!res.ok) {
            const errBody = await res.json().catch(() => ({}))
            throw new Error(errBody.detail || `Request failed (${res.status})`)
          }
          return res.json()
        })
        .then((resBody) => {
          if (cancelled) return
          setIndicators(resBody.indicators)
          setIndError(null)
        })
        .catch((err) => {
          if (!cancelled) setIndError(err.message)
        })
    }, 350)
    return () => {
      cancelled = true
      clearTimeout(handle)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, selected, paramValues])

  // Only show indicators that are currently selected.
  const shownIndicators = Object.values(indicators).filter((ind) =>
    selected.has(ind.key),
  )

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Historical OHLCV</h1>

      <form
        onSubmit={handleSubmit}
        className="flex flex-wrap items-end gap-4 rounded-lg border border-gray-200 bg-white p-4"
      >
        <Field label="Symbol">
          <input
            value={form.symbol}
            onChange={update('symbol')}
            className="w-28 rounded-md border border-gray-300 px-2 py-1 uppercase"
          />
        </Field>
        <Field label="Start">
          <input
            type="date"
            value={form.start}
            onChange={update('start')}
            className="rounded-md border border-gray-300 px-2 py-1"
          />
        </Field>
        <Field label="End">
          <input
            type="date"
            value={form.end}
            onChange={update('end')}
            className="rounded-md border border-gray-300 px-2 py-1"
          />
        </Field>
        <Field label="Timeframe">
          <select
            value={form.timeframe}
            onChange={update('timeframe')}
            className="rounded-md border border-gray-300 px-2 py-1"
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
        </Field>
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
        >
          {loading ? 'Loading…' : 'Fetch'}
        </button>
      </form>

      {/* Indicator selection — driven by the backend catalog. */}
      {catalog.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
            Indicators
          </p>
          <div className="flex flex-col gap-2">
            {catalog.map((meta) => {
              const isOn = selected.has(meta.key)
              const values = paramsForKey(meta.key)
              return (
                <div
                  key={meta.key}
                  className="flex flex-wrap items-center gap-x-4 gap-y-1"
                >
                  <label
                    className="flex items-center gap-2 text-sm"
                    title={meta.description}
                  >
                    <input
                      type="checkbox"
                      checked={isOn}
                      onChange={() => toggleIndicator(meta.key)}
                    />
                    {meta.label}
                  </label>
                  {isOn &&
                    (meta.params ?? []).map((p) => (
                      <label
                        key={p.name}
                        className="flex items-center gap-1 text-xs text-gray-500"
                      >
                        {p.label}
                        <input
                          type="number"
                          value={values[p.name]}
                          min={p.min ?? undefined}
                          max={p.max ?? undefined}
                          step={p.step ?? (p.type === 'float' ? 0.1 : 1)}
                          onChange={(e) =>
                            setParam(meta.key, p.name, Number(e.target.value))
                          }
                          className="w-16 rounded border border-gray-300 px-1 py-0.5"
                        />
                      </label>
                    ))}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {error && (
        <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {data && (
        <ChartSyncProvider>
        <div className="space-y-3">
          {data.bars.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-2">
              <CandlestickChart bars={data.bars} height={400} />
            </div>
          )}

          {/* Indicator cards for the current selection. */}
          {indError && (
            <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
              {indError}
            </p>
          )}
          {shownIndicators.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2">
              {shownIndicators.map((ind) => {
                const meta = catalog.find((c) => c.key === ind.key)
                return (
                  <div
                    key={ind.key}
                    className="rounded-lg border border-gray-200 bg-white p-3"
                  >
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-sm font-semibold">{ind.label}</h3>
                        <p className="text-xs text-gray-500">
                          latest: {formatNumber(ind.latest)}
                          {ind.extra?.annualized != null &&
                            ` · annualized: ${formatNumber(ind.extra.annualized)}`}
                          {ind.extra?.mfi != null &&
                            ` · MFI: ${formatNumber(ind.extra.mfi)}`}
                          {ind.extra?.histogram != null &&
                            ` · hist: ${formatNumber(ind.extra.histogram)}`}
                        </p>
                      </div>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${readingTone(ind.reading)}`}
                      >
                        {ind.reading}
                      </span>
                    </div>
                    {(() => {
                      const names = Object.keys(ind.series)
                      return (
                        names.length > 1 && (
                          <div className="mb-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500">
                            {names.map((name, j) => (
                              <span key={name} className="flex items-center gap-1">
                                <span
                                  className="inline-block h-2 w-2 rounded-full"
                                  style={{
                                    backgroundColor:
                                      LINE_COLORS[j % LINE_COLORS.length],
                                  }}
                                />
                                {name}
                              </span>
                            ))}
                          </div>
                        )
                      )
                    })()}
                    <IndicatorChart
                      lines={Object.values(ind.series).map((points, j) => ({
                        points,
                        color: LINE_COLORS[j % LINE_COLORS.length],
                      }))}
                      height={140}
                    />
                    {meta && <Understanding description={meta.description} />}
                  </div>
                )
              })}
            </div>
          )}

          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              {data.results_count} bars for{' '}
              <span className="font-medium">{data.symbol}</span> (
              {data.timeframe})
            </p>
            <button
              type="button"
              onClick={() => setShowTable((prev) => !prev)}
              className="rounded-md border border-gray-300 px-3 py-1 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              {showTable ? 'Hide table' : 'Show table'}
            </button>
          </div>
          {showTable && (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full text-right text-sm">
                <thead className="bg-gray-50 text-gray-500">
                  <tr>
                    <th className="px-4 py-2 text-left">Timestamp</th>
                    <th className="px-4 py-2">Open</th>
                    <th className="px-4 py-2">High</th>
                    <th className="px-4 py-2">Low</th>
                    <th className="px-4 py-2">Close</th>
                    <th className="px-4 py-2">Volume</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.bars.map((bar) => (
                    <tr key={bar.timestamp}>
                      <td className="px-4 py-2 text-left font-mono text-xs">
                        {bar.timestamp}
                      </td>
                      <td className="px-4 py-2">{bar.open.toFixed(2)}</td>
                      <td className="px-4 py-2">{bar.high.toFixed(2)}</td>
                      <td className="px-4 py-2">{bar.low.toFixed(2)}</td>
                      <td className="px-4 py-2">{bar.close.toFixed(2)}</td>
                      <td className="px-4 py-2">{bar.volume.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        </ChartSyncProvider>
      )}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1 text-left">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      {children}
    </label>
  )
}
