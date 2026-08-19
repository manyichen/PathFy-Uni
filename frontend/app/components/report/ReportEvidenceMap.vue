<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import P5SceneHost from '~/components/visualization/P5SceneHost.client.vue'
import type { ReportTargetDecision } from '~/types/report'
import type { ReportEvidenceSelection } from '~/types/report-evidence'
import type { P5SceneStatus } from '~/types/visualization'
import { buildReportEvidenceSceneData } from '~/utils/visualization/report-evidence-adapter'
import { createReportEvidenceScene } from '~/utils/visualization/scenes/report-evidence-scene'

const props = defineProps<{ decision?: ReportTargetDecision }>()
const emit = defineEmits<{ review: [] }>()
const selectedRowId = ref('')
const status = ref<P5SceneStatus>('idle')
const sceneError = ref('')
const sceneData = computed(() => buildReportEvidenceSceneData(props.decision, selectedRowId.value))
const selectedRow = computed(() => sceneData.value.rows.find(row => row.id === sceneData.value.selectedRowId))
const coverage = computed(() => Math.round(sceneData.value.summary.coverage * 100))
const canvasHeight = computed(() => Math.max(470, sceneData.value.rows.length * 116 + (sceneData.value.orphanActions.length ? 104 : 68)))
const coverageState = computed(() => {
  const outcomes = sceneData.value.summary.outcomeEvidenceCount
  const unlinked = sceneData.value.summary.unlinkedActionCount
  if (unlinked) return { label: '存在行动断链', tone: 'weak', description: `有 ${unlinked} 项行动没有完整关联到能力事实，需要先修正行动依据。` }
  if (!outcomes && coverage.value >= 80) return { label: '链路已连通 · 成果待补', tone: 'partial', description: '系统数据、判断和行动已经连通，但目前没有经复盘确认的成果记录；100 分只代表链路完整，不代表能力已被证明。' }
  if (coverage.value >= 80) return { label: '已有成果记录 · 归因待核对', tone: 'good', description: `当前目标已有 ${outcomes} 项用户确认成果；由于旧记录没有能力维度归因，不能自动把它们判定为某项能力已达标。` }
  return { label: '判断依据不完整', tone: 'weak', description: '当前事实、判断或行动存在缺失，应先补画像、岗位标尺或行动来源。' }
})
const selectedFacts = computed(() => selectedRow.value?.facts.filter(fact => ['当前能力', '岗位要求', '有效差距', '容差内差值'].some(label => fact.label.includes(label))) || [])
const nextEvidenceTask = computed(() => {
  const row = selectedRow.value
  if (!row) return '当前没有可展开的能力判断。'
  if (!row.chainConnected) return `“${row.dimensionLabel}”的依据或行动尚未连通，先核对事实引用和行动归属。`
  if (row.closureState === 'verified') return `“${row.dimensionLabel}”已有成果证据，可在下次复盘检查时效与质量。`
  if (row.closureState === 'awaiting_review') return `行动已勾选完成，但还不能自动视为能力证明；请补充产物链接、截图或反馈。`
  if (sceneData.value.summary.outcomeEvidenceCount) return `当前目标已有 ${sceneData.value.summary.outcomeEvidenceCount} 项成果记录，但尚未明确归因到“${row.dimensionLabel}”；复盘时请说明它证明了什么。`
  if (row.nextAction) return `完成“${row.nextAction.title}”，并保留“${row.nextAction.deliverable}”作为复盘材料。`
  return `“${row.dimensionLabel}”尚未配置针对性行动，需要先拆解一个可验收产物。`
})

watch(() => props.decision?.job_id, () => { selectedRowId.value = ''; sceneError.value = '' })

function onSelect(value: unknown) {
  const rowId = String((value as ReportEvidenceSelection | undefined)?.rowId || '')
  if (rowId) selectedRowId.value = rowId
}
function selectRow(rowId: string) { selectedRowId.value = rowId }
function selectFirstBroken() {
  const row = sceneData.value.rows.find(item => !item.chainConnected || item.closureState === 'missing_action')
  if (row) selectedRowId.value = row.id
}
function onSceneError(error: unknown) { sceneError.value = error instanceof Error ? error.message : String(error || 'unknown') }
</script>

<template>
  <section class="evidence-map" aria-labelledby="evidence-map-title">
    <div class="evidence-stage">
      <div class="stage-main">
        <header class="map-header">
          <div class="title-row"><span class="map-index">01 / 证据路径</span><span class="coverage-state" :data-tone="coverageState.tone">{{ coverageState.label }}</span></div>
          <h2 id="evidence-map-title">能力差值如何变成行动，<br>又如何留下真实成果</h2>
          <p>{{ coverageState.description }}</p>
        </header>

        <div class="metric-strip">
          <div data-tone="blue"><UIcon name="i-lucide-scan-line" /><span>可量化判断</span><strong>{{ sceneData.summary.comparableCount }}<small>/ {{ sceneData.summary.claimCount }}</small></strong><em>当前分与岗位标尺可比较</em></div>
          <div data-tone="amber" :class="{ attention: sceneData.summary.riskCount > 0 }"><UIcon name="i-lucide-triangle-alert" /><span>需补齐或验证</span><strong>{{ sceneData.summary.riskCount }}</strong><em>硬缺口与容差内风险</em></div>
          <div data-tone="violet" :class="{ attention: sceneData.summary.unlinkedActionCount > 0 }"><UIcon name="i-lucide-waypoints" /><span>行动映射</span><strong>{{ sceneData.summary.linkedActionCount }}<small>/ {{ sceneData.summary.actionCount }}</small></strong><em>{{ sceneData.summary.unlinkedActionCount }} 项缺少完整依据</em></div>
          <div data-tone="green" :class="{ attention: sceneData.summary.outcomeEvidenceCount === 0 }"><UIcon name="i-lucide-badge-check" /><span>已确认成果</span><strong>{{ sceneData.summary.outcomeEvidenceCount }}</strong><em>{{ sceneData.summary.completedActionCount }} 项行动已完成</em></div>
        </div>

        <div class="map-canvas-wrap">
          <div class="paper-pin" aria-hidden="true" />
          <div class="map-legend" aria-hidden="true"><span data-kind="current">圆点 · 当前画像</span><span data-kind="required">菱形 · 岗位标尺</span><span data-kind="risk">红 / 黄 · 待处理</span><span data-kind="strength">绿 · 相对优势</span></div>
          <P5SceneHost :data="sceneData" :create-scene="createReportEvidenceScene" accessible-name="按能力维度组织的决策依据板" :min-height="canvasHeight" @select="onSelect" @status="value => status = value" @error="onSceneError">
            <template #fallback><span>决策依据板暂时不可用，下方维度索引、数值与行动详情仍可正常查看。</span></template>
          </P5SceneHost>
          <footer><span>PATHFY / EVIDENCE TRACE</span><span>点击任一能力行查看依据</span></footer>
        </div>
      </div>

      <aside class="stage-margin">
        <article class="coverage-note">
          <span>链路完整度</span>
          <strong>{{ coverage }}<small>/ 100</small></strong>
          <p>只表示“事实—判断—行动”是否连通，不代表录用率，也不自动证明能力达标。</p>
        </article>

        <div v-if="sceneData.rows.length" class="dimension-index" aria-label="能力判断索引">
          <p>切换观察维度</p>
          <button v-for="(row, index) in sceneData.rows" :key="row.id" type="button" :class="{ active: row.id === sceneData.selectedRowId }" :data-state="row.state" @click="selectRow(row.id)"><em>{{ String(index + 1).padStart(2, '0') }}</em><span>{{ row.dimensionLabel }}</span><strong>{{ row.comparisonLabel }}</strong></button>
        </div>

      <article class="selected-detail" :data-state="selectedRow?.state">
        <div class="detail-heading"><span>{{ selectedRow?.stateLabel || '能力判断' }}</span><strong>{{ selectedRow?.dimensionLabel || '请选择一项判断' }}</strong></div>
        <h3>{{ selectedRow?.title || '暂无可展示的能力结论' }}</h3>
        <p>{{ selectedRow?.summary || '需要补充可比较的画像和岗位要求。' }}</p>
        <div v-if="selectedFacts.length" class="fact-chips"><span v-for="fact in selectedFacts" :key="fact.id"><small>{{ fact.label }}</small><b>{{ fact.value ?? '—' }}{{ fact.unit }}</b></span></div>
        <small v-if="selectedRow">{{ selectedRow.grade }} 级系统依据 · {{ selectedRow.chainConnected ? '依据到行动已连通' : '依据链存在断点' }}</small>
      </article>
      <article class="next-proof">
        <div class="detail-heading"><span>下一份证据</span><strong>{{ selectedRow?.closureLabel || '待判断' }}</strong></div>
        <h3>{{ nextEvidenceTask }}</h3>
        <p v-if="selectedRow?.nextAction">交付物：{{ selectedRow.nextAction.deliverable }} · {{ selectedRow.nextAction.deadline }}</p>
        <div><UButton v-if="sceneData.summary.unlinkedActionCount" size="sm" color="warning" variant="soft" @click="selectFirstBroken">定位断链判断</UButton><UButton size="sm" color="neutral" icon="i-lucide-arrow-up-right" @click="emit('review')">去复盘补成果</UButton></div>
      </article>
      </aside>
    </div>
    <p class="sr-only" aria-live="polite">决策依据板状态：{{ status }}。当前链路完整度 {{ coverage }} 分，已确认成果记录 {{ sceneData.summary.outcomeEvidenceCount }} 项。</p>
    <p v-if="sceneError" class="sr-only">决策依据板错误：{{ sceneError }}</p>
  </section>
</template>

<style scoped>
.evidence-map{overflow:hidden;border:1px solid color-mix(in srgb,var(--pathfy-evidence) 25%,var(--pathfy-line));border-radius:1.35rem;background:var(--pathfy-surface-panel);box-shadow:0 28px 60px -48px rgb(15 23 42 / .75)}
.map-header{position:relative;display:flex;align-items:flex-start;justify-content:space-between;gap:1.5rem;overflow:hidden;padding:1.7rem 1.8rem;background:radial-gradient(circle at 84% 10%,color-mix(in srgb,var(--pathfy-route) 18%,transparent),transparent 14rem),linear-gradient(125deg,color-mix(in srgb,var(--pathfy-evidence) 15%,var(--pathfy-surface-panel)),var(--pathfy-surface-panel) 64%)}
.map-header::after{position:absolute;right:7rem;bottom:-4rem;width:10rem;height:10rem;border:1px solid color-mix(in srgb,var(--pathfy-evidence) 15%,transparent);border-radius:50%;content:"";pointer-events:none}.title-row{display:flex;flex-wrap:wrap;align-items:center;gap:.6rem}.map-index{color:var(--pathfy-evidence);font-size:.76rem;font-weight:850;letter-spacing:.1em}.coverage-state{border-radius:999px;padding:.3rem .65rem;font-size:.72rem;font-weight:750}.coverage-state[data-tone=good]{background:color-mix(in srgb,var(--pathfy-success) 14%,transparent);color:var(--pathfy-success)}.coverage-state[data-tone=partial]{background:color-mix(in srgb,var(--pathfy-gap) 14%,transparent);color:var(--pathfy-gap)}.coverage-state[data-tone=weak]{background:color-mix(in srgb,var(--pathfy-risk) 13%,transparent);color:var(--pathfy-risk)}.map-header h2{max-width:52rem;margin-top:.65rem;font-size:clamp(1.35rem,2.1vw,1.85rem);font-weight:780;letter-spacing:-.025em;line-height:1.25;text-wrap:balance}.map-header p{margin-top:.55rem;max-width:52rem;color:var(--ui-text-muted);font-size:.88rem;line-height:1.75}.coverage-score{position:relative;z-index:1;display:grid;min-width:9rem;flex:0 0 auto;text-align:right}.coverage-score strong{font-size:3.1rem;line-height:.95;color:var(--pathfy-evidence);letter-spacing:-.07em}.coverage-score span{margin-top:.4rem;color:var(--ui-text);font-size:.76rem;font-weight:700}.coverage-score small{margin-top:.18rem;color:var(--ui-text-muted);font-size:.68rem}.metric-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem;border:0;padding:1rem 1.15rem;background:color-mix(in srgb,var(--pathfy-evidence) 2%,var(--ui-bg))}.metric-strip>div{--metric:var(--pathfy-evidence);position:relative;display:grid;grid-template-columns:auto 1fr;column-gap:.55rem;min-height:7.2rem;border:1px solid color-mix(in srgb,var(--metric) 22%,var(--pathfy-line));border-radius:.95rem;background:linear-gradient(145deg,color-mix(in srgb,var(--metric) 10%,var(--ui-bg)),var(--ui-bg) 68%);padding:.9rem 1rem;box-shadow:0 14px 30px -28px rgb(15 23 42 / .7)}.metric-strip>div[data-tone=amber]{--metric:var(--pathfy-gap)}.metric-strip>div[data-tone=violet]{--metric:var(--pathfy-route)}.metric-strip>div[data-tone=green]{--metric:var(--pathfy-success)}.metric-strip svg{grid-row:1;align-self:center;color:var(--metric);font-size:1.1rem}.metric-strip span{align-self:center;color:var(--ui-text-muted);font-size:.74rem;font-weight:700}.metric-strip strong{grid-column:1/-1;margin-top:.45rem;color:var(--metric);font-size:1.65rem;line-height:1}.metric-strip strong small{color:var(--ui-text-muted);font-size:.78rem}.metric-strip em{grid-column:1/-1;margin-top:.35rem;color:var(--ui-text-muted);font-size:.7rem;font-style:normal;line-height:1.45}.metric-strip .attention strong{color:var(--metric)}.metric-strip .attention em{color:color-mix(in srgb,var(--metric) 82%,var(--ui-text-muted))}.map-canvas-wrap{margin:0 1.15rem;padding:.9rem 1rem .4rem;border:1px solid color-mix(in srgb,var(--pathfy-evidence) 18%,var(--pathfy-line));border-radius:1rem;background:linear-gradient(180deg,color-mix(in srgb,var(--pathfy-evidence) 4%,var(--ui-bg)),var(--ui-bg))}.map-legend{display:flex;flex-wrap:wrap;gap:.55rem 1.15rem;margin-bottom:.65rem;color:var(--ui-text-muted);font-size:.72rem}.map-legend span{display:flex;align-items:center;gap:.35rem}.map-legend span::before{width:.5rem;height:.5rem;border-radius:999px;background:var(--dot);content:""}.map-legend [data-kind=current]{--dot:#24a5ce}.map-legend [data-kind=required]{--dot:#8b72df}.map-legend [data-kind=risk]{--dot:#d99a2b}.map-legend [data-kind=strength]{--dot:#148b80}.dimension-index{display:flex;gap:.55rem;overflow-x:auto;padding:.85rem 1.15rem}.dimension-index button{display:grid;min-width:11rem;border:1px solid color-mix(in srgb,var(--row-accent,var(--pathfy-evidence)) 20%,var(--pathfy-line));border-radius:.75rem;background:var(--ui-bg);padding:.65rem .75rem;text-align:left;transition:transform 160ms ease,box-shadow 160ms ease}.dimension-index button:hover{transform:translateY(-2px)}.dimension-index button.active{border-color:var(--row-accent);background:color-mix(in srgb,var(--row-accent) 6%,var(--ui-bg));box-shadow:inset 4px 0 var(--row-accent),0 12px 24px -22px var(--row-accent)}.dimension-index button[data-state=hard_gap]{--row-accent:var(--pathfy-risk)}.dimension-index button[data-state=verify]{--row-accent:var(--pathfy-gap)}.dimension-index button[data-state=strength]{--row-accent:var(--pathfy-success)}.dimension-index button[data-state=opportunity]{--row-accent:var(--pathfy-evidence)}.dimension-index span{font-size:.8rem;font-weight:750}.dimension-index strong{margin-top:.22rem;color:var(--ui-text-muted);font-size:.68rem;font-weight:550}.map-feedback{display:grid;gap:.85rem;padding:.15rem 1.15rem 1.2rem}.map-feedback article{border:1px solid var(--pathfy-line);border-radius:1rem;padding:1.05rem 1.1rem}.detail-heading{display:flex;align-items:center;justify-content:space-between;gap:.5rem}.detail-heading span{color:var(--ui-text-muted);font-size:.72rem}.detail-heading strong{font-size:.78rem}.map-feedback h3{margin-top:.55rem;font-size:.95rem;font-weight:730;line-height:1.55}.map-feedback p,.map-feedback>article>small{display:block;margin-top:.4rem;color:var(--ui-text-muted);font-size:.78rem;line-height:1.65}.selected-detail{border-left:4px solid var(--pathfy-evidence)!important;background:linear-gradient(135deg,color-mix(in srgb,var(--pathfy-evidence) 5%,var(--ui-bg)),var(--ui-bg))}.selected-detail[data-state=hard_gap]{border-left-color:var(--pathfy-risk)!important}.selected-detail[data-state=verify]{border-left-color:var(--pathfy-gap)!important}.selected-detail[data-state=strength]{border-left-color:var(--pathfy-success)!important}.fact-chips{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.75rem}.fact-chips span{display:flex;align-items:baseline;gap:.4rem;border:1px solid color-mix(in srgb,var(--pathfy-evidence) 14%,var(--pathfy-line));border-radius:.6rem;background:var(--ui-bg-elevated);padding:.45rem .6rem}.fact-chips small{color:var(--ui-text-muted);font-size:.68rem}.fact-chips b{font-size:.82rem}.next-proof{border-left:4px solid var(--pathfy-route)!important;background:linear-gradient(135deg,color-mix(in srgb,var(--pathfy-route) 7%,var(--ui-bg)),var(--ui-bg))}.next-proof>div:last-child{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.75rem}@media(min-width:800px){.map-feedback{grid-template-columns:1fr 1fr}}@media(max-width:760px){.map-header{display:grid;padding:1.3rem}.coverage-score{text-align:left}.coverage-score strong{font-size:2.5rem}.metric-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.map-canvas-wrap{margin-inline:.75rem;padding-inline:.65rem}}@media(max-width:480px){.metric-strip{grid-template-columns:1fr}.metric-strip>div{min-height:auto}.map-feedback{padding-inline:.75rem}}

/* Editorial evidence desk — visually aligned with the home-page workroom. */
.evidence-map {
  --stage-ink: #08242d;
  overflow: visible;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.evidence-stage {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(18rem, .31fr);
  gap: clamp(1.35rem, 3vw, 3rem);
  overflow: hidden;
  border-radius: 1.8rem;
  background:
    radial-gradient(circle at 16% 15%, rgb(36 165 206 / .16), transparent 25rem),
    radial-gradient(circle at 83% 70%, rgb(20 139 128 / .15), transparent 22rem),
    var(--stage-ink);
  padding: clamp(1.25rem, 3vw, 2.5rem);
  box-shadow: 0 36px 80px -52px rgb(5 25 32 / .9);
}

.evidence-stage::before {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgb(105 185 193 / .15) .8px, transparent .8px);
  background-size: 22px 22px;
  content: "";
  mask-image: linear-gradient(90deg, #000, transparent 72%);
  pointer-events: none;
}

.stage-main,
.stage-margin { position: relative; z-index: 1; min-width: 0; }
.stage-main { display: grid; align-content: start; }
.stage-margin { display: grid; align-content: start; gap: 1.1rem; padding-top: .3rem; }

.map-header {
  display: block;
  max-width: 58rem;
  overflow: visible;
  padding: .4rem .35rem 1.5rem;
  background: transparent;
  color: #f5fbfc;
}

.map-header::after { display: none; }
.title-row { gap: .75rem; }
.map-index { color: #73e1d3; font: 850 .78rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .12em; }
.coverage-state { border: 1px solid rgb(255 255 255 / .12); background: rgb(255 255 255 / .07); padding: .38rem .72rem; font-size: .75rem; }
.coverage-state[data-tone="good"] { background: rgb(107 214 174 / .08); color: #8ce7bd; }
.coverage-state[data-tone="partial"] { background: rgb(241 200 91 / .08); color: #f4d570; }
.coverage-state[data-tone="weak"] { background: rgb(241 110 128 / .08); color: #ff9bab; }
.map-header h2 { max-width: 51rem; margin-top: 1rem; font-size: clamp(1.75rem, 3vw, 3rem); font-weight: 780; letter-spacing: -.05em; line-height: 1.12; }
.map-header p { max-width: 48rem; margin-top: .9rem; color: rgb(226 242 245 / .68); font-size: .92rem; line-height: 1.8; }

.metric-strip {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  border-top: 1px solid rgb(210 238 241 / .16);
  border-bottom: 1px solid rgb(210 238 241 / .16);
  padding: 0;
  background: transparent;
}

.metric-strip > div {
  --metric: #55c7e3;
  grid-template-columns: auto 1fr;
  gap: .35rem .55rem;
  min-height: 7.5rem;
  border: 0;
  border-right: 1px solid rgb(210 238 241 / .14);
  border-radius: 0;
  background: transparent;
  padding: 1rem .9rem;
  color: #f2fbfc;
  box-shadow: none;
}

.metric-strip > div:last-child { border-right: 0; }
.metric-strip > div[data-tone="amber"] { --metric: #f1c85b; }
.metric-strip > div[data-tone="violet"] { --metric: #b6a3ff; }
.metric-strip > div[data-tone="green"] { --metric: #6bd6ae; }
.metric-strip svg { width: 1.15rem; height: 1.15rem; color: var(--metric); }
.metric-strip span { color: rgb(224 241 244 / .62); font-size: .78rem; }
.metric-strip strong { margin-top: 0; color: var(--metric); font-size: 1.9rem; }
.metric-strip strong small { color: rgb(224 241 244 / .58); font-size: .8rem; }
.metric-strip em { margin-top: 0; color: rgb(224 241 244 / .58); font-size: .73rem; line-height: 1.5; }
.metric-strip .attention::after { position: absolute; right: .8rem; bottom: .75rem; width: .42rem; height: .42rem; border-radius: 50%; background: var(--metric); box-shadow: 0 0 0 .3rem color-mix(in srgb, var(--metric) 14%, transparent); content: ""; }

.map-canvas-wrap {
  position: relative;
  margin: 1.65rem 0 0;
  overflow: hidden;
  border: 1px solid rgb(134 118 77 / .25);
  border-radius: .35rem .9rem .9rem .35rem;
  background: linear-gradient(90deg, rgb(141 118 78 / .055) 1px, transparent 1px), linear-gradient(#fffdf5, #faf7ed);
  background-size: 28px 100%, 100% 100%;
  padding: 1.1rem 1rem .75rem;
  color: #243438;
  box-shadow: 0 28px 55px -34px rgb(0 0 0 / .72);
  transform: rotate(-.2deg);
}

.map-canvas-wrap::before { position: absolute; top: 0; bottom: 0; left: 1rem; width: 1px; background: rgb(190 24 93 / .12); content: ""; pointer-events: none; }
.paper-pin { position: absolute; top: -.3rem; left: 47%; z-index: 3; width: 4.4rem; height: .85rem; background: rgb(135 207 222 / .55); transform: rotate(-2deg); }
.map-legend { position: relative; z-index: 1; gap: .5rem 1.1rem; margin: 0; border-bottom: 1px dashed rgb(35 48 52 / .18); padding: .25rem .5rem .8rem 1rem; color: rgb(35 48 52 / .65); font-size: .75rem; font-weight: 650; }
.map-canvas-wrap footer { display: flex; justify-content: space-between; gap: 1rem; border-top: 1px solid rgb(35 48 52 / .15); padding: .7rem .35rem 0 1rem; color: rgb(35 48 52 / .46); font: 650 .64rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .05em; }

.coverage-note {
  position: relative;
  border-radius: .25rem;
  background: #f3df99;
  padding: 1.35rem 1.4rem;
  color: #382f1e;
  box-shadow: 0 20px 42px -28px rgb(0 0 0 / .8);
  transform: rotate(1.2deg);
}

.coverage-note::before { position: absolute; top: -.42rem; left: 38%; width: 4rem; height: .85rem; background: rgb(255 255 255 / .42); content: ""; transform: rotate(-3deg); }
.coverage-note > span { font-size: .76rem; font-weight: 850; letter-spacing: .08em; }
.coverage-note > strong { display: block; margin-top: .45rem; color: #0b6d77; font-size: 3.4rem; letter-spacing: -.07em; line-height: 1; }
.coverage-note > strong small { margin-left: .2rem; font-size: .85rem; letter-spacing: 0; }
.coverage-note p { margin-top: .7rem; color: #55482c; font-size: .8rem; line-height: 1.7; }

.dimension-index { display: grid; gap: 0; overflow: visible; border-top: 1px solid rgb(210 238 241 / .16); padding: 0; }
.dimension-index > p { padding: .85rem .1rem .55rem; color: rgb(224 241 244 / .52); font-size: .72rem; font-weight: 750; }
.dimension-index button {
  --row-accent: #55c7e3;
  display: grid;
  grid-template-columns: 2rem minmax(0, .75fr) minmax(0, 1fr);
  gap: .55rem;
  align-items: center;
  min-width: 0;
  border: 0;
  border-bottom: 1px solid rgb(210 238 241 / .13);
  border-radius: 0;
  background: transparent;
  padding: .75rem .15rem;
  color: rgb(226 242 245 / .68);
  transition: color 160ms ease, padding 160ms ease, background 160ms ease;
}

.dimension-index button:hover,
.dimension-index button.active { border: 0; border-bottom: 1px solid rgb(210 238 241 / .13); background: linear-gradient(90deg, color-mix(in srgb, var(--row-accent) 13%, transparent), transparent); color: #fff; padding-left: .55rem; box-shadow: none; transform: none; }
.dimension-index button[data-state="hard_gap"] { --row-accent: #f16e80; }
.dimension-index button[data-state="verify"] { --row-accent: #f1c85b; }
.dimension-index button[data-state="strength"] { --row-accent: #6bd6ae; }
.dimension-index em { color: var(--row-accent); font: 750 .68rem/1 ui-monospace, monospace; font-style: normal; }
.dimension-index span { font-size: .84rem; }
.dimension-index strong { margin: 0; color: inherit; font-size: .72rem; line-height: 1.35; }

.selected-detail {
  --row-tone: #62c7df;
  border: 0 !important;
  border-left: 3px solid var(--row-tone) !important;
  border-radius: 0;
  background: transparent;
  padding: .35rem 0 .35rem 1rem;
  color: #f3fbfc;
}

.selected-detail[data-state="hard_gap"] { --row-tone: #f16e80; border-left-color: var(--row-tone) !important; }
.selected-detail[data-state="verify"] { --row-tone: #f1c85b; border-left-color: var(--row-tone) !important; }
.selected-detail[data-state="strength"] { --row-tone: #6bd6ae; border-left-color: var(--row-tone) !important; }
.detail-heading span { color: var(--row-tone, #73e1d3); font-size: .74rem; font-weight: 800; }
.detail-heading strong { color: rgb(226 242 245 / .62); font-size: .75rem; }
.selected-detail h3,
.next-proof h3 { margin-top: .7rem; font-size: 1rem; font-weight: 730; line-height: 1.55; }
.selected-detail p,
.selected-detail > small,
.next-proof p { display: block; margin-top: .5rem; color: rgb(226 242 245 / .62); font-size: .78rem; line-height: 1.65; }
.fact-chips span { display: grid; border: 1px solid rgb(210 238 241 / .15); background: rgb(255 255 255 / .055); }
.fact-chips small { color: rgb(226 242 245 / .55); }
.fact-chips b { margin-top: .12rem; color: #fff; }

.next-proof {
  position: relative;
  border: 0 !important;
  border-radius: .25rem;
  background: #f7f2df;
  padding: 1.25rem;
  color: #26363a;
  box-shadow: 0 18px 38px -30px #000;
  transform: rotate(-.7deg);
}

.next-proof .detail-heading span { color: #0f766e; }
.next-proof .detail-heading strong { color: #556267; }
.next-proof p { color: #697478; }
.next-proof > div:last-child { margin-top: .85rem; }

@media (max-width: 1100px) {
  .evidence-stage { grid-template-columns: 1fr; }
  .stage-margin { grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; }
  .coverage-note { grid-row: span 2; }
  .dimension-index { grid-column: 2; }
  .metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .metric-strip > div:nth-child(2) { border-right: 0; }
}

@media (max-width: 700px) {
  .evidence-stage { border-radius: 1.25rem; padding: 1rem; }
  .map-header { padding: .4rem .2rem 1.25rem; }
  .map-header h2 { font-size: 2rem; }
  .metric-strip { grid-template-columns: 1fr 1fr; }
  .metric-strip > div { min-height: 6.7rem; }
  .stage-margin { grid-template-columns: 1fr; }
  .coverage-note, .dimension-index { grid-row: auto; grid-column: auto; }
  .map-canvas-wrap { padding-inline: .35rem; transform: none; }
  .map-legend, .map-canvas-wrap footer { padding-left: .7rem; }
}

@media (max-width: 440px) {
  .metric-strip { grid-template-columns: 1fr; }
  .metric-strip > div { min-height: auto; border-right: 0; }
  .map-header h2 { font-size: 1.72rem; }
  .coverage-note { transform: none; }
}
</style>
