<script setup lang="ts">
definePageMeta({ middleware: 'admin' })
useSeoMeta({ title: '图谱任务队列' })
const graph = useGraphTasksApi()
const toast = useToast()
const data = ref<any>({ items: [], total: 0 })
const page = ref(1)
const status = ref('all')
const type = ref('all')
const guard = ref<any>()
async function load() {
  try {
    [data.value, guard.value] = await Promise.all([
      graph.tasks({ page: page.value, status: status.value === 'all' ? '' : status.value, task_type: type.value === 'all' ? '' : type.value }),
      graph.guard()
    ])
  } catch (e) { toast.add({ title: String(e), color: 'error' }) }
}
async function cancel(id: number) {
  try { await graph.cancel(id); await load() }
  catch (e) { toast.add({ title: String(e), color: 'error' }) }
}
watch([page, status, type], load)
onMounted(load)
</script>

<template>
  <div class="page-stack">
    <GraphAdminNav />
    <GraphGuardBanner :guard="guard" />
    <div class="page-heading"><h1>历史任务队列</h1><p class="muted">查看排队、执行、待确认及历史任务</p></div>
    <UCard><div class="flex flex-wrap gap-3">
      <USelect v-model="status" :items="[{ label: '全部状态', value: 'all' }, ...['queued','running','awaiting_confirmation','succeeded','partial_failed','failed','rejected','cancelled'].map(x => ({ label: x, value: x }))]" class="w-56" />
      <USelect v-model="type" :items="[{ label: '全部类型', value: 'all' }, { label: '岗位', value: 'job_import' }, { label: '学习资源', value: 'learning_resource_import' }, { label: '竞赛', value: 'competition_import' }]" class="w-56" />
    </div></UCard>
    <div class="grid gap-3">
      <UCard v-for="item in data.items" :key="item.id"><div class="flex flex-wrap items-center justify-between gap-3"><div><div class="flex gap-2"><UBadge :label="item.status" /><UBadge :label="item.task_type" color="neutral" variant="soft" /></div><p class="mt-2 font-medium">#{{ item.id }} · {{ item.input_file_name }}</p><p class="text-sm muted">{{ item.created_at }}</p></div><div class="flex gap-2"><UButton :to="`/graph-admin/tasks/${item.id}`" variant="soft">详情</UButton><UButton v-if="item.status === 'queued'" color="error" variant="ghost" @click="cancel(item.id)">取消</UButton></div></div></UCard>
      <UEmpty v-if="!data.items.length" title="暂无任务" />
    </div>
    <UPagination v-model:page="page" :total="data.total" :items-per-page="20" />
  </div>
</template>
