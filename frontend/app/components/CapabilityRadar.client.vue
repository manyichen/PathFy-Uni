<script setup lang="ts">
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import type { CapabilityScores } from '~/types/api'

use([RadarChart, CanvasRenderer, LegendComponent, TooltipComponent])
const props = withDefaults(defineProps<{ scores?: Partial<CapabilityScores>; compare?: Partial<CapabilityScores>; height?: string }>(), { height: '300px' })
const dimensions: Array<[keyof CapabilityScores, string]> = [['cap_req_theory','理论'],['cap_req_cross','交叉'],['cap_req_practice','实践'],['cap_req_digital','数字'],['cap_req_innovation','创新'],['cap_req_teamwork','协作'],['cap_req_social','社会'],['cap_req_growth','成长']]
const option = computed(() => ({
  tooltip: {}, legend: props.compare ? { data: ['能力画像', '岗位要求'] } : undefined,
  radar: { indicator: dimensions.map(([, name]) => ({ name, max: 100 })), radius: '68%' },
  series: [{ type: 'radar', data: [
    { name: '能力画像', value: dimensions.map(([key]) => Number(props.scores?.[key] || 0)), areaStyle: { opacity: .18 } },
    ...(props.compare ? [{ name: '岗位要求', value: dimensions.map(([key]) => Number(props.compare?.[key] || 0)), areaStyle: { opacity: .1 } }] : [])
  ] }]
}))
</script>
<template><VChart :option="option" autoresize :style="{ height }" /></template>
