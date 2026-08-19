import { z } from 'zod'
import type { GraphChangeGroup, GraphGuard, GraphStats, GraphTask, GraphTaskList } from '~/types/graph-task'
import { asArray, asNumber, asRecord, asString } from '~/utils/normalizers'

const taskSchema = z.object({ id: z.coerce.number(), status: z.string() }).passthrough()
const taskListSchema = z.object({ items: z.array(z.unknown()).default([]), total: z.coerce.number().default(0), page: z.coerce.number().default(1), page_size: z.coerce.number().default(20) }).passthrough()

function normalizeTask(value: unknown): GraphTask {
  const row = taskSchema.parse(value)
  return { ...row, id: row.id, status: row.status, task_type: asString(row.task_type) || undefined }
}

export function useGraphTasksApi() {
  const api = useApi()
  const guard = async (): Promise<GraphGuard> => asRecord(await api.ok<unknown>('/api/graph/guard')) as GraphGuard
  const stats = async (): Promise<GraphStats> => asRecord(await api.ok<unknown>('/api/graph/stats')) as GraphStats
  const tasks = async (params: { page?: number; status?: string; task_type?: string; requested_by?: number; created_from?: string; created_to?: string } = {}): Promise<GraphTaskList> => {
    const query = new URLSearchParams({ page: String(params.page || 1), page_size: '20' })
    if (params.status) query.set('status', params.status)
    if (params.task_type) query.set('task_type', params.task_type)
    if (params.requested_by) query.set('requested_by', String(params.requested_by))
    if (params.created_from) query.set('created_from', params.created_from)
    if (params.created_to) query.set('created_to', params.created_to)
    const row = taskListSchema.parse(await api.ok<unknown>(`/api/graph/tasks?${query}`))
    return { ...row, items: asArray(row.items).map(normalizeTask), total: asNumber(row.total), page: asNumber(row.page, 1), page_size: asNumber(row.page_size, 20) }
  }
  const task = async (id: number | string): Promise<GraphTask> => normalizeTask(await api.ok<unknown>(`/api/graph/tasks/${id}`))
  const changes = async (id: number | string, params: { group?: string; page?: number } = {}): Promise<GraphChangeGroup> => {
    const query = new URLSearchParams({ page: String(params.page || 1), page_size: '20' })
    if (params.group) query.set('group', params.group)
    return asRecord(await api.ok<unknown>(`/api/graph/tasks/${id}/changes?${query}`)) as GraphChangeGroup
  }
  const downloadFile = (id: number | string, role: string) => api.request<Blob>(`/api/graph/tasks/${id}/files/${encodeURIComponent(role)}/download`, { responseType: 'blob' })
  const create = (body: FormData | Record<string, unknown>) => api.ok<GraphTask>('/api/graph/tasks', { method: 'POST', body })
  const confirm = (id: number) => api.ok<GraphTask>(`/api/graph/tasks/${id}/confirm`, { method: 'POST', body: {} })
  const reject = (id: number, reason: string) => api.ok<GraphTask>(`/api/graph/tasks/${id}/reject`, { method: 'POST', body: { reason } })
  const cancel = (id: number) => api.ok<GraphTask>(`/api/graph/tasks/${id}/cancel`, { method: 'POST', body: {} })
  return { guard, stats, tasks, task, changes, downloadFile, create, confirm, reject, cancel }
}
