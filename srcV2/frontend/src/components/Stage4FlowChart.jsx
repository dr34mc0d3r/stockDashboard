// The Stage 4 lifecycle as a flowchart — the established visual language
// (boxes colour-coded by where they run), now with two phases: the run-once
// corpus prep, then training that reads the cached sentiment.

const LANES = {
  browser: {
    label: 'Browser — this page',
    box: 'border-sky-500/40 bg-sky-500/10',
    dot: 'bg-sky-400',
  },
  api: {
    label: 'FastAPI — routers',
    box: 'border-violet-500/40 bg-violet-500/10',
    dot: 'bg-violet-400',
  },
  worker: {
    label: 'Background thread — prep / trainer',
    box: 'border-amber-500/40 bg-amber-500/10',
    dot: 'bg-amber-400',
  },
  db: {
    label: 'Database — news_articles + feature_cache + run row',
    box: 'border-emerald-500/40 bg-emerald-500/10',
    dot: 'bg-emerald-400',
  },
  disk: {
    label: 'On disk — FinBERT model cache + .pt artifact',
    box: 'border-rose-500/40 bg-rose-500/10',
    dot: 'bg-rose-400',
  },
}

function Node({ lane, title, children, className = '' }) {
  const l = LANES[lane]
  return (
    <div className={`rounded-lg border p-3 ${l.box} ${className}`}>
      <div className="mb-1 flex items-center gap-2">
        <span className={`h-2 w-2 shrink-0 rounded-full ${l.dot}`} />
        <span className="text-sm font-semibold text-slate-100">{title}</span>
      </div>
      <div className="text-xs leading-relaxed text-slate-400">{children}</div>
    </div>
  )
}

function Down({ label }) {
  return (
    <div className="flex flex-col items-center py-0.5">
      <div className="h-3 w-px bg-slate-600" />
      {label && (
        <span className="my-0.5 rounded bg-slate-800/80 px-2 py-0.5 font-mono text-[11px] text-slate-400">
          {label}
        </span>
      )}
      <div className="h-3 w-px bg-slate-600" />
      <span className="-mt-1.5 text-[10px] leading-none text-slate-600">▼</span>
    </div>
  )
}

export default function Stage4FlowChart() {
  return (
    <div className="space-y-1">
      <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1.5">
        {Object.values(LANES).map((l) => (
          <span key={l.label} className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className={`h-2 w-2 rounded-full ${l.dot}`} />
            {l.label}
          </span>
        ))}
      </div>

      <p className="pb-1 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">
        Phase 1 — prep, run once per corpus
      </p>

      <Node lane="browser" title="Fetch & score corpus" className="mx-auto max-w-xl">
        Pick symbol + date range + a headline cap, hit the button. The page polls the prep run every
        1.5s and draws the scoring progress bar.
      </Node>

      <Down label="POST /api/v1/sentiment/prepare → queued run (stage finbert-prep)" />

      <Node lane="worker" title="Fetch headlines — news_client.py" className="mx-auto max-w-xl">
        Alpaca News API, same auth + pagination pattern as the Stage 1 bars client. Headlines only,
        capped (the "small corpus" guard) — stored in <code>news_articles</code> with the article id
        as the dedupe key.
      </Node>

      <Down />

      <Node lane="worker" title="Score with FinBERT — scorer.py" className="mx-auto max-w-xl">
        The <span className="text-rose-300">~440MB model</span> downloads once to the HF cache, then
        loads lazily per process. Batches of 16 headlines → softmax over positive/negative/neutral →
        scores written back per headline. Already-scored rows are skipped, so re-runs only pay for
        what's new.
      </Node>

      <Down />

      <Node lane="db" title="Aggregate per day → feature_cache" className="mx-auto max-w-xl">
        Per calendar day: <code>net = mean(pos) − mean(neg)</code> + headline count, cached under
        the <code>finbert_daily</code> feature set. This is the run-once payoff: training below
        never touches the model again.
      </Node>

      <Down label="Phase 2 — train (as often as you like)" />

      <Node lane="api" title="POST /api/v1/train/sentiment" className="mx-auto max-w-xl">
        The same Stage 3 machinery with <code>stage="sentiment"</code> — fails fast with a clear
        message if the slice has no cached coverage.
      </Node>

      <Down />

      <Node
        lane="worker"
        title="Features = indicators + two sentiment columns"
        className="mx-auto max-w-xl"
      >
        The indicator matrix builds exactly as Stage 3; then each bar gets{' '}
        <strong>yesterday's</strong> net sentiment + headline count (lag 1 — no same-day leakage;
        quiet days are a defined 0, never forward-filled). Two more columns, hstacked — the dataset
        builder doesn't change at all.
      </Node>

      <Down />

      <Node lane="worker" title="Train the three-headed net → save" className="mx-auto max-w-xl">
        Identical loop to Stage 3. The artifact additionally records the sentiment config so the
        overlay rebuilds the exact same columns (or its <code>n_features</code> wouldn't match).
      </Node>

      <Down label="GET /runs/{id}/predictions" />

      <Node lane="browser" title="Read the A/B" className="mx-auto max-w-xl">
        The verdict + runs table answer the only question that matters: same slice, same indicators,
        sentiment on vs off — did the direction edge move?
      </Node>
    </div>
  )
}
