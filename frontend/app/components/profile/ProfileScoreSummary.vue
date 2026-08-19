<script setup lang="ts">
defineProps<{ completeness?: number; competitiveness?: number; completenessText?: string; competitivenessText?: string }>()
</script>
<template><aside class="profile-score-ledger" aria-labelledby="profile-score-heading"><header><span>03 / CALIBRATE</span><h2 id="profile-score-heading">画像刻度</h2><p>分数不是终点，而是下一轮补充证据的坐标。</p></header><div v-for="metric in [{label:'能力完整度',value:completeness,text:completenessText,fallback:'覆盖材料越丰富，完整度评估越可靠。',code:'CPL'},{label:'就业竞争力',value:competitiveness,text:competitivenessText,fallback:'综合八维能力与就业场景给出竞争力判断。',code:'CMP'}]" :key="metric.code" class="profile-score-metric"><div class="profile-score-number"><small>{{ metric.code }}</small><strong>{{ Math.round(metric.value || 0) }}</strong><span>/100</span></div><div class="profile-score-copy"><div><b>{{ metric.label }}</b><span>{{ Math.round(metric.value || 0) >= 80 ? '稳定区' : '生长区' }}</span></div><div class="profile-score-track"><i :style="{width:`${Math.max(0,Math.min(100,metric.value || 0))}%`}" /></div><p>{{ metric.text || metric.fallback }}</p></div></div><footer><UIcon name="i-lucide-refresh-cw" /><span>新材料会重新校准全部刻度</span></footer></aside></template>

<style>
.profile-score-ledger { min-width:0; display:flex; flex-direction:column; padding:1.25rem; background:#073b49; color:white; }
.profile-score-ledger header { padding-bottom:1rem; border-bottom:1px solid rgb(255 255 255/.18); }
.profile-score-ledger header span { color:#c9e3e8; font-size:.63rem; font-weight:800; letter-spacing:.08em; }
.profile-score-ledger h2 { margin-top:.18rem; font-size:1.05rem; font-weight:750; }.profile-score-ledger header p { margin-top:.5rem; color:#d1e6ea; font-size:.75rem; line-height:1.6; }
.profile-score-metric { display:grid; grid-template-columns:4.25rem 1fr; gap:.75rem; padding:1.15rem 0; border-bottom:1px solid rgb(255 255 255/.14); }
.profile-score-number { display:grid; align-content:start; }.profile-score-number small { color:#bdd9df; font-size:.58rem; letter-spacing:.1em; }.profile-score-number strong { font:700 2.25rem/1 ui-monospace,SFMono-Regular,monospace; }.profile-score-number span { color:#bdd9df; font-size:.6rem; }
.profile-score-copy>div:first-child { display:flex; justify-content:space-between; gap:.5rem; font-size:.78rem; }.profile-score-copy>div:first-child span { color:#a8f5e4; font-size:.65rem; }
.profile-score-track { height:3px; margin:.65rem 0; background:rgb(255 255 255/.18); }.profile-score-track i { display:block; height:100%; background:#7ee7d1; box-shadow:0 0 12px #7ee7d1; }
.profile-score-copy p { color:#d1e6ea; font-size:.7rem; line-height:1.6; }.profile-score-ledger footer { display:flex; align-items:center; gap:.45rem; margin-top:auto; padding-top:1rem; color:#c5dfe4; font-size:.65rem; }
</style>
