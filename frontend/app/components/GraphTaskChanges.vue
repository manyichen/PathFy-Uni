<script setup lang="ts">
const props = defineProps<{ taskId: number; enabled: boolean }>()
const graph = useGraphTasksApi()
const data = ref<any>()
const group = ref('')
const page = ref(1)
const loading = ref(false)
const selectedCapability = ref<any>()

const dimensions = [
  { key: 'theory', label: '理论' }, { key: 'cross', label: '交叉' },
  { key: 'practice', label: '实践' }, { key: 'digital', label: '数字' },
  { key: 'innovation', label: '创新' }, { key: 'teamwork', label: '协作' },
  { key: 'social', label: '社会' }, { key: 'growth', label: '成长' }
]
const groupLabels: Record<string, string> = {
  input_keys: '输入岗位', jobs: '岗位与评分', job_titles: '岗位名称', promotions: '晋升路径',
  lateral: '换岗关系', nodes: '节点', relationships: '关系', deletions: '删除项',
  resources: '学习资源', competitions: '竞赛', learning_recommendations: '学习推荐',
  competition_recommendations: '竞赛推荐'
}
const columnLabels: Record<string, string> = {
  job_key: '岗位标识', id: '标识', name: '名称', title: '名称', count: '数量',
  promotion_id: '晋升路线', from_job_title: '起点岗位', to_job_title: '目标岗位',
  source_id: '来源', parsed: '解析状态'
}
const hiddenColumns = new Set(['capability', 'old', 'new', 'row', 'ai', 'fingerprint', 'cap_input_fingerprint'])

async function load() {
  if (!props.enabled) return
  loading.value = true
  try {
    data.value = await graph.changes(props.taskId, { group: group.value || undefined, page: page.value })
  } finally { loading.value = false }
}

watch([() => props.enabled, group, page], load, { immediate: true })

const activeGroup = computed(() => group.value || data.value?.group || '')
const scalarItems = computed(() => Boolean(data.value?.items?.length) && data.value.items.every((item: unknown) => ['string', 'number'].includes(typeof item)))
const columns = computed(() => {
  const first = data.value?.items?.find((item: unknown) => item && typeof item === 'object' && !Array.isArray(item))
  return first ? Object.keys(first).filter(key => !hiddenColumns.has(key)).slice(0, 6) : []
})
const hasCapability = computed(() => Boolean(data.value?.items?.some((item: any) => item?.capability)))
const hasSalary = computed(() => Boolean(data.value?.items?.some((item: any) => item?.new?.salary_norm)))

function selectGroup(name: string) {
  if (activeGroup.value === name) return
  page.value = 1
  group.value = name
}

function cellText(value: unknown) {
  if (value == null || value === '') return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return '结构化数据'
  return String(value)
}

function average(item: any, prefix: string) {
  const values = dimensions.map(dim => Number(item?.capability?.[`${prefix}${dim.key}`])).filter(Number.isFinite)
  return values.length ? (values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(prefix.includes('conf') ? 2 : 1) : '-'
}

function evidenceText(value: unknown) {
  if (typeof value === 'string') return value
  if (value && typeof value === 'object') return Object.entries(value).map(([key, item]) => `${key}: ${String(item)}`).join('；')
  return String(value ?? '')
}
</script>

<template>
  <div class="grid gap-4">
    <div v-if="data?.groups" class="flex flex-wrap gap-2">
      <UButton
        v-for="(count, name) in data.groups"
        :key="name"
        size="sm"
        :variant="activeGroup === name ? 'solid' : 'soft'"
        @click="selectGroup(String(name))"
      >{{ groupLabels[String(name)] || name }} · {{ count }}</UButton>
    </div>

    <USkeleton v-if="loading" class="h-32" />

    <div v-else-if="scalarItems" class="overflow-hidden rounded-lg border border-default">
      <div class="bg-muted/50 px-3 py-2 text-sm font-medium">{{ groupLabels[activeGroup] || activeGroup }}</div>
      <div class="grid max-h-96 gap-px overflow-y-auto bg-default sm:grid-cols-2 xl:grid-cols-3">
        <code v-for="item in data.items" :key="String(item)" class="break-all bg-default p-3 text-xs">{{ item }}</code>
      </div>
    </div>

    <div v-else-if="data?.items?.length" class="overflow-x-auto rounded-lg border border-default">
      <table class="w-full table-fixed text-left text-sm">
        <thead class="bg-muted/50">
          <tr>
            <th v-for="column in columns" :key="column" class="px-3 py-2 font-medium">{{ columnLabels[column] || column }}</th>
            <th v-if="hasCapability" class="w-52 px-3 py-2">八维评分</th>
            <th v-if="hasSalary" class="w-64 px-3 py-2">薪资变化</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in data.items" :key="item.job_key || item.id || index" class="border-t border-default align-top">
            <td v-for="column in columns" :key="column" class="px-3 py-2">
              <span class="block truncate" :title="cellText(item[column])">{{ cellText(item[column]) }}</span>
            </td>
            <td v-if="hasCapability" class="px-3 py-2">
              <div v-if="item.capability" class="flex items-center justify-between gap-2">
                <div class="whitespace-nowrap text-xs"><strong>均分 {{ average(item, 'cap_req_') }}</strong><p class="muted">置信度 {{ average(item, 'cap_conf_') }}</p></div>
                <UButton size="xs" variant="soft" @click="selectedCapability = item">查看</UButton>
              </div>
              <span v-else>-</span>
            </td>
            <td v-if="hasSalary" class="px-3 py-2">
              <span v-if="item.new?.salary_norm"><span class="muted">{{ item.old?.salary_norm || '未设置' }}</span> → <strong>{{ item.new.salary_norm }}</strong><p class="text-xs muted">{{ item.new.salary_parse_version }}</p></span><span v-else>-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <UEmpty v-else title="没有可分页展示的明细" />
    <UPagination v-if="data?.total > data?.page_size" v-model:page="page" :total="data.total" :items-per-page="data.page_size" />

    <UModal :open="Boolean(selectedCapability)" :title="`八维评分 · ${selectedCapability?.job_key || selectedCapability?.row?.title || '岗位'}`" @update:open="value => { if (!value) selectedCapability = undefined }">
      <template #body>
        <div class="grid gap-3 sm:grid-cols-2">
          <div v-for="dim in dimensions" :key="dim.key" class="rounded-xl border border-default p-3">
            <div class="flex items-center justify-between"><strong>{{ dim.label }}</strong><UBadge :label="`置信度 ${selectedCapability?.capability?.[`cap_conf_${dim.key}`] ?? '-'}`" color="neutral" variant="soft" /></div>
            <p class="mt-2 text-lg font-semibold text-primary"><span v-if="selectedCapability?.old?.[`cap_req_${dim.key}`] != null" class="mr-2 text-sm font-normal muted">{{ selectedCapability.old[`cap_req_${dim.key}`] }} →</span>{{ selectedCapability?.capability?.[`cap_req_${dim.key}`] ?? '-' }}</p>
          </div>
        </div>
        <div v-if="selectedCapability?.capability?.cap_evidence?.length" class="mt-5"><h3 class="font-semibold">评估证据</h3><ul class="mt-2 grid gap-2 text-sm"><li v-for="(evidence, index) in selectedCapability.capability.cap_evidence" :key="index" class="rounded-lg bg-elevated p-3">{{ evidenceText(evidence) }}</li></ul></div>
        <div v-if="selectedCapability?.capability?.cap_risk_flags?.length" class="mt-5"><h3 class="font-semibold">风险标记</h3><div class="mt-2 flex flex-wrap gap-2"><UBadge v-for="risk in selectedCapability.capability.cap_risk_flags" :key="risk" color="warning" variant="soft" :label="risk" /></div></div>
      </template>
    </UModal>
  </div>
</template>
