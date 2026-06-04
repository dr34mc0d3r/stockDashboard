// Stage 3 hyperparameter form configuration.
// Matches the backend MultiTaskHyperParams defaults and bounds: the Stage 2
// knobs plus the per-task loss weights and the volatility target window.

/** @type {import('../../lib/types.js').HyperParamField[]} */
export const HP_FIELDS = [
  { key: 'seq_len', label: 'Sequence length', min: 5, max: 240, hint: 'bars per window' },
  { key: 'horizon', label: 'Horizon', min: 1, max: 20, hint: 'bars ahead to predict' },
  { key: 'vol_window', label: 'Vol window', min: 2, max: 60, hint: 'bars of realized vol' },
  { key: 'hidden', label: 'Hidden units', min: 8, max: 128 },
  { key: 'layers', label: 'LSTM layers', min: 1, max: 3 },
  { key: 'dropout', label: 'Dropout', step: 0.05, min: 0, max: 0.8 },
  { key: 'lr', label: 'Learning rate', step: 0.0001, min: 0.0001, max: 1 },
  { key: 'batch', label: 'Batch size', min: 8, max: 512 },
  { key: 'epochs', label: 'Max epochs', min: 1, max: 200 },
  { key: 'patience', label: 'Early-stop patience', min: 1, max: 50 },
  { key: 'w_dir', label: 'Direction weight', step: 0.1, min: 0, max: 10, hint: 'loss weight' },
  { key: 'w_ret', label: 'Return weight', step: 0.1, min: 0, max: 10, hint: 'loss weight' },
  { key: 'w_vol', label: 'Volatility weight', step: 0.1, min: 0, max: 10, hint: 'loss weight' },
]

export const HP_DEFAULTS = {
  seq_len: 60,
  horizon: 1,
  vol_window: 5,
  hidden: 64,
  layers: 2,
  dropout: 0.2,
  lr: 0.001,
  batch: 64,
  epochs: 30,
  patience: 5,
  lr_factor: 0.5,
  lr_patience: 2,
  w_dir: 1.0,
  w_ret: 1.0,
  w_vol: 1.0,
}

// Headline params shown as chips on each example card.
export const CHIP_KEYS = ['seq_len', 'hidden', 'layers', 'w_dir', 'w_ret', 'w_vol', 'epochs']
