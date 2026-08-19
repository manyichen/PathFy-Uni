<script setup lang="ts">
import type { JobCard } from '~/types/job'
import type { MatchCandidate, MatchLlmResult, MatchPreferenceContext } from '~/types/match'

const props = defineProps<{ jobs: MatchCandidate[]; llm?: MatchLlmResult; refineRequested?: boolean; refining?: boolean; preferenceContext?: MatchPreferenceContext }>()
defineEmits<{ select: [job: JobCard]; detail: [job: JobCard]; retryRefine: [] }>()
const isLocalFallback = computed(() => props.llm?.fallback_mode === 'local')
const showAbilityOrder = ref(false)
const displayJobs = computed(() => showAbilityOrder.value
  ? [...props.jobs].sort((a, b) => Number(a.match_preview?.ability_rank || 999) - Number(b.match_preview?.ability_rank || 999))
  : props.jobs)
function preferenceFit(jobId: string) { return props.jobs.find(item => item.job.id === jobId)?.match_preview?.preference_fit }
</script>

<template>
  <div class="grid gap-6">
    <section v-if="llm || refineRequested" aria-labelledby="match-refine-heading">
      <div class="mb-3 flex items-end justify-between gap-3"><div><h2 id="match-refine-heading" class="text-lg font-semibold">智能推荐 Top 5</h2><p class="text-sm muted">结合能力画像与发展策略进行独立精排</p></div><UBadge v-if="llm?.model" :label="llm.model" variant="soft" /></div>
      <UCard v-if="refining" role="status"><div class="flex items-start gap-3"><UIcon name="i-lucide-loader-circle" class="mt-0.5 size-5 animate-spin text-primary" /><div><h3 class="font-medium">粗排已完成，AI 正在精排</h3><p class="mt-1 text-sm muted">先分析前 20 个候选；若服务响应超时，会自动缩小到前 10 个候选重试。完整能力排序仍可正常浏览。</p></div></div></UCard>
      <div v-else-if="llm?.ok && llm.top5.length" class="grid gap-3">
        <UAlert v-if="isLocalFallback" color="warning" variant="soft" icon="i-lucide-shield-check" title="已切换为本地增强排序" :description="llm.notice || '云端 AI 暂不可用，当前 Top 5 由本地八维算法生成。'"><template #actions><UButton size="sm" color="warning" variant="outline" @click="$emit('retryRefine')">重试云端 AI</UButton></template></UAlert>
        <UAlert v-else-if="llm.degraded" color="info" variant="soft" title="已通过轻量模式完成精排" :description="`首次请求波动后，候选池从 ${llm.initial_pool_size || 20} 个缩小到 ${llm.fallback_pool_size || llm.pool_size || 10} 个并成功生成推荐。`" />
        <MatchCandidateCard v-for="item in llm.top5" :key="item.job_id" :job="item.job" :rank="item.rank" :score="item.overall_fit_0_100" :reason="item.one_line" :strengths="item.strengths" :gaps="item.gaps" :risks="item.risks" :preference-fit="preferenceFit(item.job_id)" :ranking-label="isLocalFallback ? '本地增强排序' : '智能精排'" featured @select="$emit('select', $event)" @detail="$emit('detail', $event)" />
      </div>
      <UAlert v-else color="warning" variant="soft" title="智能精排暂不可用" :description="llm?.error || '仍可查看下方完整能力排序。'"><template #actions><UButton size="sm" color="warning" variant="outline" @click="$emit('retryRefine')">重试</UButton></template></UAlert>
    </section>
    <section>
      <div class="mb-3 flex items-end justify-between gap-3"><div><h2 class="text-lg font-semibold">完整匹配结果</h2><p class="text-sm muted">能力为主排序，共 {{ jobs.length }} 个岗位。</p></div><UButton v-if="preferenceContext?.tie_break?.applied" size="xs" color="neutral" variant="soft" icon="i-lucide-arrow-up-down" @click="() => { showAbilityOrder = !showAbilityOrder }">{{ showAbilityOrder ? '查看偏好二级排序' : '查看原能力排名' }}</UButton></div>
      <div class="grid gap-3"><MatchCandidateCard v-for="(item, index) in displayJobs" :key="item.id || item.job.id" :job="item.job" :rank="index + 1" :score="item.match_score" :reason="item.reason || item.explanation" :preference-fit="item.match_preview?.preference_fit" @select="$emit('select', $event)" @detail="$emit('detail', $event)" /></div>
    </section>
  </div>
</template>
