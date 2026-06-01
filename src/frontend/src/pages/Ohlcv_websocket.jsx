import { useEffect, useMemo, useRef, useState } from 'react'
import CandlestickChart from '../components/CandlestickChart.jsx'
import IndicatorChart from '../components/IndicatorChart.jsx'
import { computeIndicators, SUPPORTED_KEYS } from '../lib/indicators.js'
import { ChartSyncProvider } from '../lib/chartSync.js'

// Build the ws:// (or wss://) URL for the backend stream proxy, reusing the
// current page's host so Vite's dev proxy forwards it to FastAPI.
function streamUrl(symbols, channels) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const params = new URLSearchParams({ symbols, channels })
  return `${protocol}//${window.location.host}/api/stream?${params}`
}

// Live "bars" frames are 1-minute bars, so indicators annualize against 1m.
const LIVE_TIMEFRAME = '1m'

// Keep memory bounded — only the most recent bars are charted.
const MAX_BARS = 500

const STATUS_TONE = {
  connecting: 'bg-amber-50 text-amber-700',
  open: 'bg-green-50 text-green-700',
  closed: 'bg-gray-100 text-gray-600',
  error: 'bg-red-50 text-red-700',
}

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

// Convert an Alpaca bar frame ({T:"b", S, o, h, l, c, v, t}) into the bar shape
// the charts and indicator math expect.
function frameToBar(frame) {
  return {
    timestamp: frame.t,
    open: frame.o,
    high: frame.h,
    low: frame.l,
    close: frame.c,
    volume: frame.v,
  }
}

// Append a bar, replacing the last one if it shares a timestamp, and cap length.
function appendBar(existing, bar) {
  const bars = existing ? [...existing] : []
  const last = bars[bars.length - 1]
  if (last && last.timestamp === bar.timestamp) bars[bars.length - 1] = bar
  else bars.push(bar)
  return bars.slice(-MAX_BARS)
}

export default function OhlcvWebsocket() {
  const [symbols, setSymbols] = useState('AAPL')
  const [channels, setChannels] = useState('bars')
  const [period, setPeriod] = useState(14)
  const [status, setStatus] = useState('closed')
  const [error, setError] = useState(null)
  // Accumulated bars per symbol, e.g. { AAPL: [{timestamp, open, ...}, ...] }.
  const [barsBySymbol, setBarsBySymbol] = useState({})
  const [frameCount, setFrameCount] = useState(0)
  const wsRef = useRef(null)

  // Indicator catalog + selection (math runs client-side on the live bars).
  const [catalog, setCatalog] = useState([])
  const [selected, setSelected] = useState(new Set())

  // Load the available indicators once so the UI is driven by the backend.
  // The live page computes indicators in-browser, so it only offers the subset
  // ported to lib/indicators.js (SUPPORTED_KEYS); the rest are backend-only.
  useEffect(() => {
    fetch('/api/indicators/catalog')
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((body) =>
        setCatalog(body.indicators.filter((m) => SUPPORTED_KEYS.has(m.key))),
      )
      .catch(() => setCatalog([]))
  }, [])

  function toggleIndicator(key) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function disconnect() {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }

  function connect() {
    disconnect()
    setError(null)
    setBarsBySymbol({})
    setFrameCount(0)
    setStatus('connecting')

    const ws = new WebSocket(streamUrl(symbols, channels))
    wsRef.current = ws

    ws.onopen = () => setStatus('open')
    ws.onmessage = (event) => {
      let payload
      try {
        payload = JSON.parse(event.data)
      } catch {
        return
      }
      // The proxy sends an {error} object on failure, otherwise a batch
      // (array) of Alpaca frames. Flatten batches into individual frames.
      if (payload && payload.error) {
        setError(payload.error)
        return
      }
      const frames = Array.isArray(payload) ? payload : [payload]
      const bars = frames.filter((f) => f?.T === 'b' && f.S)
      if (bars.length === 0) return

      setFrameCount((n) => n + bars.length)
      setBarsBySymbol((prev) => {
        const next = { ...prev }
        for (const frame of bars) {
          next[frame.S] = appendBar(next[frame.S], frameToBar(frame))
        }
        return next
      })
    }
    ws.onerror = () => setStatus('error')
    ws.onclose = () => {
      setStatus('closed')
      wsRef.current = null
    }
  }

  // Tear the socket down if the user navigates away.
  useEffect(() => disconnect, [])

  const connected = status === 'open' || status === 'connecting'
  const symbolList = Object.keys(barsBySymbol).sort()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Live Market Data</h1>
        <span
          className={`rounded-full px-3 py-0.5 text-xs font-medium ${
            STATUS_TONE[status] ?? STATUS_TONE.closed
          }`}
        >
          {status}
        </span>
      </div>

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-gray-200 bg-white p-4">
        <Field label="Symbols">
          <input
            value={symbols}
            onChange={(e) => setSymbols(e.target.value)}
            disabled={connected}
            placeholder="AAPL,MSFT"
            className="w-48 rounded-md border border-gray-300 px-2 py-1 uppercase disabled:bg-gray-50"
          />
        </Field>
        <Field label="Channels">
          <input
            value={channels}
            onChange={(e) => setChannels(e.target.value)}
            disabled={connected}
            placeholder="bars,trades,quotes"
            className="w-48 rounded-md border border-gray-300 px-2 py-1 disabled:bg-gray-50"
          />
        </Field>
        <Field label="Period">
          <input
            type="number"
            min="2"
            value={period}
            onChange={(e) => setPeriod(Number(e.target.value))}
            className="w-20 rounded-md border border-gray-300 px-2 py-1"
          />
        </Field>
        <button
          type="button"
          onClick={connect}
          disabled={connected}
          className="rounded-md bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
        >
          {status === 'connecting' ? 'Connecting...' : 'Connect'}
        </button>
        <button
          type="button"
          onClick={disconnect}
          disabled={status === 'closed'}
          className="rounded-md border border-gray-300 px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
        >
          Disconnect
        </button>
      </div>

      {/* Indicator selection — driven by the backend catalog, computed live. */}
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

      <p className="text-sm text-gray-600">
        {frameCount} bar{frameCount === 1 ? '' : 's'} received
        {symbolList.length > 0 && ` · ${symbolList.length} symbol${
          symbolList.length === 1 ? '' : 's'
        }`}
      </p>

      {symbolList.length === 0 ? (
        <p className="rounded-lg border border-dashed border-gray-300 px-4 py-8 text-center text-sm text-gray-400">
          No bar data yet. Connect to start streaming (the chart needs the{' '}
          <span className="font-mono">bars</span> channel).
        </p>
      ) : (
        symbolList.map((symbol) => (
          <SymbolPanel
            key={symbol}
            symbol={symbol}
            bars={barsBySymbol[symbol]}
            period={period}
            catalog={catalog}
            selected={selected}
          />
        ))
      )}
    </div>
  )
}

// One live candlestick chart plus its indicator cards for a single symbol.
// Indicators are recomputed on every new bar so they update in real time.
function SymbolPanel({ symbol, bars, period, catalog, selected }) {
  const indicators = useMemo(
    () => computeIndicators(bars, period, LIVE_TIMEFRAME, catalog, selected),
    [bars, period, catalog, selected],
  )
  const shownIndicators = Object.values(indicators)

  return (
    <ChartSyncProvider>
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{symbol}</h2>
        <span className="text-sm text-gray-500">{bars.length} bars</span>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-2">
        <CandlestickChart bars={bars} height={400} />
      </div>

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
    </div>
    </ChartSyncProvider>
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
