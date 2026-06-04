// Stage 4 — FinBERT News Sentiment.
//
// Thin shell on the 10-section template. New here: the run-once corpus prep
// (PrepPanel → headline browser → coverage timeline) feeding two cached
// sentiment columns into the Stage 3 training machinery via one toggle.

import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  deleteRun,
  getCatalog,
  getCoverage,
  getHeadlines,
  getRunPredictions,
  getRuns,
  trainSentiment,
} from '../api/client.js'
import FilesPanel from '../components/FilesPanel.jsx'
import LessonPanel from '../components/LessonPanel.jsx'
import RunsTable from '../components/RunsTable.jsx'
import Stage4FlowChart from '../components/Stage4FlowChart.jsx'
import Section from '../components/ui/Section.jsx'
import { useInventory } from '../hooks/useInventory.js'
import { usePolledRun } from '../hooks/usePolledRun.js'
import { defaultSelection } from './stage3/indicators.js'
import RunResults from './stage3/RunResults.jsx'
import CoverageTimeline from './stage4/CoverageTimeline.jsx'
import ExamplesPanel from './stage4/ExamplesPanel.jsx'
import HeadlineBrowser from './stage4/HeadlineBrowser.jsx'
import { HP_DEFAULTS, HP_FIELDS } from './stage4/hyperparams.js'
import PrepPanel from './stage4/PrepPanel.jsx'
import { STAGE_FILES } from './stage4/stageFiles.js'
import TrainForm from './stage4/TrainForm.jsx'

import whatMd from '../content/stage4.what.md?raw'
import whyMd from '../content/stage4.why.md?raw'
import understandMd from '../content/stage4.understand.md?raw'
import writeupMd from '../content/stage4.writeup.md?raw'

export default function Stage4Sentiment() {
  const [source, setSource] = useState('') // "SYMBOL|timeframe"
  const [slice, setSlice] = useState({ start: '', end: '' })
  const [catalog, setCatalog] = useState([])
  const [selection, setSelection] = useState({})
  const [sentimentOn, setSentimentOn] = useState(true)
  const [hp, setHp] = useState(HP_DEFAULTS)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [overlay, setOverlay] = useState(null)
  const [overlayBusy, setOverlayBusy] = useState(false)
  const [runs, setRuns] = useState([])
  const [headlines, setHeadlines] = useState([])
  const [coverage, setCoverage] = useState(null)

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

  const symbol = source.split('|')[0] || ''

  // Corpus views follow the selected symbol; refreshed after each prep run.
  const refreshCorpus = useCallback((sym) => {
    if (!sym) return
    getHeadlines(sym, 200)
      .then(setHeadlines)
      .catch(() => setHeadlines([]))
    getCoverage(sym)
      .then(setCoverage)
      .catch(() => setCoverage(null))
  }, [])
  useEffect(() => {
    refreshCorpus(symbol)
  }, [symbol, refreshCorpus])

  const refreshRuns = () =>
    getRuns('sentiment')
      .then(setRuns)
      .catch(() => {})
  useEffect(() => {
    refreshRuns()
  }, [run?.id, run?.status])

  // --- handlers -----------------------------------------------------------
  const setHpField = (k, v) => setHp((h) => ({ ...h, [k]: v }))
  const setIndicator = (key, value) => setSelection((s) => ({ ...s, [key]: value }))

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
    setSentimentOn(ex.sentiment.enabled)
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

  const useRunParams = (r) => {
    const picked = {}
    for (const f of HP_FIELDS) {
      if (r.hyperparams?.[f.key] != null) picked[f.key] = r.hyperparams[f.key]
    }
    setHp({ ...HP_DEFAULTS, ...picked })
    setSelection(selectionFromItems(r.hyperparams?.indicators ?? []))
    setSentimentOn(Boolean(r.hyperparams?.sentiment?.enabled))
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

  const requestItems = useMemo(
    () =>
      Object.entries(selection)
        .filter(([, v]) => v.enabled)
        .map(([name, v]) => ({ name, params: v.params })),
    [selection],
  )

  async function onTrain(e) {
    e.preventDefault()
    if (!source) return
    const [sym, timeframe] = source.split('|')
    setBusy(true)
    setError('')
    setRun(null)
    setOverlay(null)
    try {
      const started = await trainSentiment({
        symbol: sym,
        timeframe,
        start: slice.start || null,
        end: slice.end || null,
        hyperparams: {
          ...hp,
          indicators: requestItems,
          sentiment: { enabled: sentimentOn, lag_days: 1 },
        },
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
        <p className="text-sm font-medium text-sky-400">Stage 4</p>
        <h2 className="text-2xl font-bold text-white">FinBERT News Sentiment</h2>
      </header>

      <Section n={1} title="What We're Doing">
        <LessonPanel source={whatMd} />
      </Section>

      <Section n={2} title="Why We're Doing It">
        <LessonPanel source={whyMd} />
      </Section>

      <Section n={3} title="How It All Flows">
        <p className="mb-4 text-sm text-slate-400">
          Two phases: the run-once prep (fetch headlines → FinBERT → daily cache) and the training
          loop that reads the cache — the model itself never runs at training time.
        </p>
        <Stage4FlowChart />
      </Section>

      <Section n={4} title="Examples">
        <ExamplesPanel onApply={applyExample} disabled={training} />
      </Section>

      <Section n={5} title="Prepare the Corpus (run once)">
        <PrepPanel defaultSymbol={source} onDone={() => refreshCorpus(symbol)} />

        {headlines.length > 0 && (
          <div className="mt-5 space-y-4 border-t border-slate-800 pt-4">
            <div>
              <h4 className="mb-2 text-sm font-semibold text-slate-200">
                The corpus, headline by headline
              </h4>
              <HeadlineBrowser headlines={headlines} />
            </div>
            <div>
              <h4 className="mb-2 text-sm font-semibold text-slate-200">Daily net sentiment</h4>
              <CoverageTimeline coverage={coverage} />
            </div>
          </div>
        )}
      </Section>

      <Section n={6} title="Parameter Config">
        <TrainForm
          inventory={inventory}
          source={source}
          onSourceChange={setSource}
          slice={slice}
          onSliceChange={setSlice}
          catalog={catalog}
          selection={selection}
          onIndicatorChange={setIndicator}
          sentimentOn={sentimentOn}
          onSentimentChange={setSentimentOn}
          coverage={coverage}
          hp={hp}
          onHpChange={setHpField}
          onTrain={onTrain}
          onReset={() => setHp(HP_DEFAULTS)}
          busy={busy}
          training={training}
          error={error}
        />
      </Section>

      <Section n={7} title="Run → Results">
        <RunResults
          run={run}
          overlay={overlay}
          overlayBusy={overlayBusy}
          onLoadOverlay={loadOverlay}
        />
      </Section>

      <Section n={8} title="Past Runs — Compare">
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

      <Section n={9} title="What Am I to See and Learn">
        <LessonPanel source={understandMd} />
      </Section>

      <Section n={10} title="Full Writeup">
        <LessonPanel source={writeupMd} />
      </Section>

      <Section n={11} title="Files Behind This Stage">
        <p className="mb-4 text-sm text-slate-400">
          Every source file involved in this stage, and what each one does.
        </p>
        <FilesPanel groups={STAGE_FILES} />
      </Section>
    </div>
  )
}
