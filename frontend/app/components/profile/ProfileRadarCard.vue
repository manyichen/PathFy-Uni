<script setup lang="ts">
import type { CapabilityScorePatch } from '~/types/capability'
defineProps<{ scores: CapabilityScorePatch; resumeId?: number }>()
</script>
<template><section class="profile-radar-board" aria-labelledby="profile-radar-heading"><header><div><span>02 / READ</span><h2 id="profile-radar-heading">八维能力星盘</h2></div><span v-if="resumeId" class="profile-radar-id">画像 #{{ resumeId }}</span></header><div class="profile-radar-stage"><span class="profile-radar-axis axis-n">专业</span><span class="profile-radar-axis axis-e">协同</span><span class="profile-radar-axis axis-s">成长</span><span class="profile-radar-axis axis-w">实践</span><DeferredCapabilityRadar :scores="scores" height="340px" /></div><footer><span>材料证据</span><i /><span>能力轮廓</span><i /><span>职业方向</span></footer></section></template>

<style>
.profile-radar-board { min-width:0; padding:1.25rem 1.35rem; border-right:1px solid var(--pathfy-line); border-left:1px solid var(--pathfy-line); background:radial-gradient(circle at 50% 45%,color-mix(in srgb,var(--pathfy-evidence) 10%,transparent),transparent 48%); }
.profile-radar-board header,.profile-radar-board footer { display:flex; align-items:center; justify-content:space-between; gap:.75rem; }
.profile-radar-board header span:first-child,.profile-radar-board footer { color:var(--ui-text-muted); font-size:.63rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
.profile-radar-board h2 { margin-top:.18rem; font-size:1.05rem; font-weight:750; }
.profile-radar-id { border:1px solid var(--pathfy-line); border-radius:999px; padding:.3rem .55rem; color:var(--pathfy-capability); font-size:.68rem; font-weight:750; }
.profile-radar-stage { position:relative; min-height:340px; }
.profile-radar-axis { position:absolute; z-index:1; color:var(--ui-text-muted); font-size:.58rem; letter-spacing:.12em; writing-mode:vertical-rl; }
.axis-n { top:1rem; left:50%; writing-mode:horizontal-tb; transform:translateX(-50%); }.axis-e { top:50%; right:0; }.axis-s { bottom:.7rem; left:50%; writing-mode:horizontal-tb; transform:translateX(-50%); }.axis-w { top:50%; left:0; transform:rotate(180deg); }
.profile-radar-board footer { justify-content:center; padding-top:.75rem; border-top:1px solid var(--pathfy-line); }
.profile-radar-board footer i { width:1.7rem; height:1px; background:var(--pathfy-line); }
@media(max-width:1099px){.profile-radar-board{border-right:0;border-left:0;border-top:1px solid var(--pathfy-line);border-bottom:1px solid var(--pathfy-line)}}
</style>
