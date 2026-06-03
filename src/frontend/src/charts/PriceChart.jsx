import { useEffect, useRef } from 'react'
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  HistogramSeries,
} from 'lightweight-charts'

// Stored bar timestamps are naive UTC ("2025-05-01T08:00:00"); append 'Z' so
// the browser parses them as UTC, then convert to epoch seconds for the chart.
const toEpoch = (ts) => Math.floor(new Date(ts + 'Z').getTime() / 1000)

/**
 * TradingView-style candlestick chart with a volume sub-pane.
 * Pan + zoom are enabled by default; a legend tracks the crosshair.
 * Built so price-scale indicator overlays can be added on the main pane and
 * other indicators in additional panes in later stages.
 */
export default function PriceChart({ bars, symbol, timeframe, markers }) {
  const containerRef = useRef(null)
  const legendRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current || !bars?.length) return

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { color: '#0f172a' },
        textColor: '#cbd5e1',
        panes: { separatorColor: '#334155' },
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#334155',
      },
      rightPriceScale: { borderColor: '#334155' },
      crosshair: { mode: 1 },
    })

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })
    candles.setData(
      bars.map((b) => ({
        time: toEpoch(b.ts),
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    )

    // Volume in its own pane (index 1) so it never fights the price scale.
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: 'volume' }, priceScaleId: '' },
      1,
    )
    volume.setData(
      bars.map((b) => ({
        time: toEpoch(b.ts),
        value: b.volume,
        color: b.close >= b.open ? '#16a34a88' : '#dc262688',
      })),
    )
    try {
      chart.panes()[1]?.setHeight(110)
    } catch {
      /* pane sizing is best-effort */
    }

    // Optional prediction markers (e.g. an LSTM's per-candle direction calls).
    // Must be time-sorted; the backend returns them oldest-first already.
    if (markers?.length) {
      createSeriesMarkers(
        candles,
        markers.map((m) => ({
          time: toEpoch(m.ts),
          position: m.position,
          color: m.color,
          shape: m.shape,
          text: m.text || '',
        })),
      )
    }

    // Legend: live OHLCV under the crosshair, falling back to the last bar.
    const last = bars[bars.length - 1]
    const fmt = (v) => Number(v).toFixed(2)
    const render = (b) => {
      if (!legendRef.current || !b) return
      legendRef.current.innerHTML =
        `O <b>${fmt(b.open)}</b>  H <b>${fmt(b.high)}</b>  ` +
        `L <b>${fmt(b.low)}</b>  C <b>${fmt(b.close)}</b>` +
        (b.volume != null ? `  V <b>${Number(b.volume).toLocaleString()}</b>` : '')
    }
    render(last)
    chart.subscribeCrosshairMove((param) => {
      const c = param.seriesData?.get(candles)
      const v = param.seriesData?.get(volume)
      if (c) render({ ...c, volume: v?.value })
      else render(last)
    })

    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [bars, markers])

  return (
    <div className="relative overflow-hidden rounded-lg border border-slate-800">
      <div className="flex items-center gap-3 border-b border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs">
        <span className="font-semibold text-slate-200">
          {symbol} · {timeframe}
        </span>
        <span ref={legendRef} className="text-slate-400" />
      </div>
      <div ref={containerRef} className="h-[460px] w-full" />
    </div>
  )
}
