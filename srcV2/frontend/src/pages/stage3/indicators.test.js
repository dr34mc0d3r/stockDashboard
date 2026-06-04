// Unit tests for the Stage 3 indicator-selection helpers (pure functions).
import { describe, expect, it } from 'vitest'
import { defaultSelection, lineColor, selectionToRequest, toChartProps } from './indicators.js'

const CATALOG = [
  {
    key: 'sma',
    label: 'Simple Moving Average',
    placement: 'overlay',
    params: [{ name: 'period', label: 'Period', default: 20 }],
  },
  {
    key: 'macd',
    label: 'MACD',
    placement: 'pane',
    params: [
      { name: 'fast', label: 'Fast', default: 12 },
      { name: 'slow', label: 'Slow', default: 26 },
      { name: 'signal', label: 'Signal', default: 9 },
    ],
  },
]

describe('defaultSelection', () => {
  it('starts everything off with catalog-default params', () => {
    const sel = defaultSelection(CATALOG)
    expect(sel.sma).toEqual({ enabled: false, params: { period: 20 } })
    expect(sel.macd.params).toEqual({ fast: 12, slow: 26, signal: 9 })
  })
})

describe('selectionToRequest', () => {
  it('emits only enabled indicators, with their params', () => {
    const sel = {
      sma: { enabled: true, params: { period: 10 } },
      macd: { enabled: false, params: { fast: 12, slow: 26, signal: 9 } },
    }
    expect(selectionToRequest(sel)).toEqual([{ name: 'sma', params: { period: 10 } }])
  })

  it('returns an empty array when nothing is enabled', () => {
    expect(selectionToRequest(defaultSelection(CATALOG))).toEqual([])
  })
})

describe('toChartProps', () => {
  const RESULTS = {
    sma: {
      key: 'sma',
      label: 'Simple Moving Average',
      placement: 'overlay',
      series: {
        sma: [
          { timestamp: '2025-01-01T00:00:00', value: null },
          { timestamp: '2025-01-01T00:01:00', value: 101.5 },
        ],
      },
    },
    macd: {
      key: 'macd',
      label: 'MACD',
      placement: 'pane',
      series: {
        macd: [{ timestamp: '2025-01-01T00:00:00', value: 0.1 }],
        signal: [{ timestamp: '2025-01-01T00:00:00', value: 0.05 }],
      },
    },
  }

  it('splits overlay vs pane by placement', () => {
    const { overlays, panes } = toChartProps(RESULTS)
    expect(overlays).toHaveLength(1)
    expect(panes).toHaveLength(1)
    expect(panes[0].key).toBe('macd')
    expect(panes[0].series.map((s) => s.name)).toEqual(['macd', 'signal'])
  })

  it('normalizes timestamps to ts and keeps warm-up nulls', () => {
    const { overlays } = toChartProps(RESULTS)
    expect(overlays[0].points[0]).toEqual({ ts: '2025-01-01T00:00:00', value: null })
  })

  it('labels single-line indicators with the indicator label', () => {
    const { overlays } = toChartProps(RESULTS)
    expect(overlays[0].name).toBe('Simple Moving Average')
  })

  it('assigns stable per-line colors with a fallback', () => {
    expect(lineColor('macd', 'signal')).toBe('#f59e0b')
    expect(lineColor('unknown', 'line')).toBe('#94a3b8')
  })

  it('handles an empty result object', () => {
    expect(toChartProps({})).toEqual({ overlays: [], panes: [] })
    expect(toChartProps(undefined)).toEqual({ overlays: [], panes: [] })
  })
})
