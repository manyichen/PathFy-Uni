<script setup lang="ts">
import type { HuePreference } from '~/composables/useAppearancePreferences'

const auth = useAuth()
const settingsApi = useSettingsApi()
const route = useRoute()
const {
  hue,
  applyHue,
  loadLocal,
  snapshot
} = useAppearancePreferences()

const open = ref(false)
const ready = ref(false)
const saving = ref(false)
let saveTimer: ReturnType<typeof setTimeout> | undefined

const hueNumber = computed({
  get: () => Number(hue.value),
  set: value => selectHue(String(value))
})

const shortcuts = [
  { label: '画像', to: '/profile', icon: 'i-lucide-radar' },
  { label: '匹配', to: '/match', icon: 'i-lucide-git-compare' },
  { label: '报告', to: '/report', icon: 'i-lucide-file-text' }
]

function persistPreference() {
  if (!ready.value || !auth.isAuthenticated.value) return
  if (saveTimer) clearTimeout(saveTimer)
  saving.value = true
  saveTimer = setTimeout(async () => {
    try {
      await settingsApi.savePreferences(snapshot())
    } finally {
      saving.value = false
    }
  }, 450)
}

function selectHue(value: HuePreference) {
  applyHue(value)
  persistPreference()
}

function scrollTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
  open.value = false
}

function closeDock() {
  open.value = false
}

function toggleDock() {
  open.value = !open.value
}

onMounted(() => {
  auth.hydrate()
  loadLocal()
  ready.value = true
})

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer)
})

watch(() => route.fullPath, () => {
  open.value = false
})
</script>

<template>
  <aside class="quick-dock" aria-label="快捷浮窗">
    <Transition name="dock-panel">
      <div v-if="open" class="quick-panel">
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-sm font-semibold">快捷浮窗</p>
            <p class="mt-0.5 text-xs muted">{{ saving ? '正在同步外观偏好' : '常用入口与外观偏好' }}</p>
          </div>
          <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="xs" aria-label="关闭快捷浮窗" @click="closeDock" />
        </div>

        <div class="mt-4 grid grid-cols-3 gap-2">
          <UButton
            v-for="item in shortcuts"
            :key="item.to"
            :to="item.to"
            :icon="item.icon"
            color="neutral"
            variant="soft"
            size="sm"
            block
          >
            {{ item.label }}
          </UButton>
        </div>

        <div class="mt-4 space-y-2">
          <div class="flex items-center justify-between">
            <p class="text-xs font-semibold uppercase text-muted">主题色</p>
            <span class="text-xs muted">{{ hue }}°</span>
          </div>
          <div class="dock-slider-shell">
            <input
              v-model.number="hueNumber"
              aria-label="快捷主题色相"
              type="range"
              min="0"
              max="360"
              step="5"
              class="dock-slider"
            >
          </div>
        </div>

        <UButton class="mt-4" block color="neutral" variant="outline" icon="i-lucide-arrow-up" @click="scrollTop">
          回到顶部
        </UButton>
      </div>
    </Transition>

    <UButton
      class="quick-toggle"
      :icon="open ? 'i-lucide-panel-right-close' : 'i-lucide-sliders-horizontal'"
      color="primary"
      size="lg"
      :aria-expanded="open"
      aria-label="快捷浮窗"
      @click="toggleDock"
    />
  </aside>
</template>

<style scoped>
.quick-dock {
  position: fixed;
  right: max(1rem, env(safe-area-inset-right));
  bottom: max(1rem, env(safe-area-inset-bottom));
  z-index: 60;
  display: grid;
  justify-items: end;
  gap: 0.75rem;
  pointer-events: none;
}

.quick-panel,
.quick-toggle {
  pointer-events: auto;
}

.quick-panel {
  width: min(22rem, calc(100vw - 2rem));
  border: 1px solid var(--ui-border);
  border-radius: 0.9rem;
  background: color-mix(in srgb, var(--ui-bg) 94%, transparent);
  padding: 1rem;
  box-shadow: 0 24px 60px -32px rgb(15 23 42 / 0.5);
  backdrop-filter: blur(18px);
}

.quick-toggle {
  box-shadow: 0 18px 34px -20px var(--ui-primary);
}

.dock-slider-shell {
  border-radius: 0.5rem;
  background: oklch(0.8 0.1 0);
  padding: 0 0.25rem;
}

.dock-slider {
  width: 100%;
  height: 1.4rem;
  appearance: none;
  border-radius: 0.35rem;
  background-image: var(--color-selection-bar);
}

.dock-slider::-webkit-slider-thumb {
  width: 0.5rem;
  height: 0.95rem;
  appearance: none;
  border-radius: 0.16rem;
  background: rgb(255 255 255 / 0.78);
  box-shadow: 0 0 0 1px rgb(15 23 42 / 0.18);
}

.dock-slider::-moz-range-thumb {
  width: 0.5rem;
  height: 0.95rem;
  border: 0;
  border-radius: 0.16rem;
  background: rgb(255 255 255 / 0.78);
  box-shadow: 0 0 0 1px rgb(15 23 42 / 0.18);
}

.dock-panel-enter-active,
.dock-panel-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.dock-panel-enter-from,
.dock-panel-leave-to {
  opacity: 0;
  transform: translateY(0.5rem) scale(0.98);
}

@media (max-width: 640px) {
  .quick-dock {
    right: 0.75rem;
    bottom: 0.75rem;
  }
}
</style>
