<script setup lang="ts">
import type { UserPreferences } from '~/types/settings'
import { themePreferenceItems } from '~/composables/useAppearancePreferences'
defineProps<{ form: UserPreferences }>()
</script>
<template><UCard><template #header><div><h2 class="font-semibold">外观</h2><p class="text-xs muted">本地即时预览，保存后同步到服务端</p></div></template><div class="grid gap-5"><UFormField label="主题模式"><USelect v-model="form.theme" :items="themePreferenceItems" label-key="label" value-key="value" class="w-full" /></UFormField><UFormField label="主题色"><div class="space-y-3"><div class="flex items-center justify-between text-sm"><span class="muted">色相</span><strong>{{ form.hue }}°</strong></div><div class="appearance-hue-shell"><input v-model="form.hue" aria-label="账户主题色相" type="range" min="0" max="360" step="5" class="appearance-hue-slider"></div></div></UFormField></div></UCard></template>
