<script setup lang="ts">
import { profileDimensionName, profileDimensionScore, profileItems } from '~/utils/profile-display'

defineProps<{ materials: Record<string, unknown>[]; advantages: unknown; weaknesses: unknown }>()
</script>

<template>
  <section class="profile-evidence-map" aria-labelledby="profile-evidence-map-heading">
    <header>
      <div><span>EVIDENCE LEDGER</span><h2 id="profile-evidence-map-heading">证据收支簿</h2></div>
      <p>同一份材料既能支撑优势，也可能暴露尚未被证明的能力。</p>
    </header>
    <div class="profile-evidence-columns">
      <section class="profile-source-column">
        <div class="profile-column-title"><span>IN / {{ materials.length }}</span><h3>材料来源</h3></div>
        <ol>
          <li v-for="(item, index) in materials" :key="`${item.name}-${index}`">
            <span>{{ String(index + 1).padStart(2, '0') }}</span>
            <div><strong>{{ item.name || '补充文本' }}</strong><p>{{ item.kind || '材料' }}<template v-if="item.chars"> · {{ item.chars }} 字</template></p></div>
            <small>{{ item.status === 'ok' ? '已识别' : String(item.status || '已使用') }}</small>
          </li>
          <li v-if="!materials.length" class="profile-list-empty">暂无材料来源记录</li>
        </ol>
      </section>
      <div class="profile-evidence-fork" aria-hidden="true"><i /><span>解析</span><i /></div>
      <section class="profile-outcome-column">
        <div class="profile-outcome-group is-strength">
          <div class="profile-column-title"><span>KEEP</span><h3>优势维度</h3></div>
          <div v-for="item in profileItems(advantages)" :key="profileDimensionName(item)" class="profile-evidence-result">
            <strong>{{ profileDimensionName(item) }}</strong><span>{{ profileDimensionScore(item) }}</span><i :style="{ width: `${Math.min(100, Math.max(0, profileDimensionScore(item)))}%` }" />
          </div>
          <p v-if="!profileItems(advantages).length" class="profile-list-empty">暂无优势维度数据</p>
        </div>
        <div class="profile-outcome-group is-gap">
          <div class="profile-column-title"><span>GROW</span><h3>待提升维度</h3></div>
          <div v-for="item in profileItems(weaknesses)" :key="profileDimensionName(item)" class="profile-evidence-result">
            <strong>{{ profileDimensionName(item) }}</strong><span>{{ profileDimensionScore(item) }}</span><i :style="{ width: `${Math.min(100, Math.max(0, profileDimensionScore(item)))}%` }" />
          </div>
          <p v-if="!profileItems(weaknesses).length" class="profile-list-empty">暂无待提升维度数据</p>
        </div>
      </section>
    </div>
  </section>
</template>

<style>
.profile-evidence-map{position:relative;overflow:hidden;border:1px solid var(--pathfy-line);border-radius:1.75rem;background:linear-gradient(135deg,color-mix(in srgb,var(--pathfy-capability) 5%,var(--ui-bg-elevated)),var(--ui-bg-elevated));padding:1.4rem 1.4rem 1.8rem;box-shadow:0 28px 65px -58px rgb(15 23 42/.8)}
.profile-evidence-map::before{content:"";position:absolute;inset:0;background:repeating-linear-gradient(90deg,transparent 0,transparent 9.9%,color-mix(in srgb,var(--pathfy-line) 25%,transparent) 10%);opacity:.2;pointer-events:none}
.profile-evidence-map>header{position:relative;z-index:1;display:flex;align-items:end;justify-content:space-between;gap:1rem;padding:.2rem .4rem 1.3rem}
.profile-evidence-map>header span,.profile-column-title span{color:var(--pathfy-capability);font-size:.61rem;font-weight:850;letter-spacing:.1em}
.profile-evidence-map h2{margin-top:.2rem;font-size:1.16rem;font-weight:770}
.profile-evidence-map>header p{max-width:26rem;color:var(--ui-text-muted);font-size:.72rem;line-height:1.6;text-align:right}
.profile-evidence-columns{position:relative;z-index:1;display:grid;grid-template-columns:minmax(15rem,.82fr) 4.5rem minmax(0,1.18fr);align-items:stretch}
.profile-column-title{display:flex;align-items:baseline;justify-content:space-between;gap:.75rem;margin-bottom:.9rem}
.profile-column-title h3{font-size:.83rem;font-weight:760}
.profile-source-column{position:relative;margin:.5rem 0;padding:1.7rem 1.4rem 1.5rem;border:1px solid color-mix(in srgb,#c7b890 34%,var(--pathfy-line));border-radius:.2rem;background:linear-gradient(90deg,transparent 2.4rem,color-mix(in srgb,#c56b5d 20%,transparent) 2.45rem,transparent 2.5rem),repeating-linear-gradient(0deg,transparent 0,transparent 2rem,color-mix(in srgb,#7795a4 14%,transparent) 2.05rem),#f5f0df;color:#263d40;box-shadow:0 16px 30px -26px rgb(15 23 42/.7);transform:rotate(-.45deg)}
.profile-source-column::before{content:"MATERIAL LOG";position:absolute;right:1rem;bottom:.6rem;color:rgb(38 61 64/.25);font:750 .56rem ui-monospace,monospace;letter-spacing:.12em}
.profile-source-column ol{display:grid}
.profile-source-column li{display:grid;grid-template-columns:1.65rem minmax(0,1fr) auto;gap:.7rem;align-items:center;min-width:0;padding:.68rem 0;border-bottom:1px solid rgb(38 61 64/.12)}
.profile-source-column li>span{color:#087c80;font:750 .6rem ui-monospace,monospace}
.profile-source-column li>div{min-width:0}
.profile-source-column strong{display:block;overflow:hidden;font-size:.75rem;text-overflow:ellipsis;white-space:nowrap}
.profile-source-column p,.profile-source-column small{color:#66797a;font-size:.62rem}
.profile-source-column small{border:1px solid rgb(38 61 64/.16);border-radius:999px;padding:.18rem .42rem;white-space:nowrap}
.profile-evidence-fork{position:relative;display:grid;place-items:center;color:var(--pathfy-capability);font-size:.58rem;font-weight:850;letter-spacing:.08em}
.profile-evidence-fork::before{content:"";position:absolute;top:50%;right:.7rem;left:.7rem;border-top:1px dashed color-mix(in srgb,var(--pathfy-capability) 45%,var(--pathfy-line))}
.profile-evidence-fork span{z-index:1;border:1px solid color-mix(in srgb,var(--pathfy-capability) 32%,var(--pathfy-line));border-radius:999px;background:var(--ui-bg-elevated);padding:.35rem .45rem}
.profile-evidence-fork i{display:none}
.profile-outcome-column{display:grid;grid-template-columns:1fr 1fr;gap:1px;overflow:hidden;border:1px solid var(--pathfy-line);border-radius:1rem;background:var(--pathfy-line)}
.profile-outcome-group{display:grid;grid-template-columns:minmax(0,1fr);align-content:start;gap:0;background:var(--ui-bg);padding:1.4rem 1.2rem}
.profile-outcome-group.is-gap{background:color-mix(in srgb,var(--pathfy-gap) 4%,var(--ui-bg))}
.profile-evidence-result{position:relative;display:grid;grid-template-columns:minmax(0,1fr) 2rem;gap:.6rem;align-items:center;padding:.72rem 0 .85rem;border-bottom:1px solid var(--pathfy-line)}
.profile-evidence-result strong{font-size:.71rem;font-weight:700}
.profile-evidence-result span{color:var(--pathfy-success);font:760 .76rem ui-monospace,monospace;text-align:right}
.is-gap .profile-evidence-result span{color:var(--pathfy-gap)}
.profile-evidence-result i{position:absolute;bottom:-1px;left:0;max-width:100%;height:2px;background:var(--pathfy-success)}
.is-gap .profile-evidence-result i{background:var(--pathfy-gap)}
.profile-list-empty{color:var(--ui-text-muted);font-size:.7rem}
@media(max-width:900px){.profile-evidence-columns{grid-template-columns:1fr}.profile-evidence-fork{height:3rem}.profile-evidence-fork::before{top:.5rem;right:50%;bottom:.5rem;left:auto;border-top:0;border-left:1px dashed color-mix(in srgb,var(--pathfy-capability) 45%,var(--pathfy-line))}}
@media(max-width:620px){.profile-evidence-map{border-radius:1.2rem;padding:1rem}.profile-evidence-map>header{align-items:start;flex-direction:column}.profile-evidence-map>header p{text-align:left}.profile-source-column{padding:1.4rem .8rem}.profile-outcome-column{grid-template-columns:1fr}.profile-source-column li{grid-template-columns:1.4rem minmax(0,1fr)}.profile-source-column small{grid-column:2;width:max-content}}
</style>
