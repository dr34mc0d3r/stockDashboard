import { useEffect, useState } from 'react'
import CandlestickChart from '../components/CandlestickChart.jsx'
import IndicatorChart from '../components/IndicatorChart.jsx'

const TIMEFRAMES = ['1m', '5m', '1h', '1d']

// Distinct colors for indicator line charts, assigned by order.
const LINE_COLORS = ['#2563eb', '#16a34a', '#d97706', '#9333ea', '#dc2626', '#0891b2']

function formatNumber(value) {
  if (value == null) return '—'
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 })
}

function readingTone(reading) {
  const r = reading.toLowerCase()
  if (/(panic|exhausting|selling|overextended)/.test(r))
    return 'bg-red-50 text-red-700'
  if (/(buying|sustainable|building|calm)/.test(r))
    return 'bg-green-50 text-green-700'
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
          className="mt-1 rounded bg-gray-50 p-2 text-xs text-gray-700"
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
    period: 14,
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
  const [indicators, setIndicators] = useState({})
  const [indError, setIndError] = useState(null)

  const update = (key) => (e) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))

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

  // Fetch indicators whenever the submitted query or the selection changes.
  // State is only set inside async callbacks (never synchronously in the
  // effect body), and stale requests are ignored via the cancelled flag.
  useEffect(() => {
    if (!query || selected.size === 0) return
    let cancelled = false
    const params = new URLSearchParams({
      symbol: query.symbol,
      start: query.start,
      end: query.end,
      timeframe: query.timeframe,
      period: query.period,
      include: [...selected].join(','),
    })
    fetch(`/api/indicators?${params}`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail || `Request failed (${res.status})`)
        }
        return res.json()
      })
      .then((body) => {
        if (cancelled) return
        setIndicators(body.indicators)
        setIndError(null)
      })
      .catch((err) => {
        if (!cancelled) setIndError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [query, selected])

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
        <Field label="Period">
          <input
            type="number"
            min="2"
            value={form.period}
            onChange={update('period')}
            className="w-20 rounded-md border border-gray-300 px-2 py-1"
          />
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
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            {catalog.map((meta) => (
              <label
                key={meta.key}
                className="flex items-center gap-2 text-sm"
                title={meta.description}
              >
                <input
                  type="checkbox"
                  checked={selected.has(meta.key)}
                  onChange={() => toggleIndicator(meta.key)}
                />
                {meta.label}
              </label>
            ))}
          </div>
        </div>
      )}

      {error && (
        <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {data && (
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
              {shownIndicators.map((ind, i) => {
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
                        </p>
                      </div>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${readingTone(ind.reading)}`}
                      >
                        {ind.reading}
                      </span>
                    </div>
                    <IndicatorChart
                      points={ind.series[ind.key] ?? []}
                      color={LINE_COLORS[i % LINE_COLORS.length]}
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
