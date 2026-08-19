<script setup lang="ts">
import { computed } from 'vue'
import type { CareerReport, DevelopmentAdjustment } from '~/types/api'
type BadgeColor = 'neutral' | 'success' | 'warning' | 'error' | 'primary'
const props=defineProps<{ report:CareerReport; adjustments:DevelopmentAdjustment[] }>()
const latest=computed(()=>props.adjustments.at(-1))
const summary=computed(()=>props.report.evaluation?.latest_review?.adjustment)
const mode=computed(()=>latest.value?.replan_mode || summary.value?.replan_mode || props.report.evaluation?.last_replan_mode || 'initial')
const meta=computed<{label:string;desc:string;color:BadgeColor}>(()=>({initial:{label:'起步计划',desc:'尚未触发自动调整，当前任务来自报告初始规划。',color:'neutral' as const},continue:{label:'继续执行',desc:'本月指标整体达标，下一月延续当前节奏。',color:'success' as const},light:{label:'轻度调整',desc:'部分指标未达标，下一月已提高相关任务优先级。',color:'warning' as const},strong:{label:'强化调整',desc:'连续未达标，下一月已增加补救行动并收紧目标。',color:'error' as const}}[mode.value] || {label:'计划更新',desc:'系统已根据复盘更新下一月安排。',color:'primary' as const}))
const triggered=computed(()=>Boolean(summary.value?.auto_adjustment?.triggered || (mode.value!=='initial'&&mode.value!=='continue')))
const nextAction=computed(()=>latest.value?.execution_hints?.[0] || props.report.evaluation?.latest_adjustment_actions?.[0] || latest.value?.label)
</script>

<template>
  <section class="adjustment-ribbon" :data-mode="mode">
    <header>
      <div class="adjustment-mark" aria-hidden="true"><span>TURN</span><i /></div>
      <div><small>PLAN SIGNAL / 计划转向信号</small><h3>为什么改变，下一步改变什么</h3><p>说明计划是否调整、触发原因以及接下来优先做什么。</p></div>
      <UBadge :label="meta.label" :color="meta.color" variant="soft" />
    </header>
    <div class="explain-line">
      <div><span>自动调整</span><strong>{{ triggered?'已触发':'未触发' }}</strong><p>{{ meta.desc }}</p></div>
      <div><span>触发指标</span><strong>{{ latest?.failed_rows?.length || summary?.failed_codes?.length || 0 }} 项</strong><p>{{ (latest?.failed_rows || []).map(row=>row.label || row.code).filter(Boolean).join('、') || (summary?.failed_codes || []).join('、') || '暂无未达标指标' }}</p></div>
      <div><span>关键变化</span><strong>{{ latest?.plan_items?.length || 0 }} 组任务</strong><p>{{ latest?.label || summary?.auto_adjustment?.reason || '保持原阶段计划' }}</p></div>
      <div class="priority"><span>NEXT / 下一月最优先</span><strong>{{ nextAction || '完成当前下月任务并留下可验证证据' }}</strong></div>
    </div>
  </section>
</template>
<style scoped>
.adjustment-ribbon { --turn-color: var(--pathfy-route); overflow: hidden; border-top: 1px solid var(--pathfy-line); border-bottom: 1px solid var(--pathfy-line); background: linear-gradient(90deg, color-mix(in srgb, var(--turn-color) 5%, transparent), transparent 45%); }
.adjustment-ribbon[data-mode=strong] { --turn-color: var(--pathfy-risk); }.adjustment-ribbon[data-mode=light] { --turn-color: var(--pathfy-gap); }.adjustment-ribbon[data-mode=continue] { --turn-color: var(--pathfy-evidence); }
.adjustment-ribbon > header { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 1rem; align-items: center; padding: 1rem .35rem; }.adjustment-mark { display: grid; align-self: stretch; justify-items: center; grid-template-rows: auto 1fr; gap: .35rem; color: var(--turn-color); }.adjustment-mark span { font: 800 .58rem/1 ui-monospace, monospace; letter-spacing: .08em; }.adjustment-mark i { width: 1px; min-height: 2.8rem; background: color-mix(in srgb, var(--turn-color) 55%, transparent); }.adjustment-ribbon header small { color: var(--turn-color); font: 800 .62rem/1.4 ui-monospace, monospace; letter-spacing: .1em; }.adjustment-ribbon h3 { margin-top: .25rem; font-size: 1.05rem; font-weight: 760; }.adjustment-ribbon header p { margin-top: .2rem; color: var(--ui-text-muted); font-size: .7rem; }
.explain-line { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) minmax(15rem, 1.2fr); border-top: 1px dashed var(--pathfy-line); }.explain-line > div { min-width: 0; padding: .9rem 1rem; border-left: 1px solid var(--pathfy-line); }.explain-line > div:first-child { border-left: 0; }.explain-line span { display: block; color: var(--ui-text-muted); font-size: .64rem; }.explain-line strong { display: block; margin-top: .22rem; font-size: .88rem; }.explain-line p { margin-top: .25rem; color: var(--ui-text-muted); font-size: .68rem; line-height: 1.5; }.priority { position: relative; background: color-mix(in srgb, var(--turn-color) 7%, var(--ui-bg)); }.priority::before { position: absolute; top: 0; bottom: 0; left: 0; width: 2px; background: var(--turn-color); content: ""; }.priority span { color: var(--turn-color); font-family: ui-monospace, monospace; font-weight: 750; letter-spacing: .08em; }.priority strong { line-height: 1.5; }
@media (max-width: 900px) { .explain-line { grid-template-columns: repeat(3, 1fr); }.priority { grid-column: 1 / -1; } }
@media (max-width: 620px) { .adjustment-ribbon > header { grid-template-columns: auto 1fr; }.adjustment-ribbon > header > :last-child { grid-column: 2; }.explain-line { grid-template-columns: 1fr; }.priority { grid-column: auto; }.explain-line > div { border-top: 1px dashed var(--pathfy-line); border-left: 0; }.explain-line > div:first-child { border-top: 0; } }
</style>
