<script setup lang="ts">
import type { P5SceneFactory, P5SceneRuntime, P5SceneSize, P5SceneStatus } from '~/types/visualization'

const props = withDefaults(defineProps<{
  data: unknown
  createScene: P5SceneFactory
  accessibleName: string
  enabled?: boolean
  minHeight?: number
}>(), {
  enabled: true,
  minHeight: 420
})

const emit = defineEmits<{
  select: [selection: unknown]
  status: [status: P5SceneStatus]
  error: [error: unknown]
}>()

const shell = ref<HTMLElement>()
const host = ref<HTMLElement>()
const status = ref<P5SceneStatus>('idle')
const lastError = ref('')
const reducedMotion = ref(false)
let runtime: P5SceneRuntime | undefined
let intersectionObserver: IntersectionObserver | undefined
let resizeObserver: ResizeObserver | undefined
let motionQuery: MediaQueryList | undefined
let visible = false
let disposed = false
let initializationId = 0
let pendingInitializationId = 0

function onMotionChange(event: MediaQueryListEvent) {
  reducedMotion.value = event.matches
  runtime?.setReducedMotion?.(event.matches)
}

function onVisibilityChange() {
  syncActivity()
}

function setStatus(next: P5SceneStatus) {
  status.value = next
  emit('status', next)
}

function rememberError(error: unknown) {
  lastError.value = error instanceof Error ? error.message : String(error || 'unknown')
}

function sceneSize(): P5SceneSize {
  const rect = host.value?.getBoundingClientRect()
  const lowPower = (navigator.hardwareConcurrency || 8) <= 4
  return {
    width: Math.max(1, Math.round(rect?.width || 1)),
    height: Math.max(1, Math.round(rect?.height || props.minHeight)),
    pixelRatio: lowPower ? 1 : Math.min(window.devicePixelRatio || 1, 1.5)
  }
}

function syncActivity() {
  runtime?.setActive(visible && !document.hidden)
}

function destroyScene() {
  initializationId += 1
  pendingInitializationId = 0
  runtime?.destroy()
  runtime = undefined
  host.value?.replaceChildren()
}

async function ensureScene() {
  if (!props.enabled || runtime || pendingInitializationId || !host.value || disposed) return
  const size = sceneSize()
  if (size.width <= 1) return
  const currentId = ++initializationId
  pendingInitializationId = currentId
  let sceneReportedError = false
  lastError.value = ''
  setStatus('loading')

  try {
    const nextRuntime = await props.createScene({
      host: host.value,
      data: props.data,
      size,
      reducedMotion: reducedMotion.value,
      onSelect: selection => emit('select', selection),
      onError: (error, context) => {
        sceneReportedError = true
        rememberError(error)
        emit('error', error)
        if (context?.recoverable) {
          sceneReportedError = false
          return
        }
        if (runtime && currentId === initializationId) {
          destroyScene()
          setStatus('failed')
        }
      }
    })
    if (disposed || currentId !== initializationId || !props.enabled) {
      nextRuntime.destroy()
      return
    }
    if (sceneReportedError) {
      nextRuntime.destroy()
      host.value?.replaceChildren()
      setStatus('failed')
      return
    }
    runtime = nextRuntime
    runtime.resize(sceneSize())
    syncActivity()
    setStatus('ready')
  } catch (error) {
    if (currentId !== initializationId || disposed) return
    host.value?.replaceChildren()
    rememberError(error)
    setStatus('failed')
    emit('error', error)
  } finally {
    if (pendingInitializationId === currentId) pendingInitializationId = 0
  }
}

function resetView() {
  runtime?.resetView?.()
}

defineExpose({ resetView })

onMounted(() => {
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  reducedMotion.value = motionQuery.matches
  motionQuery.addEventListener('change', onMotionChange)

  document.addEventListener('visibilitychange', onVisibilityChange)

  resizeObserver = new ResizeObserver(() => runtime?.resize(sceneSize()))
  if (host.value) resizeObserver.observe(host.value)

  intersectionObserver = new IntersectionObserver(entries => {
    visible = Boolean(entries[0]?.isIntersecting)
    if (visible) void ensureScene()
    syncActivity()
  }, { rootMargin: '240px 0px', threshold: 0.01 })
  if (shell.value) intersectionObserver.observe(shell.value)
})

watch(() => props.data, value => runtime?.update(value))
watch(() => props.enabled, enabled => {
  if (!enabled) {
    destroyScene()
    setStatus('idle')
    return
  }
  if (visible) void ensureScene()
})

onBeforeUnmount(() => {
  disposed = true
  motionQuery?.removeEventListener('change', onMotionChange)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  intersectionObserver?.disconnect()
  resizeObserver?.disconnect()
  destroyScene()
})
</script>

<template>
  <div
    ref="shell"
    class="p5-scene-shell"
    :data-p5-scene-status="status"
    :data-p5-scene-error="lastError || undefined"
    :style="{ '--p5-scene-min-height': `${minHeight}px` }"
  >
    <div
      ref="host"
      class="p5-scene-canvas"
      aria-hidden="true"
      role="presentation"
    />
    <div v-if="status === 'loading'" class="p5-scene-state" aria-hidden="true">
      <span class="p5-scene-loader" />
      <span>正在建立可视化空间…</span>
    </div>
    <div v-else-if="status === 'failed'" class="p5-scene-state p5-scene-state--failed">
      <slot name="fallback">
        <span>动态图谱暂时不可用，请使用列表视图。</span>
      </slot>
    </div>
    <p class="sr-only" aria-live="polite">
      {{ status === 'ready' ? `${accessibleName}已就绪` : status === 'failed' ? `${accessibleName}加载失败` : '' }}
    </p>
    <slot name="overlay" :status="status" />
  </div>
</template>

<style scoped>
.p5-scene-shell {
  position: relative;
  min-height: var(--p5-scene-min-height);
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--ui-primary) 18%, var(--ui-border));
  border-radius: 1rem;
  background:
    radial-gradient(circle at 50% 45%, color-mix(in srgb, var(--ui-primary) 8%, transparent), transparent 46%),
    color-mix(in srgb, var(--ui-bg-elevated) 82%, var(--ui-bg));
  isolation: isolate;
}
.p5-scene-canvas { position: absolute; inset: 0; }
.p5-scene-canvas :deep(canvas) { display: block; width: 100% !important; height: 100% !important; }
.p5-scene-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: .65rem;
  color: var(--ui-text-muted);
  font-size: .82rem;
}
.p5-scene-state--failed { padding: 1rem; text-align: center; }
.p5-scene-loader {
  width: .9rem;
  height: .9rem;
  border: 2px solid color-mix(in srgb, var(--ui-primary) 24%, transparent);
  border-top-color: var(--ui-primary);
  border-radius: 999px;
  animation: p5-scene-spin .8s linear infinite;
}
@keyframes p5-scene-spin { to { transform: rotate(1turn); } }
@media (prefers-reduced-motion: reduce) { .p5-scene-loader { animation: none; } }
</style>
