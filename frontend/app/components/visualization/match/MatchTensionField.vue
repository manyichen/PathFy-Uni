<script setup lang="ts">
import P5SceneHost from '../P5SceneHost.client.vue'
import type { CapabilityScorePatch } from '~/types/capability'
import type { JobCard } from '~/types/job'
import type { P5SceneStatus } from '~/types/visualization'
import { buildMatchTensionSceneData } from '~/utils/visualization/match-tension-adapter'
import { createMatchTensionScene } from '~/utils/visualization/scenes/match-tension-scene'

const props = defineProps<{
  studentScores: CapabilityScorePatch
  job: JobCard
}>()

const localReplayRevision = ref(0)
const status = ref<P5SceneStatus>('idle')
const announcement = ref('')
let announcementTimer: ReturnType<typeof setTimeout> | undefined

const sceneData = computed(() => buildMatchTensionSceneData({
  studentScores: props.studentScores,
  job: props.job,
  animationRevision: localReplayRevision.value
}))

function announce(message: string) {
  announcement.value = message
  if (announcementTimer) clearTimeout(announcementTimer)
  announcementTimer = setTimeout(() => { announcement.value = '' }, 1600)
}

function replay() {
  localReplayRevision.value += 1
  announce('正在重新演示能力与岗位要求的张力变化')
}

watch(() => props.job.id, () => announce(`已切换到${props.job.title}，正在更新能力张力场`))
onBeforeUnmount(() => {
  if (announcementTimer) clearTimeout(announcementTimer)
})
</script>

<template>
  <section class="match-tension-field" aria-labelledby="match-tension-heading">
    <div class="match-tension-heading">
      <div>
        <div class="match-tension-title-row">
          <h3 id="match-tension-heading">能力张力场</h3>
          <UBadge label="方向概览" color="neutral" variant="soft" />
        </div>
        <p>连线表达八维差距的方向与强弱，节点旁同时标注画像分与岗位要求分。</p>
      </div>
      <UButton
        icon="i-lucide-refresh-cw"
        color="neutral"
        variant="ghost"
        size="xs"
        aria-label="重播张力变化"
        :disabled="status === 'loading'"
        @click="replay"
      />
    </div>

    <div class="match-tension-legend" aria-hidden="true">
      <span data-kind="student">画像能力</span>
      <span data-kind="requirement">岗位要求</span>
      <span data-kind="deficit">需要补齐</span>
      <span data-kind="surplus">能力余量</span>
    </div>

    <P5SceneHost
      :data="sceneData"
      :create-scene="createMatchTensionScene"
      accessible-name="人岗八维能力张力场"
      :min-height="360"
      @status="value => status = value"
    >
      <template #fallback>
        <span>张力动画暂时不可用，下方差距摘要仍可正常使用。</span>
      </template>
    </P5SceneHost>

    <div class="match-tension-summary">
      <span><strong>{{ sceneData.summary.deficitCount }}</strong> 项需补齐</span>
      <span><strong>{{ sceneData.summary.balancedCount }}</strong> 项较均衡</span>
      <span><strong>{{ sceneData.summary.surplusCount }}</strong> 项有余量</span>
    </div>
    <p v-if="sceneData.summary.largestDeficit" class="match-tension-focus">
      当前最大缺口：{{ sceneData.summary.largestDeficit.label }} {{ Math.round(Math.abs(sceneData.summary.largestDeficit.gap)) }} 分
    </p>
    <ul class="sr-only">
      <li v-for="dimension in sceneData.dimensions" :key="dimension.id">
        {{ dimension.label }}：画像 {{ Math.round(dimension.studentScore) }} 分，岗位要求 {{ Math.round(dimension.requirementScore) }} 分，{{ dimension.status === 'deficit' ? `缺口 ${Math.round(Math.abs(dimension.gap))} 分` : dimension.status === 'surplus' ? `余量 ${Math.round(dimension.gap)} 分` : '基本均衡' }}。
      </li>
    </ul>
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
  </section>
</template>

<style scoped>
.match-tension-field { display: grid; gap: .7rem; margin-bottom: 1rem; }
.match-tension-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: .75rem; }
.match-tension-title-row { display: flex; flex-wrap: wrap; align-items: center; gap: .45rem; }
.match-tension-title-row h3 { font-size: .88rem; font-weight: 700; }
.match-tension-heading p { margin-top: .2rem; color: var(--ui-text-muted); font-size: .7rem; line-height: 1.55; }
.match-tension-legend { display: flex; flex-wrap: wrap; gap: .35rem .75rem; color: var(--ui-text-muted); font-size: .65rem; }
.match-tension-legend span { display: inline-flex; align-items: center; gap: .3rem; }
.match-tension-legend span::before { width: .5rem; height: .5rem; border-radius: 999px; background: var(--legend-color); content: ''; box-shadow: 0 0 7px color-mix(in srgb, var(--legend-color) 55%, transparent); }
.match-tension-legend [data-kind="student"] { --legend-color: #22d3ee; }
.match-tension-legend [data-kind="requirement"] { --legend-color: #a78bfa; }
.match-tension-legend [data-kind="deficit"] { --legend-color: #fb7185; }
.match-tension-legend [data-kind="surplus"] { --legend-color: #2dd4bf; }
.match-tension-summary { display: grid; gap: .35rem; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.match-tension-summary span { border-radius: .55rem; background: var(--ui-bg-elevated); padding: .45rem .3rem; color: var(--ui-text-muted); font-size: .65rem; text-align: center; }
.match-tension-summary strong { color: var(--ui-text); font-size: .78rem; }
.match-tension-focus { color: var(--ui-text-muted); font-size: .68rem; text-align: center; }
@media (max-width: 390px) {
  .match-tension-summary { grid-template-columns: 1fr; }
}
</style>
