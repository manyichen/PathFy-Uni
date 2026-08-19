<script setup lang="ts">
import type { PersonalityPreferenceAxis, PersonalityResult } from '~/types/personality'
import { usePersonalityApi } from '~/composables/api/usePersonalityApi'

const api = usePersonalityApi()
const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const result = ref<PersonalityResult>()

const axisLabels: Record<string, string> = {
  interaction_intensity: '互动恢复',
  abstraction_preference: '抽象探索',
  analytical_decision: '分析判断',
  structure_preference: '计划结构'
}

function axisTitle(axis: PersonalityPreferenceAxis) {
  return axisLabels[axis.code] || axis.code
}

function dateText(value?: string) {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('zh-CN')
}

async function togglePersonalization(enabled: boolean) {
  if (!result.value?.profile_id || saving.value) return
  saving.value = true
  try {
    result.value = await api.setPersonalization(result.value.profile_id, enabled)
    toast.add({ title: enabled ? '已允许用于匹配解释' : '已停用偏好个性化', color: 'success' })
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '设置保存失败', color: 'error' })
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    result.value = await api.latest()
  } catch {
    result.value = undefined
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <UCard class="mt-5">
    <template #header>
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p class="text-xs font-semibold uppercase tracking-[.16em] text-primary">Preference Portrait</p>
          <h2 class="mt-1 text-lg font-semibold">工作偏好画像</h2>
          <p class="mt-1 text-sm muted">与能力画像并列描述你更自然的工作方式，不修改任何能力分数。</p>
        </div>
        <UBadge v-if="result?.status === 'measured'" :label="`${result.mbti_type || ''} · 连续测量`" variant="soft" />
        <UBadge v-else-if="result?.status === 'legacy'" label="历史类型摘要" color="neutral" variant="soft" />
      </div>
    </template>

    <div v-if="loading" class="grid gap-3 md:grid-cols-2"><USkeleton v-for="index in 4" :key="index" class="h-16" /></div>
    <div v-else-if="!result" class="flex flex-wrap items-center justify-between gap-4">
      <div><h3 class="font-medium">尚未建立工作偏好画像</h3><p class="mt-1 text-sm muted">这是可选增强；不做测评也能继续岗位匹配和生涯规划。</p></div>
      <UButton to="/personality" icon="i-lucide-brain-circuit">开始偏好测评</UButton>
    </div>
    <div v-else-if="result.status === 'legacy'" class="flex flex-wrap items-center justify-between gap-4">
      <div><h3 class="font-medium">{{ result.mbti_type }} 历史类型摘要</h3><p class="mt-1 text-sm muted">旧结果缺少连续四维数据，只用于回顾，不生成环境适配解释。</p></div>
      <UButton to="/personality" color="neutral" variant="outline">重新测评</UButton>
    </div>
    <div v-else>
      <div class="grid gap-4 md:grid-cols-2">
        <div v-for="axis in result.preference_axes || []" :key="axis.code" class="rounded-xl border border-default p-3">
          <div class="mb-2 flex items-center justify-between gap-3 text-sm"><span class="font-medium">{{ axisTitle(axis) }}</span><strong>{{ Math.round(axis.value) }}</strong></div>
          <UProgress :model-value="axis.value" :max="100" />
          <div class="mt-1 flex justify-between text-[11px] muted"><span>{{ axis.low_label }}</span><span>{{ axis.high_label }}</span></div>
        </div>
      </div>
      <div class="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-default pt-4">
        <div><p class="text-sm font-medium">用于匹配解释和后续行动个性化</p><p class="mt-1 text-xs muted">测评于 {{ dateText(result.completed_at) }} · 当前阶段不影响岗位排序</p></div>
        <div class="flex items-center gap-3">
          <USwitch :model-value="Boolean(result.personalization_enabled)" :loading="saving" label="允许个性化" @update:model-value="togglePersonalization(Boolean($event))" />
          <UButton to="/personality" color="neutral" variant="outline" size="sm">查看结果</UButton>
        </div>
      </div>
    </div>
  </UCard>
</template>
