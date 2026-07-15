<script setup lang="ts">
const props = defineProps<{ reportId: number; plans: any[]; recommendations?: any }>()
const emit = defineEmits<{ changed: [] }>()
const api = useApi()
const toast = useToast()
const pending = reactive(new Set<string>())
const doneState = reactive<Record<string, boolean>>({})
const phaseOrder = ['early', 'mid', 'late']

function actionKey(jobId: string, itemIndex: number, actionIndex: number) {
  return `${jobId}-${itemIndex}-${actionIndex}`
}

watch(() => props.plans, plans => {
  for (const plan of plans || []) {
    for (const [itemIndex, item] of (plan.next_month_plan?.items || []).entries()) {
      for (const [actionIndex, action] of (item.custom_actions || []).entries()) {
        const key = actionKey(plan.job_id, itemIndex, actionIndex)
        if (!pending.has(key)) doneState[key] = Boolean(action.done)
      }
    }
  }
}, { immediate: true, deep: true })

function phases(plan: any) {
  return phaseOrder.map(key => ({ key, ...(plan.phases?.[key] || {}) })).filter(item => item.items?.length)
}

function recFor(plan: any) {
  if (plan.recommendations) return plan.recommendations
  return props.recommendations?.by_target?.find((item: any) => item.job_id === plan.job_id) || {}
}

function refLabel(item: any) { return item.label || item.resource_name || item.competition_name || item.id || '推荐内容' }
function refUrl(item: any) { return item.url || item.resource_url || item.official_url || '' }

async function toggle(jobId: string, itemIndex: number, actionIndex: number, action: any, checked: boolean) {
  const key = actionKey(jobId, itemIndex, actionIndex)
  if (pending.has(key)) return
  const previous = doneState[key] ?? Boolean(action.done)
  doneState[key] = checked
  pending.add(key)
  try {
    await api.ok(`/api/report/${props.reportId}/plan-actions/done`, { method: 'POST', body: { job_id: jobId, item_index: itemIndex, action_index: actionIndex, done: checked } })
    action.done = checked
    emit('changed')
  } catch (error) {
    doneState[key] = previous
    toast.add({ title: error instanceof Error ? error.message : '保存失败', color: 'error' })
  } finally { pending.delete(key) }
}
</script>

<template>
  <div class="grid gap-5">
    <UCard v-for="plan in plans || []" :key="plan.job_id">
      <template #header>
        <div class="flex flex-wrap items-start justify-between gap-3"><div><p class="text-xs text-primary">分岗成长计划</p><h3 class="mt-1 text-xl font-semibold">{{ plan.display_title || plan.job_title_name }}</h3><p v-if="plan.narrative?.path_advice" class="mt-2 max-w-4xl text-sm leading-6 muted">{{ plan.narrative.path_advice }}</p></div><UBadge v-if="plan.match_score != null" :label="`匹配 ${Math.round(plan.match_score)} 分`" /></div>
      </template>

      <div class="grid gap-5">
        <section v-if="plan.next_month_plan?.items?.length" class="rounded-xl border border-primary/30 bg-primary/5 p-4">
          <div class="mb-3 flex items-center justify-between"><div><h4 class="font-semibold">下月优先任务</h4><p class="text-xs muted">{{ plan.next_month_plan.phase_label }} · 第 {{ plan.next_month_plan.plan_month || 1 }} 月</p></div><UBadge label="当前执行" variant="soft" /></div>
          <div class="grid gap-3 md:grid-cols-2">
            <article v-for="(item, itemIndex) in plan.next_month_plan.items" :key="`${plan.job_id}-${itemIndex}`" class="rounded-lg bg-default p-3">
              <h5 class="font-medium">{{ item.focus_label || item.focus_dimension }}</h5><p class="mt-1 text-sm muted">{{ item.milestone }}</p>
              <div class="mt-3 grid gap-2"><UCheckbox v-for="(action, actionIndex) in item.custom_actions || []" :key="actionKey(plan.job_id, Number(itemIndex), Number(actionIndex))" :model-value="doneState[actionKey(plan.job_id, Number(itemIndex), Number(actionIndex))] ?? Boolean(action.done)" :label="action.text" :class="pending.has(actionKey(plan.job_id, Number(itemIndex), Number(actionIndex))) && 'pointer-events-none'" @update:model-value="toggle(plan.job_id, Number(itemIndex), Number(actionIndex), action, Boolean($event))" /></div>
            </article>
          </div>
        </section>

        <div class="phase-grid">
          <section v-for="phase in phases(plan)" :key="phase.key" class="rounded-xl border border-default p-4">
            <div class="mb-3"><p class="text-xs text-primary">{{ phase.period }}</p><h4 class="font-semibold">{{ phase.label }}</h4><p v-if="phase.line_one_liner || phase.summary" class="mt-1 text-sm muted">{{ phase.line_one_liner || phase.summary }}</p></div>
            <div class="grid gap-3"><article v-for="item in phase.items" :key="`${item.order}-${item.focus_dimension}`" class="border-t border-default pt-3 first:border-0 first:pt-0"><div class="flex items-start justify-between gap-2"><h5 class="text-sm font-medium">{{ item.focus_label || item.focus_dimension }}</h5><UBadge v-if="item.period" :label="item.period" color="neutral" size="sm" variant="soft" /></div><p class="mt-1 text-sm leading-6 muted">里程碑：{{ item.milestone }}</p><ul v-if="item.learning_path?.length || item.practice_plan?.length" class="mt-2 list-disc space-y-1 pl-5 text-sm"><li v-for="entry in [...(item.learning_path || []), ...(item.practice_plan || [])].slice(0, 5)" :key="entry">{{ entry }}</li></ul><div v-if="item.learning_path_refs?.length || item.practice_plan_refs?.length" class="mt-2 flex flex-wrap gap-1.5"><UButton v-for="ref in [...(item.learning_path_refs || []), ...(item.practice_plan_refs || [])]" :key="ref.id" :to="refUrl(ref) || undefined" :target="refUrl(ref) ? '_blank' : undefined" size="xs" color="neutral" variant="soft">{{ refLabel(ref) }}</UButton></div></article></div>
          </section>
        </div>

        <section v-if="recFor(plan).learning_resources?.length || recFor(plan).competitions?.length" class="grid gap-4 border-t border-default pt-4 md:grid-cols-2">
          <div><h4 class="mb-2 font-semibold">学习资源</h4><div class="grid gap-2"><a v-for="item in recFor(plan).learning_resources || []" :key="item.resource_id" :href="refUrl(item) || undefined" target="_blank" class="rounded-lg bg-elevated p-3 hover:text-primary"><p class="text-sm font-medium">{{ refLabel(item) }}</p><p class="mt-1 text-xs muted">{{ [item.resource_type, item.difficulty, item.skill_tag].filter(Boolean).join(' · ') }}</p></a><p v-if="!recFor(plan).learning_resources?.length" class="text-sm muted">暂无推荐资源</p></div></div>
          <div><h4 class="mb-2 font-semibold">竞赛实践</h4><div class="grid gap-2"><a v-for="item in recFor(plan).competitions || []" :key="item.competition_id" :href="refUrl(item) || undefined" target="_blank" class="rounded-lg bg-elevated p-3 hover:text-primary"><p class="text-sm font-medium">{{ refLabel(item) }}</p><p class="mt-1 text-xs muted">{{ [item.competition_type, item.difficulty, item.award_level].filter(Boolean).join(' · ') }}</p></a><p v-if="!recFor(plan).competitions?.length" class="text-sm muted">暂无竞赛推荐</p></div></div>
        </section>
      </div>
    </UCard>
  </div>
</template>

<style scoped>
.phase-grid { display: grid; gap: .75rem; }
@media (min-width: 1024px) { .phase-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
</style>
