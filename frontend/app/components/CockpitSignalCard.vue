<script setup lang="ts">
withDefaults(defineProps<{ label: string; value: string | number; description: string; icon: string; tone?: 'capability' | 'gap' | 'success' | 'risk' | 'route' | 'evidence' }>(), { tone: 'capability' })
</script>

<template>
  <article class="cockpit-signal" :data-tone="tone"><div class="cockpit-signal-label"><UIcon :name="icon" class="size-4" /><span>{{ label }}</span></div><strong class="cockpit-signal-value" :title="String(value)">{{ value }}</strong><p class="cockpit-signal-description">{{ description }}</p></article>
</template>
