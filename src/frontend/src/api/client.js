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

// --- Stage 2: training ---

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

/** List runs, newest first. @returns {Promise<import('../lib/types.js').Run[]>} */
export function getRuns(stage) {
  const q = stage ? `?${new URLSearchParams({ stage })}` : ''
  return fetch(`/api/v1/runs${q}`).then((r) => asJson(r, 'runs'))
}

export function getRunPredictions(id, limit = 200) {
  const q = new URLSearchParams({ limit })
  return fetch(`/api/v1/runs/${id}/predictions?${q}`).then((r) => asJson(r, 'predictions'))
}
