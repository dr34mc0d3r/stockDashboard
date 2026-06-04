// The indicator toggle panel: every indicator from the backend catalog gets an
// on/off switch; toggling one on reveals its parameter inputs (pre-filled with
// the catalog defaults). Pure presentation — state lives in the page.

/**
 * @param {object} props
 * @param {{key: string, label: string, description: string, placement: string,
 *          params: {name: string, label: string, default: number, min?: number,
 *                   max?: number, type: string, step?: number}[]}[]} props.catalog
 * @param {Record<string, {enabled: boolean, params: Record<string, number>}>} props.selection
 * @param {(key: string, value: {enabled: boolean, params: Record<string, number>}) => void} props.onChange
 * @param {boolean} [props.disabled]
 */
export default function IndicatorPanel({ catalog, selection, onChange, disabled }) {
  if (!catalog.length) {
    return <p className="text-sm text-slate-500">Loading the indicator catalog…</p>
  }

  const groups = [
    { label: 'Price-pane overlays', placement: 'overlay' },
    { label: 'Own-pane indicators', placement: 'pane' },
  ]

  return (
    <div className="space-y-4">
      {groups.map((g) => (
        <div key={g.placement}>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {g.label}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {catalog
              .filter((spec) => spec.placement === g.placement)
              .map((spec) => {
                const sel = selection[spec.key] ?? { enabled: false, params: {} }
                return (
                  <div
                    key={spec.key}
                    className={`rounded-lg border p-3 ${
                      sel.enabled
                        ? 'border-sky-500/40 bg-sky-500/5'
                        : 'border-slate-800 bg-slate-950/40'
                    }`}
                  >
                    <label className="flex cursor-pointer items-start gap-2.5">
                      <input
                        type="checkbox"
                        checked={sel.enabled}
                        disabled={disabled}
                        onChange={(e) => onChange(spec.key, { ...sel, enabled: e.target.checked })}
                        className="mt-0.5 accent-sky-500"
                      />
                      <span>
                        <span className="text-sm font-medium text-slate-200">{spec.label}</span>
                        <span className="block text-xs leading-relaxed text-slate-500">
                          {spec.description}
                        </span>
                      </span>
                    </label>

                    {sel.enabled && spec.params.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2 border-t border-slate-800 pt-2">
                        {spec.params.map((p) => (
                          <label
                            key={p.name}
                            className="flex flex-col gap-0.5 text-xs text-slate-400"
                          >
                            <span>{p.label}</span>
                            <input
                              type="number"
                              value={sel.params[p.name] ?? p.default}
                              min={p.min ?? undefined}
                              max={p.max ?? undefined}
                              step={p.step ?? (p.type === 'int' ? 1 : 0.1)}
                              disabled={disabled}
                              onChange={(e) =>
                                onChange(spec.key, {
                                  ...sel,
                                  params: { ...sel.params, [p.name]: Number(e.target.value) },
                                })
                              }
                              className="w-24 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm text-slate-200"
                            />
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
          </div>
        </div>
      ))}
    </div>
  )
}
