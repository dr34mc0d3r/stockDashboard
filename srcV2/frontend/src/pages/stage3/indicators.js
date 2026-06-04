// Pure helpers around the indicator selection: building the API request from
// the panel's toggle state, and turning the API response into PriceChart
// props. No React in here — these are unit-tested in indicators.test.js.

// One stable color per indicator line, keyed "indicatorKey.lineName".
// Falls back to PALETTE_DEFAULT for anything unlisted.
export const LINE_COLORS = {
  'sma.sma': '#f59e0b',
  'ema.ema': '#38bdf8',
  'bollinger.upper': '#a78bfa',
  'bollinger.middle': '#7c3aed',
  'bollinger.lower': '#a78bfa',
  'vwap.vwap': '#f472b6',
  'rsi.rsi': '#34d399',
  'macd.macd': '#38bdf8',
  'macd.signal': '#f59e0b',
  'stochastic.k': '#34d399',
  'stochastic.d': '#f59e0b',
  'atr.atr': '#fb923c',
  'adx.adx': '#e2e8f0',
  'adx.plus_di': '#22c55e',
  'adx.minus_di': '#ef4444',
  'obv.obv': '#60a5fa',
}
export const PALETTE_DEFAULT = '#94a3b8'

export const lineColor = (indicatorKey, lineName) =>
  LINE_COLORS[`${indicatorKey}.${lineName}`] ?? PALETTE_DEFAULT

/**
 * Build the initial panel state from the fetched catalog: everything off,
 * params at their declared defaults.
 * @param {{key: string, params: {name: string, default: number}[]}[]} catalog
 * @returns {Record<string, {enabled: boolean, params: Record<string, number>}>}
 */
export function defaultSelection(catalog) {
  const selection = {}
  for (const spec of catalog) {
    const params = {}
    for (const p of spec.params) params[p.name] = p.default
    selection[spec.key] = { enabled: false, params }
  }
  return selection
}

/**
 * The `indicators=[{name, params}]` array the API expects, from panel state.
 * @param {Record<string, {enabled: boolean, params: Record<string, number>}>} selection
 */
export function selectionToRequest(selection) {
  return Object.entries(selection)
    .filter(([, v]) => v.enabled)
    .map(([name, v]) => ({ name, params: v.params }))
}

/**
 * Split an `/indicators` response into PriceChart props: price-pane overlay
 * lines vs own-pane series, with timestamps normalized to `ts` and colors
 * assigned per line.
 * @param {Record<string, any>} indicatorResults - response.indicators
 * @returns {{overlays: any[], panes: any[]}}
 */
export function toChartProps(indicatorResults) {
  const overlays = []
  const panes = []
  for (const result of Object.values(indicatorResults ?? {})) {
    const lines = Object.entries(result.series).map(([lineName, points]) => ({
      // Single-line indicators show their label; multi-line ones each line.
      name: Object.keys(result.series).length === 1 ? result.label : lineName,
      color: lineColor(result.key, lineName),
      points: points.map((p) => ({ ts: p.timestamp, value: p.value })),
    }))
    if (result.placement === 'overlay') overlays.push(...lines)
    else panes.push({ key: result.key, series: lines })
  }
  return { overlays, panes }
}
