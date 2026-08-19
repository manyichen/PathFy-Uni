<script setup lang="ts">
import CareerGraphExplorer from '~/components/visualization/career/CareerGraphExplorer.vue'
import type { CareerLateralResponse, CareerPromotionResponse, CareerTransitionResponse } from '~/types/career-graph'
import type { JobCard } from '~/types/job'
import { isAbortError } from '~/composables/useApi'
import { createLatestRequestController } from '~/utils/request-performance'
import { buildCareerGraphData } from '~/utils/visualization/career-graph-adapter'

definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '职业图谱' })

const jobsApi = useJobsApi()
const toast = useToast()
const from = ref('')
const to = ref('')
const fromJob = ref<JobCard>()
const toJob = ref<JobCard>()
const picker = ref<'from' | 'to' | null>(null)
const loading = ref(false)
const promotion = ref<CareerPromotionResponse>()
const lateral = ref<CareerLateralResponse>()
const transition = ref<CareerTransitionResponse>()
const attempted = ref(false)
const analysisIssues = ref<string[]>([])
const analysisRequests = createLatestRequestController()
const CAREER_GRAPH_TIMEOUT_MS = 18_000

const hasAnalysis = computed(() => Boolean(promotion.value || lateral.value || transition.value))

const careerGraph = computed(() => buildCareerGraphData({
  currentJob: fromJob.value,
  targetJob: toJob.value,
  promotion: promotion.value,
  lateral: lateral.value,
  transition: transition.value
}))

function chooseJob(job: JobCard) {
  if (picker.value === 'from') {
    const changed = from.value !== job.id
    from.value = job.id
    fromJob.value = job
    if (changed) {
      analysisRequests.cancel()
      loading.value = false
      promotion.value = undefined
      lateral.value = undefined
      transition.value = undefined
      attempted.value = false
      analysisIssues.value = []
    }
    return
  }

  const changed = to.value !== job.id
  to.value = job.id
  toJob.value = job
  if (changed) {
    analysisRequests.cancel()
    loading.value = false
    transition.value = undefined
    attempted.value = false
    analysisIssues.value = []
  }
}

function issueMessage(label: string, error: unknown) {
  if (isAbortError(error)) return `${label}请求超时，请稍后重试`
  const detail = error instanceof Error ? error.message : '服务暂时不可用'
  return `${label}：${detail}`
}

async function analyze() {
  if (!from.value) {
    toast.add({ title: '请先选择当前岗位', color: 'warning' })
    return
  }

  const ticket = analysisRequests.start()
  loading.value = true
  attempted.value = true
  analysisIssues.value = []
  promotion.value = undefined
  lateral.value = undefined
  transition.value = undefined

  const requestOptions = { signal: ticket.signal, timeout: CAREER_GRAPH_TIMEOUT_MS }
  const tasks: Array<{ label: string; run: () => Promise<void> }> = [
    {
      label: '晋升路径',
      run: async () => {
        const result = await jobsApi.promotion(from.value, requestOptions)
        if (ticket.isCurrent()) promotion.value = result
      }
    },
    {
      label: '横向迁移',
      run: async () => {
        const result = await jobsApi.lateral(from.value, requestOptions)
        if (ticket.isCurrent()) lateral.value = result
      }
    }
  ]

  if (to.value && to.value !== from.value) {
    tasks.push({
      label: '目标差距',
      run: async () => {
        const result = await jobsApi.transition(from.value, to.value, requestOptions)
        if (ticket.isCurrent()) transition.value = result
      }
    })
  }

  try {
    const settled = await Promise.allSettled(tasks.map(task => task.run()))
    if (!ticket.isCurrent()) return

    analysisIssues.value = settled.flatMap((result, index) => (
      result.status === 'rejected' ? [issueMessage(tasks[index]!.label, result.reason)] : []
    ))

    if (!hasAnalysis.value) {
      toast.add({ title: '路径分析未完成', description: analysisIssues.value.join('；'), color: 'error' })
    } else if (analysisIssues.value.length) {
      toast.add({ title: '已展示可用的分析结果', description: '部分数据源暂时不可用，可稍后重试', color: 'warning' })
    }
  } finally {
    if (ticket.isCurrent()) loading.value = false
  }
}

onBeforeUnmount(() => analysisRequests.cancel())
</script>

<template>
  <div class="cockpit-page">
    <CockpitPageHeader eyebrow="Career Graph / Pathways" title="职业关联图谱" description="把晋升、横向迁移与目标差距放进同一张路径地图，从当前位置看清下一站及其能力门槛。" icon="i-lucide-network" mark="04" edition-label="路径图谱" />

    <UCard>
      <div class="grid gap-4 md:grid-cols-[1fr_1fr_auto]">
        <UFormField label="当前岗位">
          <button type="button" class="job-trigger" @click="picker = 'from'">
            <div v-if="fromJob" class="min-w-0 text-left">
              <p class="truncate font-medium">{{ fromJob.title }}</p>
              <p class="truncate text-xs muted">{{ fromJob.company }} · {{ fromJob.location }}</p>
            </div>
            <span v-else class="muted">选择当前岗位</span>
            <UIcon name="i-lucide-search" class="shrink-0" />
          </button>
        </UFormField>
        <UFormField label="目标岗位（可选）">
          <button type="button" class="job-trigger" @click="picker = 'to'">
            <div v-if="toJob" class="min-w-0 text-left">
              <p class="truncate font-medium">{{ toJob.title }}</p>
              <p class="truncate text-xs muted">{{ toJob.company }} · {{ toJob.location }}</p>
            </div>
            <span v-else class="muted">选择目标岗位</span>
            <UIcon name="i-lucide-search" class="shrink-0" />
          </button>
        </UFormField>
        <div class="flex items-end">
          <UButton :loading="loading" :disabled="loading" icon="i-lucide-route" @click="analyze">分析路径</UButton>
        </div>
      </div>
    </UCard>

    <UCard v-if="loading && !hasAnalysis" class="analysis-status" role="status" aria-live="polite">
      <div class="flex items-center gap-3">
        <UIcon name="i-lucide-loader-circle" class="size-5 animate-spin text-primary" />
        <div>
          <p class="font-medium">正在并行分析职业路径</p>
          <p class="text-sm muted">晋升、横向迁移与目标差距会分别返回，不会再因单项缓慢而无限等待。</p>
        </div>
      </div>
    </UCard>

    <UAlert
      v-if="analysisIssues.length"
      color="warning"
      variant="soft"
      icon="i-lucide-triangle-alert"
      title="部分路径数据暂时不可用"
      :description="analysisIssues.join('；')"
    />

    <UEmpty v-if="!attempted && !loading && !hasAnalysis" title="请选择岗位开始分析" icon="i-lucide-network" />

    <UCard v-else-if="attempted && !loading && !hasAnalysis" class="analysis-status analysis-status--error">
      <div>
        <p class="font-semibold">本次路径分析未能完成</p>
        <p class="mt-1 text-sm muted">数据服务已停止等待，不会一直停留在加载状态。你可以直接重新分析。</p>
        <UButton class="mt-4" color="neutral" variant="soft" icon="i-lucide-refresh-cw" @click="analyze">重新分析</UButton>
      </div>
    </UCard>

    <CareerGraphExplorer v-if="hasAnalysis" :data="careerGraph">
      <template #list>
        <UCard v-if="promotion">
          <template #header>
            <div><h2 class="text-lg font-semibold">晋升路径</h2><p class="text-sm muted">按阶段查看目标岗位、里程碑和推荐资源</p></div>
          </template>
          <CareerPathView kind="promotion" :data="promotion" />
        </UCard>
        <UCard v-if="lateral">
          <template #header>
            <div><h2 class="text-lg font-semibold">横向换岗</h2><p class="text-sm muted">按能力相似度展示可迁移方向和准备动作</p></div>
          </template>
          <CareerPathView kind="lateral" :data="lateral" />
        </UCard>
        <UCard v-if="transition">
          <template #header><h2 class="text-lg font-semibold">目标差距与行动建议</h2></template>
          <CareerPathView kind="transition" :data="transition" />
        </UCard>
      </template>
    </CareerGraphExplorer>

    <JobPickerDialog
      :open="Boolean(picker)"
      :title="picker === 'from' ? '选择当前岗位' : '选择目标岗位'"
      :selected-ids="[from, to].filter(Boolean)"
      @update:open="value => { if (!value) picker = null }"
      @select="chooseJob"
    />
  </div>
</template>

<style scoped>
.job-trigger { display: flex; width: 100%; min-height: 3.5rem; align-items: center; justify-content: space-between; gap: .75rem; border: 1px solid var(--ui-border); border-radius: .5rem; padding: .6rem .75rem; background: var(--ui-bg); }
.job-trigger:hover { border-color: color-mix(in srgb, var(--ui-primary) 48%, transparent); }
.analysis-status { border-style: dashed; }
.analysis-status--error { border-color: color-mix(in srgb, var(--ui-error) 42%, var(--ui-border)); }
</style>
