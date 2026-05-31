import { useEffect, useRef } from 'react'
import { CandlestickSeries, ColorType, createChart } from 'lightweight-charts'

// Convert API bars ({ timestamp, open, high, low, close }) into the
// { time, open, high, low, close } shape lightweight-charts expects.
// lightweight-charts requires times to be unique and strictly ascending.
function toCandles(bars) {
  const seen = new Set()
  return bars
    .map((bar) => ({
      time: Math.floor(Date.parse(bar.timestamp) / 1000),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }))
    .filter((candle) => Number.isFinite(candle.time))
    .sort((a, b) => a.time - b.time)
    .filter((candle) => {
      if (seen.has(candle.time)) return false
      seen.add(candle.time)
      return true
    })
}

/**
 * Reusable TradingView-style candlestick chart.
 * Pan (drag / scroll) and zoom (wheel / pinch) are handled natively by
 * lightweight-charts.
 *
 * @param {{ bars?: Array, height?: number }} props
 */
export default function CandlestickChart({ bars = [], height = 400 }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)

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

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderUpColor: '#16a34a',
      borderDownColor: '#dc2626',
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626',
    })

    chartRef.current = chart
    seriesRef.current = series

    return () => {
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [])

  // Push new data whenever bars change, then fit the view to it.
  useEffect(() => {
    if (!seriesRef.current) return
    seriesRef.current.setData(toCandles(bars))
    chartRef.current?.timeScale().fitContent()
  }, [bars])

  return <div ref={containerRef} className="w-full" style={{ height }} />
}
