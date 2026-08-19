<script setup lang="ts">defineProps<{ content?: string }>()</script>
<template><UCard v-if="content"><template #header><h2 class="font-semibold">压力应对</h2></template><p class="leading-7 muted">{{ content }}</p></UCard></template>
