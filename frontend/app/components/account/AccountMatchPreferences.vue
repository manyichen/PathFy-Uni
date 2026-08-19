<script setup lang="ts">
import type { UserPreferences } from '~/types/settings'
defineProps<{ form: UserPreferences; maxResults: number; error?: string }>()
</script>
<template><UCard><template #header><h2 class="font-semibold">匹配偏好</h2></template><div class="grid gap-4 sm:grid-cols-2"><UFormField label="默认目标"><USelect v-model="form.default_match_goal" :items="[{label:'稳妥匹配',value:'fit'},{label:'冲刺发展',value:'stretch'}]" class="w-full" /></UFormField><UFormField label="结果数量" :error="error"><UInput v-model.number="form.match_result_count" type="number" min="1" :max="maxResults" class="w-full" /></UFormField><USwitch v-model="form.default_refine_with_llm" label="默认启用 AI 精排" /></div></UCard></template>
