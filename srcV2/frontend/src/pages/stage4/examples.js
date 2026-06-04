// Stage 4 presets: hyperparams + indicator selection + the sentiment toggle.
// The point of this set is the A/B discipline — same everything, one change.

export const EXAMPLES = [
  {
    name: 'Sentiment only',
    data: 'a slice your prep run covers',
    expect:
      "No indicators at all — just OHLCV returns plus the two news columns. The cleanest read on whether yesterday's headlines carry any next-bar signal on their own.",
    params: { seq_len: 30, hidden: 16, layers: 1, epochs: 10, patience: 8 },
    indicators: [],
    sentiment: { enabled: true, lag_days: 1 },
  },
  {
    name: 'Indicators + sentiment',
    data: 'a covered slice with plenty of bars',
    expect:
      'The full Stage 4 stack: trend/momentum indicators AND the news columns. Compare its direction edge against the rematch below — that difference is what sentiment bought you.',
    params: { seq_len: 30, hidden: 32, layers: 2 },
    indicators: [
      { name: 'sma', params: { period: 20 } },
      { name: 'ema', params: { period: 20 } },
      { name: 'rsi', params: { period: 14 } },
      { name: 'macd', params: { fast: 12, slow: 26, signal: 9 } },
    ],
    sentiment: { enabled: true, lag_days: 1 },
  },
  {
    name: 'Stage 3 rematch (the control)',
    data: 'the SAME slice as the run above',
    expect:
      "Identical indicators and hyperparameters, sentiment OFF. Train both, put them side by side in the runs table, and let the edge column settle the argument. One changed variable — that's the whole method.",
    params: { seq_len: 30, hidden: 32, layers: 2 },
    indicators: [
      { name: 'sma', params: { period: 20 } },
      { name: 'ema', params: { period: 20 } },
      { name: 'rsi', params: { period: 14 } },
      { name: 'macd', params: { fast: 12, slow: 26, signal: 9 } },
    ],
    sentiment: { enabled: false, lag_days: 1 },
  },
]
