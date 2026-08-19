<script setup lang="ts">
import P5SceneHost from '../P5SceneHost.client.vue'
import type { HomeWorkflowStageKey } from '~/types/home-workflow-experience'
import type { P5SceneStatus } from '~/types/visualization'
import { emitHomeWorkflowExperienceEvent } from '~/utils/home-workflow-metrics'
import { buildHomeWorkflowSceneData } from '~/utils/visualization/home-workflow-adapter'
import { createHomeWorkflowScene } from '~/utils/visualization/scenes/home-workflow-scene'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [open: boolean] }>()
const activeIndex = ref(0)
const animationRevision = ref(0)
const autoPlaying = ref(true)
const reducedMotion = ref(false)
const status = ref<P5SceneStatus>('idle')
const announcement = ref('')
let stepTimer: ReturnType<typeof setTimeout> | undefined
let motionQuery: MediaQueryList | undefined
let completionTracked = false

const sceneData = computed(() => buildHomeWorkflowSceneData({ activeIndex: activeIndex.value, animationRevision: animationRevision.value }))
const isComplete = computed(() => activeIndex.value === sceneData.value.stages.length - 1)

function clearStepTimer() {
  if (stepTimer) clearTimeout(stepTimer)
  stepTimer = undefined
}

function scheduleNext() {
  clearStepTimer()
  if (!props.open || !autoPlaying.value || reducedMotion.value || document.hidden || isComplete.value) return
  stepTimer = setTimeout(() => setStage(activeIndex.value + 1, false), 1350)
}

function announce(message: string) {
  announcement.value = message
}

function setStage(index: number, manual = true) {
  const next = Math.max(0, Math.min(sceneData.value.stages.length - 1, index))
  if (manual) autoPlaying.value = false
  if (next === activeIndex.value) animationRevision.value += 1
  else activeIndex.value = next
  const stage = sceneData.value.stages[next]!
  emitHomeWorkflowExperienceEvent('stage', stage.key)
  announce(`当前阶段：${stage.label}，${stage.hint}`)
  if (next === sceneData.value.stages.length - 1 && !completionTracked) {
    completionTracked = true
    emitHomeWorkflowExperienceEvent('complete', stage.key)
  }
}

function selectFromCanvas(selection: unknown) {
  const stage = String((selection as { stage?: unknown })?.stage || '') as HomeWorkflowStageKey
  const index = sceneData.value.stages.findIndex(item => item.key === stage)
  if (index >= 0) setStage(index)
}

function togglePlayback() {
  autoPlaying.value = !autoPlaying.value
  if (autoPlaying.value && isComplete.value) {
    completionTracked = false
    activeIndex.value = 0
    animationRevision.value += 1
  }
  announce(autoPlaying.value ? '流程演示继续播放' : '流程演示已暂停')
  scheduleNext()
}

function replay() {
  completionTracked = false
  activeIndex.value = 0
  animationRevision.value += 1
  autoPlaying.value = !reducedMotion.value
  emitHomeWorkflowExperienceEvent('stage', 'material')
  announce(reducedMotion.value ? '已回到材料阶段，可使用下一步按钮浏览' : '正在从材料阶段重新演示')
  scheduleNext()
}

function close() {
  emitHomeWorkflowExperienceEvent('exit', sceneData.value.activeStage.key)
  emit('update:open', false)
}

function onOpenChange(value: boolean) {
  if (!value) close()
}

function onMotionChange(event: MediaQueryListEvent) {
  reducedMotion.value = event.matches
  if (event.matches) autoPlaying.value = false
  scheduleNext()
}

function onVisibilityChange() {
  scheduleNext()
}

function sceneError(error: unknown) {
  console.error('首页职业路径体验绘制失败', error)
}

watch(activeIndex, scheduleNext)
watch(() => props.open, (open) => {
  if (open) scheduleNext()
  else clearStepTimer()
})

onMounted(() => {
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  reducedMotion.value = motionQuery.matches
  if (reducedMotion.value) autoPlaying.value = false
  motionQuery.addEventListener('change', onMotionChange)
  document.addEventListener('visibilitychange', onVisibilityChange)
  emitHomeWorkflowExperienceEvent('open', 'material')
  scheduleNext()
})

onBeforeUnmount(() => {
  clearStepTimer()
  motionQuery?.removeEventListener('change', onMotionChange)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <UModal
    :open="open"
    title="职业规划五阶段路径体验"
    description="固定产品流程演示，不读取或推测你的个人材料、画像和规划进度。"
    :ui="{ content: 'sm:max-w-5xl' }"
    @update:open="onOpenChange"
  >
    <template #body>
      <div class="home-workflow-experience">
        <div class="experience-toolbar">
          <div>
            <UBadge label="主动体验 · 约 7 秒" color="neutral" variant="soft" />
            <p>观察信息如何从材料流向画像、匹配与计划，再由复盘结果返回下一轮校准。</p>
          </div>
          <div class="flex gap-1">
            <UButton
              :icon="autoPlaying ? 'i-lucide-pause' : 'i-lucide-play'"
              color="neutral"
              variant="ghost"
              size="xs"
              :aria-label="autoPlaying ? '暂停流程演示' : '继续流程演示'"
              :disabled="reducedMotion"
              @click="togglePlayback"
            />
            <UButton icon="i-lucide-refresh-cw" color="neutral" variant="ghost" size="xs" aria-label="重新播放流程演示" @click="replay" />
          </div>
        </div>

        <P5SceneHost
          :data="sceneData"
          :create-scene="createHomeWorkflowScene"
          accessible-name="职业规划五阶段路径体验"
          :min-height="390"
          @select="selectFromCanvas"
          @status="value => status = value"
          @error="sceneError"
        >
          <template #fallback>
            <span>动态路径暂时不可用，请使用下方五阶段按钮继续浏览流程。</span>
          </template>
        </P5SceneHost>

        <ol class="experience-stage-list" aria-label="职业规划五阶段演示">
          <li v-for="(stage, index) in sceneData.stages" :key="stage.key">
            <button type="button" :aria-current="index === activeIndex ? 'step' : undefined" @click="setStage(index)">
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <strong>{{ stage.label }}</strong>
              <small>{{ stage.hint }}</small>
            </button>
          </li>
        </ol>

        <article class="experience-stage-detail" :style="{ '--stage-color': sceneData.activeStage.color }">
          <div>
            <span>当前阶段 {{ String(activeIndex + 1).padStart(2, '0') }}</span>
            <h3>{{ sceneData.activeStage.label }} · {{ sceneData.activeStage.hint }}</h3>
            <p>{{ sceneData.activeStage.description }}</p>
          </div>
          <UButton :to="sceneData.activeStage.to" trailing-icon="i-lucide-arrow-right">
            进入{{ sceneData.activeStage.label }}模块
          </UButton>
        </article>

        <div class="experience-controls">
          <UButton color="neutral" variant="soft" icon="i-lucide-arrow-left" :disabled="activeIndex === 0" @click="setStage(activeIndex - 1)">上一步</UButton>
          <span>{{ activeIndex + 1 }} / {{ sceneData.stages.length }}</span>
          <UButton v-if="!isComplete" trailing-icon="i-lucide-arrow-right" @click="setStage(activeIndex + 1)">下一步</UButton>
          <UButton v-else trailing-icon="i-lucide-rotate-ccw" @click="replay">再次体验</UButton>
        </div>
        <p class="sr-only" aria-live="polite">{{ announcement }}</p>
      </div>
    </template>
    <template #footer>
      <div class="flex w-full items-center justify-between gap-3">
        <span class="text-xs muted">演示场景不会保存个人数据或改变工作区状态。</span>
        <UButton color="neutral" variant="soft" @click="close">关闭流程演示</UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.home-workflow-experience { display: grid; gap: .85rem; }
.experience-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: .8rem; }
.experience-toolbar p { margin-top: .35rem; max-width: 720px; color: var(--ui-text-muted); font-size: .75rem; line-height: 1.6; }
.experience-stage-list { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .4rem; }
.experience-stage-list button { display: grid; width: 100%; gap: .12rem; border: 1px solid var(--ui-border); border-radius: .65rem; background: var(--ui-bg-elevated); padding: .55rem .4rem; text-align: center; transition: border-color .16s ease, background .16s ease; }
.experience-stage-list button:hover, .experience-stage-list button:focus-visible, .experience-stage-list button[aria-current="step"] { border-color: color-mix(in srgb, var(--ui-primary) 58%, var(--ui-border)); background: color-mix(in srgb, var(--ui-primary) 8%, var(--ui-bg-elevated)); outline: none; }
.experience-stage-list span { color: var(--ui-text-muted); font-family: ui-monospace, monospace; font-size: .62rem; }
.experience-stage-list strong { font-size: .78rem; }
.experience-stage-list small { color: var(--ui-text-muted); font-size: .65rem; }
.experience-stage-detail { --stage-color: var(--ui-primary); display: flex; align-items: center; justify-content: space-between; gap: 1rem; border-left: 3px solid var(--stage-color); border-radius: .7rem; background: color-mix(in srgb, var(--stage-color) 7%, var(--ui-bg-elevated)); padding: .85rem 1rem; }
.experience-stage-detail span { color: var(--ui-text-muted); font-size: .65rem; }
.experience-stage-detail h3 { margin-top: .15rem; font-size: .95rem; font-weight: 700; }
.experience-stage-detail p { margin-top: .2rem; color: var(--ui-text-muted); font-size: .72rem; line-height: 1.55; }
.experience-controls { display: flex; align-items: center; justify-content: center; gap: .8rem; }
.experience-controls > span { min-width: 3rem; color: var(--ui-text-muted); font-size: .72rem; text-align: center; }
@media (max-width: 720px) {
  .experience-stage-list { grid-template-columns: 1fr; }
  .experience-stage-detail { align-items: stretch; flex-direction: column; }
}
</style>
