import { useEffect, useState } from 'react'
import LessonPanel from '../components/LessonPanel.jsx'
import HyperParamForm from '../components/HyperParamForm.jsx'
import MetricsChart from '../components/MetricsChart.jsx'
import TrainingProgress from '../components/TrainingProgress.jsx'
import { getInventory, trainLstm, getRun } from '../api/client.js'

import whatMd from '../content/stage2.what.md?raw'
import whyMd from '../content/stage2.why.md?raw'
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

const ACTIVE = (s) => s === 'queued' || s === 'running'

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

      <Section n={3} title="Parameter Config">
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

      <Section n={4} title="Run → Results">
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

      <Section n={5} title="Full Writeup">
        <LessonPanel source={writeupMd} />
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
