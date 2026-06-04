// Unit tests for the Stage 4 pure helpers.
import { describe, expect, it } from 'vitest'
import { coverageToPoints, netColor, sliceCoverage } from './sentiment.js'

const COVERAGE = {
  symbol: 'TSLA',
  days_with_news: 3,
  first_day: '2025-06-02',
  last_day: '2025-06-10',
  daily: [
    { day: '2025-06-02', count: 4, net: 0.5 },
    { day: '2025-06-05', count: 1, net: -0.2 },
    { day: '2025-06-10', count: 2, net: 0.01 },
  ],
}

describe('coverageToPoints', () => {
  it('indexes days and computes the symmetric extent', () => {
    const { points, maxAbs } = coverageToPoints(COVERAGE)
    expect(points).toHaveLength(3)
    expect(points[1]).toEqual({ i: 1, day: '2025-06-05', net: -0.2, count: 1 })
    expect(maxAbs).toBe(0.5)
  })

  it('keeps a minimum extent so flat corpora still render', () => {
    expect(coverageToPoints({ daily: [{ day: 'x', net: 0, count: 1 }] }).maxAbs).toBe(0.1)
    expect(coverageToPoints(null).points).toEqual([])
  })
})

describe('sliceCoverage', () => {
  it('counts covered days inside the slice against its calendar span', () => {
    const c = sliceCoverage(COVERAGE, '2025-06-01', '2025-06-10')
    expect(c.daysWithNews).toBe(3)
    expect(c.covered).toBeCloseTo(3 / 10)
  })

  it('a slice outside the corpus has zero covered days', () => {
    const c = sliceCoverage(COVERAGE, '2025-07-01', '2025-07-31')
    expect(c.daysWithNews).toBe(0)
    expect(c.covered).toBe(0)
  })

  it('handles an empty corpus', () => {
    expect(sliceCoverage({ daily: [] }, null, null)).toEqual({ covered: 0, daysWithNews: 0 })
  })
})

describe('netColor', () => {
  it('maps positive/negative/neutral nets to the three colors', () => {
    expect(netColor(0.4)).toBe('#34d399')
    expect(netColor(-0.4)).toBe('#ef4444')
    expect(netColor(0.01)).toBe('#94a3b8')
  })
})
