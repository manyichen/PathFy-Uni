import type { AuthUser, CodeEnvelope, OkEnvelope } from '~/types/api'

export const AUTH_TOKEN_KEY = 'auth_token'
export const AUTH_USER_KEY = 'auth_user'
export const USER_CACHE_PREFIXES = ['career_profile_portrait_v1_', 'career_pj_match_v1_', 'career_personality_v1_', 'career_report_workspace_v1_'] as const

export function parseStoredUser(raw: string | null): AuthUser | null {
  if (!raw) return null
  try { return JSON.parse(raw) as AuthUser } catch { return null }
}

export function cacheKeysForLogout(userId?: number): string[] {
  return USER_CACHE_PREFIXES.flatMap(prefix => [
    ...(userId ? [`${prefix}${userId}`] : []),
    `${prefix}guest`
  ])
}

export function unwrapOk<T>(body: OkEnvelope<T>): T {
  if (!body.ok) throw new Error(body.message || '请求失败')
  return body.data as T
}

export function unwrapCode<T>(body: CodeEnvelope<T>): T {
  if (body.code !== 200) throw new Error(body.msg || '请求失败')
  return body.data as T
}
