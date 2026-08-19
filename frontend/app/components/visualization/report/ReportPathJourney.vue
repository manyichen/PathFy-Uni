<script setup lang="ts">
import P5SceneHost from '../P5SceneHost.client.vue'
import type { CareerReport, DevelopmentAdjustment, DevelopmentLine, ReportEnrichmentState, ReportPlan } from '~/types/report'
import type { ReportPathAnimationKind, ReportPathNodeKind } from '~/types/report-path'
import type { P5SceneStatus } from '~/types/visualization'
import { buildReportPathSceneData } from '~/utils/visualization/report-path-adapter'
import { createReportPathScene } from '~/utils/visualization/scenes/report-path-scene'

const props = withDefaults(defineProps<{
  reportId?: number
  report: CareerReport
  line?: DevelopmentLine
  plan?: ReportPlan
  adjustments?: DevelopmentAdjustment[]
  enrichState?: ReportEnrichmentState | 'idle'
  selectedMonth?: number
  animationRevision?: number
  animationKind?: ReportPathAnimationKind
}>(), {
  adjustments: () => [],
  enrichState: 'idle',
  selectedMonth: 0,
  animationRevision: 0,
  animationKind: 'none'
})

const emit = defineEmits<{ selectMonth: [month: number] }>()
const sceneHost = ref<{ resetView?: () => void }>()
const status = ref<P5SceneStatus>('idle')
const announcement = ref('')
let announcementTimer: ReturnType<typeof setTimeout> | undefined

const sceneData = computed(() => buildReportPathSceneData({
  reportId: props.reportId,
  report: props.report,
  line: props.line,
  plan: props.plan,
  adjustments: props.adjustments,
  enrichState: props.enrichState,
  selectedMonth: props.selectedMonth,
  animationRevision: props.animationRevision,
  animationKind: props.animationKind
}))

const kindLabels: Record<ReportPathNodeKind, string> = {
  origin: '报告起点',
  plan: '计划检查点',
  review: '确认复盘',
  adjustment: '计划调整'
}

const trajectoryCopy = computed(() => {
  const summary = sceneData.value.summary
  if (summary.dataState === 'unmeasured') return {
    label: '尚未形成成长曲线',
    description: '当前没有用户确认的复盘结果，因此不预测、不补线。完成第一次复盘后才写入真实成长点。'
  }
  if (summary.dataState === 'single_review') return {
    label: '已有首个成长锚点',
    description: `第 ${Math.round(summary.latestVerifiedMonth || 0)} 月已形成轨迹指数 ${Math.round(summary.latestVerifiedProgress || 0)}；它由已保存行动与确认指标计算，单次复盘暂不足以判断趋势。`
  }
  return {
    label: '已形成复盘趋势',
    description: `最近更新至第 ${Math.round(summary.latestVerifiedMonth || 0)} 月，轨迹指数 ${Math.round(summary.latestVerifiedProgress || 0)}；曲线只连接已完成行动与确认复盘，不外推未来。`
  }
})

const latestProgress = computed(() => sceneData.value.summary.latestVerifiedProgress)

function announce(message: string) {
  announcement.value = message
  if (announcementTimer) clearTimeout(announcementTimer)
  announcementTimer = setTimeout(() => { announcement.value = '' }, 1600)
}

function selectMonth(month: number) {
  const selected = Math.max(0, Math.min(12, Math.round(month)))
  emit('selectMonth', selected)
  announce(`已选择第 ${selected} 月，请在下方查看计划、复盘与调整详情`)
}

function onCanvasSelect(selection: unknown) {
  if (!selection || typeof selection !== 'object') return
  const month = Number((selection as { month?: unknown }).month)
  if (Number.isFinite(month)) selectMonth(month)
}

function replay() {
  sceneHost.value?.resetView?.()
  announce('正在重新演示已确认成长轨迹')
}

function onSceneError(error: unknown) {
  console.error('已验证成长轨迹绘制失败', error)
}

onBeforeUnmount(() => {
  if (announcementTimer) clearTimeout(announcementTimer)
})
</script>

<template>
  <section class="growth-trajectory" aria-labelledby="report-path-heading">
    <div class="trajectory-coordinate" aria-hidden="true"><span>12</span><i /><b /></div>
    <header class="trajectory-heading">
      <div class="trajectory-index" aria-hidden="true"><span>01</span><i /></div>
      <div class="trajectory-title">
        <p>ROUTE SIGNATURE / REVIEW-BASED</p>
        <h2 id="report-path-heading">12 个月已验证成长轨迹</h2>
        <span>{{ sceneData.title }} · 只有被确认的行动与复盘，才会在这张航图上留下坐标。</span>
      </div>
      <div class="trajectory-status">
        <UBadge label="复盘数据驱动" color="neutral" variant="soft" />
        <UBadge :label="sceneData.enrichment.label" :color="sceneData.enrichment.status === 'failed' ? 'error' : sceneData.enrichment.status === 'completed' ? 'success' : 'warning'" variant="soft" />
        <UButton icon="i-lucide-refresh-cw" color="neutral" variant="soft" size="xs" aria-label="重播已验证成长轨迹" :disabled="status === 'loading'" @click="replay">重播航线</UButton>
      </div>
    </header>

    <div class="trajectory-console">
      <div class="trajectory-visual">
        <div class="trajectory-insight" :data-state="sceneData.summary.dataState">
          <div><span>CURRENT READING / 当前判断</span><strong>{{ trajectoryCopy.label }}</strong><p>{{ trajectoryCopy.description }}</p></div>
        </div>

        <div class="trajectory-legend" aria-hidden="true">
          <span data-kind="actual">已确认复盘</span>
          <span v-if="sceneData.summary.plannedPointCount" data-kind="planned">明确计划检查点</span>
          <span data-kind="phase">计划阶段背景</span>
          <span data-kind="adjustment">计划调整</span>
        </div>

        <div class="trajectory-canvas">
          <P5SceneHost
            ref="sceneHost"
            :data="sceneData"
            :create-scene="createReportPathScene"
            accessible-name="12个月已验证成长轨迹"
            :min-height="390"
            @select="onCanvasSelect"
            @status="value => status = value"
            @error="onSceneError"
          >
            <template #fallback>
              <span>成长轨迹暂时不可用，下方月份详情仍可正常使用。</span>
            </template>
          </P5SceneHost>
        </div>
      </div>

      <aside class="trajectory-logbook" aria-label="航线读数">
        <div class="route-seal" aria-hidden="true"><i /><i /><span>PF<br>ROUTE</span></div>
        <p>VERIFIED POSITION</p>
        <div class="latest-score"><strong>{{ latestProgress == null ? '—' : Math.round(latestProgress) }}</strong><span>成长轨迹指数</span><small>反映执行与验证进展，不是能力分</small></div>
        <div class="trajectory-summary">
          <div><span>确认复盘</span><strong>{{ sceneData.summary.reviewCount }}</strong><small>次真实写入</small></div>
          <div><span>最新指数</span><strong>{{ latestProgress == null ? '待测' : Math.round(latestProgress) }}</strong><small>{{ latestProgress == null ? '复盘后生成' : `/ 100 · 第 ${Math.round(sceneData.summary.latestVerifiedMonth || 0)} 月` }}</small></div>
          <div><span>当前计划</span><strong>第 {{ Math.round(sceneData.currentMonth) }} 月</strong><small>只表示计划位置</small></div>
          <div><span>计划调整</span><strong>{{ sceneData.summary.adjustmentCount }}</strong><small>次已记录变更</small></div>
        </div>
        <footer><span>PATHFY / NAVIGATION LOG</span><b>{{ sceneData.summary.dataState === 'unmeasured' ? 'WAITING FOR SIGNAL' : 'SIGNAL RECORDED' }}</b></footer>
      </aside>
    </div>

    <div v-if="sceneData.nodes.length" class="trajectory-event-ledger">
      <div class="event-ledger-title"><span>MONTH MARKERS</span><strong>沿途航标</strong><small>点击任一坐标，展开该月留下的计划、事实与转向。</small></div>
      <div class="trajectory-events" aria-label="成长轨迹事件">
        <button v-for="node in sceneData.nodes" :key="node.id" type="button" :class="{ selected: node.selected }" :data-kind="node.kind" :aria-pressed="node.selected" @click="selectMonth(node.month)">
          <i aria-hidden="true" />
          <span>{{ String(Math.round(node.month)).padStart(2, '0') }} / MONTH</span>
          <strong>{{ kindLabels[node.kind] }}</strong>
          <small>{{ node.label }}<template v-if="node.progress !== undefined"> · {{ Math.round(node.progress) }}</template><template v-if="node.linkedMonth != null"> · 作用于第 {{ Math.round(node.linkedMonth) }} 月</template></small>
        </button>
      </div>
    </div>

    <footer class="trajectory-note">
      <UIcon name="i-lucide-shield-check" />
      <p><strong>如何读这张图：</strong>横轴是月度复盘顺序，周复盘不会占用月份；纵轴由已保存的行动完成情况和用户确认指标共同累计。没有复盘就不画线，只有文字总结时不虚构增长，计划调整本身也不会自动加分。</p>
    </footer>
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
  </section>
</template>

<style scoped>
.growth-trajectory{position:relative;display:grid;gap:1.15rem;overflow:hidden;border-radius:1.65rem;background:#082b31;color:#edfdfb;padding:clamp(1rem,2.6vw,2rem);box-shadow:0 34px 72px -48px rgb(3 24 31 / .92)}.growth-trajectory::before{position:absolute;inset:0;background-image:radial-gradient(circle,rgb(125 242 225 / .13) 1px,transparent 1.2px),radial-gradient(circle at 15% 16%,rgb(56 210 193 / .12),transparent 25rem),radial-gradient(circle at 87% 73%,rgb(104 119 245 / .1),transparent 26rem);background-size:28px 28px,auto,auto;content:"";pointer-events:none}.trajectory-coordinate{position:absolute;right:2.5%;top:-1.5rem;width:13rem;height:13rem;color:rgb(194 255 245 / .05);pointer-events:none}.trajectory-coordinate span{font:800 10rem/.9 Georgia,serif;letter-spacing:-.09em}.trajectory-coordinate i,.trajectory-coordinate b{position:absolute;right:1.2rem;top:1rem;width:8rem;height:8rem;border:1px solid rgb(115 230 214 / .12);border-radius:50%}.trajectory-coordinate b{right:3rem;top:2.8rem;width:4.4rem;height:4.4rem}.trajectory-heading,.trajectory-console,.trajectory-event-ledger,.trajectory-note{position:relative;z-index:1}.trajectory-heading{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:1rem;align-items:center;padding-bottom:.25rem}.trajectory-index{display:grid;align-self:stretch;justify-items:center;grid-template-rows:auto 1fr;gap:.35rem;color:#62e5d1}.trajectory-index span{font:850 .72rem/1 ui-monospace,monospace}.trajectory-index i{width:1px;background:rgb(98 229 209 / .42)}.trajectory-title>p{color:#62e5d1;font:800 .68rem/1 ui-monospace,monospace;letter-spacing:.13em}.trajectory-title h2{margin-top:.42rem;color:#f4fffd;font-size:clamp(1.55rem,2.7vw,2.35rem);font-weight:790;letter-spacing:-.04em}.trajectory-title>span{display:block;max-width:48rem;margin-top:.42rem;color:rgb(220 244 241 / .68);font-size:.8rem;line-height:1.65}.trajectory-status{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:.42rem}.trajectory-console{display:grid;grid-template-columns:minmax(0,1.72fr) minmax(15.5rem,.58fr);gap:1rem;align-items:stretch}.trajectory-visual{display:grid;min-width:0;gap:.75rem}.trajectory-insight{border-left:2px solid #62e5d1;padding:.15rem 0 .15rem .9rem}.trajectory-insight[data-state=unmeasured]{border-left-color:#f0c75e}.trajectory-insight span{color:#62e5d1;font:750 .62rem/1.2 ui-monospace,monospace;letter-spacing:.11em}.trajectory-insight strong{display:block;margin-top:.34rem;font-size:1rem}.trajectory-insight p{max-width:50rem;margin-top:.25rem;color:rgb(220 244 241 / .64);font-size:.74rem;line-height:1.6}.trajectory-legend{display:flex;flex-wrap:wrap;gap:.55rem 1rem;color:rgb(220 244 241 / .65);font-size:.68rem}.trajectory-legend span{display:inline-flex;align-items:center;gap:.35rem}.trajectory-legend span::before{width:.75rem;height:.18rem;border-radius:999px;background:var(--legend);box-shadow:0 0 9px var(--legend);content:""}.trajectory-legend [data-kind=actual]{--legend:#31d5c4}.trajectory-legend [data-kind=planned]{--legend:#6f92ff}.trajectory-legend [data-kind=phase]{--legend:#91a4b0}.trajectory-legend [data-kind=adjustment]{--legend:#b38af2}.trajectory-canvas{overflow:hidden;border:1px solid rgb(147 236 224 / .2);border-radius:1.1rem;background:linear-gradient(145deg,rgb(245 252 252 / .96),rgb(224 239 240 / .96));box-shadow:inset 0 0 70px rgb(21 103 111 / .09)}.trajectory-logbook{position:relative;display:flex;min-height:100%;flex-direction:column;overflow:hidden;background:#f4ecd8;color:#18373c;padding:1.2rem 1.15rem 1rem;box-shadow:0 14px 30px rgb(0 0 0 / .16);transform:rotate(.45deg);clip-path:polygon(0 0,94% 1%,100% 7%,98% 96%,7% 100%,1% 94%)}.trajectory-logbook::before{position:absolute;inset:0;background-image:linear-gradient(rgb(24 55 60 / .055) 1px,transparent 1px);background-size:100% 1.65rem;content:"";pointer-events:none}.trajectory-logbook>p,.latest-score,.trajectory-summary,.trajectory-logbook footer,.route-seal{position:relative;z-index:1}.trajectory-logbook>p{margin-top:1rem;color:#8f6f24;font:800 .61rem/1 ui-monospace,monospace;letter-spacing:.12em}.route-seal{position:relative;width:4.2rem;height:4.2rem;margin-left:auto}.route-seal i{position:absolute;inset:0;border:1px solid rgb(28 112 109 / .4);border-radius:50%}.route-seal i:nth-child(2){inset:.45rem}.route-seal span{position:absolute;inset:0;display:grid;place-items:center;color:#176f6c;font:800 .56rem/1.25 ui-monospace,monospace;text-align:center}.latest-score{display:grid;margin-top:.5rem;padding-bottom:1rem;border-bottom:2px solid rgb(24 55 60 / .18)}.latest-score strong{color:#0c817b;font:800 4rem/.9 Georgia,serif;letter-spacing:-.08em}.latest-score span{margin-top:.45rem;font-size:.76rem;font-weight:800}.latest-score small{margin-top:.16rem;color:rgb(24 55 60 / .6);font-size:.61rem}.trajectory-summary{display:grid;margin-top:.7rem}.trajectory-summary>div{display:grid;grid-template-columns:1fr auto;gap:.08rem .5rem;border-bottom:1px solid rgb(24 55 60 / .15);padding:.55rem .1rem}.trajectory-summary span{font-size:.66rem}.trajectory-summary strong{font-size:.78rem}.trajectory-summary small{grid-column:1/-1;color:rgb(24 55 60 / .58);font-size:.58rem}.trajectory-logbook footer{display:grid;gap:.12rem;margin-top:auto;padding-top:1rem;color:rgb(24 55 60 / .55);font:700 .53rem/1.4 ui-monospace,monospace;letter-spacing:.08em}.trajectory-logbook footer b{color:#0c817b}.trajectory-event-ledger{display:grid;grid-template-columns:minmax(10rem,.28fr) minmax(0,1fr);gap:1.3rem;border-top:1px solid rgb(142 222 211 / .2);border-bottom:1px solid rgb(142 222 211 / .2);padding:1rem 0}.event-ledger-title{display:grid;align-content:center;border-right:1px solid rgb(142 222 211 / .2);padding-right:1rem}.event-ledger-title span{color:#62e5d1;font:800 .61rem/1 ui-monospace,monospace;letter-spacing:.12em}.event-ledger-title strong{margin-top:.35rem;font-size:1.15rem}.event-ledger-title small{margin-top:.3rem;color:rgb(220 244 241 / .58);font-size:.66rem;line-height:1.5}.trajectory-events{position:relative;display:flex;gap:0;overflow-x:auto;padding:.25rem 0 .4rem}.trajectory-events::before{position:absolute;left:1.1rem;right:1.1rem;top:1rem;border-top:1px dashed rgb(98 229 209 / .35);content:""}.trajectory-events button{--event-tone:#62e5d1;position:relative;display:grid;flex:1 0 10rem;max-width:15rem;gap:.14rem;border:0;background:transparent;padding:1.75rem .8rem .35rem;color:#edfdfb;text-align:left;transition:transform 170ms ease,color 170ms ease}.trajectory-events button[data-kind=review]{--event-tone:#31d5c4}.trajectory-events button[data-kind=adjustment]{--event-tone:#b38af2}.trajectory-events button[data-kind=plan]{--event-tone:#6f92ff}.trajectory-events button>i{position:absolute;left:.85rem;top:.68rem;width:.68rem;height:.68rem;border:2px solid var(--event-tone);border-radius:50%;background:#082b31;box-shadow:0 0 0 .22rem #082b31,0 0 14px var(--event-tone)}.trajectory-events button:hover,.trajectory-events button.selected{transform:translateY(-2px)}.trajectory-events button.selected>i{background:var(--event-tone)}.trajectory-events span{color:var(--event-tone);font:800 .58rem/1 ui-monospace,monospace;letter-spacing:.08em}.trajectory-events strong{margin-top:.17rem;font-size:.77rem}.trajectory-events small{overflow:hidden;color:rgb(220 244 241 / .58);font-size:.63rem;line-height:1.45;text-overflow:ellipsis;white-space:nowrap}.trajectory-note{display:flex;gap:.6rem;align-items:flex-start;color:rgb(220 244 241 / .6)}.trajectory-note svg{flex:0 0 auto;margin-top:.13rem;color:#62e5d1}.trajectory-note p{font-size:.68rem;line-height:1.65}.trajectory-note strong{color:#edfdfb}@media(max-width:960px){.trajectory-console{grid-template-columns:1fr}.trajectory-logbook{min-height:auto;transform:none;clip-path:none}.trajectory-summary{grid-template-columns:repeat(4,minmax(0,1fr));gap:.5rem}.trajectory-summary>div{display:grid;grid-template-columns:1fr}.trajectory-event-ledger{grid-template-columns:1fr}.event-ledger-title{border-right:0;border-bottom:1px solid rgb(142 222 211 / .2);padding:0 0 .75rem}}@media(max-width:700px){.trajectory-heading{grid-template-columns:1fr}.trajectory-index{display:none}.trajectory-status{justify-content:flex-start}.trajectory-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.trajectory-coordinate{display:none}}@media(max-width:440px){.growth-trajectory{border-radius:1rem;padding:.85rem}.trajectory-summary{grid-template-columns:1fr}}
</style>
