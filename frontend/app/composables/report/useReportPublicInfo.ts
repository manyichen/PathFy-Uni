import type { PublicInfoState, ReportTarget } from '~/types/api'
import { useReportApi } from '~/composables/api/useReportApi'
import { reportTargetKey } from './useReportWorkspace'
import { isAbortError } from '~/composables/useApi'

export function useReportPublicInfo() {
  const reportApi = useReportApi()
  const states = reactive<Record<string, PublicInfoState>>({})
  const controllers = new Map<string, AbortController>()

  async function load(item: ReportTarget, forceRefresh = false) {
    const key = reportTargetKey(item)
    const title = item.track_profile?.job_title || item.title || item.display_title || ''
    if (!key && !title) return
    if (states[key]?.data && !forceRefresh) return
    controllers.get(key)?.abort()
    const controller = new AbortController()
    controllers.set(key, controller)
    states[key] = { ...states[key], loading: true, error: undefined }
    try {
      const data = await reportApi.publicInfo({ job_id: key, job_title: title, force_refresh: forceRefresh }, { signal: controller.signal })
      if (controllers.get(key) !== controller) return
      states[key] = { data }
    } catch (cause) {
      if (isAbortError(cause)) return
      states[key] = { data: states[key]?.data, error: cause instanceof Error ? cause.message : '近期公开信息加载失败' }
    } finally {
      if (controllers.get(key) === controller) controllers.delete(key)
    }
  }

  function clear() {
    for (const controller of controllers.values()) controller.abort()
    controllers.clear()
    for (const key of Object.keys(states)) delete states[key]
  }
  return { states, load, clear }
}
