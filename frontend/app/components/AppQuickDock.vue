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
          <div class="appearance-hue-shell">
            <input
              v-model.number="hueNumber"
              aria-label="快捷主题色相"
              type="range"
              min="0"
              max="360"
              step="5"
              class="appearance-hue-slider"
            >
          </div>
        </div>

        <UButton class="mt-4" block color="neutral" variant="outline" icon="i-lucide-arrow-up" @click="scrollTop">
          回到顶部
        </UButton>

        <footer class="dock-signature">
          <p class="dock-pursuit">“把复杂的选择，做成清晰而有温度的成长路径。”</p>
          <dl class="dock-meta">
            <div>
              <dt>开发团队</dt>
              <dd>suilli小队</dd>
            </div>
            <div>
              <dt>联系我们</dt>
              <dd><a href="mailto:3374161455@qq.com">3374161455@qq.com</a></dd>
            </div>
          </dl>
        </footer>
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

.dock-signature {
  margin-top: 0.9rem;
  padding-top: 0.85rem;
  border-top: 1px dashed color-mix(in srgb, var(--ui-border) 78%, transparent);
}

.dock-pursuit {
  color: var(--ui-text-muted);
  font-size: 0.74rem;
  line-height: 1.55;
}

.dock-meta {
  display: grid;
  gap: 0.35rem;
  margin-top: 0.65rem;
  font-size: 0.72rem;
}

.dock-meta > div {
  display: grid;
  grid-template-columns: 4.4rem minmax(0, 1fr);
  gap: 0.5rem;
}

.dock-meta dt {
  color: var(--ui-text-muted);
}

.dock-meta dd {
  min-width: 0;
  color: var(--ui-text);
  font-weight: 600;
}

.dock-meta a {
  color: var(--ui-primary);
  text-decoration: none;
  overflow-wrap: anywhere;
}

.dock-meta a:hover {
  text-decoration: underline;
  text-underline-offset: 0.18rem;
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
