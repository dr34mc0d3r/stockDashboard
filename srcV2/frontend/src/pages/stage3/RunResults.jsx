// The Stage 3 Run → Results section: live per-head training progress, the
// direction-head verdict, and the prediction overlay — arrows like Stage 2,
// plus each arrow's predicted return as marker text.

import PriceChart from '../../charts/PriceChart.jsx'
import MetricsChart from '../../components/MetricsChart.jsx'
import RunVerdict from '../../components/RunVerdict.jsx'
import TrainingProgress from '../../components/TrainingProgress.jsx'
import { majorityBaseline } from '../../lib/runStats.js'

const fmtPct = (logReturn) => `${(logReturn * 100).toFixed(2)}%`

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
          <p className="mt-2 text-xs text-slate-500">
            The verdict judges the <strong>direction head</strong> (the comparable number across
            stages). The return/volatility heads are scored by their MAE above.
          </p>
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
              <span className="text-red-400">▼ red</span> = predicted down · the number beside each
              arrow is the predicted return ·{' '}
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
                  text: p.pred_return != null ? fmtPct(p.pred_return) : '',
                }))}
              />
              <p className="text-xs text-slate-500">
                Each arrow is the direction head's call for the next candle; the percentage is the
                return head's estimate over the horizon. Compare the predicted returns to what
                followed — they cluster tightly around zero, which is itself the lesson: even with
                indicators, next-bar expectations are tiny.{' '}
                {overlay.out_of_sample
                  ? 'These are held-out test candles the model never trained on.'
                  : 'This run has no stored slice, so these are recent bars — illustrative only.'}
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
