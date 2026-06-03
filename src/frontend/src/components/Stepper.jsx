import { NavLink } from 'react-router-dom'

// The ordered Market ML Lab path. Stage 1 is live; later stages unlock as we
// build them.
export const STAGES = [
  { n: 1, title: 'Data Acquisition', path: '/stage/1', ready: true },
  { n: 2, title: 'LSTM Direction', path: '/stage/2', ready: true },
  { n: 3, title: 'Multi-Task Model', ready: false },
  { n: 4, title: 'FinBERT Sentiment', ready: false },
  { n: 5, title: 'GDELT News', ready: false },
  { n: 6, title: 'Transformer Core', ready: false },
  { n: 7, title: 'Regime Detection', ready: false },
  { n: 8, title: 'Unified Engine', ready: false },
]

export default function Stepper() {
  return (
    <nav className="flex flex-col gap-1">
      {STAGES.map((s) => {
        const base =
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition'
        if (!s.ready) {
          return (
            <div
              key={s.n}
              className={`${base} cursor-not-allowed text-slate-600`}
              title="Coming soon"
            >
              <Badge n={s.n} muted />
              <span>{s.title}</span>
            </div>
          )
        }
        return (
          <NavLink
            key={s.n}
            to={s.path}
            className={({ isActive }) =>
              `${base} ${
                isActive
                  ? 'bg-sky-500/15 text-sky-300'
                  : 'text-slate-300 hover:bg-slate-800'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Badge n={s.n} active={isActive} />
                <span>{s.title}</span>
              </>
            )}
          </NavLink>
        )
      })}
    </nav>
  )
}

function Badge({ n, active, muted }) {
  const cls = muted
    ? 'bg-slate-800 text-slate-600'
    : active
      ? 'bg-sky-500 text-white'
      : 'bg-slate-700 text-slate-200'
  return (
    <span
      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${cls}`}
    >
      {n}
    </span>
  )
}
