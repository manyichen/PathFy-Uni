<script setup lang="ts">
import type { ProfileDimensionAnalysis } from '~/types/profile'
import { profileDimensionInsight, profileDimensionName, profileDimensionScore, profileItem, profileStringList, profileText } from '~/utils/profile-display'

const props = defineProps<{ shortTerm: unknown; longTerm: unknown; dimensions?: unknown }>()
type RouteKind = 'short' | 'long'
interface RouteStop { title: string; timeframe: string; phase: string; currentScore: number; targetScore: number; objective: string; actions: string[]; evidence: string; metric: string }

const dimensionRows = computed(() => (Array.isArray(props.dimensions) ? props.dimensions : []) as ProfileDimensionAnalysis[])

function rawRows(value: unknown): Record<string, unknown>[] {
  const values = Array.isArray(value) ? value : value == null ? [] : [value]
  return values.map(item => typeof item === 'string' ? { description: item } : profileItem(item))
}

function normalizedStop(row: Record<string, unknown>, index: number, kind: RouteKind): RouteStop {
  const title = profileText(row.title || row.dimension || row.goal) || `${kind === 'short' ? '近期行动' : '长期目标'} ${index + 1}`
  const currentScore = Number(row.current_score ?? row.score ?? 0) || 0
  const targetScore = Number(row.target_score) || Math.min(100, currentScore + (kind === 'short' ? 8 : 15))
  const actions = profileStringList(row.actions || row.suggestions || row.milestones || row.steps)
  return {
    title,
    timeframe: profileText(row.timeframe || row.period) || (kind === 'short' ? [`第 1–30 天`, `第 31–60 天`, `第 61–90 天`][index] || '90 天内' : [`6–12 个月`, `12–18 个月`, `18–36 个月`][index] || '未来 1–3 年'),
    phase: profileText(row.phase || row.goal_type) || (kind === 'short' ? ['建立基线', '完成实践', '验证沉淀'][index] || '持续推进' : '形成长期竞争力'),
    currentScore,
    targetScore,
    objective: profileText(row.milestone || row.outcome || row.description || row.content || row.plan) || `围绕${title}形成可验证提升`,
    actions: actions.length ? actions.slice(0, 3) : [`围绕${title}完成一次真实任务`, '记录过程并获取外部反馈'],
    evidence: profileText(row.deliverable || row.portfolio_evidence || row.expected_evidence) || `${title}成果、过程记录与复盘`,
    metric: profileText(row.success_metric || row.metric || row.validation) || '完成至少 1 项可展示成果并获得反馈'
  }
}

function derivedStops(kind: RouteKind): RouteStop[] {
  const ranked = [...dimensionRows.value].sort((a, b) => profileDimensionScore(a) - profileDimensionScore(b))
  const selected = kind === 'short' ? ranked.slice(0, 3) : [...ranked.slice(0, 2), ...(ranked.length ? [ranked[ranked.length - 1]!] : [])]
  return selected.filter((item, index, rows) => rows.findIndex(candidate => profileDimensionName(candidate) === profileDimensionName(item)) === index).map((item, index) => {
    const insight = profileDimensionInsight(item, dimensionRows.value, [])
    const isStrength = kind === 'long' && insight.score === Math.max(...dimensionRows.value.map(profileDimensionScore))
    return {
      title: insight.name,
      timeframe: kind === 'short' ? [`第 1–30 天`, `第 31–60 天`, `第 61–90 天`][index]! : [`6–12 个月`, `12–18 个月`, `18–36 个月`][index]!,
      phase: kind === 'short' ? ['建立基线', '完成实践', '验证沉淀'][index]! : isStrength ? '深化优势' : '补齐关键能力',
      currentScore: insight.score,
      targetScore: Math.min(100, insight.score + (kind === 'short' ? 8 : isStrength ? 8 : 15)),
      objective: isStrength ? `把${insight.name}转化为可复用的代表成果` : `补齐${insight.name}的关键证据缺口`,
      actions: insight.actions,
      evidence: insight.expectedEvidence,
      metric: insight.successMetric
    }
  })
}

function completeStops(value: unknown, kind: RouteKind) {
  const supplied = rawRows(value).slice(0, 3).map((row, index) => normalizedStop(row, index, kind))
  const fallbacks = derivedStops(kind)
  const merged = [...supplied]
  for (const fallback of fallbacks) {
    if (merged.length >= 3) break
    if (!merged.some(stop => stop.title === fallback.title)) merged.push(fallback)
  }
  return merged.slice(0, 3)
}

const shortStops = computed(() => completeStops(props.shortTerm, 'short'))
const longStops = computed(() => completeStops(props.longTerm, 'long'))
</script>

<template>
  <section class="profile-action-route" aria-labelledby="profile-action-heading">
    <header><div><span>ROUTE / NOW → NEXT</span><h2 id="profile-action-heading">成长路线图</h2></div><p>从当前分数出发，为每一阶段明确行动、应留下的证据和可检查的完成标准。</p></header>
    <div class="profile-route-overview" aria-label="路线摘要"><span><b>NOW</b> 当前画像</span><i /><span><b>90 DAYS</b> {{ shortStops.length }} 个近期里程碑</span><i /><span><b>1—3 YEARS</b> {{ longStops.length }} 个发展目标</span></div>

    <div v-for="lane in [{ key: 'short', label: '01 / BUILD EVIDENCE', title: '接下来 90 天', description: '优先补齐排名靠后的能力，用小成果验证提升是否真实发生。', stops: shortStops }, { key: 'long', label: '02 / COMPOUND VALUE', title: '未来 1—3 年', description: '一边补齐关键短板，一边把最强能力沉淀为长期职业资产。', stops: longStops }]" :key="lane.key" :class="['profile-route-lane', lane.key === 'long' && 'is-future']">
      <header><span>{{ lane.label }}</span><h3>{{ lane.title }}</h3><p>{{ lane.description }}</p></header>
      <ol>
        <li v-for="(stop, index) in lane.stops" :key="`${stop.title}-${index}`">
          <div class="profile-route-marker"><span>{{ String(index + 1).padStart(2, '0') }}</span><i /></div>
          <article>
            <div class="profile-route-stop-head"><div><small>{{ stop.timeframe }} · {{ stop.phase }}</small><h4>{{ stop.title }}</h4></div><b v-if="stop.currentScore">{{ stop.currentScore }} <i>→</i> {{ stop.targetScore }}</b></div>
            <p class="profile-route-objective">{{ stop.objective }}</p>
            <ul><li v-for="action in stop.actions" :key="action">{{ action }}</li></ul>
            <dl><div><dt>{{ lane.key === 'long' ? '职业资产' : '应留下的证据' }}</dt><dd>{{ stop.evidence }}</dd></div><div><dt>{{ lane.key === 'long' ? '验收指标' : '完成标准' }}</dt><dd>{{ stop.metric }}</dd></div></dl>
          </article>
        </li>
      </ol>
    </div>
  </section>
</template>

<style>
.profile-action-route{position:relative;display:grid;gap:1.4rem;overflow:hidden;background:radial-gradient(circle at 18% 18%,rgb(45 212 191/.1),transparent 24%),linear-gradient(145deg,#103338,#071d27 66%,#081722);padding:2rem;color:#f6fbfa}.profile-action-route::before{content:"";position:absolute;inset:0;background-image:radial-gradient(circle,rgb(255 255 255/.14) 1px,transparent 1px);background-size:34px 34px;mask-image:linear-gradient(to right,#000,transparent 72%);opacity:.2;pointer-events:none}.profile-action-route>header{position:relative;z-index:1;display:flex;align-items:end;justify-content:space-between;gap:1rem}.profile-action-route>header span,.profile-route-lane>header span{color:#66e2cc;font-size:.61rem;font-weight:850;letter-spacing:.11em}.profile-action-route h2{margin-top:.25rem;font-size:1.25rem;font-weight:780}.profile-action-route>header p{max-width:34rem;color:#afc4c3;font-size:.74rem;line-height:1.65;text-align:right}.profile-route-overview{position:relative;z-index:1;display:grid;grid-template-columns:auto 1fr auto 1fr auto;gap:.8rem;align-items:center;border:1px solid rgb(255 255 255/.1);border-radius:999px;background:rgb(255 255 255/.04);padding:.7rem 1rem;color:#b9ccca;font-size:.66rem}.profile-route-overview span{white-space:nowrap}.profile-route-overview b{margin-right:.3rem;color:#66e2cc;font:800 .6rem ui-monospace,monospace}.profile-route-overview i{position:relative;height:1px;background:linear-gradient(90deg,rgb(102 226 204/.2),rgb(102 226 204/.7))}.profile-route-overview i::after{content:"";position:absolute;right:0;top:-2px;width:5px;height:5px;border-radius:50%;background:#66e2cc}.profile-route-lane{position:relative;z-index:1;display:grid;grid-template-columns:minmax(13rem,.28fr) minmax(0,1fr);gap:2rem;border-top:1px solid rgb(255 255 255/.1);padding-top:1.4rem}.profile-route-lane>header h3{margin:.35rem 0 .45rem;font-size:1.15rem}.profile-route-lane>header p{max-width:17rem;color:#a9bfbd;font-size:.7rem;line-height:1.65}.profile-route-lane>ol{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.profile-route-lane>ol>li{display:grid;grid-template-columns:1.8rem minmax(0,1fr);gap:.55rem}.profile-route-marker{display:grid;grid-template-rows:1.6rem 1fr;justify-items:center}.profile-route-marker span{display:grid;width:1.6rem;height:1.6rem;place-items:center;border:1px solid rgb(102 226 204/.55);border-radius:50%;background:#0b2930;color:#7cebd7;font:750 .58rem ui-monospace,monospace}.profile-route-marker i{width:1px;background:linear-gradient(rgb(102 226 204/.5),transparent)}.profile-route-lane article{border:1px solid rgb(255 255 255/.1);border-radius:1rem;background:rgb(255 255 255/.045);padding:1rem;box-shadow:0 20px 40px -34px #000}.profile-route-stop-head{display:flex;align-items:start;justify-content:space-between;gap:.6rem}.profile-route-stop-head small{color:#7fcfc2;font-size:.58rem}.profile-route-stop-head h4{margin-top:.3rem;font-size:.84rem}.profile-route-stop-head>b{flex:0 0 auto;border-radius:999px;background:rgb(102 226 204/.1);padding:.35rem .48rem;color:#7cebd7;font:750 .65rem ui-monospace,monospace}.profile-route-stop-head>b i{font-style:normal;opacity:.6}.profile-route-objective{margin:.75rem 0;color:#d9e8e6;font-size:.72rem;font-weight:650;line-height:1.55}.profile-route-lane ul{display:grid;gap:.35rem;margin:.65rem 0;padding-top:.65rem;border-top:1px dashed rgb(255 255 255/.12)}.profile-route-lane ul li{display:grid;grid-template-columns:.65rem 1fr;gap:.25rem;color:#b9ccca;font-size:.66rem;line-height:1.5}.profile-route-lane ul li::before{content:"↳";color:#66e2cc}.profile-route-lane dl{display:grid;gap:.45rem;margin-top:.75rem}.profile-route-lane dl>div{border-left:2px solid rgb(102 226 204/.35);padding-left:.55rem}.profile-route-lane dt{color:#789a98;font-size:.56rem;font-weight:800;letter-spacing:.06em}.profile-route-lane dd{margin-top:.15rem;color:#c8d9d7;font-size:.63rem;line-height:1.45}.profile-route-lane.is-future article{border-color:rgb(237 219 167/.18);background:rgb(242 235 216/.07)}.profile-route-lane.is-future .profile-route-marker span{border-color:rgb(237 219 167/.45);color:#eedda9}.profile-route-lane.is-future .profile-route-stop-head small,.profile-route-lane.is-future .profile-route-stop-head>b{color:#eedda9}.profile-route-lane.is-future .profile-route-stop-head>b{background:rgb(237 219 167/.08)}
@media(max-width:1050px){.profile-route-lane{grid-template-columns:1fr}.profile-route-lane>header p{max-width:34rem}.profile-route-lane>ol{grid-template-columns:1fr}}
@media(max-width:620px){.profile-action-route{padding:1.2rem}.profile-action-route>header{align-items:start;flex-direction:column}.profile-action-route>header p{text-align:left}.profile-route-overview{grid-template-columns:1fr;justify-items:start;border-radius:1rem}.profile-route-overview i{width:1px;height:1rem;margin-left:1rem}.profile-route-lane{gap:1rem}.profile-route-lane>ol>li{grid-template-columns:1.6rem minmax(0,1fr)}}
</style>
