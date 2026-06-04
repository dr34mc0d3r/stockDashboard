import { useEffect, useRef } from 'react'
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
} from 'lightweight-charts'

import { CHART_HEIGHT_PX } from '../constants.js'

// Stored bar timestamps are naive UTC ("2025-05-01T08:00:00"); append 'Z' so
// the browser parses them as UTC, then convert to epoch seconds for the chart.
const toEpoch = (ts) => Math.floor(new Date(ts.replace(/Z$/, '') + 'Z').getTime() / 1000)

// Indicator series arrive aligned 1:1 with bars, nulls during warm-up — the
// chart wants only the defined points.
const toLineData = (points) =>
  (points ?? [])
    .filter((p) => p.value != null)
    .map((p) => ({ time: toEpoch(p.ts), value: p.value }))

/**
 * TradingView-style candlestick chart with a volume sub-pane.
 * Pan + zoom are enabled by default; a legend tracks the crosshair.
 *
 * @param {object} props
 * @param {import('../lib/types.js').Bar[]} props.bars
 * @param {string} props.symbol
 * @param {string} props.timeframe
 * @param {{ts: string, position: string, color: string, shape: string, text?: string}[]} [props.markers]
 * @param {{name: string, color: string, points: {ts: string, value: number|null}[]}[]} [props.overlays]
 *   Price-scale indicator lines drawn ON the candlestick pane (SMA, EMA, …).
 * @param {{key: string, series: {name: string, color: string, points: {ts: string, value: number|null}[]}[]}[]} [props.panes]
 *   Own-scale indicators, each in its own stacked sub-pane below the volume
 *   pane (RSI, MACD, …) — native lightweight-charts v5 panes sharing the
 *   time axis with price.
 */
export default function PriceChart({ bars, symbol, timeframe, markers, overlays, panes }) {
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

    // Price-scale indicator overlays (SMA/EMA/Bollinger/VWAP) on the main pane.
    for (const ov of overlays ?? []) {
      const line = chart.addSeries(LineSeries, {
        color: ov.color,
        lineWidth: 1,
        title: ov.name,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      line.setData(toLineData(ov.points))
    }

    // Own-scale indicators in stacked sub-panes (after price=0, volume=1).
    ;(panes ?? []).forEach((pane, idx) => {
      const paneIndex = 2 + idx
      for (const s of pane.series) {
        const line = chart.addSeries(
          LineSeries,
          {
            color: s.color,
            lineWidth: 1,
            title: s.name,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          },
          paneIndex,
        )
        line.setData(toLineData(s.points))
      }
      try {
        chart.panes()[paneIndex]?.setHeight(90)
      } catch {
        /* pane sizing is best-effort */
      }
    })

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
  }, [bars, markers, overlays, panes])

  return (
    <div className="relative overflow-hidden rounded-lg border border-slate-800">
      <div className="flex items-center gap-3 border-b border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs">
        <span className="font-semibold text-slate-200">
          {symbol} · {timeframe}
        </span>
        <span ref={legendRef} className="text-slate-400" />
      </div>
      {/* Grow the canvas so each indicator sub-pane gets its ~90px slice. */}
      <div
        ref={containerRef}
        className="w-full"
        style={{ height: CHART_HEIGHT_PX + 90 * (panes?.length ?? 0) }}
      />
    </div>
  )
}
