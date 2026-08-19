import type { ReportWorkspace } from './useReportWorkspace'
import type { ReportEnrichmentState, ReportEnrichmentStatus, ReportPdfExportOptions, ReportRefreshScope } from '~/types/report'
import { useReportApi } from '~/composables/api/useReportApi'
import { reportTargetKey } from './useReportWorkspace'

export function useReportGeneration(workspace: ReportWorkspace, afterReportLoaded?: () => Promise<void>) {
  const reportApi = useReportApi()
  const toast = useToast()
  const enrichError = ref('')
  const enrichState = ref<ReportEnrichmentState | 'idle'>('idle')
  const enrichStatus = ref<ReportEnrichmentStatus>()
  const exportState = ref<'idle' | 'preparing' | 'failed'>('idle')
  const exportError = ref('')

  let pollVersion = 0

  const delay = (milliseconds: number) => new Promise(resolve => setTimeout(resolve, milliseconds))

  async function pollEnrichment(id: number, version: number, showToast: boolean) {
    let consecutiveStatusFailures = 0
    for (let attempt = 0; attempt < 150 && version === pollVersion; attempt += 1) {
      let status: Awaited<ReturnType<typeof reportApi.enrichmentStatus>>
      try {
        status = await reportApi.enrichmentStatus(id)
        consecutiveStatusFailures = 0
      } catch (error) {
        consecutiveStatusFailures += 1
        if (consecutiveStatusFailures >= 3) throw error
        await delay(2_000)
        continue
      }
      if (version !== pollVersion) return
      enrichState.value = status.status
      enrichStatus.value = status
      if (status.status === 'completed') {
        const latest = await reportApi.detail(id)
        if (version !== pollVersion) return
        workspace.applyReportResponse(latest)
        await afterReportLoaded?.()
        enrichError.value = ''
        if (showToast) toast.add({ title: 'AI 增强内容已更新', color: 'success' })
        return
      }
      if (status.status === 'failed') {
        throw new Error(status.error || 'AI 增强失败')
      }
      await delay(2_000)
    }
    if (version === pollVersion) {
      enrichState.value = 'pending'
      throw new Error('AI 增强仍在后台执行，可稍后刷新或从历史报告恢复')
    }
  }

  async function enrich(id = workspace.reportId.value, showToast = true, scope: ReportRefreshScope = 'full') {
    if (!id) return
    const version = ++pollVersion
    enrichState.value = 'queued'
    enrichError.value = ''
    try {
      const status = await reportApi.startEnrichment(id, scope)
      enrichState.value = status.status
      enrichStatus.value = status
      await pollEnrichment(id, version, showToast)
    } catch (error) {
      if (version !== pollVersion) return
      enrichState.value = 'failed'
      enrichError.value = error instanceof Error ? error.message : 'AI 增强失败'
      if (showToast) toast.add({ title: enrichError.value, color: 'error' })
    }
  }

  async function resume(id = workspace.reportId.value) {
    if (!id || workspace.report.value?.llm_enrich_pending !== true) return
    const version = ++pollVersion
    try {
      const status = await reportApi.enrichmentStatus(id)
      enrichState.value = status.status
      enrichStatus.value = status
      if (status.status === 'queued' || status.status === 'running') {
        await pollEnrichment(id, version, false)
      } else if (status.status === 'completed') {
        const latest = await reportApi.detail(id)
        workspace.applyReportResponse(latest)
      }
    } catch (error) {
      if (version !== pollVersion) return
      enrichState.value = 'failed'
      enrichError.value = error instanceof Error ? error.message : 'AI 增强状态恢复失败'
    }
  }

  async function generate() {
    if (!workspace.resumeId.value || !workspace.targets.value.length) return void toast.add({ title: '请选择画像和目标岗位', color: 'warning' })
    const primaryJobId = workspace.primaryJobId.value || reportTargetKey(workspace.targets.value[0])
    if (!primaryJobId || !workspace.targets.value.some(target => reportTargetKey(target) === primaryJobId)) {
      return void toast.add({ title: '请设置有效的主目标岗位', color: 'warning' })
    }
    workspace.operation.value = 'generate'
    enrichError.value = ''
    try {
      const data = await reportApi.generate({
        resume_id: workspace.resumeId.value,
        target_job_ids: workspace.targets.value.map(reportTargetKey),
        primary_job_id: primaryJobId,
        match_goal: workspace.goal.value
      })
      workspace.applyReportResponse(data, primaryJobId)
      workspace.triggerReportPathAnimation('build')
      await afterReportLoaded?.()
      toast.add({ title: '基础报告已生成', description: 'AI 增强已转入后台，不影响现在查看报告。', color: 'success' })
      if (data.llm_enrich_pending !== false) void enrich(data.report_id, false)
    } catch (error) {
      const message = error instanceof Error ? error.message : '报告生成失败'
      toast.add({ title: /timeout|aborted/i.test(message) ? '基础报告生成超时，请稍后从历史报告恢复' : message, color: 'error' })
    }
    finally { workspace.operation.value = '' }
  }

  async function exportPdf(options: ReportPdfExportOptions): Promise<boolean> {
    if (!workspace.reportId.value) return false
    workspace.operation.value = 'pdf'
    exportState.value = 'preparing'
    exportError.value = ''
    try {
      const blob = await reportApi.exportPdf(workspace.reportId.value, options)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `career_report_${workspace.reportId.value}.pdf`
      anchor.click()
      URL.revokeObjectURL(url)
      exportState.value = 'idle'
      toast.add({ title: 'PDF 已生成并开始下载', color: 'success' })
      return true
    } catch (error) {
      exportState.value = 'failed'
      exportError.value = error instanceof Error ? error.message : '导出失败'
      toast.add({ title: exportError.value, color: 'error' })
      return false
    } finally { workspace.operation.value = '' }
  }

  async function exportData() {
    if (!workspace.reportId.value) return
    workspace.operation.value = 'data-export'
    try {
      const data = await reportApi.exportData(workspace.reportId.value)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `career_report_${workspace.reportId.value}_data.json`
      anchor.click()
      URL.revokeObjectURL(url)
      toast.add({ title: '报告数据已导出', color: 'success' })
    } catch (error) {
      toast.add({ title: error instanceof Error ? error.message : '报告数据导出失败', color: 'error' })
    } finally { workspace.operation.value = '' }
  }

  function stop() { pollVersion += 1 }

  return { enrichError, enrichState, enrichStatus, exportState, exportError, generate, enrich, resume, stop, exportPdf, exportData }
}
