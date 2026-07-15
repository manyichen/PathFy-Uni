<script setup lang="ts">
import type { HuePreference } from '~/composables/useAppearancePreferences'

const auth = useAuth()
const settingsApi = useSettingsApi()
const {
  hue,
  applyHue,
  applyPreferences,
  loadLocal,
  snapshot
} = useAppearancePreferences()

const ready = ref(false)
const saving = ref(false)
let saveTimer: ReturnType<typeof setTimeout> | undefined

const hueNumber = computed({
  get: () => Number(hue.value),
  set: value => selectHue(String(value))
})

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

onMounted(async () => {
  auth.hydrate()
  loadLocal()

  if (auth.isAuthenticated.value) {
    try {
      const data = await settingsApi.preferences()
      applyPreferences(data?.preferences)
    } catch {
      /* Account page surfaces preference loading errors. */
    }
  }
  ready.value = true
})

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer)
})
</script>

<template>
  <UPopover>
    <UButton icon="i-lucide-palette" color="neutral" variant="ghost" aria-label="外观设置" />

    <template #content>
      <div class="w-72 space-y-5 p-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="text-sm font-semibold">外观</p>
            <p class="text-xs muted">{{ saving ? '正在同步偏好' : '同步本机与账户偏好' }}</p>
          </div>
          <div class="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
            <UIcon name="i-lucide-swatch-book" class="size-5" />
          </div>
        </div>

        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">主题色</span>
            <span class="text-xs muted">{{ hue }}°</span>
          </div>
          <div class="theme-slider-shell">
            <input
              v-model.number="hueNumber"
              aria-label="主题色相"
              type="range"
              min="0"
              max="360"
              step="5"
              class="theme-slider"
            >
          </div>
        </div>
      </div>
    </template>
  </UPopover>
</template>

<style scoped>
.theme-slider-shell {
  border-radius: 0.55rem;
  background: oklch(0.8 0.1 0);
  padding: 0 0.25rem;
}

.theme-slider {
  width: 100%;
  height: 1.5rem;
  appearance: none;
  border-radius: 0.35rem;
  background-image: var(--color-selection-bar);
}

.theme-slider::-webkit-slider-thumb {
  width: 0.55rem;
  height: 1rem;
  appearance: none;
  border-radius: 0.18rem;
  background: rgb(255 255 255 / 0.78);
  box-shadow: 0 0 0 1px rgb(15 23 42 / 0.18);
}

.theme-slider::-moz-range-thumb {
  width: 0.55rem;
  height: 1rem;
  border: 0;
  border-radius: 0.18rem;
  background: rgb(255 255 255 / 0.78);
  box-shadow: 0 0 0 1px rgb(15 23 42 / 0.18);
}
</style>
