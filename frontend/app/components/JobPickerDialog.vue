<script setup lang="ts">
const props = withDefaults(defineProps<{
  open: boolean
  title?: string
  selectedIds?: string[]
  multiple?: boolean
}>(), { title: '选择岗位', selectedIds: () => [], multiple: false })

const emit = defineEmits<{
  'update:open': [value: boolean]
  select: [job: any]
}>()

const api = useApi()
const toast = useToast()
const query = ref('')
const page = ref(1)
const loading = ref(false)
const result = ref<any>({ jobs: [], total: 0, page_size: 20 })

async function load(reset = false) {
  if (reset) page.value = 1
  loading.value = true
  try {
    const params = new URLSearchParams({ page: String(page.value), page_size: '20' })
    if (query.value.trim()) params.set('q', query.value.trim())
    result.value = await api.ok<any>(`/api/jobs/options?${params}`)
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '岗位加载失败', color: 'error' })
  } finally { loading.value = false }
}

function choose(job: any) {
  emit('select', job)
  if (!props.multiple) emit('update:open', false)
}

watch(() => props.open, value => { if (value) load(true) })
watch(page, () => { if (props.open) load() })
</script>

<template>
  <UModal :open="open" :title="title" :ui="{ content: 'sm:max-w-5xl' }" @update:open="emit('update:open', $event)">
    <template #body>
      <div class="grid gap-4">
        <form class="flex gap-2" @submit.prevent="load(true)">
          <UInput v-model="query" class="flex-1" size="lg" icon="i-lucide-search" placeholder="搜索岗位名称、公司或地点" />
          <UButton type="submit" size="lg" :loading="loading">搜索</UButton>
        </form>
        <div class="flex items-center justify-between text-sm muted"><span>共 {{ result.total || 0 }} 个岗位</span><span>可按岗位、公司和城市检索</span></div>
        <div v-if="loading" class="grid gap-3 md:grid-cols-2"><USkeleton v-for="n in 6" :key="n" class="h-28" /></div>
        <div v-else-if="result.jobs?.length" class="job-picker-grid">
          <button v-for="job in result.jobs" :key="job.id" type="button" :class="['job-option', selectedIds.includes(job.id) && 'selected']" @click="choose(job)">
            <div class="min-w-0"><div class="flex items-center gap-2"><h3 class="truncate font-semibold">{{ job.title }}</h3><UBadge v-if="selectedIds.includes(job.id)" label="已选择" size="sm" variant="soft" /></div><p class="mt-2 flex items-center gap-1.5 text-sm muted"><UIcon name="i-lucide-building-2" class="shrink-0" /><span class="truncate">{{ job.company || '未知公司' }}</span></p><p class="mt-1 flex items-center gap-1.5 text-sm muted"><UIcon name="i-lucide-map-pin" class="shrink-0" />{{ job.location || '未知地点' }}<span v-if="job.experience_years">· {{ job.experience_years }} 年经验</span></p></div><div class="shrink-0 text-right"><p class="font-medium text-primary">{{ job.salary || '薪资面议' }}</p><UIcon name="i-lucide-chevron-right" class="mt-3" /></div>
          </button>
        </div>
        <UEmpty v-else title="没有找到岗位" description="换一个岗位、公司或地点关键词试试" icon="i-lucide-search-x" />
        <div class="flex justify-center"><UPagination v-if="result.total > (result.page_size || 20)" v-model:page="page" :total="result.total" :items-per-page="result.page_size || 20" /></div>
      </div>
    </template>
    <template v-if="multiple" #footer><div class="flex w-full items-center justify-between"><span class="text-sm muted">已选择 {{ selectedIds.length }} 个岗位</span><UButton @click="emit('update:open', false)">完成选择</UButton></div></template>
  </UModal>
</template>

<style scoped>
.job-picker-grid { display: grid; gap: .75rem; max-height: min(62vh, 680px); overflow-y: auto; padding: .15rem; }
.job-option { display: flex; min-width: 0; align-items: flex-start; justify-content: space-between; gap: 1rem; border: 1px solid var(--ui-border); border-radius: .85rem; padding: 1rem; text-align: left; transition: border-color .15s ease, background .15s ease; }
.job-option:hover, .job-option.selected { border-color: color-mix(in srgb, var(--ui-primary) 48%, transparent); background: color-mix(in srgb, var(--ui-primary) 6%, transparent); }
@media (min-width: 768px) { .job-picker-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
