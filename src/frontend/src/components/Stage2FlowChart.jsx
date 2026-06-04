// A flowchart of the full Stage 2 run lifecycle, built from plain divs +
// Tailwind (no chart lib needed for boxes and arrows). Each node is colour-coded
// by *where it runs* — browser, FastAPI request handler, the background training
// thread, the database row, or the artifact on disk — because the key idea of
// this stage's architecture is that those five places talk to each other only
// through HTTP calls and the `training_runs` row.

const LANES = {
  browser: {
    label: 'Browser — this page',
    box: 'border-sky-500/40 bg-sky-500/10',
    dot: 'bg-sky-400',
  },
  api: {
    label: 'FastAPI — routers/train.py',
    box: 'border-violet-500/40 bg-violet-500/10',
    dot: 'bg-violet-400',
  },
  worker: {
    label: 'Training thread — trainer.py',
    box: 'border-amber-500/40 bg-amber-500/10',
    dot: 'bg-amber-400',
  },
  db: {
    label: 'Database — training_runs row',
    box: 'border-emerald-500/40 bg-emerald-500/10',
    dot: 'bg-emerald-400',
  },
  disk: {
    label: 'Artifact on disk — registry.py',
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

// Vertical connector with an optional label (usually the HTTP call or event).
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

// Horizontal connector for the parallel band (stacks vertically on mobile).
function Across({ label }) {
  return (
    <div className="flex items-center justify-center gap-1 px-1 py-2 lg:py-0">
      <span className="hidden text-slate-600 lg:block">◀</span>
      <span className="rounded bg-slate-800/80 px-2 py-0.5 text-center font-mono text-[11px] text-slate-400">
        {label}
      </span>
      <span className="text-slate-600 lg:hidden">▲</span>
    </div>
  )
}

export default function Stage2FlowChart() {
  return (
    <div className="space-y-1">
      {/* Legend */}
      <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1.5">
        {Object.values(LANES).map((l) => (
          <span key={l.label} className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className={`h-2 w-2 rounded-full ${l.dot}`} />
            {l.label}
          </span>
        ))}
      </div>

      {/* 1 — configure */}
      <Node lane="browser" title="You configure a run" className="mx-auto max-w-xl">
        Pick a stored series (plus an optional date slice), tune the hyperparameters — or Apply an
        example preset — and hit <strong>Train model</strong>.
      </Node>

      <Down label="POST /api/v1/train/lstm" />

      {/* 2 — kickoff */}
      <Node lane="api" title="Create the run, return immediately" className="mx-auto max-w-xl">
        Checks bars exist for the slice → inserts a <code>TrainingRun</code> row (status{' '}
        <code>queued</code>) → spawns a <strong>daemon thread</strong> for the actual training →
        responds with the run right away, so the API never blocks.
      </Node>

      <Down label="run id → page state · thread starts" />

      {/* 3 — the parallel band: browser polls ⟷ DB row ⟷ worker trains */}
      <div className="rounded-xl border border-dashed border-slate-700 p-3">
        <p className="mb-3 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">
          While training — these run in parallel
        </p>
        <div className="grid items-center gap-1 lg:grid-cols-[1fr_auto_1.1fr_auto_1.2fr]">
          <Node lane="browser" title="Poll &amp; watch live">
            <code>getRun(id)</code> every 1.5&nbsp;s. TrainingProgress shows the status badge and
            epoch counter; MetricsChart redraws the loss, learning-rate and val-accuracy curves from{' '}
            <code>progress[]</code> after every epoch.
          </Node>

          <Across label="reads · GET /runs/{id}" />

          <Node lane="db" title="training_runs row">
            The <strong>single source of truth</strong>: status, data slice, hyperparams, the
            growing per-epoch <code>progress</code> JSON, and — at the end — final metrics and the
            artifact path.
          </Node>

          <Across label="commits each epoch" />

          <div className="space-y-1">
            <Node lane="worker" title="Build the dataset — datasets.py">
              Load bars → stationary return features (ln&nbsp;O/H/L/C ÷ prev close, log1p volume) →
              windows of <code>seq_len</code> bars, label = did the close rise <code>horizon</code>{' '}
              bars later → 70/15/15 split <em>by time</em> → scaler fit on training rows only
              (leakage-safe).
            </Node>
            <Down />
            <Node lane="worker" title="Train, epoch by epoch">
              Adam + BCEWithLogitsLoss → validate → append{' '}
              <code>{'{epoch, losses, val_acc, lr}'}</code> to the run row → ReduceLROnPlateau may
              cut the LR → early-stop once val loss has been stale for <code>patience</code> epochs.
            </Node>
          </div>
        </div>
      </div>

      <Down label="training finished" />

      {/* 4 — finish & save */}
      <Node lane="worker" title="Finish &amp; save" className="mx-auto max-w-xl">
        Restore the best-validation weights → score the untouched <strong>test set</strong>{' '}
        (accuracy + 2×2 confusion matrix) → <code>registry.save()</code> bundles weights,
        hyperparams, scaler stats and metrics into one{' '}
        <span className="text-rose-300">.pt artifact</span> → status <code>done</code>.
      </Node>

      <Down label='poll sees status "done" → final metrics + confusion matrix render' />

      {/* 5 — overlay request */}
      <Node
        lane="browser"
        title="You click “Show predictions on candles”"
        className="mx-auto max-w-xl"
      >
        One click, one request — nothing retrains.
      </Node>

      <Down label="GET /runs/{id}/predictions" />

      {/* 6 — out-of-sample inference */}
      <Node
        lane="api"
        title="Out-of-sample inference — predict_service.py"
        className="mx-auto max-w-xl"
      >
        Loads the saved <span className="text-rose-300">.pt bundle</span> → rebuilds the{' '}
        <em>same</em> return features with the <em>saved</em> scaler (no refit) → runs the model
        over candles clamped to the held-out test region → returns each candle's predicted direction
        plus what actually happened.
      </Node>

      <Down />

      {/* 7 — read the chart */}
      <Node lane="browser" title="Read the chart" className="mx-auto max-w-xl">
        PriceChart draws the candles with <span className="text-emerald-400">▲</span>/
        <span className="text-red-400">▼</span> markers — each arrow is the model's call for the{' '}
        <em>next</em> bar. Strictly out-of-sample, so what you see is what the test accuracy
        actually means.
      </Node>
    </div>
  )
}
