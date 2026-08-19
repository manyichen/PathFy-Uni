<script setup lang="ts">
import type { MatchHistoryItem } from '~/types/match'

defineProps<{ items: MatchHistoryItem[]; loading: boolean }>()
defineEmits<{ restore: [item: MatchHistoryItem] }>()
const open = defineModel<boolean>('open', { required: true })

function dateLabel(value?: string) {
  if (!value) return '时间未知'
  return value.replace('T', ' ').slice(0, 16)
}
</script>

<template>
  <UModal v-model:open="open" title="匹配历史" description="恢复时会同步画像、过滤条件、策略和结果">
    <template #body>
      <div v-if="loading" class="grid gap-3"><USkeleton v-for="n in 3" :key="n" class="h-24" /></div>
      <div v-else-if="items.length" class="grid gap-3">
        <button v-for="item in items" :key="item.run_id" type="button" class="history-row" @click="$emit('restore', item)">
          <div class="flex items-start justify-between gap-3"><div class="text-left"><p class="font-medium">{{ item.student_name || '未命名画像' }}</p><p class="mt-1 text-xs muted">{{ dateLabel(item.created_at) }}</p></div><UBadge :label="item.match_goal === 'stretch' ? '冲刺发展' : '优先吻合'" variant="soft" /></div>
          <div class="mt-3 flex flex-wrap gap-2 text-xs muted"><span>关键词：{{ item.q || '不限' }}</span><span>地点：{{ item.location_q || '不限' }}</span><span>{{ item.refine_with_llm ? 'AI 精排' : '常规排序' }}</span><span>{{ item.preference_mode === 'explain' ? '含偏好解释快照' : '未使用工作偏好' }}</span><span>{{ item.returned || 0 }} 个结果</span></div>
        </button>
      </div>
      <UEmpty v-else title="暂无匹配历史" description="完成一次匹配后会自动保存快照" />
    </template>
  </UModal>
</template>

<style scoped>
.history-row { width: 100%; border: 1px solid var(--ui-border); border-radius: .75rem; padding: .9rem; background: var(--ui-bg); transition: border-color .18s ease; }
.history-row:hover { border-color: color-mix(in srgb, var(--ui-primary) 45%, transparent); }
</style>
