import { z } from 'zod'
import type { MatchHistoryItem, MatchPreviewResult, MatchRunRequest } from '~/types/match'
import { asArray, asNumber, asRecord, asString, normalizeMatchPreview } from '~/utils/normalizers'

const previewResponseSchema = z.object({}).passthrough().refine(value => {
  const row = value as Record<string, unknown>
  return Array.isArray(row.jobs) || Array.isArray(row.ranked_jobs) || Array.isArray(row.results)
}, '匹配结果缺少岗位列表')

const historyResponseSchema = z.object({ items: z.array(z.unknown()).default([]) }).passthrough()

function normalizeHistoryItem(value: unknown): MatchHistoryItem {
  const row = asRecord(value)
  return {
    ...row,
    run_id: asNumber(row.run_id || row.id),
    resume_id: Number.isFinite(Number(row.resume_id)) ? Number(row.resume_id) : undefined,
    student_name: asString(row.student_name || row.name) || undefined,
    match_goal: asString(row.match_goal) || undefined,
    q: asString(row.q) || undefined,
    location_q: asString(row.location_q) || undefined,
    refine_with_llm: Boolean(row.refine_with_llm),
    llm_ok: Boolean(row.llm_ok),
    returned: Number.isFinite(Number(row.returned)) ? Number(row.returned) : undefined,
    created_at: asString(row.created_at) || undefined,
    preference_mode: (['explain', 'tie_break'].includes(asString(row.preference_mode)) ? asString(row.preference_mode) : 'off') as MatchHistoryItem['preference_mode'],
    personality_profile_id: Number.isFinite(Number(row.personality_profile_id)) ? Number(row.personality_profile_id) : undefined,
    preference_status: asString(row.preference_status) || undefined
  }
}

export function useMatchApi() {
  const api = useApi()

  const preview = async (body: MatchRunRequest, options: { signal?: AbortSignal; timeout?: number } = {}): Promise<MatchPreviewResult> => {
    const raw = await api.ok<unknown>('/api/match/preview', {
      method: 'POST',
      body,
      signal: options.signal,
      timeout: options.timeout
    })
    return normalizeMatchPreview(previewResponseSchema.parse(raw))
  }

  const history = async (limit = 30): Promise<MatchHistoryItem[]> => {
    const raw = historyResponseSchema.parse(await api.ok<unknown>(`/api/match/history?limit=${limit}`))
    return asArray(raw.items).map(normalizeHistoryItem).filter(item => item.run_id > 0)
  }

  const historyDetail = async (runId: number): Promise<MatchPreviewResult> => {
    const raw = await api.ok<unknown>(`/api/match/history/${runId}`)
    return normalizeMatchPreview(previewResponseSchema.parse(raw))
  }

  return { preview, history, historyDetail }
}
