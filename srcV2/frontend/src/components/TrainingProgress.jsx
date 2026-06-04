// Live training status for one run: a status badge, epoch counter, final
// test metrics, and a 2x2 confusion matrix. Reusable across stages.

import { STATUS_STYLES } from '../lib/statusStyles.js'

export default function TrainingProgress({ run }) {
  if (!run) return null
  const { status, progress = [], metrics, hyperparams, detail } = run
  const last = progress[progress.length - 1]
  const totalEpochs = hyperparams?.epochs ?? '?'

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLES[status] ?? ''}`}
        >
          {status}
        </span>
        <span className="text-slate-400">run #{run.id}</span>
        {(status === 'running' || status === 'queued') && (
          <span className="text-slate-400">
            epoch {last?.epoch ?? 0} / {totalEpochs}
            {last && (
              <>
                {' · '}val_loss {last.val_loss} · val_acc {(last.val_acc * 100).toFixed(1)}%
              </>
            )}
          </span>
        )}
      </div>

      {status === 'error' && (
        <pre className="overflow-auto rounded-md bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {detail?.split('\n')[0] || 'Training failed.'}
        </pre>
      )}

      {status === 'done' && metrics && (
        <div className="flex flex-wrap gap-6">
          <div className="space-y-1 text-sm">
            <Stat
              label="Test accuracy"
              value={`${(metrics.test_acc * 100).toFixed(2)}%`}
              highlight
            />
            <Stat label="Test loss" value={metrics.test_loss} />
            <Stat label="Best val loss" value={metrics.best_val_loss} />
            <Stat label="Epochs run" value={metrics.epochs_run} />
            <Stat
              label="Up-label balance (tr/va/te)"
              value={`${metrics.class_balance.train} / ${metrics.class_balance.val} / ${metrics.class_balance.test}`}
            />
          </div>
          <ConfusionMatrix c={metrics.confusion} />
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, highlight }) {
  return (
    <div className="flex justify-between gap-6">
      <span className="text-slate-500">{label}</span>
      <span
        className={`tabular-nums ${highlight ? 'font-semibold text-emerald-300' : 'text-slate-200'}`}
      >
        {value}
      </span>
    </div>
  )
}

function ConfusionMatrix({ c }) {
  if (!c) return null
  // Rows = actual, cols = predicted. tp/tn correct (diagonal), fp/fn wrong.
  const cell = (v, ok) =>
    `rounded-md px-4 py-3 text-center tabular-nums ${ok ? 'bg-emerald-500/15 text-emerald-200' : 'bg-red-500/10 text-red-200'}`
  return (
    <div className="text-xs">
      <div className="mb-1 text-slate-400">Confusion matrix (test)</div>
      <div className="grid grid-cols-[auto_1fr_1fr] gap-1">
        <div />
        <div className="text-center text-slate-500">pred ↑</div>
        <div className="text-center text-slate-500">pred ↓</div>
        <div className="flex items-center text-slate-500">actual ↑</div>
        <div className={cell(c.tp, true)}>{c.tp}</div>
        <div className={cell(c.fn, false)}>{c.fn}</div>
        <div className="flex items-center text-slate-500">actual ↓</div>
        <div className={cell(c.fp, false)}>{c.fp}</div>
        <div className={cell(c.tn, true)}>{c.tn}</div>
      </div>
    </div>
  )
}
