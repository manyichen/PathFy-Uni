<script setup lang="ts">
import { computed } from 'vue'
import type { CapabilityDimension, ReportPlan, ReportTarget } from '~/types/api'

const props = defineProps<{ target?: ReportTarget; plan?: ReportPlan }>()
const labels: Record<CapabilityDimension, string> = { cap_req_theory:'理论基础',cap_req_cross:'交叉能力',cap_req_practice:'实践技能',cap_req_digital:'数字素养',cap_req_innovation:'创新能力',cap_req_teamwork:'团队协作',cap_req_social:'社会连接',cap_req_growth:'成长韧性' }

function score(source: unknown, key: string) {
  const value = Number((source as Record<string, unknown> | undefined)?.[key])
  return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : undefined
}

const rows = computed(() => {
  const preview = props.target?.match_preview as Record<string, unknown> | undefined
  const student = preview?.student_scores
  const requirement = preview?.job_requirement_scores
  const rawDeltas = preview?.dimension_raw_delta
  const softGaps = preview?.dimension_gaps || props.plan?.dimension_gaps
  const keys = new Set([
    ...Object.keys((student as Record<string, unknown>) || {}),
    ...Object.keys((requirement as Record<string, unknown>) || {}),
    ...Object.keys((softGaps as Record<string, unknown>) || {})
  ])
  return [...keys].map(key => {
    const current = score(student, key)
    const required = score(requirement, key)
    const measuredRaw = Number((rawDeltas as Record<string, unknown> | undefined)?.[key])
    const raw = Number.isFinite(measuredRaw) ? measuredRaw : current !== undefined && required !== undefined ? required - current : undefined
    const soft = score(softGaps, key) || 0
    const status = soft > 0 ? 'gap' : Number(raw || 0) > 0 ? 'verify' : 'ready'
    return { key, label: labels[key as CapabilityDimension] || key, current, required, raw, soft, status }
  }).filter(row => row.current !== undefined || row.required !== undefined).sort((a, b) => Number(b.raw || 0) - Number(a.raw || 0))
})

function difference(row: typeof rows.value[number]) {
  if (row.raw === undefined) return '差值待补充'
  if (row.status === 'gap') return `硬缺口 ${Math.round(row.soft)} 分`
  if (row.status === 'verify') return `低于要求 ${Math.round(row.raw)} 分 · 容差内`
  if (row.raw < 0) return `高于要求 ${Math.abs(Math.round(row.raw))} 分`
  return '达到当前标尺'
}
</script>

<template>
  <section class="capability-compare" aria-labelledby="capability-compare-title">
    <header><div><span>能力对照</span><h3 id="capability-compare-title">能力差距与岗位要求</h3><p>同时显示原始差值和软缺口，避免“0 缺口”等同于“已经达标”。</p></div><div class="legend"><span class="current">当前</span><span class="required">要求</span></div></header>
    <div v-if="rows.length" class="compare-rows">
      <article v-for="row in rows" :key="row.key" :data-state="row.status">
        <div class="row-title"><strong>{{ row.label }}</strong><span>{{ difference(row) }}</span></div>
        <div class="score-line" role="img" :aria-label="`${row.label}，当前 ${row.current ?? '未知'}，要求 ${row.required ?? '未知'}`">
          <span class="track" />
          <span v-if="row.current !== undefined" class="marker current" :style="{ left: `${row.current}%` }"><b>{{ Math.round(row.current) }}</b></span>
          <span v-if="row.required !== undefined" class="marker required" :style="{ left: `${row.required}%` }"><b>{{ Math.round(row.required) }}</b></span>
        </div>
      </article>
    </div>
    <UEmpty v-else title="暂无可对照的能力数据" description="需要同时具备能力画像或岗位要求快照。" icon="i-lucide-gauge" />
    <footer><UIcon name="i-lucide-info" /><span>软缺口会扣除匹配策略允许的容差；原始差值仍会进入“待验证”结论，并影响补证行动。</span></footer>
  </section>
</template>

<style scoped>
.capability-compare{border:1px solid color-mix(in srgb,var(--pathfy-evidence) 22%,var(--pathfy-line));border-radius:1.15rem;background:linear-gradient(145deg,color-mix(in srgb,var(--pathfy-evidence) 7%,var(--pathfy-surface-panel)),var(--pathfy-surface-panel) 42%);padding:1.25rem}.capability-compare>header{display:flex;align-items:start;justify-content:space-between;gap:1rem}.capability-compare header>div:first-child>span{color:var(--pathfy-evidence);font-size:.73rem;font-weight:850;letter-spacing:.1em}.capability-compare h3{margin-top:.28rem;font-size:1.15rem;font-weight:760}.capability-compare header p{margin-top:.3rem;color:var(--ui-text-muted);font-size:.8rem;line-height:1.6}.legend{display:flex;flex-shrink:0;gap:.75rem;color:var(--ui-text-muted);font-size:.72rem}.legend span{display:flex;align-items:center;gap:.3rem}.legend span::before{width:.55rem;height:.55rem;border-radius:999px;background:var(--dot);content:""}.legend .current{--dot:#0ea5e9}.legend .required{--dot:#8b5cf6}.compare-rows{display:grid;gap:.7rem;margin-top:1rem}.compare-rows article{border:1px solid color-mix(in srgb,var(--state-color) 14%,var(--pathfy-line));border-left:4px solid var(--state-color);border-radius:.75rem;background:var(--ui-bg);padding:.75rem .85rem;--state-color:var(--pathfy-success)}.compare-rows article[data-state=verify]{--state-color:var(--pathfy-gap)}.compare-rows article[data-state=gap]{--state-color:var(--pathfy-risk)}.row-title{display:flex;align-items:center;justify-content:space-between;gap:.7rem}.row-title strong{font-size:.84rem}.row-title span{color:var(--state-color);font-size:.72rem;font-weight:700;text-align:right}.score-line{position:relative;height:1.8rem;margin:.7rem .6rem .1rem}.track{position:absolute;top:.85rem;left:0;width:100%;height:3px;border-radius:99px;background:var(--pathfy-line)}.marker{position:absolute;top:.5rem;width:.8rem;height:.8rem;transform:translateX(-50%);border:2px solid var(--ui-bg);border-radius:999px;background:var(--marker-color);box-shadow:0 0 0 3px color-mix(in srgb,var(--marker-color) 12%,transparent)}.marker.current{--marker-color:#0ea5e9}.marker.required{--marker-color:#8b5cf6}.marker b{position:absolute;top:-.55rem;left:50%;transform:translate(-50%,-100%);color:var(--marker-color);font-size:.66rem;font-weight:750}.capability-compare footer{display:flex;gap:.5rem;margin-top:1rem;border-top:1px solid var(--pathfy-line);padding-top:.8rem;color:var(--ui-text-muted);font-size:.72rem;line-height:1.6}@media(max-width:520px){.capability-compare>header{flex-direction:column}.legend{align-self:flex-end}.row-title{align-items:flex-start;flex-direction:column;gap:.2rem}}
</style>
