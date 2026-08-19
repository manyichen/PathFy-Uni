<script setup lang="ts">
import { VChart } from '~/utils/charts/echarts'

const props = defineProps<{ lines: any[] }>()
const colors = ['#0ea5e9', '#8b5cf6', '#14b8a6', '#f59e0b', '#ec4899']
const titleId = useId()

function points(line: any): Array<[number, number, string, string]> {
  if (!Array.isArray(line.timeline)) return []
  return [...line.timeline]
    .filter((item: any) => item?.progress !== null && item?.progress !== undefined && item?.progress !== '' && Number.isFinite(Number(item.progress)))
    .sort((a, b) => Number(a.month) - Number(b.month))
    .map((item: any) => [Number(item.month || 0), Math.max(0, Math.min(100, Number(item.progress))), item.label || '', item.kind || 'stage'])
}

const tableRows = computed(() => (props.lines || []).flatMap(line => points(line).map(point => ({ line: line.line_name || line.line_id || '发展路线', month: point[0], progress: point[1], label: point[2] || '阶段节点' }))))
const summary = computed(() => {
  const lineCount = props.lines?.length || 0
  const latest = [...tableRows.value].sort((a, b) => Number(b.month) - Number(a.month))[0]
  return `共 ${lineCount} 条发展路线${latest ? `，已确认数据更新到第 ${latest.month} 月，最新成长指数 ${latest.progress}` : '，尚无确认复盘，不绘制成长曲线'}。`
})

const option = computed(() => ({
  aria: { enabled: true, description: summary.value },
  color: colors,
  tooltip: { trigger: 'item', formatter: (params: any) => `${params.seriesName}<br/>第 ${params.value[0]} 月 · 已验证成长指数 ${Math.round(params.value[1])}${params.value[2] ? `<br/>${params.value[2]}` : ''}` },
  legend: { top: 0, type: 'scroll' },
  grid: { left: 48, right: 24, top: 48, bottom: 42 },
  xAxis: { type: 'value', min: 0, max: 12, interval: 1, name: '月份', nameLocation: 'middle', nameGap: 28 },
  yAxis: { type: 'value', min: 0, max: 100, interval: 20, name: '已验证成长指数' },
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

<template>
  <figure :aria-labelledby="titleId">
    <figcaption :id="titleId" class="chart-caption"><strong>0—12 月已验证成长轨迹</strong><span>{{ summary }}</span></figcaption>
    <VChart :option="option" autoresize style="height: 390px" />
    <details class="chart-data"><summary>查看成长轨迹数据表</summary><div class="overflow-x-auto"><table><thead><tr><th scope="col">路线</th><th scope="col">月份</th><th scope="col">成长指数</th><th scope="col">节点</th></tr></thead><tbody><tr v-for="(row,index) in tableRows" :key="`${row.line}-${row.month}-${index}`"><th scope="row">{{ row.line }}</th><td>{{ row.month }}</td><td>{{ row.progress }}</td><td>{{ row.label }}</td></tr></tbody></table></div></details>
  </figure>
</template>

<style scoped>
.chart-caption{display:grid;gap:.15rem;margin-bottom:.35rem}.chart-caption strong{font-size:.875rem}.chart-caption span{color:var(--ui-text-muted);font-size:.75rem}.chart-data{margin-top:.4rem;color:var(--ui-text-muted);font-size:.75rem}.chart-data summary{cursor:pointer}.chart-data table{width:100%;margin-top:.4rem;border-collapse:collapse}.chart-data th,.chart-data td{border:1px solid var(--ui-border);padding:.35rem;text-align:left}
</style>
