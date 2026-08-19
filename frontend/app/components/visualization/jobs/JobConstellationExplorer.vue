<script setup lang="ts">
import P5SceneHost from '../P5SceneHost.client.vue'
import type { JobCard } from '~/types/job'
import type { JobConstellationSourceKind } from '~/types/job-constellation'
import type { P5SceneStatus } from '~/types/visualization'
import { buildJobConstellationSceneData } from '~/utils/visualization/job-constellation-adapter'
import { createJobConstellationScene } from '~/utils/visualization/scenes/job-constellation-scene'

const props = withDefaults(defineProps<{
  jobs: JobCard[]
  selectedId?: string | null
  sourceKind?: JobConstellationSourceKind
  totalAvailable?: number
  page?: number
  pageSize?: number
  query?: string
  sort?: string
}>(), {
  selectedId: '',
  sourceKind: 'list',
  totalAvailable: 0,
  page: 1,
  pageSize: 20,
  query: '',
  sort: 'default'
})

const emit = defineEmits<{ select: [jobId: string]; refresh: [] }>()
const status = ref<P5SceneStatus>('idle')
const animationRevision = ref(0)
const announcement = ref('')
let announcementTimer: ReturnType<typeof setTimeout> | undefined

const sceneData = computed(() => buildJobConstellationSceneData({
  jobs: props.jobs,
  selectedId: props.selectedId,
  sourceKind: props.sourceKind,
  totalAvailable: props.totalAvailable,
  page: props.page,
  pageSize: props.pageSize,
  query: props.query,
  sort: props.sort,
  animationRevision: animationRevision.value
}))

function announce(message: string) {
  announcement.value = message
  if (announcementTimer) clearTimeout(announcementTimer)
  announcementTimer = setTimeout(() => { announcement.value = '' }, 1800)
}

function selectJob(jobId: string) {
  const job = sceneData.value.nodes.find(node => node.id === jobId)
  emit('select', jobId)
  announce(`已选择${job?.title || '岗位'}，正在打开岗位详情`)
}

function selectFromCanvas(selection: unknown) {
  const jobId = String((selection as { jobId?: unknown })?.jobId || '')
  if (jobId) selectJob(jobId)
}

function exploreRandomly() {
  animationRevision.value += 1
  emit('refresh')
  announce('正在随机换一批岗位，探索新的岗位星群')
}

function sceneError(error: unknown) {
  console.error('岗位星群绘制失败', error)
}

onBeforeUnmount(() => {
  if (announcementTimer) clearTimeout(announcementTimer)
})
</script>

<template>
  <section class="job-constellation-explorer" aria-labelledby="job-constellation-heading">
    <div class="job-constellation-heading">
      <div>
        <div class="job-constellation-title-row">
          <h2 id="job-constellation-heading">岗位星群</h2>
          <UBadge label="当前结果集" color="neutral" variant="soft" />
          <UBadge :label="sceneData.sourceKind === 'assistant' ? 'AI 筛选' : `第 ${sceneData.page} 页`" variant="soft" />
        </div>
        <p>岗位按主导能力进入六片星域，八维要求投影决定星域内方位；节点大小表示岗位要求均值，不代表个人匹配度或推荐排名。</p>
      </div>
      <UButton
        icon="i-lucide-shuffle"
        color="neutral"
        variant="ghost"
        size="xs"
        aria-label="随机探索一批岗位"
        label="换一片星域"
        title="随机探索一批岗位"
        :disabled="status === 'loading'"
        @click="exploreRandomly"
      />
    </div>

    <div class="job-constellation-legend" aria-hidden="true">
      <span v-for="group in sceneData.groups" :key="group.key" :style="{ '--group-color': group.color }">
        {{ group.label }} {{ group.count }} 个
      </span>
    </div>

    <P5SceneHost
      :data="sceneData"
      :create-scene="createJobConstellationScene"
      accessible-name="岗位星群探索视图"
      :min-height="520"
      @select="selectFromCanvas"
      @status="value => status = value"
      @error="sceneError"
    >
      <template #fallback>
        <span>岗位星群暂时不可用，下方岗位按钮和列表视图仍可正常打开详情。</span>
      </template>
    </P5SceneHost>

    <div class="job-constellation-summary">
      <span><strong>{{ sceneData.summary.resultCount }}</strong> 个当前岗位</span>
      <span><strong>{{ sceneData.summary.regionCount }}</strong> 个活跃能力星域</span>
      <span><strong>{{ Math.round(sceneData.summary.minimumRequirement) }}–{{ Math.round(sceneData.summary.maximumRequirement) }}</strong> 要求均值范围</span>
    </div>

    <p class="job-constellation-note">
      细线只连接同一能力星域内八维要求最接近的岗位，不表示晋升、企业关系或系统推荐。当前{{ sceneData.resultLabel }}共展示 {{ sceneData.nodes.length }} 个岗位<span v-if="sceneData.totalAvailable > sceneData.nodes.length">，全部筛选结果共 {{ sceneData.totalAvailable }} 个</span>。
    </p>

    <div class="job-constellation-accessible" aria-label="当前星群岗位列表">
      <button
        v-for="node in sceneData.nodes"
        :key="node.id"
        type="button"
        :aria-current="node.selected ? 'true' : undefined"
        @click="selectJob(node.id)"
      >
        <span>{{ node.title }}</span>
        <small>{{ node.company }} · {{ node.location }} · 岗位要求均值 {{ Math.round(node.requirementAverage) }} 分</small>
      </button>
    </div>
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
  </section>
</template>

<style scoped>
.job-constellation-explorer { display: grid; gap: .8rem; }
.job-constellation-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: .8rem; }
.job-constellation-title-row { display: flex; flex-wrap: wrap; align-items: center; gap: .45rem; }
.job-constellation-title-row h2 { font-size: 1rem; font-weight: 720; }
.job-constellation-heading p { margin-top: .25rem; max-width: 760px; color: var(--ui-text-muted); font-size: .73rem; line-height: 1.6; }
.job-constellation-legend { display: flex; flex-wrap: wrap; gap: .4rem .8rem; color: var(--ui-text-muted); font-size: .68rem; }
.job-constellation-legend span { display: inline-flex; align-items: center; gap: .32rem; }
.job-constellation-legend span::before { width: .5rem; height: .5rem; border-radius: 999px; background: var(--group-color); box-shadow: 0 0 8px color-mix(in srgb, var(--group-color) 60%, transparent); content: ''; }
.job-constellation-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .45rem; }
.job-constellation-summary span { border-radius: .65rem; background: var(--ui-bg-elevated); padding: .55rem .4rem; color: var(--ui-text-muted); font-size: .7rem; text-align: center; }
.job-constellation-summary strong { color: var(--ui-text); font-size: .83rem; }
.job-constellation-note { color: var(--ui-text-muted); font-size: .7rem; line-height: 1.6; text-align: center; }
.job-constellation-accessible { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .45rem; }
.job-constellation-accessible button { min-width: 0; border: 1px solid var(--ui-border); border-radius: .65rem; background: color-mix(in srgb, var(--ui-bg-elevated) 84%, transparent); padding: .58rem .7rem; text-align: left; transition: border-color .16s ease, background .16s ease; }
.job-constellation-accessible button:hover, .job-constellation-accessible button:focus-visible, .job-constellation-accessible button[aria-current="true"] { border-color: color-mix(in srgb, var(--ui-primary) 55%, var(--ui-border)); background: color-mix(in srgb, var(--ui-primary) 8%, var(--ui-bg-elevated)); outline: none; }
.job-constellation-accessible span, .job-constellation-accessible small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.job-constellation-accessible span { font-size: .78rem; font-weight: 650; }
.job-constellation-accessible small { margin-top: .18rem; color: var(--ui-text-muted); font-size: .65rem; }
@media (max-width: 720px) {
  .job-constellation-accessible, .job-constellation-summary { grid-template-columns: 1fr; }
}
</style>
