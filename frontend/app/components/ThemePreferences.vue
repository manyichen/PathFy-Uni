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
          <div class="appearance-hue-shell">
            <input
              v-model.number="hueNumber"
              aria-label="主题色相"
              type="range"
              min="0"
              max="360"
              step="5"
              class="appearance-hue-slider"
            >
          </div>
        </div>
      </div>
    </template>
  </UPopover>
</template>
