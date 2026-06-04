// Preset configurations, each chosen to surface a specific, instructive result.
// `params` are overrides on top of HP_DEFAULTS; `data` is the suggested source.

export const EXAMPLES = [
  {
    name: 'Quick smoke test',
    data: 'a small series — e.g. AAPL 1m',
    expect:
      'Finishes in seconds. Confirms the whole pipeline runs end-to-end: training, live metrics, confusion matrix, and a saved model.',
    params: { seq_len: 30, hidden: 16, layers: 1, dropout: 0.1, epochs: 8, patience: 8 },
  },
  {
    name: 'Watch it learn (LR steps down)',
    data: 'any stored series',
    expect:
      'High starting LR + an impatient scheduler: training loss falls and the Learning-rate chart visibly steps down (0.01 → 0.005 → 0.0025 …) each time val loss plateaus.',
    params: {
      seq_len: 30,
      hidden: 32,
      layers: 2,
      lr: 0.01,
      epochs: 20,
      patience: 8,
      lr_patience: 1,
    },
  },
  {
    name: 'Make it overfit',
    data: 'a SMALL slice — AAPL 1m, or a ~1-month date range',
    expect:
      'A big model on little data: training loss keeps diving while validation loss flattens then turns up — the textbook overfitting gap. Early stopping restores the best pre-overfit weights.',
    params: {
      seq_len: 60,
      hidden: 128,
      layers: 3,
      dropout: 0.0,
      batch: 32,
      epochs: 50,
      patience: 12,
      lr_patience: 6,
    },
  },
  {
    name: 'The honest baseline',
    data: 'a full year — e.g. TSLA 1m, 2025-01-01 → 2026-01-01',
    expect:
      'Test accuracy hovers around 50%. Next-bar direction on raw 1-minute OHLCV is nearly random — the expected result, and exactly why Stage 3 adds real features.',
    params: {}, // pure defaults
  },
]
