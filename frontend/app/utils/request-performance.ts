export const SEARCH_DEBOUNCE_MS = 300

export interface LatestRequestTicket {
  signal: AbortSignal
  isCurrent: () => boolean
}

export function createLatestRequestController() {
  let active: AbortController | undefined
  let generation = 0

  function start(): LatestRequestTicket {
    active?.abort()
    active = new AbortController()
    const currentGeneration = ++generation
    return {
      signal: active.signal,
      isCurrent: () => currentGeneration === generation && !active?.signal.aborted
    }
  }

  function cancel() {
    active?.abort()
    active = undefined
    generation++
  }

  return { start, cancel }
}

export function createExpiringCache<T>(ttlMs: number, now: () => number = Date.now) {
  const entries = new Map<string, { value: T; expiresAt: number }>()

  function get(key: string): T | undefined {
    const entry = entries.get(key)
    if (!entry) return undefined
    if (entry.expiresAt <= now()) {
      entries.delete(key)
      return undefined
    }
    return entry.value
  }

  function set(key: string, value: T) {
    entries.set(key, { value, expiresAt: now() + ttlMs })
  }

  function clear(key?: string) {
    if (key) entries.delete(key)
    else entries.clear()
  }

  return { get, set, clear }
}

export function shouldVirtualizeList(total: number, renderedCount: number) {
  return total > 100 && renderedCount > 100
}
