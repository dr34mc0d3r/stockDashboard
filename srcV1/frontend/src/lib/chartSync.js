import { createContext, createElement, useContext, useRef } from 'react'

// Coordinates pan/zoom across every chart rendered inside a <ChartSyncProvider>.
// Each chart registers its lightweight-charts instance; when one chart's
// visible time range changes (drag, wheel, pinch) we apply the same range to
// the others. We sync by *time* rather than logical (index) range because the
// indicator series drop null points, so their indices don't line up with the
// candlestick chart — absolute time does.

const ChartSyncContext = createContext(null)

export function ChartSyncProvider({ children }) {
  // `applying` guards against feedback loops: setVisibleRange fires the range
  // change subscription synchronously, which would otherwise re-broadcast.
  const stateRef = useRef({ charts: new Set(), applying: false })

  const api = useRef({
    register(chart) {
      const state = stateRef.current
      state.charts.add(chart)
      const timeScale = chart.timeScale()

      const handler = (range) => {
        if (!range || state.applying) return
        state.applying = true
        try {
          for (const other of state.charts) {
            if (other === chart) continue
            try {
              other.timeScale().setVisibleRange(range)
            } catch {
              // A chart with no data yet rejects setVisibleRange; ignore it.
            }
          }
        } finally {
          state.applying = false
        }
      }

      timeScale.subscribeVisibleTimeRangeChange(handler)
      return () => {
        timeScale.unsubscribeVisibleTimeRangeChange(handler)
        state.charts.delete(chart)
      }
    },
  }).current

  return createElement(ChartSyncContext.Provider, { value: api }, children)
}

// Returns the sync API, or null when used outside a provider (charts then
// behave independently).
export function useChartSync() {
  return useContext(ChartSyncContext)
}
