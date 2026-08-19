import type { MatchHistoryItem, MatchHistoryResponse, ReportTarget } from '~/types/api'
import { useMatchApi } from '~/composables/api/useMatchApi'
import { useReportApi } from '~/composables/api/useReportApi'
import type { ReportWorkspace } from './useReportWorkspace'
import { reportTargetKey } from './useReportWorkspace'

export function useReportTargets(workspace: ReportWorkspace) {
  const matchApi = useMatchApi()
  const reportApi = useReportApi()
  const toast = useToast()
  const pickerOpen = ref(false)
  const explorerOpen = ref(false)
  const matchOpen = ref(false)
  const matchHistory = ref<MatchHistoryResponse['items']>([])
  const matchHistoryLoading = ref(false)
  const matchHistoryError = ref('')
  const selectedIds = computed(() => workspace.targets.value.map(reportTargetKey))

  function addTarget(item: ReportTarget) {
    if (workspace.targets.value.length >= 5) return void toast.add({ title: '最多选择 5 个目标', color: 'warning' })
    const normalized = { ...item, job_id: reportTargetKey(item) }
    if (!workspace.targets.value.some(target => reportTargetKey(target) === reportTargetKey(normalized))) {
      workspace.targets.value.push(normalized)
      workspace.primaryJobId.value ||= reportTargetKey(normalized)
    }
  }

  function removeTarget(index: number) {
    const [removed] = workspace.targets.value.splice(index, 1)
    if (reportTargetKey(removed) === workspace.primaryJobId.value) {
      workspace.primaryJobId.value = reportTargetKey(workspace.targets.value[0])
    }
  }
  function clearTargets() {
    workspace.targets.value = []
    workspace.primaryJobId.value = ''
  }
  function setPrimary(jobId: string) {
    if (workspace.targets.value.some(target => reportTargetKey(target) === jobId)) {
      workspace.primaryJobId.value = jobId
      workspace.activeJobId.value = jobId
      workspace.persist()
    }
  }

  async function openMatchHistory() {
    matchOpen.value = true
    matchHistoryLoading.value = true
    matchHistoryError.value = ''
    try { matchHistory.value = await matchApi.history() }
    catch (error) { matchHistoryError.value = error instanceof Error ? error.message : '匹配记录加载失败' }
    finally { matchHistoryLoading.value = false }
  }

  async function importMatch(runId: number) {
    workspace.operation.value = 'import'
    try {
      const data = await reportApi.importFromMatch(runId, 5)
      workspace.targets.value = (data.targets || []).slice(0, 5)
      workspace.primaryJobId.value = reportTargetKey(workspace.targets.value[0])
      workspace.goal.value = data.match_goal === 'stretch' ? 'stretch' : 'fit'
      if (workspace.resumes.value.some(item => item.id === data.resume_id)) workspace.resumeId.value = data.resume_id
      matchOpen.value = false
      workspace.persist()
      toast.add({ title: `已导入 ${workspace.targets.value.length} 个匹配目标`, color: 'success' })
    } catch (error) { toast.add({ title: error instanceof Error ? error.message : '导入失败', color: 'error' }) }
    finally { workspace.operation.value = '' }
  }

  return { pickerOpen, explorerOpen, matchOpen, matchHistory, matchHistoryLoading, matchHistoryError, selectedIds, addTarget, removeTarget, clearTargets, setPrimary, openMatchHistory, importMatch }
}
