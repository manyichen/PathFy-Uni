<script setup lang="ts">
import type { ReportHistoryItem } from '~/types/api'

defineProps<{
  open: boolean
  items: ReportHistoryItem[]
  loading?: boolean
  restoringId?: number
  error?: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  restore: [reportId: number]
  retry: []
}>()
</script>

<template>
  <UModal :open="open" title="历史报告" @update:open="emit('update:open', $event)">
    <template #body>
      <div class="grid gap-2">
        <UAlert v-if="error" color="error" variant="soft" title="历史报告加载失败" :description="error">
          <template #actions><UButton size="xs" color="error" variant="soft" @click="emit('retry')">重试</UButton></template>
        </UAlert>
        <template v-if="loading"><USkeleton v-for="index in 3" :key="index" class="h-16 rounded-lg" /></template>
        <button
          v-for="item in items"
          :key="item.report_id"
          type="button"
          class="modal-row"
          :disabled="Boolean(restoringId)"
          @click="emit('restore', item.report_id)"
        >
          <div class="min-w-0">
            <p class="font-medium">{{ item.title || `报告 #${item.report_id}` }}</p>
            <p class="truncate text-xs muted">{{ (item.target_titles || []).join('、') || String(item.created_at || '').replace('T', ' ').slice(0, 19) }}</p>
          </div>
          <UIcon :name="restoringId === item.report_id ? 'i-lucide-loader-circle' : 'i-lucide-chevron-right'" :class="{ 'animate-spin': restoringId === item.report_id }" />
        </button>
        <UEmpty v-if="!loading && !error && !items.length" title="暂无历史报告" />
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.modal-row {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid var(--ui-border);
  border-radius: 0.8rem;
  padding: 0.85rem;
  text-align: left;
  transition: border-color 160ms ease, background 160ms ease;
}

.modal-row:hover {
  border-color: color-mix(in srgb, var(--ui-primary) 45%, var(--ui-border));
  background: color-mix(in srgb, var(--ui-primary) 6%, transparent);
}
.modal-row:disabled { cursor: wait; opacity: .65; }
</style>
