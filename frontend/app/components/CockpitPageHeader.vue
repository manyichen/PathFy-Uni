<script setup lang="ts">
withDefaults(defineProps<{
  eyebrow: string
  title: string
  description: string
  icon: string
  mark?: string
  edition?: string
  editionLabel?: string
}>(), {
  mark: '00',
  edition: 'PATHFY',
  editionLabel: '职业档案'
})
</script>

<template>
  <header class="cockpit-page-header">
    <div class="cockpit-page-copy">
      <p class="cockpit-eyebrow">{{ eyebrow }}</p>
      <div class="cockpit-title-row"><h1>{{ title }}</h1></div>
      <p class="cockpit-page-description">{{ description }}</p>
    </div>
    <span class="cockpit-page-mark" aria-hidden="true">{{ mark }}</span>
    <div class="cockpit-page-aside">
      <div class="cockpit-page-edition">
        <UIcon :name="icon" aria-hidden="true" />
        <span>{{ edition }}<strong>{{ editionLabel }}</strong></span>
      </div>
    </div>
    <div v-if="$slots.actions" class="cockpit-page-actions"><slot name="actions" /></div>
  </header>
</template>
