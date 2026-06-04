// The Stage 3 Parameter Config section: data source + slice, the indicator
// toggle panel WITH a live chart preview of exactly what the model will see,
// the hyperparameter grid, and the Train button. Pure presentation — state
// lives in the page.

import PriceChart from '../../charts/PriceChart.jsx'
import HyperParamForm from '../../components/HyperParamForm.jsx'
import ErrorNote from '../../components/ui/ErrorNote.jsx'
import Field from '../../components/ui/Field.jsx'
import IndicatorPanel from './IndicatorPanel.jsx'
import { HP_FIELDS } from './hyperparams.js'

export default function TrainForm({
  inventory,
  source,
  onSourceChange,
  slice,
  onSliceChange,
  catalog,
  selection,
  onIndicatorChange,
  preview,
  previewBusy,
  chartProps,
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

        <div>
          <h4 className="mb-2 text-sm font-semibold text-slate-200">
            Indicator features — what the model will see
          </h4>
          <IndicatorPanel
            catalog={catalog}
            selection={selection}
            onChange={onIndicatorChange}
            disabled={training}
          />
        </div>

        {preview && preview.bars.length > 0 && (
          <div className="space-y-1">
            {previewBusy && <p className="text-xs text-slate-500">Updating…</p>}
            <PriceChart
              bars={preview.bars}
              symbol={preview.symbol}
              timeframe={preview.timeframe}
              overlays={chartProps.overlays}
              panes={chartProps.panes}
            />
            <p className="text-xs text-slate-500">
              Live preview of the most recent {preview.bar_count.toLocaleString()} stored bars with
              your selection. Early candles without indicator values are the warm-up window — the
              training pipeline trims those rows.
            </p>
          </div>
        )}

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
