// App-wide constants — named here so "why this number?" has one answer.

// How often the UI re-fetches an active training run. 1.5s feels live without
// hammering the API (a CPU epoch usually takes longer than this anyway).
export const POLL_INTERVAL_MS = 1500

// Pixel height of the candlestick chart container.
export const CHART_HEIGHT_PX = 460
