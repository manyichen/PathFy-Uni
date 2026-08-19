<script setup lang="ts">
import type { MatchGoal, MatchPreferenceContext, PreferenceMode } from '~/types/match'
import type { PersonalityResult } from '~/types/personality'
import type { ResumeOption } from '~/types/profile'

const props = defineProps<{ resumes: ResumeOption[]; loading: boolean; personality?: PersonalityResult; preferenceContext?: MatchPreferenceContext }>()
defineEmits<{ run: []; history: [] }>()
const resumeId = defineModel<number | undefined>('resumeId')
const q = defineModel<string>('q', { required: true })
const locationQ = defineModel<string>('locationQ', { required: true })
const goal = defineModel<MatchGoal>('goal', { required: true })
const refine = defineModel<boolean>('refine', { required: true })
const preferenceMode = defineModel<PreferenceMode>('preferenceMode', { required: true })
const canExplain = computed(() => props.personality?.status === 'measured' && props.personality.personalization_enabled)
const preferenceItems = computed(() => [
  { label: '不使用', value: 'off' },
  { label: '仅解释（不改变排序）', value: 'explain', disabled: !canExplain.value },
  { label: '同分岗位偏好优先（实验）', value: 'tie_break', disabled: !canExplain.value }
])
</script>

<template>
  <UCard class="cockpit-workbench">
    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-[1.2fr_1fr_1fr_1fr_auto]">
      <UFormField label="能力画像"><USelect v-model="resumeId" value-key="id" label-key="name" :items="resumes" placeholder="选择已保存画像" class="w-full" /></UFormField>
      <UFormField label="岗位关键词"><UInput v-model="q" placeholder="如：数据分析" /></UFormField>
      <UFormField label="工作地点"><UInput v-model="locationQ" placeholder="如：上海" /></UFormField>
      <UFormField label="匹配策略"><USelect v-model="goal" :items="[{label:'优先吻合',value:'fit'},{label:'挑战发展',value:'stretch'}]" /></UFormField>
      <div class="flex min-w-36 flex-col justify-end gap-2"><USwitch v-model="refine" label="AI 智能精排" /><UButton :loading="loading" icon="i-lucide-sparkles" block @click="$emit('run')">开始匹配</UButton></div>
    </div>
    <div class="mt-4 flex items-center justify-between gap-3 border-t border-default pt-3">
      <div class="grid gap-1">
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs font-medium">工作偏好</span>
          <USelect v-model="preferenceMode" :items="preferenceItems" size="sm" class="w-56" />
          <UBadge v-if="canExplain" :label="`${personality?.mbti_type || ''} · ${personality?.completed_at?.slice(0, 10) || '当前画像'}`" variant="soft" />
          <UButton v-else to="/personality" size="xs" color="neutral" variant="ghost">{{ personality?.status === 'legacy' ? '重新测评' : personality ? '开启个性化' : '补充工作偏好' }}</UButton>
        </div>
        <p class="hidden text-xs muted md:block"><UIcon name="i-lucide-info" class="mr-1 inline size-3.5" />粗排只看八维能力；偏好只会在能力分相近且证据覆盖达标时做二级排序，原能力名次始终可查看。</p>
      </div>
      <UButton variant="ghost" color="neutral" icon="i-lucide-history" @click="$emit('history')">查看匹配历史</UButton>
    </div>
  </UCard>
</template>
