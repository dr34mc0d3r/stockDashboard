// Per-epoch training curves, rendered as lightweight inline SVG (epochs aren't
// timestamps, so this is cleaner than the time-axis chart library). Reusable by
// any stage that emits a `progress` list of { epoch, train_loss, val_loss, val_acc }.

const W = 460
const H = 180
const PAD = { top: 12, right: 12, bottom: 24, left: 40 }

function Plot({ title, series, yMin, yMax, formatY = (v) => v.toFixed(2) }) {
  const epochs = series[0]?.points.length ?? 0
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const xAt = (i) =>
    PAD.left + (epochs <= 1 ? innerW / 2 : (i / (epochs - 1)) * innerW)
  const yAt = (v) =>
    PAD.top + innerH - ((v - yMin) / (yMax - yMin || 1)) * innerH

  const ticks = [yMin, (yMin + yMax) / 2, yMax]

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-300">{title}</span>
        <div className="flex gap-3">
          {series.map((s) => (
            <span key={s.label} className="flex items-center gap-1 text-xs text-slate-400">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={PAD.left} y1={yAt(t)} x2={W - PAD.right} y2={yAt(t)} stroke="#1e293b" />
            <text x={PAD.left - 6} y={yAt(t) + 3} textAnchor="end" className="fill-slate-600" fontSize="9">
              {formatY(t)}
            </text>
          </g>
        ))}
        {series.map((s) => (
          <polyline
            key={s.label}
            fill="none"
            stroke={s.color}
            strokeWidth="1.5"
            points={s.points.map((p, i) => `${xAt(i)},${yAt(p)}`).join(' ')}
          />
        ))}
        <text x={(W) / 2} y={H - 4} textAnchor="middle" className="fill-slate-600" fontSize="9">
          epoch →
        </text>
      </svg>
    </div>
  )
}

export default function MetricsChart({ progress }) {
  if (!progress?.length) return null
  const trainLoss = progress.map((p) => p.train_loss)
  const valLoss = progress.map((p) => p.val_loss)
  const valAcc = progress.map((p) => p.val_acc)

  const lossMax = Math.max(...trainLoss, ...valLoss) * 1.05
  const lossMin = Math.min(...trainLoss, ...valLoss) * 0.95

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Plot
        title="Loss"
        yMin={lossMin}
        yMax={lossMax}
        formatY={(v) => v.toFixed(3)}
        series={[
          { label: 'train', color: '#38bdf8', points: trainLoss },
          { label: 'val', color: '#f472b6', points: valLoss },
        ]}
      />
      <Plot
        title="Validation accuracy"
        yMin={0}
        yMax={1}
        formatY={(v) => `${(v * 100).toFixed(0)}%`}
        series={[{ label: 'val_acc', color: '#34d399', points: valAcc }]}
      />
    </div>
  )
}
