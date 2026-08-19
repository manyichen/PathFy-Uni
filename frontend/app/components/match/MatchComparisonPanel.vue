<script setup lang="ts">
import MatchTensionField from '~/components/visualization/match/MatchTensionField.vue'
import type { CapabilityScorePatch } from '~/types/capability'
import type { JobCard } from '~/types/job'

defineProps<{ studentScores: CapabilityScorePatch; job?: JobCard }>()
defineEmits<{ detail: [job: JobCard] }>()
</script>

<template>
  <UCard class="comparison-panel">
    <template #header><div><h2 class="font-semibold">八维能力对比</h2><p class="text-xs muted">画像能力与岗位真实要求</p></div></template>
    <template v-if="job">
      <div class="mb-2"><h3 class="font-medium">{{ job.title }}</h3><p class="text-sm muted">{{ job.company }} · {{ job.location }}</p></div>
      <MatchTensionField :student-scores="studentScores" :job="job" />
      <UButton block variant="soft" trailing-icon="i-lucide-arrow-up-right" @click="$emit('detail', job)">查看完整岗位详情</UButton>
    </template>
    <div v-else class="grid min-h-80 place-items-center text-center"><div><UIcon name="i-lucide-radar" class="mx-auto size-10 text-primary" /><p class="mt-3 font-medium">选择一个岗位进行对比</p><p class="mt-1 text-sm muted">这里将展示画像与岗位八维要求的张力雷达</p></div></div>
  </UCard>
</template>
