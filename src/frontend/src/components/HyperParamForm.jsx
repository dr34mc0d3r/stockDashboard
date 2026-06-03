// Reusable numeric hyperparameter grid, shared across Lab stages.
// Driven by a `fields` spec so each stage declares its own params + defaults.
//
//   fields = [{ key, label, step, min, max, hint }]
//   values = { key: number }
//   onChange(key, number)

export default function HyperParamForm({ fields, values, onChange, disabled }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
      {fields.map((f) => (
        <label key={f.key} className="flex flex-col gap-1 text-sm text-slate-400">
          <span title={f.hint}>{f.label}</span>
          <input
            type="number"
            value={values[f.key]}
            step={f.step ?? 1}
            min={f.min}
            max={f.max}
            disabled={disabled}
            onChange={(e) =>
              onChange(f.key, e.target.value === '' ? '' : Number(e.target.value))
            }
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 tabular-nums disabled:opacity-50"
          />
          {f.hint && <span className="text-xs text-slate-600">{f.hint}</span>}
        </label>
      ))}
    </div>
  )
}
