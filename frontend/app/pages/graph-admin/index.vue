<script setup lang="ts">
definePageMeta({ middleware: 'admin' })
useSeoMeta({ title: '图谱 Dashboard' })
const graph = useGraphTasksApi()
const toast = useToast()
const stats = ref<Record<string, number>>({})
const guard = ref<any>()
const recent = ref<any[]>([])
const counts = ref({ queued: 0, running: 0, awaiting_confirmation: 0, failed: 0 })
async function load() {
  try {
    const [statData, guardData, recentData, queued, running, waiting, failed] = await Promise.all([
      graph.stats(), graph.guard(), graph.tasks(), graph.tasks({ status: 'queued' }),
      graph.tasks({ status: 'running' }), graph.tasks({ status: 'awaiting_confirmation' }),
      graph.tasks({ status: 'failed' })
    ])
    stats.value = statData; guard.value = guardData; recent.value = recentData.items || []
    counts.value = { queued: queued.total, running: running.total, awaiting_confirmation: waiting.total, failed: failed.total }
  } catch (e) { toast.add({ title: String(e), color: 'error' }) }
}
onMounted(load)
</script>

<template>
  <div class="page-stack">
    <GraphAdminNav />
    <GraphGuardBanner :guard="guard" />
    <div class="page-heading"><h1>图谱 Dashboard</h1><p class="muted">图谱状态、版本和任务概览</p></div>
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <UCard><p class="text-sm muted">图谱版本</p><p class="mt-2 text-3xl font-bold">{{ guard?.graph_revision ?? '-' }}</p></UCard>
      <UCard v-for="(value,key) in counts" :key="key"><p class="text-sm muted">{{ key }}</p><p class="mt-2 text-3xl font-bold">{{ value }}</p></UCard>
      <UCard v-for="(value,key) in stats" :key="key"><p class="text-sm muted">{{ key }}</p><p class="mt-2 text-3xl font-bold">{{ value }}</p></UCard>
    </div>
    <UCard><template #header><div class="flex justify-between"><h2 class="font-semibold">最近任务</h2><UButton to="/graph-admin/tasks" variant="ghost">查看全部</UButton></div></template><UTable v-if="recent.length" :data="recent.slice(0,8)" /><UEmpty v-else title="暂无任务" /></UCard>
  </div>
</template>
