<script setup lang="ts">
import { profileItems, profileText } from '~/utils/profile-display'
defineProps<{ items: unknown }>()
</script>

<template>
  <section class="profile-industry-field" aria-labelledby="profile-industry-heading">
    <header><div><span>OPPORTUNITY FIELD</span><h2 id="profile-industry-heading">行业适配性分析</h2></div><UIcon name="i-lucide-compass" /></header>
    <p class="profile-industry-intro">结合能力结构，寻找更容易发挥优势的行业场景。</p>
    <div class="profile-industry-list">
      <article v-for="(item, index) in profileItems(items)" :key="index">
        <span>{{ String(Number(index) + 1).padStart(2, '0') }}</span>
        <div><h3>{{ item.industry || item.name || item.field || '适配方向' }}</h3><p>{{ profileText(item) }}</p></div>
        <strong v-if="item.match_score || item.score">{{ item.match_score || item.score }}</strong>
      </article>
      <p v-if="!profileItems(items).length" class="profile-industry-empty">暂无行业适配分析</p>
    </div>
  </section>
</template>

<style>
.profile-industry-field{position:relative;z-index:1;min-width:0;border:1px solid color-mix(in srgb,#c7b890 34%,var(--pathfy-line));border-radius:.2rem;background:linear-gradient(90deg,transparent 3rem,color-mix(in srgb,#c56b5d 17%,transparent) 3.05rem,transparent 3.1rem),repeating-linear-gradient(0deg,transparent 0,transparent 2.45rem,color-mix(in srgb,#7795a4 13%,transparent) 2.5rem),#f5f0df;padding:1.8rem 2rem 2rem 3.8rem;color:#263d40;box-shadow:0 18px 34px -28px rgb(15 23 42/.8);transform:rotate(-.35deg)}
.profile-industry-field::after{content:"ARCHIVE / 03";position:absolute;right:1.1rem;bottom:.7rem;color:rgb(38 61 64/.24);font:750 .58rem ui-monospace,monospace;letter-spacing:.12em}
.profile-industry-field header{display:flex;align-items:center;justify-content:space-between;gap:1rem}
.profile-industry-field header span{color:#087c80;font-size:.61rem;font-weight:850;letter-spacing:.1em}
.profile-industry-field h2{margin-top:.2rem;font-size:1.12rem;font-weight:770}
.profile-industry-field header svg{width:2.1rem;height:2.1rem;border:1px solid rgb(38 61 64/.2);border-radius:50%;padding:.5rem;color:#087c80}
.profile-industry-intro{margin:.65rem 0 1.2rem;color:#66797a;font-size:.7rem}
.profile-industry-list{display:grid;grid-template-columns:1fr 1fr;gap:0 1.6rem}
.profile-industry-list article{display:grid;grid-template-columns:1.6rem minmax(0,1fr) auto;gap:.65rem;align-items:start;min-width:0;padding:.72rem 0;border-bottom:1px solid rgb(38 61 64/.14)}
.profile-industry-list article>span{padding-top:.08rem;color:#087c80;font:750 .6rem ui-monospace,monospace}
.profile-industry-list article>div{min-width:0}
.profile-industry-list h3{font-size:.74rem;font-weight:760}
.profile-industry-list p{margin-top:.24rem;color:#66797a;font-size:.65rem;line-height:1.55}
.profile-industry-list strong{color:#087c80;font:760 .78rem ui-monospace,monospace}
.profile-industry-empty{color:#66797a;font-size:.7rem}
@media(max-width:650px){.profile-industry-field{padding:1.5rem 1rem 1.7rem 2rem}.profile-industry-list{grid-template-columns:1fr}}
</style>
