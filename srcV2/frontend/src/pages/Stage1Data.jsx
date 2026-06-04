// Stage 1 — Data Acquisition.
//
// Owns the download form, the stored-data inventory (with per-row Chart and
// Delete actions), and the price chart. Built from the shared ui/ primitives;
// the file inventory for the Files section lives in pages/stage1/stageFiles.js.

import { useState } from 'react'

import { deleteBars, getBars, ingest } from '../api/client.js'
import PriceChart from '../charts/PriceChart.jsx'
import FilesPanel from '../components/FilesPanel.jsx'
import LessonPanel from '../components/LessonPanel.jsx'
import ErrorNote from '../components/ui/ErrorNote.jsx'
import Field from '../components/ui/Field.jsx'
import Section from '../components/ui/Section.jsx'
import { Td, Th } from '../components/ui/Table.jsx'
import { useInventory } from '../hooks/useInventory.js'
import { STAGE_FILES } from './stage1/stageFiles.js'

import whatMd from '../content/stage1.what.md?raw'
import whyMd from '../content/stage1.why.md?raw'
import writeupMd from '../content/stage1.writeup.md?raw'

const TIMEFRAMES = ['1m', '5m', '1h', '1d']

export default function Stage1Data() {
  const [form, setForm] = useState({
    symbol: 'AAPL',
    start: '2025-05-01',
    end: '2025-05-02',
    timeframe: '1m',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [chart, setChart] = useState(null) // { symbol, timeframe, bars }
  const [chartLoading, setChartLoading] = useState(false)

  const { inventory, refreshInventory } = useInventory()

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function loadChart(symbol, timeframe) {
    setChartLoading(true)
    try {
      const bars = await getBars(symbol, timeframe)
      setChart({ symbol, timeframe, bars })
    } catch (e) {
      setError(e.message)
    } finally {
      setChartLoading(false)
    }
  }

  async function onDelete(symbol, timeframe) {
    if (!window.confirm(`Delete all stored ${symbol} ${timeframe} bars? This cannot be undone.`))
      return
    setError('')
    try {
      await deleteBars(symbol, timeframe)
      // Clear the chart if it was showing the deleted series.
      if (chart && chart.symbol === symbol && chart.timeframe === timeframe) setChart(null)
      await refreshInventory()
    } catch (e) {
      setError(e.message)
    }
  }

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const res = await ingest(form)
      setResult(res)
      await refreshInventory()
      await loadChart(res.symbol, res.timeframe)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="text-sm font-medium text-sky-400">Stage 1</p>
        <h2 className="text-2xl font-bold text-white">Data Acquisition</h2>
      </header>

      <Section n={1} title="What We're Doing">
        <LessonPanel source={whatMd} />
      </Section>

      <Section n={2} title="Why We're Doing It">
        <LessonPanel source={whyMd} />
      </Section>

      <Section n={3} title="Parameter Config">
        <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-4">
          <Field label="Symbol">
            <input
              value={form.symbol}
              onChange={set('symbol')}
              className="w-28 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 uppercase"
            />
          </Field>
          <Field label="Start">
            <input
              type="date"
              value={form.start}
              onChange={set('start')}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
            />
          </Field>
          <Field label="End">
            <input
              type="date"
              value={form.end}
              onChange={set('end')}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
            />
          </Field>
          <Field label="Timeframe">
            <select
              value={form.timeframe}
              onChange={set('timeframe')}
              className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
            >
              {TIMEFRAMES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-sky-500 px-5 py-2 font-semibold text-white hover:bg-sky-400 disabled:opacity-50"
          >
            {busy ? 'Downloading…' : 'Download'}
          </button>
        </form>

        <ErrorNote error={error} />
        {result && (
          <p className="mt-3 rounded-md bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
            Stored {result.bars_written.toLocaleString()} {result.symbol} {result.timeframe} bars
            {result.first_ts && (
              <>
                {' '}
                ({result.first_ts.replace('T', ' ')} → {result.last_ts.replace('T', ' ')})
              </>
            )}
            .
          </p>
        )}
      </Section>

      <Section n={4} title="Run → Results">
        <h3 className="mb-2 text-sm font-semibold text-slate-300">Stored data inventory</h3>
        {inventory.length === 0 ? (
          <p className="text-sm text-slate-500">Nothing stored yet — download something above.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900 text-slate-400">
                <tr>
                  <Th>Symbol</Th>
                  <Th>Timeframe</Th>
                  <Th className="text-right">Bars</Th>
                  <Th>Earliest</Th>
                  <Th>Latest</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {inventory.map((row) => (
                  <tr
                    key={`${row.symbol}-${row.timeframe}`}
                    className="border-t border-slate-800 hover:bg-slate-900/50"
                  >
                    <Td className="font-semibold text-slate-100">{row.symbol}</Td>
                    <Td>{row.timeframe}</Td>
                    <Td className="text-right tabular-nums">{row.bar_count.toLocaleString()}</Td>
                    <Td className="text-slate-400">{row.earliest.replace('T', ' ')}</Td>
                    <Td className="text-slate-400">{row.latest.replace('T', ' ')}</Td>
                    <Td className="text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => loadChart(row.symbol, row.timeframe)}
                          className="rounded bg-slate-700 px-3 py-1 text-xs hover:bg-slate-600"
                        >
                          Chart
                        </button>
                        <button
                          onClick={() => onDelete(row.symbol, row.timeframe)}
                          className="rounded bg-red-500/20 px-3 py-1 text-xs text-red-300 hover:bg-red-500/30"
                        >
                          Delete
                        </button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4">
          {chartLoading && <p className="text-sm text-slate-500">Loading chart…</p>}
          {chart && !chartLoading && (
            <PriceChart bars={chart.bars} symbol={chart.symbol} timeframe={chart.timeframe} />
          )}
        </div>
      </Section>

      <Section n={5} title="Full Writeup">
        <LessonPanel source={writeupMd} />
      </Section>

      <Section n={6} title="Files Behind This Stage">
        <p className="mb-4 text-sm text-slate-400">
          Every source file involved in this stage, and what each one does.
        </p>
        <FilesPanel groups={STAGE_FILES} />
      </Section>
    </div>
  )
}
