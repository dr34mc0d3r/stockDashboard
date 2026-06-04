// Run-quality math shared by the verdict panel and the runs table.
//
// The central idea: on a binary up/down label, "always guess the majority
// class" is free, so a model is only interesting if its test accuracy beats
// that baseline by more than sampling noise (~2 standard errors on the test
// count). Everything here is computed from fields the backend already stores
// on the run row — no extra API calls.

// Majority-class rate from an "up" fraction (0..1): guessing the more common
// direction every time gets you this accuracy for free.
export function majorityBaseline(upFraction) {
  return upFraction == null ? null : Math.max(upFraction, 1 - upFraction)
}

// Edge of test accuracy over the majority baseline, with a rough binomial
// standard error so we can call the edge "real" or "noise".
export function baselineEdge(metrics) {
  const base = majorityBaseline(metrics?.class_balance?.test)
  if (base == null || metrics?.test_acc == null) return null
  const n = metrics.n_test
  const se = n ? Math.sqrt((base * (1 - base)) / n) : null
  const edge = metrics.test_acc - base
  return { base, edge, se, significant: se != null && edge > 2 * se }
}

// Approximate trainable parameter count of the Stage 2 LSTMClassifier:
// per layer 4h(in+h) weights + 8h biases (PyTorch keeps ih and hh bias
// vectors), then the h→1 linear head.
export function lstmParamCount(hp, nFeatures = 5) {
  const h = hp?.hidden ?? 64
  const layers = hp?.layers ?? 2
  let p = 0
  for (let l = 0; l < layers; l++) {
    const inp = l === 0 ? nFeatures : h
    p += 4 * h * (inp + h) + 8 * h
  }
  return p + h + 1
}

// Stage 3 MultiTaskNet: the same LSTM trunk, but three h→1 heads instead of
// one. nFeatures should include the indicator columns (5 + k).
export function multitaskParamCount(hp, nFeatures = 5) {
  const h = hp?.hidden ?? 64
  return lstmParamCount(hp, nFeatures) + 2 * (h + 1) // two extra heads
}

const pct = (v) => `${(v * 100).toFixed(1)}%`
const pts = (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}pt`

// Full plain-English diagnosis of a finished run.
// Returns { tone: 'good'|'mixed'|'bad', headline, findings: [{level, title, text}] }
// or null if the run hasn't finished. level ∈ good | warn | bad | info.
export function analyzeRun(run) {
  if (!run || run.status !== 'done' || !run.metrics) return null
  const m = run.metrics
  const hp = run.hyperparams || {}
  const prog = run.progress || []
  const findings = []

  // --- 1. Edge over the majority-class baseline -------------------------
  const eb = baselineEdge(m)
  let edgeLevel = 'info'
  if (eb) {
    if (eb.edge <= 0) {
      edgeLevel = 'bad'
      findings.push({
        level: 'bad',
        title: `No edge: ${pct(m.test_acc)} vs a ${pct(eb.base)} always-guess-the-majority baseline`,
        text: `Guessing the test split's more common direction every time scores ${pct(eb.base)}; the model does no better. That's the expected Stage 2 result on raw OHLCV — not a bug to tune away.`,
      })
    } else if (!eb.significant) {
      edgeLevel = 'warn'
      findings.push({
        level: 'warn',
        title: `Edge within noise: ${pts(eb.edge)} over the ${pct(eb.base)} baseline`,
        text: `On ${m.n_test ?? '?'} test windows, sampling noise alone is about ±${pct(2 * (eb.se ?? 0))} — a ${pts(eb.edge)} edge could easily be luck. Re-run on a different slice before believing it.`,
      })
    } else {
      edgeLevel = 'good'
      findings.push({
        level: 'good',
        title: `Real edge: ${pts(eb.edge)} over the ${pct(eb.base)} baseline (> 2 standard errors)`,
        text: `That's unusual on raw OHLCV — verify it isn't a fluke: retrain on a different date slice and a different symbol. If it survives both, you've found something.`,
      })
    }
  }

  // --- 2. Degenerate predictions (always one class) ---------------------
  const c = m.confusion
  if (c) {
    const total = c.tp + c.tn + c.fp + c.fn
    const predUp = c.tp + c.fp
    const minorShare = total ? Math.min(predUp, total - predUp) / total : 0.5
    if (total && minorShare < 0.05) {
      findings.push({
        level: 'warn',
        title: `Collapsed predictions: ${pct(Math.max(predUp, total - predUp) / total)} of calls are the same direction`,
        text: 'The model has collapsed to a near-constant guess — typical when there is no learnable signal, since the loss is then minimized at the base rate. More capacity will not fix this; better features (Stage 3) might.',
      })
    }
  }

  // --- 3. Overfitting: did val loss turn up while train kept falling? ---
  if (prog.length >= 3) {
    const valLosses = prog.map((p) => p.val_loss)
    const minVal = Math.min(...valLosses)
    const minIdx = valLosses.indexOf(minVal)
    const lastVal = valLosses[valLosses.length - 1]
    const rise = (lastVal - minVal) / minVal
    if (rise > 0.02 && minIdx < prog.length - 1) {
      findings.push({
        level: 'warn',
        title: `Overfitting after epoch ${prog[minIdx].epoch}: val loss rose ${pct(rise)} from its best`,
        text: `Early stopping restored the epoch-${prog[minIdx].epoch} weights, so the score above is the pre-overfit model. To delay the turn next time: raise dropout, shrink hidden/layers, or train on more bars.`,
      })
    } else {
      // 3b. Under-training: budget ran out while val was still improving.
      const ranOut = m.epochs_run === (hp.epochs ?? m.epochs_run)
      if (ranOut && minIdx >= prog.length - 2) {
        findings.push({
          level: 'warn',
          title: 'Stopped by the epoch budget, not by early stopping',
          text: `Val loss was still at (or near) its best on the final epoch — the model may not have finished learning. Raise epochs and let early stopping decide when to quit.`,
        })
      } else {
        findings.push({
          level: 'good',
          title: `Clean stop: best val loss at epoch ${prog[minIdx].epoch} of ${m.epochs_run}`,
          text: 'Validation loss flattened and early stopping kept the best weights — no overfit visible in this run.',
        })
      }
    }
  }

  // --- 4. Model size vs data size ---------------------------------------
  if (m.n_train) {
    const nFeatures = m.n_features ?? 5
    const params =
      run.stage === 'multitask' ? multitaskParamCount(hp, nFeatures) : lstmParamCount(hp, nFeatures)
    const ratio = params / m.n_train
    if (m.n_train < 500) {
      findings.push({
        level: 'bad',
        title: `Tiny training set: ${m.n_train.toLocaleString()} windows`,
        text: 'Below ~500 windows, val/test scores swing wildly between runs and mean little. Widen the date slice or pick a series with more bars.',
      })
    } else if (ratio > 20) {
      findings.push({
        level: 'warn',
        title: `Big model, modest data: ~${params.toLocaleString()} params for ${m.n_train.toLocaleString()} windows`,
        text: `At ${ratio.toFixed(0)} parameters per training window the model can memorize rather than generalize. Shrink hidden or layers, or feed it more data.`,
      })
    } else {
      findings.push({
        level: 'good',
        title: `Sane capacity: ~${params.toLocaleString()} params for ${m.n_train.toLocaleString()} training windows`,
        text: 'Model size is reasonable for the amount of data — capacity is not the limiting factor here.',
      })
    }
  }

  // --- 5. Label-distribution checks --------------------------------------
  const cb = m.class_balance
  if (cb?.train != null && cb?.test != null) {
    const shift = Math.abs(cb.train - cb.test)
    if (shift > 0.08) {
      findings.push({
        level: 'warn',
        title: `Regime shift: ${pct(cb.train)} up-labels in train vs ${pct(cb.test)} in test`,
        text: 'The market the model tested on behaved differently from the one it trained on (the splits are by time, so this happens). Scores partly measure that shift, not just the model. Try a different slice.',
      })
    }
    const base = majorityBaseline(cb.test)
    if (base != null && base > 0.55) {
      findings.push({
        level: 'info',
        title: `Skewed test labels: ${pct(Math.max(cb.test, 1 - cb.test))} lean one way`,
        text: 'Raw accuracy flatters on a skewed split — that is exactly why the verdict compares against the majority baseline instead of 50%. The confusion matrix shows whether both directions are actually being called.',
      })
    }
  }

  // --- Headline -----------------------------------------------------------
  const hasBad = findings.some((f) => f.level === 'bad')
  const hygieneIssue = findings.some(
    (f) => f.level === 'warn' && !f.title.startsWith('Edge within noise'),
  )
  let tone, headline
  if (edgeLevel === 'good' && !hasBad && !hygieneIssue) {
    tone = 'good'
    headline =
      'A clean run that beats its baseline — rare on raw OHLCV. Confirm it on a different slice before trusting it.'
  } else if (edgeLevel === 'good') {
    tone = 'mixed'
    headline =
      'The accuracy beats baseline, but the flagged issues below could explain it — fix them and re-run before believing the edge.'
  } else if (!hasBad && !hygieneIssue) {
    tone = 'mixed'
    headline =
      'A clean, well-behaved run with no real edge — the honest Stage 2 result. Training hygiene is fine; raw OHLCV simply carries almost no next-bar signal. Stage 3 features are the fix, not more tuning.'
  } else {
    tone = 'bad'
    headline = 'Fix the flagged issues below before reading anything into the accuracy number.'
  }

  return { tone, headline, findings }
}
