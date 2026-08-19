<script setup lang="ts">
import P5SceneHost from '../P5SceneHost.client.vue'
import type { CareerGraphData, CareerGraphNode, CareerGraphNodeKind } from '~/types/career-graph'
import type { P5SceneStatus } from '~/types/visualization'
import { createCareerGraphScene } from '~/utils/visualization/scenes/career-graph-scene'

const props = defineProps<{ data: CareerGraphData }>()
const mode = ref<'graph' | 'list'>('graph')
const selectedNodeId = ref(props.data.currentNodeId)
const sceneStatus = ref<P5SceneStatus>('idle')
const sceneHost = ref<InstanceType<typeof P5SceneHost>>()

const sceneData = computed<CareerGraphData>(() => ({
  ...props.data,
  selectedNodeId: selectedNodeId.value
}))
const selectedNode = computed(() => props.data.nodes.find(node => node.id === selectedNodeId.value) || props.data.nodes[0])

const kindMeta: Record<CareerGraphNodeKind, { label: string; icon: string }> = {
  current: { label: '当前岗位', icon: 'i-lucide-map-pin' },
  promotion: { label: '晋升方向', icon: 'i-lucide-trending-up' },
  lateral: { label: '横向迁移', icon: 'i-lucide-git-compare-arrows' },
  target: { label: '指定目标', icon: 'i-lucide-crosshair' }
}

function isCareerGraphNode(value: unknown): value is CareerGraphNode {
  if (!value || typeof value !== 'object') return false
  const node = value as Partial<CareerGraphNode>
  return typeof node.id === 'string' && typeof node.title === 'string' && typeof node.kind === 'string'
}

function selectNode(value: unknown) {
  if (isCareerGraphNode(value)) selectedNodeId.value = value.id
}

function reportSceneError(error: unknown) {
  console.error('[PathFy career graph] 场景运行异常', error)
}

watch(() => props.data.currentNodeId, currentNodeId => {
  if (!props.data.nodes.some(node => node.id === selectedNodeId.value)) selectedNodeId.value = currentNodeId
})
</script>

<template>
  <section class="career-graph-explorer" aria-labelledby="career-graph-heading">
    <header class="career-graph-header">
      <div>
        <p class="career-graph-eyebrow">PATH RELATIONSHIP MAP</p>
        <h2 id="career-graph-heading">职业路径星图</h2>
        <p class="muted">从同一视角查看晋升、横向迁移和指定目标之间的关系。</p>
      </div>
      <div class="career-view-switch" role="tablist" aria-label="职业路径查看方式">
        <button type="button" role="tab" :aria-selected="mode === 'graph'" :class="{ active: mode === 'graph' }" @click="mode = 'graph'">
          <UIcon name="i-lucide-orbit" />图谱
        </button>
        <button type="button" role="tab" :aria-selected="mode === 'list'" :class="{ active: mode === 'list' }" @click="mode = 'list'">
          <UIcon name="i-lucide-list-tree" />列表
        </button>
      </div>
    </header>

    <div v-if="mode === 'graph'" role="tabpanel" class="career-graph-panel">
      <div class="career-graph-signals" aria-label="图谱摘要">
        <span><strong>{{ data.summary.promotionCount }}</strong> 条晋升路线</span>
        <span><strong>{{ data.summary.lateralCount }}</strong> 个横向方向</span>
        <span><strong>{{ data.nodes.length }}</strong> 个关系节点</span>
        <span v-if="data.summary.hasTransition" class="has-target"><UIcon name="i-lucide-crosshair" />已标记目标岗位</span>
      </div>

      <div class="career-graph-layout">
        <div class="career-canvas-column">
          <P5SceneHost
            ref="sceneHost"
            :data="sceneData"
            :create-scene="createCareerGraphScene"
            accessible-name="职业路径星图"
            :min-height="480"
            @select="selectNode"
            @status="value => sceneStatus = value"
            @error="reportSceneError"
          >
            <template #fallback>
              <div>
                <p>动态图谱暂时不可用。</p>
                <button type="button" class="career-inline-action" @click="mode = 'list'">切换到完整列表</button>
              </div>
            </template>
          </P5SceneHost>
          <div class="career-canvas-controls">
            <p><UIcon name="i-lucide-mouse-pointer-2" />悬停聚焦，拖动画布，滚轮缩放，点击查看节点说明</p>
            <button type="button" :disabled="sceneStatus !== 'ready'" @click="sceneHost?.resetView()">
              <UIcon name="i-lucide-focus" />回到当前岗位
            </button>
          </div>
        </div>

        <aside class="career-node-panel" aria-label="图谱节点说明">
          <div v-if="selectedNode" class="career-node-detail">
            <span class="career-node-kind"><UIcon :name="kindMeta[selectedNode.kind].icon" />{{ kindMeta[selectedNode.kind].label }}</span>
            <h3>{{ selectedNode.title }}</h3>
            <p v-if="selectedNode.description">{{ selectedNode.description }}</p>
            <p v-else class="muted">选择列表视图可查看阶段任务、资源和完整行动建议。</p>
            <div v-if="selectedNode.score != null" class="career-node-score">
              <span>关系可信度</span>
              <strong>{{ Math.round(selectedNode.score * 100) }}%</strong>
            </div>
          </div>

          <div class="career-node-index">
            <p>键盘节点索引</p>
            <button
              v-for="node in data.nodes"
              :key="node.id"
              type="button"
              :aria-current="node.id === selectedNodeId ? 'true' : undefined"
              @click="selectedNodeId = node.id"
            >
              <span :data-kind="node.kind" />
              <span>{{ node.title }}</span>
            </button>
          </div>
        </aside>
      </div>
    </div>

    <div v-else role="tabpanel" class="career-list-panel">
      <slot name="list" />
    </div>
  </section>
</template>

<style scoped>
.career-graph-explorer { display: grid; gap: 1rem; }
.career-graph-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; }
.career-graph-header h2 { margin-top: .15rem; font-size: 1.25rem; font-weight: 700; }
.career-graph-header .muted { margin-top: .25rem; font-size: .86rem; }
.career-graph-eyebrow { color: var(--ui-primary); font-size: .68rem; font-weight: 800; letter-spacing: .16em; }
.career-view-switch { display: inline-flex; flex: 0 0 auto; gap: .25rem; border: 1px solid var(--ui-border); border-radius: .65rem; background: var(--ui-bg-elevated); padding: .22rem; }
.career-view-switch button { display: inline-flex; align-items: center; gap: .35rem; border-radius: .45rem; padding: .45rem .7rem; color: var(--ui-text-muted); font-size: .78rem; font-weight: 700; }
.career-view-switch button.active { background: var(--ui-bg); color: var(--ui-primary); box-shadow: 0 5px 16px -12px rgb(15 23 42 / .7); }
.career-graph-panel { display: grid; gap: .75rem; }
.career-graph-signals { display: flex; flex-wrap: wrap; gap: .55rem; }
.career-graph-signals span { display: inline-flex; align-items: center; gap: .3rem; border: 1px solid var(--ui-border); border-radius: 999px; background: var(--ui-bg-elevated); padding: .32rem .65rem; color: var(--ui-text-muted); font-size: .72rem; }
.career-graph-signals strong { color: var(--ui-text); font-size: .82rem; }
.career-graph-signals .has-target { border-color: color-mix(in srgb, #fbbf24 42%, var(--ui-border)); color: color-mix(in srgb, #f59e0b 76%, var(--ui-text)); }
.career-graph-layout { display: grid; gap: .85rem; grid-template-columns: minmax(0, 1fr) minmax(14rem, 18rem); }
.career-canvas-column { min-width: 0; }
.career-canvas-controls { display: flex; align-items: center; justify-content: space-between; gap: .75rem; padding: .55rem .25rem 0; color: var(--ui-text-muted); font-size: .7rem; }
.career-canvas-controls p, .career-canvas-controls button { display: inline-flex; align-items: center; gap: .35rem; }
.career-canvas-controls button { color: var(--ui-primary); font-weight: 700; }
.career-canvas-controls button:disabled { cursor: not-allowed; opacity: .45; }
.career-node-panel { display: grid; align-content: start; gap: .75rem; min-height: 480px; max-height: 520px; overflow: hidden; border: 1px solid var(--ui-border); border-radius: 1rem; background: var(--ui-bg-elevated); padding: .85rem; }
.career-node-detail { border-bottom: 1px solid var(--ui-border); padding: .25rem .15rem .85rem; }
.career-node-kind { display: inline-flex; align-items: center; gap: .35rem; color: var(--ui-primary); font-size: .7rem; font-weight: 800; }
.career-node-detail h3 { margin-top: .5rem; font-size: 1rem; font-weight: 700; }
.career-node-detail p { margin-top: .45rem; color: var(--ui-text-muted); font-size: .76rem; line-height: 1.65; }
.career-node-score { display: flex; align-items: baseline; justify-content: space-between; margin-top: .7rem; border-radius: .6rem; background: var(--ui-bg); padding: .55rem .65rem; font-size: .7rem; }
.career-node-score strong { color: var(--ui-primary); font-size: 1rem; }
.career-node-index { min-height: 0; overflow: auto; }
.career-node-index > p { padding: .15rem .25rem .45rem; color: var(--ui-text-muted); font-size: .68rem; font-weight: 700; }
.career-node-index button { display: grid; width: 100%; grid-template-columns: .55rem minmax(0, 1fr); align-items: center; gap: .5rem; border-radius: .5rem; padding: .46rem .5rem; text-align: left; }
.career-node-index button:hover, .career-node-index button[aria-current="true"] { background: var(--ui-bg); }
.career-node-index button span:last-child { overflow: hidden; font-size: .75rem; text-overflow: ellipsis; white-space: nowrap; }
.career-node-index button span[data-kind] { width: .45rem; height: .45rem; border-radius: 999px; background: #94a3b8; }
.career-node-index button span[data-kind="promotion"] { background: #38bdf8; }
.career-node-index button span[data-kind="lateral"] { background: #2dd4bf; }
.career-node-index button span[data-kind="target"] { background: #fbbf24; }
.career-node-index button span[data-kind="current"] { border: 1px solid var(--ui-border-accented); background: #f8fafc; }
.career-inline-action { margin-top: .45rem; color: var(--ui-primary); font-weight: 700; }
.career-list-panel { display: grid; gap: 1rem; }
@media (max-width: 900px) {
  .career-graph-layout { grid-template-columns: 1fr; }
  .career-node-panel { min-height: 0; max-height: none; }
  .career-node-index { max-height: 13rem; }
}
@media (max-width: 640px) {
  .career-graph-header { align-items: stretch; flex-direction: column; }
  .career-view-switch { align-self: flex-start; }
  .career-canvas-controls { align-items: flex-start; flex-direction: column; }
}
</style>
