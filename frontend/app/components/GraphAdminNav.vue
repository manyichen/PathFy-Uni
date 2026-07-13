<script setup lang="ts">
const route = useRoute()
const items = [
  { label: 'Dashboard', icon: 'i-lucide-layout-dashboard', to: '/graph-admin' },
  { label: '更新图谱', icon: 'i-lucide-upload', to: '/graph-admin/update' },
  { label: '任务队列', icon: 'i-lucide-history', to: '/graph-admin/tasks' }
]
</script>
<template><div class="flex flex-wrap gap-2"><UButton v-for="item in items" :key="item.to" :to="item.to" :icon="item.icon" color="neutral" :variant="route.path===item.to?'solid':'soft'">{{item.label}}</UButton></div></template>
