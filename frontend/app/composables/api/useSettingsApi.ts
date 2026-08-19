import type { PreferencesPayload, SystemSettings } from '~/types/settings'

export function useSettingsApi() {
  const api = useApi()
  const admin = () => api.ok<SystemSettings>('/api/admin/settings')
  const publish = (baseRevision: number | null, settings: Record<string, unknown>) => api.ok<SystemSettings>('/api/admin/settings/publish', { method: 'POST', body: { base_revision: baseRevision, settings } })
  const history = (page = 1) => api.ok<{ items: SystemSettings[]; [key: string]: unknown }>(`/api/admin/settings/history?page=${page}&page_size=20`)
  const revision = (value: number) => api.ok<SystemSettings>(`/api/admin/settings/revisions/${value}`)
  const preferences = () => api.ok<PreferencesPayload>('/api/account/preferences')
  const savePreferences = (body: Record<string, unknown>) => api.ok<PreferencesPayload>('/api/account/preferences', { method: 'PATCH', body })
  return { admin, publish, history, revision, preferences, savePreferences }
}
