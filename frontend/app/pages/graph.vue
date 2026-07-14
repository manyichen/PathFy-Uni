<script setup lang="ts">
definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '职业图谱' })

const jobsApi = useJobsApi()
const toast = useToast()
const from = ref('')
const to = ref('')
const fromJob = ref<any>()
const toJob = ref<any>()
const picker = ref<'from' | 'to' | null>(null)
const loading = ref(false)
const promotion = ref<any>()
const lateral = ref<any>()
const transition = ref<any>()

function chooseJob(job: any) {
  if (picker.value === 'from') { from.value = job.id; fromJob.value = job }
  else { to.value = job.id; toJob.value = job }
}

async function analyze() {
  if (!from.value) { toast.add({ title: '请先选择当前岗位', color: 'warning' }); return }
  loading.value = true
  transition.value = undefined
  try {
    [promotion.value, lateral.value] = await Promise.all([jobsApi.promotion(from.value), jobsApi.lateral(from.value)])
    if (to.value && to.value !== from.value) transition.value = await jobsApi.transition(from.value, to.value)
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '路径分析失败', color: 'error' })
  } finally { loading.value = false }
}

</script>

<template>
  <div class="page-stack">
    <div class="page-heading"><h1>职业关联图谱</h1><p class="muted">把晋升、换岗和目标差距放在同一页直接比较</p></div>
    <UCard><div class="grid gap-4 md:grid-cols-[1fr_1fr_auto]"><UFormField label="当前岗位"><button type="button" class="job-trigger" @click="picker = 'from'"><div v-if="fromJob" class="min-w-0 text-left"><p class="truncate font-medium">{{ fromJob.title }}</p><p class="truncate text-xs muted">{{ fromJob.company }} · {{ fromJob.location }}</p></div><span v-else class="muted">选择当前岗位</span><UIcon name="i-lucide-search" class="shrink-0" /></button></UFormField><UFormField label="目标岗位（可选）"><button type="button" class="job-trigger" @click="picker = 'to'"><div v-if="toJob" class="min-w-0 text-left"><p class="truncate font-medium">{{ toJob.title }}</p><p class="truncate text-xs muted">{{ toJob.company }} · {{ toJob.location }}</p></div><span v-else class="muted">选择目标岗位</span><UIcon name="i-lucide-search" class="shrink-0" /></button></UFormField><div class="flex items-end"><UButton :loading="loading" icon="i-lucide-route" @click="analyze">分析路径</UButton></div></div></UCard>
    <UEmpty v-if="!promotion && !lateral" title="请选择岗位开始分析" icon="i-lucide-network" />
    <template v-else>
      <UCard><template #header><div><h2 class="text-lg font-semibold">晋升路径</h2><p class="text-sm muted">按阶段查看目标岗位、里程碑和推荐资源</p></div></template><CareerPathView kind="promotion" :data="promotion" /></UCard>
      <UCard><template #header><div><h2 class="text-lg font-semibold">横向换岗</h2><p class="text-sm muted">按能力相似度展示可迁移方向和准备动作</p></div></template><CareerPathView kind="lateral" :data="lateral" /></UCard>
      <UCard v-if="transition"><template #header><h2 class="text-lg font-semibold">目标差距与行动建议</h2></template><CareerPathView kind="transition" :data="transition" /></UCard>
    </template>
    <JobPickerDialog :open="Boolean(picker)" :title="picker === 'from' ? '选择当前岗位' : '选择目标岗位'" :selected-ids="[from, to].filter(Boolean)" @update:open="value => { if (!value) picker = null }" @select="chooseJob" />
  </div>
</template>

<style scoped>
.job-trigger { display: flex; width: 100%; min-height: 3.5rem; align-items: center; justify-content: space-between; gap: .75rem; border: 1px solid var(--ui-border); border-radius: .5rem; padding: .6rem .75rem; background: var(--ui-bg); }
.job-trigger:hover { border-color: color-mix(in srgb, var(--ui-primary) 48%, transparent); }
</style>
