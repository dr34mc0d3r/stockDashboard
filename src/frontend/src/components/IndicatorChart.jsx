import { useEffect, useRef } from 'react'
import { ColorType, LineSeries, createChart } from 'lightweight-charts'

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

/** Reusable line chart for a single indicator series (pan/zoom native). */
export default function IndicatorChart({ points = [], height = 140, color = '#2563eb' }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)

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

    return () => {
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [color])

  useEffect(() => {
    if (!seriesRef.current) return
    seriesRef.current.setData(toLine(points))
    chartRef.current?.timeScale().fitContent()
  }, [points])

  return <div ref={containerRef} className="w-full" style={{ height }} />
}
