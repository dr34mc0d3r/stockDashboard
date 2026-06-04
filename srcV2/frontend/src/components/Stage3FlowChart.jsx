// The Stage 3 run lifecycle as a flowchart — same visual language as
// Stage2FlowChart (boxes colour-coded by where they run), extended with the
// indicator/feature pipeline and the three-headed model.

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
    label: 'Training thread — trainer.py',
    box: 'border-amber-500/40 bg-amber-500/10',
    dot: 'bg-amber-400',
  },
  db: {
    label: 'Database — run row + feature_cache',
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

export default function Stage3FlowChart() {
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

      <Node
        lane="browser"
        title="You pick indicators (and see them instantly)"
        className="mx-auto max-w-xl"
      >
        The toggle panel is built from <code>GET /indicators/catalog</code>, so params can never
        drift from the backend. Every change calls <code>POST /indicators</code> and redraws the
        chart preview — the exact series the model will train on.
      </Node>

      <Down label="Train model → POST /api/v1/train/multitask" />

      <Node lane="api" title="Create the run, return immediately" className="mx-auto max-w-xl">
        Same bookkeeping as Stage 2 (<code>run_service</code>): a queued <code>TrainingRun</code>{' '}
        row — now with the indicator config inside its hyperparams — and a daemon thread for the
        work.
      </Node>

      <Down label="thread starts · page begins polling every 1.5s" />

      <Node
        lane="worker"
        title="Build the features — feature_pipeline.py"
        className="mx-auto max-w-xl"
      >
        Runs the <em>same</em> indicator functions over the slice and flattens every line into one
        matrix. The matrix is cached in <code>feature_cache</code> keyed by a hash of the config —
        an identical re-run reads instead of recomputing (the pattern Stages 4–5 will lean on hard).
      </Node>

      <Down />

      <Node
        lane="worker"
        title="Build the dataset — build_multitask_dataset"
        className="mx-auto max-w-xl"
      >
        Return features + indicator columns, <strong>warm-up rows trimmed</strong> (no NaNs in),
        70/15/15 by time, scaler fit on train rows only. Each window gets{' '}
        <strong>three labels</strong>: direction, log return over the horizon, and realized
        volatility over <code>vol_window</code> bars (regression targets standardized by train
        stats).
      </Node>

      <Down />

      <Node
        lane="worker"
        title="Train the three-headed net — epoch by epoch"
        className="mx-auto max-w-xl"
      >
        One shared LSTM trunk → three heads. Loss = <code>w_dir·BCE + w_ret·MSE + w_vol·MSE</code>.
        Per-epoch progress (total loss, direction accuracy, return/vol MAE) commits to the run row;
        ReduceLROnPlateau + early stopping watch the <em>total</em> validation loss.
      </Node>

      <Down label="per-epoch metrics → run row → live charts above" />

      <Node lane="worker" title="Finish & save" className="mx-auto max-w-xl">
        Best weights restored → held-out test scoring <em>per head</em> →{' '}
        <code>registry.save()</code> bundles weights + hyperparams + scaler +{' '}
        <span className="text-rose-300">target-scaling stats</span> into one .pt artifact → status{' '}
        <code>done</code>.
      </Node>

      <Down label="GET /runs/{id}/predictions (multitask branch)" />

      <Node
        lane="api"
        title="Out-of-sample overlay — predict_overlay_multitask"
        className="mx-auto max-w-xl"
      >
        Rebuilds the same features from the run's stored indicator config (saved scaler, no refit),
        clamps to the held-out test region accounting for indicator warm-up, and returns each
        candle's direction call <em>plus</em> the predicted return and volatility.
      </Node>

      <Down />

      <Node lane="browser" title="Read the chart" className="mx-auto max-w-xl">
        Arrows = direction head; the number beside each arrow = the return head's estimate. The
        volatility estimate rides along in the data for later stages to use.
      </Node>
    </div>
  )
}
