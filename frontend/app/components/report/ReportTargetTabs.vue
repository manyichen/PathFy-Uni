<script setup lang="ts">
import { nextTick } from 'vue'
import type { ReportTarget } from '~/types/api'
import { reportTargetKey } from '~/composables/report/useReportWorkspace'
const props = defineProps<{ targets: ReportTarget[]; activeJobId: string; primaryJobId: string }>()
const emit = defineEmits<{ select: [jobId: string] }>()
function title(item: ReportTarget) { return item.display_title || item.title || item.job_id || item.id || '目标岗位' }
function topGap(item: ReportTarget) { const values = Object.values(item.match_preview?.dimension_gaps || {}).map(Number).filter(Number.isFinite); return values.length ? Math.round(Math.max(...values)) : 0 }
function move(event: KeyboardEvent, index: number) {
  const direction = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
  if (!direction) return
  event.preventDefault()
  const next = (index + direction + props.targets.length) % props.targets.length
  const target = props.targets[next]
  if (target) emit('select', reportTargetKey(target))
  nextTick(() => (event.currentTarget as HTMLElement)?.parentElement?.querySelectorAll<HTMLElement>('[role="tab"]')[next]?.focus())
}
</script>

<template>
  <section v-if="targets.length" aria-label="报告目标岗位">
    <div class="section-heading"><h2>目标岗位</h2><p>选择一个岗位查看对应行动和证据。</p></div>
    <div class="target-tabs" role="tablist" aria-label="目标岗位" :style="{ '--target-count': Math.max(1, targets.length) }">
      <div v-for="(item,index) in targets" :key="reportTargetKey(item)" class="target-tab-shell" :class="{ active: reportTargetKey(item) === activeJobId, primary: reportTargetKey(item) === primaryJobId }">
        <button type="button" role="tab" class="target-tab-main" :aria-selected="reportTargetKey(item) === activeJobId" :tabindex="reportTargetKey(item) === activeJobId ? 0 : -1" @click="emit('select', reportTargetKey(item))" @keydown="move($event,index)">
          <span>{{ title(item) }}</span><small>{{ item.company || '岗位方向' }}</small><span class="target-signal"><b>{{ Math.round(item.match_preview?.match_score || 0) }}</b> 匹配 · <b>{{ topGap(item) }}</b> 最大差距</span>
        </button>
        <span v-if="reportTargetKey(item) === primaryJobId" class="primary-label"><UIcon name="i-lucide-star" />主目标</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.section-heading { margin-bottom: .75rem; }.section-heading h2{font-size:1.2rem;font-weight:700}.section-heading p{margin-top:.2rem;color:var(--ui-text-muted);font-size:.875rem}
.target-tabs{display:grid;grid-template-columns:repeat(var(--target-count,5),minmax(0,1fr));gap:0;overflow:hidden;border-bottom:1px solid var(--ui-border)}.target-tab-shell{position:relative;min-width:0;border-bottom:2px solid transparent;transition:160ms}.target-tab-shell:hover{background:color-mix(in srgb,var(--pathfy-route) 4%,transparent)}.target-tab-shell.active{border-bottom-color:var(--pathfy-route);background:color-mix(in srgb,var(--pathfy-route) 6%,transparent)}.target-tab-main{display:block;width:100%;min-width:0;padding:.7rem .85rem .55rem;text-align:left}.target-tab-shell.primary .target-tab-main{padding-right:4.5rem}.target-tab-main span,.target-tab-main small{display:block;min-width:0}.target-tab-main>span:first-child{display:-webkit-box;overflow:hidden;min-height:2.6em;font-weight:650;line-height:1.3;-webkit-box-orient:vertical;-webkit-line-clamp:2}.target-tab-main small{margin-top:.12rem;overflow:hidden;color:var(--ui-text-muted);font-size:.7rem;text-overflow:ellipsis;white-space:nowrap}.target-tabs .target-signal{margin-top:.4rem;color:var(--ui-text-muted);font-size:.66rem;font-weight:500;white-space:nowrap}.target-tabs .target-signal b{color:var(--pathfy-route)}.primary-label{display:flex;align-items:center;gap:.25rem;position:absolute;right:.55rem;top:.55rem;color:var(--ui-primary);font-size:.62rem;font-weight:700}.primary-label svg{width:.72rem;height:.72rem}@media(max-width:900px){.target-tabs{display:flex;overflow-x:auto}.target-tab-shell{flex:0 0 min(17rem,78vw);min-width:11.5rem}}
</style>
