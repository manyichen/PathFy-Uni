import type { ProfileDetail, ResumeOption } from '~/types/profile'
import { asArray, normalizeProfileDetail, normalizeResumeOption } from '~/utils/normalizers'

export function useProfileApi() {
  const api = useApi()

  const listResumes = async (): Promise<ResumeOption[]> =>
    asArray(await api.legacyCode<unknown>('/api/profile/resumes')).map(normalizeResumeOption).filter(item => item.id > 0)

  const getPortrait = async (id: number): Promise<ProfileDetail> =>
    normalizeProfileDetail(await api.legacyCode<unknown>(`/api/profile/result/${id}`))

  const uploadPortrait = async (body: FormData): Promise<ProfileDetail> =>
    normalizeProfileDetail(await api.legacyCode<unknown>('/api/profile/upload', { method: 'POST', body }))

  return { listResumes, getPortrait, uploadPortrait }
}
