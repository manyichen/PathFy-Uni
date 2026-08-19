<template>
  <section class="home-planning-workbench" aria-label="规划入口与生涯报告工作台">
    <HomeFeatureBento />
    <HomeExperienceShowcase />
  </section>
</template>

<style>
.home-planning-workbench {
  display: grid;
  gap: 0;
  overflow: hidden;
  border: 1px solid var(--ui-border);
  border-radius: 1.9rem;
  background: linear-gradient(145deg, color-mix(in srgb, var(--pathfy-capability) 3%, var(--ui-bg)), var(--ui-bg));
  box-shadow: 0 34px 80px -62px rgb(15 23 42 / .82);
}

.home-planning-workbench .module-atlas,
.home-planning-workbench .report-desk {
  padding: clamp(1.25rem, 3vw, 2.5rem);
}

.home-planning-workbench .report-desk {
  border-top: 1px solid var(--ui-border);
}

.home-planning-workbench .module-browser {
  border: 0;
  border-radius: 0;
  box-shadow: none;
}

.home-planning-workbench .workroom {
  border-radius: 0;
  background: transparent;
  padding: 0;
}

@media (max-width: 767px) {
  .home-planning-workbench { border-radius: 1.25rem; }
  .home-planning-workbench .module-atlas,
  .home-planning-workbench .report-desk { padding: 1rem; }
}
</style>
