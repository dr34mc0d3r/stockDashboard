// The Parameter Config section: data source + optional date slice, the
// hyperparameter grid, and the Train/Reset buttons. Pure presentation —
// all state lives in the page.

import HyperParamForm from '../../components/HyperParamForm.jsx'
import ErrorNote from '../../components/ui/ErrorNote.jsx'
import Field from '../../components/ui/Field.jsx'
import { HP_FIELDS } from './hyperparams.js'

/**
 * @param {object} props
 * @param {import('../../lib/types.js').InventoryItem[]} props.inventory
 * @param {string} props.source - Selected "SYMBOL|timeframe".
 * @param {(v: string) => void} props.onSourceChange
 * @param {{start: string, end: string}} props.slice
 * @param {(v: {start: string, end: string}) => void} props.onSliceChange
 * @param {Record<string, number>} props.hp - Current hyperparameter values.
 * @param {(key: string, value: number) => void} props.onHpChange
 * @param {(e: Event) => void} props.onTrain - Form submit handler.
 * @param {() => void} props.onReset - Restore default hyperparameters.
 * @param {boolean} props.busy - True while the start request is in flight.
 * @param {boolean} props.training - True while a run is queued/running.
 * @param {string} props.error
 */
export default function TrainForm({
  inventory,
  source,
  onSourceChange,
  slice,
  onSliceChange,
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

        <HyperParamForm fields={HP_FIELDS} values={hp} onChange={onHpChange} disabled={training} />

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={busy || training}
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
        </div>
      </form>

      <ErrorNote error={error} />
    </>
  )
}
