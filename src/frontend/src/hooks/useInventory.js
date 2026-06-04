// Fetches the stored-data inventory once on mount. Both stage pages need this
// list (Stage 1 to display it, Stage 2 to offer data sources), so the fetch
// lives in one hook.

import { useCallback, useEffect, useRef, useState } from 'react'
import { getInventory } from '../api/client.js'

/**
 * @param {(inventory: import('../lib/types.js').InventoryItem[]) => void} [onLoad]
 *   Optional callback fired with the list after every (re)fetch — e.g. to pick
 *   a default selection.
 * @returns {{ inventory: import('../lib/types.js').InventoryItem[], refreshInventory: () => Promise<void> }}
 */
export function useInventory(onLoad) {
  const [inventory, setInventory] = useState([])

  // Callers pass inline arrows for onLoad; keeping the latest one in a ref
  // means a new arrow identity never re-triggers the mount fetch. (Synced in
  // an effect — refs must not be written during render.)
  const onLoadRef = useRef(onLoad)
  useEffect(() => {
    onLoadRef.current = onLoad
  })

  const refreshInventory = useCallback(async () => {
    try {
      const inv = await getInventory()
      setInventory(inv)
      onLoadRef.current?.(inv)
    } catch {
      // Inventory is non-critical chrome; a failed fetch just leaves it empty.
    }
  }, [])

  useEffect(() => {
    // False positive: refreshInventory is async, so setState runs after the
    // await (the standard fetch-on-mount pattern), not synchronously here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshInventory()
  }, [refreshInventory])

  return { inventory, refreshInventory }
}
