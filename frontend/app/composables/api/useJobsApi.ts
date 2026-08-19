import type { JobAssistantMessage, JobAssistantResponse, JobAssistantSession, JobCard, JobDetail, JobListResult } from '~/types/job'
import type { CareerLateralResponse, CareerPromotionResponse, CareerTransitionResponse } from '~/types/career-graph'
import { asArray, asNumber, asRecord, asString, normalizeJobCard, optionalNumber } from '~/utils/normalizers'
import { createExpiringCache } from '~/utils/request-performance'

const jobDetailCache = createExpiringCache<JobDetail>(5 * 60 * 1000)

interface CareerPathRequestOptions {
  signal?: AbortSignal
  timeout?: number
}

export function clearJobDetailCache(id?: string) {
  jobDetailCache.clear(id)
}

function normalizeMessage(value: unknown): JobAssistantMessage {
  const row = asRecord(value)
  return {
    ...row,
    id: optionalNumber(row.id),
    role: asString(row.role, 'assistant'),
    content: asString(row.content),
    is_saved: Boolean(row.is_saved),
    created_at: asString(row.created_at) || undefined,
    result_job_ids_json: asArray(row.result_job_ids_json).map(item => asString(item)).filter(Boolean)
  }
}

function normalizeSession(value: unknown): JobAssistantSession {
  const row = asRecord(value)
  return {
    ...row,
    id: asNumber(row.id),
    title: asString(row.title) || undefined,
    created_at: asString(row.created_at) || undefined,
    updated_at: asString(row.updated_at) || undefined,
    last_message_at: asString(row.last_message_at) || undefined
  }
}

function normalizeAssistant(value: unknown): JobAssistantResponse {
  const row = asRecord(value)
  return {
    ...row,
    session_id: optionalNumber(row.session_id),
    reply: asString(row.reply) || undefined,
    message: asString(row.message) || undefined,
    jobs: asArray(row.jobs).map(normalizeJobCard),
    messages: asArray(row.messages).map(normalizeMessage),
    assistant_message: row.assistant_message ? normalizeMessage(row.assistant_message) : undefined,
    user_message: row.user_message ? normalizeMessage(row.user_message) : undefined,
    session: row.session ? normalizeSession(row.session) : undefined,
    filters: asRecord(row.filters)
  }
}

export function useJobsApi() {
  const api = useApi()

  async function list(params: { q?: string; page?: number; pageSize?: number; sort?: string; seed?: string } = {}, options: { signal?: AbortSignal } = {}): Promise<JobListResult> {
    const query = new URLSearchParams({ page: String(params.page || 1), page_size: String(params.pageSize || 20) })
    if (params.q) query.set('q', params.q)
    if (params.sort && params.sort !== 'default') query.set('sort', params.sort)
    if (params.seed) query.set('seed', params.seed)
    const row = asRecord(await api.ok<unknown>(`/api/jobs?${query}`, { signal: options.signal }))
    return {
      ...row,
      jobs: asArray(row.jobs).map(normalizeJobCard),
      total: asNumber(row.total),
      page: asNumber(row.page, 1),
      page_size: asNumber(row.page_size, params.pageSize || 20),
      total_pages: asNumber(row.total_pages, 1),
      seed: typeof row.seed === 'string' ? row.seed : undefined
    }
  }

  const detail = async (id: string, options: { signal?: AbortSignal; force?: boolean } = {}): Promise<JobDetail> => {
    const cached = options.force ? undefined : jobDetailCache.get(id)
    if (cached) return cached
    const value = normalizeJobCard(await api.ok<unknown>(`/api/jobs/${encodeURIComponent(id)}`, { signal: options.signal, timeout: 15_000, retry: 0 })) as JobDetail
    jobDetailCache.set(id, value)
    return value
  }
  const promotion = (id: string, options: CareerPathRequestOptions = {}) => api.ok<CareerPromotionResponse>(`/api/jobs/${encodeURIComponent(id)}/promotion-path?max_depth=4&max_paths=3`, options)
  const lateral = (id: string, options: CareerPathRequestOptions = {}) => api.ok<CareerLateralResponse>(`/api/jobs/${encodeURIComponent(id)}/lateral-paths?max_paths=6`, options)
  const transition = (from: string, to: string, options: CareerPathRequestOptions = {}) => api.ok<CareerTransitionResponse>('/api/jobs/transition-analysis', { method: 'POST', body: { from_job_id: from, to_job_id: to }, ...options })
  const chat = async (message: string, sessionId?: number) => normalizeAssistant(await api.ok<unknown>('/api/jobs/assistant/chat', { method: 'POST', body: { message, session_id: sessionId } }))
  const sessions = async () => {
    const row = asRecord(await api.ok<unknown>('/api/jobs/assistant/sessions'))
    return { sessions: asArray(row.sessions).map(normalizeSession).filter(item => item.id > 0) }
  }
  const session = async (id: number) => normalizeAssistant(await api.ok<unknown>(`/api/jobs/assistant/sessions/${id}`))
  const saveMessage = (id: number) => api.ok<Record<string, unknown>>(`/api/jobs/assistant/messages/${id}/save`, { method: 'POST', body: {} })
  return { list, detail, promotion, lateral, transition, chat, sessions, session, saveMessage }
}
