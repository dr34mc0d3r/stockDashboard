import { useEffect, useState } from 'react'
import LessonPanel from '../components/LessonPanel.jsx'
import HyperParamForm from '../components/HyperParamForm.jsx'
import MetricsChart from '../components/MetricsChart.jsx'
import TrainingProgress from '../components/TrainingProgress.jsx'
import FilesPanel from '../components/FilesPanel.jsx'
import { getInventory, trainLstm, getRun } from '../api/client.js'

import whatMd from '../content/stage2.what.md?raw'
import whyMd from '../content/stage2.why.md?raw'
import understandMd from '../content/stage2.understand.md?raw'
import writeupMd from '../content/stage2.writeup.md?raw'

// Matches the backend LstmHyperParams defaults (and PLAN.md).
const HP_FIELDS = [
  { key: 'seq_len', label: 'Sequence length', min: 5, max: 240, hint: 'bars per window' },
  { key: 'horizon', label: 'Horizon', min: 1, max: 20, hint: 'bars ahead to predict' },
  { key: 'hidden', label: 'Hidden units', min: 8, max: 128 },
  { key: 'layers', label: 'LSTM layers', min: 1, max: 3 },
  { key: 'dropout', label: 'Dropout', step: 0.05, min: 0, max: 0.8 },
  { key: 'lr', label: 'Learning rate', step: 0.0001, min: 0.0001, max: 1 },
  { key: 'batch', label: 'Batch size', min: 8, max: 512 },
  { key: 'epochs', label: 'Max epochs', min: 1, max: 200 },
  { key: 'patience', label: 'Early-stop patience', min: 1, max: 50 },
  { key: 'lr_factor', label: 'LR drop factor', step: 0.05, min: 0.1, max: 0.9, hint: 'LR ×= this on plateau' },
  { key: 'lr_patience', label: 'LR drop patience', min: 1, max: 20, hint: 'epochs before LR drop' },
]
const HP_DEFAULTS = {
  seq_len: 60, horizon: 1, hidden: 64, layers: 2, dropout: 0.2,
  lr: 0.001, batch: 64, epochs: 30, patience: 5, lr_factor: 0.5, lr_patience: 2,
}

// Preset configurations, each chosen to surface a specific, instructive result.
// `params` are overrides on top of HP_DEFAULTS; `data` is the suggested source.
const EXAMPLES = [
  {
    name: 'Quick smoke test',
    data: 'a small series — e.g. AAPL 1m',
    expect: 'Finishes in seconds. Confirms the whole pipeline runs end-to-end: training, live metrics, confusion matrix, and a saved model.',
    params: { seq_len: 30, hidden: 16, layers: 1, dropout: 0.1, epochs: 8, patience: 8 },
  },
  {
    name: 'Watch it learn (LR steps down)',
    data: 'any stored series',
    expect: 'High starting LR + an impatient scheduler: training loss falls and the Learning-rate chart visibly steps down (0.01 → 0.005 → 0.0025 …) each time val loss plateaus.',
    params: { seq_len: 30, hidden: 32, layers: 2, lr: 0.01, epochs: 20, patience: 8, lr_patience: 1 },
  },
  {
    name: 'Make it overfit',
    data: 'a SMALL slice — AAPL 1m, or a ~1-month date range',
    expect: 'A big model on little data: training loss keeps diving while validation loss flattens then turns up — the textbook overfitting gap. Early stopping restores the best pre-overfit weights.',
    params: { seq_len: 60, hidden: 128, layers: 3, dropout: 0.0, batch: 32, epochs: 50, patience: 12, lr_patience: 6 },
  },
  {
    name: 'The honest baseline',
    data: 'a full year — e.g. TSLA 1m, 2025-01-01 → 2026-01-01',
    expect: 'Test accuracy hovers around 50%. Next-bar direction on raw 1-minute OHLCV is nearly random — the expected result, and exactly why Stage 3 adds real features.',
    params: {},  // pure defaults
  },
]

// Headline params shown as chips on each example card.
const CHIP_KEYS = ['seq_len', 'hidden', 'layers', 'dropout', 'lr', 'epochs', 'lr_patience']

const ACTIVE = (s) => s === 'queued' || s === 'running'

// The source files behind this stage, with what each one does.
const STAGE_FILES = [
  {
    label: 'Backend — model & training',
    files: [
      { path: 'src/backend/ml/models/lstm.py', desc: 'Defines LSTMClassifier — an nn.LSTM whose final-timestep hidden state passes through a dropout + linear head to a single logit (probability of "up") — plus build_model(), which constructs it from a hyperparameter dict.' },
      { path: 'src/backend/services/datasets.py', desc: 'Turns raw OHLCV into supervised windows. Derives stationary return features (ln(O/H/L/C / prev_close) + log1p(volume)) so price-level scale never crushes the signal, labels each window from the real close price, splits 70/15/15 by time, and fits the scaler on training rows only (leakage-safe).' },
      { path: 'src/backend/services/training/trainer.py', desc: 'The background training loop, run in a daemon thread so the API stays responsive. Trains with Adam + BCEWithLogitsLoss, a ReduceLROnPlateau scheduler, and early stopping; writes per-epoch metrics (train/val loss, val accuracy, learning rate) to the run row for live polling; then scores the held-out test set and saves the model artifact.' },
      { path: 'src/backend/ml/registry.py', desc: 'Saves/loads a trained model as one self-contained .pt bundle = weights + hyperparams + scaler stats + metrics, under src/backend/artifacts/ (gitignored). Lets a run be reloaded later with identical preprocessing.' },
      { path: 'src/backend/routers/train.py', desc: 'Defines POST /api/v1/train/lstm (creates a queued TrainingRun and spawns the worker thread), GET /api/v1/runs (list past runs), and GET /api/v1/runs/{id} (poll one run\'s live progress).' },
    ],
  },
  {
    label: 'Backend — shared infrastructure',
    files: [
      { path: 'src/backend/models.py', desc: 'Adds TrainingRun (stage, hyperparams/metrics/progress JSON, status, artifact path) — the row the UI polls during training — and FeatureCache (used from Stage 3 on).' },
      { path: 'src/backend/schemas.py', desc: 'Adds LstmHyperParams (defaults and bounds for seq_len, horizon, hidden, layers, dropout, lr, batch, epochs, patience, lr_factor, lr_patience), TrainLstmRequest, and TrainingRunOut.' },
      { path: 'src/backend/main.py · db.py · config.py', desc: 'The shared FastAPI app, SQLAlchemy engine/session, and config (see Stage 1 for detail). The training router is registered in main.py; the trainer opens its own DB session via SessionLocal.' },
    ],
  },
  {
    label: 'Frontend',
    files: [
      { path: 'src/frontend/src/pages/Stage2Lstm.jsx', desc: 'This page. An inventory-backed data-source selector + optional date slice, the hyperparameter form, the Train button, and a Run→Results section that polls the run every 1.5s while it trains.' },
      { path: 'src/frontend/src/components/HyperParamForm.jsx', desc: 'Reusable numeric hyperparameter grid driven by a field spec — used here for the LSTM params, and by later stages for theirs.' },
      { path: 'src/frontend/src/components/MetricsChart.jsx', desc: 'Reusable inline-SVG charts that update live: Loss (train vs val), Learning rate, and Validation accuracy across epochs.' },
      { path: 'src/frontend/src/components/TrainingProgress.jsx', desc: 'Reusable status panel: status badge, live epoch counter, final test metrics, and the 2×2 confusion matrix.' },
      { path: 'src/frontend/src/api/client.js', desc: 'Adds the training calls: trainLstm (start a run), getRun (poll one), and getRuns (list).' },
      { path: 'src/frontend/src/components/FilesPanel.jsx · LessonPanel.jsx · Stepper.jsx · App.jsx · main.jsx', desc: 'Shared shell + this files section, the markdown lesson renderer, the stage stepper, the app layout, and the router (see Stage 1).' },
    ],
  },
  {
    label: 'Lesson content',
    files: [
      { path: 'src/frontend/src/content/stage2.what.md', desc: 'The "What we\'re doing" lesson text shown in section 1.' },
      { path: 'src/frontend/src/content/stage2.why.md', desc: 'The "Why we\'re doing it" lesson text shown in section 2.' },
      { path: 'src/frontend/src/content/stage2.understand.md', desc: 'The "What am I to see and learn" lesson shown in section 6 — maps the loss/accuracy/confusion outputs back to reading a candlestick chart.' },
      { path: 'src/frontend/src/content/stage2.writeup.md', desc: 'The full deep-dive writeup shown in section 7 (windows, why an LSTM, return features, the time-ordered split, reading the loss/LR/accuracy charts).' },
    ],
  },
]

export default function Stage2Lstm() {
  const [inventory, setInventory] = useState([])
  const [source, setSource] = useState('') // "SYMBOL|timeframe"
  const [slice, setSlice] = useState({ start: '', end: '' })
  const [hp, setHp] = useState(HP_DEFAULTS)
  const [run, setRun] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getInventory()
      .then((inv) => {
        setInventory(inv)
        if (inv.length) setSource(`${inv[0].symbol}|${inv[0].timeframe}`)
      })
      .catch(() => {})
  }, [])

  // Poll the active run until it finishes.
  useEffect(() => {
    if (!run || !ACTIVE(run.status)) return
    const t = setTimeout(() => {
      getRun(run.id).then(setRun).catch((e) => setError(e.message))
    }, 1500)
    return () => clearTimeout(t)
  }, [run])

  const setHpField = (k, v) => setHp((h) => ({ ...h, [k]: v }))
  const applyExample = (ex) => setHp({ ...HP_DEFAULTS, ...ex.params })

  async function onTrain(e) {
    e.preventDefault()
    if (!source) return
    const [symbol, timeframe] = source.split('|')
    setBusy(true)
    setError('')
    setRun(null)
    try {
      const started = await trainLstm({
        symbol,
        timeframe,
        start: slice.start || null,
        end: slice.end || null,
        hyperparams: hp,
      })
      setRun(started)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const training = run && ACTIVE(run.status)

  return (
    <div className="space-y-8">
      <header>
        <p className="text-sm font-medium text-sky-400">Stage 2</p>
        <h2 className="text-2xl font-bold text-white">LSTM Direction Model</h2>
      </header>

      <Section n={1} title="What We're Doing">
        <LessonPanel source={whatMd} />
      </Section>

      <Section n={2} title="Why We're Doing It">
        <LessonPanel source={whyMd} />
      </Section>

      <Section n={3} title="Examples">
        <p className="mb-4 text-sm text-slate-400">
          Presets chosen to surface a specific result. Click <strong>Apply</strong> to load one
          into the form below, pick the suggested data source, then train.
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
                    onClick={() => applyExample(ex)}
                    disabled={training}
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
      </Section>

      <Section n={4} title="Parameter Config">
        {inventory.length === 0 ? (
          <p className="text-sm text-slate-500">
            No stored data yet — download some on{' '}
            <span className="text-sky-400">Stage 1</span> first.
          </p>
        ) : (
          <form onSubmit={onTrain} className="space-y-5">
            <div className="flex flex-wrap items-end gap-4">
              <Field label="Data source">
                <select
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  disabled={training}
                  className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 disabled:opacity-50"
                >
                  {inventory.map((r) => {
                    const v = `${r.symbol}|${r.timeframe}`
                    return (
                      <option key={v} value={v}>
                        {r.symbol} · {r.timeframe} · {r.bar_count.toLocaleString()} bars
                      </option>
                    )
                  })}
                </select>
              </Field>
              <Field label="Slice start (optional)">
                <input
                  type="date"
                  value={slice.start}
                  onChange={(e) => setSlice({ ...slice, start: e.target.value })}
                  disabled={training}
                  className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 disabled:opacity-50"
                />
              </Field>
              <Field label="Slice end (optional)">
                <input
                  type="date"
                  value={slice.end}
                  onChange={(e) => setSlice({ ...slice, end: e.target.value })}
                  disabled={training}
                  className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 disabled:opacity-50"
                />
              </Field>
            </div>

            <HyperParamForm
              fields={HP_FIELDS}
              values={hp}
              onChange={setHpField}
              disabled={training}
            />

            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={busy || training}
                className="rounded-md bg-sky-500 px-5 py-2 font-semibold text-white hover:bg-sky-400 disabled:opacity-50"
              >
                {training ? 'Training…' : busy ? 'Starting…' : 'Train model'}
              </button>
              <button
                type="button"
                onClick={() => setHp(HP_DEFAULTS)}
                disabled={training}
                className="rounded-md border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
              >
                Reset defaults
              </button>
            </div>
          </form>
        )}

        {error && (
          <p className="mt-3 rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}
      </Section>

      <Section n={5} title="Run → Results">
        {!run ? (
          <p className="text-sm text-slate-500">
            Configure parameters above and train a model to see results.
          </p>
        ) : (
          <div className="space-y-5">
            <TrainingProgress run={run} />
            <MetricsChart progress={run.progress} />
          </div>
        )}
      </Section>

      <Section n={6} title="What Am I to See and Learn">
        <LessonPanel source={understandMd} />
      </Section>

      <Section n={7} title="Full Writeup">
        <LessonPanel source={writeupMd} />
      </Section>

      <Section n={8} title="Files Behind This Stage">
        <p className="mb-4 text-sm text-slate-400">
          Every source file involved in this stage, and what each one does.
        </p>
        <FilesPanel groups={STAGE_FILES} />
      </Section>
    </div>
  )
}

function Section({ n, title, children }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/30 p-6">
      <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-500/20 text-sm text-sky-300">
          {n}
        </span>
        {title}
      </h3>
      {children}
    </section>
  )
}

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-slate-400">
      <span>{label}</span>
      {children}
    </label>
  )
}
