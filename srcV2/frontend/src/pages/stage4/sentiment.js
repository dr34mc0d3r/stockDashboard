// Pure helpers for the Stage 4 page (vitest-covered in sentiment.test.js).

/**
 * Turn the coverage response into sparkline-ready points: x = day index,
 * y = net sentiment, plus the global extent for scaling.
 * @param {{daily: {day: string, net: number, count: number}[]}} coverage
 */
export function coverageToPoints(coverage) {
  const daily = coverage?.daily ?? []
  const maxAbs = Math.max(0.1, ...daily.map((d) => Math.abs(d.net)))
  return {
    points: daily.map((d, i) => ({ i, day: d.day, net: d.net, count: d.count })),
    maxAbs,
  }
}

/**
 * How much of a [start, end] training slice has news coverage — used to warn
 * before training. Both bounds optional; falls back to the corpus extent.
 * @param {{daily: {day: string}[], first_day: string|null, last_day: string|null}} coverage
 */
export function sliceCoverage(coverage, start, end) {
  const daily = coverage?.daily ?? []
  if (!daily.length) return { covered: 0, daysWithNews: 0 }
  const lo = start || coverage.first_day
  const hi = end || coverage.last_day
  const inSlice = daily.filter((d) => (!lo || d.day >= lo) && (!hi || d.day <= hi))
  // Rough span in days for the denominator (calendar days, good enough for a hint).
  const spanDays =
    lo && hi ? Math.max(1, Math.round((new Date(hi) - new Date(lo)) / 86400000) + 1) : daily.length
  return {
    covered: Math.min(1, inSlice.length / spanDays),
    daysWithNews: inSlice.length,
  }
}

/** The marker color for a net-sentiment value (matches the score bars). */
export const netColor = (net) => (net > 0.05 ? '#34d399' : net < -0.05 ? '#ef4444' : '#94a3b8')
