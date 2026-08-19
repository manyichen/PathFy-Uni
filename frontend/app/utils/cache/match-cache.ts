import type { MatchGoal, MatchPreviewResult, PreferenceMode } from '~/types/match'
import { asRecord, asString, normalizeMatchPreview, optionalNumber } from '~/utils/normalizers'
import { cacheKey, readCache, removeCache, type CacheUserId, writeCache } from './base'

const prefix = 'career_pj_match_v1_'
export interface MatchCacheState { resumeId?: number; result: MatchPreviewResult; filters: { q: string; locationQ: string; goal: MatchGoal; refine: boolean; preferenceMode: PreferenceMode } }
export const matchCacheKey = (userId: CacheUserId) => cacheKey(prefix, userId)

function migrate(raw: unknown): MatchCacheState | undefined {
  const row = asRecord(raw)
  const payload = asRecord(row.data || row)
  if (!payload.result || typeof payload.result !== 'object') return undefined
  const filters = asRecord(payload.filters)
  return {
    resumeId: optionalNumber(payload.resumeId),
    result: normalizeMatchPreview(payload.result),
    filters: { q: asString(filters.q), locationQ: asString(filters.locationQ), goal: filters.goal === 'stretch' ? 'stretch' : 'fit', refine: Boolean(filters.refine), preferenceMode: filters.preferenceMode === 'explain' ? 'explain' : 'off' }
  }
}

export const readMatchCache = (userId: CacheUserId) => readCache(matchCacheKey(userId), userId, migrate)
export const writeMatchCache = (userId: CacheUserId, data: MatchCacheState) => writeCache(matchCacheKey(userId), userId, data)
export const clearMatchCache = (userId: CacheUserId) => removeCache(matchCacheKey(userId))
