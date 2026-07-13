<script setup lang="ts">
definePageMeta({ middleware: 'admin' })
useSeoMeta({ title: '图谱任务详情' })
const route = useRoute()
const graph = useGraphTasksApi()
const toast = useToast()
const task = ref<any>()
const guard = ref<any>()
const loading = ref('')
const rejectOpen = ref(false)
const reason = ref('')
let timer: ReturnType<typeof setInterval> | undefined
async function load() {
  try { [task.value, guard.value] = await Promise.all([graph.task(String(route.params.id)), graph.guard()]) }
  catch (e) { toast.add({ title: String(e), color: 'error' }) }
}
async function confirm() {
  loading.value = 'confirm'
  try { await graph.confirm(task.value.id); toast.add({ title: '变更已提交', color: 'success' }); await load() }
  catch (e) { toast.add({ title: String(e), color: 'error' }) }
  finally { loading.value = '' }
}
async function reject() {
  loading.value = 'reject'
  try { await graph.reject(task.value.id, reason.value); rejectOpen.value = false; await load() }
  catch (e) { toast.add({ title: String(e), color: 'error' }) }
  finally { loading.value = '' }
}
onMounted(async () => { await load(); timer = setInterval(() => { if (['queued', 'running', 'applying'].includes(task.value?.status)) load() }, 3000) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="page-stack">
    <GraphAdminNav />
    <GraphGuardBanner :guard="guard" />
    <template v-if="task">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div class="page-heading"><h1>任务 #{{ task.id }}</h1><p class="muted">{{ task.task_type }} · {{ task.input_file_name }}</p></div>
        <div v-if="task.status === 'awaiting_confirmation'" class="flex gap-2">
          <UButton color="error" variant="soft" @click="() => { rejectOpen = true }">拒绝</UButton>
          <UButton :loading="loading === 'confirm'" @click="confirm">确认整单变更</UButton>
        </div>
      </div>
      <div class="grid gap-3 md:grid-cols-3">
        <UCard><p class="muted">状态</p><UBadge class="mt-2" :label="task.status" /></UCard>
        <UCard><p class="muted">来源</p><p class="mt-2 font-medium">{{ task.source_id || '-' }} · {{ task.mode }}</p></UCard>
        <UCard><p class="muted">SHA-256</p><p class="mt-2 break-all text-xs">{{ task.input_sha256 }}</p></UCard>
      </div>
      <UCard><template #header><h2 class="font-semibold">更新摘要</h2></template><pre class="overflow-auto whitespace-pre-wrap text-sm">{{ JSON.stringify(task.change_summary || {}, null, 2) }}</pre></UCard>
      <UCard v-if="task.error_message"><template #header><h2 class="font-semibold text-error">错误</h2></template><p class="whitespace-pre-wrap">{{ task.error_message }}</p></UCard>
      <UCard><template #header><h2 class="font-semibold">任务时间线</h2></template><div class="grid gap-4"><div v-for="event in task.events" :key="event.id" class="border-l-2 border-primary pl-4"><div class="flex justify-between gap-3"><strong>{{ event.message }}</strong><span class="text-xs muted">{{ event.created_at }}</span></div><p class="text-sm muted">{{ event.stage }} · {{ event.event_type }}</p><pre v-if="event.detail" class="mt-2 overflow-auto text-xs">{{ JSON.stringify(event.detail, null, 2) }}</pre></div></div></UCard>
    </template>
    <USkeleton v-else class="h-80" />
    <UModal v-model:open="rejectOpen" title="拒绝变更"><template #body><UTextarea v-model="reason" :rows="5" placeholder="填写拒绝原因" /><div class="mt-4 flex justify-end"><UButton color="error" :loading="loading === 'reject'" @click="reject">确认拒绝</UButton></div></template></UModal>
  </div>
</template>
