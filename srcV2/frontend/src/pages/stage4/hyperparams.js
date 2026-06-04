// Stage 4 hyperparameter form configuration — Stage 3's fields verbatim
// (the model is the same three-headed net); the sentiment toggle is separate
// UI in the TrainForm, not a numeric field.

export { CHIP_KEYS, HP_FIELDS } from '../stage3/hyperparams.js'
import { HP_DEFAULTS as STAGE3_DEFAULTS } from '../stage3/hyperparams.js'

export const HP_DEFAULTS = { ...STAGE3_DEFAULTS }
