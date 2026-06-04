// Unit tests for the run-quality math. These are pure functions, so the tests
// double as worked examples of what each number means.
import { describe, it, expect } from 'vitest'
import { analyzeRun, baselineEdge, lstmParamCount, majorityBaseline } from './runStats.js'

describe('majorityBaseline', () => {
  it('returns null when the up-fraction is unknown', () => {
    expect(majorityBaseline(null)).toBeNull()
    expect(majorityBaseline(undefined)).toBeNull()
  })

  it('always returns the larger class share', () => {
    expect(majorityBaseline(0.7)).toBe(0.7)
    expect(majorityBaseline(0.3)).toBe(0.7)
    expect(majorityBaseline(0.5)).toBe(0.5)
  })
})

describe('baselineEdge', () => {
  it('returns null when metrics are missing or incomplete', () => {
    expect(baselineEdge(null)).toBeNull()
    expect(baselineEdge({})).toBeNull()
    expect(baselineEdge({ test_acc: 0.55 })).toBeNull() // no class_balance
  })

  it('computes edge = test accuracy minus the majority baseline', () => {
    const eb = baselineEdge({ test_acc: 0.55, class_balance: { test: 0.5 }, n_test: 400 })
    expect(eb.base).toBe(0.5)
    expect(eb.edge).toBeCloseTo(0.05)
  })

  it('marks a big edge on many test windows as significant (> 2 SE)', () => {
    // se = sqrt(0.5*0.5/10000) = 0.005 → 2se = 1pt; a 5pt edge clears it.
    const eb = baselineEdge({ test_acc: 0.55, class_balance: { test: 0.5 }, n_test: 10000 })
    expect(eb.significant).toBe(true)
  })

  it('marks a small edge on few test windows as noise', () => {
    // se = sqrt(0.5*0.5/100) = 0.05 → 2se = 10pt; a 5pt edge is within noise.
    const eb = baselineEdge({ test_acc: 0.55, class_balance: { test: 0.5 }, n_test: 100 })
    expect(eb.significant).toBe(false)
  })

  it('leaves se null (and significance false) when n_test is absent', () => {
    const eb = baselineEdge({ test_acc: 0.55, class_balance: { test: 0.5 } })
    expect(eb.se).toBeNull()
    expect(eb.significant).toBe(false)
  })
})

describe('lstmParamCount', () => {
  it('matches the hand-computed count for a small one-layer model', () => {
    // One layer (h=8, 5 input features): 4h(in+h) weights + 8h biases = 416 + 64,
    // plus the h→1 head (8 weights + 1 bias) → 489.
    expect(lstmParamCount({ hidden: 8, layers: 1 })).toBe(4 * 8 * (5 + 8) + 8 * 8 + 8 + 1)
  })

  it('stacks layers with hidden-to-hidden input size after the first', () => {
    const one = lstmParamCount({ hidden: 8, layers: 1 })
    const two = lstmParamCount({ hidden: 8, layers: 2 })
    expect(two - one).toBe(4 * 8 * (8 + 8) + 8 * 8) // second layer: in = hidden
  })

  it('falls back to the Stage 2 defaults when hp is empty', () => {
    expect(lstmParamCount({})).toBe(lstmParamCount({ hidden: 64, layers: 2 }))
  })
})

// Helper: a finished run shaped like the backend's TrainingRunOut.
function doneRun(overrides = {}) {
  const epochs = [0.7, 0.69, 0.685, 0.684, 0.684]
  return {
    status: 'done',
    hyperparams: { hidden: 16, layers: 1, epochs: 30, ...overrides.hyperparams },
    progress: epochs.map((val_loss, i) => ({
      epoch: i + 1,
      train_loss: val_loss - 0.005,
      val_loss,
      val_acc: 0.5,
      lr: 0.001,
    })),
    metrics: {
      test_acc: 0.5,
      test_loss: 0.69,
      best_val_loss: 0.684,
      epochs_run: epochs.length,
      n_train: 5000,
      n_val: 1000,
      n_test: 1000,
      class_balance: { train: 0.5, val: 0.5, test: 0.5 },
      confusion: { tp: 250, tn: 250, fp: 250, fn: 250 },
      ...overrides.metrics,
    },
    ...overrides.run,
  }
}

describe('analyzeRun', () => {
  it('returns null for unfinished runs', () => {
    expect(analyzeRun(null)).toBeNull()
    expect(analyzeRun({ status: 'running', progress: [] })).toBeNull()
    expect(analyzeRun({ status: 'done' })).toBeNull() // no metrics yet
  })

  it('flags "no edge" as a bad finding when accuracy <= baseline', () => {
    const verdict = analyzeRun(doneRun())
    const noEdge = verdict.findings.find((f) => f.title.startsWith('No edge'))
    expect(noEdge?.level).toBe('bad')
  })

  it('gives a clean within-noise run the honest "mixed" headline', () => {
    // +1pt edge on only 400 test windows (2 SE ≈ 5pt) → noise, but training
    // hygiene is clean → the "honest Stage 2 result" headline.
    const verdict = analyzeRun(doneRun({ metrics: { test_acc: 0.51, n_test: 400 } }))
    expect(verdict.tone).toBe('mixed')
    expect(verdict.headline).toMatch(/no real edge/i)
  })

  it('flags overfitting when val loss rises well off its minimum', () => {
    const valLosses = [0.7, 0.66, 0.62, 0.65, 0.7, 0.75]
    const verdict = analyzeRun(
      doneRun({
        run: {
          progress: valLosses.map((val_loss, i) => ({
            epoch: i + 1,
            train_loss: 0.7 - i * 0.08, // training keeps diving
            val_loss,
            val_acc: 0.5,
            lr: 0.001,
          })),
        },
      }),
    )
    const overfit = verdict.findings.find((f) => f.title.startsWith('Overfitting'))
    expect(overfit?.level).toBe('warn')
    expect(overfit?.title).toContain('epoch 3') // val loss bottomed at epoch 3
  })

  it('flags a tiny training set as bad', () => {
    const verdict = analyzeRun(doneRun({ metrics: { n_train: 300 } }))
    const tiny = verdict.findings.find((f) => f.title.startsWith('Tiny training set'))
    expect(tiny?.level).toBe('bad')
  })

  it('flags collapsed predictions when nearly all calls are one direction', () => {
    const verdict = analyzeRun(
      doneRun({ metrics: { confusion: { tp: 490, fp: 500, tn: 5, fn: 5 } } }),
    )
    const collapsed = verdict.findings.find((f) => f.title.startsWith('Collapsed'))
    expect(collapsed?.level).toBe('warn')
  })
})
