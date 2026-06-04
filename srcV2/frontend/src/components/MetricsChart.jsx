// Per-epoch training curves, rendered as lightweight inline SVG (epochs aren't
// timestamps, so this is cleaner than the time-axis chart library). Reusable by
// any stage that emits a `progress` list of { epoch, train_loss, val_loss, val_acc }.

const W = 460
const H = 180
const PAD = { top: 12, right: 12, bottom: 24, left: 40 }

function Plot({ title, series, yMin, yMax, formatY = (v) => v.toFixed(2), refLine }) {
  const epochs = series[0]?.points.length ?? 0
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const xAt = (i) => PAD.left + (epochs <= 1 ? innerW / 2 : (i / (epochs - 1)) * innerW)
  const yAt = (v) => PAD.top + innerH - ((v - yMin) / (yMax - yMin || 1)) * innerH

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
            <text
              x={PAD.left - 6}
              y={yAt(t) + 3}
              textAnchor="end"
              className="fill-slate-600"
              fontSize="9"
            >
              {formatY(t)}
            </text>
          </g>
        ))}
        {refLine && (
          <g>
            <line
              x1={PAD.left}
              y1={yAt(refLine.value)}
              x2={W - PAD.right}
              y2={yAt(refLine.value)}
              stroke="#94a3b8"
              strokeWidth="1"
              strokeDasharray="4 3"
            />
            <text
              x={W - PAD.right - 2}
              y={yAt(refLine.value) - 4}
              textAnchor="end"
              className="fill-slate-400"
              fontSize="9"
            >
              {refLine.label}
            </text>
          </g>
        )}
        {series.map((s) => (
          <polyline
            key={s.label}
            fill="none"
            stroke={s.color}
            strokeWidth="1.5"
            points={s.points.map((p, i) => `${xAt(i)},${yAt(p)}`).join(' ')}
          />
        ))}
        <text x={W / 2} y={H - 4} textAnchor="middle" className="fill-slate-600" fontSize="9">
          epoch →
        </text>
      </svg>
    </div>
  )
}

// `accBaseline` (optional, 0..1): the majority-class rate of the validation
// split — drawn as a dashed line on the accuracy plot so "above the line"
// vs "noise" is visible at a glance. Known once the run finishes.
export default function MetricsChart({ progress, accBaseline }) {
  if (!progress?.length) return null
  const trainLoss = progress.map((p) => p.train_loss)
  const valLoss = progress.map((p) => p.val_loss)
  const valAcc = progress.map((p) => p.val_acc)

  const lossMax = Math.max(...trainLoss, ...valLoss) * 1.05
  const lossMin = Math.min(...trainLoss, ...valLoss) * 0.95

  // Learning rate: only present on runs trained with the LR scheduler.
  const hasLr = progress.some((p) => p.lr != null)
  const lr = progress.map((p) => p.lr)
  const lrHi = Math.max(...lr)
  const lrLo = Math.min(...lr)
  // If the LR never dropped it's a flat line — center it; else pad the range.
  const lrMin = lrHi === lrLo ? 0 : lrLo * 0.9
  const lrMax = lrHi === lrLo ? lrHi * 2 : lrHi * 1.1

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
      {hasLr && (
        <Plot
          title="Learning rate"
          yMin={lrMin}
          yMax={lrMax}
          formatY={(v) => v.toExponential(1)}
          series={[{ label: 'lr', color: '#fbbf24', points: lr }]}
        />
      )}
      <Plot
        title="Validation accuracy"
        yMin={0}
        yMax={1}
        formatY={(v) => `${(v * 100).toFixed(0)}%`}
        series={[{ label: 'val_acc', color: '#34d399', points: valAcc }]}
        refLine={
          accBaseline != null
            ? { value: accBaseline, label: `baseline ${(accBaseline * 100).toFixed(1)}%` }
            : undefined
        }
      />
      {/* Stage 3 multitask runs also chart the regression heads' val MAE. */}
      {progress.some((p) => p.ret_mae != null) && (
        <Plot
          title="Return head — val MAE (log-return)"
          yMin={0}
          yMax={Math.max(...progress.map((p) => p.ret_mae ?? 0)) * 1.1 || 1}
          formatY={(v) => v.toFixed(4)}
          series={[{ label: 'ret_mae', color: '#fb923c', points: progress.map((p) => p.ret_mae) }]}
        />
      )}
      {progress.some((p) => p.vol_mae != null) && (
        <Plot
          title="Volatility head — val MAE (standardized)"
          yMin={0}
          yMax={Math.max(...progress.map((p) => p.vol_mae ?? 0)) * 1.1 || 1}
          formatY={(v) => v.toFixed(3)}
          series={[{ label: 'vol_mae', color: '#a78bfa', points: progress.map((p) => p.vol_mae) }]}
        />
      )}
    </div>
  )
}
