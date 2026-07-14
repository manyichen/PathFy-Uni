<script setup lang="ts">
const props = defineProps<{ kind: 'promotion' | 'lateral' | 'transition'; data: any }>()

const promotionRoutes = computed(() => props.data?.routes || props.data?.paths || [])
const lateralRoutes = computed(() => props.data?.routes || [])
const transition = computed(() => props.data || {})

function asList(value: unknown): any[] { return Array.isArray(value) ? value : [] }
function titleOf(node: any) { return node?.title || node?.job_title || node?.target_title || node?.label || '目标岗位' }
function resourceName(item: any) { return item?.resource_name || item?.competition_name || item?.label || item?.name || '推荐内容' }
function resourceUrl(item: any) { return item?.resource_url || item?.official_url || item?.url || '' }
</script>

<template>
  <div v-if="kind === 'promotion'" class="grid gap-4">
    <article v-for="(route, ri) in promotionRoutes" :key="route.id || ri" class="path-card">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div><p class="text-xs text-primary">晋升路线 {{ Number(ri) + 1 }}</p><h3 class="mt-1 font-semibold">{{ route.route_title || route.target_title || titleOf(route.nodes?.at(-1)) }}</h3><p v-if="route.rationale || route.route_text" class="mt-1 text-sm leading-6 muted">{{ route.rationale || route.route_text }}</p></div>
        <UBadge v-if="route.confidence != null" :label="`置信度 ${Math.round(Number(route.confidence) * (Number(route.confidence) <= 1 ? 100 : 1))}%`" variant="soft" />
      </div>
      <div v-if="route.stages?.length" class="mt-4 grid gap-2">
        <div v-for="stage in route.stages" :key="stage.stage" class="stage-row"><span class="stage-dot">{{ stage.stage }}</span><div><p class="font-medium">{{ stage.label }} · {{ stage.role }}</p><p class="text-sm muted">{{ stage.period }} · {{ stage.milestone }}</p><ul v-if="stage.actions?.length" class="mt-2 list-disc space-y-1 pl-5 text-sm"><li v-for="action in stage.actions" :key="action">{{ action }}</li></ul></div></div>
      </div>
      <div v-else-if="route.nodes?.length" class="mt-4 flex flex-wrap items-center gap-2"><template v-for="(node, i) in route.nodes" :key="node.id || i"><UBadge :label="titleOf(node)" color="neutral" variant="soft" /><UIcon v-if="Number(i) < route.nodes.length - 1" name="i-lucide-arrow-right" class="muted" /></template></div>
      <div v-if="asList(route.learning_resources).length || asList(route.competitions).length" class="mt-4 flex flex-wrap gap-2"><UButton v-for="item in [...asList(route.learning_resources), ...asList(route.competitions)].slice(0, 6)" :key="resourceName(item)" :to="resourceUrl(item) || undefined" :target="resourceUrl(item) ? '_blank' : undefined" size="xs" color="neutral" variant="soft">{{ resourceName(item) }}</UButton></div>
    </article>
    <UEmpty v-if="!promotionRoutes.length" title="暂无晋升路径" description="图谱中还没有该岗位的晋升关系" icon="i-lucide-trending-up" />
  </div>

  <div v-else-if="kind === 'lateral'" class="grid gap-3">
    <article v-for="(route, i) in lateralRoutes" :key="route.id || i" class="path-card">
      <div class="flex items-start justify-between gap-3"><div><p class="text-xs muted">从 {{ route.from_title || data?.job_title || '当前岗位' }} 转向</p><h3 class="mt-1 text-lg font-semibold">{{ route.target_title }}</h3></div><div class="text-right"><strong class="text-xl text-primary">{{ Math.round(Number(route.score || route.cap_similarity || 0) * (Number(route.score || route.cap_similarity || 0) <= 1 ? 100 : 1)) }}</strong><p class="text-xs muted">相似度</p></div></div>
      <p v-if="route.rationale" class="mt-3 text-sm leading-6 muted">{{ route.rationale }}</p>
      <div v-if="route.candidate_jobs?.length" class="mt-3 flex flex-wrap gap-2"><UBadge v-for="job in route.candidate_jobs.slice(0, 4)" :key="job.id" :label="`${job.title}${job.company ? ` · ${job.company}` : ''}`" color="neutral" variant="soft" /></div>
      <div v-if="route.action_plan?.phases?.length" class="mt-4 grid gap-2 sm:grid-cols-3"><div v-for="phase in route.action_plan.phases" :key="phase.stage" class="rounded-lg bg-elevated p-3"><p class="text-xs text-primary">{{ phase.label }} · {{ phase.period }}</p><p class="mt-1 text-sm font-medium">{{ phase.milestone }}</p></div></div>
    </article>
    <UEmpty v-if="!lateralRoutes.length" title="暂无横向换岗" description="图谱中还没有相近岗位关系" icon="i-lucide-git-branch" />
  </div>

  <div v-else class="grid gap-4">
    <div class="flex flex-wrap items-center justify-center gap-3 rounded-xl bg-elevated p-4"><strong>{{ titleOf(transition.from_job) }}</strong><UIcon name="i-lucide-arrow-right" class="text-primary" /><strong>{{ titleOf(transition.to_job) }}</strong><UBadge v-if="transition.advice?.feasibility" :label="`可行性 ${transition.advice.feasibility}`" /></div>
    <p v-if="transition.advice?.summary" class="leading-7">{{ transition.advice.summary }}</p>
    <div class="grid gap-3 md:grid-cols-2">
      <section class="rounded-xl border border-default p-4"><h3 class="font-semibold text-success">可迁移优势</h3><ul class="mt-3 list-disc space-y-2 pl-5 text-sm"><li v-for="item in transition.advice?.advantages || transition.analysis?.transferable_skills || []" :key="item">{{ item }}</li></ul></section>
      <section class="rounded-xl border border-default p-4"><h3 class="font-semibold text-warning">关键差距</h3><ul class="mt-3 list-disc space-y-2 pl-5 text-sm"><li v-for="item in transition.advice?.gaps || transition.analysis?.skill_missing || []" :key="item">{{ item }}</li></ul></section>
    </div>
    <section v-if="transition.advice?.learning_plan?.length" class="rounded-xl border border-default p-4"><h3 class="font-semibold">行动建议</h3><ol class="mt-3 grid gap-2"><li v-for="(item, i) in transition.advice.learning_plan" :key="item" class="flex gap-3 text-sm"><span class="grid size-6 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary">{{ Number(i) + 1 }}</span><span class="leading-6">{{ item }}</span></li></ol></section>
    <p v-if="transition.advice?.final_recommendation" class="rounded-xl bg-primary/10 p-4 text-sm leading-6"><strong>综合建议：</strong>{{ transition.advice.final_recommendation }}</p>
  </div>
</template>

<style scoped>
.path-card { border: 1px solid var(--ui-border); border-radius: .85rem; padding: 1rem; }
.stage-row { display: grid; grid-template-columns: 1.75rem 1fr; gap: .75rem; align-items: start; }
.stage-dot { display: grid; width: 1.75rem; height: 1.75rem; place-items: center; border-radius: 999px; background: color-mix(in srgb, var(--ui-primary) 14%, transparent); color: var(--ui-primary); font-size: .75rem; font-weight: 700; }
</style>
