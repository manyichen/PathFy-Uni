<script setup lang="ts">
import type { JobCard } from '~/types/job'
import type { MatchPreferenceFit } from '~/types/match'

defineProps<{
  job: JobCard
  rank: number
  score: number
  reason?: string
  strengths?: string[]
  gaps?: string[]
  risks?: string[]
  featured?: boolean
  rankingLabel?: string
  preferenceFit?: MatchPreferenceFit
}>()
const emit = defineEmits<{ select: [job: JobCard]; detail: [job: JobCard] }>()
</script>

<template>
  <UCard :class="['candidate-card', featured && 'featured']">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="text-xs font-medium text-primary">第 {{ rank }} 名 · {{ rankingLabel || (featured ? '智能精排' : '八维粗排') }}</p>
        <h3 class="truncate text-lg font-semibold">{{ job.title }}</h3>
        <p class="truncate text-sm muted">{{ job.company || '未知公司' }} · {{ job.location || '地点不限' }}</p>
      </div>
      <div class="shrink-0 text-right"><p class="text-2xl font-bold text-primary">{{ Math.round(score) }}</p><p class="text-[11px] muted">匹配度</p></div>
    </div>
    <p v-if="reason" class="mt-3 text-sm leading-6"><span class="font-medium">排名依据：</span>{{ reason }}</p>
    <div v-if="preferenceFit && preferenceFit.status !== 'not_enabled'" class="mt-3 rounded-lg bg-elevated px-3 py-2 text-xs muted">
      <span class="font-medium text-default">偏好解释：</span>
      <span v-if="preferenceFit.status === 'insufficient_job_evidence'">岗位工作环境证据待补充，暂不输出适配分；未影响排名。</span>
      <span v-else-if="preferenceFit.status === 'legacy_user_profile'">当前为历史类型摘要，需重新测评后生成连续解释。</span>
      <span v-else-if="preferenceFit.status === 'personalization_disabled'">个性化已关闭，本岗位未使用偏好数据。</span>
      <span v-else-if="preferenceFit.status === 'missing_user_profile'">尚无可用工作偏好画像。</span>
      <template v-else>
        <span class="font-medium text-primary">适配 {{ preferenceFit.score?.toFixed(0) }} · {{ preferenceFit.confidence_level === 'high' ? '证据较充分' : '中等证据' }}</span>
        <p class="mt-1">{{ preferenceFit.axes?.[0]?.explanation }} {{ preferenceFit.influenced_ranking ? '该岗位在能力同分带内参与了偏好二级排序。' : '未影响排名。' }}</p>
        <details v-if="preferenceFit.axes?.length" class="mt-2"><summary class="cursor-pointer font-medium text-default">查看逐轴证据</summary><ul class="mt-2 grid gap-2"><li v-for="axis in preferenceFit.axes" :key="axis.code"><span class="font-medium">{{ axis.fit.toFixed(0) }} 分：</span>{{ axis.explanation }}<span v-if="axis.evidence[0]"> 证据：{{ axis.evidence[0].text }}</span></li></ul></details>
      </template>
    </div>
    <div v-if="strengths?.length || gaps?.length || risks?.length" class="mt-3 grid gap-2 text-sm sm:grid-cols-3">
      <div v-if="strengths?.length"><p class="font-medium text-success">优势</p><ul class="mt-1 list-disc pl-4 muted"><li v-for="item in strengths.slice(0, 3)" :key="item">{{ item }}</li></ul></div>
      <div v-if="gaps?.length"><p class="font-medium text-warning">缺口</p><ul class="mt-1 list-disc pl-4 muted"><li v-for="item in gaps.slice(0, 3)" :key="item">{{ item }}</li></ul></div>
      <div v-if="risks?.length"><p class="font-medium text-error">风险</p><ul class="mt-1 list-disc pl-4 muted"><li v-for="item in risks.slice(0, 3)" :key="item">{{ item }}</li></ul></div>
    </div>
    <div class="mt-3 flex items-center justify-between border-t border-default pt-3">
      <span class="font-medium text-primary">{{ job.salary || '薪资面议' }}</span>
      <div class="flex gap-1"><UButton size="sm" variant="ghost" @click="emit('select', job)">选择比较</UButton><UButton size="sm" variant="ghost" trailing-icon="i-lucide-arrow-up-right" @click="emit('detail', job)">岗位详情</UButton></div>
    </div>
  </UCard>
</template>

<style scoped>
.candidate-card { transition: border-color .18s ease, transform .18s ease; }
.candidate-card:hover { border-color: color-mix(in srgb, var(--ui-primary) 40%, transparent); transform: translateY(-1px); }
.candidate-card.featured { border-color: color-mix(in srgb, var(--ui-primary) 32%, var(--ui-border)); background: color-mix(in srgb, var(--ui-primary) 4%, var(--ui-bg)); }
</style>
