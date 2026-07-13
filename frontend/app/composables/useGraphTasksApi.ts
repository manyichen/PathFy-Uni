export function useGraphTasksApi() {
  const api = useApi()
  const guard = () => api.ok<any>('/api/graph/guard')
  const stats = () => api.ok<Record<string, number>>('/api/graph/stats')
  const tasks = (params: { page?: number; status?: string; task_type?: string } = {}) => {
    const query = new URLSearchParams({ page: String(params.page || 1), page_size: '20' })
    if (params.status) query.set('status', params.status)
    if (params.task_type) query.set('task_type', params.task_type)
    return api.ok<any>(`/api/graph/tasks?${query}`)
  }
  const task = (id: number | string) => api.ok<any>(`/api/graph/tasks/${id}`)
  const create = (body: FormData) => api.ok<any>('/api/graph/tasks', { method: 'POST', body })
  const confirm = (id: number) => api.ok<any>(`/api/graph/tasks/${id}/confirm`, { method: 'POST', body: {} })
  const reject = (id: number, reason: string) => api.ok<any>(`/api/graph/tasks/${id}/reject`, { method: 'POST', body: { reason } })
  const cancel = (id: number) => api.ok<any>(`/api/graph/tasks/${id}/cancel`, { method: 'POST', body: {} })
  return { guard, stats, tasks, task, create, confirm, reject, cancel }
}
