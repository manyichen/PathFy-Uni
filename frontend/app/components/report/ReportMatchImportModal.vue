<script setup lang="ts">
import type { MatchHistoryItem } from '~/types/api'

const props = defineProps<{
  open: boolean
  items: MatchHistoryItem[]
  loading: boolean
  error?: string
  importLoading?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  import: [runId: number]
  retry: []
}>()

const modelOpen = computed({
  get: () => props.open,
  set: value => emit('update:open', value)
})
</script>

<template>
  <UModal v-model:open="modelOpen" title="从人岗匹配导入">
    <template #body>
      <div class="grid gap-2">
        <UAlert
          v-if="error"
          color="error"
          variant="soft"
          icon="i-lucide-triangle-alert"
          title="匹配记录加载失败"
          :description="error"
        ><template #actions><UButton size="xs" color="error" variant="soft" @click="emit('retry')">重试</UButton></template></UAlert>
        <template v-if="loading">
          <USkeleton v-for="index in 3" :key="index" class="h-16 rounded-lg" />
        </template>
        <template v-else>
          <button
            v-for="item in items"
            :key="item.run_id"
            type="button"
            class="modal-row"
            :disabled="importLoading"
            @click="emit('import', item.run_id)"
          >
            <div class="min-w-0">
              <p class="font-medium">{{ item.student_name || '能力画像' }} · {{ item.match_goal === 'stretch' ? '冲刺目标' : '稳妥目标' }}</p>
              <p class="truncate text-xs muted">{{ String(item.created_at || '').replace('T', ' ').slice(0, 19) }} · {{ item.q || '全部岗位' }}</p>
            </div>
            <UBadge :label="`${item.returned || 0} 个岗位`" color="neutral" variant="soft" />
          </button>
        </template>
        <UEmpty
          v-if="!loading && !error && !items.length"
          title="暂无匹配记录"
          description="请先在人岗匹配页面生成一次结果"
        />
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
  transition: border-color 160ms ease, background 160ms ease, opacity 160ms ease;
}

.modal-row:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--ui-primary) 45%, var(--ui-border));
  background: color-mix(in srgb, var(--ui-primary) 6%, transparent);
}

.modal-row:disabled {
  cursor: wait;
  opacity: 0.65;
}
</style>
