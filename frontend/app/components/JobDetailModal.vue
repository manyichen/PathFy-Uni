<script setup lang="ts">
import type { JobDetail } from '~/types/job'
import { createLatestRequestController } from '~/utils/request-performance'
import { safeExternalUrl } from '~/utils/external-url'

const props = defineProps<{ jobId: string | null }>()
const emit = defineEmits<{ close: [] }>()
const jobs = useJobsApi()
const data = ref<JobDetail>()
const loading = ref(false)
const errorMessage = ref('')
const requests = createLatestRequestController()
const sourceUrl = computed(() => safeExternalUrl(data.value?.source_url))

function clean(value: unknown) {
  return String(value || '').replace(/<br\s*\/?>/gi, '\n').replace(/&nbsp;/gi, ' ').trim()
}

async function loadDetail(id: string, force = false) {
  const ticket = requests.start()
  loading.value = true
  data.value = undefined
  errorMessage.value = ''
  try {
    const result = await jobs.detail(id, { signal: ticket.signal, force })
    if (ticket.isCurrent()) data.value = result
  } catch (error) {
    if (ticket.isCurrent()) errorMessage.value = error instanceof Error ? error.message : '岗位详情加载失败'
  } finally {
    if (ticket.isCurrent()) loading.value = false
  }
}

function retry() {
  if (props.jobId) void loadDetail(props.jobId, true)
}

watch(() => props.jobId, async (id) => {
  if (!id) {
    requests.cancel()
    loading.value = false
    data.value = undefined
    errorMessage.value = ''
    return
  }
  await loadDetail(id)
}, { immediate: true })

onBeforeUnmount(requests.cancel)
</script>

<template>
  <USlideover :open="Boolean(jobId)" :title="data?.title || '岗位详情'" :ui="{ content: 'w-screen max-w-2xl' }" @update:open="v => !v && emit('close')">
    <template #body>
      <div v-if="loading" class="grid gap-5" aria-label="岗位详情加载中">
        <USkeleton class="h-8 w-3/4" />
        <USkeleton class="h-[360px]" />
        <USkeleton class="h-28" />
        <USkeleton class="h-28" />
      </div>
      <UAlert v-else-if="errorMessage" color="error" variant="soft" icon="i-lucide-triangle-alert" title="岗位详情暂时无法加载" :description="errorMessage">
        <template #actions><UButton color="error" variant="outline" size="sm" icon="i-lucide-refresh-cw" @click="retry">重新加载</UButton></template>
      </UAlert>
      <div v-else-if="data" class="grid gap-5 pb-8">
        <div class="flex flex-wrap gap-2 text-sm">
          <UBadge icon="i-lucide-building-2" :label="data.company || '未知公司'" color="neutral" variant="soft" />
          <UBadge icon="i-lucide-map-pin" :label="data.location || '未知地点'" color="neutral" variant="soft" />
          <UBadge icon="i-lucide-wallet-cards" :label="data.salary || '薪资面议'" variant="soft" />
          <UBadge v-if="data.experience_text" icon="i-lucide-briefcase" :label="data.experience_text" color="neutral" variant="soft" />
        </div>
        <UCard v-if="data.scores">
          <template #header><div class="flex items-center justify-between"><h3 class="font-semibold">八维能力需求</h3><span class="text-sm muted">均分 {{ data.score_avg || 0 }} · 置信度 {{ Number(data.conf_avg || 0).toFixed(1) }}%</span></div></template>
          <DeferredCapabilityRadar :scores="data.scores" height="280px" />
        </UCard>
        <JobWorkstyleCard :workstyle="data.workstyle" />
        <section v-if="data.company_detail"><h3 class="section-title">公司介绍</h3><p class="detail-copy">{{ clean(data.company_detail) }}</p></section>
        <section v-if="data.demand || data.description"><h3 class="section-title">岗位职责</h3><p class="detail-copy">{{ clean(data.demand || data.description) }}</p></section>
        <section v-if="data.internship_req"><h3 class="section-title">实习 / 任职要求</h3><p class="detail-copy">{{ clean(data.internship_req) }}</p></section>
        <section v-if="data.requirements?.length"><h3 class="section-title">关联能力要求</h3><div class="flex flex-wrap gap-2"><UBadge v-for="item in data.requirements.slice(0, 20)" :key="`${item.name}-${item.level}`" :label="`${item.name}${item.level ? ` · ${item.level}` : ''}`" color="neutral" variant="soft" /></div></section>
        <section v-if="data.cap_evidence?.length"><h3 class="section-title">能力证据片段</h3><ul class="list-disc space-y-2 pl-5 text-sm leading-6 muted"><li v-for="item in data.cap_evidence.slice(0, 8)" :key="item">{{ item }}</li></ul></section>
        <UButton v-if="sourceUrl" :to="sourceUrl" target="_blank" rel="noopener noreferrer" variant="soft" trailing-icon="i-lucide-external-link">查看原始岗位页面</UButton>
      </div>
    </template>
  </USlideover>
</template>

<style scoped>
.section-title { margin-bottom: .65rem; font-weight: 650; color: var(--ui-primary); }
.detail-copy { white-space: pre-wrap; line-height: 1.85; color: var(--ui-text-muted); }
</style>
