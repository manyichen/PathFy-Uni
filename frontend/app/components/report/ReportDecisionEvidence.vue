<script setup lang="ts">
import { computed } from 'vue'
import type { ReportDecisionClaim, ReportTargetDecision } from '~/types/api'

const props = defineProps<{ decision?: ReportTargetDecision }>()
const claims = computed(() => props.decision?.claims || [])
const priorityClaims = computed(() => claims.value.filter(item => item.kind === 'gap' || item.kind === 'risk').slice(0, 4))
const strengthClaims = computed(() => claims.value.filter(item => item.kind === 'strength' || item.kind === 'opportunity').slice(0, 4))
const freshness = computed(() => Object.entries(props.decision?.freshness || {}))
const unlinkedActions = computed(() => props.decision?.evidence_metrics?.unlinked_action_count || 0)
const gradeTone: Record<string, 'success' | 'primary' | 'warning' | 'neutral'> = { A: 'success', B: 'primary', C: 'warning', D: 'neutral' }
const kindLabel: Record<ReportDecisionClaim['kind'], string> = { gap: '硬缺口', risk: '待验证', strength: '已见优势', opportunity: '机会' }

function priority(claim: ReportDecisionClaim) {
  return claim.priority === undefined ? '' : `优先级 ${Math.round(claim.priority)}`
}

function displayTime(value?: string) {
  if (!value) return '时间待补充'
  const compact = value.match(/^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})$/)
  if (compact) return `${compact[1]}-${compact[2]}-${compact[3]} ${compact[4]}:${compact[5]}`
  return value.replace('T', ' ').replace(/\.\d+Z?$/, '').replace(/Z$/, '')
}
</script>

<template>
  <section class="decision-evidence" aria-labelledby="decision-evidence-title">
    <div class="section-heading">
      <div><span>判断明细</span><h2 id="decision-evidence-title">哪些结论可用，哪些仍需验证</h2><p>“容差内”只代表不是硬缺口，不代表能力已经达到岗位要求。</p></div>
      <UBadge v-if="decision" :label="decision.role_label" variant="soft" />
    </div>

    <div v-if="decision" class="judgement-card">
      <div class="judgement-main"><span>系统建议</span><strong>{{ decision.judgement.recommendation }}</strong><p>{{ decision.display_title }}</p></div>
      <div class="score-block"><strong>{{ Math.round(decision.judgement.match_score) }}</strong><span>模型匹配分</span></div>
      <div class="judgement-note"><UIcon name="i-lucide-info" /><p>该分数用于排序，不是录用概率。最终判断还应结合真实作品、面试反馈和最新招聘信息。</p></div>
    </div>

    <div v-if="decision?.judgement.data_gaps.length || unlinkedActions" class="quality-notices">
      <UAlert v-if="decision?.judgement.data_gaps.length" color="warning" variant="soft" title="决策信息仍不完整" :description="decision.judgement.data_gaps.join('；')" />
      <UAlert v-if="unlinkedActions" color="warning" variant="soft" title="行动与依据存在断链" :description="`${unlinkedActions} 项行动尚未关联具体结论或事实，完成后请在复盘中补充成果。`" />
    </div>

    <div class="claim-layout">
      <section class="claim-column risk-column">
        <div class="column-heading"><span class="column-index">01</span><div><h3>需要补齐或验证</h3><p>优先处理真实差值和证据不足，而不是只看软缺口。</p></div></div>
        <details v-for="claim in priorityClaims" :key="claim.id" class="claim-card priority" :open="claim === priorityClaims[0]">
          <summary><span><span class="kind-label">{{ kindLabel[claim.kind] }}</span><strong>{{ claim.title }}</strong><small>{{ claim.summary }}</small></span><span class="claim-badges"><UBadge :label="`${claim.quality.evidence_grade} 级依据`" :color="gradeTone[claim.quality.evidence_grade]" size="sm" /><em>{{ priority(claim) }}</em></span></summary>
          <p class="impact">{{ claim.impact }}</p>
          <div class="facts"><div v-for="fact in claim.facts" :key="fact.id"><span>{{ fact.label }}</span><strong>{{ fact.value ?? '—' }}{{ fact.unit }}</strong><small>{{ fact.source_label }} · {{ displayTime(fact.observed_at) }}</small></div></div>
        </details>
        <p v-if="!priorityClaims.length" class="empty-copy"><UIcon name="i-lucide-circle-check" />当前没有测得硬缺口或容差内风险；仍建议用真实成果验证画像分数。</p>
      </section>

      <section class="claim-column strength-column">
        <div class="column-heading"><span class="column-index">02</span><div><h3>可复用的优势</h3><p>这些优势可作为行动起点，但不能替代作品和反馈。</p></div></div>
        <details v-for="claim in strengthClaims" :key="claim.id" class="claim-card strength">
          <summary><span><span class="kind-label">{{ kindLabel[claim.kind] }}</span><strong>{{ claim.title }}</strong><small>{{ claim.summary }}</small></span><UBadge :label="`${claim.quality.evidence_grade} 级依据`" :color="gradeTone[claim.quality.evidence_grade]" size="sm" /></summary>
          <p class="impact">{{ claim.impact }}</p>
          <div class="facts"><div v-for="fact in claim.facts" :key="fact.id"><span>{{ fact.label }}</span><strong>{{ fact.value ?? '—' }}{{ fact.unit }}</strong><small>{{ fact.source_label }} · {{ displayTime(fact.observed_at) }}</small></div></div>
        </details>
        <p v-if="!strengthClaims.length" class="empty-copy">当前证据不足以确认明显优势。</p>
      </section>
    </div>

    <section v-if="freshness.length" class="freshness-section" aria-label="数据新鲜度">
      <div class="freshness-heading"><strong>数据口径与时间</strong><span>旧数据会降低决策可信度，建议在简历、岗位或复盘变化后刷新。</span></div>
      <div class="freshness-strip"><div v-for="([key, item]) in freshness" :key="key"><span>{{ item.source_label }}</span><strong>{{ displayTime(item.as_of) }}</strong><UBadge :label="`${item.evidence_grade} 级`" size="sm" color="neutral" variant="soft" /></div></div>
    </section>
  </section>
</template>

<style scoped>
.decision-evidence{border:1px solid color-mix(in srgb,var(--pathfy-route) 18%,var(--pathfy-line));border-radius:1.25rem;background:linear-gradient(150deg,color-mix(in srgb,var(--pathfy-route) 4%,var(--pathfy-surface-panel)),var(--pathfy-surface-panel) 38%);padding:1.4rem;box-shadow:0 24px 52px -46px rgb(15 23 42 / .72)}.section-heading{display:flex;align-items:end;justify-content:space-between;gap:1rem;margin-bottom:1.1rem}.section-heading>div>span{color:var(--pathfy-route);font-size:.75rem;font-weight:850;letter-spacing:.1em}.section-heading h2{margin-top:.28rem;font-size:clamp(1.25rem,1.8vw,1.6rem);font-weight:770;letter-spacing:-.02em}.section-heading p{margin-top:.32rem;color:var(--ui-text-muted);font-size:.84rem;line-height:1.65}.judgement-card{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(16rem,.7fr);gap:1.2rem;align-items:center;border:1px solid color-mix(in srgb,var(--pathfy-evidence) 30%,var(--pathfy-line));border-radius:1rem;background:radial-gradient(circle at 70% 0,color-mix(in srgb,var(--pathfy-route) 12%,transparent),transparent 12rem),linear-gradient(110deg,color-mix(in srgb,var(--pathfy-evidence) 11%,var(--ui-bg)),var(--ui-bg));padding:1.15rem 1.25rem}.judgement-main span,.score-block span{color:var(--ui-text-muted);font-size:.75rem}.judgement-main strong{display:block;margin-top:.22rem;font-size:1.18rem;line-height:1.4}.judgement-main p{margin-top:.25rem;color:var(--ui-text-muted);font-size:.8rem}.score-block{display:grid;min-width:6rem;text-align:center}.score-block strong{color:var(--pathfy-evidence);font-size:2.25rem;line-height:1;letter-spacing:-.05em}.score-block span{margin-top:.25rem}.judgement-note{display:flex;gap:.6rem;border-left:1px solid var(--pathfy-line);padding-left:1.1rem;color:var(--ui-text-muted)}.judgement-note svg{flex:0 0 auto;color:var(--pathfy-route)}.judgement-note p{font-size:.78rem;line-height:1.7}.quality-notices{display:grid;gap:.65rem;margin-top:.9rem}.claim-layout{display:grid;gap:1.1rem;margin-top:1.2rem}.claim-column{border-radius:1rem;padding:1rem}.risk-column{background:linear-gradient(145deg,color-mix(in srgb,var(--pathfy-gap) 7%,var(--ui-bg)),var(--ui-bg) 50%)}.strength-column{background:linear-gradient(145deg,color-mix(in srgb,var(--pathfy-success) 7%,var(--ui-bg)),var(--ui-bg) 50%)}.column-heading{display:flex;gap:.75rem;align-items:flex-start;margin-bottom:.75rem}.column-index{display:grid;width:2rem;height:2rem;flex:0 0 auto;place-items:center;border-radius:.6rem;background:color-mix(in srgb,var(--column-tone,var(--pathfy-evidence)) 13%,var(--ui-bg));color:var(--column-tone,var(--pathfy-evidence));font-size:.72rem;font-weight:850}.risk-column .column-heading{--column-tone:var(--pathfy-gap)}.strength-column .column-heading{--column-tone:var(--pathfy-success)}.column-heading h3{font-size:1rem;font-weight:750}.column-heading p{margin-top:.18rem;color:var(--ui-text-muted);font-size:.75rem;line-height:1.55}.claim-card{border:1px solid color-mix(in srgb,var(--claim-tone) 18%,var(--pathfy-line));border-radius:.9rem;background:color-mix(in srgb,var(--claim-tone) 3%,var(--ui-bg));padding:.9rem 1rem;--claim-tone:var(--pathfy-evidence);transition:transform 160ms ease,box-shadow 160ms ease}.claim-card:hover{transform:translateY(-1px);box-shadow:0 16px 32px -28px var(--claim-tone)}.claim-card+.claim-card{margin-top:.65rem}.claim-card.priority{--claim-tone:var(--pathfy-gap);border-left:4px solid var(--claim-tone)}.claim-card.strength{--claim-tone:var(--pathfy-success);border-left:4px solid var(--claim-tone)}.claim-card summary{display:flex;cursor:pointer;align-items:start;justify-content:space-between;gap:.9rem;list-style:none}.claim-card summary::-webkit-details-marker{display:none}.claim-card summary>span:first-child{min-width:0}.claim-card strong,.claim-card small{display:block}.claim-card summary strong{font-size:.9rem;line-height:1.5}.kind-label{display:inline-block;margin-bottom:.35rem;border-radius:999px;background:color-mix(in srgb,var(--claim-tone) 11%,var(--ui-bg));padding:.2rem .48rem;color:var(--claim-tone);font-size:.68rem;font-weight:750}.claim-card small{margin-top:.3rem;color:var(--ui-text-muted);font-size:.78rem;line-height:1.6}.claim-badges{display:flex;flex-shrink:0;align-items:center;gap:.4rem}.claim-badges em{color:var(--ui-text-muted);font-size:.7rem;font-style:normal}.impact{margin-top:.85rem;border-left:3px solid var(--claim-tone);padding:.15rem 0 .15rem .75rem;color:var(--ui-text-muted);font-size:.82rem;line-height:1.7}.facts{display:grid;gap:.5rem;margin-top:.8rem}.facts>div{display:grid;grid-template-columns:minmax(6rem,.7fr) auto minmax(9rem,1fr);gap:.7rem;align-items:center;border:1px solid color-mix(in srgb,var(--claim-tone) 10%,var(--pathfy-line));border-radius:.65rem;background:var(--ui-bg-elevated);padding:.6rem .7rem;font-size:.78rem}.facts>div>span{color:var(--ui-text-muted)}.facts>div>strong{color:var(--claim-tone);font-size:.88rem}.facts>div>small{text-align:right;font-size:.7rem}.empty-copy{display:flex;align-items:center;gap:.5rem;border:1px dashed color-mix(in srgb,var(--pathfy-success) 25%,var(--pathfy-line));border-radius:.8rem;padding:.9rem;color:var(--ui-text-muted);font-size:.8rem;line-height:1.55}.freshness-section{margin-top:1.2rem;border-top:1px solid var(--pathfy-line);padding-top:1rem}.freshness-heading{display:flex;align-items:center;justify-content:space-between;gap:.7rem}.freshness-heading strong{font-size:.86rem}.freshness-heading span{color:var(--ui-text-muted);font-size:.72rem}.freshness-strip{display:grid;gap:.55rem;margin-top:.7rem}.freshness-strip>div{display:grid;grid-template-columns:1fr auto auto;gap:.65rem;align-items:center;border:1px solid color-mix(in srgb,var(--pathfy-route) 10%,var(--pathfy-line));border-radius:.7rem;background:var(--ui-bg-elevated);padding:.65rem .7rem;font-size:.76rem}.freshness-strip span{color:var(--ui-text-muted)}
@media(min-width:900px){.claim-layout{grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr)}.freshness-strip{grid-template-columns:repeat(3,minmax(0,1fr))}.freshness-strip>div{grid-template-columns:1fr}.freshness-strip>div>small{text-align:left}}
@media(max-width:700px){.judgement-card{grid-template-columns:1fr auto}.judgement-note{grid-column:1/-1;border-top:1px solid var(--pathfy-line);border-left:0;padding-top:.65rem;padding-left:0}.facts>div{grid-template-columns:1fr auto}.facts>div>small{grid-column:1/-1;text-align:left}.freshness-heading{align-items:flex-start;flex-direction:column}}
</style>
