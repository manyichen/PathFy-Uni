<script setup lang="ts">
import { graphTaskCatalog, type GraphTaskType } from '~/types/graph'
definePageMeta({ middleware: 'admin' })
useSeoMeta({ title: '更新图谱' })
const graph = useGraphTasksApi(); const toast = useToast()
const type = ref<GraphTaskType>('job_import'); const files = reactive<Record<string, File | undefined>>({})
const mode = ref('merge'); const sourceId = ref(''); const batch = ref(128); const capabilityBatch = ref(8); const promotions = ref(true); const lateral = ref(true)
const scope = ref('missing'); const force = ref(false); const loading = ref(false); const guard = ref<any>()
const categories = ['岗位与能力', '策展数据', '图谱维护']
const itemsByCategory = (category: string) => Object.entries(graphTaskCatalog).filter(([key, item]) => item.category === category && key !== 'emergency_clear')
const selected = computed(() => graphTaskCatalog[type.value])
const isCurated = computed(() => selected.value.category === '策展数据')
const needsPrimaryFile = computed(() => ['job_import','job_capability_result_import','learning_resource_import','competition_import','job_promotion_import','job_lateral_import'].includes(type.value))
const accepts = computed(() => type.value === 'job_import' ? '.xls,.xlsx' : type.value === 'job_capability_result_import' ? '.jsonl' : '.csv')
const contracts: Partial<Record<GraphTaskType,string>> = {
  job_import: 'Excel（.xls/.xlsx）。关键列：岗位名称、公司名称、地址、薪资范围、所属行业、岗位详情、岗位编码、岗位来源地址。',
  job_capability_result_import: 'JSONL（每行一个 JSON）。关键字段：job_key 或 job_id、scores、confidence、evidence、risk_flags。scores 和 confidence 均需包含完整八维。',
  learning_resource_import: 'CSV。关键列：resource_id、job_name、resource_name、resource_url、resource_type、difficulty、skill_tag。多个岗位名称用 | 分隔。',
  competition_import: 'CSV。关键列：competition_id、job_name、competition_name、official_url、competition_type、difficulty、cap_tags、skill_tags。',
  job_promotion_import: 'CSV。关键列：promotion_id、job_title、title、promotion、stage1、stage2、stage3、stage3_job_title。',
  job_lateral_import: 'CSV。关键列：from_job_title、to_job_title、score、rank、track_from、track_to、cap_similarity、rationale。',
  promotion_recommendation_import: '同时上传两个 CSV。学习资源文件需 promotion_id、resource_id、stage、rank、score；竞赛文件需 promotion_id、competition_id、stage、rank、score。'
}
function pick(role: string, event: Event) { files[role] = (event.target as HTMLInputElement).files?.[0] }
function selectTask(value: string) { type.value = value as GraphTaskType }
watch(type, value => {
  Object.keys(files).forEach(key => { files[key] = undefined })
  if (graphTaskCatalog[value].category === '策展数据') { mode.value = 'snapshot'; sourceId.value = value.replaceAll('_import','') }
  else { mode.value = 'merge'; sourceId.value = '' }
})
async function submit() {
  if (needsPrimaryFile.value && !files.file) { toast.add({ title: '请选择导入文件', color: 'warning' }); return }
  if (type.value === 'promotion_recommendation_import' && (!files.learning_file || !files.competition_file)) { toast.add({ title: '两个推荐文件都必须上传', color: 'warning' }); return }
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
onMounted(async () => { try { guard.value = await graph.guard() } catch {} })
</script>

<template>
  <div class="page-stack">
    <GraphAdminNav/><GraphGuardBanner :guard="guard"/>
    <div class="page-heading"><h1 class="flex items-center gap-2"><UIcon name="i-lucide-upload" class="text-primary"/>更新图谱</h1><p class="muted">先生成完整变更集，确认前 Neo4j 不会变化</p></div>
    <div class="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <UCard class="h-fit"><div v-for="category in categories" :key="category" class="mb-5 last:mb-0"><p class="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{{ category }}</p><div class="grid gap-1"><UButton v-for="([value,item]) in itemsByCategory(category)" :key="value" :icon="item.icon" :variant="type === value ? 'soft' : 'ghost'" class="justify-start" @click="selectTask(value)">{{ item.label }}</UButton></div></div></UCard>
      <UCard><template #header><div class="flex items-center gap-3"><UIcon :name="selected.icon" class="size-6 text-primary"/><div><h2 class="font-semibold">{{ selected.label }}</h2><p class="text-sm muted">{{ selected.category }}</p></div></div></template>
        <div class="grid gap-5 md:grid-cols-2">
          <template v-if="needsPrimaryFile"><UFormField label="导入文件" required><UInput type="file" :accept="accepts" @change="pick('file',$event)"/></UFormField></template>
          <template v-if="type === 'promotion_recommendation_import'"><UFormField label="学习资源推荐 CSV" required><UInput type="file" accept=".csv" @change="pick('learning_file',$event)"/></UFormField><UFormField label="竞赛推荐 CSV" required><UInput type="file" accept=".csv" @change="pick('competition_file',$event)"/></UFormField></template>
          <template v-if="isCurated || type === 'job_import'"><UFormField label="导入模式"><USelect v-model="mode" :items="[{label:'增量合并',value:'merge'},{label:'来源快照',value:'snapshot'}]" class="w-full"/></UFormField><UFormField label="source_id" :required="mode === 'snapshot'"><UInput v-model="sourceId" placeholder="稳定的数据来源标识"/></UFormField></template>
          <template v-if="type === 'job_import'"><UFormField label="岗位抽取批大小"><UInput v-model.number="batch" type="number" min="1" max="1000"/></UFormField><UFormField label="八维评估批大小"><UInput v-model.number="capabilityBatch" type="number" min="1" max="50"/><template #hint>每次模型请求包含的岗位数，建议 5–10。</template></UFormField><div class="grid gap-2"><UCheckbox v-model="promotions" label="生成自动晋升路线"/><UCheckbox v-model="lateral" label="生成自动换岗关系"/><p class="text-xs muted">岗位名称同步和八维评估始终执行。</p></div></template>
          <template v-if="type === 'job_capability_evaluation'"><UFormField label="评估范围"><USelect v-model="scope" :items="[{label:'仅缺失评分',value:'missing'},{label:'版本过期',value:'stale'},{label:'全部岗位',value:'all'}]" class="w-full"/></UFormField><UFormField label="八维评估批大小"><UInput v-model.number="capabilityBatch" type="number" min="1" max="50"/><template #hint>每次模型请求包含的岗位数，建议 5–10。</template></UFormField><UFormField label="限定 source_id（可选）"><UInput v-model="sourceId"/></UFormField></template>
          <UCheckbox v-if="type === 'salary_normalization'" v-model="force" label="强制重新计算所有岗位"/>
        </div>
        <UAlert v-if="contracts[type]" class="mt-5" icon="i-lucide-info" title="输入格式" :description="contracts[type]"/>
        <UAlert v-if="type === 'inferred_job_cleanup'" class="mt-5" color="error" icon="i-lucide-triangle-alert" title="危险维护任务" description="将固化并审阅 source=inferred 的岗位及 job_count < 2 的岗位名称；创建任务不会立即删除。"/>
        <div class="mt-6 flex items-center justify-between border-t border-default pt-5"><p class="text-sm muted">Worker 完成规划后需要管理员整单确认。</p><UButton size="lg" :loading="loading" @click="submit">创建更新任务</UButton></div>
      </UCard>
    </div>
  </div>
</template>
