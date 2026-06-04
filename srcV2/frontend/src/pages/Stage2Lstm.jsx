// Stage 2 — LSTM Direction Model.
//
// This page is a thin shell: it owns the state and the handlers, and lays out
// the numbered sections. The heavyweight pieces live next door:
//   pages/stage2/   config data + the section components
//   hooks/          inventory fetching and live run polling
//   components/     the reusable charts, tables, and panels

import { useEffect, useState } from 'react'

import { deleteRun, getRunPredictions, getRuns, trainLstm } from '../api/client.js'
import FilesPanel from '../components/FilesPanel.jsx'
import LessonPanel from '../components/LessonPanel.jsx'
import RunsTable from '../components/RunsTable.jsx'
import Stage2FlowChart from '../components/Stage2FlowChart.jsx'
import Section from '../components/ui/Section.jsx'
import { useInventory } from '../hooks/useInventory.js'
import { usePolledRun } from '../hooks/usePolledRun.js'
import ExamplesPanel from './stage2/ExamplesPanel.jsx'
import { HP_DEFAULTS, HP_FIELDS } from './stage2/hyperparams.js'
import RunResults from './stage2/RunResults.jsx'
import { STAGE_FILES } from './stage2/stageFiles.js'
import TrainForm from './stage2/TrainForm.jsx'

import whatMd from '../content/stage2.what.md?raw'
import whyMd from '../content/stage2.why.md?raw'
import understandMd from '../content/stage2.understand.md?raw'
import writeupMd from '../content/stage2.writeup.md?raw'

export default function Stage2Lstm() {
  const [source, setSource] = useState('') // "SYMBOL|timeframe"
  const [slice, setSlice] = useState({ start: '', end: '' })
  const [hp, setHp] = useState(HP_DEFAULTS)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [overlay, setOverlay] = useState(null) // { symbol, timeframe, bars, predictions }
  const [overlayBusy, setOverlayBusy] = useState(false)
  const [runs, setRuns] = useState([])

  const { inventory } = useInventory((inv) => {
    if (inv.length) setSource(`${inv[0].symbol}|${inv[0].timeframe}`)
  })
  const { run, setRun, training } = usePolledRun(setError)

  const refreshRuns = () =>
    getRuns('lstm')
      .then(setRuns)
      .catch(() => {})

  // Load the table on mount, and keep it in sync as the current run
  // starts/finishes.
  useEffect(() => {
    refreshRuns()
  }, [run?.id, run?.status])

  const setHpField = (k, v) => setHp((h) => ({ ...h, [k]: v }))
  const applyExample = (ex) => setHp({ ...HP_DEFAULTS, ...ex.params })

  // Reload a past run's results into the Run → Results section.
  const viewRun = (r) => {
    setRun(r)
    setOverlay(null)
    setError('')
  }

  const removeRun = async (r) => {
    if (
      !window.confirm(
        `Delete run #${r.id} (${r.symbol} · ${r.timeframe}) and its saved model? This cannot be undone.`,
      )
    )
      return
    setError('')
    try {
      await deleteRun(r.id)
      if (run?.id === r.id) {
        setRun(null)
        setOverlay(null)
      }
      refreshRuns()
    } catch (err) {
      setError(err.message)
    }
  }

  // Load a past run's configuration back into the form (known fields only —
  // stored hyperparams may carry extras the form/API don't take).
  const useRunParams = (r) => {
    const picked = {}
    for (const f of HP_FIELDS) {
      if (r.hyperparams?.[f.key] != null) picked[f.key] = r.hyperparams[f.key]
    }
    setHp({ ...HP_DEFAULTS, ...picked })
    const v = `${r.symbol}|${r.timeframe}`
    if (inventory.some((i) => `${i.symbol}|${i.timeframe}` === v)) setSource(v)
    setSlice({ start: (r.start || '').slice(0, 10), end: (r.end || '').slice(0, 10) })
  }

  async function loadOverlay() {
    setOverlayBusy(true)
    setError('')
    try {
      setOverlay(await getRunPredictions(run.id, 200))
    } catch (err) {
      setError(err.message)
    } finally {
      setOverlayBusy(false)
    }
  }

  async function onTrain(e) {
    e.preventDefault()
    if (!source) return
    const [symbol, timeframe] = source.split('|')
    setBusy(true)
    setError('')
    setRun(null)
    setOverlay(null)
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

      <Section n={3} title="How It All Flows">
        <p className="mb-4 text-sm text-slate-400">
          Everything below this section, as one picture: what happens in your browser, what happens
          on the server, and how the two stay in sync through a single database row while a model
          trains.
        </p>
        <Stage2FlowChart />
      </Section>

      <Section n={4} title="Examples">
        <ExamplesPanel onApply={applyExample} disabled={training} />
      </Section>

      <Section n={5} title="Parameter Config">
        <TrainForm
          inventory={inventory}
          source={source}
          onSourceChange={setSource}
          slice={slice}
          onSliceChange={setSlice}
          hp={hp}
          onHpChange={setHpField}
          onTrain={onTrain}
          onReset={() => setHp(HP_DEFAULTS)}
          busy={busy}
          training={training}
          error={error}
        />
      </Section>

      <Section n={6} title="Run → Results">
        <RunResults
          run={run}
          overlay={overlay}
          overlayBusy={overlayBusy}
          onLoadOverlay={loadOverlay}
        />
      </Section>

      <Section n={7} title="Past Runs — Compare">
        <RunsTable
          runs={runs}
          currentRunId={run?.id}
          busy={training}
          onView={viewRun}
          onUseParams={useRunParams}
          onDelete={removeRun}
          onRefresh={refreshRuns}
        />
      </Section>

      <Section n={8} title="What Am I to See and Learn">
        <LessonPanel source={understandMd} />
      </Section>

      <Section n={9} title="Full Writeup">
        <LessonPanel source={writeupMd} />
      </Section>

      <Section n={10} title="Files Behind This Stage">
        <p className="mb-4 text-sm text-slate-400">
          Every source file involved in this stage, and what each one does.
        </p>
        <FilesPanel groups={STAGE_FILES} />
      </Section>
    </div>
  )
}
