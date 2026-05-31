import { useEffect, useRef } from 'react'
import { ColorType, LineSeries, createChart } from 'lightweight-charts'
import { useChartSync } from '../lib/chartSync.js'

// Convert API points ({ timestamp, value }) into the { time, value } shape
// lightweight-charts expects: drop nulls, sort ascending, de-dupe times.
function toLine(points) {
  const seen = new Set()
  return points
    .filter((p) => p.value != null)
    .map((p) => ({
      time: Math.floor(Date.parse(p.timestamp) / 1000),
      value: p.value,
    }))
    .filter((p) => Number.isFinite(p.time))
    .sort((a, b) => a.time - b.time)
    .filter((p) => {
      if (seen.has(p.time)) return false
      seen.add(p.time)
      return true
    })
}

// Pick a display precision from the data's magnitude. Some indicators (e.g.
// Parkinson Volatility) produce values near zero, where the default 2-decimal
// format rounds everything — including the crosshair tooltip — to 0.00.
function precisionFor(line) {
  const maxAbs = line.reduce((m, p) => Math.max(m, Math.abs(p.value)), 0)
  if (maxAbs === 0) return 2
  if (maxAbs >= 1) return 2
  if (maxAbs >= 0.01) return 4
  return 6
}

/** Reusable line chart for a single indicator series (pan/zoom native). */
export default function IndicatorChart({ points = [], height = 140, color = '#2563eb' }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)
  const sync = useChartSync()

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#6b7280',
        attributionLogo: false,
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
      handleScroll: true,
      handleScale: true,
    })

    const series = chart.addSeries(LineSeries, { color, lineWidth: 2 })
    chartRef.current = chart
    seriesRef.current = series
    const unregister = sync?.register(chart)

    return () => {
      unregister?.()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [color, sync])

  useEffect(() => {
    if (!seriesRef.current) return
    const line = toLine(points)
    const precision = precisionFor(line)
    seriesRef.current.applyOptions({
      priceFormat: { type: 'price', precision, minMove: 10 ** -precision },
    })
    seriesRef.current.setData(line)
    chartRef.current?.timeScale().fitContent()
  }, [points])

  return <div ref={containerRef} className="w-full" style={{ height }} />
}
