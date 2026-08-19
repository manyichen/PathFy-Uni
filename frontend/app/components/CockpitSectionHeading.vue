<script setup lang="ts">
defineProps<{ kicker: string; title: string; description?: string }>()
</script>

<template>
  <div class="cockpit-section-heading">
    <div class="cockpit-section-heading-copy"><p class="cockpit-section-kicker">{{ kicker }}</p><h2>{{ title }}</h2><p v-if="description">{{ description }}</p></div>
    <slot name="actions" />
  </div>
</template>
