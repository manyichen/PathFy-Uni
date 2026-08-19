<script setup lang="ts">
import type { AuthJourneySnapshot } from '~/types/auth-journey'
import { createJourneySketch, type JourneySketchController } from './sketch/createJourneySketch'
import { journeyConfig } from './sketch/config'

const journey = useAuthJourney()
let layer: HTMLElement | null = null
let controller: JourneySketchController | null = null
let disposed = false
let cleanupTimer: ReturnType<typeof setTimeout> | undefined

function snapshot(): AuthJourneySnapshot {
  return {
    state: journey.state.value,
    mode: journey.mode.value,
    identityActive: journey.identityActive.value,
    passwordReady: journey.passwordReady.value,
    successStartedAt: journey.successStartedAt.value,
    errorStartedAt: journey.errorStartedAt.value
  }
}

function syncLayer() {
  if (!layer) return
  layer.dataset.state = journey.state.value
  layer.classList.toggle('is-transitioning', journey.isTransitioning.value)
}

function cleanup() {
  if (cleanupTimer) clearTimeout(cleanupTimer)
  cleanupTimer = undefined
  controller?.remove()
  controller = null
  layer?.remove()
  layer = null
}

onMounted(async () => {
  layer = document.createElement('div')
  layer.className = 'auth-journey-canvas-layer is-visible'
  layer.dataset.state = journey.state.value
  layer.dataset.sketchStatus = 'loading'
  layer.setAttribute('aria-hidden', 'true')
  document.body.append(layer)

  try {
    controller = await createJourneySketch(layer, snapshot)
    if (disposed && !journey.isTransitioning.value) {
      cleanup()
      return
    }
    layer.dataset.sketchStatus = 'ready'
    syncLayer()
  } catch (error) {
    if (layer) layer.dataset.sketchStatus = 'failed'
    console.error('[AuthJourney] Canvas 初始化失败', error)
  }
})

watch([journey.state, journey.isTransitioning], syncLayer)

onBeforeUnmount(() => {
  disposed = true
  if (!journey.isTransitioning.value) {
    cleanup()
    return
  }

  const remaining = Math.max(0, journey.successStartedAt.value + journeyConfig.reveal.finishAt + 260 - performance.now())
  cleanupTimer = setTimeout(cleanup, remaining)
})
</script>

<template>
  <p class="sr-only" aria-live="polite">{{ journey.liveMessage.value }}</p>
</template>
