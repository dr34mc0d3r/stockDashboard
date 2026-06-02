import { useEffect, useRef, useState } from 'react'
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  createChart,
} from 'lightweight-charts'
import { useChartSync } from '../lib/chartSync.js'

const UP_COLOR = '#16a34a'
const DOWN_COLOR = '#dc2626'

// Convert API bars ({ timestamp, open, high, low, close, volume }) into the
// shapes lightweight-charts expects for the candle and volume series.
// lightweight-charts requires times to be unique and strictly ascending.
function toSeriesData(bars) {
  const seen = new Set()
  const cleaned = bars
    .map((bar) => ({
      time: Math.floor(Date.parse(bar.timestamp) / 1000),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume,
    }))
    .filter((bar) => Number.isFinite(bar.time))
    .sort((a, b) => a.time - b.time)
    .filter((bar) => {
      if (seen.has(bar.time)) return false
      seen.add(bar.time)
      return true
    })

  const candles = cleaned.map(({ time, open, high, low, close }) => ({
    time,
    open,
    high,
    low,
    close,
  }))
  const volumes = cleaned.map(({ time, open, close, volume }) => ({
    time,
    value: volume ?? 0,
    color: close >= open ? UP_COLOR : DOWN_COLOR,
  }))
  return { candles, volumes }
}

function formatPrice(value) {
  if (value == null || !Number.isFinite(value)) return '—'
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 })
}

function formatVolume(value) {
  if (value == null || !Number.isFinite(value)) return '—'
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })
}

/**
 * Reusable TradingView-style candlestick chart with a volume histogram and an
 * OHLCV legend that tracks the crosshair (defaulting to the most recent bar).
 * Pan (drag / scroll) and zoom (wheel / pinch) are handled natively by
 * lightweight-charts.
 *
 * @param {{ bars?: Array, height?: number }} props
 */
export default function CandlestickChart({ bars = [], height = 400 }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const candleSeriesRef = useRef(null)
  const volumeSeriesRef = useRef(null)
  const sync = useChartSync()

  // The OHLCV values shown in the legend; null until there's data to show.
  const [legend, setLegend] = useState(null)

  // Create the chart once on mount.
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#374151',
      },
      grid: {
        vertLines: { color: '#f3f4f6' },
        horzLines: { color: '#f3f4f6' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#e5e7eb',
      },
      rightPriceScale: { borderColor: '#e5e7eb' },
      // Pan & zoom (on by default; set explicitly for clarity).
      handleScroll: true,
      handleScale: true,
    })

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOR,
      downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR,
      borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR,
      wickDownColor: DOWN_COLOR,
    })

    // Volume as an overlay histogram pinned to the bottom ~20% of the pane.
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      priceLineVisible: false,
      lastValueVisible: false,
    })
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    chartRef.current = chart
    candleSeriesRef.current = candleSeries
    volumeSeriesRef.current = volumeSeries
    const unregister = sync?.register(chart)

    // Update the legend as the crosshair moves; clear it when it leaves so the
    // effect below can fall back to the latest bar.
    const onCrosshairMove = (param) => {
      const candle = param.seriesData?.get(candleSeries)
      const volume = param.seriesData?.get(volumeSeries)
      if (!candle) {
        setLegend(null)
        return
      }
      setLegend({ ...candle, volume: volume?.value })
    }
    chart.subscribeCrosshairMove(onCrosshairMove)

    return () => {
      chart.unsubscribeCrosshairMove(onCrosshairMove)
      unregister?.()
      chart.remove()
      chartRef.current = null
      candleSeriesRef.current = null
      volumeSeriesRef.current = null
    }
  }, [sync])

  // Push new data whenever bars change, then fit the view to it. Default the
  // legend to the most recent bar so values are visible without hovering.
  useEffect(() => {
    if (!candleSeriesRef.current) return
    const { candles, volumes } = toSeriesData(bars)
    candleSeriesRef.current.setData(candles)
    volumeSeriesRef.current?.setData(volumes)
    chartRef.current?.timeScale().fitContent()

    const lastCandle = candles[candles.length - 1]
    const lastVolume = volumes[volumes.length - 1]
    setLegend(
      lastCandle ? { ...lastCandle, volume: lastVolume?.value } : null,
    )
  }, [bars])

  return (
    <div className="relative w-full" style={{ height }}>
      {legend && (
        <div className="pointer-events-none absolute left-2 top-2 z-10 flex flex-wrap gap-x-3 gap-y-0.5 rounded bg-white/85 px-2 py-1 font-mono text-xs text-gray-700 shadow-sm">
          <span>O <b className="text-gray-900">{formatPrice(legend.open)}</b></span>
          <span>H <b className="text-gray-900">{formatPrice(legend.high)}</b></span>
          <span>L <b className="text-gray-900">{formatPrice(legend.low)}</b></span>
          <span>C <b className="text-gray-900">{formatPrice(legend.close)}</b></span>
          <span>V <b className="text-gray-900">{formatVolume(legend.volume)}</b></span>
        </div>
      )}
      <div ref={containerRef} className="h-full w-full" />
    </div>
  )
}
