<script setup lang="ts">
import type { ReportLongitudinalInsights } from '~/types/api'

const props = defineProps<{ insights?: ReportLongitudinalInsights }>()
const domainLabels: Record<string, string> = { profile: '能力画像', job_market: '岗位信息', resources: '资源', plan: '计划', review: '复盘' }
const statusLabels = { fresh: '新鲜', aging: '建议刷新', stale: '已过期', outdated: '源数据已变化', unknown: '时间未知' } as const
const statusColors = { fresh: 'success', aging: 'warning', stale: 'error', outdated: 'warning', unknown: 'neutral' } as const
const completionLabel = computed(() => {
  const value = props.insights?.execution_profile.current_completion_rate
  return value == null ? '样本不足' : `${Math.round(value * 100)}%`
})
const stabilityLabel = computed(() => `${Math.round(Number(props.insights?.trends.plan_stability || 0) * 100)}%`)
</script>

<template>
  <section v-if="insights" class="calibration-journal">
    <header class="journal-heading">
      <span class="journal-number" aria-hidden="true">∞</span>
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p>LONGITUDINAL SIGNAL / 长期校准</p>
          <h2>长期校准</h2>
          <strong class="journal-thesis">让行动留下轨迹，让系统只从确认过的事实里学习</strong>
          <p class="mt-1 text-xs muted">只基于已确认复盘、行动事件和计划决定，不学习未确认草稿。</p>
        </div>
        <UBadge :label="insights.execution_profile.confidence === 'high' ? '高置信' : insights.execution_profile.confidence === 'medium' ? '中等置信' : '样本较少'" :color="insights.execution_profile.confidence === 'high' ? 'success' : 'neutral'" variant="soft" />
      </div>
    </header>

    <div class="calibration-grid">
      <section class="calibration-main">
        <div class="signal-strip">
          <div><span>执行判断</span><strong>{{ insights.execution_profile.diagnosis_label }}</strong></div>
          <div><span>当前完成率</span><strong>{{ completionLabel }}</strong></div>
          <div><span>计划稳定度</span><strong>{{ stabilityLabel }}</strong></div>
          <div><span>可信样本</span><strong>{{ insights.execution_profile.evidence_points }} 条</strong></div>
        </div>

        <div class="rhythm-note">
          <span class="rhythm-number">{{ insights.personalization.suggested_weekly_action_limit }}</span>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <strong class="text-sm">每周建议行动上限</strong>
            <UBadge :label="insights.personalization.recommendation_active ? '个性化建议已启用' : '观察模式'" :color="insights.personalization.recommendation_active ? 'primary' : 'neutral'" variant="soft" />
          </div>
          <p class="rhythm-summary">每周最多 {{ insights.personalization.suggested_weekly_action_limit }} 项 · 约 {{ insights.personalization.suggested_weekly_hours }} 小时</p>
          <p class="mt-1 text-sm muted">把精力留给可验收的少数行动。</p>
          <p class="mt-2 text-sm leading-6 muted">{{ insights.personalization.focus }}</p>
          <p class="mt-2 text-xs muted">依据：{{ insights.personalization.learned_from.confirmed_reviews }} 次确认复盘、{{ insights.personalization.learned_from.action_events }} 条行动事件、{{ insights.personalization.learned_from.decided_proposals }} 次计划决定。</p>
        </div>

        <UAlert v-for="reminder in insights.reminders" :key="`${reminder.kind}-${reminder.label}`" class="mt-3" :color="reminder.severity === 'warning' ? 'warning' : 'info'" variant="soft" :title="reminder.label" :description="reminder.days == null ? '请结合当前实际情况完成确认。' : reminder.days < 0 ? `已逾期 ${Math.abs(reminder.days)} 天` : `${reminder.days} 天内到期`" />
      </section>

      <aside class="freshness-ledger">
        <div><span>DATA FRESHNESS</span><h3>哪些判断还值得相信</h3></div>
        <div class="freshness-list">
          <article v-for="(domain, key) in insights.freshness.domains" :key="key" class="freshness-row">
            <div class="flex items-center justify-between gap-2">
              <strong class="text-xs">{{ domainLabels[String(key)] || key }}</strong>
              <UBadge :label="statusLabels[domain.status]" :color="statusColors[domain.status]" size="sm" variant="soft" />
            </div>
            <p class="mt-1 text-xs muted">{{ domain.reason }}</p>
            <p v-if="domain.status !== 'fresh'" class="mt-1 text-xs text-primary">{{ domain.refresh_action }}</p>
          </article>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.calibration-journal { position: relative; overflow: hidden; border-top: 1px solid var(--pathfy-line); border-bottom: 1px solid var(--pathfy-line); padding: clamp(1.2rem, 2.8vw, 2.1rem) clamp(.2rem, 2vw, 1rem); }.journal-heading { position: relative; min-height: 8rem; padding-right: clamp(5rem, 12vw, 10rem); }.journal-number { position: absolute; top: -2.8rem; right: .5rem; color: color-mix(in srgb, var(--pathfy-capability) 8%, transparent); font: 300 clamp(8rem, 15vw, 13rem)/1 Georgia, serif; }.journal-heading > div { position: relative; z-index: 1; }.journal-heading > div > div > p:first-child { color: var(--pathfy-capability); font: 800 .64rem/1.4 ui-monospace, monospace; letter-spacing: .11em; }.journal-heading h2 { margin-top: .35rem; font-size: .9rem; font-weight: 760; }.journal-thesis { display: block; max-width: 50rem; margin-top: .28rem; font-size: clamp(1.25rem, 2.4vw, 2rem); font-weight: 760; letter-spacing: -.035em; line-height: 1.2; }.rhythm-summary { margin-top: .55rem; font-size: 1.05rem; font-weight: 750; }
.calibration-grid { display: grid; gap: clamp(1rem, 2vw, 2rem); }.calibration-main { min-width: 0; }.signal-strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 1px solid var(--pathfy-line); border-bottom: 1px solid var(--pathfy-line); }.signal-strip > div { min-width: 0; padding: .8rem .85rem; border-left: 1px solid var(--pathfy-line); }.signal-strip > div:first-child { border-left: 0; }.signal-strip span { display: block; color: var(--ui-text-muted); font-size: .64rem; }.signal-strip strong { display: block; margin-top: .22rem; font-size: .85rem; line-height: 1.45; }
.rhythm-note { position: relative; overflow: hidden; margin-top: 1rem; border-left: 3px solid var(--pathfy-capability); background: linear-gradient(100deg, color-mix(in srgb, var(--pathfy-capability) 8%, var(--ui-bg)), transparent); padding: 1rem 1rem 1rem clamp(5.8rem, 9vw, 7.5rem); }.rhythm-number { position: absolute; top: 50%; left: 1rem; color: color-mix(in srgb, var(--pathfy-capability) 68%, var(--ui-text)); font: 760 4.6rem/1 ui-monospace, monospace; transform: translateY(-50%); }.rhythm-number::after { position: absolute; right: -.8rem; bottom: .2rem; color: var(--ui-text-muted); font-size: .55rem; content: "ACTIONS"; transform: rotate(-90deg); }.calibration-main :deep([role=alert]) { border-radius: .25rem .8rem .8rem .25rem; }
.freshness-ledger { border-left: 1px solid var(--pathfy-line); padding-left: 1.2rem; }.freshness-ledger > div:first-child span { color: var(--pathfy-route); font: 800 .62rem/1.4 ui-monospace, monospace; letter-spacing: .1em; }.freshness-ledger h3 { margin-top: .25rem; font-size: 1rem; }.freshness-list { display: grid; margin-top: .7rem; }.freshness-row { border-top: 1px dashed var(--pathfy-line); padding: .75rem .1rem; }.freshness-row:first-child { border-top-style: solid; }.freshness-row p { line-height: 1.5; }
@media (min-width: 1024px) { .calibration-grid { grid-template-columns: minmax(0, 1.35fr) minmax(280px, .65fr); } }
@media (max-width: 760px) { .journal-heading { padding-right: 0; }.journal-number { display: none; }.signal-strip { grid-template-columns: repeat(2, 1fr); }.signal-strip > div:nth-child(3) { border-left: 0; }.signal-strip > div:nth-child(n+3) { border-top: 1px solid var(--pathfy-line); }.rhythm-note { padding-left: 5rem; }.rhythm-number { font-size: 3.4rem; }.freshness-ledger { border-top: 1px solid var(--pathfy-line); border-left: 0; padding-top: 1rem; padding-left: 0; } }
</style>
