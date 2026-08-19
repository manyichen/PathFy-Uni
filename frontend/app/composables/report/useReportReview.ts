import type { ReportPlanProposal, ReportPlanVersion, ReportReview, ReportReviewCycle, ReportReviewDraft } from '~/types/api'
import { useReportApi } from '~/composables/api/useReportApi'
import type { ReportWorkspace } from './useReportWorkspace'

export function useReportReview(workspace: ReportWorkspace) {
  const reportApi = useReportApi()
  const toast = useToast()
  const reviewText = ref('')
  const reviewScope = ref<'target' | 'all'>('target')
  const reviewCycle = ref<ReportReviewCycle>('monthly')
  const reviewSignal = ref<'normal' | 'goal_changed' | 'overloaded' | 'stalled' | 'evidence_missing'>('normal')
  const preferenceSignals = ref({ energy_after_tasks: 3, collaboration_fit: 3, structure_fit: 3, task_mode_fit: 3, note: '' })
  const reviews = ref<ReportReview[]>([])
  const planVersions = ref<ReportPlanVersion[]>([])
  const draft = ref<ReportReviewDraft>()
  const proposal = ref<ReportPlanProposal>()
  const error = ref('')

  async function load() {
    if (!workspace.reportId.value) return
    const [reviewResult, versionResult] = await Promise.allSettled([
      reportApi.reviews(workspace.reportId.value),
      reportApi.planVersions(workspace.reportId.value)
    ])
    reviews.value = reviewResult.status === 'fulfilled' ? reviewResult.value : []
    planVersions.value = versionResult.status === 'fulfilled' ? versionResult.value : []
    const latestProposed = planVersions.value.find(item => item.status === 'proposed' && !item.stale)
    if (!proposal.value && latestProposed) proposal.value = latestProposed
  }

  function applyTemplate() {
    reviewText.value = reviewCycle.value === 'weekly'
      ? '本周完成：\n投入时间：\n新增成果或证据：\n阻塞事项：\n下周最重要的一步：'
      : '本月完成：\n能力进步：\n目标岗位贴合度变化：\n新增作品或成果：\n遇到的困难与下月重点：'
  }

  function resetFlow() {
    draft.value = undefined
    proposal.value = undefined
  }

  async function createDraft() {
    if (!workspace.reportId.value || !reviewText.value.trim()) return
    const jobId = workspace.activeJobId.value || workspace.primaryJobId.value
    if (reviewScope.value === 'target' && !jobId) return void toast.add({ title: '请先选择复盘目标岗位', color: 'warning' })
    workspace.operation.value = 'review-draft'
    error.value = ''
    try {
      draft.value = await reportApi.createReviewDraft({
        report_id: workspace.reportId.value,
        review_text: reviewText.value,
        review_cycle: reviewCycle.value,
        scope: reviewScope.value,
        job_id: reviewScope.value === 'target' ? jobId : undefined
      })
      proposal.value = undefined
      toast.add({ title: draft.value.candidates.length ? '草稿已生成，请核对候选指标' : '草稿已生成；未发现可量化指标', color: 'info' })
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '复盘草稿生成失败'
      toast.add({ title: error.value, color: 'error' })
    } finally { workspace.operation.value = '' }
  }

  async function confirmDraft() {
    if (!draft.value) return
    workspace.operation.value = 'review-confirm'
    error.value = ''
    try {
      const result = await reportApi.confirmReviewDraft(draft.value.draft_id, {
        candidates: draft.value.candidates.map(item => ({ code: item.code, decision: item.decision === 'confirm' ? 'confirm' : 'ignore', value: item.value })),
        signals: reviewSignal.value === 'normal' ? {} : { [reviewSignal.value]: true }
        , preference_signals: preferenceSignals.value
      })
      proposal.value = result.plan_proposal || undefined
      const latest = await reportApi.detail(workspace.reportId.value!)
      workspace.applyReportResponse(latest)
      workspace.triggerReportPathAnimation('append')
      reviewText.value = ''
      draft.value = undefined
      reviewSignal.value = 'normal'
      await load()
      toast.add({ title: proposal.value ? '复盘已确认，计划提案等待你的决定' : '复盘已确认，本次未生成计划变更', color: 'success' })
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '复盘确认失败'
      toast.add({ title: error.value, color: 'error' })
    } finally { workspace.operation.value = '' }
  }

  async function decideProposal(decision: 'accept' | 'reject') {
    if (!proposal.value) return
    workspace.operation.value = 'plan-proposal'
    error.value = ''
    try {
      const acceptedIds = proposal.value.changes.filter(item => item.accepted).map(item => item.id)
      await reportApi.decidePlanProposal(proposal.value.proposal_id, {
        decision,
        accepted_change_ids: decision === 'accept' ? acceptedIds : [],
        change_overrides: decision === 'accept'
          ? proposal.value.changes.filter(item => item.accepted).map(item => ({ id: item.id, after: item.after }))
          : []
      })
      const latest = await reportApi.detail(workspace.reportId.value!)
      workspace.applyReportResponse(latest)
      if (decision === 'accept') workspace.triggerReportPathAnimation('append')
      proposal.value = undefined
      await load()
      toast.add({ title: decision === 'accept' ? '已应用所选计划变更' : '已拒绝计划提案，当前计划保持不变', color: 'success' })
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '计划提案处理失败'
      toast.add({ title: error.value, color: 'error' })
    } finally { workspace.operation.value = '' }
  }

  return {
    reviewText, reviewScope, reviewCycle, reviewSignal, reviews, planVersions,
    preferenceSignals,
    draft, proposal, error, load, applyTemplate, resetFlow, createDraft,
    confirmDraft, decideProposal
  }
}
