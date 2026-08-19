<script setup lang="ts">
import { computed } from 'vue'
import type { DevelopmentAdjustment, DevelopmentLine, ReportNextMonthPlan, ReportPlan, ReportPlanChange, ReportPlanProposal } from '~/types/api'

const props = defineProps<{
  month: number
  line?: DevelopmentLine
  adjustments: DevelopmentAdjustment[]
  plan?: ReportPlan
  proposal?: ReportPlanProposal
  jobId?: string
}>()
const emit = defineEmits<{ openReview: [] }>()

const review = computed(() => props.line?.timeline?.find(item => Math.round(Number(item.month) || 0) === props.month && item.kind === 'review'))
const adjustments = computed(() => props.adjustments.filter(item => Math.round(Number(item.anchor_review_month ?? item.month) || 0) === props.month))
const submitted = computed(() => Object.entries(review.value?.detail?.submitted || {}))
const actionCompletion = computed(() => review.value?.detail?.action_completion)
const completedActions = computed(() => Number(actionCompletion.value?.done_count || 0))
const totalActions = computed(() => Number(actionCompletion.value?.total_count || 0))
const previousProgress = computed(() => {
  const points = (props.line?.timeline || [])
    .filter(item => item.kind === 'review' && Number(item.month) < props.month)
    .sort((a, b) => Number(b.month) - Number(a.month))
  return Number(points[0]?.progress || 0)
})
const progressGain = computed(() => Math.max(0, Number(review.value?.progress || 0) - previousProgress.value))

function planFromChange(change?: ReportPlanChange): ReportNextMonthPlan | undefined {
  const after = change?.after
  if (!after || typeof after !== 'object') return undefined
  return (after as ReportPlan).next_month_plan
}

const pendingPlan = computed(() => {
  const change = props.proposal?.changes.find(item => item.kind === 'replace_target_plan' && (!props.jobId || item.job_id === props.jobId))
  const plan = planFromChange(change)
  if (!plan) return undefined
  const anchor = Number(plan.review_anchor_month)
  const planMonth = Number(plan.plan_month)
  return anchor === props.month || planMonth === props.month + 1 ? plan : undefined
})
const appliedPlan = computed(() => {
  const plan = props.plan?.next_month_plan
  if (!plan) return undefined
  const anchor = Number(plan.review_anchor_month)
  const planMonth = Number(plan.plan_month)
  return anchor === props.month || planMonth === props.month + 1 ? plan : undefined
})
const nextArrangement = computed(() => pendingPlan.value || appliedPlan.value)
const arrangementPending = computed(() => Boolean(pendingPlan.value))
const arrangementActions = computed(() => (nextArrangement.value?.items || []).flatMap(item => item.custom_actions || []))
const statusLabel = computed(() => review.value
  ? nextArrangement.value
    ? arrangementPending.value ? '已复盘 · 待确认下月计划' : '已复盘 · 下月计划已生效'
    : '已复盘'
  : adjustments.value.length ? '计划节点' : props.month === 0 ? '路线起点' : '等待记录')

function display(value: unknown) { return typeof value === 'object' ? JSON.stringify(value) : String(value ?? '-') }
</script>

<template>
  <section class="month-logbook" :data-state="review?'review':adjustments.length?'plan':'empty'" aria-labelledby="month-detail-heading">
    <header class="logbook-heading">
      <div class="logbook-index"><span>02 / MONTH LOG</span><strong>{{ String(month).padStart(2, '0') }}</strong></div>
      <div><p>SELECTED COORDINATE / 已选坐标</p><h3 id="month-detail-heading">第 {{ month }} 月详情</h3><span>{{ review ? '同时查看本月事实、轨迹推进依据和下一月安排。' : adjustments.length ? '这一坐标记录了计划转向与下一段执行要求。' : month===0?'这是报告生成时的路线原点。':'这一月尚未写入计划或复盘。' }}</span></div>
      <div class="logbook-status"><i aria-hidden="true" /><span>{{ statusLabel }}</span><small>{{ review ? 'VERIFIED' : adjustments.length ? 'PLANNED' : 'OPEN' }}</small></div>
    </header>

    <div v-if="review || adjustments.length || nextArrangement" class="detail-grid">
      <section v-if="review" class="review-sheet">
        <div class="sheet-tape" aria-hidden="true" />
        <header><span>01 / FIELD RECORD</span><h4>这一个月，真实发生了什么</h4></header>
        <blockquote v-if="review.detail?.review_text" class="pre">{{ review.detail.review_text }}</blockquote>
        <p v-if="review.detail?.llm_summary" class="summary"><strong>复盘摘录</strong>{{ review.detail.llm_summary }}</p>
        <div v-if="submitted.length" class="metric-list">
          <span>SUBMITTED EVIDENCE</span>
          <div v-for="(entry,index) in submitted" :key="entry[0]"><small>{{ String(index+1).padStart(2,'0') }}</small><strong>{{ entry[0] }}：<b>{{ display(entry[1]) }}</b></strong></div>
        </div>
      </section>

      <section v-if="review" class="growth-receipt">
        <header><span>02 / GROWTH RECEIPT</span><h4>这次轨迹为什么移动</h4></header>
        <div class="growth-score"><strong>+{{ progressGain.toFixed(1) }}</strong><span>本月轨迹推进</span><small>累计 {{ Number(review.progress || 0).toFixed(1) }} / 100</small></div>
        <div class="growth-basis">
          <div><span>行动执行</span><strong>{{ completedActions }} / {{ totalActions || '—' }}</strong><small>{{ totalActions ? `完成率 ${Math.round(completedActions / totalActions * 100)}%` : '当次未找到可核对清单' }}</small></div>
          <div><span>量化指标</span><strong>{{ submitted.length }}</strong><small>{{ submitted.length ? '项已确认指标' : '本次未确认数值指标' }}</small></div>
        </div>
        <p>{{ progressGain > 0 ? '推进值只来自已勾选并保存的行动与已确认指标；它代表计划执行和验证进展，不等同于能力分。' : '本次只有文字记录，尚无已保存的完成行动或已确认指标，因此系统不会凭空增加成长值。' }}</p>
      </section>

      <section v-if="nextArrangement" class="next-plan-sheet" :data-pending="arrangementPending">
        <div class="plan-pin" aria-hidden="true" />
        <header><span>03 / NEXT MONTH</span><h4>第 {{ nextArrangement.plan_month || month + 1 }} 月安排</h4></header>
        <div class="plan-state"><span>{{ arrangementPending ? '待你确认后生效' : '已进入执行清单' }}</span><small>{{ nextArrangement.phase_label || '延续当前发展阶段' }}</small></div>
        <div class="next-plan-items">
          <article v-for="(item,index) in nextArrangement.items || []" :key="`${item.focus_dimension || 'item'}-${index}`">
            <small>{{ String(index + 1).padStart(2, '0') }}</small>
            <div><strong>{{ item.milestone || item.focus_label || '继续推进阶段目标' }}</strong><span>{{ item.focus_label || '阶段任务' }}</span></div>
          </article>
        </div>
        <ul v-if="arrangementActions.length"><li v-for="(action,index) in arrangementActions.slice(0,6)" :key="action.action_uid || `${action.text}-${index}`"><UIcon :name="action.done ? 'i-lucide-check-circle-2' : 'i-lucide-circle'" /><span>{{ action.text || action.deliverable || '待执行行动' }}</span></li></ul>
        <UButton v-if="arrangementPending" size="sm" icon="i-lucide-list-checks" @click="emit('openReview')">前往复盘页核对并应用</UButton>
      </section>

      <section v-for="planAdjustment in adjustments" :key="planAdjustment.id" class="plan-sheet">
        <div class="plan-pin" aria-hidden="true" />
        <header><span>04 / COURSE CORRECTION</span><h4>路线调整依据</h4></header>
        <p class="plan-thesis">{{ planAdjustment.label || planAdjustment.focus_label || '继续执行当前计划' }}</p>
        <ul v-if="planAdjustment.execution_hints?.length"><li v-for="(hint,index) in planAdjustment.execution_hints" :key="hint"><small>{{ String(index+1).padStart(2,'0') }}</small><span>{{ hint }}</span></li></ul>
        <div v-if="planAdjustment.failed_rows?.length" class="failed"><strong>为何在这里转向</strong><span v-for="(row,index) in planAdjustment.failed_rows" :key="index">{{ display(row.label || row.code) }}：实际 {{ display(row.actual_value) }} / 目标 {{ display(row.target_raw) }}</span></div>
      </section>
    </div>
    <div v-else class="empty-coordinate">
      <div class="empty-orbit" aria-hidden="true"><i /><i /><span>{{ String(month).padStart(2, '0') }}</span></div>
      <div><strong>{{ month===0?'这是发展线起点':'本月暂无计划或复盘' }}</strong><p>空白不是失败，而是尚未被事实写入。完成月度复盘后，这里会出现原文、指标和调整结果。</p></div>
    </div>
    <footer><span>PATHFY / MONTHLY FIELD NOTE</span><span>PLAN → ACTION → REVIEW → ROUTE</span></footer>
  </section>
</template>
<style scoped>
.month-logbook{--log-tone:var(--pathfy-evidence);overflow:hidden;border:1px solid color-mix(in srgb,var(--log-tone) 25%,var(--pathfy-line));border-radius:1.4rem;background:linear-gradient(145deg,color-mix(in srgb,var(--log-tone) 6%,var(--pathfy-surface-panel)),var(--pathfy-surface-panel));box-shadow:0 28px 65px -52px rgb(12 45 56 / .8)}.month-logbook[data-state=review]{--log-tone:var(--pathfy-success)}.month-logbook[data-state=plan]{--log-tone:var(--pathfy-route)}.logbook-heading{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:1.25rem;align-items:center;border-bottom:1px solid var(--pathfy-line);padding:1.15rem clamp(1rem,2.6vw,1.8rem)}.logbook-index{display:grid;min-width:5.5rem;color:var(--log-tone)}.logbook-index span{font:800 .56rem/1 ui-monospace,monospace;letter-spacing:.1em}.logbook-index strong{margin-top:.15rem;font:800 3.8rem/.9 Georgia,serif;letter-spacing:-.08em}.logbook-heading>div:nth-child(2)>p{color:var(--log-tone);font:800 .6rem/1 ui-monospace,monospace;letter-spacing:.11em}.logbook-heading h3{margin-top:.3rem;font-size:clamp(1.4rem,2.4vw,2rem);font-weight:780;letter-spacing:-.035em}.logbook-heading>div:nth-child(2)>span{display:block;margin-top:.28rem;color:var(--ui-text-muted);font-size:.75rem}.logbook-status{display:grid;grid-template-columns:auto auto;gap:.08rem .45rem;align-items:center;min-width:7rem}.logbook-status i{grid-row:1/3;width:.65rem;height:.65rem;border-radius:50%;background:var(--log-tone);box-shadow:0 0 0 .3rem color-mix(in srgb,var(--log-tone) 12%,transparent),0 0 15px color-mix(in srgb,var(--log-tone) 45%,transparent)}.logbook-status span{font-size:.76rem;font-weight:800}.logbook-status small{color:var(--ui-text-muted);font:700 .55rem/1 ui-monospace,monospace}.detail-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(16rem,.85fr);gap:1rem;padding:clamp(1rem,2.6vw,1.8rem)}.detail-grid>section{position:relative;min-width:0}.review-sheet{background:#f7f4ea;color:#273b40;padding:1.45rem 1.35rem;box-shadow:0 14px 28px rgb(17 41 46 / .12);transform:rotate(-.25deg)}.review-sheet::before{position:absolute;inset:0;background-image:linear-gradient(rgb(40 70 74 / .065) 1px,transparent 1px);background-size:100% 1.75rem;content:"";pointer-events:none}.sheet-tape{position:absolute;left:50%;top:-.35rem;width:4.6rem;height:1rem;background:rgb(218 224 215 / .72);box-shadow:0 2px 4px rgb(0 0 0 / .08);transform:translateX(-50%) rotate(1deg)}.review-sheet>*:not(.sheet-tape){position:relative}.detail-grid header span{color:#087b77;font:800 .57rem/1 ui-monospace,monospace;letter-spacing:.11em}.detail-grid h4{margin-top:.35rem;font-size:1.05rem;font-weight:800}.pre{margin-top:1rem;border-left:3px solid #2dbbae;padding:.25rem 0 .25rem 1rem;white-space:pre-wrap;font:600 clamp(1rem,1.7vw,1.3rem)/1.65 Georgia,"Noto Serif SC",serif}.summary{display:grid;gap:.25rem;margin-top:1rem;color:rgb(39 59 64 / .68);font-size:.75rem;line-height:1.65}.summary strong{color:#273b40}.metric-list{display:grid;gap:.2rem;margin-top:1.1rem;border-top:2px solid rgb(39 59 64 / .18);padding-top:.6rem}.metric-list>span{color:rgb(39 59 64 / .5);font:800 .55rem/1 ui-monospace,monospace;letter-spacing:.1em}.metric-list>div{display:grid;grid-template-columns:auto 1fr;gap:.7rem;align-items:center;border-bottom:1px solid rgb(39 59 64 / .13);padding:.5rem 0}.metric-list small{color:#087b77;font:700 .56rem/1 ui-monospace,monospace}.metric-list strong{font-size:.72rem}.metric-list b{color:#087b77;font-size:.82rem}.plan-sheet{align-self:start;background:#e8f1f1;padding:1.4rem 1.25rem;box-shadow:0 12px 24px rgb(17 41 46 / .1);transform:rotate(.35deg)}.plan-pin{position:absolute;right:1rem;top:.85rem;width:.7rem;height:.7rem;border:2px solid rgb(115 140 143 / .55);border-radius:50%;box-shadow:inset 0 0 0 2px #e8f1f1}.plan-thesis{margin-top:1rem;font-size:1rem;font-weight:760;line-height:1.5}.plan-sheet ul{display:grid;gap:0;margin-top:.9rem}.plan-sheet li{display:grid;grid-template-columns:auto 1fr;gap:.6rem;border-top:1px solid rgb(39 59 64 / .12);padding:.55rem 0;color:rgb(39 59 64 / .72);font-size:.74rem}.plan-sheet li small{color:#087b77;font:700 .56rem/1.4 ui-monospace,monospace}.failed{display:grid;gap:.35rem;margin-top:1rem;border-left:3px solid #c98c43;background:rgb(255 249 232 / .58);padding:.65rem .75rem}.failed strong{color:#93601f;font-size:.68rem}.failed span{font-size:.68rem}.empty-coordinate{display:flex;align-items:center;justify-content:center;gap:1.5rem;min-height:14rem;padding:2rem}.empty-coordinate>div:last-child{max-width:30rem}.empty-coordinate strong{font-size:1.05rem}.empty-coordinate p{margin-top:.4rem;color:var(--ui-text-muted);font-size:.78rem;line-height:1.65}.empty-orbit{position:relative;display:grid;flex:0 0 7rem;width:7rem;height:7rem;place-items:center}.empty-orbit i{position:absolute;inset:0;border:1px solid color-mix(in srgb,var(--log-tone) 30%,transparent);border-radius:50%}.empty-orbit i:nth-child(2){inset:1rem}.empty-orbit span{color:var(--log-tone);font:800 2.4rem/1 Georgia,serif}.month-logbook>footer{display:flex;justify-content:space-between;gap:1rem;border-top:1px solid var(--pathfy-line);padding:.7rem clamp(1rem,2.6vw,1.8rem);color:var(--ui-text-muted);font:700 .53rem/1 ui-monospace,monospace;letter-spacing:.08em}@media(max-width:820px){.detail-grid{grid-template-columns:1fr}.logbook-heading{grid-template-columns:auto 1fr}.logbook-status{grid-column:2}}@media(max-width:520px){.logbook-heading{grid-template-columns:1fr}.logbook-index{display:none}.logbook-status{grid-column:1}.empty-coordinate{align-items:flex-start;flex-direction:column}.month-logbook>footer{flex-direction:column}}
.growth-receipt{display:grid;align-content:start;gap:1rem;border:1px solid rgb(30 130 121 / .18);background:linear-gradient(145deg,#f1fbf8,#e6f4f1);padding:1.4rem 1.25rem}.growth-score{display:grid;grid-template-columns:auto 1fr;gap:.08rem .8rem;align-items:end;border-bottom:1px solid rgb(25 91 86 / .14);padding-bottom:.9rem}.growth-score strong{grid-row:1/3;color:#0b8178;font:800 2.8rem/.9 Georgia,serif}.growth-score span{font-size:.78rem;font-weight:800}.growth-score small{color:rgb(39 59 64 / .6);font-size:.64rem}.growth-basis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.6rem}.growth-basis>div{display:grid;gap:.18rem;border-left:2px solid #2dbbae;background:rgb(255 255 255 / .56);padding:.7rem}.growth-basis span{color:rgb(39 59 64 / .62);font-size:.64rem}.growth-basis strong{font-size:1.05rem}.growth-basis small{color:rgb(39 59 64 / .55);font-size:.6rem}.growth-receipt>p{color:rgb(39 59 64 / .68);font-size:.7rem;line-height:1.65}.next-plan-sheet{align-self:start;background:#fff2c9;padding:1.4rem 1.25rem;box-shadow:0 14px 28px rgb(70 51 11 / .12);transform:rotate(.25deg)}.next-plan-sheet[data-pending=true]{border-top:4px solid #d89a27}.plan-state{display:flex;align-items:center;justify-content:space-between;gap:.8rem;margin-top:.75rem;border-bottom:1px solid rgb(83 61 18 / .16);padding-bottom:.7rem}.plan-state span{border-radius:999px;background:#145f64;color:#fff;padding:.3rem .55rem;font-size:.64rem;font-weight:800}.next-plan-sheet[data-pending=true] .plan-state span{background:#9a6814}.plan-state small{color:rgb(69 54 24 / .62);font-size:.63rem}.next-plan-items{display:grid;gap:.45rem;margin-top:.8rem}.next-plan-items article{display:grid;grid-template-columns:auto 1fr;gap:.65rem;align-items:start;background:rgb(255 255 255 / .46);padding:.65rem}.next-plan-items article>small{color:#a46d11;font:800 .58rem/1.5 ui-monospace,monospace}.next-plan-items article>div{display:grid;gap:.16rem}.next-plan-items strong{font-size:.78rem;line-height:1.45}.next-plan-items span{color:rgb(69 54 24 / .58);font-size:.62rem}.next-plan-sheet ul{display:grid;gap:.35rem;margin:.8rem 0}.next-plan-sheet li{display:flex;gap:.45rem;align-items:flex-start;color:rgb(69 54 24 / .72);font-size:.69rem;line-height:1.5}.next-plan-sheet li svg{flex:0 0 auto;margin-top:.12rem;color:#19877e}
</style>
