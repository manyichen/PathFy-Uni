<script setup lang="ts">
import type { CapabilityScores } from '~/types/api'
const props = withDefaults(defineProps<{ scores?: Partial<CapabilityScores>; compare?: Partial<CapabilityScores>; height?: string }>(), { height: '300px' })
const hasData = computed(() => [props.scores, props.compare].some(series => series && Object.values(series).some(value => Number.isFinite(Number(value)))))
</script>

<template>
  <ChartDeferredMount v-if="hasData" :height="height"><LazyCapabilityRadar :scores="scores" :compare="compare" :height="height" /></ChartDeferredMount>
  <div v-else class="grid place-items-center text-sm muted" :style="{ minHeight: height }">暂无能力维度数据</div>
</template>
