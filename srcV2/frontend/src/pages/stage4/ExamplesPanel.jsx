// Stage 4 preset cards: indicator chips + a sentiment badge + param chips.

import { EXAMPLES } from './examples.js'
import { CHIP_KEYS, HP_DEFAULTS } from './hyperparams.js'

export default function ExamplesPanel({ onApply, disabled }) {
  return (
    <>
      <p className="mb-4 text-sm text-slate-400">
        Presets built around one discipline: change a single variable, then compare in the runs
        table. <strong>Apply</strong> loads hyperparameters, indicators AND the sentiment toggle.
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
              <div className="mt-auto space-y-1.5">
                <div className="flex flex-wrap gap-1.5">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-semibold ${
                      ex.sentiment.enabled
                        ? 'bg-emerald-500/15 text-emerald-300'
                        : 'bg-slate-800 text-slate-500'
                    }`}
                  >
                    {ex.sentiment.enabled ? '📰 sentiment ON' : 'sentiment off'}
                  </span>
                  {ex.indicators.map((item) => (
                    <span
                      key={item.name}
                      className="rounded bg-sky-500/15 px-2 py-0.5 text-xs text-sky-300"
                    >
                      {item.name}
                    </span>
                  ))}
                </div>
                <div className="flex flex-wrap gap-1.5">
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
            </div>
          )
        })}
      </div>
    </>
  )
}
