// Stage 2 hyperparameter form configuration.
// Matches the backend LstmHyperParams defaults and bounds (and PLAN.md).

/** @type {import('../../lib/types.js').HyperParamField[]} */
export const HP_FIELDS = [
  { key: 'seq_len', label: 'Sequence length', min: 5, max: 240, hint: 'bars per window' },
  { key: 'horizon', label: 'Horizon', min: 1, max: 20, hint: 'bars ahead to predict' },
  { key: 'hidden', label: 'Hidden units', min: 8, max: 128 },
  { key: 'layers', label: 'LSTM layers', min: 1, max: 3 },
  { key: 'dropout', label: 'Dropout', step: 0.05, min: 0, max: 0.8 },
  { key: 'lr', label: 'Learning rate', step: 0.0001, min: 0.0001, max: 1 },
  { key: 'batch', label: 'Batch size', min: 8, max: 512 },
  { key: 'epochs', label: 'Max epochs', min: 1, max: 200 },
  { key: 'patience', label: 'Early-stop patience', min: 1, max: 50 },
  {
    key: 'lr_factor',
    label: 'LR drop factor',
    step: 0.05,
    min: 0.1,
    max: 0.9,
    hint: 'LR ×= this on plateau',
  },
  { key: 'lr_patience', label: 'LR drop patience', min: 1, max: 20, hint: 'epochs before LR drop' },
]

export const HP_DEFAULTS = {
  seq_len: 60,
  horizon: 1,
  hidden: 64,
  layers: 2,
  dropout: 0.2,
  lr: 0.001,
  batch: 64,
  epochs: 30,
  patience: 5,
  lr_factor: 0.5,
  lr_patience: 2,
}

// Headline params shown as chips on each example card.
export const CHIP_KEYS = ['seq_len', 'hidden', 'layers', 'dropout', 'lr', 'epochs', 'lr_patience']
