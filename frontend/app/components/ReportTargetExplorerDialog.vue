<script setup lang="ts">
const props = withDefaults(defineProps<{
  open: boolean
  selectedIds?: string[]
  selectedTargets?: any[]
  maxTargets?: number
}>(), {
  selectedIds: () => [],
  selectedTargets: () => [],
  maxTargets: 5
})

const emit = defineEmits<{
  'update:open': [value: boolean]
  select: [target: any]
  remove: [index: number]
}>()

const api = useApi()
const toast = useToast()

const query = ref('')
const locationQ = ref('')
const mode = ref<'random' | 'search'>('random')
const loading = ref(false)
const errorMessage = ref('')
const page = ref(1)
const total = ref(0)
const totalPages = ref(1)
const seed = ref('')
const targets = ref<any[]>([])

const selectedSet = computed(() => new Set((props.selectedIds || []).map(String)))
const selectedFull = computed(() => (props.selectedTargets || []).filter(Boolean))
const canAddMore = computed(() => selectedSet.value.size < props.maxTargets)

function targetId(item: any) {
  return String(item?.job_id || item?.id || '')
}

function newSeed() {
  if (import.meta.client && 'crypto' in window && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function normalizeResult(data: any) {
  targets.value = data?.targets || data?.jobs || data?.items || []
  total.value = Number(data?.total ?? data?.count ?? targets.value.length)
  page.value = Number(data?.page || page.value || 1)
  totalPages.value = Number(data?.total_pages || Math.max(1, Math.ceil(total.value / Number(data?.page_size || 12))))
}

async function runSearch() {
  const q = query.value.trim()
  if (!q) {
    toast.add({ title: '请输入岗位关键词', color: 'warning' })
    return
  }

  mode.value = 'search'
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await api.ok<any>('/api/report/targets/manual-search', {
      method: 'POST',
      body: { q, location_q: locationQ.value.trim(), limit: 24 }
    })
    page.value = 1
    normalizeResult(data)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '搜索候选岗位失败'
    targets.value = []
  } finally {
    loading.value = false
  }
}

async function loadRandom(reset = false) {
  mode.value = 'random'
  if (reset || !seed.value) {
    seed.value = newSeed()
    page.value = 1
  }

  loading.value = true
  errorMessage.value = ''
  try {
    const params = new URLSearchParams({
      seed: seed.value,
      page: String(page.value),
      page_size: '12'
    })
    const data = await api.ok<any>(`/api/report/targets/random-browse?${params}`)
    normalizeResult(data)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '随机浏览岗位失败'
    targets.value = []
  } finally {
    loading.value = false
  }
}

function choose(item: any) {
  const id = targetId(item)
  if (!id) return
  if (selectedSet.value.has(id)) return
  if (!canAddMore.value) {
    toast.add({ title: `最多选择 ${props.maxTargets} 个目标`, color: 'warning' })
    return
  }
  emit('select', { ...item, job_id: id })
}

function changeRandomPage(next: number) {
  page.value = Math.min(Math.max(1, next), totalPages.value)
  loadRandom(false)
}

watch(() => props.open, value => {
  if (value && !targets.value.length) loadRandom(true)
})
</script>

<template>
  <UModal
    :open="open"
    title="搜索候选 / 随机浏览"
    :ui="{ content: 'sm:max-w-6xl' }"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div class="explorer-layout">
        <section class="explorer-main">
          <form class="search-bar" @submit.prevent="runSearch">
            <UInput v-model="query" class="min-w-0 flex-1" size="lg" icon="i-lucide-search" placeholder="搜索岗位、公司或技能关键词" />
            <UInput v-model="locationQ" class="location-input" size="lg" icon="i-lucide-map-pin" placeholder="城市，可选" />
            <UButton type="submit" size="lg" :loading="loading && mode === 'search'">搜索候选</UButton>
            <UButton color="neutral" variant="soft" size="lg" icon="i-lucide-shuffle" :loading="loading && mode === 'random'" @click="loadRandom(true)">
              随机浏览
            </UButton>
          </form>

          <div class="result-meta">
            <span>{{ mode === 'search' ? '搜索结果' : '随机浏览' }} · {{ total || targets.length }} 个候选</span>
            <span v-if="mode === 'random'">第 {{ page }} / {{ totalPages }} 页</span>
          </div>

          <UAlert v-if="errorMessage" color="error" variant="soft" icon="i-lucide-triangle-alert" :title="errorMessage" />

          <div v-if="loading" class="target-list">
            <USkeleton v-for="n in 6" :key="n" class="h-28" />
          </div>
          <div v-else-if="targets.length" class="target-list">
            <button
              v-for="item in targets"
              :key="targetId(item)"
              type="button"
              class="target-option"
              :class="{ selected: selectedSet.has(targetId(item)) }"
              @click="choose(item)"
            >
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="truncate font-semibold">{{ item.title || item.job_id }}</h3>
                  <UBadge v-if="item.source" :label="item.source === 'manual_search' ? '搜索' : '随机'" color="neutral" variant="soft" size="sm" />
                  <UBadge v-if="selectedSet.has(targetId(item))" label="已加入" variant="soft" size="sm" />
                </div>
                <p class="mt-2 flex items-center gap-1.5 text-sm muted">
                  <UIcon name="i-lucide-building-2" class="shrink-0" />
                  <span class="truncate">{{ item.company || '未知公司' }}</span>
                </p>
                <p class="mt-1 flex flex-wrap items-center gap-1.5 text-sm muted">
                  <UIcon name="i-lucide-map-pin" class="shrink-0" />
                  <span>{{ item.location || '未知地点' }}</span>
                  <span v-if="item.salary">· {{ item.salary }}</span>
                </p>
              </div>
              <UIcon :name="selectedSet.has(targetId(item)) ? 'i-lucide-check' : 'i-lucide-plus'" class="size-5 shrink-0 text-primary" />
            </button>
          </div>
          <UEmpty v-else title="暂无候选岗位" description="换个关键词，或点随机浏览再试一次" icon="i-lucide-search-x" />

          <div v-if="mode === 'random' && totalPages > 1" class="flex justify-center gap-2">
            <UButton color="neutral" variant="soft" icon="i-lucide-chevron-left" :disabled="page <= 1 || loading" @click="changeRandomPage(page - 1)">上一页</UButton>
            <UButton color="neutral" variant="soft" trailing-icon="i-lucide-chevron-right" :disabled="page >= totalPages || loading" @click="changeRandomPage(page + 1)">下一页</UButton>
          </div>
        </section>

        <aside class="selected-panel">
          <div>
            <p class="text-sm font-semibold">已选目标 {{ selectedSet.size }}/{{ maxTargets }}</p>
            <p class="mt-1 text-xs muted">点击左侧候选加入报告目标，最多保留 5 个方向。</p>
          </div>
          <div class="mt-4 grid gap-2">
            <button
              v-for="(item, index) in selectedFull"
              :key="targetId(item)"
              type="button"
              class="selected-row"
              @click="emit('remove', index)"
            >
              <span class="min-w-0">
                <strong class="block truncate">{{ item.title || item.job_id }}</strong>
                <small class="block truncate">{{ item.company || '未知公司' }}</small>
              </span>
              <UIcon name="i-lucide-x" class="shrink-0" />
            </button>
            <UEmpty v-if="!selectedFull.length" title="还没有目标" icon="i-lucide-target" />
          </div>
        </aside>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full items-center justify-between">
        <span class="text-sm muted">已选择 {{ selectedSet.size }} 个目标岗位</span>
        <UButton @click="emit('update:open', false)">完成选择</UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.explorer-layout {
  display: grid;
  gap: 1rem;
}

.explorer-main {
  display: grid;
  gap: 1rem;
}

.search-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.location-input {
  flex: 0 1 12rem;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.5rem;
  color: var(--ui-text-muted);
  font-size: 0.875rem;
}

.target-list {
  display: grid;
  max-height: min(58vh, 42rem);
  gap: 0.75rem;
  overflow-y: auto;
  padding: 0.1rem;
}

.target-option {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid var(--ui-border);
  border-radius: 0.85rem;
  background: var(--ui-bg);
  padding: 1rem;
  text-align: left;
  transition: border-color 160ms ease, background 160ms ease, transform 160ms ease;
}

.target-option:hover,
.target-option.selected {
  border-color: color-mix(in srgb, var(--ui-primary) 45%, var(--ui-border));
  background: color-mix(in srgb, var(--ui-primary) 6%, var(--ui-bg));
}

.target-option:active {
  transform: translateY(1px);
}

.selected-panel {
  border: 1px solid var(--ui-border);
  border-radius: 0.9rem;
  background: var(--ui-bg-elevated);
  padding: 1rem;
}

.selected-row {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  border-radius: 0.65rem;
  background: color-mix(in srgb, var(--ui-primary) 7%, transparent);
  padding: 0.65rem 0.75rem;
  text-align: left;
}

.selected-row small {
  color: var(--ui-text-muted);
}

@media (min-width: 1024px) {
  .explorer-layout {
    grid-template-columns: minmax(0, 1fr) minmax(16rem, 0.32fr);
  }

  .target-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
