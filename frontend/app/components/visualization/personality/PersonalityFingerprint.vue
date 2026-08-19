<script setup lang="ts">
import P5SceneHost from '../P5SceneHost.client.vue'
import type { PersonalityAnswer, PersonalityResult } from '~/types/personality'
import type { P5SceneStatus } from '~/types/visualization'
import { buildPersonalityFingerprintSceneData } from '~/utils/visualization/personality-fingerprint-adapter'
import { createPersonalityFingerprintScene } from '~/utils/visualization/scenes/personality-fingerprint-scene'

const props = withDefaults(defineProps<{
  result: PersonalityResult
  answers?: Record<number, 'A' | 'B'> | PersonalityAnswer[]
  animationRevision?: number
}>(), {
  answers: () => ({}),
  animationRevision: 0
})

const sceneHost = ref<{ resetView?: () => void }>()
const status = ref<P5SceneStatus>('idle')
const announcement = ref('')
let announcementTimer: ReturnType<typeof setTimeout> | undefined

const sceneData = computed(() => buildPersonalityFingerprintSceneData({
  result: props.result,
  answers: props.answers,
  animationRevision: props.animationRevision
}))
const measured = computed(() => sceneData.value.mode === 'measured')

function replay() {
  sceneHost.value?.resetView?.()
  announcement.value = '正在重新绘制你的人格视觉指纹'
  if (announcementTimer) clearTimeout(announcementTimer)
  announcementTimer = setTimeout(() => { announcement.value = '' }, 1600)
}

onBeforeUnmount(() => {
  if (announcementTimer) clearTimeout(announcementTimer)
})
</script>

<template>
  <section class="personality-fingerprint" aria-labelledby="personality-fingerprint-heading">
    <div class="personality-fingerprint-heading">
      <div>
        <div class="personality-fingerprint-title-row">
          <h3 id="personality-fingerprint-heading">人格视觉指纹</h3>
          <UBadge :label="measured ? '真实倾向比例' : '类型视觉签名'" color="neutral" variant="soft" />
        </div>
        <p>由四个偏好维度生成的稳定纹样，同一份结果会保持同一外观。</p>
      </div>
      <UButton
        icon="i-lucide-refresh-cw"
        color="neutral"
        variant="ghost"
        size="xs"
        aria-label="重播人格视觉指纹绘制"
        :disabled="status === 'loading'"
        @click="replay"
      />
    </div>

    <P5SceneHost
      ref="sceneHost"
      :data="sceneData"
      :create-scene="createPersonalityFingerprintScene"
      accessible-name="人格视觉指纹"
      :min-height="320"
      @status="value => status = value"
    >
      <template #fallback>
        <span>视觉指纹暂时不可用，下方四维数据和完整分析仍可正常阅读。</span>
      </template>
    </P5SceneHost>

    <div class="personality-fingerprint-axes" :aria-label="measured ? '本次测试的四维倾向比例' : '当前 MBTI 类型的四维字母'">
      <div v-for="axis in sceneData.axes" :key="axis.code" class="personality-fingerprint-axis">
        <span>{{ axis.label }}</span>
        <strong v-if="measured">{{ axis.dominant }} {{ Math.round(Math.max(axis.leftScore, axis.rightScore)) }}%</strong>
        <strong v-else>{{ axis.dominant }} · 类型预设</strong>
      </div>
    </div>
    <p class="personality-fingerprint-note">
      <template v-if="measured">纹样由本次真实答题的四维倾向比例生成；它用于呈现偏好结构，不是心理诊断。</template>
      <template v-else>历史结果缺少四维倾向比例；当前纹样依据 MBTI 类型生成，不代表精确心理测量。</template>
    </p>
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
  </section>
</template>

<style scoped>
.personality-fingerprint { display: grid; gap: .65rem; }
.personality-fingerprint-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: .75rem; }
.personality-fingerprint-title-row { display: flex; flex-wrap: wrap; align-items: center; gap: .45rem; }
.personality-fingerprint-title-row h3 { font-size: .88rem; font-weight: 700; }
.personality-fingerprint-heading p { margin-top: .2rem; color: var(--ui-text-muted); font-size: .7rem; line-height: 1.55; }
.personality-fingerprint-axes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .35rem; }
.personality-fingerprint-axis { display: flex; align-items: center; justify-content: space-between; gap: .5rem; border-radius: .55rem; background: color-mix(in srgb, var(--ui-bg-elevated) 86%, transparent); padding: .42rem .55rem; color: var(--ui-text-muted); font-size: .64rem; }
.personality-fingerprint-axis strong { color: var(--ui-text); font-size: .68rem; font-weight: 650; }
.personality-fingerprint-note { color: var(--ui-text-muted); font-size: .64rem; line-height: 1.55; }
@media (max-width: 390px) { .personality-fingerprint-axes { grid-template-columns: 1fr; } }
</style>
