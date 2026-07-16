<script setup lang="ts">
import { graphTaskCatalog, type GraphTaskType } from '~/types/graph'
definePageMeta({ middleware: 'admin' })
useSeoMeta({ title: '更新图谱' })
const graph = useGraphTasksApi(); const toast = useToast()
const type = ref<string>('job_import'); const files = reactive<Record<string, File | undefined>>({})
const mode = ref('merge'); const sourceId = ref(''); const batch = ref(128); const capabilityBatch = ref(8); const promotions = ref(true); const lateral = ref(true)
const scope = ref('missing'); const force = ref(false); const loading = ref(false); const guard = ref<any>()
const remoteCatalog = ref<any[]>([])
const fallbackFiles: Partial<Record<GraphTaskType, { role: string, extensions: string[], required: boolean, max_bytes: number }[]>> = {
  job_import: [{ role: 'file', extensions: ['.xls', '.xlsx'], required: true, max_bytes: 25 * 1024 * 1024 }],
  job_capability_result_import: [{ role: 'file', extensions: ['.jsonl'], required: true, max_bytes: 25 * 1024 * 1024 }],
  learning_resource_import: [{ role: 'file', extensions: ['.csv'], required: true, max_bytes: 25 * 1024 * 1024 }],
  competition_import: [{ role: 'file', extensions: ['.csv'], required: true, max_bytes: 25 * 1024 * 1024 }],
  job_promotion_import: [{ role: 'file', extensions: ['.csv'], required: true, max_bytes: 25 * 1024 * 1024 }],
  job_lateral_import: [{ role: 'file', extensions: ['.csv'], required: true, max_bytes: 25 * 1024 * 1024 }],
  promotion_recommendation_import: [
    { role: 'learning_file', extensions: ['.csv'], required: true, max_bytes: 25 * 1024 * 1024 },
    { role: 'competition_file', extensions: ['.csv'], required: true, max_bytes: 25 * 1024 * 1024 }
  ]
}
const fallbackCatalog = Object.entries(graphTaskCatalog).map(([task_type, item]) => ({
  task_type, ...item, category_label: item.category,
  files: fallbackFiles[task_type as GraphTaskType] || [],
  create_via: task_type === 'emergency_clear' || task_type === 'graph_inverse' ? 'special' : 'tasks'
}))
const catalogItems = computed(() => remoteCatalog.value.length ? remoteCatalog.value : fallbackCatalog)
const categories = computed(() => [...new Set(catalogItems.value.filter(item => item.create_via === 'tasks').map(item => item.category_label))])
const itemsByCategory = (category: string) => catalogItems.value.filter(item => item.category_label === category && item.create_via === 'tasks')
const selected = computed<any>(() => catalogItems.value.find(item => item.task_type === type.value) || graphTaskCatalog[type.value as GraphTaskType])
const isCurated = computed(() => (selected.value.category_label || selected.value.category) === '策展数据')
const fileSpecs = computed<any[]>(() => selected.value?.files || [])
const fallbackContracts: Partial<Record<GraphTaskType,string>> = {
  job_import: 'Excel（.xls/.xlsx）。关键列：岗位名称、公司名称、地址、薪资范围、所属行业、岗位详情、岗位编码、岗位来源地址。',
  job_capability_result_import: 'JSONL（每行一个 JSON）。关键字段：job_key 或 job_id、scores、confidence、evidence、risk_flags。scores 和 confidence 均需包含完整八维。',
  learning_resource_import: 'CSV。关键列：resource_id、job_name、resource_name、resource_url、resource_type、difficulty、skill_tag。多个岗位名称用 | 分隔。',
  competition_import: 'CSV。关键列：competition_id、job_name、competition_name、official_url、competition_type、difficulty、cap_tags、skill_tags。',
  job_promotion_import: 'CSV。关键列：promotion_id、job_title、title、promotion、stage1、stage2、stage3、stage3_job_title。',
  job_lateral_import: 'CSV。关键列：from_job_title、to_job_title、score、rank、track_from、track_to、cap_similarity、rationale。',
  promotion_recommendation_import: '同时上传两个 CSV。学习资源文件需 promotion_id、resource_id、stage、rank、score；竞赛文件需 promotion_id、competition_id、stage、rank、score。'
}
const contract = computed(() => selected.value?.input_format
  ? `${selected.value.input_format}。${selected.value.columns?.length ? `关键列：${selected.value.columns.join('、')}。` : selected.value.description || ''}`
  : fallbackContracts[type.value as GraphTaskType])
function pick(role: string, event: Event) { files[role] = (event.target as HTMLInputElement).files?.[0] }
function selectTask(value: string) { type.value = value }
function fileLabel(role: string) {
  return ({ file: '导入文件', learning_file: '学习资源推荐 CSV', competition_file: '竞赛推荐 CSV' } as Record<string, string>)[role] || role
}
function fileHint(spec: any) {
  const formats = (spec.extensions || []).join('、') || '指定格式'
  const maxMiB = Math.round(Number(spec.max_bytes || 0) / 1024 / 1024)
  return `${formats}${maxMiB ? `，最大 ${maxMiB} MiB` : ''}`
}
watch(type, value => {
  Object.keys(files).forEach(key => { files[key] = undefined })
  const item = catalogItems.value.find(entry => entry.task_type === value)
  if ((item?.category_label || graphTaskCatalog[value as GraphTaskType]?.category) === '策展数据') { mode.value = 'snapshot'; sourceId.value = value.replaceAll('_import','') }
  else { mode.value = 'merge'; sourceId.value = '' }
})
async function submit() {
  const missingFile = fileSpecs.value.find(spec => spec.required && !files[spec.role])
  if (missingFile) { toast.add({ title: `请选择${fileLabel(missingFile.role)}`, color: 'warning' }); return }
  if (mode.value === 'snapshot' && isCurated.value && !sourceId.value.trim()) { toast.add({ title: '来源快照必须填写 source_id', color: 'warning' }); return }
  loading.value = true
  try {
    let body: FormData | Record<string, unknown>
    if (Object.values(files).some(Boolean)) {
      const form = new FormData(); form.append('task_type', type.value); form.append('mode', mode.value); form.append('source_id', sourceId.value)
      form.append('batch_size', String(batch.value)); form.append('capability_batch_size', String(capabilityBatch.value)); form.append('generate_promotions', String(promotions.value)); form.append('generate_lateral', String(lateral.value)); form.append('scope', scope.value); form.append('force', String(force.value))
      Object.entries(files).forEach(([role,file]) => { if (file) form.append(role, file) }); body = form
    } else body = { task_type: type.value, mode: mode.value, source_id: sourceId.value, scope: scope.value, capability_batch_size: capabilityBatch.value, force: force.value }
    const task = await graph.create(body); toast.add({ title: '任务已进入队列', color: 'success' }); await navigateTo(`/graph-admin/tasks/${task.id}`)
  } catch (error) { toast.add({ title: String(error), color: 'error' }) } finally { loading.value = false }
}
onMounted(async () => {
  const [guardResult, catalogResult] = await Promise.allSettled([graph.guard(), graph.catalog()])
  if (guardResult.status === 'fulfilled') guard.value = guardResult.value
  if (catalogResult.status === 'fulfilled') remoteCatalog.value = catalogResult.value.items || []
})
</script>

<template>
  <div class="page-stack">
    <GraphAdminNav/><GraphGuardBanner :guard="guard"/>
    <div class="page-heading"><h1 class="flex items-center gap-2"><UIcon name="i-lucide-upload" class="text-primary"/>更新图谱</h1><p class="muted">先生成完整变更集，确认前 Neo4j 不会变化</p></div>
    <div class="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <UCard class="h-fit"><div v-for="category in categories" :key="category" class="mb-5 last:mb-0"><p class="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{{ category }}</p><div class="grid gap-1"><UButton v-for="item in itemsByCategory(category)" :key="item.task_type" :icon="item.icon" :variant="type === item.task_type ? 'soft' : 'ghost'" class="justify-start" @click="selectTask(item.task_type)">{{ item.label }}</UButton></div></div></UCard>
      <UCard><template #header><div class="flex items-center gap-3"><UIcon :name="selected.icon" class="size-6 text-primary"/><div><h2 class="font-semibold">{{ selected.label }}</h2><p class="text-sm muted">{{ selected.category_label || selected.category }}</p></div></div></template>
        <div class="grid gap-5 md:grid-cols-2">
          <UFormField v-for="spec in fileSpecs" :key="spec.role" :label="fileLabel(spec.role)" :required="spec.required" :hint="fileHint(spec)"><UInput type="file" :accept="(spec.extensions || []).join(',')" @change="pick(spec.role,$event)"/></UFormField>
          <template v-if="isCurated || type === 'job_import'"><UFormField label="导入模式"><USelect v-model="mode" :items="[{label:'增量合并',value:'merge'},{label:'来源快照',value:'snapshot'}]" class="w-full"/></UFormField><UFormField label="source_id" :required="mode === 'snapshot'"><UInput v-model="sourceId" placeholder="稳定的数据来源标识"/></UFormField></template>
          <template v-if="type === 'job_import'"><UFormField label="岗位抽取批大小"><UInput v-model.number="batch" type="number" min="1" max="1000"/></UFormField><UFormField label="八维评估批大小"><UInput v-model.number="capabilityBatch" type="number" min="1" max="50"/><template #hint>每次模型请求包含的岗位数，建议 5–10。</template></UFormField><div class="grid gap-2"><UCheckbox v-model="promotions" label="生成自动晋升路线"/><UCheckbox v-model="lateral" label="生成自动换岗关系"/><p class="text-xs muted">岗位名称同步和八维评估始终执行。</p></div></template>
          <template v-if="type === 'job_capability_evaluation'"><UFormField label="评估范围"><USelect v-model="scope" :items="[{label:'仅缺失评分',value:'missing'},{label:'版本过期',value:'stale'},{label:'全部岗位',value:'all'}]" class="w-full"/></UFormField><UFormField label="八维评估批大小"><UInput v-model.number="capabilityBatch" type="number" min="1" max="50"/><template #hint>每次模型请求包含的岗位数，建议 5–10。</template></UFormField><UFormField label="限定 source_id（可选）"><UInput v-model="sourceId"/></UFormField></template>
          <UCheckbox v-if="type === 'salary_normalization'" v-model="force" label="强制重新计算所有岗位"/>
        </div>
        <UAlert v-if="contract" class="mt-5" icon="i-lucide-info" title="输入格式" :description="contract"/>
        <UAlert v-if="type === 'inferred_job_cleanup'" class="mt-5" color="error" icon="i-lucide-triangle-alert" title="危险维护任务" description="将固化并审阅 source=inferred 的岗位及 job_count < 2 的岗位名称；创建任务不会立即删除。"/>
        <div class="mt-6 flex items-center justify-between border-t border-default pt-5"><p class="text-sm muted">Worker 完成规划后需要管理员整单确认。</p><UButton size="lg" :loading="loading" @click="submit">创建更新任务</UButton></div>
      </UCard>
    </div>
  </div>
</template>
