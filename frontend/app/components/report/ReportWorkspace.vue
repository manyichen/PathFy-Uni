<script setup lang="ts">
import { useReportWorkspace } from '~/composables/report/useReportWorkspace'
import { useReportGeneration } from '~/composables/report/useReportGeneration'
import { useReportHistory } from '~/composables/report/useReportHistory'
import { useReportPublicInfo } from '~/composables/report/useReportPublicInfo'
import { useReportReview } from '~/composables/report/useReportReview'
import { useReportTargets } from '~/composables/report/useReportTargets'
import { useReportApi } from '~/composables/api/useReportApi'
import ReportPathJourney from '~/components/visualization/report/ReportPathJourney.vue'
import type { ReportWorkspaceTab } from '~/components/report/ReportWorkspaceTabs.vue'
import type { ReportPdfExportOptions } from '~/types/report'
const workspace = useReportWorkspace()
const reportApi = useReportApi()
const toast = useToast()
const review = useReportReview(workspace)
const history = useReportHistory(workspace, review.load)
const generation = useReportGeneration(workspace, review.load)
const targetTools = useReportTargets(workspace)
const publicInfo = useReportPublicInfo()
const activeWorkspaceTab = ref<ReportWorkspaceTab>('action')
const deleteOpen = ref(false)
const pdfExportOpen = ref(false)
const deleteConfirmation = ref('')
const deleteReady = computed(() => Boolean(workspace.reportId.value) && deleteConfirmation.value.trim() === String(workspace.reportId.value))
const activeRecommendations = computed(() => workspace.report.value?.recommendations?.by_target?.find(item => item.job_id === workspace.activeJobId.value))
const decisionSupport = computed(() => workspace.report.value?.decision_support)
const activeDecision = computed(() => {
  const decisions = decisionSupport.value?.target_decisions || []
  if (!workspace.activeJobId.value) return decisions[0]
  return decisions.find(item => item.job_id === workspace.activeJobId.value)
})
const evidenceCount = computed(() => activeDecision.value?.claims.length || 0)
const enrichmentStageLabel = computed(() => ({
  queued: '等待执行', loading_snapshot: '校验输入快照', snapshot_verified: '快照已确认', evidence_retrieved: '证据检索完成',
  constraint_plan_built: '约束计划已生成', structured_copy_generated: '结构化内容已生成', narrative_generated: '文案生成完成',
  quality_gate_completed: '内容门禁已完成', completed: '增强完成', failed: '增强失败'
}[generation.enrichStatus.value?.stage || ''] || '后台处理中'))
const enrichmentDescription = computed(() => {
  const progress = generation.enrichStatus.value?.progress
  return `AI 增强正在后台执行：${enrichmentStageLabel.value}${typeof progress === 'number' ? `（${progress}%）` : ''}；当前规则版报告可立即使用。`
})

async function initialize() {
  const cache = await workspace.initialize()
  if (cache?.reportId) await history.restore(cache.reportId, cache.report || cache.reportSnapshot, cache.activeJobId)
  if (workspace.reportId.value && workspace.report.value?.llm_enrich_pending === true) void generation.resume()
}

async function refreshCurrentReport() {
  const reportId = workspace.reportId.value
  if (!reportId) return
  try {
    const data = await reportApi.detail(reportId)
    workspace.applyReportResponse(data, workspace.activeJobId.value)
  } catch (error) {
    toast.add({ title: error instanceof Error ? `行动已保存，但刷新失败：${error.message}` : '行动已保存，请刷新查看', color: 'warning' })
  }
}

function handleActionChanged(reload: boolean) {
  if (!reload) {
    workspace.persist()
    return
  }
  void refreshCurrentReport()
}

function reset() {
  review.reviewText.value = ''
  review.reviews.value = []
  review.planVersions.value = []
  review.resetFlow()
  publicInfo.clear()
  workspace.resetWorkspace()
}

function openDelete() {
  deleteConfirmation.value = ''
  deleteOpen.value = true
}

function openPdfExport() {
  generation.exportError.value = ''
  pdfExportOpen.value = true
}

async function exportPdf(options: ReportPdfExportOptions) {
  const succeeded = await generation.exportPdf(options)
  if (succeeded) pdfExportOpen.value = false
}

async function deleteCurrentReport() {
  const reportId = workspace.reportId.value
  if (!reportId || !deleteReady.value) return
  workspace.operation.value = 'delete-report'
  try {
    await reportApi.deleteReport(reportId)
    review.reviewText.value = ''
    review.reviews.value = []
    review.planVersions.value = []
    review.resetFlow()
    publicInfo.clear()
    deleteOpen.value = false
    deleteConfirmation.value = ''
    workspace.resetWorkspace('报告及关联数据已永久删除')
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '报告删除失败', color: 'error' })
  } finally {
    workspace.operation.value = ''
  }
}

onMounted(initialize)
onUnmounted(generation.stop)
</script>

<template>
  <div class="cockpit-page">
    <ReportPageHeader :has-report="Boolean(workspace.report.value)" :report-id="workspace.reportId.value" :enrich-state="generation.enrichState.value" :config-collapsed="workspace.configCollapsed.value" :enrich-error="generation.enrichError.value" :export-state="generation.exportState.value" @toggle-config="workspace.configCollapsed.value=!workspace.configCollapsed.value" @history="history.load" @enrich="generation.enrich()" @export="openPdfExport" @export-data="generation.exportData" @delete-report="openDelete" @reset="workspace.resetOpen.value=true" />
    <CockpitStageRail current="plan" />

    <UAlert v-if="['queued','running'].includes(generation.enrichState.value) && workspace.report.value" color="info" variant="soft" title="基础报告已生成" :description="enrichmentDescription" />
    <UAlert v-if="generation.enrichError.value && workspace.report.value" color="warning" variant="soft" title="报告骨架已保留" :description="`${generation.enrichError.value}。可点击“重试 AI 增强”，不影响继续查看和复盘。`" />
    <UAlert v-if="generation.exportError.value && workspace.report.value" color="error" variant="soft" title="PDF 导出失败" :description="generation.exportError.value" />
    <ReportCockpitOverview v-if="workspace.report.value" :report-id="workspace.reportId.value" :report="workspace.report.value" :target="workspace.activeTarget.value" :plan="workspace.activePlan.value" :goal="workspace.goal.value" />
    <CockpitSectionHeading v-else kicker="01 · Primary View" title="建立报告目标" description="先导入或选择岗位，再生成可执行、可复盘的生涯计划。" />
    <ReportConfigPanel v-model:resume-id="workspace.resumeId.value" v-model:goal="workspace.goal.value" :collapsed="workspace.configCollapsed.value" :has-report="Boolean(workspace.report.value)" :status="workspace.workspaceStatus.value" :resumes="workspace.resumes.value" :targets="workspace.targets.value" :primary-job-id="workspace.primaryJobId.value" :loading="workspace.operation.value" @open-match="targetTools.openMatchHistory" @open-explorer="targetTools.explorerOpen.value=true" @open-picker="targetTools.pickerOpen.value=true" @remove-target="targetTools.removeTarget" @set-primary="targetTools.setPrimary" @clear-targets="targetTools.clearTargets" @generate="generation.generate" />

    <UEmpty v-if="!workspace.report.value" title="尚未生成生涯报告" description="导入匹配记录、搜索候选或随机浏览岗位后即可快速开始" icon="i-lucide-file-chart-column" />

    <template v-else>
      <ReportTargetTabs :targets="workspace.reportTargets.value" :active-job-id="workspace.activeJobId.value" :primary-job-id="workspace.reportPrimaryJobId.value" @select="workspace.selectTarget" />
      <ReportWorkspaceTabs v-model="activeWorkspaceTab" :evidence-count="evidenceCount" :review-count="review.reviews.value.length" />

      <section v-if="activeWorkspaceTab === 'action'" id="report-panel-action" role="tabpanel" aria-labelledby="report-tab-action" class="workspace-panel">
        <ReportEditorialHeading
          index="02"
          kicker="把计划做完"
          :title-lines="['别把计划写成愿望，', '让每一步都有回声']"
          description="这里不是任务堆积区。每项行动都要有投入、交付物和验收标准，完成状态会自动保存并进入下一次复盘。"
          tone="action"
        />
        <ReportPreferenceStrategy v-if="workspace.reportId.value" :report-id="workspace.reportId.value" :strategy="workspace.report.value.preference_strategy" @changed="refreshCurrentReport" />
        <ReportNextBestAction v-if="workspace.reportId.value" :report-id="workspace.reportId.value" :plan="workspace.activePlan.value" :decision="activeDecision" @changed="handleActionChanged" />
        <ReportLongitudinalInsights :insights="workspace.report.value.longitudinal_insights" />
      </section>

      <section v-else-if="activeWorkspaceTab === 'evidence'" id="report-panel-evidence" role="tabpanel" aria-labelledby="report-tab-evidence" class="workspace-panel evidence-workspace">
        <header class="evidence-editorial-heading">
          <div class="evidence-section-mark" aria-hidden="true"><span>03</span><i /></div>
          <div class="evidence-heading-copy"><p>把判断摊开</p><h2>别只看结论，先看它站在哪些事实之上</h2></div>
          <p class="evidence-heading-note">岗位要求、个人画像、行动与成果分层呈现。你看到的不只是 AI 的结论，还能继续追问它为什么成立。</p>
        </header>
        <ReportEvidenceMap :decision="activeDecision" @review="activeWorkspaceTab='review'" />
        <div class="evidence-maintenance" aria-label="依据内容维护">
          <div><span class="maintenance-index">更新台 / UPDATE</span><strong>哪部分变化，就只刷新哪部分</strong><span>保留已核对内容，避免整份报告被 AI 反复改写。</span></div>
          <div>
            <UButton size="xs" color="neutral" variant="soft" icon="i-lucide-file-text" @click="generation.enrich(workspace.reportId.value, true, 'narrative')">仅刷新文案</UButton>
            <UButton size="xs" color="neutral" variant="soft" icon="i-lucide-library" @click="generation.enrich(workspace.reportId.value, true, 'resources')">仅刷新资源</UButton>
            <UButton size="xs" color="neutral" variant="soft" icon="i-lucide-list-checks" @click="generation.enrich(workspace.reportId.value, true, 'plan')">仅刷新计划</UButton>
          </div>
        </div>
        <section class="evidence-ledger" aria-label="判断依据与目标比较档案">
          <header class="ledger-heading"><span>02</span><div><small>展开判断</small><strong>从单条结论读到多目标取舍</strong></div><p>先核对高风险判断，再看同一组事实如何影响不同岗位。</p></header>
          <ReportDecisionEvidence :decision="activeDecision" />
          <ReportTargetComparison :support="decisionSupport" />
          <footer><span>PATHFY / DECISION LEDGER</span><span>系统计算 × 用户材料 × 最新复盘</span></footer>
        </section>
        <div class="report-focus-grid">
          <ReportGapTable :target="workspace.activeTarget.value" :plan="workspace.activePlan.value" />
          <ReportTrackProfile :target="workspace.activeTarget.value" :state="publicInfo.states[workspace.activeJobId.value]" @load="publicInfo.load(workspace.activeTarget.value!, $event)" />
        </div>
        <ReportEvidenceShelf :plan="workspace.activePlan.value" :recommendations="activeRecommendations" />
      </section>

      <section v-else-if="activeWorkspaceTab === 'route'" id="report-panel-route" role="tabpanel" aria-labelledby="report-tab-route" class="workspace-panel route-workspace">
        <ReportEditorialHeading
          index="04"
          kicker="把时间折成航线"
          :title-lines="['路线不是预言，', '是被事实点亮的航标']"
          description="计划负责给出方向，复盘负责留下坐标。这里只连接真实发生过的成长节点，让每一次转向都有来处，也让下一段行程看得见。"
          tone="route"
        />
        <ReportPathJourney
          :report-id="workspace.reportId.value"
          :report="workspace.report.value"
          :line="workspace.activeLine.value"
          :plan="workspace.activePlan.value"
          :adjustments="workspace.activeAdjustments.value"
          :enrich-state="generation.enrichState.value"
          :selected-month="workspace.selectedMonth.value"
          :animation-revision="workspace.reportPathAnimationRevision.value"
          :animation-kind="workspace.reportPathAnimationKind.value"
          @select-month="workspace.selectedMonth.value=$event"
        />
        <ReportMonthDetail
          :month="workspace.selectedMonth.value"
          :line="workspace.activeLine.value"
          :adjustments="workspace.activeAdjustments.value"
          :plan="workspace.activePlan.value"
          :proposal="review.proposal.value"
          :job-id="workspace.activeJobId.value"
          @open-review="activeWorkspaceTab='review'"
        />
        <section v-if="workspace.activePlan.value && workspace.reportId.value" class="route-plan-section">
          <ReportPlanView :report-id="workspace.reportId.value" :plans="[workspace.activePlan.value]" :recommendations="workspace.report.value.recommendations" :show-next-month="false" @changed="workspace.persist" />
        </section>
      </section>

      <section v-else id="report-panel-review" role="tabpanel" aria-labelledby="report-tab-review" class="workspace-panel">
        <ReportEditorialHeading
          index="05"
          kicker="让事实回流"
          :title-lines="['复盘不是总结，', '是下一轮行动的转向器']"
          description="把发生过的事实送回计划：先记录，再核对，最后决定是否改变方向。数据不足时只保留记录，不把缺失误判为失败。"
          tone="review"
        />
        <ReportAdjustmentNotice :report="workspace.report.value" :adjustments="workspace.activeAdjustments.value" />
        <ReportReviewSection
          v-model:review-text="review.reviewText.value"
          v-model:review-scope="review.reviewScope.value"
          v-model:review-cycle="review.reviewCycle.value"
          v-model:review-signal="review.reviewSignal.value"
          v-model:preference-signals="review.preferenceSignals.value"
          :report="workspace.report.value"
          :active-target="workspace.activeTarget.value"
          :reviews="review.reviews.value"
          :plan-versions="review.planVersions.value"
          :draft="review.draft.value"
          :proposal="review.proposal.value"
          :loading="workspace.operation.value"
          @apply-template="review.applyTemplate"
          @create-draft="review.createDraft"
          @confirm-draft="review.confirmDraft"
          @decide-proposal="review.decideProposal"
        />
      </section>
    </template>

    <ReportMatchImportModal v-model:open="targetTools.matchOpen.value" :items="targetTools.matchHistory.value" :loading="targetTools.matchHistoryLoading.value" :error="targetTools.matchHistoryError.value" :import-loading="workspace.operation.value==='import'" @import="targetTools.importMatch" @retry="targetTools.openMatchHistory" />
    <ReportHistoryModal v-model:open="history.open.value" :items="history.items.value" :loading="history.loading.value" :restoring-id="history.restoringId.value" :error="history.error.value" @restore="history.restore" @retry="history.load" />

    <ReportPdfExportModal
      v-if="workspace.report.value && workspace.reportId.value"
      v-model:open="pdfExportOpen"
      :report-id="workspace.reportId.value"
      :report="workspace.report.value"
      :source-title="workspace.reportTitle.value"
      :exporting="generation.exportState.value === 'preparing'"
      :export-error="generation.exportError.value"
      @export="exportPdf"
    />

    <UModal v-model:open="workspace.resetOpen.value" title="清空报告工作区"><template #body><p class="text-sm leading-6 muted">这会清空当前选择、报告快照、复盘文本和本地工作区。后端历史报告仍可恢复。</p></template><template #footer><div class="flex w-full justify-end gap-2"><UButton color="neutral" variant="soft" @click="() => { workspace.resetOpen.value = false }">取消</UButton><UButton color="error" icon="i-lucide-trash-2" @click="reset">确认清空</UButton></div></template></UModal>
    <UModal v-model:open="deleteOpen" title="永久删除生涯报告">
      <template #body>
        <div class="grid gap-4">
          <UAlert color="error" variant="soft" icon="i-lucide-triangle-alert" title="删除后不可恢复" description="报告、目标、复盘、草稿、计划版本、证据、行动事件和实验分组都会被永久删除。建议先导出个人数据。" />
          <UFormField :label="`输入报告编号 ${workspace.reportId.value} 以确认`">
            <UInput v-model="deleteConfirmation" inputmode="numeric" autocomplete="off" :placeholder="String(workspace.reportId.value || '')" />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton color="neutral" variant="soft" :disabled="workspace.operation.value === 'delete-report'" @click="() => { deleteOpen = false }">取消</UButton>
          <UButton color="error" icon="i-lucide-trash-2" :disabled="!deleteReady" :loading="workspace.operation.value === 'delete-report'" @click="deleteCurrentReport">永久删除</UButton>
        </div>
      </template>
    </UModal>
    <ReportTargetExplorerDialog v-model:open="targetTools.explorerOpen.value" :selected-ids="targetTools.selectedIds.value" :selected-targets="workspace.targets.value" :max-targets="5" @select="targetTools.addTarget" @remove="targetTools.removeTarget" />
    <JobPickerDialog v-model:open="targetTools.pickerOpen.value" title="选择报告目标岗位" multiple :selected-ids="targetTools.selectedIds.value" @select="targetTools.addTarget" />
  </div>
</template>

<style scoped>
.workspace-panel{display:grid;gap:1rem;min-width:0}.evidence-workspace{gap:clamp(1.6rem,3vw,3rem);padding:.25rem;background:transparent}.report-focus-grid{display:grid;gap:1.35rem}.evidence-editorial-heading{display:grid;grid-template-columns:auto minmax(0,1.45fr) minmax(18rem,.75fr);gap:1.2rem;align-items:center;padding:.4rem .35rem .25rem}.evidence-section-mark{display:grid;align-self:stretch;justify-items:center;grid-template-rows:auto 1fr;gap:.45rem;color:var(--pathfy-evidence)}.evidence-section-mark span{font:850 .76rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em}.evidence-section-mark i{width:1px;min-height:3.8rem;background:color-mix(in srgb,var(--pathfy-evidence) 55%,transparent)}.evidence-heading-copy{border-right:1px solid var(--pathfy-line);padding-right:1.5rem}.evidence-heading-copy>p{color:var(--pathfy-evidence);font-size:.78rem;font-weight:850;letter-spacing:.1em}.evidence-heading-copy h2{max-width:54rem;margin-top:.45rem;font-size:clamp(2rem,3.6vw,3.55rem);font-weight:790;letter-spacing:-.055em;line-height:1.08;text-wrap:balance}.evidence-heading-note{max-width:31rem;color:var(--ui-text-muted);font-size:.9rem;line-height:1.8}.evidence-maintenance{display:flex;align-items:center;justify-content:space-between;gap:1.5rem;margin-inline:clamp(.2rem,2vw,1.4rem);border:0;border-top:1px solid var(--pathfy-line);border-bottom:1px solid var(--pathfy-line);border-radius:0;background:transparent;padding:1rem .2rem;box-shadow:none}.evidence-maintenance>div:first-child{display:grid;grid-template-columns:auto auto;gap:.18rem .8rem;align-items:baseline}.maintenance-index{grid-row:1/3;color:var(--pathfy-evidence)!important;font:800 .68rem/1.5 ui-monospace,SFMono-Regular,Menlo,monospace!important;letter-spacing:.08em}.evidence-maintenance strong{font-size:.92rem}.evidence-maintenance span{color:var(--ui-text-muted);font-size:.78rem;line-height:1.5}.evidence-maintenance>div:last-child{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:.5rem}.evidence-ledger{position:relative;overflow:hidden;border:1px solid color-mix(in srgb,#9b8155 24%,var(--pathfy-line));border-radius:.3rem 1rem 1rem .3rem;background:linear-gradient(90deg,rgb(141 118 78 / .05) 1px,transparent 1px),linear-gradient(#fffdf7,#faf8f0);background-size:30px 100%,100% 100%;padding:clamp(1.1rem,2.5vw,2.2rem);box-shadow:0 32px 65px -48px rgb(47 39 25 / .72)}.evidence-ledger::before{position:absolute;top:0;bottom:0;left:1.15rem;width:1px;background:rgb(190 24 93 / .12);content:""}.ledger-heading{position:relative;display:grid;grid-template-columns:2.5rem minmax(0,1fr) minmax(16rem,.55fr);gap:1rem;align-items:center;border-bottom:1px solid rgb(35 48 52 / .17);padding:.2rem .4rem 1.2rem 1rem;color:#26363a}.ledger-heading>span{color:#0f766e;font:850 .82rem/1 ui-monospace,monospace}.ledger-heading>div{display:grid;gap:.18rem}.ledger-heading small{color:rgb(35 48 52 / .52);font-size:.7rem;font-weight:750;letter-spacing:.08em}.ledger-heading strong{font-size:1.15rem}.ledger-heading p{color:rgb(35 48 52 / .58);font-size:.8rem;line-height:1.65}.evidence-ledger :deep(.decision-evidence),.evidence-ledger :deep(.target-comparison){border:0;border-radius:0;background:transparent;padding:clamp(1rem,2vw,1.5rem) 1rem;box-shadow:none}.evidence-ledger :deep(.decision-evidence){border-bottom:1px solid rgb(35 48 52 / .16)}.evidence-ledger>footer{display:flex;justify-content:space-between;gap:1rem;border-top:1px solid rgb(35 48 52 / .15);padding:.8rem .5rem .1rem 1rem;color:rgb(35 48 52 / .45);font:650 .64rem/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.05em}.section-heading{margin:.25rem 0 .8rem}.section-heading h2{font-size:1.2rem;font-weight:700}.section-heading p{margin-top:.2rem;color:var(--ui-text-muted);font-size:.875rem}@media(min-width:960px){.report-focus-grid{grid-template-columns:minmax(0,1.12fr) minmax(0,.88fr);align-items:start}.report-focus-grid>*:nth-child(2){margin-top:2.3rem}}@media(max-width:820px){.evidence-editorial-heading{grid-template-columns:auto 1fr}.evidence-heading-copy{border-right:0;padding-right:0}.evidence-heading-note{grid-column:2}.ledger-heading{grid-template-columns:2.5rem 1fr}.ledger-heading p{grid-column:2}}@media(max-width:680px){.evidence-workspace{gap:1.4rem}.evidence-editorial-heading{grid-template-columns:1fr;padding-inline:.1rem}.evidence-section-mark{display:none}.evidence-heading-note{grid-column:auto}.evidence-heading-copy h2{font-size:2.15rem}.evidence-maintenance{align-items:flex-start;flex-direction:column;margin-inline:0}.evidence-maintenance>div:first-child{grid-template-columns:1fr}.maintenance-index{grid-row:auto}.evidence-maintenance>div:last-child{justify-content:flex-start}.evidence-ledger{padding:.8rem}.evidence-ledger::before{left:.55rem}.ledger-heading{grid-template-columns:2rem 1fr;padding-left:.45rem}.evidence-ledger>footer{flex-direction:column}}
</style>
