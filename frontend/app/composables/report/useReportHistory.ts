import type { CareerReport } from '~/types/api'
import { useReportApi } from '~/composables/api/useReportApi'
import type { ReportWorkspace } from './useReportWorkspace'

export function useReportHistory(workspace: ReportWorkspace, afterRestore?: () => Promise<void>) {
  const reportApi = useReportApi()
  const items = ref<Awaited<ReturnType<typeof reportApi.history>>>([])
  const open = ref(false)
  const loading = ref(false)
  const restoringId = ref<number>()
  const error = ref('')
  const toast = useToast()

  async function load() {
    open.value = true
    loading.value = true
    error.value = ''
    try { items.value = await reportApi.history() }
    catch (cause) { error.value = cause instanceof Error ? cause.message : '历史报告加载失败' }
    finally { loading.value = false }
  }

  async function restore(id: number, fallback?: CareerReport, preferredJobId = workspace.activeJobId.value) {
    workspace.operation.value = 'restore'
    restoringId.value = id
    error.value = ''
    try {
      const data = await reportApi.detail(id)
      workspace.applyReportResponse(data, preferredJobId)
      open.value = false
      await afterRestore?.()
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '报告恢复失败'
      if (fallback) {
        workspace.applyReportResponse({
          report_id: id,
          report: fallback,
          primary_job_id: workspace.reportPrimaryJobId.value,
          target_job_ids: (fallback.targets || []).map(item => String(item.job_id || item.id || '')).filter(Boolean)
        }, preferredJobId)
        open.value = false
        toast.add({ title: '已加载本地报告副本', description: '服务器详情暂时不可用，待网络恢复后会自动以服务器数据为准。', color: 'warning' })
      }
    } finally { workspace.operation.value = ''; restoringId.value = undefined }
  }

  return { items, open, loading, restoringId, error, load, restore }
}
