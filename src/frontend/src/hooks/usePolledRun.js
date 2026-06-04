// Owns the "watch a training run live" loop: while the current run is queued
// or running, re-fetch it every POLL_INTERVAL_MS so the page re-renders with
// fresh progress. Polling stops by itself once the run reaches a final state.

import { useEffect, useRef, useState } from 'react'
import { getRun } from '../api/client.js'
import { POLL_INTERVAL_MS } from '../constants.js'

/** Is this run still being worked on? */
export const isActive = (status) => status === 'queued' || status === 'running'

/**
 * @param {(message: string) => void} [onError] - Called if a poll fails.
 * @returns {{
 *   run: import('../lib/types.js').Run | null,
 *   setRun: (run: import('../lib/types.js').Run | null) => void,
 *   training: boolean,
 * }}
 */
export function usePolledRun(onError) {
  const [run, setRun] = useState(null)

  // Latest error handler in a ref so its identity never re-arms the timer.
  // (Synced in an effect — refs must not be written during render.)
  const onErrorRef = useRef(onError)
  useEffect(() => {
    onErrorRef.current = onError
  })

  useEffect(() => {
    if (!run || !isActive(run.status)) return
    const t = setTimeout(() => {
      getRun(run.id)
        .then(setRun)
        .catch((e) => onErrorRef.current?.(e.message))
    }, POLL_INTERVAL_MS)
    return () => clearTimeout(t)
  }, [run])

  return { run, setRun, training: Boolean(run && isActive(run.status)) }
}
