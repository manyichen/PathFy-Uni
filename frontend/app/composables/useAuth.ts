import type { AuthUser } from '~/types/api'

import { AUTH_TOKEN_KEY, AUTH_USER_KEY, cacheKeysForLogout, parseStoredUser } from '~/utils/contracts'

export function useAuth() {
  const token = useState<string | null>('auth-token', () => null)
  const user = useState<AuthUser | null>('auth-user', () => null)
  const ready = useState<boolean>('auth-ready', () => false)

  function hydrate() {
    if (!import.meta.client || ready.value) return
    token.value = localStorage.getItem(AUTH_TOKEN_KEY)
    user.value = parseStoredUser(localStorage.getItem(AUTH_USER_KEY))
    ready.value = true
  }

  function save(nextToken: string, nextUser: AuthUser) {
    token.value = nextToken
    user.value = nextUser
    if (import.meta.client) {
      localStorage.setItem(AUTH_TOKEN_KEY, nextToken)
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(nextUser))
    }
  }

  function clear() {
    const id = user.value?.id
    if (import.meta.client) {
      for (const key of cacheKeysForLogout(id)) localStorage.removeItem(key)
      localStorage.removeItem(AUTH_TOKEN_KEY)
      localStorage.removeItem(AUTH_USER_KEY)
    }
    token.value = null
    user.value = null
  }

  if (import.meta.client) hydrate()
  return { token, user, ready, isAuthenticated: computed(() => Boolean(token.value)), isAdmin: computed(() => Boolean(user.value?.is_admin)), hydrate, save, clear }
}
