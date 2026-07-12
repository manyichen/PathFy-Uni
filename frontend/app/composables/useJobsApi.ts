import type { JobCard } from '~/types/api'

export function useJobsApi() {
  const api = useApi()
  async function list(params: { q?: string; page?: number; pageSize?: number; sort?: string; seed?: string } = {}) {
    const query = new URLSearchParams({ page: String(params.page || 1), page_size: String(params.pageSize || 20) })
    if (params.q) query.set('q', params.q)
    if (params.sort && params.sort !== 'default') query.set('sort', params.sort)
    if (params.seed) query.set('seed', params.seed)
    return api.ok<{ jobs: JobCard[]; total: number; page: number; page_size: number; total_pages: number; seed?: string }>(`/api/jobs?${query}`)
  }
  const detail = (id: string) => api.ok<any>(`/api/jobs/${encodeURIComponent(id)}`)
  const promotion = (id: string) => api.ok<any>(`/api/jobs/${encodeURIComponent(id)}/promotion-path?max_depth=4&max_paths=3`)
  const lateral = (id: string) => api.ok<any>(`/api/jobs/${encodeURIComponent(id)}/lateral-paths?max_paths=6`)
  const transition = (from: string, to: string) => api.ok<any>('/api/jobs/transition-analysis', { method: 'POST', body: { from_job_id: from, to_job_id: to } })
  const chat = (message: string, sessionId?: number) => api.ok<any>('/api/jobs/assistant/chat', { method: 'POST', body: { message, session_id: sessionId } })
  const sessions = () => api.ok<{ sessions: any[] }>('/api/jobs/assistant/sessions')
  const session = (id: number) => api.ok<any>(`/api/jobs/assistant/sessions/${id}`)
  const saveMessage = (id: number) => api.ok<any>(`/api/jobs/assistant/messages/${id}/save`, { method: 'POST', body: {} })
  return { list, detail, promotion, lateral, transition, chat, sessions, session, saveMessage }
}
