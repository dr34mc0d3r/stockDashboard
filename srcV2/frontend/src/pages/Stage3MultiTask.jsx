// Stage 3 — Multi-Task Model (indicators as features; three prediction heads).
//
// Thin shell, same pattern as Stage 2: it owns the state and handlers and lays
// out the numbered sections. The heavyweight pieces live next door:
//   pages/stage3/   config data + the section components + indicator helpers
//   hooks/          inventory fetching and live run polling
//   components/     the reusable charts, tables, and panels

import { useEffect, useMemo, useState } from 'react'

import {
  computeIndicators,
  deleteRun,
  getCatalog,
  getRunPredictions,
  getRuns,
  trainMultiTask,
} from '../api/client.js'
import FilesPanel from '../components/FilesPanel.jsx'
import LessonPanel from '../components/LessonPanel.jsx'
import RunsTable from '../components/RunsTable.jsx'
import Stage3FlowChart from '../components/Stage3FlowChart.jsx'
import Section from '../components/ui/Section.jsx'
import { useInventory } from '../hooks/useInventory.js'
import { usePolledRun } from '../hooks/usePolledRun.js'
import ExamplesPanel from './stage3/ExamplesPanel.jsx'
import { HP_DEFAULTS, HP_FIELDS } from './stage3/hyperparams.js'
import { defaultSelection, selectionToRequest, toChartProps } from './stage3/indicators.js'
import RunResults from './stage3/RunResults.jsx'
import { STAGE_FILES } from './stage3/stageFiles.js'
import TrainForm from './stage3/TrainForm.jsx'

import whatMd from '../content/stage3.what.md?raw'
import whyMd from '../content/stage3.why.md?raw'
import understandMd from '../content/stage3.understand.md?raw'
import writeupMd from '../content/stage3.writeup.md?raw'

const PREVIEW_BARS = 300

export default function Stage3MultiTask() {
  const [source, setSource] = useState('') // "SYMBOL|timeframe"
  const [slice, setSlice] = useState({ start: '', end: '' })
  const [catalog, setCatalog] = useState([])
  const [selection, setSelection] = useState({})
  const [hp, setHp] = useState(HP_DEFAULTS)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [overlay, setOverlay] = useState(null)
  const [overlayBusy, setOverlayBusy] = useState(false)
  const [runs, setRuns] = useState([])
  // The preview remembers which request produced it; "busy" is derived by
  // comparing that key to the current request (no setState-in-effect needed).
  const [preview, setPreview] = useState(null)

  const { inventory } = useInventory((inv) => {
    if (inv.length) setSource(`${inv[0].symbol}|${inv[0].timeframe}`)
  })
  const { run, setRun, training } = usePolledRun(setError)

  useEffect(() => {
    getCatalog()
      .then((c) => {
        setCatalog(c.indicators)
        setSelection(defaultSelection(c.indicators))
      })
      .catch((e) => setError(e.message))
  }, [])

  const refreshRuns = () =>
    getRuns('multitask')
      .then(setRuns)
      .catch(() => {})
  useEffect(() => {
    refreshRuns()
  }, [run?.id, run?.status])

  // --- indicator selection → live preview -------------------------------
  const requestItems = useMemo(() => selectionToRequest(selection), [selection])
  const requestKey = useMemo(
    () => `${source}|${JSON.stringify(requestItems)}`,
    [source, requestItems],
  )
  useEffect(() => {
    if (!source || !requestItems.length) return
    const [symbol, timeframe] = source.split('|')
    let cancelled = false
    computeIndicators({ symbol, timeframe, limit: PREVIEW_BARS, indicators: requestItems })
      .then((res) => {
        if (!cancelled) setPreview({ ...res, key: requestKey })
      })
      .catch((e) => {
        if (!cancelled) setError(e.message)
      })
    return () => {
      cancelled = true
    }
  }, [source, requestItems, requestKey])

  const previewBusy = requestItems.length > 0 && preview?.key !== requestKey
  const chartProps = useMemo(
    () => (preview ? toChartProps(preview.indicators) : { overlays: [], panes: [] }),
    [preview],
  )
  const visiblePreview = requestItems.length > 0 ? preview : null

  // --- handlers -----------------------------------------------------------
  const setHpField = (k, v) => setHp((h) => ({ ...h, [k]: v }))
  const setIndicator = (key, value) => setSelection((s) => ({ ...s, [key]: value }))

  // A preset fully defines the run: hyperparams AND the indicator selection
  // (everything else resets to catalog defaults, off).
  const selectionFromItems = (items) => {
    const next = defaultSelection(catalog)
    for (const item of items) {
      next[item.name] = { enabled: true, params: { ...next[item.name]?.params, ...item.params } }
    }
    return next
  }

  const applyExample = (ex) => {
    setHp({ ...HP_DEFAULTS, ...ex.params })
    setSelection(selectionFromItems(ex.indicators))
  }

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

  // Load a past run's config back into the form — hyperparams AND indicators.
  const useRunParams = (r) => {
    const picked = {}
    for (const f of HP_FIELDS) {
      if (r.hyperparams?.[f.key] != null) picked[f.key] = r.hyperparams[f.key]
    }
    setHp({ ...HP_DEFAULTS, ...picked })
    setSelection(selectionFromItems(r.hyperparams?.indicators ?? []))
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
      const started = await trainMultiTask({
        symbol,
        timeframe,
        start: slice.start || null,
        end: slice.end || null,
        hyperparams: { ...hp, indicators: requestItems },
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
        <p className="text-sm font-medium text-sky-400">Stage 3</p>
        <h2 className="text-2xl font-bold text-white">Multi-Task Model</h2>
      </header>

      <Section n={1} title="What We're Doing">
        <LessonPanel source={whatMd} />
      </Section>

      <Section n={2} title="Why We're Doing It">
        <LessonPanel source={whyMd} />
      </Section>

      <Section n={3} title="How It All Flows">
        <p className="mb-4 text-sm text-slate-400">
          The Stage 2 lifecycle, extended: indicator selection feeds a live preview AND the training
          request, the worker builds (and caches) the feature matrix before training, and the model
          now returns three answers per candle.
        </p>
        <Stage3FlowChart />
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
          catalog={catalog}
          selection={selection}
          onIndicatorChange={setIndicator}
          preview={visiblePreview}
          previewBusy={previewBusy}
          chartProps={chartProps}
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
