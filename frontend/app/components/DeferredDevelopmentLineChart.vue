<script setup lang="ts">
import type { DevelopmentLine } from '~/types/api'
defineProps<{ lines: DevelopmentLine[] }>()
</script>

<template><ChartDeferredMount height="390px"><LazyDevelopmentLineChart :lines="lines" /></ChartDeferredMount></template>
