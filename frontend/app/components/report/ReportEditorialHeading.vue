<script setup lang="ts">
withDefaults(defineProps<{
  index: string
  kicker: string
  titleLines: string[]
  description: string
  tone?: 'action' | 'route' | 'review'
}>(), { tone: 'action' })
</script>

<template>
  <header class="report-editorial-heading" :data-tone="tone">
    <div class="editorial-index" aria-hidden="true"><span>{{ index }}</span><i /></div>
    <div class="editorial-copy">
      <p>{{ kicker }}</p>
      <h2><span v-for="line in titleLines" :key="line">{{ line }}</span></h2>
    </div>
    <p class="editorial-note">{{ description }}</p>
  </header>
</template>

<style scoped>
.report-editorial-heading{--editorial-accent:var(--pathfy-capability);display:grid;grid-template-columns:auto minmax(0,1.45fr) minmax(18rem,.72fr);gap:clamp(.9rem,2.4vw,2rem);align-items:center;padding:.7rem .35rem .9rem}.report-editorial-heading[data-tone='route']{--editorial-accent:var(--pathfy-evidence)}.report-editorial-heading[data-tone='review']{--editorial-accent:var(--pathfy-route)}.editorial-index{display:grid;align-self:stretch;justify-items:center;grid-template-rows:auto 1fr;gap:.5rem;color:var(--editorial-accent)}.editorial-index span{font:850 .78rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em}.editorial-index i{width:1px;min-height:5rem;background:color-mix(in srgb,var(--editorial-accent) 55%,transparent)}.editorial-copy{border-right:1px solid var(--pathfy-line);padding-right:clamp(1rem,3vw,2.2rem)}.editorial-copy>p{color:var(--editorial-accent);font-size:.76rem;font-weight:850;letter-spacing:.12em}.editorial-copy h2{max-width:52rem;margin-top:.55rem;font-size:clamp(2rem,4vw,3.8rem);font-weight:790;letter-spacing:-.06em;line-height:1.03;text-wrap:balance}.editorial-copy h2 span{display:block}.editorial-note{max-width:30rem;color:var(--ui-text-muted);font-size:.9rem;line-height:1.85}@media(max-width:800px){.report-editorial-heading{grid-template-columns:auto 1fr}.editorial-note{grid-column:2}.editorial-copy{border-right:0;padding-right:0}.editorial-copy h2{font-size:clamp(1.85rem,8vw,3rem)}}
</style>
