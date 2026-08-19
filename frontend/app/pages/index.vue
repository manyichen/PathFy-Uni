<script setup lang="ts">
useSeoMeta({
  title: '首页',
  description: '基于岗位图谱、能力证据、工作偏好和 AI 分析的大学生职业规划工作台'
})
</script>

<template>
  <div class="home-page">
    <HomeHero />
    <CockpitStageRail variant="journey" />
    <HomeProcessFlow />
    <HomePlanningWorkbench />
  </div>
</template>

<style scoped>
.home-page {
  display: grid;
  gap: 3.5rem;
  padding-bottom: 2rem;
}
</style>

<style>
.home-editorial-heading {
  display: grid;
  grid-template-columns: auto minmax(0, 1.25fr) minmax(16rem, .75fr);
  gap: 1.25rem;
  align-items: end;
}

.home-editorial-mark {
  display: grid;
  align-self: stretch;
  grid-template-rows: auto 1fr;
  justify-items: center;
  color: var(--pathfy-capability);
  font: 800 .75rem/1 ui-monospace, SFMono-Regular, Menlo, monospace;
}

.home-editorial-mark i {
  width: 1px;
  margin-top: .55rem;
  background: color-mix(in srgb, var(--pathfy-capability) 35%, var(--ui-border));
}

.home-editorial-kicker {
  margin-bottom: .45rem;
  color: var(--pathfy-capability);
  font-size: .76rem;
  font-weight: 800;
  letter-spacing: .08em;
}

.home-editorial-title h2 {
  max-width: 44rem;
  font-size: clamp(1.65rem, 3vw, 2.55rem);
  font-weight: 780;
  letter-spacing: -.035em;
  line-height: 1.18;
}

.home-editorial-note {
  border-left: 1px solid var(--ui-border);
  padding-left: 1rem;
  color: var(--ui-text-muted);
  font-size: .88rem;
  line-height: 1.75;
}

@media (max-width: 767px) {
  .home-editorial-heading { grid-template-columns: auto 1fr; }
  .home-editorial-note { grid-column: 2; border-left: 0; padding-left: 0; }
}
</style>
