<script setup lang="ts">
import type { UserPreferences } from '~/types/settings'
defineProps<{ form: UserPreferences; learningMax: number; competitionMax: number; learningError?: string; competitionError?: string }>()
</script>
<template><UCard><template #header><h2 class="font-semibold">推荐数量</h2></template><div class="grid gap-4 sm:grid-cols-2"><UFormField label="每个目标的学习资源" :error="learningError"><UInput v-model.number="form.learning_resource_count" type="number" min="1" :max="learningMax" class="w-full" /></UFormField><UFormField label="每个目标的竞赛" :error="competitionError"><UInput v-model.number="form.competition_count" type="number" min="0" :max="competitionMax" class="w-full" /></UFormField></div></UCard></template>
