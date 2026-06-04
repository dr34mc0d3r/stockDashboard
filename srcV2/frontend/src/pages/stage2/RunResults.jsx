// The Run → Results section: live training progress and charts while a run is
// active; the verdict and the on-candle prediction overlay once it finishes.

import PriceChart from '../../charts/PriceChart.jsx'
import MetricsChart from '../../components/MetricsChart.jsx'
import RunVerdict from '../../components/RunVerdict.jsx'
import TrainingProgress from '../../components/TrainingProgress.jsx'
import { majorityBaseline } from '../../lib/runStats.js'

/**
 * @param {object} props
 * @param {import('../../lib/types.js').Run | null} props.run
 * @param {{symbol: string, timeframe: string, out_of_sample: boolean,
 *          bars: import('../../lib/types.js').Bar[],
 *          predictions: {ts: string, pred: number}[]} | null} props.overlay
 * @param {boolean} props.overlayBusy
 * @param {() => void} props.onLoadOverlay
 */
export default function RunResults({ run, overlay, overlayBusy, onLoadOverlay }) {
  if (!run) {
    return (
      <p className="text-sm text-slate-500">
        Configure parameters above and train a model to see results.
      </p>
    )
  }

  return (
    <div className="space-y-5">
      <TrainingProgress run={run} />
      <MetricsChart
        progress={run.progress}
        accBaseline={majorityBaseline(run.metrics?.class_balance?.val)}
      />

      {run.status === 'done' && (
        <div className="border-t border-slate-800 pt-4">
          <RunVerdict run={run} />
        </div>
      )}

      {run.status === 'done' && (
        <div className="space-y-3 border-t border-slate-800 pt-4">
          <div className="flex flex-wrap items-center gap-3">
            <h4 className="text-sm font-semibold text-slate-200">Predictions on the chart</h4>
            <button
              type="button"
              onClick={onLoadOverlay}
              disabled={overlayBusy}
              className="rounded-md bg-sky-500 px-4 py-1.5 text-sm font-semibold text-white hover:bg-sky-400 disabled:opacity-50"
            >
              {overlayBusy ? 'Loading…' : overlay ? 'Refresh' : 'Show predictions on candles'}
            </button>
            <span className="text-xs text-slate-500">
              <span className="text-emerald-400">▲ green</span> = predicted up ·{' '}
              <span className="text-red-400">▼ red</span> = predicted down ·{' '}
              {overlay
                ? overlay.out_of_sample
                  ? 'held-out test region'
                  : 'recent bars'
                : 'most recent candles'}
            </span>
          </div>
          {overlay && overlay.bars.length > 0 && (
            <>
              <PriceChart
                bars={overlay.bars}
                symbol={overlay.symbol}
                timeframe={overlay.timeframe}
                markers={overlay.predictions.map((p) => ({
                  ts: p.ts,
                  position: p.pred === 1 ? 'belowBar' : 'aboveBar',
                  color: p.pred === 1 ? '#22c55e' : '#ef4444',
                  shape: p.pred === 1 ? 'arrowUp' : 'arrowDown',
                }))}
              />
              <p className="text-xs text-slate-500">
                Each arrow is the model's call at that candle for the next one. Compare the arrow to
                the candle that follows — over many candles you'll feel why ~50% accuracy looks like
                noise.{' '}
                {overlay.out_of_sample
                  ? 'These are the held-out test candles the model never trained on.'
                  : 'This run predates slice tracking, so these are recent bars and may overlap training data — illustrative only.'}
              </p>
            </>
          )}
          {overlay && overlay.bars.length === 0 && (
            <p className="text-sm text-slate-500">
              Not enough stored bars for this symbol to build a prediction window.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
