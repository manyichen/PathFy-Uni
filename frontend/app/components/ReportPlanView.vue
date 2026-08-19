<script setup lang="ts">
import type { ReportPlan, ReportPlanAction, ReportPlanPhase, ReportRecommendationRef, ReportRecommendations, ReportRecommendationSet } from '~/types/api'
import { useReportApi } from '~/composables/api/useReportApi'
import { safeExternalUrl } from '~/utils/external-url'
const props = withDefaults(defineProps<{ reportId: number; plans: ReportPlan[]; recommendations?: ReportRecommendations; showNextMonth?: boolean }>(), { showNextMonth: true })
const emit = defineEmits<{ changed: [] }>()
const reportApi = useReportApi()
const toast = useToast()
const saving = ref('')
const phaseOrder = ['early', 'short', 'mid', 'middle', 'late', 'long']

function phases(plan: ReportPlan): Array<ReportPlanPhase & { key: string }> {
  return phaseOrder.map(key => ({ key, ...(plan.phases?.[key] || {}) })).filter(item => item.items?.length)
}

function recFor(plan: ReportPlan): ReportRecommendationSet {
  if (plan.recommendations) return plan.recommendations
  return props.recommendations?.by_target?.find(item => item.job_id === plan.job_id) || {}
}

function refLabel(item: ReportRecommendationRef) { return item.label || item.resource_name || item.competition_name || item.id || '推荐内容' }
function refUrl(item: ReportRecommendationRef) { return safeExternalUrl(item.url || item.resource_url || item.official_url) }

async function toggle(jobId: string, itemIndex: number, actionIndex: number, action: ReportPlanAction) {
  const key = `${jobId}-${itemIndex}-${actionIndex}`
  saving.value = key
  const previous = Boolean(action.done)
  action.done = !previous
  try {
    await reportApi.setPlanActionDone(props.reportId, { job_id: jobId, item_index: itemIndex, action_index: actionIndex, done: action.done })
    emit('changed')
  } catch (error) {
    action.done = previous
    toast.add({ title: error instanceof Error ? error.message : '保存失败', color: 'error' })
  } finally { saving.value = '' }
}
</script>

<template>
  <div class="plan-atlas-stack">
    <section v-for="plan in plans || []" :key="plan.job_id" class="plan-atlas" aria-labelledby="plan-atlas-heading">
      <header class="atlas-heading">
        <div class="atlas-number" aria-hidden="true"><span>03</span><i /></div>
        <div class="atlas-title"><p>STAGE ATLAS / 阶段图谱</p><h3 id="plan-atlas-heading">{{ plan.display_title || plan.job_title_name }}</h3><span v-if="plan.narrative?.path_advice">{{ plan.narrative.path_advice }}</span><span v-else>把长期方向拆成可验证的阶段，不用一次看完所有未来。</span></div>
        <div class="atlas-seal"><small>ROUTE FIT</small><strong>{{ plan.match_score == null ? '—' : Math.round(plan.match_score) }}</strong><span>{{ phases(plan).length }} 个推进阶段</span></div>
      </header>

      <section v-if="showNextMonth && plan.next_month_plan?.items?.length" class="next-month-strip">
        <header><span>NOW / CURRENT LEG</span><div><h4>下月优先任务</h4><p>{{ plan.next_month_plan.phase_label }} · 第 {{ plan.next_month_plan.plan_month || 1 }} 月</p></div><b>正在执行</b></header>
        <div class="next-month-items">
          <article v-for="(item, itemIndex) in plan.next_month_plan.items" :key="`${plan.job_id}-${itemIndex}`">
            <span>{{ String(Number(itemIndex)+1).padStart(2,'0') }}</span><div><h5>{{ item.focus_label || item.focus_dimension }}</h5><p>{{ item.milestone }}</p><div class="action-checks"><UCheckbox v-for="(action, actionIndex) in item.custom_actions || []" :key="actionIndex" :model-value="Boolean(action.done)" :label="action.text" :disabled="saving === `${plan.job_id}-${itemIndex}-${actionIndex}`" @update:model-value="toggle(plan.job_id, Number(itemIndex), Number(actionIndex), action)" /></div></div>
          </article>
        </div>
      </section>

      <div v-if="phases(plan).length" class="phase-map">
        <div class="phase-axis" aria-hidden="true"><span>NOW</span><i /><span>NEXT</span><i /><span>THEN</span></div>
        <div class="phase-grid">
          <section v-for="(phase,phaseIndex) in phases(plan)" :key="phase.key" class="phase-leaf">
            <header><div class="phase-coordinate"><span>{{ String(Number(phaseIndex)+1).padStart(2,'0') }}</span><i /></div><div><p>{{ phase.period || `STAGE ${Number(phaseIndex)+1}` }}</p><h4>{{ phase.label }}</h4><span v-if="phase.line_one_liner || phase.summary">{{ phase.line_one_liner || phase.summary }}</span></div></header>
            <div class="phase-items">
              <article v-for="(item,itemIndex) in phase.items" :key="`${item.order}-${item.focus_dimension}`">
                <span class="item-index">{{ String(Number(itemIndex)+1).padStart(2,'0') }}</span>
                <div><div class="item-heading"><h5>{{ item.focus_label || item.focus_dimension }}</h5><small v-if="item.period">{{ item.period }}</small></div><p><strong>抵达标志</strong>{{ item.milestone }}</p><ul v-if="item.learning_path?.length || item.practice_plan?.length"><li v-for="entry in [...(item.learning_path || []), ...(item.practice_plan || [])].slice(0, 5)" :key="entry">{{ entry }}</li></ul><div v-if="item.learning_path_refs?.length || item.practice_plan_refs?.length" class="phase-refs"><UButton v-for="ref in [...(item.learning_path_refs || []), ...(item.practice_plan_refs || [])]" :key="ref.id" :to="refUrl(ref)" :target="refUrl(ref) ? '_blank' : undefined" rel="noopener noreferrer" size="xs" color="neutral" variant="soft">{{ refLabel(ref) }}</UButton></div></div>
              </article>
            </div>
          </section>
        </div>
      </div>
      <div v-else class="phase-await">
        <div class="await-route" aria-hidden="true"><i /><i /><i /><span>?</span></div>
        <div><span>STAGE SIGNAL / WAITING</span><strong>阶段坐标尚未写入</strong><p>当前只有方向建议，还没有足够明确的阶段里程碑。完成一次行动与复盘后，再把真实节奏整理成阶段路线。</p></div>
      </div>

      <section v-if="recFor(plan).learning_resources?.length || recFor(plan).competitions?.length" class="route-supplies">
        <header><span>ROUTE SUPPLIES</span><h4>沿途补给</h4><p>资源只在需要时出现，它们不是路线本身。</p></header>
        <div class="supply-columns">
          <div><h5>学习资源</h5><a v-for="(item,index) in recFor(plan).learning_resources || []" :key="item.resource_id" :href="refUrl(item)" :target="refUrl(item) ? '_blank' : undefined" rel="noopener noreferrer"><span>{{ String(Number(index)+1).padStart(2,'0') }}</span><div><strong>{{ refLabel(item) }}</strong><small>{{ [item.resource_type, item.difficulty, item.skill_tag].filter(Boolean).join(' · ') }}</small></div><b>↗</b></a><p v-if="!recFor(plan).learning_resources?.length">暂无推荐资源</p></div>
          <div><h5>竞赛实践</h5><a v-for="(item,index) in recFor(plan).competitions || []" :key="item.competition_id" :href="refUrl(item)" :target="refUrl(item) ? '_blank' : undefined" rel="noopener noreferrer"><span>{{ String(Number(index)+1).padStart(2,'0') }}</span><div><strong>{{ refLabel(item) }}</strong><small>{{ [item.competition_type, item.difficulty, item.award_level].filter(Boolean).join(' · ') }}</small></div><b>↗</b></a><p v-if="!recFor(plan).competitions?.length">暂无竞赛推荐</p></div>
        </div>
      </section>

      <footer class="atlas-footer"><span>PATHFY / DEVELOPMENT ATLAS</span><span>方向由计划提出，位置由复盘确认。</span></footer>
    </section>
  </div>
</template>

<style scoped>
.plan-atlas-stack{display:grid;gap:1.5rem}.plan-atlas{overflow:hidden;border:1px solid color-mix(in srgb,var(--pathfy-evidence) 22%,var(--pathfy-line));border-radius:1.5rem;background:linear-gradient(145deg,var(--pathfy-surface-panel),color-mix(in srgb,var(--pathfy-evidence) 4%,var(--pathfy-surface-panel)));box-shadow:0 30px 65px -52px rgb(15 42 54 / .76)}.atlas-heading{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:1.1rem;align-items:center;padding:clamp(1rem,2.6vw,1.8rem)}.atlas-number{display:grid;align-self:stretch;justify-items:center;grid-template-rows:auto 1fr;gap:.35rem;color:var(--pathfy-evidence)}.atlas-number span{font:850 .7rem/1 ui-monospace,monospace}.atlas-number i{width:1px;background:color-mix(in srgb,var(--pathfy-evidence) 45%,transparent)}.atlas-title>p{color:var(--pathfy-evidence);font:800 .63rem/1 ui-monospace,monospace;letter-spacing:.12em}.atlas-title h3{margin-top:.4rem;font-size:clamp(1.55rem,2.8vw,2.35rem);font-weight:790;letter-spacing:-.045em}.atlas-title>span{display:block;max-width:55rem;margin-top:.42rem;color:var(--ui-text-muted);font-size:.78rem;line-height:1.65}.atlas-seal{position:relative;display:grid;width:8.8rem;height:8.8rem;place-content:center;border:1px solid color-mix(in srgb,var(--pathfy-evidence) 28%,transparent);border-radius:50%;text-align:center}.atlas-seal::before,.atlas-seal::after{position:absolute;border:1px solid color-mix(in srgb,var(--pathfy-evidence) 18%,transparent);border-radius:50%;content:""}.atlas-seal::before{inset:.6rem}.atlas-seal::after{inset:1.25rem}.atlas-seal>*{position:relative;z-index:1}.atlas-seal small{color:var(--pathfy-evidence);font:800 .52rem/1 ui-monospace,monospace;letter-spacing:.1em}.atlas-seal strong{margin-top:.2rem;color:var(--pathfy-evidence);font:800 2.3rem/.9 Georgia,serif}.atlas-seal span{margin-top:.3rem;color:var(--ui-text-muted);font-size:.58rem}.next-month-strip{margin:0 clamp(1rem,2.6vw,1.8rem) 1rem;border-top:1px solid var(--pathfy-line);border-bottom:1px solid var(--pathfy-line);padding:1rem 0}.next-month-strip>header{display:grid;grid-template-columns:auto 1fr auto;gap:.8rem;align-items:center}.next-month-strip>header>span{color:var(--pathfy-evidence);font:800 .58rem/1 ui-monospace,monospace;letter-spacing:.1em}.next-month-strip h4{font-size:.9rem}.next-month-strip header p{color:var(--ui-text-muted);font-size:.65rem}.next-month-strip header b{color:var(--pathfy-success);font-size:.66rem}.next-month-items{display:grid;gap:.35rem;margin-top:.8rem}.next-month-items article{display:grid;grid-template-columns:auto 1fr;gap:.75rem;border-top:1px dashed var(--pathfy-line);padding:.65rem 0}.next-month-items article>span{color:var(--pathfy-evidence);font:800 .58rem/1.5 ui-monospace,monospace}.next-month-items h5{font-size:.78rem}.next-month-items p{margin-top:.2rem;color:var(--ui-text-muted);font-size:.7rem}.action-checks{display:grid;gap:.35rem;margin-top:.5rem}.phase-map{position:relative;border-top:1px solid var(--pathfy-line);border-bottom:1px solid var(--pathfy-line);background:linear-gradient(180deg,color-mix(in srgb,var(--pathfy-evidence) 4%,transparent),transparent);padding:clamp(1rem,2.8vw,2rem)}.phase-axis{display:grid;grid-template-columns:auto 1fr auto 1fr auto;gap:.5rem;align-items:center;margin-bottom:1.15rem;color:var(--ui-text-muted);font:800 .55rem/1 ui-monospace,monospace;letter-spacing:.1em}.phase-axis i{border-top:1px dashed color-mix(in srgb,var(--pathfy-evidence) 32%,var(--pathfy-line))}.phase-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.phase-leaf{position:relative;overflow:hidden;min-width:0;border:1px solid color-mix(in srgb,var(--pathfy-evidence) 18%,var(--pathfy-line));border-radius:48% 48% 1.1rem 1.1rem/2.5rem 2.5rem 1.1rem 1.1rem;background:color-mix(in srgb,var(--pathfy-evidence) 5%,var(--pathfy-surface-panel));padding:1.15rem 1rem 1rem}.phase-leaf:nth-child(2){margin-top:1.6rem}.phase-leaf::before{position:absolute;left:50%;top:0;width:1px;height:1.1rem;background:var(--pathfy-evidence);content:""}.phase-leaf>header{display:grid;grid-template-columns:auto 1fr;gap:.7rem;padding-bottom:.85rem}.phase-coordinate{display:grid;align-content:start;justify-items:center;color:var(--pathfy-evidence)}.phase-coordinate span{font:800 .62rem/1 ui-monospace,monospace}.phase-coordinate i{width:1px;height:2.4rem;margin-top:.35rem;background:color-mix(in srgb,var(--pathfy-evidence) 42%,transparent)}.phase-leaf>header p{color:var(--pathfy-evidence);font:800 .56rem/1 ui-monospace,monospace;letter-spacing:.08em}.phase-leaf>header h4{margin-top:.28rem;font-size:1rem}.phase-leaf>header div>span{display:block;margin-top:.28rem;color:var(--ui-text-muted);font-size:.65rem;line-height:1.5}.phase-items{display:grid}.phase-items article{display:grid;grid-template-columns:auto 1fr;gap:.6rem;border-top:1px solid var(--pathfy-line);padding:.8rem 0}.item-index{color:var(--pathfy-evidence);font:750 .54rem/1.45 ui-monospace,monospace}.item-heading{display:flex;align-items:start;justify-content:space-between;gap:.5rem}.item-heading h5{font-size:.75rem}.item-heading small{flex:0 0 auto;color:var(--ui-text-muted);font-size:.55rem}.phase-items article p{display:grid;gap:.13rem;margin-top:.4rem;color:var(--ui-text-muted);font-size:.67rem;line-height:1.5}.phase-items article p strong{color:var(--ui-text);font-size:.58rem}.phase-items ul{display:grid;gap:.3rem;margin-top:.55rem}.phase-items li{position:relative;padding-left:.7rem;color:var(--ui-text-muted);font-size:.64rem;line-height:1.45}.phase-items li::before{position:absolute;left:0;top:.5em;width:.26rem;height:.26rem;border-radius:50%;background:var(--pathfy-evidence);content:""}.phase-refs{display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.55rem}.phase-await{display:flex;align-items:center;justify-content:center;gap:1.4rem;min-height:11rem;border-top:1px solid var(--pathfy-line);border-bottom:1px solid var(--pathfy-line);background:linear-gradient(90deg,color-mix(in srgb,var(--pathfy-evidence) 5%,transparent),transparent);padding:1.5rem}.phase-await>div:last-child{max-width:34rem}.phase-await>div>span{color:var(--pathfy-evidence);font:800 .58rem/1 ui-monospace,monospace;letter-spacing:.11em}.phase-await strong{display:block;margin-top:.35rem;font-size:1.05rem}.phase-await p{margin-top:.35rem;color:var(--ui-text-muted);font-size:.7rem;line-height:1.6}.await-route{position:relative;display:grid;flex:0 0 6.5rem;width:6.5rem;height:6.5rem;place-items:center}.await-route i{position:absolute;inset:0;border:1px dashed color-mix(in srgb,var(--pathfy-evidence) 34%,transparent);border-radius:50%}.await-route i:nth-child(2){inset:.8rem}.await-route i:nth-child(3){inset:1.6rem}.await-route span{color:var(--pathfy-evidence);font:800 1.8rem/1 Georgia,serif}.route-supplies{display:grid;grid-template-columns:minmax(11rem,.3fr) minmax(0,1fr);gap:1.3rem;padding:clamp(1rem,2.6vw,1.8rem)}.route-supplies>header{border-right:1px solid var(--pathfy-line);padding-right:1rem}.route-supplies>header span{color:var(--pathfy-evidence);font:800 .58rem/1 ui-monospace,monospace;letter-spacing:.1em}.route-supplies>header h4{margin-top:.35rem;font-size:1.05rem}.route-supplies>header p{margin-top:.35rem;color:var(--ui-text-muted);font-size:.66rem;line-height:1.5}.supply-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}.supply-columns>div{min-width:0}.supply-columns h5{margin-bottom:.35rem;color:var(--ui-text-muted);font-size:.66rem}.supply-columns a{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:.55rem;align-items:center;border-top:1px solid var(--pathfy-line);padding:.6rem .1rem;transition:color 150ms ease,padding-left 150ms ease}.supply-columns a:hover{padding-left:.35rem;color:var(--pathfy-evidence)}.supply-columns a>span{color:var(--pathfy-evidence);font:700 .54rem/1 ui-monospace,monospace}.supply-columns a div{display:grid;min-width:0}.supply-columns a strong{overflow:hidden;font-size:.68rem;text-overflow:ellipsis;white-space:nowrap}.supply-columns a small{margin-top:.12rem;color:var(--ui-text-muted);font-size:.56rem}.supply-columns a>b{color:var(--pathfy-evidence)}.supply-columns>div>p{color:var(--ui-text-muted);font-size:.68rem}.atlas-footer{display:flex;justify-content:space-between;gap:1rem;border-top:1px solid var(--pathfy-line);padding:.7rem clamp(1rem,2.6vw,1.8rem);color:var(--ui-text-muted);font:700 .53rem/1 ui-monospace,monospace;letter-spacing:.07em}@media(max-width:920px){.phase-grid{grid-template-columns:1fr}.phase-leaf:nth-child(2){margin-top:0}.phase-leaf{border-radius:1.1rem}.route-supplies{grid-template-columns:1fr}.route-supplies>header{border-right:0;border-bottom:1px solid var(--pathfy-line);padding:0 0 .75rem}}@media(max-width:680px){.atlas-heading{grid-template-columns:1fr}.atlas-number{display:none}.atlas-seal{width:6.8rem;height:6.8rem}.supply-columns{grid-template-columns:1fr}.phase-await{align-items:flex-start;flex-direction:column}.atlas-footer{flex-direction:column}}
</style>
