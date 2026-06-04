// The scored corpus, headline by headline — the Stage 4 teaching centerpiece:
// you can read exactly what FinBERT read and see how it scored each line.

import { Td, Th } from '../../components/ui/Table.jsx'

function ScoreBar({ pos, neg, neutral }) {
  if (pos == null) return <span className="text-xs text-slate-600">unscored</span>
  const pct = (v) => `${Math.round(v * 100)}%`
  return (
    <div className="w-36">
      <div className="flex h-2 overflow-hidden rounded bg-slate-800">
        <div className="bg-emerald-500" style={{ width: pct(pos) }} />
        <div className="bg-slate-500" style={{ width: pct(neutral) }} />
        <div className="bg-red-500" style={{ width: pct(neg) }} />
      </div>
      <div className="mt-0.5 flex justify-between text-[10px] tabular-nums text-slate-500">
        <span className="text-emerald-400">{pct(pos)}</span>
        <span>{pct(neutral)}</span>
        <span className="text-red-400">{pct(neg)}</span>
      </div>
    </div>
  )
}

export default function HeadlineBrowser({ headlines }) {
  if (!headlines.length) {
    return (
      <p className="text-sm text-slate-500">
        No scored headlines yet — run the corpus prep above first.
      </p>
    )
  }

  return (
    <div className="max-h-96 overflow-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-slate-900 text-slate-400">
          <tr>
            <Th>When</Th>
            <Th>Headline</Th>
            <Th>
              <span className="text-emerald-400">pos</span> /{' '}
              <span className="text-slate-400">neu</span> /{' '}
              <span className="text-red-400">neg</span>
            </Th>
          </tr>
        </thead>
        <tbody>
          {headlines.map((h, i) => (
            <tr key={i} className="border-t border-slate-800/60 hover:bg-slate-900/50">
              <Td className="whitespace-nowrap text-xs text-slate-500">
                {h.ts.replace('T', ' ').slice(0, 16)}
              </Td>
              <Td className="text-slate-300">
                {h.url ? (
                  <a href={h.url} target="_blank" rel="noreferrer" className="hover:text-sky-300">
                    {h.headline}
                  </a>
                ) : (
                  h.headline
                )}
                <span className="ml-2 text-xs text-slate-600">{h.source}</span>
              </Td>
              <Td>
                <ScoreBar pos={h.pos} neg={h.neg} neutral={h.neutral} />
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
