<script setup lang="ts">
import type { CareerReport, ReportPlan, ReportTarget } from '~/types/api'

const props = defineProps<{ reportId?: number; report: CareerReport; target?: ReportTarget; plan?: ReportPlan; goal: string }>()
const dimensionLabels: Record<string, string> = { cap_req_theory: '理论基础', cap_req_cross: '交叉学科', cap_req_practice: '实践技能', cap_req_digital: '数字素养', cap_req_innovation: '创新能力', cap_req_teamwork: '团队协作', cap_req_social: '社会网络', cap_req_growth: '成长潜力' }
const goalLabel = computed(() => props.goal === 'stretch' ? '冲刺发展' : '优先吻合')
const targetTitle = computed(() => props.target?.display_title || props.target?.title || props.plan?.display_title || props.plan?.job_title_name || '等待目标岗位')
const latestReview = computed(() => props.report.evaluation?.latest_review)
const currentStatus = computed(() => {
  const month = props.plan?.current_plan_month ?? props.plan?.next_month_plan?.plan_month ?? 1
  return latestReview.value ? `第 ${month} 月 · 已复盘` : `第 ${month} 月 · 执行中`
})
const largestGap = computed(() => {
  const gaps = props.target?.match_preview?.dimension_gaps || props.plan?.dimension_gaps || {}
  const entry = Object.entries(gaps).map(([key, value]) => [key, Number(value || 0)] as const).sort((a, b) => b[1] - a[1])[0]
  return entry && entry[1] > 0 ? `${dimensionLabels[entry[0]] || entry[0]} ${Math.round(entry[1])} 分` : '暂无明显差距'
})
const nextAction = computed(() => {
  const item = props.plan?.next_month_plan?.items?.[0]
  const action = item?.custom_actions?.find(candidate => !candidate.done)
  return action?.text || item?.milestone || item?.focus_label || '查看计划并确定本月行动'
})
const matchScore = computed(() => Math.round(Number(props.target?.match_preview?.match_score || props.plan?.match_score || 0)))
const planActions = computed(() => (props.plan?.next_month_plan?.items || []).flatMap(item => item.custom_actions || []))
const completion = computed(() => {
  const total = planActions.value.length
  return total ? Math.round(planActions.value.filter(action => action.done).length / total * 100) : 0
})
const evidenceCount = computed(() => props.report.decision_support?.target_decisions.find(item => item.job_id === props.plan?.job_id)?.claims.length || 0)
</script>

<template>
  <section class="report-lead" aria-label="报告首屏摘要">
    <div class="lead-main">
      <span class="sr-only">编号 {{ reportId || '-' }}，按月持续校准</span>
      <div class="lead-meta"><span>{{ currentStatus }}</span><span>报告 #{{ reportId || '-' }}</span><span>{{ goalLabel }}</span></div>
      <h2>{{ targetTitle }}</h2>
      <p class="lead-question">现在最值得完成什么？</p>
      <p class="lead-action">{{ nextAction }}</p>
      <p class="lead-note">完成后保留可查看的成果或反馈，复盘时只记录真实结果。</p>
    </div>
    <div class="lead-facts">
      <div><span>岗位匹配</span><strong>{{ matchScore }}</strong><small>/ 100</small></div>
      <div><span>本月完成</span><strong>{{ completion }}%</strong><small>{{ planActions.length }} 项行动</small></div>
      <div><span>主要短板</span><strong class="fact-text">{{ largestGap }}</strong><small>{{ evidenceCount }} 条结论依据</small></div>
    </div>
  </section>
</template>

<style scoped>
.report-lead{display:grid;overflow:hidden;border:1px solid var(--pathfy-line);border-radius:1rem;background:var(--pathfy-surface-panel)}.lead-main{position:relative;padding:1.45rem 1.5rem;background:linear-gradient(120deg,color-mix(in srgb,var(--pathfy-capability) 10%,transparent),transparent 65%)}.lead-main::after{content:"";position:absolute;right:-2rem;bottom:-4rem;width:12rem;height:12rem;border:1px solid color-mix(in srgb,var(--pathfy-capability) 12%,transparent);border-radius:50%}.lead-meta{display:flex;flex-wrap:wrap;gap:.45rem}.lead-meta span{border:1px solid color-mix(in srgb,var(--pathfy-capability) 20%,var(--ui-border));border-radius:999px;padding:.22rem .55rem;color:var(--pathfy-capability);font-size:.68rem;font-weight:650}.lead-main h2{margin-top:1rem;font-size:clamp(1.35rem,3vw,2rem);font-weight:760;line-height:1.2}.lead-question{margin-top:1.15rem;color:var(--ui-text-muted);font-size:.72rem}.lead-action{position:relative;z-index:1;margin-top:.25rem;max-width:42rem;font-size:1rem;font-weight:680;line-height:1.6}.lead-note{margin-top:.45rem;color:var(--ui-text-muted);font-size:.76rem}.lead-facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid var(--pathfy-line)}.lead-facts>div{min-width:0;padding:.9rem 1rem;border-left:1px solid var(--pathfy-line)}.lead-facts>div:first-child{border-left:0}.lead-facts span,.lead-facts small{display:block;color:var(--ui-text-muted);font-size:.68rem}.lead-facts strong{display:inline-block;margin-top:.18rem;font-size:1.35rem;font-weight:740}.lead-facts small{margin-top:.16rem}.lead-facts .fact-text{font-size:.92rem;line-height:1.4}@media(min-width:960px){.report-lead{grid-template-columns:minmax(0,1.65fr) minmax(25rem,1fr)}.lead-facts{grid-template-columns:1fr;border-top:0;border-left:1px solid var(--pathfy-line)}.lead-facts>div{display:grid;grid-template-columns:1fr auto;align-items:center;border-left:0;border-top:1px solid var(--pathfy-line)}.lead-facts>div:first-child{border-top:0}.lead-facts strong{grid-column:2;grid-row:1/3}.lead-facts small{grid-column:1}.lead-facts .fact-text{max-width:11rem;text-align:right}}@media(max-width:600px){.lead-facts{grid-template-columns:1fr}.lead-facts>div{border-left:0;border-top:1px solid var(--pathfy-line)}}
</style>
