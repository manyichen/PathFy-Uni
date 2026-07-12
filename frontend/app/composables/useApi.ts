import type { CodeEnvelope, OkEnvelope } from '~/types/api'
import { unwrapCode, unwrapOk } from '~/utils/contracts'

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
    } catch (error: any) {
      if (error?.statusCode === 401 || error?.response?.status === 401) {
        auth.clear()
        if (import.meta.client) await navigateTo(`/login?redirect=${encodeURIComponent(location.pathname)}`)
      }
      const data = error?.data as Record<string, unknown> | undefined
      throw new Error(String(data?.message || data?.msg || error?.message || '请求失败'))
    }
  }

  async function ok<T>(path: string, options?: Parameters<typeof $fetch<OkEnvelope<T>>>[1]): Promise<T> {
    const body = await request<OkEnvelope<T>>(path, options)
    return unwrapOk(body)
  }

  async function code<T>(path: string, options?: Parameters<typeof $fetch<CodeEnvelope<T>>>[1]): Promise<T> {
    const body = await request<CodeEnvelope<T>>(path, options)
    return unwrapCode(body)
  }

  return { request, ok, code }
}
