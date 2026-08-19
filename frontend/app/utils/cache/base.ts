export type CacheUserId = number | 'guest'

export interface CacheEnvelope<T> {
  schemaVersion: 2
  savedAt: number
  userId: CacheUserId
  data: T
}

function storage(): Storage | undefined {
  return typeof localStorage === 'undefined' ? undefined : localStorage
}

export function cacheKey(prefix: string, userId: CacheUserId): string {
  return `${prefix}${userId}`
}

export function writeCache<T>(key: string, userId: CacheUserId, data: T): void {
  storage()?.setItem(key, JSON.stringify({ schemaVersion: 2, savedAt: Date.now(), userId, data } satisfies CacheEnvelope<T>))
}

export function readCache<T>(key: string, userId: CacheUserId, migrate: (raw: unknown) => T | undefined): T | undefined {
  const target = storage()
  const raw = target?.getItem(key)
  if (!raw) return undefined
  try {
    const parsed = JSON.parse(raw) as Partial<CacheEnvelope<T>>
    if (parsed.schemaVersion === 2 && parsed.userId === userId && parsed.data !== undefined) return parsed.data
    const migrated = migrate(parsed)
    if (migrated !== undefined) writeCache(key, userId, migrated)
    else target?.removeItem(key)
    return migrated
  } catch {
    target?.removeItem(key)
    return undefined
  }
}

export function removeCache(key: string): void {
  storage()?.removeItem(key)
}
