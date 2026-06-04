// Thin wrappers over the FastAPI backend. The Vite dev server proxies /api.
// Response shapes are documented in lib/types.js.

const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function asJson(res, label) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `${label} failed`)
  }
  return res.json()
}

/** @returns {Promise<import('../lib/types.js').InventoryItem[]>} */
export function getInventory() {
  return fetch('/api/v1/inventory').then((r) => asJson(r, 'inventory'))
}

export function ingest(body) {
  return fetch('/api/v1/ingest', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  }).then((r) => asJson(r, 'ingest'))
}

/** @returns {Promise<import('../lib/types.js').Bar[]>} */
export function getBars(symbol, timeframe, limit = 5000) {
  const q = new URLSearchParams({ symbol, timeframe, limit })
  return fetch(`/api/v1/bars?${q}`).then((r) => asJson(r, 'bars'))
}

export function deleteBars(symbol, timeframe) {
  const q = new URLSearchParams({ symbol, timeframe })
  return fetch(`/api/v1/bars?${q}`, { method: 'DELETE' }).then((r) => asJson(r, 'delete'))
}

// --- Stage 3: indicators ---

/** Indicator metadata (labels, placement, param schema) for building the UI. */
export function getCatalog() {
  return fetch('/api/v1/indicators/catalog').then((r) => asJson(r, 'catalog'))
}

/** Compute indicators over stored bars; returns bars + aligned series. */
export function computeIndicators(body) {
  return fetch('/api/v1/indicators', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  }).then((r) => asJson(r, 'indicators'))
}

// --- Stage 4: news sentiment ---

/** Kick off the fetch+FinBERT prep job; returns the run to poll. */
export function prepareSentiment(body) {
  return fetch('/api/v1/sentiment/prepare', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  }).then((r) => asJson(r, 'sentiment prep'))
}

/** The stored, scored headline corpus for a symbol (newest first). */
export function getHeadlines(symbol, limit = 200) {
  const q = new URLSearchParams({ symbol, limit })
  return fetch(`/api/v1/sentiment/headlines?${q}`).then((r) => asJson(r, 'headlines'))
}

/** Per-day sentiment coverage for the timeline + slice checks. */
export function getCoverage(symbol) {
  const q = new URLSearchParams({ symbol })
  return fetch(`/api/v1/sentiment/coverage?${q}`).then((r) => asJson(r, 'coverage'))
}

/** Start a Stage 4 training run (multitask + sentiment columns). */
export function trainSentiment(body) {
  return fetch('/api/v1/train/sentiment', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  }).then((r) => asJson(r, 'train'))
}

// --- Stage 2: training ---

/** Start a Stage 3 multitask run. @returns {Promise<import('../lib/types.js').Run>} */
export function trainMultiTask(body) {
  return fetch('/api/v1/train/multitask', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  }).then((r) => asJson(r, 'train'))
}

/** Start a training run. @returns {Promise<import('../lib/types.js').Run>} */
export function trainLstm(body) {
  return fetch('/api/v1/train/lstm', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  }).then((r) => asJson(r, 'train'))
}

/** Poll one run. @returns {Promise<import('../lib/types.js').Run>} */
export function getRun(id) {
  return fetch(`/api/v1/runs/${id}`).then((r) => asJson(r, 'run'))
}

/** Delete a finished run (row + saved artifact). */
export function deleteRun(id) {
  return fetch(`/api/v1/runs/${id}`, { method: 'DELETE' }).then((r) => asJson(r, 'delete run'))
}

/** List runs, newest first. @returns {Promise<import('../lib/types.js').Run[]>} */
export function getRuns(stage) {
  const q = stage ? `?${new URLSearchParams({ stage })}` : ''
  return fetch(`/api/v1/runs${q}`).then((r) => asJson(r, 'runs'))
}

export function getRunPredictions(id, limit = 200) {
  const q = new URLSearchParams({ limit })
  return fetch(`/api/v1/runs/${id}/predictions?${q}`).then((r) => asJson(r, 'predictions'))
}
