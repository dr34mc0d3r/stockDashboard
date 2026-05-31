import { useEffect, useRef, useState } from 'react'

// Build the ws:// (or wss://) URL for the backend stream proxy, reusing the
// current page's host so Vite's dev proxy forwards it to FastAPI.
function streamUrl(symbols, channels) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const params = new URLSearchParams({ symbols, channels })
  return `${protocol}//${window.location.host}/api/stream?${params}`
}

const STATUS_TONE = {
  connecting: 'bg-amber-50 text-amber-700',
  open: 'bg-green-50 text-green-700',
  closed: 'bg-gray-100 text-gray-600',
  error: 'bg-red-50 text-red-700',
}

// Alpaca tags each frame with a "T" type: t=trade, q=quote, b=bar,
// plus control frames (success/subscription/error).
const FRAME_LABEL = {
  t: 'trade',
  q: 'quote',
  b: 'bar',
  subscription: 'subscription',
  success: 'success',
  error: 'error',
}

export default function OhlcvWebsocket() {
  const [symbols, setSymbols] = useState('AAPL')
  const [channels, setChannels] = useState('bars')
  const [status, setStatus] = useState('closed')
  const [messages, setMessages] = useState([])
  const [error, setError] = useState(null)
  const wsRef = useRef(null)

  function disconnect() {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }

  function connect() {
    disconnect()
    setError(null)
    setMessages([])
    setStatus('connecting')

    const ws = new WebSocket(streamUrl(symbols, channels))
    wsRef.current = ws

    ws.onopen = () => setStatus('open')
    ws.onmessage = (event) => {
      let payload
      try {
        payload = JSON.parse(event.data)
      } catch {
        payload = { raw: event.data }
      }
      // The proxy sends an {error} object on failure, otherwise a batch
      // (array) of Alpaca frames. Flatten batches into individual frames.
      if (payload && payload.error) {
        setError(payload.error)
        return
      }
      const frames = Array.isArray(payload) ? payload : [payload]
      const at = new Date().toISOString()
      setMessages((prev) => [
        ...frames.map((frame) => ({ at, frame })),
        ...prev,
      ].slice(0, 200))
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

      <p className="text-sm text-gray-600">
        Streams live market data from Alpaca
        (<code className="font-mono text-xs">
          wss://stream.data.alpaca.markets/v2/iex
        </code>)
        proxied through the backend.
      </p>

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-gray-200 bg-white p-4">
        <Field label="Symbols (comma-separated)">
          <input
            value={symbols}
            onChange={(e) => setSymbols(e.target.value)}
            disabled={connected}
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
        <button
          type="button"
          onClick={connect}
          disabled={connected}
          className="rounded-md bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
        >
          Connect
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

      {error && (
        <p className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="space-y-2">
        <p className="text-sm text-gray-600">
          {messages.length} frame{messages.length === 1 ? '' : 's'}
        </p>
        {messages.length === 0 ? (
          <p className="rounded-lg border border-dashed border-gray-300 px-4 py-8 text-center text-sm text-gray-400">
            No data yet. Connect to start streaming. (Bars/trades only arrive
            during market hours.)
          </p>
        ) : (
          <ul className="space-y-2">
            {messages.map((msg, i) => (
              <li
                key={`${msg.at}-${i}`}
                className="rounded-lg border border-gray-200 bg-white p-3"
              >
                <p className="mb-1 flex items-center gap-2 font-mono text-xs text-gray-400">
                  <span className="rounded bg-gray-100 px-1.5 py-0.5 text-gray-600">
                    {FRAME_LABEL[msg.frame?.T] ?? msg.frame?.T ?? 'frame'}
                  </span>
                  {msg.frame?.S && (
                    <span className="font-semibold text-gray-700">
                      {msg.frame.S}
                    </span>
                  )}
                  {msg.at}
                </p>
                <pre className="overflow-x-auto whitespace-pre-wrap break-words text-xs text-gray-700">
                  {JSON.stringify(msg.frame, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        )}
      </div>
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
