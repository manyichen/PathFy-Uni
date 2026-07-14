<script setup lang="ts">
import { summaryLabels } from '~/types/graph'
const props = defineProps<{ summary?: Record<string, unknown> }>()
const rows = computed(() => Object.entries(props.summary || {}).filter(([key, value]) => key !== 'preview' && value !== null && typeof value !== 'object'))
function display(value: unknown) {
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value ?? '-')
}
</script>

<template>
  <div v-if="rows.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
    <div v-for="([key,value]) in rows" :key="key" class="rounded-lg border border-default bg-muted/30 p-3">
      <p class="text-xs text-muted">{{ summaryLabels[key] || key }}</p>
      <p class="mt-1 text-xl font-semibold">{{ display(value) }}</p>
    </div>
  </div>
  <UEmpty v-else title="尚未生成更新摘要" description="Worker 完成规划后会在这里显示可审阅统计。" />
</template>
