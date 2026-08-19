<script setup lang="ts">
defineProps<{ mbti?: string; name?: string; summary?: string }>()
const slots = useSlots()
</script>

<template>
  <UCard>
    <div class="personality-hero" :class="{ 'personality-hero--with-visual': slots.visual }">
      <div class="personality-hero-copy">
        <p class="text-5xl font-bold text-primary">{{ mbti || 'MBTI' }}</p>
        <h2 class="mt-3 text-xl font-semibold">{{ name || '性格分析' }}</h2>
        <p v-if="summary" class="mt-4 leading-7 muted">{{ summary }}</p>
      </div>
      <div v-if="slots.visual" class="personality-hero-visual">
        <slot name="visual" />
      </div>
    </div>
  </UCard>
</template>

<style scoped>
.personality-hero { text-align: center; }
.personality-hero-copy { min-width: 0; }
.personality-hero-copy > p:last-child { max-width: 48rem; margin-inline: auto; }
.personality-hero--with-visual { display: grid; grid-template-columns: minmax(0, .9fr) minmax(320px, 1.1fr); align-items: center; gap: 1.4rem; text-align: left; }
.personality-hero--with-visual .personality-hero-copy > p:last-child { margin-inline: 0; }
.personality-hero-visual { min-width: 0; }
@media (max-width: 760px) {
  .personality-hero--with-visual { grid-template-columns: 1fr; text-align: center; }
  .personality-hero--with-visual .personality-hero-copy > p:last-child { margin-inline: auto; }
}
</style>
