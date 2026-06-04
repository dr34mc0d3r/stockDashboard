// Daily net-sentiment sparkline + coverage readout: green bars up = positive
// days, red bars down = negative, bar height = |net|. Answers "is the slice I
// want to train on actually covered by news?" at a glance.

import { coverageToPoints, netColor } from './sentiment.js'

const W = 720
const H = 90
const MID = H / 2

export default function CoverageTimeline({ coverage }) {
  const { points, maxAbs } = coverageToPoints(coverage)
  if (!points.length) {
    return <p className="text-sm text-slate-500">No coverage yet — run the corpus prep first.</p>
  }

  const bw = Math.max(2, Math.min(14, W / points.length - 2))
  const xAt = (i) => (points.length === 1 ? W / 2 : (i / (points.length - 1)) * (W - bw))

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap gap-x-5 text-xs text-slate-400">
        <span>
          <strong className="text-slate-200">{coverage.days_with_news}</strong> days with news
        </span>
        <span>
          {coverage.first_day} → {coverage.last_day}
        </span>
        <span>
          <span className="text-emerald-400">▮ positive</span> ·{' '}
          <span className="text-red-400">▮ negative</span> · height = strength
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full rounded-lg border border-slate-800 bg-slate-950/50"
      >
        <line x1={0} y1={MID} x2={W} y2={MID} stroke="#334155" strokeDasharray="3 3" />
        {points.map((p) => {
          const h = Math.max(2, (Math.abs(p.net) / maxAbs) * (MID - 6))
          return (
            <rect
              key={p.day}
              x={xAt(p.i)}
              y={p.net >= 0 ? MID - h : MID}
              width={bw}
              height={h}
              fill={netColor(p.net)}
            >
              <title>{`${p.day} · net ${p.net} · ${p.count} headline${p.count === 1 ? '' : 's'}`}</title>
            </rect>
          )
        })}
      </svg>
    </div>
  )
}
