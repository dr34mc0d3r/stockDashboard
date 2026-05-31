// Client-side port of the backend indicator math (see
// src/backend/services/indicators.py). The live stream delivers bars one at a
// time and there is no backend endpoint that computes indicators from an
// in-memory bar list, so the live page recomputes them in the browser. The
// functions here mirror their Python counterparts exactly so the readings match
// the historical page. Labels and descriptions still come from
// /api/indicators/catalog — only the math lives here.

// Approximate number of bars per trading year, used to annualize volatility.
const PERIODS_PER_YEAR = {
  '1m': 252 * 390,
  '5m': 252 * 78,
  '1h': 252 * 7,
  '1d': 252,
}

function typicalPrices(bars) {
  return bars.map((b) => (b.high + b.low + b.close) / 3)
}

function lastNonNull(series) {
  for (let i = series.length - 1; i >= 0; i--) {
    if (series[i] != null) return series[i]
  }
  return null
}

// Population standard deviation, matching Python's statistics.pstdev.
function pstdev(values) {
  const n = values.length
  if (n === 0) return 0
  const mean = values.reduce((a, b) => a + b, 0) / n
  const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / n
  return Math.sqrt(variance)
}

// Pair each series value with its bar timestamp (the { timestamp, value } shape
// IndicatorChart expects).
function toPoints(bars, series) {
  return bars.map((bar, i) => ({ timestamp: bar.timestamp, value: series[i] }))
}

// --------------------------------------------------------------------------- //
// Parkinson volatility
// --------------------------------------------------------------------------- //
function parkinsonVolatility(bars, period, timeframe) {
  const factor = 1.0 / (4.0 * Math.log(2.0) * period)
  const logHlSq = bars.map((b) =>
    b.high > 0 && b.low > 0 ? Math.log(b.high / b.low) ** 2 : null,
  )

  const series = []
  for (let i = 0; i < bars.length; i++) {
    const window = logHlSq.slice(i - period + 1, i + 1)
    if (i + 1 < period || window.some((x) => x == null)) {
      series.push(null)
    } else {
      series.push(Math.sqrt(factor * window.reduce((a, b) => a + b, 0)))
    }
  }

  const latest = lastNonNull(series)
  const perYear = PERIODS_PER_YEAR[timeframe] ?? 252
  const annualized = latest != null ? latest * Math.sqrt(perYear) : null

  const observed = series.filter((x) => x != null)
  let reading = 'insufficient data'
  if (latest != null && observed.length > 0) {
    const avg = observed.reduce((a, b) => a + b, 0) / observed.length
    if (latest > avg * 1.5)
      reading = 'panic — volatility spiking well above its own average'
    else if (latest > avg) reading = 'elevated — above its recent average'
    else reading = 'calm — at or below its recent average'
  }

  return {
    latest,
    reading,
    lines: { parkinson_volatility: series },
    extra: { annualized },
  }
}

// --------------------------------------------------------------------------- //
// Acceleration
// --------------------------------------------------------------------------- //
function acceleration(bars, period) {
  const closes = bars.map((b) => b.close)
  const n = closes.length

  const velocity = new Array(n).fill(null)
  for (let i = period; i < n; i++) velocity[i] = closes[i] - closes[i - period]

  const accel = new Array(n).fill(null)
  for (let i = 1; i < n; i++) {
    const prev = velocity[i - 1]
    const cur = velocity[i]
    if (prev != null && cur != null) accel[i] = cur - prev
  }

  const latest = lastNonNull(accel)
  let reading
  if (latest == null) reading = 'insufficient data'
  else if (latest > 0) reading = 'sustainable — momentum is still building'
  else if (latest < 0) reading = 'exhausting — momentum is fading'
  else reading = 'steady — momentum unchanged'

  return { latest, reading, lines: { acceleration: accel, velocity } }
}

// --------------------------------------------------------------------------- //
// Money Flow Ratio
// --------------------------------------------------------------------------- //
function moneyFlowRatio(bars, period) {
  const tp = typicalPrices(bars)
  const n = bars.length

  const signed = new Array(n).fill(0.0)
  for (let i = 1; i < n; i++) {
    const raw = tp[i] * bars[i].volume
    if (tp[i] > tp[i - 1]) signed[i] = raw
    else if (tp[i] < tp[i - 1]) signed[i] = -raw
  }

  const series = new Array(n).fill(null)
  const mfi = new Array(n).fill(null)
  for (let i = period; i < n; i++) {
    const window = signed.slice(i - period + 1, i + 1)
    const pos = window.filter((x) => x > 0).reduce((a, b) => a + b, 0)
    const neg = -window.filter((x) => x < 0).reduce((a, b) => a + b, 0)
    if (neg === 0) {
      series[i] = null
      mfi[i] = pos > 0 ? 100.0 : null
    } else {
      const ratio = pos / neg
      series[i] = ratio
      mfi[i] = 100.0 - 100.0 / (1.0 + ratio)
    }
  }

  const latest = lastNonNull(series)
  let reading
  if (latest == null) reading = 'no selling pressure in window — heavy buying'
  else if (latest > 1.2) reading = 'buying — money flow favors the ask'
  else if (latest < 0.8) reading = 'selling — money flow favors the bid'
  else reading = 'balanced — buyers and sellers roughly even'

  return {
    latest,
    reading,
    lines: { money_flow_ratio: series },
    extra: { mfi: lastNonNull(mfi) },
  }
}

// --------------------------------------------------------------------------- //
// VWAP Z-Score
// --------------------------------------------------------------------------- //
function vwapZscore(bars, period) {
  const tp = typicalPrices(bars)
  const closes = bars.map((b) => b.close)
  const vols = bars.map((b) => b.volume)
  const n = bars.length

  const series = new Array(n).fill(null)
  for (let i = period - 1; i < n; i++) {
    const lo = i - period + 1
    let volSum = 0
    for (let j = lo; j <= i; j++) volSum += vols[j]
    if (volSum === 0) continue
    let weighted = 0
    for (let j = lo; j <= i; j++) weighted += tp[j] * vols[j]
    const vwap = weighted / volSum
    const deviations = []
    for (let j = lo; j <= i; j++) deviations.push(closes[j] - vwap)
    const sd = pstdev(deviations)
    series[i] = sd === 0 ? 0.0 : (closes[i] - vwap) / sd
  }

  const latest = lastNonNull(series)
  let reading
  if (latest == null) reading = 'insufficient data'
  else if (latest > 2) reading = 'overextended high — stretched above VWAP'
  else if (latest < -2) reading = 'overextended low — stretched below VWAP'
  else reading = 'fair — within normal range of VWAP'

  return { latest, reading, lines: { vwap_zscore: series } }
}

// Registry keyed by the same keys the backend catalog uses.
const COMPUTERS = {
  parkinson_volatility: parkinsonVolatility,
  acceleration,
  money_flow_ratio: moneyFlowRatio,
  vwap_zscore: vwapZscore,
}

/**
 * Compute the requested indicators over a live bar list. Mirrors the shape the
 * backend /api/indicators endpoint returns so the same UI can render it.
 *
 * @param {Array} bars   - [{ timestamp, open, high, low, close, volume }]
 * @param {number} period
 * @param {string} timeframe
 * @param {Array} catalog - [{ key, label, description }] from the backend
 * @param {Set<string>} keys - which indicators to compute
 * @returns {Object} keyed by indicator key
 */
export function computeIndicators(bars, period, timeframe, catalog, keys) {
  const results = {}
  for (const key of keys) {
    const fn = COMPUTERS[key]
    if (!fn || bars.length === 0) continue
    const meta = catalog.find((c) => c.key === key)
    const comp = fn(bars, period, timeframe)
    const series = {}
    for (const [name, line] of Object.entries(comp.lines)) {
      series[name] = toPoints(bars, line)
    }
    results[key] = {
      key,
      label: meta?.label ?? key,
      description: meta?.description ?? '',
      latest: comp.latest,
      reading: comp.reading,
      series,
      extra: comp.extra ?? {},
    }
  }
  return results
}
