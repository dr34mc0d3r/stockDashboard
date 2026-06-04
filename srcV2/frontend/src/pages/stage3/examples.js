// Stage 3 preset configurations: each pairs hyperparameter overrides with an
// indicator selection, chosen to surface a specific lesson.

export const EXAMPLES = [
  {
    name: 'Quick smoke test',
    data: 'a smaller series — e.g. an hourly timeframe',
    expect:
      'Finishes fast. Confirms the whole Stage 3 pipeline end-to-end: indicator features, the three-head model, per-head metrics, and the overlay with predicted returns.',
    params: { seq_len: 30, hidden: 16, layers: 1, dropout: 0.1, epochs: 8, patience: 8 },
    indicators: [
      { name: 'sma', params: { period: 20 } },
      { name: 'rsi', params: { period: 14 } },
    ],
  },
  {
    name: 'Trend pack',
    data: 'a long slice — e.g. a year of 1h or 5m bars',
    expect:
      'The classic trend toolkit as features. The question to ask the runs table afterwards: does the direction head now beat its majority baseline where Stage 2 could not?',
    params: { seq_len: 60, hidden: 64, layers: 2 },
    indicators: [
      { name: 'sma', params: { period: 20 } },
      { name: 'ema', params: { period: 20 } },
      { name: 'macd', params: { fast: 12, slow: 26, signal: 9 } },
      { name: 'adx', params: { period: 14 } },
    ],
  },
  {
    name: 'Volatility focus',
    data: 'any stored series with real movement',
    expect:
      "Volatility-flavored features plus a raised w_vol: watch the volatility head's MAE fall while direction stays near its baseline — different heads learn different things, and vol is far more predictable than direction.",
    params: { seq_len: 60, hidden: 32, layers: 2, w_vol: 3.0, vol_window: 10 },
    indicators: [
      { name: 'atr', params: { period: 14 } },
      { name: 'bollinger', params: { period: 20, std_mult: 2 } },
      { name: 'stochastic', params: { k_period: 14, d_period: 3, smooth: 3 } },
    ],
  },
  {
    name: 'All ten, equal weights',
    data: 'a full year of bars',
    expect:
      "Every indicator, default weights — the honest Stage 3 baseline. More features ≠ free edge: expect the direction head to move only slightly, and read the verdict's significance call before celebrating.",
    params: {},
    indicators: [
      { name: 'sma', params: { period: 20 } },
      { name: 'ema', params: { period: 20 } },
      { name: 'bollinger', params: { period: 20, std_mult: 2 } },
      { name: 'vwap', params: { period: 20 } },
      { name: 'rsi', params: { period: 14 } },
      { name: 'macd', params: { fast: 12, slow: 26, signal: 9 } },
      { name: 'stochastic', params: { k_period: 14, d_period: 3, smooth: 3 } },
      { name: 'atr', params: { period: 14 } },
      { name: 'adx', params: { period: 14 } },
      { name: 'obv', params: { period: 20 } },
    ],
  },
]
