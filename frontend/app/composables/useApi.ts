import type { ApiEnvelope, ApiFieldError, CodeEnvelope, OkEnvelope } from '~/types/api'
import { normalizeFieldErrors, unwrapApi, unwrapCode, unwrapOk } from '~/utils/contracts'

type FetchLikeError = {
  name?: string
  cause?: { name?: string }
  statusCode?: number
  response?: { status?: number }
  data?: unknown
  message?: string
}

export class ApiRequestError extends Error {
  readonly status?: number
  readonly fields: ApiFieldError[]

  constructor(message: string, options: { status?: number; fields?: ApiFieldError[] } = {}) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = options.status
    this.fields = options.fields || []
  }
}

function isFetchLikeError(error: unknown): error is FetchLikeError {
  return typeof error === 'object' && error !== null
}

export function isAbortError(error: unknown): boolean {
  if (!isFetchLikeError(error)) return false
  return error.name === 'AbortError' || error.cause?.name === 'AbortError'
}

export function useApi() {
  const config = useRuntimeConfig()
  const auth = useAuth()

  async function request<T>(path: string, options: Parameters<typeof $fetch<T>>[1] = {}): Promise<T> {
    auth.hydrate()
    try {
      return await $fetch<T>(path, {
        baseURL: String(config.public.apiBase || ''),
        ...options,
        headers: {
          Accept: 'application/json',
          ...(auth.token.value ? { Authorization: `Bearer ${auth.token.value}` } : {}),
          ...(options.headers as Record<string, string> | undefined)
        }
      })
    } catch (error: unknown) {
      if (isAbortError(error)) throw error
      const fetchError = isFetchLikeError(error) ? error : {}
      const status = fetchError.statusCode || fetchError.response?.status
      if (status === 401) {
        auth.clear()
        if (import.meta.client && !['/login', '/register'].includes(location.pathname)) {
          await navigateTo(`/login?redirect=${encodeURIComponent(location.pathname)}`)
        }
      }
      let errorData: unknown = fetchError.data
      if (typeof Blob !== 'undefined' && errorData instanceof Blob) {
        try {
          const text = await errorData.text()
          errorData = JSON.parse(text)
        } catch {
          errorData = undefined
        }
      }
      const data = errorData && typeof errorData === 'object' ? errorData as Record<string, unknown> : {}
      const message = String(data.message || data.msg || fetchError.message || (status ? `请求失败（${status}）` : '网络请求失败'))
      throw new ApiRequestError(message, { status, fields: normalizeFieldErrors(data.errors || data.detail) })
    }
  }

  async function ok<T>(path: string, options?: Parameters<typeof $fetch<OkEnvelope<T>>>[1]): Promise<T> {
    const body = await request<OkEnvelope<T>>(path, options)
    return unwrapOk(body)
  }

  async function legacyCode<T>(path: string, options?: Parameters<typeof $fetch<CodeEnvelope<T>>>[1]): Promise<T> {
    const body = await request<CodeEnvelope<T>>(path, options)
    return unwrapCode(body)
  }

  async function data<T>(path: string, options?: Parameters<typeof $fetch<ApiEnvelope<T>>>[1]): Promise<T> {
    const body = await request<ApiEnvelope<T>>(path, options)
    return unwrapApi(body)
  }

  return { request, ok, legacyCode, data }
}
