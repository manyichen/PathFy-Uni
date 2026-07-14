<script setup lang="ts">
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([LineChart, CanvasRenderer, GridComponent, LegendComponent, TooltipComponent])
const props = defineProps<{ lines: any[] }>()
const colors = ['#0ea5e9', '#8b5cf6', '#14b8a6', '#f59e0b', '#ec4899']

function points(line: any) {
  if (line.timeline?.length) return [...line.timeline].sort((a, b) => Number(a.month) - Number(b.month)).map((item: any) => [Number(item.month || 0), Number(item.progress || 0), item.label || '', item.kind || 'stage'])
  const nodes = line.nodes || []
  return nodes.map((item: any, index: number) => [Math.round(index * 12 / Math.max(1, nodes.length - 1)), Math.round(index * 100 / Math.max(1, nodes.length - 1)), item.label || '', item.stage || 'stage'])
}

const option = computed(() => ({
  color: colors,
  tooltip: { trigger: 'item', formatter: (params: any) => `${params.seriesName}<br/>第 ${params.value[0]} 月 · 进步度 ${Math.round(params.value[1])}%${params.value[2] ? `<br/>${params.value[2]}` : ''}` },
  legend: { top: 0, type: 'scroll' },
  grid: { left: 48, right: 24, top: 48, bottom: 42 },
  xAxis: { type: 'value', min: 0, max: 12, interval: 1, name: '月份', nameLocation: 'middle', nameGap: 28 },
  yAxis: { type: 'value', min: 0, max: 100, interval: 20, name: '进步度' },
  series: (props.lines || []).map(line => ({
    name: line.line_name || line.line_id,
    type: 'line',
    smooth: .22,
    symbolSize: 10,
    showSymbol: true,
    data: points(line),
    lineStyle: { width: 3 },
    areaStyle: { opacity: .06 }
  }))
}))
</script>

<template><VChart :option="option" autoresize style="height: 390px" /></template>
