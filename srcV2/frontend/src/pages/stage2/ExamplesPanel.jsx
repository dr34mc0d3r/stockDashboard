// The Examples section: preset cards that load instructive hyperparameter
// combinations into the form with one click.

import { EXAMPLES } from './examples.js'
import { CHIP_KEYS, HP_DEFAULTS } from './hyperparams.js'

/**
 * @param {object} props
 * @param {(example: (typeof EXAMPLES)[number]) => void} props.onApply
 * @param {boolean} props.disabled - True while a run is training.
 */
export default function ExamplesPanel({ onApply, disabled }) {
  return (
    <>
      <p className="mb-4 text-sm text-slate-400">
        Presets chosen to surface a specific result. Click <strong>Apply</strong> to load one into
        the form below, pick the suggested data source, then train.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        {EXAMPLES.map((ex) => {
          const merged = { ...HP_DEFAULTS, ...ex.params }
          return (
            <div
              key={ex.name}
              className="flex flex-col rounded-lg border border-slate-800 bg-slate-950/40 p-4"
            >
              <div className="mb-1 flex items-center justify-between gap-2">
                <h4 className="font-semibold text-slate-100">{ex.name}</h4>
                <button
                  type="button"
                  onClick={() => onApply(ex)}
                  disabled={disabled}
                  className="shrink-0 rounded-md bg-sky-500/90 px-3 py-1 text-xs font-semibold text-white hover:bg-sky-400 disabled:opacity-50"
                >
                  Apply
                </button>
              </div>
              <p className="mb-2 text-sm leading-relaxed text-slate-400">{ex.expect}</p>
              <p className="mb-3 text-xs text-slate-500">
                Suggested data: <span className="text-slate-400">{ex.data}</span>
              </p>
              <div className="mt-auto flex flex-wrap gap-1.5">
                {CHIP_KEYS.map((k) => (
                  <span
                    key={k}
                    className="rounded bg-slate-800 px-2 py-0.5 text-xs tabular-nums text-slate-300"
                  >
                    {k}={merged[k]}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}
