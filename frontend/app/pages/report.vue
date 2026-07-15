<script setup lang="ts">
import type { CodeEnvelope } from '~/types/api'

definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '生涯报告' })

const api = useApi()
const auth = useAuth()
const toast = useToast()
const resumes = ref<any[]>([])
const resumeId = ref<number>()
const targets = ref<any[]>([])
const pickerOpen = ref(false)
const goal = ref('fit')
const loading = ref('')
const reportId = ref<number>()
const report = ref<any>()
const history = ref<any[]>([])
const historyOpen = ref(false)
const matchHistory = ref<any[]>([])
const matchOpen = ref(false)
const reviews = ref<any[]>([])
const reviewHistoryOpen = ref(false)
const reviewPeriod = ref('')
const reviewActivities = ref('')
const reviewCapability = ref('')
const reviewTarget = ref('')
const reviewOutputs = ref('')
const reviewNext = ref('')
const cacheKey = computed(() => `career_report_workspace_v1_${auth.user.value?.id || 'guest'}`)

function persist() {
  if (!import.meta.client) return
  localStorage.setItem(cacheKey.value, JSON.stringify({ v: 1, userId: auth.user.value?.id || 'guest', savedAt: Date.now(), resumeId: resumeId.value, selectedResumeId: resumeId.value, targets: targets.value, selectedTargets: targets.value, goal: goal.value, reportMatchGoal: goal.value, reportId: reportId.value, report: report.value, reportSnapshot: report.value }))
}

function addTarget(item: any) {
  if (targets.value.length >= 5) { toast.add({ title: '最多选择 5 个目标', color: 'warning' }); return }
  const normalized = { ...item, job_id: item.job_id || item.id }
  if (!targets.value.some(x => x.job_id === normalized.job_id)) targets.value.push(normalized)
  persist()
}

function removeTarget(index: number) { targets.value.splice(index, 1); persist() }

async function openMatchHistory() {
  matchOpen.value = true
  try { matchHistory.value = (await api.ok<{ items: any[] }>('/api/match/history?limit=30')).items || [] }
  catch (error) { toast.add({ title: error instanceof Error ? error.message : '匹配记录加载失败', color: 'error' }) }
}

async function importMatch(runId: number) {
  loading.value = 'import'
  try {
    const data = await api.ok<any>('/api/report/targets/import-from-match', { method: 'POST', body: { run_id: runId, limit: 5 } })
    targets.value = (data.targets || []).slice(0, 5)
    goal.value = data.match_goal === 'stretch' ? 'stretch' : 'fit'
    if (resumes.value.some(item => item.id === data.resume_id)) resumeId.value = data.resume_id
    matchOpen.value = false
    persist()
    toast.add({ title: `已导入 ${targets.value.length} 个匹配目标`, color: 'success' })
  } catch (error) { toast.add({ title: error instanceof Error ? error.message : '导入失败', color: 'error' }) }
  finally { loading.value = '' }
}

async function generate() {
  if (!resumeId.value || !targets.value.length) { toast.add({ title: '请选择画像和目标岗位', color: 'warning' }); return }
  loading.value = 'generate'
  try {
    const data = await api.ok<any>('/api/report/generate', { method: 'POST', body: { resume_id: resumeId.value, target_job_ids: targets.value.map(x => x.job_id), primary_job_id: targets.value[0].job_id, match_goal: goal.value } })
    reportId.value = data.report_id
    report.value = data.report
    persist()
    if (data.llm_enrich_pending !== false) {
      loading.value = 'enrich'
      const enriched = await api.ok<any>(`/api/report/${data.report_id}/enrich`, { method: 'POST', body: {} })
      report.value = enriched.report || report.value
      persist()
    }
    await loadReviews()
    toast.add({ title: '报告生成成功', color: 'success' })
  } catch (error) { toast.add({ title: error instanceof Error ? error.message : '报告生成失败', color: 'error' }) }
  finally { loading.value = '' }
}

async function openHistory() {
  historyOpen.value = true
  try { history.value = (await api.ok<{ items: any[] }>('/api/report/my/list?limit=30')).items || [] }
  catch (error) { toast.add({ title: error instanceof Error ? error.message : '历史报告加载失败', color: 'error' }) }
}

async function restore(id: number) {
  loading.value = 'restore'
  try {
    const data = await api.ok<any>(`/api/report/${id}`)
    reportId.value = data.report_id || id
    report.value = data.report
    if (data.target_job_ids?.length && report.value?.targets) targets.value = report.value.targets.map((item: any) => ({ job_id: item.id, ...item }))
    historyOpen.value = false
    await loadReviews()
    persist()
  } catch (error) { toast.add({ title: error instanceof Error ? error.message : '报告恢复失败', color: 'error' }) }
  finally { loading.value = '' }
}

async function loadReviews() {
  if (!reportId.value) return
  try { reviews.value = (await api.ok<{ items: any[] }>(`/api/report/${reportId.value}/reviews`)).items || [] }
  catch { reviews.value = [] }
}

async function review() {
  if (!reportId.value) return
  const fields = [
    ['本周期', reviewPeriod.value], ['做过的事', reviewActivities.value], ['能力短板', reviewCapability.value],
    ['和目标岗位', reviewTarget.value], ['能拿得出手的成果', reviewOutputs.value], ['卡点与下周打算', reviewNext.value]
  ]
  const missing = fields.find(([, value]) => !String(value).trim())
  if (missing) { toast.add({ title: `请填写「${missing[0]}」`, color: 'warning' }); return }
  if (!/(\d{1,2}\s*[月日]|第\s*\d+\s*周|本周|上周|下周|至|—|-|~)/.test(reviewPeriod.value)) {
    toast.add({ title: '本周期需要包含具体日期或第几周', color: 'warning' }); return
  }
  if (reviewActivities.value.trim().length < 20) {
    toast.add({ title: '“做过的事”至少填写 20 个字，并说明完成进度', color: 'warning' }); return
  }
  if (reviewCapability.value.trim().length < 12 || !/(提升|改善|变强|还弱|不足|短板|百分之|%)/.test(reviewCapability.value)) {
    toast.add({ title: '“能力短板”需要说明提升或不足，建议提供百分比', color: 'warning' }); return
  }
  if (reviewTarget.value.trim().length < 10 || !/(更好|提升|持平|差不多|更难|下降|贴合|匹配|\d+\s*分)/.test(reviewTarget.value)) {
    toast.add({ title: '“和目标岗位”需要说明贴合度变化', color: 'warning' }); return
  }
  if (!/\d+/.test(reviewOutputs.value)) {
    toast.add({ title: '“能拿得出手的成果”需要包含成果数量', color: 'warning' }); return
  }
  if (reviewNext.value.trim().length < 15 || !/(卡|困难|阻碍)/.test(reviewNext.value) || !/(下周|接下来|下一步|推进|计划)/.test(reviewNext.value)) {
    toast.add({ title: '请分别写明当前卡点和下周推进事项', color: 'warning' }); return
  }
  const reviewText = `本周期：${reviewPeriod.value.trim()}\n\n【做过的事】\n${reviewActivities.value.trim()}\n\n【能力短板】\n${reviewCapability.value.trim()}\n\n【和目标岗位】\n${reviewTarget.value.trim()}\n\n【能拿得出手的成果】\n${reviewOutputs.value.trim()}\n\n【卡点与下周打算】\n${reviewNext.value.trim()}`
  loading.value = 'review'
  try {
    await api.ok('/api/report/review-cycle', { method: 'POST', body: { report_id: reportId.value, review_text: reviewText } })
    const latest = await api.ok<any>(`/api/report/${reportId.value}`)
    report.value = latest.report
    reviewPeriod.value = ''; reviewActivities.value = ''; reviewCapability.value = ''
    reviewTarget.value = ''; reviewOutputs.value = ''; reviewNext.value = ''
    await loadReviews()
    persist()
    toast.add({ title: '复盘已提交，计划已更新', color: 'success' })
  } catch (error) { toast.add({ title: error instanceof Error ? error.message : '复盘提交失败', color: 'error' }) }
  finally { loading.value = '' }
}

function reviewTextOf(item: any) { return item.metrics?.review_text || item.adjustment?.review_text || '' }
function reviewSummaryOf(item: any) { return item.metrics?.llm_extract?.summary || '' }
function reviewPassRate(item: any) { return Math.round(Number(item.metrics?.evaluation?.pass_rate || item.adjustment?.pass_rate || 0) * 100) }

async function exportPdf() {
  if (!reportId.value) return
  loading.value = 'pdf'
  try {
    const response = await api.request<Blob>(`/api/report/${reportId.value}/export/pdf`, { responseType: 'blob' })
    const url = URL.createObjectURL(response)
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `career_report_${reportId.value}.pdf`; anchor.click()
    URL.revokeObjectURL(url)
  } catch (error) { toast.add({ title: error instanceof Error ? error.message : '导出失败', color: 'error' }) }
  finally { loading.value = '' }
}

function targetTitle(item: any) { return item.display_title || [item.title, item.company].filter(Boolean).join(' · ') || item.id }
function gapEntries(item: any) {
  const gaps = item.match_preview?.dimension_gaps || {}
  const labels: Record<string, string> = { cap_req_theory: '理论', cap_req_cross: '交叉', cap_req_practice: '实践', cap_req_digital: '数字', cap_req_innovation: '创新', cap_req_teamwork: '协作', cap_req_social: '社会', cap_req_growth: '成长' }
  return Object.entries(gaps).map(([key, value]) => ({ key, label: labels[key] || key, value: Number(value || 0) })).sort((a, b) => b.value - a.value)
}

function reportStrategyText() {
  return report.value?.narrative?.text || report.value?.summary || report.value?.overview || '这份报告以能力画像为起点，对照目标岗位的真实要求，将差距拆成可执行的阶段任务。建议先完成近期里程碑并留下作品、证书或项目证据，再通过每月复盘持续校准路线。'
}

onMounted(async () => {
  auth.hydrate()
  const body = await api.request<CodeEnvelope<any[]>>('/api/profile/resumes')
  if (body.code === 200) { resumes.value = Array.isArray(body.data) ? body.data : []; resumeId.value = resumes.value[0]?.id }
  const raw = localStorage.getItem(cacheKey.value)
  if (raw) {
    try {
      const cache = JSON.parse(raw)
      resumeId.value = cache.resumeId || cache.selectedResumeId || resumeId.value
      targets.value = cache.targets || cache.selectedTargets || []
      goal.value = cache.goal || cache.reportMatchGoal || 'fit'
      reportId.value = cache.reportId
      report.value = cache.report || cache.reportSnapshot
      if (reportId.value) { await restore(reportId.value).catch(() => { report.value = cache.report || cache.reportSnapshot }) }
    } catch { /* ignore invalid cache */ }
  }
})

watch([resumeId, targets, goal], persist, { deep: true })
</script>

<template>
  <div class="page-stack">
    <div class="flex flex-wrap items-end justify-between gap-3"><div class="page-heading"><h1 class="flex items-center gap-2"><UIcon name="i-lucide-file-text" class="text-primary"/>职业生涯发展报告</h1><p class="muted">从匹配结果导入目标，在一页中查看差距、发展线、行动计划和复盘</p></div><div class="flex gap-2"><UButton icon="i-lucide-history" color="neutral" variant="soft" @click="openHistory">历史报告</UButton><UButton v-if="reportId" :loading="loading === 'pdf'" icon="i-lucide-download" variant="soft" @click="exportPdf">导出 PDF</UButton></div></div>

    <div class="report-workspace">
      <aside class="report-sidebar">
        <ReportWorkspaceSidebar
          v-model:resume-id="resumeId"
          v-model:goal="goal"
          v-model:review-period="reviewPeriod"
          v-model:review-activities="reviewActivities"
          v-model:review-capability="reviewCapability"
          v-model:review-target="reviewTarget"
          v-model:review-outputs="reviewOutputs"
          v-model:review-next="reviewNext"
          :resumes="resumes"
          :targets="targets"
          :loading="loading"
          :report="report"
          :reviews-count="reviews.length"
          @import="openMatchHistory"
          @pick="pickerOpen = true"
          @remove-target="removeTarget"
          @clear-targets="targets = []"
          @generate="generate"
          @review="review"
          @view-history="reviewHistoryOpen = true"
        />
      </aside>

      <main class="report-main">
        <UEmpty v-if="!report" title="尚未生成生涯报告" description="从左侧导入一次人岗匹配记录即可快速开始" icon="i-lucide-file-chart-column" />
        <template v-else>
      <UCard><div class="flex flex-wrap items-start justify-between gap-4"><div class="max-w-4xl"><p class="text-xs text-primary">报告 #{{ reportId }} · {{ String(report.generated_at || '').replace('T', ' ').slice(0, 19) }}</p><h2 class="mt-1 text-xl font-semibold">发展策略摘要</h2><p class="mt-3 whitespace-pre-wrap leading-7 muted">{{ reportStrategyText() }}</p><div class="mt-4 grid gap-2 text-sm sm:grid-cols-3"><div class="rounded-lg bg-elevated p-3"><strong>先看差距</strong><p class="mt-1 text-xs leading-5 muted">对照“你的水平、岗位期望和待提升量”，确定真正需要优先补齐的维度。</p></div><div class="rounded-lg bg-elevated p-3"><strong>再做成果</strong><p class="mt-1 text-xs leading-5 muted">把课程学习转成项目、竞赛、证书或作品集，而不是只完成学习时长。</p></div><div class="rounded-lg bg-elevated p-3"><strong>每月复盘</strong><p class="mt-1 text-xs leading-5 muted">记录能力和成果变化，发展线会随复盘结果更新，并动态调整下月任务。</p></div></div></div><UBadge :label="goal === 'stretch' ? '冲刺目标' : '稳妥目标'" /></div></UCard>

      <section><div class="section-heading"><h2>目标与能力差距</h2><p>每个目标直接展示匹配分、图谱信号和最需要补齐的维度</p></div><div class="mb-3 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm leading-6 muted"><strong class="text-default">如何阅读：</strong>匹配分反映当前画像与岗位要求的综合贴合度；招聘可见度表示岗位样本的活跃程度，发展路径表示图谱中的晋升与换岗宽度，资源密度表示可关联的课程和竞赛数量。下方“差距”越大，越应优先进入近期计划。</div><div class="target-grid"><UCard v-for="item in report.targets || []" :key="item.id"><div class="flex items-start justify-between gap-3"><div><h3 class="font-semibold">{{ targetTitle(item) }}</h3><p class="text-sm muted">{{ item.location }} · {{ item.salary }}</p></div><div class="text-right"><strong class="text-2xl text-primary">{{ Math.round(item.match_preview?.match_score || 0) }}</strong><p class="text-xs muted">匹配分</p></div></div><div v-if="item.track_profile" class="mt-4 grid grid-cols-3 gap-2 text-center"><div class="metric"><strong>{{ Math.round(item.track_profile.hiring_visibility_0_100 || 0) }}</strong><span>招聘可见度</span></div><div class="metric"><strong>{{ Math.round(item.track_profile.path_breadth_0_100 || 0) }}</strong><span>发展路径</span></div><div class="metric"><strong>{{ Math.round(item.track_profile.resource_density_0_100 || 0) }}</strong><span>资源密度</span></div></div><div class="mt-4 grid gap-2"><div v-for="gap in gapEntries(item).slice(0, 4)" :key="gap.key" class="grid grid-cols-[3rem_1fr_2.5rem] items-center gap-2 text-xs"><span>{{ gap.label }}</span><UProgress :model-value="Math.max(0, gap.value)" :max="100" /><span class="text-right">{{ gap.value.toFixed(0) }}</span></div></div></UCard></div></section>

      <section v-if="report.development_lines?.lines?.length"><div class="section-heading"><h2>发展线与复盘节点</h2><p>横轴是报告生成后的第 0—12 月，纵轴是复盘进步度；折线不是预测结果，而是计划节点与真实复盘共同形成的成长轨迹。</p></div><UCard><DevelopmentLineChart :lines="report.development_lines.lines" /><div class="mt-3 border-t border-default pt-4"><div class="grid gap-4"><article v-for="line in report.development_lines.lines" :key="line.line_id"><div class="flex items-center justify-between"><h3 class="font-semibold">{{ line.line_name }}</h3><span class="text-xs muted">蓝色节点表示已复盘，其他节点表示计划安排</span></div><div v-if="line.timeline?.length" class="mt-2 flex flex-wrap gap-2"><UBadge v-for="point in line.timeline" :key="`${point.month}-${point.review_id}`" :label="`${point.month} 月 · ${point.label || Math.round(point.progress) + '%'}`" :color="point.kind === 'review' ? 'primary' : 'neutral'" variant="soft" /></div></article></div></div></UCard></section>

      <section><div class="section-heading"><h2>分岗成长计划</h2><p>每个岗位独立规划短期补基础、中期做项目、长期形成可投递成果；“下月优先任务”是当前最值得执行的一小组动作。</p></div><ReportPlanView :report-id="reportId!" :plans="report.plans_by_target || []" :recommendations="report.recommendations" @changed="persist" /></section>

          <section><div class="section-heading"><h2>评估指标</h2><p>复盘入口固定在左侧；这里集中展示用于判断计划进度的量化标准。</p></div><UCard><div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3"><article v-for="metric in report.evaluation?.metrics || []" :key="metric.code" class="rounded-lg border border-default p-3"><div class="flex justify-between gap-2"><strong class="text-sm">{{ metric.label }}</strong><UBadge :label="metric.cycle === 'monthly' ? '每月' : metric.cycle" color="neutral" size="sm" variant="soft" /></div><p class="mt-1 text-xs leading-5 muted">{{ metric.description }}</p><p class="mt-2 text-xs text-primary">目标：{{ metric.target }}</p></article><p v-if="!report.evaluation?.metrics?.length" class="text-sm muted">暂无评估指标</p></div></UCard></section>
        </template>
      </main>
    </div>

    <UModal v-model:open="matchOpen" title="从人岗匹配导入"><template #body><div class="grid gap-2"><button v-for="item in matchHistory" :key="item.run_id" type="button" class="flex items-center justify-between rounded-xl border border-default p-3 text-left hover:border-primary" @click="importMatch(item.run_id)"><div><p class="font-medium">{{ item.student_name || '能力画像' }} · {{ item.match_goal === 'stretch' ? '冲刺目标' : '稳妥目标' }}</p><p class="text-xs muted">{{ String(item.created_at || '').replace('T', ' ').slice(0, 19) }} · {{ item.q || '全部岗位' }}</p></div><UBadge :label="`${item.returned || 0} 个岗位`" color="neutral" variant="soft" /></button><UEmpty v-if="!matchHistory.length" title="暂无匹配记录" description="请先在人岗匹配页面生成一次结果" /></div></template></UModal>
    <UModal v-model:open="historyOpen" title="历史报告"><template #body><div class="grid gap-2"><button v-for="item in history" :key="item.report_id" type="button" class="flex items-center justify-between rounded-xl border border-default p-3 text-left hover:border-primary" @click="restore(item.report_id)"><div><p class="font-medium">{{ item.title || `报告 #${item.report_id}` }}</p><p class="text-xs muted">{{ (item.target_titles || []).join('、') || String(item.created_at || '').replace('T', ' ').slice(0, 19) }}</p></div><UIcon name="i-lucide-chevron-right" /></button><UEmpty v-if="!history.length" title="暂无历史报告" /></div></template></UModal>
    <UModal v-model:open="reviewHistoryOpen" title="历史复盘" :ui="{ content: 'sm:max-w-3xl' }"><template #body><div class="grid gap-3"><article v-for="item in reviews" :key="item.review_id" class="rounded-xl border border-default p-4"><div class="flex flex-wrap items-center justify-between gap-2"><div><strong>复盘 #{{ item.review_id }}</strong><p class="mt-1 text-xs muted">{{ String(item.created_at || '').replace('T', ' ').slice(0, 19) }}</p></div><div class="flex gap-2"><UBadge :label="`通过率 ${reviewPassRate(item)}%`" variant="soft"/><UBadge v-if="item.adjustment?.replan_mode" :label="item.adjustment.replan_mode" color="neutral" variant="soft"/></div></div><p v-if="reviewSummaryOf(item)" class="mt-3 rounded-lg bg-primary/5 p-3 text-sm leading-6">{{ reviewSummaryOf(item) }}</p><div v-if="reviewTextOf(item)" class="mt-3"><p class="mb-1 text-xs font-semibold text-primary">复盘原文</p><p class="whitespace-pre-wrap text-sm leading-6 muted">{{ reviewTextOf(item) }}</p></div></article><UEmpty v-if="!reviews.length" title="暂无历史复盘" description="完成第一次周期复盘后会显示在这里。"/></div></template></UModal>
    <JobPickerDialog v-model:open="pickerOpen" title="选择报告目标岗位" multiple :selected-ids="targets.map(item => item.job_id)" @select="addTarget" />
  </div>
</template>

<style scoped>
.report-workspace { display: grid; gap: 1rem; align-items: start; }
.report-main { display: grid; min-width: 0; gap: 1.25rem; }
.section-heading { margin: .25rem 0 .8rem; }
.section-heading h2 { font-size: 1.2rem; font-weight: 700; }
.section-heading p { margin-top: .2rem; font-size: .875rem; color: var(--ui-text-muted); }
.target-grid { display: grid; gap: .75rem; }
.metric { display: grid; border-radius: .6rem; background: var(--ui-bg-elevated); padding: .55rem .25rem; }
.metric strong { font-size: 1rem; }
.metric span { font-size: .65rem; color: var(--ui-text-muted); }
.timeline-node { max-width: 11rem; border-radius: 999px; background: color-mix(in srgb, var(--ui-primary) 12%, transparent); padding: .4rem .65rem; color: var(--ui-primary); font-size: .75rem; font-weight: 600; text-align: center; }
@media (min-width: 768px) { .target-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (min-width: 1280px) { .report-workspace { grid-template-columns: 19rem minmax(0, 1fr); } }
</style>
