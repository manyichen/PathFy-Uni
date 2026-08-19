<script setup lang="ts">
import type { JobWorkstyleProfile } from '~/types/job'

defineProps<{ workstyle?: JobWorkstyleProfile }>()
const labels: Record<string, string> = {
  interaction_intensity: '互动强度', abstraction_preference: '任务抽象度',
  analytical_decision: '决策方式', structure_preference: '结构化程度'
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div><h3 class="font-semibold">岗位工作环境画像</h3><p class="mt-1 text-xs muted">来自岗位文本或经复核岗位族证据，不代表能力门槛。</p></div>
        <UBadge v-if="workstyle?.inherited_from_job_title" label="含岗位族继承数据" color="warning" variant="soft" />
      </div>
    </template>
    <div v-if="workstyle?.axes?.length" class="grid gap-4">
      <div v-for="axis in workstyle.axes" :key="axis.code" class="grid gap-1.5">
        <div class="flex items-center justify-between gap-2 text-sm"><span class="font-medium">{{ labels[axis.code] || axis.code }}</span><span class="muted">{{ axis.value.toFixed(0) }} · 证据置信度 {{ Math.round(axis.confidence * 100) }}%</span></div>
        <UProgress :model-value="axis.value" size="sm" />
        <div class="flex justify-between text-xs muted"><span>{{ axis.low_label }}</span><span>{{ axis.high_label }}</span></div>
        <p v-if="axis.evidence[0]" class="text-xs leading-5 muted">证据：{{ axis.evidence[0].text }}<span v-if="axis.inherited_from_job_title">（岗位族）</span></p>
      </div>
    </div>
    <UAlert v-else color="neutral" variant="soft" icon="i-lucide-circle-dashed" title="工作环境证据待补充" description="系统不会仅根据岗位名称推断高置信度工作方式。" />
  </UCard>
</template>
