<script setup lang="ts">
const auth = useAuth()
const settingsApi = useSettingsApi()
const { theme, toggleLightDark, loadLocal, snapshot } = useAppearancePreferences()

const isDark = ref(false)
const changing = ref(false)

function syncFromDocument() {
  if (!import.meta.client) return
  isDark.value = document.documentElement.classList.contains('dark')
}

async function persistPreference() {
  if (!auth.isAuthenticated.value) return
  await settingsApi.savePreferences(snapshot()).catch(() => {})
}

async function onToggle(event: MouseEvent) {
  if (changing.value) return
  changing.value = true
  try {
    await toggleLightDark(event)
    syncFromDocument()
    await persistPreference()
  } finally {
    changing.value = false
  }
}

onMounted(() => {
  auth.hydrate()
  loadLocal()
  syncFromDocument()
})

watch(theme, () => nextTick(syncFromDocument))
</script>

<template>
  <button
    type="button"
    class="scheme-switch"
    aria-label="明暗切换"
    :data-mode="isDark ? 'dark' : 'light'"
    :disabled="changing"
    @click="onToggle"
  >
    <span class="icon-layer" :class="{ inactive: isDark }" aria-hidden="true">
      <UIcon name="i-lucide-sun" class="size-5" />
    </span>
    <span class="icon-layer" :class="{ inactive: !isDark }" aria-hidden="true">
      <UIcon name="i-lucide-moon" class="size-5" />
    </span>
  </button>
</template>

<style scoped>
.scheme-switch {
  position: relative;
  z-index: 60;
  display: grid;
  width: 2.5rem;
  height: 2.5rem;
  place-items: center;
  border-radius: 0.65rem;
  color: var(--ui-text-muted);
  transition: background-color 160ms ease, color 160ms ease, transform 160ms ease;
}

.scheme-switch:hover {
  background: var(--ui-bg-elevated);
  color: var(--ui-text);
}

.scheme-switch:active {
  transform: scale(0.94);
}

.scheme-switch:disabled {
  cursor: wait;
  opacity: 0.72;
}

.icon-layer {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  pointer-events: none;
  transition: opacity 260ms ease, transform 260ms ease;
}

.icon-layer.inactive {
  opacity: 0;
  transform: scale(0.72) rotate(90deg);
}

.scheme-switch[data-mode="dark"] .icon-layer.inactive {
  transform: scale(0.72) rotate(-90deg);
}
</style>
