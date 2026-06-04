// Plain-English diagnosis of a finished run: is the accuracy real, did it
// overfit, was there enough data — each finding ends in a concrete knob to
// turn. The math lives in lib/runStats.js; this just renders it.

import { analyzeRun } from '../lib/runStats.js'

const TONE = {
  good: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200',
  mixed: 'border-amber-500/40 bg-amber-500/10 text-amber-200',
  bad: 'border-red-500/40 bg-red-500/10 text-red-200',
}

const LEVEL = {
  good: { icon: '✓', cls: 'text-emerald-400' },
  warn: { icon: '!', cls: 'text-amber-400' },
  bad: { icon: '✗', cls: 'text-red-400' },
  info: { icon: 'i', cls: 'text-sky-400' },
}

export default function RunVerdict({ run }) {
  const verdict = analyzeRun(run)
  if (!verdict) return null

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-semibold text-slate-200">Run verdict — can you use this?</h4>
      <p className={`rounded-md border px-3 py-2 text-sm leading-relaxed ${TONE[verdict.tone]}`}>
        {verdict.headline}
      </p>
      <ul className="space-y-2">
        {verdict.findings.map((f) => {
          const l = LEVEL[f.level]
          return (
            <li key={f.title} className="flex gap-2.5 text-sm">
              <span
                className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-current text-[10px] font-bold leading-none ${l.cls}`}
              >
                {l.icon}
              </span>
              <span>
                <span className="font-medium text-slate-200">{f.title}.</span>{' '}
                <span className="text-slate-400">{f.text}</span>
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
