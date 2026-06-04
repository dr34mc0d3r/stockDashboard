// The Stage 4 Parameter Config: Stage 3's form (source/slice + indicators +
// hyperparams) plus the one new control — the news-sentiment toggle, with a
// coverage hint so you can't accidentally train on an uncovered slice.

import HyperParamForm from '../../components/HyperParamForm.jsx'
import ErrorNote from '../../components/ui/ErrorNote.jsx'
import Field from '../../components/ui/Field.jsx'
import IndicatorPanel from '../stage3/IndicatorPanel.jsx'
import { HP_FIELDS } from './hyperparams.js'
import { sliceCoverage } from './sentiment.js'

export default function TrainForm({
  inventory,
  source,
  onSourceChange,
  slice,
  onSliceChange,
  catalog,
  selection,
  onIndicatorChange,
  sentimentOn,
  onSentimentChange,
  coverage,
  hp,
  onHpChange,
  onTrain,
  onReset,
  busy,
  training,
  error,
}) {
  if (inventory.length === 0) {
    return (
      <>
        <p className="text-sm text-slate-500">
          No stored data yet — download some on <span className="text-sky-400">Stage 1</span> first.
        </p>
        <ErrorNote error={error} />
      </>
    )
  }

  const cov = sliceCoverage(coverage, slice.start || null, slice.end || null)
  const blocked = sentimentOn && cov.daysWithNews === 0

  return (
    <>
      <form onSubmit={onTrain} className="space-y-5">
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Data source">
            <select
              value={source}
              onChange={(e) => onSourceChange(e.target.value)}
              disabled={training}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 disabled:opacity-50"
            >
              {inventory.map((r) => {
                const v = `${r.symbol}|${r.timeframe}`
                return (
                  <option key={v} value={v}>
                    {r.symbol} · {r.timeframe} · {r.bar_count.toLocaleString()} bars
                  </option>
                )
              })}
            </select>
          </Field>
          <Field label="Slice start (optional)">
            <input
              type="date"
              value={slice.start}
              onChange={(e) => onSliceChange({ ...slice, start: e.target.value })}
              disabled={training}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 disabled:opacity-50"
            />
          </Field>
          <Field label="Slice end (optional)">
            <input
              type="date"
              value={slice.end}
              onChange={(e) => onSliceChange({ ...slice, end: e.target.value })}
              disabled={training}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 disabled:opacity-50"
            />
          </Field>
        </div>

        {/* The one new control of Stage 4. */}
        <div
          className={`rounded-lg border p-3 ${
            sentimentOn
              ? 'border-emerald-500/40 bg-emerald-500/5'
              : 'border-slate-800 bg-slate-950/40'
          }`}
        >
          <label className="flex cursor-pointer items-start gap-2.5">
            <input
              type="checkbox"
              checked={sentimentOn}
              disabled={training}
              onChange={(e) => onSentimentChange(e.target.checked)}
              className="mt-0.5 accent-emerald-500"
            />
            <span>
              <span className="text-sm font-medium text-slate-200">
                Add news sentiment features
              </span>
              <span className="block text-xs leading-relaxed text-slate-500">
                Two extra columns from the cached FinBERT corpus: yesterday's net sentiment and
                headline count (lag 1 day — bars never see same-day afternoon news; the lesson
                explains why).
              </span>
              {sentimentOn && (
                <span
                  className={`mt-1 block text-xs ${
                    cov.daysWithNews === 0 ? 'text-red-300' : 'text-emerald-300'
                  }`}
                >
                  {cov.daysWithNews === 0
                    ? 'No news coverage for this symbol/slice — run the corpus prep above first.'
                    : `${cov.daysWithNews} covered news days in this slice (~${Math.round(cov.covered * 100)}% of calendar days).`}
                </span>
              )}
            </span>
          </label>
        </div>

        <div>
          <h4 className="mb-2 text-sm font-semibold text-slate-200">Indicator features</h4>
          <IndicatorPanel
            catalog={catalog}
            selection={selection}
            onChange={onIndicatorChange}
            disabled={training}
          />
        </div>

        <HyperParamForm fields={HP_FIELDS} values={hp} onChange={onHpChange} disabled={training} />

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={busy || training || blocked}
            className="rounded-md bg-sky-500 px-5 py-2 font-semibold text-white hover:bg-sky-400 disabled:opacity-50"
          >
            {training ? 'Training…' : busy ? 'Starting…' : 'Train model'}
          </button>
          <button
            type="button"
            onClick={onReset}
            disabled={training}
            className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
          >
            Reset defaults
          </button>
          {blocked && (
            <span className="text-xs text-red-300">
              Train is disabled until the slice has news coverage.
            </span>
          )}
        </div>
      </form>

      <ErrorNote error={error} />
    </>
  )
}
