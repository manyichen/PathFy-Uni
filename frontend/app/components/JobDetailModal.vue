<script setup lang="ts">
const props = defineProps<{ jobId: string | null }>()
const emit = defineEmits<{ close: [] }>()
const jobs = useJobsApi(); const data = ref<any>(); const pathData = ref<any>(); const loading = ref(false); const tab = ref('detail')
watch(() => props.jobId, async id => { if (!id) return; loading.value = true; data.value = undefined; pathData.value = undefined; tab.value = 'detail'; try { data.value = await jobs.detail(id) } finally { loading.value = false } }, { immediate: true })
watch(tab, async value => {
  if (!props.jobId || pathData.value?.[value] || value === 'detail' || value === 'raw') return
  loading.value = true
  try { pathData.value = { ...pathData.value, [value]: value === 'promotion' ? await jobs.promotion(props.jobId) : await jobs.lateral(props.jobId) } } finally { loading.value = false }
})
</script>
<template>
  <UModal :open="Boolean(jobId)" title="岗位详情" fullscreen @update:open="v => !v && emit('close')">
    <template #body><USkeleton v-if="loading" class="h-80" /><div v-else-if="data" class="page-stack"><div><h2 class="text-2xl font-bold">{{ data.title }}</h2><p class="muted">{{ data.company }} · {{ data.location }} · {{ data.salary }}</p></div><LazyCapabilityRadar :scores="data.scores" /><UTabs v-model="tab" :items="[{label:'岗位说明',value:'detail'},{label:'晋升路径',value:'promotion'},{label:'横向路径',value:'lateral'},{label:'原始数据',value:'raw'}]" /><div v-if="tab === 'detail'" class="whitespace-pre-wrap">{{ data.demand || data.description || '暂无岗位说明' }}</div><pre v-else-if="tab === 'raw'" class="overflow-auto rounded-lg bg-muted p-4 text-xs">{{ JSON.stringify(data, null, 2) }}</pre><pre v-else class="overflow-auto rounded-lg bg-muted p-4 text-sm">{{ JSON.stringify(pathData?.[tab] || {}, null, 2) }}</pre></div></template>
  </UModal>
</template>
