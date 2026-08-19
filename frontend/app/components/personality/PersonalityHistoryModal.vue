<script setup lang="ts">
import type { PersonalityResult } from '~/types/personality'

defineProps<{
  items: PersonalityResult[]
  loading?: boolean
  activatingId?: number
}>()

defineEmits<{ activate: [profileId: number] }>()
const open = defineModel<boolean>('open', { default: false })

function dateText(value?: string): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' })
}
</script>

<template>
  <UModal v-model:open="open" title="人格测评历史" description="切换只会改变当前展示结果；是否参与个性化推荐由你另行授权。">
    <template #body>
      <div v-if="loading" class="grid gap-3">
        <USkeleton v-for="index in 3" :key="index" class="h-20" />
      </div>
      <div v-else class="grid gap-3">
        <div v-for="item in items" :key="item.profile_id" class="flex items-center justify-between gap-4 rounded-xl border border-default p-4">
          <div>
            <div class="flex items-center gap-2">
              <strong class="text-lg">{{ item.mbti_type || '未分类' }}</strong>
              <UBadge v-if="item.is_active" label="当前" color="primary" variant="soft" />
              <UBadge v-if="item.status === 'legacy'" label="历史口径" color="neutral" variant="soft" />
            </div>
            <p class="mt-1 text-xs muted">#{{ item.profile_id }} · {{ dateText(item.completed_at || item.created_at) }}</p>
          </div>
          <UButton
            v-if="!item.is_active && item.profile_id"
            size="sm"
            color="neutral"
            variant="outline"
            :loading="activatingId === item.profile_id"
            :disabled="Boolean(activatingId)"
            @click="$emit('activate', item.profile_id)"
          >
            设为当前
          </UButton>
        </div>
        <UEmpty v-if="!items.length" title="暂无历史测评" />
      </div>
    </template>
  </UModal>
</template>
