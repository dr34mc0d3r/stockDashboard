// Shared JSDoc typedefs for the data shapes that cross the API boundary.
// Nothing here runs — importing these names in a @type/@param comment gives
// editors autocomplete and shape-checking without TypeScript.
//
// Usage:  /** @param {import('../lib/types.js').Run} run */

/**
 * One stored OHLCV bar (backend BarOut).
 * @typedef {object} Bar
 * @property {string} ts - Naive-UTC ISO timestamp, e.g. "2025-05-01T08:00:00".
 * @property {number} open
 * @property {number} high
 * @property {number} low
 * @property {number} close
 * @property {number} volume
 */

/**
 * A stored (symbol, timeframe) summary row (backend InventoryItem).
 * @typedef {object} InventoryItem
 * @property {string} symbol
 * @property {string} timeframe
 * @property {number} bar_count
 * @property {string} earliest
 * @property {string} latest
 */

/**
 * One epoch's worth of live training metrics (an entry in Run.progress).
 * @typedef {object} EpochProgress
 * @property {number} epoch - 1-based.
 * @property {number} train_loss
 * @property {number} val_loss
 * @property {number} val_acc - 0..1.
 * @property {number} [lr] - LR used during this epoch (newer runs only).
 */

/**
 * Final metrics of a finished run (Run.metrics).
 * @typedef {object} RunMetrics
 * @property {number} test_acc - 0..1.
 * @property {number} test_loss
 * @property {number} best_val_loss
 * @property {number} epochs_run
 * @property {{tp: number, tn: number, fp: number, fn: number}} confusion
 * @property {{train: number, val: number, test: number}} class_balance - Fraction of "up" labels per split.
 * @property {number} n_train
 * @property {number} n_val
 * @property {number} n_test
 */

/**
 * A training run row (backend TrainingRunOut).
 * @typedef {object} Run
 * @property {number} id
 * @property {string} stage - e.g. "lstm".
 * @property {string} symbol
 * @property {string} timeframe
 * @property {string|null} start - Optional data-slice start (ISO date).
 * @property {string|null} end
 * @property {'queued'|'running'|'done'|'error'} status
 * @property {Record<string, any>} hyperparams
 * @property {EpochProgress[]} progress
 * @property {RunMetrics|null} metrics
 * @property {string|null} artifact_path
 * @property {string} detail - Error text when status is "error".
 * @property {string} created_at
 * @property {string} updated_at
 */

/**
 * One numeric field in a hyperparameter form (see HyperParamForm).
 * @typedef {object} HyperParamField
 * @property {string} key - Key into the values object (e.g. "seq_len").
 * @property {string} label
 * @property {number} [min]
 * @property {number} [max]
 * @property {number} [step]
 * @property {string} [hint] - Small helper text under the input.
 */

export {}
