import type { ProfileDetail } from '~/types/profile'
import { asNumber, asRecord, normalizeProfileDetail } from '~/utils/normalizers'
import { cacheKey, readCache, removeCache, type CacheUserId, writeCache } from './base'

const prefix = 'career_profile_portrait_v1_'
export interface ProfileCacheState { resumeId?: number; portrait: ProfileDetail }
export const profileCacheKey = (userId: CacheUserId) => cacheKey(prefix, userId)

function migrate(raw: unknown): ProfileCacheState | undefined {
  const row = asRecord(raw)
  const payload = asRecord(row.data || row)
  const portraitRaw = payload.portrait || payload.result || payload
  if (!portraitRaw || typeof portraitRaw !== 'object') return undefined
  const portrait = normalizeProfileDetail(portraitRaw)
  if (!portrait.id) return undefined
  return { resumeId: asNumber(payload.resumeId || payload.resume_id || portrait.resume_id || portrait.id), portrait }
}

export const readProfileCache = (userId: CacheUserId) => readCache(profileCacheKey(userId), userId, migrate)
export const writeProfileCache = (userId: CacheUserId, data: ProfileCacheState) => writeCache(profileCacheKey(userId), userId, data)
export const clearProfileCache = (userId: CacheUserId) => removeCache(profileCacheKey(userId))
