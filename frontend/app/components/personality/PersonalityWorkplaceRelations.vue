<script setup lang="ts">defineProps<{ items: string[] }>()</script>
<template><UCard v-if="items.length"><template #header><h2 class="font-semibold">职场关系</h2></template><ul class="list-disc space-y-2 pl-5"><li v-for="x in items" :key="x">{{ x }}</li></ul></UCard></template>
