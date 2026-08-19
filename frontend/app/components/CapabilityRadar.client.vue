<script setup lang="ts">
import type { CapabilityScores } from '~/types/api'
import { capabilityDimensions, type CapabilityDimension } from '~/types/capability'
import { VChart } from '~/utils/charts/echarts'

const props = withDefaults(defineProps<{ scores?: Partial<CapabilityScores>; compare?: Partial<CapabilityScores>; height?: string }>(), { height: '300px' })
const shortLabels: Record<CapabilityDimension, string> = {
  cap_req_theory: '理论',
  cap_req_cross: '交叉',
  cap_req_practice: '实践',
  cap_req_digital: '数字',
  cap_req_innovation: '创新',
  cap_req_teamwork: '协作',
  cap_req_social: '社会',
  cap_req_growth: '成长'
}
const dimensions: Array<[CapabilityDimension, string]> = capabilityDimensions.map(key => [key, shortLabels[key]])
const titleId = useId()
const rows = computed(() => dimensions.map(([key, label]) => ({ key, label, score: Math.round(Number(props.scores?.[key] || 0)), compare: props.compare ? Math.round(Number(props.compare[key] || 0)) : undefined })))
const summary = computed(() => {
  const strongest = [...rows.value].sort((a, b) => b.score - a.score)[0]
  const largestGap = props.compare ? [...rows.value].sort((a, b) => Number(b.compare) - b.score - (Number(a.compare) - a.score))[0] : undefined
  return `能力画像共 8 个维度${strongest ? `，最高为${strongest.label} ${strongest.score} 分` : ''}${largestGap && Number(largestGap.compare) > largestGap.score ? `；与岗位相比最大差距为${largestGap.label} ${Number(largestGap.compare) - largestGap.score} 分` : ''}。`
})
const option = computed(() => ({
  aria: { enabled: true, description: summary.value },
  tooltip: {}, legend: props.compare ? { data: ['能力画像', '岗位要求'] } : undefined,
  radar: {
    indicator: dimensions.map(([, name]) => ({ name, max: 100 })),
    radius: '68%',
    startAngle: 90,
    clockwise: false
  },
  series: [{ type: 'radar', data: [
    { name: '能力画像', value: dimensions.map(([key]) => Number(props.scores?.[key] || 0)), areaStyle: { opacity: .18 } },
    ...(props.compare ? [{ name: '岗位要求', value: dimensions.map(([key]) => Number(props.compare?.[key] || 0)), areaStyle: { opacity: .1 } }] : [])
  ] }]
}))
</script>
<template>
  <figure class="chart-figure" :aria-labelledby="titleId">
    <figcaption :id="titleId" class="chart-caption"><strong>八维能力雷达图</strong><span>{{ summary }}</span></figcaption>
    <VChart :option="option" autoresize :style="{ height }" />
    <details class="chart-data"><summary>查看雷达图数据表</summary><div class="overflow-x-auto"><table><thead><tr><th scope="col">维度</th><th scope="col">能力画像</th><th v-if="compare" scope="col">岗位要求</th></tr></thead><tbody><tr v-for="row in rows" :key="row.key"><th scope="row">{{ row.label }}</th><td>{{ row.score }}</td><td v-if="compare">{{ row.compare }}</td></tr></tbody></table></div></details>
  </figure>
</template>

<style scoped>
.chart-caption{display:grid;gap:.15rem;margin-bottom:.35rem}.chart-caption strong{font-size:.875rem}.chart-caption span{color:var(--ui-text-muted);font-size:.75rem}.chart-data{margin-top:.4rem;color:var(--ui-text-muted);font-size:.75rem}.chart-data summary{cursor:pointer}.chart-data table{width:100%;margin-top:.4rem;border-collapse:collapse}.chart-data th,.chart-data td{border:1px solid var(--ui-border);padding:.35rem;text-align:left}
</style>
