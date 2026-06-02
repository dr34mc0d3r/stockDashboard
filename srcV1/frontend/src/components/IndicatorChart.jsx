import { useEffect, useMemo, useRef } from 'react'
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

/**
 * Reusable line chart for one or more indicator series (pan/zoom native).
 *
 * Pass a single series via `points` (+ optional `color`), or several at once
 * via `lines` ([{ points, color }]) for multi-line indicators like MACD or
 * Bollinger Bands. `lines` takes precedence when provided.
 */
export default function IndicatorChart({
  points = [],
  lines = null,
  height = 140,
  color = '#2563eb',
}) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef([])
  const sync = useChartSync()

  const defs = useMemo(() => lines ?? [{ points, color }], [lines, points, color])
  // Recreate the chart only when the series shape (count + colors) changes;
  // data updates are handled by the second effect.
  const shapeKey = defs.map((d) => d.color).join(',')

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

    seriesRef.current = defs.map((d) =>
      chart.addSeries(LineSeries, { color: d.color, lineWidth: 2 }),
    )
    chartRef.current = chart
    const unregister = sync?.register(chart)

    return () => {
      unregister?.()
      chart.remove()
      chartRef.current = null
      seriesRef.current = []
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shapeKey, sync])

  useEffect(() => {
    if (!chartRef.current) return
    defs.forEach((d, idx) => {
      const series = seriesRef.current[idx]
      if (!series) return
      const line = toLine(d.points)
      const precision = precisionFor(line)
      series.applyOptions({
        priceFormat: { type: 'price', precision, minMove: 10 ** -precision },
      })
      series.setData(line)
    })
    chartRef.current.timeScale().fitContent()
  }, [defs])

  return <div ref={containerRef} className="w-full" style={{ height }} />
}
