import type { CareerReport, ReportDetailResponse, ReportPlan, ReportTarget, ResumeOption } from '~/types/api'
import { useProfileApi } from '~/composables/api/useProfileApi'
import { clearReportCache, readReportCache, writeReportCache, type ReportWorkspaceCache } from '~/utils/cache/report-cache'
import type { ReportPathAnimationKind } from '~/types/report-path'

export function reportTargetKey(item: ReportTarget | undefined): string {
  return String(item?.job_id || item?.id || '')
}

export function useReportWorkspace() {
  const auth = useAuth()
  const profileApi = useProfileApi()
  const toast = useToast()
  const ready = ref(false)
  const operation = ref('')
  const resumes = ref<ResumeOption[]>([])
  const resumeId = ref<number>()
  const targets = ref<ReportTarget[]>([])
  const primaryJobId = ref('')
  const reportPrimaryJobId = ref('')
  const goal = ref('fit')
  const reportId = ref<number>()
  const reportTitle = ref('')
  const report = ref<CareerReport>()
  const activeJobId = ref('')
  const selectedMonth = ref(0)
  const configCollapsed = ref(false)
  const resetOpen = ref(false)
  const reportPathAnimationRevision = ref(0)
  const reportPathAnimationKind = ref<ReportPathAnimationKind>('none')

  const cacheUserId = computed(() => auth.user.value?.id || 'guest')
  const reportTargets = computed(() => report.value?.targets || [])
  const activeTarget = computed(() => reportTargets.value.find(item => reportTargetKey(item) === activeJobId.value) || reportTargets.value[0])
  const activePlan = computed<ReportPlan | undefined>(() => report.value?.plans_by_target?.find(item => item.job_id === activeJobId.value) || report.value?.plans_by_target?.[0])
  const activeLine = computed(() => {
    const planLineId = activePlan.value?.line_id
    const lines = report.value?.development_lines?.lines || []
    return lines.find(item => item.line_id === planLineId || item.target_job_id === activeJobId.value) || lines[0]
  })
  const activeAdjustments = computed(() => (report.value?.development_lines?.adjustments || []).filter(item => !activeLine.value?.line_id || item.line_id === activeLine.value.line_id))
  const workspaceStatus = computed(() => report.value
    ? `报告 #${reportId.value || '-'} · ${targets.value.length} 个目标`
    : targets.value.length ? `已选择 ${targets.value.length} 个目标` : '等待选择目标')

  function snapshot(): ReportWorkspaceCache {
    return {
      resumeId: resumeId.value,
      selectedResumeId: resumeId.value,
      targets: targets.value,
      selectedTargets: targets.value,
      primaryJobId: primaryJobId.value,
      reportPrimaryJobId: reportPrimaryJobId.value,
      goal: goal.value,
      reportMatchGoal: goal.value,
      reportId: reportId.value,
      reportTitle: reportTitle.value,
      report: report.value,
      reportSnapshot: report.value,
      activeJobId: activeJobId.value,
      selectedMonth: selectedMonth.value,
      selectedCanvasMonth: selectedMonth.value,
      configCollapsed: configCollapsed.value,
      configRailCollapsed: configCollapsed.value
    }
  }

  function persist() {
    if (ready.value) writeReportCache(cacheUserId.value, snapshot())
  }

  function triggerReportPathAnimation(kind: Exclude<ReportPathAnimationKind, 'none'>) {
    reportPathAnimationKind.value = kind
    reportPathAnimationRevision.value += 1
  }

  function selectTarget(jobId: string) {
    if (!reportTargets.value.some(item => reportTargetKey(item) === jobId)) return
    activeJobId.value = jobId
    const months = (activeLine.value?.timeline || []).map(item => Math.round(Number(item.month) || 0))
    selectedMonth.value = months.includes(selectedMonth.value) ? selectedMonth.value : 0
  }

  function applyCachedWorkspace(cache: Partial<ReportWorkspaceCache>) {
    resumeId.value = cache.resumeId || cache.selectedResumeId || resumeId.value
    targets.value = Array.isArray(cache.targets) ? cache.targets : Array.isArray(cache.selectedTargets) ? cache.selectedTargets : []
    const cachedTargetIds = new Set(targets.value.map(reportTargetKey))
    primaryJobId.value = cachedTargetIds.has(String(cache.primaryJobId || ''))
      ? String(cache.primaryJobId)
      : reportTargetKey(targets.value[0])
    reportPrimaryJobId.value = cachedTargetIds.has(String(cache.reportPrimaryJobId || ''))
      ? String(cache.reportPrimaryJobId)
      : primaryJobId.value
    goal.value = cache.goal || cache.reportMatchGoal || 'fit'
    reportId.value = cache.reportId
    reportTitle.value = cache.reportTitle || ''
    report.value = cache.report || cache.reportSnapshot
    activeJobId.value = cache.activeJobId || reportTargetKey(report.value?.targets?.[0])
    selectedMonth.value = Math.max(0, Math.min(12, Math.round(cache.selectedMonth ?? cache.selectedCanvasMonth ?? 0)))
    configCollapsed.value = Boolean(cache.configCollapsed ?? cache.configRailCollapsed ?? report.value)
  }

  function applyReportResponse(data: Pick<ReportDetailResponse, 'report_id' | 'report' | 'primary_job_id' | 'target_job_ids' | 'title'>, preferredJobId = activeJobId.value) {
    const previousReportId = reportId.value
    reportId.value = data.report_id
    reportTitle.value = data.title || (previousReportId === data.report_id ? reportTitle.value : '')
    report.value = data.report
    if (data.report.targets?.length) targets.value = data.report.targets.map(item => ({ job_id: reportTargetKey(item), ...item }))
    const ids = new Set((data.report.targets || []).map(reportTargetKey))
    primaryJobId.value = ids.has(String(data.primary_job_id || ''))
      ? String(data.primary_job_id)
      : reportTargetKey(data.report.targets?.[0])
    reportPrimaryJobId.value = primaryJobId.value
    activeJobId.value = ids.has(preferredJobId) ? preferredJobId : ids.has(String(data.primary_job_id || '')) ? String(data.primary_job_id) : reportTargetKey(data.report.targets?.[0])
    const availableMonths = new Set((activeLine.value?.timeline || []).map(item => Math.round(Number(item.month) || 0)))
    if (!availableMonths.has(selectedMonth.value)) selectedMonth.value = 0
    configCollapsed.value = true
    persist()
  }

  async function initialize(): Promise<ReportWorkspaceCache | undefined> {
    auth.hydrate()
    const cache = readReportCache(cacheUserId.value)
    if (cache) applyCachedWorkspace(cache)
    try {
      resumes.value = await profileApi.listResumes()
      resumeId.value ||= resumes.value[0]?.id
    } catch (error) {
      toast.add({ title: error instanceof Error ? error.message : '画像列表加载失败', color: 'error' })
    }
    ready.value = true
    persist()
    return cache
  }

  function resetWorkspace(successTitle = '报告工作区已清空') {
    clearReportCache(cacheUserId.value)
    resumeId.value = resumes.value[0]?.id
    targets.value = []
    primaryJobId.value = ''
    reportPrimaryJobId.value = ''
    goal.value = 'fit'
    reportId.value = undefined
    reportTitle.value = ''
    report.value = undefined
    activeJobId.value = ''
    selectedMonth.value = 0
    configCollapsed.value = false
    resetOpen.value = false
    reportPathAnimationRevision.value = 0
    reportPathAnimationKind.value = 'none'
    persist()
    toast.add({ title: successTitle, color: 'success' })
  }

  watch([resumeId, targets, primaryJobId, goal, activeJobId, selectedMonth, configCollapsed], persist, { deep: true })
  watch(report, persist, { deep: true })

  return {
    operation, resumes, resumeId, targets, primaryJobId, reportPrimaryJobId, goal, reportId, reportTitle, report, activeJobId, selectedMonth,
    configCollapsed, resetOpen, reportPathAnimationRevision, reportPathAnimationKind,
    reportTargets, activeTarget, activePlan, activeLine, activeAdjustments,
    workspaceStatus, persist, selectTarget, applyReportResponse, triggerReportPathAnimation, initialize, resetWorkspace
  }
}

export type ReportWorkspace = ReturnType<typeof useReportWorkspace>
