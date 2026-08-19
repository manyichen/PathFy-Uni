import type { PersonalityAnswer, PersonalityQuestion, PersonalityResult } from '~/types/personality'
import { asArray, asRecord, normalizePersonalityQuestion, normalizePersonalityResult } from '~/utils/normalizers'

export function usePersonalityApi() {
  const api = useApi()

  const questions = async (): Promise<PersonalityQuestion[]> =>
    asArray(await api.legacyCode<unknown>('/api/personality/questions')).map(normalizePersonalityQuestion).filter(item => item.id > 0)

  const submit = async (answers: PersonalityAnswer[]): Promise<PersonalityResult> =>
    normalizePersonalityResult(await api.legacyCode<unknown>('/api/personality/submit', { method: 'POST', body: { answers } }))

  const latest = async (): Promise<PersonalityResult | undefined> => {
    const raw = asRecord(await api.legacyCode<unknown>('/api/personality/me/latest'))
    if (raw.status === 'missing' || !raw.profile_id && !raw.id) return undefined
    return normalizePersonalityResult(raw)
  }

  const history = async (limit = 30): Promise<PersonalityResult[]> =>
    asArray(await api.legacyCode<unknown>(`/api/personality/me/profiles?limit=${Math.max(1, Math.min(limit, 80))}`))
      .map(normalizePersonalityResult)
      .filter(item => Boolean(item.profile_id))

  const detail = async (profileId: number): Promise<PersonalityResult> =>
    normalizePersonalityResult(await api.legacyCode<unknown>(`/api/personality/profiles/${profileId}`))

  const activate = async (profileId: number): Promise<PersonalityResult> =>
    normalizePersonalityResult(await api.legacyCode<unknown>(`/api/personality/profiles/${profileId}/activate`, { method: 'POST' }))

  const setPersonalization = async (profileId: number, enabled: boolean): Promise<PersonalityResult> =>
    normalizePersonalityResult(await api.legacyCode<unknown>(`/api/personality/profiles/${profileId}/preferences`, {
      method: 'PATCH',
      body: { personalization_enabled: enabled }
    }))

  const remove = async (profileId: number): Promise<{ deleted_profiles?: number; scrubbed_match_runs?: number }> =>
    asRecord(await api.legacyCode<unknown>(`/api/personality/profiles/${profileId}`, { method: 'DELETE' }))

  return { questions, submit, latest, history, detail, activate, setPersonalization, remove }
}
