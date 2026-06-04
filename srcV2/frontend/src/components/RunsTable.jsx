// Compare past training runs side by side: key hyperparams, test accuracy,
// and — the column that matters — the edge over each run's own majority-class
// baseline. Turns tuning into an experiment loop: View reloads a run's results
// below, Use params loads its configuration back into the form.

import { baselineEdge } from '../lib/runStats.js'
import { STATUS_STYLES } from '../lib/statusStyles.js'

// First line of a failed run's error detail (the human-readable part —
// the traceback below it is for the View panel).
const errorLine = (r) => (r.detail || '').split('\n')[0].trim()

function fmtWhen(iso) {
  const d = new Date(iso)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function EdgeCell({ metrics }) {
  const eb = baselineEdge(metrics)
  if (!eb) return <span className="text-slate-600">—</span>
  const txt = `${eb.edge >= 0 ? '+' : ''}${(eb.edge * 100).toFixed(1)}pt`
  const cls =
    eb.edge <= 0
      ? 'text-red-300'
      : eb.significant
        ? 'font-semibold text-emerald-300'
        : 'text-slate-400'
  return (
    <span className={`tabular-nums ${cls}`} title={`baseline ${(eb.base * 100).toFixed(1)}%`}>
      {txt}
      {eb.edge > 0 && !eb.significant && <span className="text-slate-600"> ≈noise</span>}
    </span>
  )
}

export default function RunsTable({
  runs,
  currentRunId,
  busy,
  onView,
  onUseParams,
  onDelete,
  onRefresh,
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">
          Every run for this stage, newest first. <strong className="text-slate-300">Edge</strong>{' '}
          is direction test accuracy minus that run's own always-guess-the-majority baseline — the
          only fair way to compare runs trained on different slices.
        </p>
        <button
          type="button"
          onClick={onRefresh}
          className="shrink-0 rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800"
        >
          Refresh
        </button>
      </div>

      {runs.length === 0 ? (
        <p className="text-sm text-slate-500">No runs yet — train a model above.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-1.5 py-2">#</th>
                <th className="px-1.5 py-2">When</th>
                <th className="px-1.5 py-2">Data</th>
                <th className="px-1.5 py-2">Params</th>
                <th className="px-1.5 py-2 text-right">Epochs</th>
                <th className="px-1.5 py-2 text-right">Test acc</th>
                <th className="px-1.5 py-2 text-right">Edge</th>
                <th className="px-1.5 py-2">Status</th>
                <th className="px-1.5 py-2" />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const hp = r.hyperparams || {}
                const slice =
                  r.start || r.end
                    ? `${(r.start || '…').slice(0, 10)} → ${(r.end || '…').slice(0, 10)}`
                    : null
                return (
                  <tr
                    key={r.id}
                    className={`border-b border-slate-800/60 ${
                      r.id === currentRunId ? 'bg-sky-500/5' : ''
                    }`}
                  >
                    <td className="px-1.5 py-2 tabular-nums text-slate-500">{r.id}</td>
                    <td className="whitespace-nowrap px-1.5 py-2 text-slate-400">
                      {fmtWhen(r.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-1.5 py-2 text-slate-300">
                      {r.symbol} · {r.timeframe}
                      {slice && <span className="block text-xs text-slate-500">{slice}</span>}
                    </td>
                    <td className="whitespace-nowrap px-1.5 py-2 font-mono text-xs text-slate-400">
                      {hp.seq_len}w · h{hp.hidden}×{hp.layers} · do{hp.dropout} · lr{hp.lr}
                    </td>
                    <td className="px-1.5 py-2 text-right tabular-nums text-slate-400">
                      {r.metrics?.epochs_run ?? '—'}/{hp.epochs ?? '?'}
                    </td>
                    <td className="px-1.5 py-2 text-right tabular-nums text-slate-200">
                      {r.metrics?.test_acc != null
                        ? `${(r.metrics.test_acc * 100).toFixed(1)}%`
                        : '—'}
                    </td>
                    <td className="px-1.5 py-2 text-right">
                      <EdgeCell metrics={r.metrics} />
                    </td>
                    <td className="px-1.5 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLES[r.status] ?? ''}`}
                        title={r.status === 'error' ? errorLine(r) : undefined}
                      >
                        {r.status}
                      </span>
                      {/* Why it failed, in-place — hover for the full line. */}
                      {r.status === 'error' && errorLine(r) && (
                        <span
                          className="mt-1 block max-w-44 truncate text-[10px] leading-tight text-red-300/80"
                          title={errorLine(r)}
                        >
                          {errorLine(r)}
                        </span>
                      )}
                    </td>
                    <td className="px-1.5 py-2">
                      <div className="flex flex-col items-stretch gap-1">
                        <button
                          type="button"
                          onClick={() => onView(r)}
                          className="rounded-md border border-slate-700 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-800"
                        >
                          View
                        </button>
                        <button
                          type="button"
                          onClick={() => onUseParams(r)}
                          disabled={busy}
                          className="whitespace-nowrap rounded-md border border-slate-700 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50"
                        >
                          Use params
                        </button>
                        {onDelete && (
                          <button
                            type="button"
                            onClick={() => onDelete(r)}
                            // Active runs can't be deleted (the worker is still
                            // writing to the row) — the backend refuses too.
                            disabled={r.status === 'queued' || r.status === 'running'}
                            className="rounded-md bg-red-500/15 px-2 py-0.5 text-xs text-red-300 hover:bg-red-500/25 disabled:opacity-40"
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
