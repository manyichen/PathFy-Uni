<script setup lang="ts">
import type {
  CareerReport, ReportPlanChange, ReportPlanProposal, ReportPlanVersion,
  ReportReview, ReportReviewCycle, ReportReviewDraft, ReportTarget
} from '~/types/api'

const props = defineProps<{
  report: CareerReport
  reviews: ReportReview[]
  planVersions: ReportPlanVersion[]
  draft?: ReportReviewDraft
  proposal?: ReportPlanProposal
  reviewText: string
  reviewScope: 'target' | 'all'
  reviewCycle: ReportReviewCycle
  reviewSignal: 'normal' | 'goal_changed' | 'overloaded' | 'stalled' | 'evidence_missing'
  activeTarget?: ReportTarget
  loading: string
}>()

const emit = defineEmits<{
  'update:reviewText': [value: string]
  'update:reviewScope': [value: 'target' | 'all']
  'update:reviewCycle': [value: ReportReviewCycle]
  'update:reviewSignal': [value: 'normal' | 'goal_changed' | 'overloaded' | 'stalled' | 'evidence_missing']
  'apply-template': []
  'create-draft': []
  'confirm-draft': []
  'decide-proposal': [decision: 'accept' | 'reject']
}>()

const reviewModel = computed({ get: () => props.reviewText, set: value => emit('update:reviewText', value) })
const scopeModel = computed({ get: () => props.reviewScope, set: value => emit('update:reviewScope', value) })
const cycleModel = computed({ get: () => props.reviewCycle, set: value => emit('update:reviewCycle', value) })
const signalModel = computed({ get: () => props.reviewSignal, set: value => emit('update:reviewSignal', value) })
const preferenceSignals = defineModel<{ energy_after_tasks: number; collaboration_fit: number; structure_fit: number; task_mode_fit: number; note: string }>('preferenceSignals', { required: true })

const scopeItems = computed(() => [
  { label: `当前岗位：${props.activeTarget?.display_title || props.activeTarget?.title || '已选岗位'}`, value: 'target' },
  { label: '全部目标（共享计划）', value: 'all' }
])
const cycleItems = [{ label: '周复盘（短周期校准）', value: 'weekly' }, { label: '月复盘（阶段评估）', value: 'monthly' }]
const signalItems = [
  { label: '正常推进', value: 'normal' },
  { label: '目标已变化', value: 'goal_changed' },
  { label: '任务过载', value: 'overloaded' },
  { label: '推进停滞', value: 'stalled' },
  { label: '成果证据缺失', value: 'evidence_missing' }
]
const latestEvaluation = computed(() => props.report.evaluation?.latest_review?.evaluation)
const latestHasEvidence = computed(() => latestEvaluation.value?.has_evidence === true || Number(latestEvaluation.value?.evaluated_count || 0) > 0)
const latestPassRateLabel = computed(() => latestHasEvidence.value
  ? `${Number(latestEvaluation.value?.missing_count || 0) > 0 ? `已评估 ${Number(latestEvaluation.value?.evaluated_count || 0)} 项 · ` : ''}通过率 ${Math.round(Number(latestEvaluation.value?.pass_rate || 0) * 100)}%`
  : '待补量化证据')
const currentStep = computed(() => props.proposal ? 3 : props.draft ? 2 : 1)
const reviewStageLabel = computed(() => ['记录现场', '核对事实', '决定转向'][currentStep.value - 1] || '记录现场')
const echoStrength = computed(() => Math.min(100, Math.round(
  Math.min(props.reviewText.trim().length, 240) / 4.8
  + (props.draft?.candidates.length || 0) * 7
  + (latestHasEvidence.value ? 24 : 0)
)))
const metricNodes = computed(() => {
  const metrics = props.report.evaluation?.metrics || []
  return metrics.slice(0, 8).map((metric, index, items) => {
    const angle = -Math.PI / 2 + index / Math.max(1, items.length) * Math.PI * 2
    const radius = items.length < 4 ? 72 : 92
    return {
      ...metric,
      x: 160 + Math.cos(angle) * radius,
      y: 126 + Math.sin(angle) * radius
    }
  })
})

function echoPath(ring: number) {
  const points: string[] = []
  const radius = 34 + ring * 13
  const seed = props.reviews.length * 17 + (props.draft?.candidates.length || 0) * 11 + currentStep.value * 23
  for (let index = 0; index <= 72; index += 1) {
    const angle = index / 72 * Math.PI * 2
    const ripple = Math.sin(angle * (ring + 3) + seed * .04) * (2.1 + ring * .48)
      + Math.cos(angle * 2 - seed * .025) * 1.35
    const radiusAtPoint = radius + ripple
    points.push(`${index ? 'L' : 'M'}${(160 + Math.cos(angle) * radiusAtPoint).toFixed(2)},${(126 + Math.sin(angle) * radiusAtPoint).toFixed(2)}`)
  }
  return `${points.join(' ')} Z`
}

const echoPaths = computed(() => Array.from({ length: 4 }, (_, index) => echoPath(index)))

function confidenceLabel(value: number) {
  if (value >= .9) return '高可信'
  if (value >= .7) return '需核对'
  return '低可信'
}

function setCandidateDecision(candidate: ReportReviewDraft['candidates'][number], decision: 'confirm' | 'ignore') {
  candidate.decision = decision
}

function changeLabel(change: ReportPlanChange) {
  if (change.kind === 'replace_target_plan') return `更新 ${change.job_id || '目标岗位'} 的下月计划`
  if (change.kind === 'replace_growth_plan') return '更新共享成长计划'
  if (change.kind === 'append_adjustments') return `新增 ${Array.isArray(change.after) ? change.after.length : 1} 条路线调整记录`
  return '计划变更'
}

interface EditableProposalAction { text?: string; title?: string; deliverable?: string; deadline?: string; effort_hours?: number }
function editableActions(change: ReportPlanChange): EditableProposalAction[] {
  if (change.kind !== 'replace_target_plan' || !change.after || typeof change.after !== 'object') return []
  const nextPlan = (change.after as { next_month_plan?: { items?: Array<{ custom_actions?: EditableProposalAction[] }> } }).next_month_plan
  return (nextPlan?.items || []).flatMap(item => item.custom_actions || [])
}

function actionText(action: EditableProposalAction) {
  return action.title || action.text || action.deliverable || '未命名行动'
}

function versionStatus(item: ReportPlanVersion) {
  if (item.stale) return '已过期'
  return ({ proposed: '待决定', accepted: '已接受', rejected: '已拒绝' } as const)[item.status]
}
</script>

<template>
  <section class="review-studio">
    <nav class="review-step-rail" aria-label="复盘流程">
      <span v-for="(item,index) in ['记录发生了什么','核对可用事实','决定是否转向']" :key="item" :class="{ active: currentStep === index + 1, done: currentStep > index + 1 }"><i>{{ String(index + 1).padStart(2,'0') }}</i><b>{{ item }}</b></span>
    </nav>

    <div class="review-grid">
      <aside class="metric-observatory">
        <header><span>EVALUATION CONSTELLATION</span><h3>本轮观察星群</h3><p>只有经你确认的事实才会点亮节点；空白不是零分。</p></header>
        <svg v-if="metricNodes.length" viewBox="0 0 320 252" role="img" aria-label="复盘评估指标星群">
          <defs>
            <filter id="review-node-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
            <radialGradient id="review-core-paper" cx="36%" cy="30%"><stop offset="0" stop-color="#fffdf2" /><stop offset="1" stop-color="#eadba7" /></radialGradient>
          </defs>
          <g class="orbit-crosshair"><line x1="160" y1="20" x2="160" y2="232" /><line x1="54" y1="126" x2="266" y2="126" /></g>
          <circle class="orbit-guide" cx="160" cy="126" r="93" />
          <path v-for="(path,index) in echoPaths" :key="`echo-${index}`" class="echo-loop" :style="{ '--echo-ring': index }" :d="path" />
          <line v-for="node in metricNodes" :key="`line-${node.code}`" class="orbit-line" x1="160" y1="126" :x2="node.x" :y2="node.y" />
          <g v-for="(node,index) in metricNodes" :key="node.code" class="metric-node">
            <circle class="metric-node-halo" :cx="node.x" :cy="node.y" :r="index === 0 ? 15 : 12" />
            <circle :cx="node.x" :cy="node.y" :r="index === 0 ? 9 : 7" />
            <text :x="node.x" :y="node.y + (node.y < 126 ? -14 : 19)" text-anchor="middle">{{ node.label }}</text>
          </g>
          <circle class="orbit-core" :class="{ confirmed: latestHasEvidence }" cx="160" cy="126" r="28" />
          <text class="orbit-core-value" x="160" y="124" text-anchor="middle">{{ reviews.length }}</text>
          <text class="orbit-core-label" x="160" y="139" text-anchor="middle">确认复盘</text>
        </svg>
        <div v-else class="metric-empty">尚未配置评估指标，仍可记录真实进展。</div>
        <div class="observatory-status">
          <span><i />当前阶段</span><strong>{{ String(currentStep).padStart(2, '0') }} · {{ reviewStageLabel }}</strong>
          <span><i />事实回声</span><strong>{{ echoStrength }} / 100</strong>
        </div>
        <div class="metric-ledger">
          <article v-for="(metric,index) in report.evaluation?.metrics || []" :key="metric.code">
            <span>{{ String(index + 1).padStart(2,'0') }}</span><div><strong>{{ metric.label }}</strong><p>{{ metric.description }}</p></div><em>{{ metric.target || '待设目标' }}</em>
          </article>
        </div>
      </aside>

      <div class="review-flow">
        <section class="review-sheet">
          <header><span>WORKSTYLE CHECK-IN</span><h3>本周期的工作方式体验</h3><p>每项 1–5 分。单次反馈不会修改人格画像；连续 3 个周期同向才会提示校准。</p></header>
          <div class="review-selectors">
            <UFormField label="任务后精力"><UInput v-model.number="preferenceSignals.energy_after_tasks" type="number" min="1" max="5" /></UFormField>
            <UFormField label="协作方式适配"><UInput v-model.number="preferenceSignals.collaboration_fit" type="number" min="1" max="5" /></UFormField>
            <UFormField label="时间结构适配"><UInput v-model.number="preferenceSignals.structure_fit" type="number" min="1" max="5" /></UFormField>
            <UFormField label="任务切入方式适配"><UInput v-model.number="preferenceSignals.task_mode_fit" type="number" min="1" max="5" /></UFormField>
          </div>
          <UInput v-model="preferenceSignals.note" class="mt-3" placeholder="可选：记录最顺手或最消耗的工作方式" />
        </section>
        <section class="review-sheet review-input-sheet">
          <header class="sheet-heading"><div><span>01 / RAW NOTE</span><h3>写下真实发生的事</h3><p>先生成草稿，不会直接评估或改动计划。</p></div><UButton size="xs" color="neutral" variant="ghost" @click="emit('apply-template')">填入模板</UButton></header>
          <UTextarea v-model="reviewModel" :rows="8" autoresize :maxrows="14" placeholder="本月完成了什么、能力哪里进步、有没有新成果、下月准备做什么…" class="w-full" />
          <div class="review-selectors">
            <label>复盘周期<USelect v-model="cycleModel" :items="cycleItems" /></label>
            <label>作用范围<USelect v-model="scopeModel" :items="scopeItems" /></label>
          </div>
          <UButton class="mt-3" block :loading="loading === 'review-draft'" :disabled="Boolean(draft)" @click="emit('create-draft')">生成可核对草稿</UButton>
        </section>

        <section v-if="draft" class="review-sheet review-fact-sheet">
          <header class="sheet-heading"><div><span>02 / FACT CHECK</span><h3>只让确认过的事实通过</h3><p>数值可以修改；未确认的候选不会参与本次评估。</p></div><b>{{ draft.candidates.length }} 条候选</b></header>
          <p v-if="draft.summary" class="sheet-summary">{{ draft.summary }}</p>
          <div v-if="draft.candidates.length" class="candidate-list">
            <article v-for="candidate in draft.candidates" :key="candidate.code" class="candidate-card" :class="`decision-${candidate.decision}`">
              <span class="candidate-signal" />
              <div class="candidate-copy"><strong>{{ candidate.label }}</strong><small>目标：{{ candidate.target || '未设置' }}</small><blockquote>“{{ candidate.source_text }}”</blockquote></div>
              <div class="candidate-controls"><UBadge :label="confidenceLabel(candidate.confidence)" :color="candidate.confidence >= .9 ? 'success' : 'warning'" variant="soft" /><UInput v-model.number="candidate.value" type="number" class="w-28" aria-label="确认值" /><span><UButton size="xs" :variant="candidate.decision === 'confirm' ? 'solid' : 'soft'" @click="setCandidateDecision(candidate, 'confirm')">确认采用</UButton><UButton size="xs" color="neutral" :variant="candidate.decision === 'ignore' ? 'solid' : 'soft'" @click="setCandidateDecision(candidate, 'ignore')">忽略</UButton></span></div>
            </article>
          </div>
          <UAlert v-else color="neutral" variant="soft" title="未识别到量化指标" description="仍可确认并保存真实复盘，系统会标记为“数据不足”，不会自动判失败或生成计划变更。" />
          <label class="signal-selector">真实情况修正<USelect v-model="signalModel" :items="signalItems" /></label>
          <UButton class="mt-3" block :loading="loading === 'review-confirm'" @click="emit('confirm-draft')">确认复盘事实</UButton>
        </section>

        <section v-if="proposal" class="review-sheet review-proposal-sheet">
          <header class="sheet-heading"><div><span>03 / TURNING POINT</span><h3>决定下一轮是否转向</h3><p>默认全选，也可以只接受部分变更。</p></div><UBadge label="尚未生效" color="warning" variant="soft" /></header>
          <UAlert v-if="proposal.stale" color="warning" variant="soft" title="提案已过期" description="当前计划已在提案生成后变化，请重新复盘。" />
          <div v-else class="proposal-list">
            <label v-for="change in proposal.changes" :key="change.id" class="change-row"><input v-model="change.accepted" type="checkbox" :aria-label="`选择${changeLabel(change)}`"><span><strong>{{ changeLabel(change) }}</strong><small v-if="change.summary">保留 {{ change.summary.kept?.length || 0 }} · 新增 {{ change.summary.added?.length || 0 }} · 移除 {{ change.summary.removed?.length || 0 }}</small><small>变更编号 {{ change.id }}</small><span v-if="change.accepted && editableActions(change).length" class="editable-actions" @click.stop><span v-for="(action, actionIndex) in editableActions(change)" :key="actionIndex"><b>{{ actionText(action) }}</b><span><UInput v-model="action.deadline" placeholder="截止时间" aria-label="编辑截止时间" /><UInput v-model.number="action.effort_hours" type="number" placeholder="投入小时" aria-label="编辑投入小时" /></span></span></span></span></label>
            <div class="proposal-actions"><UButton color="neutral" variant="soft" :loading="loading === 'plan-proposal'" @click="emit('decide-proposal','reject')">拒绝并保留当前计划</UButton><UButton :disabled="!proposal.changes.some(item => item.accepted)" :loading="loading === 'plan-proposal'" @click="emit('decide-proposal','accept')">应用所选变更</UButton></div>
          </div>
        </section>

        <section v-if="report.evaluation?.latest_review || planVersions.length" class="review-archive">
          <header><span>ARCHIVE / 复盘档案</span><h3>每一次转向都有版本</h3><p>历史只读，保留接受、拒绝和过期状态。</p></header>
          <div v-if="report.evaluation?.latest_review" class="latest-review"><span><strong>最近一次复盘</strong><small>状态：{{ report.evaluation.latest_review.status || '未分类' }}</small></span><UBadge :label="latestPassRateLabel" :color="latestHasEvidence ? 'primary' : 'neutral'" variant="soft" /></div>
          <div v-if="planVersions.length" class="version-strip"><article v-for="item in planVersions.slice(0, 8)" :key="item.proposal_id"><span><strong>#{{ item.proposal_id }}</strong><small>{{ item.changes.length }} 项变更<br>{{ item.created_at }}</small></span><UBadge :label="versionStatus(item)" :color="item.status === 'accepted' ? 'success' : item.stale ? 'warning' : 'neutral'" variant="soft" /></article></div>
        </section>
      </div>
    </div>
  </section>
</template>

<style scoped>
.review-studio { --review-mint: #67e8c2; --review-ink: #24383c; display: grid; gap: 1rem; }
.review-step-rail { position: relative; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); overflow: hidden; border-top: 1px solid var(--pathfy-line); border-bottom: 1px solid var(--pathfy-line); padding: .7rem 0; }
.review-step-rail::before { position: absolute; top: 50%; right: 8%; left: 8%; height: 1px; background: color-mix(in srgb, var(--pathfy-route) 20%, var(--pathfy-line)); content: ""; }
.review-step-rail span { position: relative; z-index: 1; display: flex; min-width: 0; align-items: center; justify-content: center; gap: .55rem; color: var(--ui-text-muted); }
.review-step-rail i { display: grid; width: 2rem; height: 2rem; place-items: center; border: 1px solid var(--pathfy-line); border-radius: 50%; background: var(--ui-bg); font: 750 .64rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; }
.review-step-rail b { max-width: 10rem; background: var(--ui-bg); padding: 0 .35rem; font-size: .72rem; font-weight: 650; }
.review-step-rail span.active { color: var(--pathfy-route); }.review-step-rail span.active i { border-color: var(--pathfy-route); background: color-mix(in srgb, var(--pathfy-route) 10%, var(--ui-bg)); box-shadow: 0 0 0 .35rem color-mix(in srgb, var(--pathfy-route) 6%, transparent); }.review-step-rail span.done i { border-color: var(--review-mint); background: #0f766e; color: white; }
.review-grid { display: grid; gap: clamp(1rem, 2vw, 1.7rem); align-items: start; }
.metric-observatory { position: relative; overflow: hidden; border: 1px solid rgb(103 232 194 / .16); border-radius: 1.7rem .45rem 1.7rem .45rem; background: radial-gradient(circle at 50% 29%, rgb(30 151 145 / .23), transparent 27%), linear-gradient(145deg, #082f36, #061b27 75%); padding: clamp(1.1rem, 2.4vw, 1.8rem); color: #effcf8; box-shadow: 0 34px 65px -48px rgb(3 24 31 / .95); }
.metric-observatory::before { position: absolute; inset: 0; background-image: radial-gradient(rgb(103 232 194 / .16) .7px, transparent .7px); background-size: 20px 20px; mask-image: linear-gradient(#000, transparent 84%); content: ""; pointer-events: none; }
.metric-observatory::after { position: absolute; right: -7rem; bottom: -8rem; width: 18rem; height: 18rem; border: 1px solid rgb(103 232 194 / .06); border-radius: 46% 54% 62% 38%; box-shadow: 0 0 0 2rem rgb(103 232 194 / .025), 0 0 0 4rem rgb(103 232 194 / .018); content: ""; transform: rotate(18deg); }
.metric-observatory > * { position: relative; z-index: 1; }.metric-observatory header > span { color: var(--review-mint); font: 800 .64rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .12em; }.metric-observatory header h3 { margin-top: .35rem; font-size: 1.4rem; font-weight: 760; }.metric-observatory header p { margin-top: .35rem; color: rgb(226 242 242 / .62); font-size: .72rem; line-height: 1.65; }
.metric-observatory svg { display: block; width: 100%; max-height: 21rem; margin: .7rem auto .1rem; overflow: visible; }.orbit-crosshair { stroke: rgb(255 255 255 / .045); stroke-width: .6; stroke-dasharray: 1 7; }.orbit-guide { fill: none; stroke: rgb(255 255 255 / .11); stroke-dasharray: 2 6; }.echo-loop { fill: none; stroke: color-mix(in srgb, var(--review-mint) calc(34% + var(--echo-ring) * 11%), #b8f7ff); stroke-width: calc(.7px + var(--echo-ring) * .2px); stroke-dasharray: calc(2px + var(--echo-ring) * .7px) calc(1.5px + var(--echo-ring) * .55px); opacity: calc(.3 + var(--echo-ring) * .12); transform-origin: 160px 126px; animation: review-echo-in 1.05s cubic-bezier(.22, 1, .36, 1) both; animation-delay: calc(var(--echo-ring) * 80ms); }.orbit-line { stroke: rgb(103 232 194 / .16); stroke-width: .7; stroke-dasharray: 2 5; }.metric-node-halo { fill: none !important; stroke: rgb(103 232 194 / .14) !important; stroke-width: 1; }.metric-node > circle:not(.metric-node-halo) { fill: #67e8c2; stroke: #dcfff4; stroke-width: 1.3; filter: url(#review-node-glow); }.metric-node:nth-of-type(3n) > circle:not(.metric-node-halo) { fill: #f0d77b; }.metric-node text { fill: rgb(236 250 247 / .78); font-size: 6.5px; font-weight: 650; }.orbit-core { fill: url(#review-core-paper); stroke: rgb(255 255 255 / .38); stroke-width: 1.2; }.orbit-core.confirmed { stroke: var(--review-mint); filter: url(#review-node-glow); }.orbit-core-value { fill: #082f36; font-size: 17px; font-weight: 850; }.orbit-core-label { fill: #416168; font-size: 6px; letter-spacing: .08em; }
.observatory-status { display: grid; grid-template-columns: auto 1fr; gap: .28rem .7rem; margin: .2rem .2rem 1rem; border-top: 1px dashed rgb(255 255 255 / .12); border-bottom: 1px dashed rgb(255 255 255 / .12); padding: .7rem 0; }.observatory-status span { display: flex; align-items: center; gap: .35rem; color: rgb(226 242 242 / .48); font-size: .62rem; }.observatory-status i { width: .3rem; height: .3rem; border-radius: 50%; background: var(--review-mint); box-shadow: 0 0 9px var(--review-mint); }.observatory-status strong { justify-self: end; color: rgb(239 252 248 / .86); font-size: .66rem; }
.metric-ledger { display: grid; }.metric-ledger article { display: grid; grid-template-columns: 1.5rem minmax(0, 1fr) auto; gap: .6rem; align-items: start; border-top: 1px solid rgb(255 255 255 / .09); padding: .7rem .1rem; }.metric-ledger article > span { color: var(--review-mint); font: 750 .58rem/1.5 ui-monospace, monospace; }.metric-ledger strong { display: block; font-size: .72rem; }.metric-ledger p { margin-top: .15rem; color: rgb(226 242 242 / .5); font-size: .62rem; line-height: 1.45; }.metric-ledger em { color: #f0d77b; font-size: .62rem; font-style: normal; }.metric-empty { display: grid; min-height: 12rem; place-items: center; color: rgb(226 242 242 / .52); font-size: .72rem; text-align: center; }
.review-flow { position: relative; display: grid; gap: 0; overflow: hidden; border: 1px solid rgb(141 118 78 / .22); border-radius: .35rem 1.35rem 1.35rem .35rem; background: linear-gradient(90deg, rgb(141 118 78 / .055) 1px, transparent 1px), linear-gradient(#fffdf7, #faf8ef); background-size: 30px 100%, 100% 100%; color: var(--review-ink); box-shadow: 0 34px 70px -54px rgb(47 39 25 / .75); }
.review-flow::before { position: absolute; top: 0; bottom: 0; left: 1.2rem; width: 1px; background: rgb(190 24 93 / .12); content: ""; }.review-sheet { position: relative; padding: clamp(1.2rem, 2.7vw, 2rem) clamp(1.1rem, 3vw, 2.2rem) clamp(1.2rem, 2.7vw, 2rem) clamp(2rem, 4vw, 3.1rem); border-bottom: 1px dashed rgb(36 56 60 / .2); }.review-sheet::after { position: absolute; right: 1.2rem; bottom: -.34rem; color: rgb(36 56 60 / .25); font: 650 .55rem/1 ui-monospace, monospace; letter-spacing: .08em; content: "PATHFY / VERIFIED REVIEW"; }.review-fact-sheet { background: linear-gradient(110deg, rgb(207 232 235 / .26), transparent 68%); }.review-proposal-sheet { background: linear-gradient(110deg, rgb(240 215 123 / .2), transparent 68%); }.review-fact-sheet::before, .review-proposal-sheet::before { position: absolute; top: -.38rem; left: 50%; width: 4rem; height: 1rem; background: rgb(255 255 255 / .62); box-shadow: 0 2px 5px rgb(47 39 25 / .08); content: ""; transform: translateX(-50%) rotate(-1.5deg); }
.sheet-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }.sheet-heading span { color: #0f766e; font: 800 .62rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .11em; }.sheet-heading h3 { margin-top: .28rem; font-size: 1.2rem; font-weight: 780; letter-spacing: -.02em; }.sheet-heading p { margin-top: .3rem; color: rgb(36 56 60 / .62); font-size: .72rem; line-height: 1.6; }.sheet-heading > b { color: #987217; font-size: .68rem; }.sheet-summary { margin-bottom: .9rem; border-left: 2px solid #0f766e; padding: .55rem .8rem; background: rgb(255 255 255 / .45); color: rgb(36 56 60 / .72); font-size: .74rem; line-height: 1.65; }
.review-sheet :deep(textarea), .review-sheet :deep(input), .review-sheet :deep(button[role=combobox]) { border-color: rgb(36 56 60 / .18) !important; background: rgb(255 255 255 / .66) !important; color: var(--review-ink) !important; }.review-sheet :deep(textarea) { min-height: 10.5rem; background-image: repeating-linear-gradient(transparent 0, transparent 1.75rem, rgb(36 56 60 / .07) 1.8rem) !important; line-height: 1.8rem; }
.review-selectors { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; margin-top: .8rem; }.review-selectors label, .signal-selector { display: grid; gap: .35rem; color: rgb(36 56 60 / .65); font-size: .68rem; }.signal-selector { margin-top: 1rem; }
.candidate-list { display: grid; }.candidate-card { position: relative; display: grid; grid-template-columns: .6rem minmax(0, 1fr) auto; gap: .8rem; align-items: center; border-top: 1px dashed rgb(36 56 60 / .17); padding: 1rem .1rem; }.candidate-card:first-child { border-top: 0; }.candidate-signal { width: .42rem; height: 2.6rem; border-radius: 999px; background: #0f766e; }.decision-ignore { opacity: .52; }.decision-ignore .candidate-signal { background: rgb(36 56 60 / .28); }.candidate-copy strong, .candidate-copy small { display: block; }.candidate-copy strong { font-size: .8rem; }.candidate-copy small { margin-top: .15rem; color: rgb(36 56 60 / .54); font-size: .64rem; }.candidate-copy blockquote { margin-top: .35rem; color: rgb(36 56 60 / .68); font-size: .7rem; line-height: 1.5; }.candidate-controls { display: grid; justify-items: end; gap: .45rem; }.candidate-controls > span { display: flex; gap: .3rem; }
.proposal-list { display: grid; gap: .7rem; }.change-row { display: flex; gap: .75rem; border: 1px solid rgb(36 56 60 / .16); border-radius: .2rem .8rem .8rem .2rem; background: rgb(255 255 255 / .4); padding: .85rem; cursor: pointer; transition: transform 160ms ease, background 160ms ease; }.change-row:hover { background: rgb(255 255 255 / .7); transform: translateX(.2rem); }.change-row > span { display: grid; flex: 1; gap: .25rem; }.change-row small { color: rgb(36 56 60 / .56); font-size: .64rem; }.editable-actions { display: grid; gap: .55rem; margin-top: .55rem; border-top: 1px dashed rgb(36 56 60 / .16); padding-top: .55rem; }.editable-actions > span { display: grid; grid-template-columns: minmax(8rem, 1fr) 1.2fr; gap: .6rem; align-items: center; }.editable-actions > span > span { display: grid; grid-template-columns: 1fr 1fr; gap: .4rem; }.proposal-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .5rem; margin-top: .35rem; }
.review-archive { position: relative; display: grid; gap: 1rem; padding: clamp(1.2rem, 2.7vw, 2rem) clamp(1.1rem, 3vw, 2.2rem) clamp(1.4rem, 3vw, 2.2rem) clamp(2rem, 4vw, 3.1rem); background: #0a3038; color: #effcf8; }.review-archive header > span { color: var(--review-mint); font: 800 .62rem/1.4 ui-monospace, monospace; letter-spacing: .1em; }.review-archive header h3 { margin-top: .35rem; font-size: 1.15rem; }.review-archive header p { margin-top: .25rem; color: rgb(226 242 242 / .55); font-size: .68rem; }.latest-review { display: flex; align-items: center; justify-content: space-between; gap: 1rem; border-top: 1px dashed rgb(255 255 255 / .12); border-bottom: 1px dashed rgb(255 255 255 / .12); padding: .7rem 0; }.latest-review strong, .latest-review small { display: block; }.latest-review strong { font-size: .76rem; }.latest-review small { margin-top: .15rem; color: rgb(226 242 242 / .5); font-size: .62rem; }.version-strip { display: flex; gap: .65rem; overflow-x: auto; padding-bottom: .25rem; }.version-strip article { display: flex; min-width: 12rem; align-items: center; justify-content: space-between; gap: .7rem; border-left: 2px solid var(--review-mint); background: rgb(255 255 255 / .055); padding: .7rem .75rem; }.version-strip strong, .version-strip small { display: block; }.version-strip strong { font-size: .72rem; }.version-strip small { margin-top: .15rem; color: rgb(226 242 242 / .5); font-size: .58rem; line-height: 1.5; }
@keyframes review-echo-in { from { opacity: 0; transform: scale(.82) rotate(-8deg); } }
@media (min-width: 1024px) { .review-grid { grid-template-columns: minmax(19rem, .78fr) minmax(31rem, 1.22fr); }.metric-observatory { position: sticky; top: 6rem; } }
@media (max-width: 720px) { .review-step-rail b { display: none; }.review-step-rail::before { right: 17%; left: 17%; }.review-flow::before { left: .65rem; }.review-sheet, .review-archive { padding: 1.25rem 1rem 1.4rem 1.45rem; }.review-selectors { grid-template-columns: 1fr; }.candidate-card { grid-template-columns: .45rem minmax(0, 1fr); }.candidate-controls { grid-column: 2; grid-template-columns: auto 1fr auto; align-items: center; justify-items: stretch; }.editable-actions > span, .editable-actions > span > span { grid-template-columns: 1fr; }.proposal-actions { justify-content: stretch; }.proposal-actions > * { flex: 1; } }
@media (prefers-reduced-motion: reduce) { .echo-loop { animation: none; }.change-row { transition: none; } }
</style>
