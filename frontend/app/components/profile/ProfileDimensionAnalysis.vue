<script setup lang="ts">
import type { ProfileDimensionAnalysis as Dimension } from '~/types/profile'
import { profileDimensionInsight, profileDimensionName, profileDimensionScore, profileItems } from '~/utils/profile-display'

const props = defineProps<{ items: unknown; materialNames: string[] }>()
const dimensions = computed(() => profileItems(props.items) as Dimension[])
const activeIndex = ref(0)
const activeDimension = computed(() => dimensions.value[activeIndex.value] || dimensions.value[0])
const activeScore = computed(() => activeDimension.value ? profileDimensionScore(activeDimension.value) : 0)
const insight = computed(() => activeDimension.value ? profileDimensionInsight(activeDimension.value, dimensions.value, props.materialNames) : undefined)
const stageStyle = computed(() => ({ '--dimension-score': `${Math.min(100, Math.max(0, activeScore.value))}%` }))

watch(dimensions, items => {
  if (activeIndex.value >= items.length) activeIndex.value = 0
})

function moveTab(index: number, direction: number) {
  if (!dimensions.value.length) return
  activeIndex.value = (index + direction + dimensions.value.length) % dimensions.value.length
  nextTick(() => document.getElementById(`profile-dimension-tab-${activeIndex.value}`)?.focus())
}
</script>

<template>
  <section class="profile-dimension-atlas" aria-labelledby="profile-dimension-heading">
    <header>
      <div><span>08 / CAPABILITY INDEX</span><h2 id="profile-dimension-heading">各维度详细分析</h2></div>
      <p>选择一个维度，查看相对位置、材料线索、能力缺口、下一步行动和验收标准。</p>
    </header>

    <div v-if="dimensions.length && activeDimension" class="profile-dimension-browser">
      <div class="profile-dimension-index-list" role="tablist" aria-label="能力维度">
        <button
          v-for="(item, index) in dimensions"
          :id="`profile-dimension-tab-${index}`"
          :key="profileDimensionName(item)"
          type="button"
          role="tab"
          :aria-controls="'profile-dimension-stage'"
          :aria-selected="activeIndex === index"
          :tabindex="activeIndex === index ? 0 : -1"
          :class="{ active: activeIndex === index }"
          @click="activeIndex = index"
          @keydown.right.prevent="moveTab(index, 1)"
          @keydown.down.prevent="moveTab(index, 1)"
          @keydown.left.prevent="moveTab(index, -1)"
          @keydown.up.prevent="moveTab(index, -1)"
        >
          <span>{{ String(Number(index) + 1).padStart(2, '0') }}</span>
          <strong>{{ profileDimensionName(item) }}</strong>
          <b>{{ profileDimensionScore(item) }}</b>
          <UIcon name="i-lucide-arrow-up-right" />
        </button>
      </div>

      <article v-if="insight" id="profile-dimension-stage" class="profile-dimension-stage" role="tabpanel" aria-label="当前能力维度详情" :style="stageStyle">
        <span class="profile-dimension-watermark" aria-hidden="true">{{ activeScore }}</span>
        <div class="profile-dimension-stage-copy">
          <p>{{ insight.stage }}</p>
          <h3>{{ insight.name }}</h3>
          <blockquote>{{ insight.interpretation }}</blockquote>
          <div class="profile-dimension-facts">
            <span>八维排名 <strong>#{{ insight.rank }}</strong></span>
            <span>个人均值 <strong>{{ insight.average.toFixed(1) }}</strong></span>
            <span>相对均值 <strong>{{ insight.delta >= 0 ? '+' : '' }}{{ insight.delta.toFixed(1) }}</strong></span>
          </div>
        </div>

        <div class="profile-dimension-ruler" aria-label="能力得分">
          <span>尚未证明</span><i><b /></i><strong>{{ activeScore }} / 100</strong><span>证据充分</span>
        </div>

        <div class="profile-dimension-insight-grid">
          <section><span>当前判断</span><p>{{ insight.judgement }}</p></section>
          <section><span>关键缺口</span><p>{{ insight.gap }}</p></section>
          <section class="profile-dimension-evidence"><span>材料与线索</span><div><b v-for="source in insight.sources" :key="source">{{ source }}</b><i v-for="clue in insight.evidenceClues" :key="clue">{{ clue }}</i><em v-if="!insight.evidenceClues.length">材料中尚未提取到明确关键词，当前判断来自综合评分</em></div></section>
          <section class="profile-dimension-actions"><span>下一步行动</span><ol><li v-for="action in insight.actions" :key="action">{{ action }}</li></ol></section>
          <section><span>应留下的证据</span><p>{{ insight.expectedEvidence }}</p></section>
          <section><span>完成标准</span><p>{{ insight.successMetric }}</p></section>
        </div>
      </article>
    </div>
    <p v-else class="profile-dimension-empty">暂无维度详细分析</p>
  </section>
</template>

<style>
.profile-dimension-atlas{display:grid;gap:1.2rem;padding:2rem 0}.profile-dimension-atlas>header{display:flex;align-items:end;justify-content:space-between;gap:1rem;padding:0 1rem}.profile-dimension-atlas>header span{color:var(--pathfy-capability);font-size:.65rem;font-weight:850;letter-spacing:.1em}.profile-dimension-atlas h2{margin-top:.25rem;font-size:1.25rem;font-weight:770}.profile-dimension-atlas>header p{max-width:34rem;color:var(--ui-text-muted);font-size:.75rem;line-height:1.6;text-align:right}.profile-dimension-browser{display:grid;grid-template-columns:minmax(13rem,.25fr) minmax(0,1fr);min-height:43rem;overflow:hidden;border:1px solid var(--pathfy-line);border-radius:1.75rem;background:color-mix(in srgb,var(--pathfy-capability) 3%,var(--ui-bg));box-shadow:0 30px 70px -58px rgb(15 23 42/.8)}.profile-dimension-index-list{display:grid;align-content:center;padding:1.2rem 0;background:color-mix(in srgb,var(--ui-bg-elevated) 82%,transparent)}.profile-dimension-index-list button{display:grid;grid-template-columns:1.7rem minmax(0,1fr) 2rem 1rem;gap:.6rem;align-items:center;border:0;border-left:3px solid transparent;background:transparent;padding:.7rem 1rem .7rem .8rem;color:var(--ui-text-muted);text-align:left;transition:background .18s ease,border-color .18s ease,color .18s ease}.profile-dimension-index-list button:hover,.profile-dimension-index-list button.active{border-left-color:var(--pathfy-capability);background:color-mix(in srgb,var(--pathfy-capability) 8%,transparent);color:var(--ui-text)}.profile-dimension-index-list button>span{font:750 .63rem ui-monospace,monospace}.profile-dimension-index-list button>strong{font-size:.75rem}.profile-dimension-index-list button>b{color:var(--pathfy-capability);font:750 .72rem ui-monospace,monospace;text-align:right}.profile-dimension-index-list button>svg{width:.85rem;opacity:0;transform:translate(-.2rem,.2rem);transition:opacity .16s ease,transform .16s ease}.profile-dimension-index-list button.active>svg{opacity:1;transform:none}.profile-dimension-stage{position:relative;display:grid;align-content:start;min-width:0;overflow:hidden;padding:clamp(2rem,4vw,3rem);background:radial-gradient(circle at 78% 20%,color-mix(in srgb,var(--pathfy-capability) 13%,transparent),transparent 27%),linear-gradient(135deg,color-mix(in srgb,var(--pathfy-capability) 6%,transparent),transparent 48%)}.profile-dimension-watermark{position:absolute;top:-2.8rem;right:1rem;color:color-mix(in srgb,var(--pathfy-capability) 7%,transparent);font:800 clamp(10rem,20vw,18rem)/1 ui-monospace,monospace;letter-spacing:-.1em}.profile-dimension-stage-copy{position:relative;z-index:1;max-width:48rem}.profile-dimension-stage-copy>p{color:var(--pathfy-capability);font-size:.7rem;font-weight:850;letter-spacing:.1em}.profile-dimension-stage-copy h3{margin-top:.5rem;font-size:clamp(2rem,4vw,3.7rem);font-weight:790;letter-spacing:-.06em;line-height:1}.profile-dimension-stage-copy blockquote{max-width:43rem;margin-top:1rem;color:var(--ui-text-muted);font-size:.85rem;line-height:1.8}.profile-dimension-facts{display:flex;flex-wrap:wrap;gap:.55rem;margin-top:1rem}.profile-dimension-facts span{border:1px solid var(--pathfy-line);border-radius:999px;background:color-mix(in srgb,var(--ui-bg) 72%,transparent);padding:.4rem .65rem;color:var(--ui-text-muted);font-size:.66rem}.profile-dimension-facts strong{margin-left:.2rem;color:var(--pathfy-capability)}.profile-dimension-ruler{position:relative;z-index:1;display:grid;grid-template-columns:auto minmax(7rem,1fr) auto auto;gap:.7rem;align-items:center;max-width:48rem;margin:1.5rem 0;color:var(--ui-text-muted);font-size:.62rem}.profile-dimension-ruler>i{height:4px;background:var(--pathfy-line)}.profile-dimension-ruler>i b{display:block;width:var(--dimension-score);height:100%;background:var(--pathfy-capability);box-shadow:0 0 12px color-mix(in srgb,var(--pathfy-capability) 40%,transparent)}.profile-dimension-ruler>strong{color:var(--pathfy-capability);font:760 .8rem ui-monospace,monospace}.profile-dimension-insight-grid{position:relative;z-index:1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}.profile-dimension-insight-grid section{border:1px solid var(--pathfy-line);border-radius:.9rem;background:color-mix(in srgb,var(--ui-bg) 72%,transparent);padding:.85rem 1rem}.profile-dimension-insight-grid section>span{display:block;margin-bottom:.42rem;color:var(--pathfy-capability);font-size:.62rem;font-weight:850;letter-spacing:.08em}.profile-dimension-insight-grid p,.profile-dimension-insight-grid li{color:var(--ui-text-muted);font-size:.72rem;line-height:1.65}.profile-dimension-evidence>div{display:flex;flex-wrap:wrap;gap:.35rem}.profile-dimension-evidence b,.profile-dimension-evidence i{border-radius:999px;padding:.28rem .48rem;font-size:.62rem;font-style:normal}.profile-dimension-evidence b{border:1px solid var(--pathfy-line);color:var(--ui-text-muted)}.profile-dimension-evidence i{background:color-mix(in srgb,var(--pathfy-capability) 12%,transparent);color:var(--pathfy-capability)}.profile-dimension-evidence em{color:var(--ui-text-muted);font-size:.68rem;font-style:normal;line-height:1.5}.profile-dimension-actions ol{display:grid;gap:.28rem;counter-reset:action}.profile-dimension-actions li{display:grid;grid-template-columns:1rem 1fr;gap:.35rem}.profile-dimension-actions li::before{counter-increment:action;content:counter(action);color:var(--pathfy-capability);font:750 .62rem ui-monospace,monospace}.profile-dimension-empty{padding:1rem;color:var(--ui-text-muted);font-size:.75rem}@media(max-width:900px){.profile-dimension-browser{grid-template-columns:1fr;min-height:auto}.profile-dimension-index-list{grid-template-columns:repeat(8,minmax(7rem,1fr));overflow-x:auto;padding:0}.profile-dimension-index-list button{grid-template-columns:auto 1fr;border-left:0;border-bottom:3px solid transparent;padding:.85rem}.profile-dimension-index-list button:hover,.profile-dimension-index-list button.active{border-bottom-color:var(--pathfy-capability)}.profile-dimension-index-list button>b,.profile-dimension-index-list button>svg{display:none}.profile-dimension-stage{min-height:auto}}@media(max-width:620px){.profile-dimension-atlas>header{align-items:start;flex-direction:column}.profile-dimension-atlas>header p{text-align:left}.profile-dimension-browser{border-radius:1.2rem}.profile-dimension-stage{padding:2rem 1.2rem}.profile-dimension-ruler{grid-template-columns:auto minmax(4rem,1fr) auto}.profile-dimension-ruler>span:last-child{display:none}.profile-dimension-insight-grid{grid-template-columns:1fr}}
</style>
