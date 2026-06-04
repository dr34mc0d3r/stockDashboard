// The "run-once" corpus prep: fetch headlines from Alpaca News and score them
// with FinBERT in a background job, with live phase progress. Owns its own
// small form + poll loop; tells the page when a prep finishes so it can
// refresh the browser/timeline.

import { useEffect, useRef, useState } from 'react'

import { prepareSentiment } from '../../api/client.js'
import ErrorNote from '../../components/ui/ErrorNote.jsx'
import Field from '../../components/ui/Field.jsx'
import { usePolledRun } from '../../hooks/usePolledRun.js'

export default function PrepPanel({ defaultSymbol, onDone }) {
  const [form, setForm] = useState({
    symbol: defaultSymbol || 'TSLA',
    start: '2025-05-01',
    end: '2025-07-31',
    max_articles: 300,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const { run, setRun, training: active } = usePolledRun(setError)

  // Follow the inventory's default symbol until the user edits the field.
  const touched = useRef(false)
  useEffect(() => {
    if (!touched.current && defaultSymbol) {
      setForm((f) => ({ ...f, symbol: defaultSymbol.split('|')[0] }))
    }
  }, [defaultSymbol])

  // Tell the page when a prep run lands so it can refresh corpus views.
  const notified = useRef(0)
  useEffect(() => {
    if (run && run.status === 'done' && notified.current !== run.id) {
      notified.current = run.id
      onDone?.(run)
    }
  }, [run, onDone])

  const set = (k) => (e) => {
    touched.current = true
    setForm({ ...form, [k]: e.target.value })
  }

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const started = await prepareSentiment({
        symbol: form.symbol,
        start: form.start,
        end: form.end,
        max_articles: Number(form.max_articles),
      })
      setRun(started)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const last = run?.progress?.[run.progress.length - 1]
  const m = run?.metrics

  return (
    <div className="space-y-4">
      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-4">
        <Field label="Symbol">
          <input
            value={form.symbol}
            onChange={set('symbol')}
            className="w-28 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 uppercase"
          />
        </Field>
        <Field label="From">
          <input
            type="date"
            value={form.start}
            onChange={set('start')}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
          />
        </Field>
        <Field label="To">
          <input
            type="date"
            value={form.end}
            onChange={set('end')}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
          />
        </Field>
        <Field label="Max headlines">
          <input
            type="number"
            min={10}
            max={1000}
            value={form.max_articles}
            onChange={set('max_articles')}
            className="w-28 rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
          />
        </Field>
        <button
          type="submit"
          disabled={busy || active}
          className="rounded-md bg-sky-500 px-5 py-2 font-semibold text-white hover:bg-sky-400 disabled:opacity-50"
        >
          {active ? 'Working…' : busy ? 'Starting…' : 'Fetch & score corpus'}
        </button>
      </form>

      <p className="text-xs text-slate-500">
        Run once per symbol/range. Fetching is fast; FinBERT scoring takes ~0.1–0.3s per headline on
        this CPU (the first ever run also downloads the model, ~440MB). Already scored headlines are
        skipped, so re-running is cheap.
      </p>

      <ErrorNote error={error} className="" />

      {run && active && last && (
        <div className="space-y-1.5 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
          <p className="text-sm text-amber-200">
            {last.phase === 'scoring'
              ? `Scoring with FinBERT… ${last.scored} / ${last.total}`
              : `${last.phase}…`}
          </p>
          {last.phase === 'scoring' && last.total > 0 && (
            <div className="h-1.5 overflow-hidden rounded bg-slate-800">
              <div
                className="h-full bg-amber-400 transition-all"
                style={{ width: `${(100 * last.scored) / last.total}%` }}
              />
            </div>
          )}
        </div>
      )}

      {run && run.status === 'done' && m && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm text-emerald-200">
          <span>
            <strong>{m.n_articles}</strong> headlines scored
          </span>
          <span>
            <strong>{m.n_days_covered}</strong> days covered ({m.first_day} → {m.last_day})
          </span>
          <span>
            mean net <strong>{m.mean_net}</strong>
          </span>
          <span>
            <strong>{Math.round((m.pct_positive_days ?? 0) * 100)}%</strong> positive days
          </span>
        </div>
      )}
      {run && run.status === 'error' && (
        <ErrorNote error={run.detail?.split('\n')[0] || 'Prep failed.'} className="" />
      )}
    </div>
  )
}
