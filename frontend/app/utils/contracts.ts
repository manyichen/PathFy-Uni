import type { ApiEnvelope, ApiFieldError, AuthUser, CodeEnvelope, OkEnvelope } from '~/types/api'

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

export function unwrapApi<T>(body: ApiEnvelope<T>): T {
  if ('ok' in body) return unwrapOk(body)
  return unwrapCode(body)
}

export function normalizeFieldErrors(value: unknown): ApiFieldError[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    if (typeof item === 'string') return { message: item }
    if (!item || typeof item !== 'object') return { message: String(item || '请求参数无效') }
    const row = item as Record<string, unknown>
    return {
      ...row,
      path: typeof row.path === 'string' ? row.path : typeof row.field === 'string' ? row.field : undefined,
      message: String(row.message || row.msg || row.error || '请求参数无效')
    }
  })
}
