<script setup lang="ts">
import { profileText } from '~/utils/profile-display'
const props = defineProps<{ items: unknown }>()
const keywords = computed(() => (Array.isArray(props.items) ? props.items : props.items ? [props.items] : []).map(profileText).filter(Boolean))
</script>

<template>
  <aside class="profile-keyword-cloud" aria-labelledby="profile-keyword-heading">
    <header><span>MATERIAL VOICE</span><h2 id="profile-keyword-heading">材料关键词分析</h2><p>你的材料反复提到什么？</p></header>
    <div class="profile-keyword-list">
      <span v-for="(keyword, index) in keywords" :key="`${keyword}-${index}`"><b>{{ String(index + 1).padStart(2, '0') }}</b>{{ keyword }}</span>
      <p v-if="!keywords.length">暂无材料关键词</p>
    </div>
    <footer><i /><span>经历 · 能力 · 方向</span></footer>
  </aside>
</template>

<style>
.profile-keyword-cloud{position:relative;z-index:2;min-width:0;margin:1.3rem 0 1.3rem -2.2rem;border:1px solid color-mix(in srgb,#c99e38 30%,var(--pathfy-line));border-radius:.25rem;background:#f1e4aa;padding:1.6rem 1.35rem 1.3rem;color:#334243;box-shadow:0 20px 38px -30px rgb(15 23 42/.8);transform:rotate(1.2deg)}
.profile-keyword-cloud::before{content:"";position:absolute;top:-.55rem;left:34%;width:4.5rem;height:1.05rem;background:rgb(255 255 255/.62);box-shadow:0 2px 8px rgb(15 23 42/.08);transform:rotate(-5deg)}
.profile-keyword-cloud header span{color:#8b6815;font-size:.6rem;font-weight:850;letter-spacing:.1em}
.profile-keyword-cloud h2{margin-top:.22rem;font-size:1.05rem;font-weight:770}
.profile-keyword-cloud header p{margin-top:.35rem;color:#555943;font-size:.69rem}
.profile-keyword-list{display:grid;gap:.15rem;margin:1.15rem 0}
.profile-keyword-list span{display:grid;grid-template-columns:1.6rem minmax(0,1fr);gap:.45rem;padding:.46rem 0;border-bottom:1px solid rgb(70 70 45/.15);font-size:.7rem;font-weight:680;line-height:1.45}
.profile-keyword-list b{color:#8b6815;font:750 .58rem ui-monospace,monospace}
.profile-keyword-list p{color:#6d735f;font-size:.7rem}
.profile-keyword-cloud footer{display:flex;align-items:center;gap:.6rem;color:#79785f;font-size:.59rem;letter-spacing:.08em}
.profile-keyword-cloud footer i{height:1px;flex:1;background:rgb(70 70 45/.18)}
@media(max-width:767px){.profile-keyword-cloud{width:calc(100% - 1.4rem);margin:-.2rem auto 0;transform:rotate(.5deg)}}
</style>
