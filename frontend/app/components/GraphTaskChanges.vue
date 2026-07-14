<script setup lang="ts">
const props = defineProps<{ taskId: number; enabled: boolean }>()
const graph = useGraphTasksApi()
const data = ref<any>()
const group = ref('')
const page = ref(1)
const loading = ref(false)
async function load() {
  if (!props.enabled) return
  loading.value = true
  try {
    data.value = await graph.changes(props.taskId, { group: group.value || undefined, page: page.value })
    if (!group.value && data.value?.group) group.value = data.value.group
  } finally { loading.value = false }
}
watch([() => props.enabled, group, page], load, { immediate: true })
const columns = computed(() => {
  const first = data.value?.items?.[0]
  return first && typeof first === 'object' ? Object.keys(first).filter(key => !['capability', 'old', 'new', 'row', 'ai'].includes(key)).slice(0, 6) : []
})
const hasCapability = computed(() => Boolean(data.value?.items?.some((item: any) => item.capability)))
const hasSalary = computed(() => Boolean(data.value?.items?.some((item: any) => item.new?.salary_norm)))
const dimensions = [{key:'theory',label:'理论'},{key:'cross',label:'交叉'},{key:'practice',label:'实践'},{key:'digital',label:'数字'},{key:'innovation',label:'创新'},{key:'teamwork',label:'协作'},{key:'social',label:'社会'},{key:'growth',label:'成长'}]
</script>

<template>
  <div class="grid gap-4">
    <div v-if="data?.groups" class="flex flex-wrap gap-2">
      <UButton v-for="(count,name) in data.groups" :key="name" size="sm" :variant="group === name ? 'solid' : 'soft'" @click="group=String(name);page=1">{{ name }} · {{ count }}</UButton>
    </div>
    <USkeleton v-if="loading" class="h-32" />
    <div v-else-if="data?.items?.length" class="overflow-x-auto rounded-lg border border-default">
      <table class="w-full text-left text-sm">
        <thead class="bg-muted/50"><tr><th v-for="column in columns" :key="column" class="px-3 py-2 font-medium">{{ column }}</th><th v-if="hasCapability" class="px-3 py-2">八维评分 / 置信度</th><th v-if="hasSalary" class="px-3 py-2">薪资变化</th></tr></thead>
        <tbody><tr v-for="(item,index) in data.items" :key="index" class="border-t border-default align-top">
          <td v-for="column in columns" :key="column" class="max-w-64 px-3 py-2">{{ typeof item[column] === 'object' ? '结构化数据' : item[column] }}</td>
          <td v-if="hasCapability" class="px-3 py-2"><template v-if="item.capability"><div class="grid min-w-80 grid-cols-2 gap-1 text-xs"><span v-for="dim in dimensions" :key="dim.key"><b>{{ dim.label }}</b> <span v-if="item.old?.[`cap_req_${dim.key}`] != null" class="text-muted">{{ item.old[`cap_req_${dim.key}`] }} → </span>{{ item.capability[`cap_req_${dim.key}`] }} <em class="text-muted">({{ item.capability[`cap_conf_${dim.key}`] }})</em></span></div><details v-if="item.capability.cap_evidence?.length || item.capability.cap_risk_flags?.length" class="mt-2 text-xs"><summary class="cursor-pointer text-primary">证据与风险</summary><p v-for="evidence in item.capability.cap_evidence" :key="evidence" class="mt-1">{{ evidence }}</p><UBadge v-for="risk in item.capability.cap_risk_flags" :key="risk" class="mr-1 mt-1" color="warning" variant="soft" :label="risk"/></details></template><span v-else>-</span></td>
          <td v-if="hasSalary" class="px-3 py-2"><span v-if="item.new?.salary_norm"><span class="text-muted">{{ item.old?.salary_norm || '未设置' }}</span> → <strong>{{ item.new.salary_norm }}</strong><p class="text-xs text-muted">{{ item.new.salary_parse_version }}</p></span><span v-else>-</span></td>
        </tr></tbody>
      </table>
    </div>
    <UEmpty v-else title="没有可分页展示的明细" />
    <UPagination v-if="data?.total > data?.page_size" v-model:page="page" :total="data.total" :items-per-page="data.page_size" />
  </div>
</template>
