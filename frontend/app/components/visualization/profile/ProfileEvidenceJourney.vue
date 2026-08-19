<script setup lang="ts">
import P5SceneHost from '../P5SceneHost.client.vue'
import { capabilityLabels, type CapabilityScorePatch } from '~/types/capability'
import type { ProfileAnalysis, ProfileMaterial } from '~/types/profile'
import type { P5SceneStatus } from '~/types/visualization'
import { buildProfileEvidenceSceneData } from '~/utils/visualization/profile-evidence-adapter'
import { createProfileEvidenceScene } from '~/utils/visualization/scenes/profile-evidence-scene'

const props = withDefaults(defineProps<{
  materials: ProfileMaterial[]
  scores: CapabilityScorePatch
  analysis: ProfileAnalysis
  animationRevision?: number
}>(), { animationRevision: 0 })

const localReplayRevision = ref(0)
const status = ref<P5SceneStatus>('idle')
const replayMessage = ref('')
let replayMessageTimer: ReturnType<typeof setTimeout> | undefined

const sceneData = computed(() => buildProfileEvidenceSceneData({
  materials: props.materials,
  scores: props.scores,
  analysis: props.analysis,
  animationRevision: props.animationRevision * 1000 + localReplayRevision.value
}))

const modeLabel = computed(() => sceneData.value.mappingMode === 'explicit' ? '逐条证据映射' : '形成过程概览')
const sortedDimensions = computed(() => [...sceneData.value.dimensions].sort((a, b) => b.score - a.score))
const strongest = computed(() => sortedDimensions.value[0])
const priority = computed(() => sortedDimensions.value[sortedDimensions.value.length - 1])
const averageScore = computed(() => sceneData.value.dimensions.length ? sceneData.value.dimensions.reduce((sum, item) => sum + item.score, 0) / sceneData.value.dimensions.length : 0)

function replay() {
  localReplayRevision.value += 1
  replayMessage.value = '正在重新演示画像形成过程'
  if (replayMessageTimer) clearTimeout(replayMessageTimer)
  replayMessageTimer = setTimeout(() => { replayMessage.value = '' }, 2200)
}

onBeforeUnmount(() => {
  if (replayMessageTimer) clearTimeout(replayMessageTimer)
})
</script>

<template>
  <section class="profile-evidence-journey" aria-labelledby="profile-evidence-journey-heading">
      <header class="profile-evidence-heading">
        <div>
          <div class="profile-evidence-title-row">
            <span class="profile-evidence-index">P5 / EVIDENCE FLOW</span>
            <h2 id="profile-evidence-journey-heading">画像形成过程</h2>
            <UBadge :label="modeLabel" :color="sceneData.mappingMode === 'explicit' ? 'success' : 'neutral'" variant="soft" />
          </div>
          <p>材料证据流向八维能力结果，帮助理解画像如何从输入逐步形成。</p>
        </div>
        <UButton icon="i-lucide-play" color="neutral" variant="soft" :disabled="status === 'loading'" @click="replay">查看形成过程</UButton>
      </header>

    <div class="profile-evidence-steps" aria-label="画像形成的三个阶段">
      <div><span>01</span><p><b>读取材料</b><small>{{ sceneData.summary.materialCount }} 份材料进入分析</small></p></div>
      <i><UIcon name="i-lucide-arrow-right" /></i>
      <div><span>02</span><p><b>提取能力信号</b><small>{{ sceneData.mappingMode === 'explicit' ? `${sceneData.summary.explicitFlowCount} 条显式贡献` : '按材料与最终分数汇聚' }}</small></p></div>
      <i><UIcon name="i-lucide-arrow-right" /></i>
      <div><span>03</span><p><b>形成八维轮廓</b><small>均值 {{ averageScore.toFixed(1) }}，差值 {{ Math.max(0, (strongest?.score || 0) - (priority?.score || 0)).toFixed(0) }}</small></p></div>
    </div>

    <div class="profile-evidence-mode-note" :data-mode="sceneData.mappingMode">
      <UIcon :name="sceneData.mappingMode === 'explicit' ? 'i-lucide-badge-check' : 'i-lucide-info'" />
      <p v-if="sceneData.mappingMode === 'explicit'">
        当前画像包含 {{ sceneData.summary.explicitFlowCount }} 条材料贡献记录，连线来自接口返回的显式证据关系。
      </p>
      <p v-else>
        当前接口未提供逐条贡献关系；动画依据材料数量和最终八维分数展示形成过程概览，不代表精确归因。
      </p>
    </div>

    <P5SceneHost
      :data="sceneData"
      :create-scene="createProfileEvidenceScene"
      accessible-name="能力画像证据汇聚图"
      :min-height="560"
      @status="value => status = value"
    >
      <template #fallback>
        <span>动画视图暂时不可用，下方材料与能力摘要不受影响。</span>
      </template>
    </P5SceneHost>

    <div class="profile-evidence-dom-summary">
      <section aria-labelledby="profile-evidence-materials-heading">
        <h3 id="profile-evidence-materials-heading">参与分析的材料</h3>
        <div class="profile-evidence-chips">
          <span v-for="material in sceneData.materials" :key="material.id">{{ material.name }} · {{ material.kind }}</span>
        </div>
      </section>
      <section aria-labelledby="profile-evidence-dimensions-heading">
        <h3 id="profile-evidence-dimensions-heading">八维结果</h3>
        <div class="profile-dimension-summary">
          <span v-for="dimension in sceneData.dimensions" :key="dimension.id">
            <span>{{ capabilityLabels[dimension.id] }}</span><strong>{{ Math.round(dimension.score) }}</strong>
          </span>
        </div>
      </section>
      <section class="profile-evidence-conclusion" aria-labelledby="profile-evidence-conclusion-heading">
        <h3 id="profile-evidence-conclusion-heading">这张画像说明什么</h3>
        <p>当前优势集中在 <strong>{{ strongest ? capabilityLabels[strongest.id] : '待补充' }} {{ Math.round(strongest?.score || 0) }}</strong>；优先补证维度是 <strong>{{ priority ? capabilityLabels[priority.id] : '待补充' }} {{ Math.round(priority?.score || 0) }}</strong>。</p>
        <small>轮廓面积反映整体能力水平，凹陷位置反映下一步最值得投入证据的方向。</small>
      </section>
    </div>
    <p class="sr-only" aria-live="polite">{{ replayMessage }}</p>
  </section>
</template>

<style>
.profile-evidence-journey{position:relative;display:grid;grid-template-columns:minmax(0,1fr);gap:1rem;overflow:hidden;border:1px solid rgb(255 255 255/.08);border-radius:1.8rem;background:radial-gradient(circle at 72% 18%,rgb(52 211 153/.12),transparent 24%),linear-gradient(145deg,#123437,#081d28 64%,#071722);padding:1.5rem;color:#f6fbfa;box-shadow:0 30px 70px -58px rgb(4 17 24/.9)}
.profile-evidence-journey::before{content:"";position:absolute;right:1.2rem;bottom:1rem;width:5.5rem;height:5.5rem;border:1px solid rgb(255 255 255/.08);border-radius:50%;box-shadow:0 0 0 1.3rem rgb(255 255 255/.025),0 0 0 2.6rem rgb(255 255 255/.02);pointer-events:none}
.profile-evidence-heading{z-index:1;display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.2rem .2rem .5rem}
.profile-evidence-title-row{display:flex;flex-wrap:wrap;align-items:center;gap:.55rem}
.profile-evidence-index{width:100%;color:#66e2cc;font-size:.61rem;font-weight:850;letter-spacing:.12em}
.profile-evidence-title-row h2{font-size:1.22rem;font-weight:760}
.profile-evidence-title-row :deep(.badge){border-color:rgb(255 255 255/.1)}
.profile-evidence-heading p{max-width:37rem;margin-top:.35rem;color:#b6cac9;font-size:.76rem;line-height:1.65}
.profile-evidence-heading :deep(button){border-color:rgb(255 255 255/.13);background:rgb(255 255 255/.08);color:#fff}
.profile-evidence-steps{position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr) auto minmax(0,1fr);gap:.8rem;align-items:center;border:1px solid rgb(255 255 255/.1);border-radius:1rem;background:rgb(255 255 255/.04);padding:.75rem}.profile-evidence-steps>div{display:flex;align-items:center;gap:.65rem;padding:.35rem .5rem}.profile-evidence-steps>div>span{display:grid;width:1.7rem;height:1.7rem;place-items:center;border:1px solid rgb(102 226 204/.42);border-radius:50%;color:#66e2cc;font:800 .6rem ui-monospace,monospace}.profile-evidence-steps p{display:grid;gap:.14rem}.profile-evidence-steps b{font-size:.72rem}.profile-evidence-steps small{color:#91afac;font-size:.61rem}.profile-evidence-steps>i{color:#66e2cc;opacity:.65}
.profile-evidence-mode-note{position:relative;z-index:2;display:flex;align-items:flex-start;gap:.6rem;margin:0;border:1px solid rgb(255 255 255/.1);border-radius:.8rem;background:rgb(242 235 216/.96);padding:.7rem 1rem;color:#33494a;font-size:.68rem;line-height:1.55;box-shadow:0 20px 36px -28px #020a0e}
.profile-evidence-mode-note::before{display:none}
.profile-evidence-mode-note[data-mode="explicit"]{background:#e0f3e7}
.profile-evidence-mode-note :deep(svg){flex:0 0 auto;margin-top:.18rem;color:#087c80}
.profile-evidence-journey .p5-scene-shell{z-index:1;overflow:hidden;border:1px solid rgb(255 255 255/.16);border-radius:1.15rem;background:#e8f2f2;box-shadow:0 22px 50px -38px #000}
.profile-evidence-dom-summary{z-index:1;display:grid;grid-template-columns:minmax(12rem,.7fr) minmax(18rem,1fr) minmax(16rem,.8fr);align-content:start;gap:1.2rem;padding:.7rem .45rem 0}
.profile-evidence-dom-summary section+section{border-left:1px solid rgb(255 255 255/.1);padding-left:1.2rem}
.profile-evidence-dom-summary h3{margin-bottom:.65rem;color:#8aa9a8;font-size:.63rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase}
.profile-evidence-chips{display:grid;gap:.35rem}
.profile-evidence-chips span{overflow:hidden;border-bottom:1px dashed rgb(255 255 255/.15);padding:.25rem 0 .45rem;color:#e7f1f0;font-size:.67rem;text-overflow:ellipsis;white-space:nowrap}
.profile-dimension-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.35rem .8rem}
.profile-dimension-summary>span{display:flex;align-items:center;justify-content:space-between;gap:.4rem;padding:.28rem 0;color:#bed1cf;font-size:.65rem}
.profile-dimension-summary strong{color:#66e2cc;font:750 .73rem ui-monospace,monospace}
.profile-evidence-conclusion p{color:#e7f1f0;font-size:.72rem;line-height:1.65}.profile-evidence-conclusion strong{color:#66e2cc}.profile-evidence-conclusion small{display:block;margin-top:.45rem;color:#8aa9a8;font-size:.62rem;line-height:1.55}
@media(max-width:900px){.profile-evidence-steps{grid-template-columns:1fr}.profile-evidence-steps>i{display:none}.profile-evidence-dom-summary{grid-template-columns:1fr 1fr;padding:.5rem}.profile-evidence-conclusion{grid-column:1/-1}.profile-evidence-dom-summary section+section{border-left:1px solid rgb(255 255 255/.1);padding-left:1rem}.profile-evidence-conclusion{border-top:1px solid rgb(255 255 255/.1);border-left:0!important;padding-top:1rem;padding-left:0!important}}
@media(max-width:620px){.profile-evidence-journey{border-radius:1.25rem;padding:1rem}.profile-evidence-heading{align-items:flex-start;flex-direction:column}.profile-evidence-journey .p5-scene-shell{border-radius:.8rem}.profile-evidence-dom-summary{grid-template-columns:1fr}.profile-evidence-conclusion{grid-column:auto}.profile-evidence-dom-summary section+section{border-top:1px solid rgb(255 255 255/.1);border-left:0;padding-top:1rem;padding-left:0}}
</style>
