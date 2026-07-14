<script setup lang="ts">
import type { CapabilityScores, CodeEnvelope } from '~/types/api'

definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '能力画像' })

const api = useApi()
const auth = useAuth()
const toast = useToast()
const name = ref('')
const major = ref('')
const text = ref('')
const files = ref<File[]>([])
const loading = ref(false)
const restoring = ref(false)
const result = ref<any>()
const history = ref<any[]>([])
const historyOpen = ref(false)
const activeResumeId = ref<number>()
const cacheKey = computed(() => `career_profile_portrait_v1_${auth.user.value?.id || 'guest'}`)
const scores = computed<Partial<CapabilityScores>>(() => result.value?.scores || scoreFields(result.value || {}))
const analysis = computed(() => result.value?.detailed_analysis || {})
const materials = computed(() => analysis.value.material_summary || result.value?.materials || [])

const dimensionLabels: Record<string, string> = {
  cap_req_theory: '专业理论', cap_req_cross: '交叉学科', cap_req_practice: '实践技能', cap_req_digital: '数字素养',
  cap_req_innovation: '创新创业', cap_req_teamwork: '团队协作', cap_req_social: '社会网络', cap_req_growth: '学习成长'
}

function scoreFields(row: any) {
  return Object.fromEntries(Object.keys(dimensionLabels).map(key => [key, Number(row?.[key] || 0)]))
}

function choose(event: Event) {
  const selected = Array.from((event.target as HTMLInputElement).files || [])
  files.value = [...files.value, ...selected].slice(0, 12)
}

function removeFile(index: number) { files.value.splice(index, 1) }

function displayText(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  if (Array.isArray(value)) return value.map(displayText).filter(Boolean).join('；')
  if (typeof value === 'object') {
    const row = value as Record<string, unknown>
    return displayText(row.interpretation || row.analysis || row.description || row.summary || row.content || row.plan || row.goal || row.name || row.dimension || Object.values(row))
  }
  return ''
}

function arrayOf(value: unknown): any[] { return Array.isArray(value) ? value : value ? [value] : [] }
function dimensionName(item: any) { return item?.dimension || item?.name || item?.label || '能力维度' }
function dimensionScore(item: any) { return Number(item?.score ?? item?.value ?? 0) }

function persist(payload: any) {
  if (!import.meta.client) return
  localStorage.setItem(cacheKey.value, JSON.stringify({ v: 1, savedAt: Date.now(), ...payload }))
}

async function loadPortrait(id: number, quiet = false) {
  restoring.value = true
  try {
    const response = await api.request<CodeEnvelope<any>>(`/api/profile/result/${id}`)
    if (response.code !== 200 || !response.data) throw new Error(response.msg || '画像加载失败')
    const row = response.data
    result.value = { ...row, scores: scoreFields(row) }
    activeResumeId.value = id
    name.value = row.name || name.value
    major.value = row.major || major.value
    persist({ ...result.value, resume_id: id })
    historyOpen.value = false
    if (!quiet) toast.add({ title: '已恢复历史画像', color: 'success' })
  } catch (error) {
    if (!quiet) toast.add({ title: error instanceof Error ? error.message : '画像加载失败', color: 'error' })
    throw error
  } finally { restoring.value = false }
}

async function submit() {
  if (!name.value || !major.value || (!files.value.length && !text.value.trim())) {
    toast.add({ title: '请填写姓名、专业并提供至少一份材料', color: 'warning' })
    return
  }
  loading.value = true
  try {
    const body = new FormData()
    body.append('name', name.value)
    body.append('major', major.value)
    if (text.value) body.append('profile_text', text.value)
    for (const file of files.value) body.append('materials', file)
    const response = await api.request<CodeEnvelope<any>>('/api/profile/upload', { method: 'POST', body })
    if (response.code !== 200) throw new Error(response.msg || '分析失败')
    result.value = response.data
    activeResumeId.value = response.data.resume_id
    persist(response.data)
    const list = await api.request<CodeEnvelope<any[]>>('/api/profile/resumes')
    if (list.code === 200) history.value = list.data || []
    toast.add({ title: '能力画像生成成功', color: 'success' })
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '分析失败', color: 'error' })
  } finally { loading.value = false }
}

onMounted(async () => {
  auth.hydrate()
  const raw = localStorage.getItem(cacheKey.value)
  let cached: any
  if (raw) try { cached = JSON.parse(raw); result.value = cached; activeResumeId.value = cached.resume_id; name.value = cached.name || ''; major.value = cached.major || '' } catch { /* ignore */ }
  try {
    const response = await api.request<CodeEnvelope<any[]>>('/api/profile/resumes')
    if (response.code !== 200) return
    history.value = response.data || []
    const latest = history.value[0]
    if (latest?.id) await loadPortrait(latest.id, true).catch(() => undefined)
  } catch {
    if (cached) result.value = cached
  }
})
</script>

<template>
  <div class="page-stack">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div class="page-heading"><h1 class="flex items-center gap-2"><UIcon name="i-lucide-radar" class="text-primary" />学生就业能力画像</h1><p class="muted">整合简历、证书、项目和补充材料，形成八维能力证据</p></div>
      <UButton icon="i-lucide-history" color="neutral" variant="soft" @click="() => { historyOpen = true }">历史画像</UButton>
    </div>

    <div class="profile-top-grid">
      <UCard>
        <template #header><div><h2 class="font-semibold">生成画像</h2><p class="text-xs muted">最多 12 份材料，可混合上传</p></div></template>
        <div class="grid gap-3">
          <div class="grid grid-cols-2 gap-3"><UFormField label="姓名"><UInput v-model="name" class="w-full" /></UFormField><UFormField label="专业"><UInput v-model="major" class="w-full" /></UFormField></div>
          <UFormField label="上传材料"><UInput type="file" multiple class="w-full" @change="choose" /></UFormField>
          <div v-if="files.length" class="flex flex-wrap gap-1.5"><UBadge v-for="(file, i) in files" :key="`${file.name}-${i}`" :label="file.name" color="neutral" variant="soft" class="max-w-full cursor-pointer truncate" @click="removeFile(Number(i))" /></div>
          <UFormField label="补充文本"><UTextarea v-model="text" :rows="4" autoresize :maxrows="8" class="w-full" placeholder="补充课程、项目、竞赛或职业目标" /></UFormField>
          <UButton block :loading="loading" icon="i-lucide-sparkles" @click="submit">生成能力画像</UButton>
        </div>
      </UCard>

      <UCard>
        <template #header><div class="flex items-center justify-between"><h2 class="font-semibold">能力雷达</h2><UBadge v-if="activeResumeId" :label="`画像 #${activeResumeId}`" color="neutral" variant="soft" /></div></template>
        <CapabilityRadar :scores="scores" height="315px" />
      </UCard>

      <UCard>
        <template #header><h2 class="font-semibold">能力评估</h2></template>
        <div class="grid gap-5">
          <div><div class="flex items-center justify-between"><span class="text-sm muted">能力完整度</span><strong class="text-2xl">{{ Number(result?.completeness || 0).toFixed(0) }}</strong></div><UProgress :model-value="result?.completeness || 0" class="mt-2" /><p class="mt-2 text-sm leading-6 muted">{{ analysis.completeness_analysis || '覆盖材料越丰富，完整度评估越可靠。' }}</p></div>
          <div><div class="flex items-center justify-between"><span class="text-sm muted">就业竞争力</span><strong class="text-2xl">{{ Number(result?.competitiveness || 0).toFixed(0) }}</strong></div><UProgress :model-value="result?.competitiveness || 0" class="mt-2" /><p class="mt-2 text-sm leading-6 muted">{{ analysis.competitiveness_analysis || '综合八维能力与就业场景给出竞争力判断。' }}</p></div>
        </div>
      </UCard>
    </div>

    <UEmpty v-if="!result" title="还没有能力画像" description="生成新画像，或从历史记录中恢复" icon="i-lucide-radar" />
    <template v-else>
      <UCard><template #header><h2 class="font-semibold">整体评价</h2></template><p class="leading-7">{{ analysis.overall_evaluation || '暂无整体评价' }}</p></UCard>

      <div class="grid gap-4 lg:grid-cols-3">
        <UCard><template #header><h2 class="font-semibold">材料来源</h2></template><div class="grid gap-2"><div v-for="(item, i) in materials" :key="`${item.name}-${i}`" class="rounded-lg border border-default p-3"><div class="flex justify-between gap-2"><span class="truncate text-sm font-medium">{{ item.name || '补充文本' }}</span><UBadge :label="item.status === 'ok' ? '已识别' : item.status || '已使用'" :color="item.status === 'ok' ? 'success' : 'neutral'" size="sm" variant="soft" /></div><p class="mt-1 text-xs muted">{{ item.kind || '材料' }}<template v-if="item.chars"> · {{ item.chars }} 字</template></p></div><p v-if="!materials.length" class="text-sm muted">暂无材料来源记录</p></div></UCard>
        <UCard><template #header><h2 class="font-semibold">优势维度</h2></template><div class="grid gap-2"><div v-for="item in arrayOf(analysis.advantage_dimensions)" :key="dimensionName(item)" class="flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 px-3 py-2"><span class="text-sm font-medium">{{ dimensionName(item) }}</span><strong class="text-success">{{ dimensionScore(item) }} 分</strong></div><p v-if="!arrayOf(analysis.advantage_dimensions).length" class="text-sm muted">暂无优势维度数据</p></div></UCard>
        <UCard><template #header><h2 class="font-semibold">待提升维度</h2></template><div class="grid gap-2"><div v-for="item in arrayOf(analysis['劣势_dimensions'] || analysis.weakness_dimensions)" :key="dimensionName(item)" class="flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 px-3 py-2"><span class="text-sm font-medium">{{ dimensionName(item) }}</span><strong class="text-warning">{{ dimensionScore(item) }} 分</strong></div><p v-if="!arrayOf(analysis['劣势_dimensions'] || analysis.weakness_dimensions).length" class="text-sm muted">暂无待提升维度数据</p></div></UCard>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <UCard><template #header><div><h2 class="font-semibold">短期行动计划</h2><p class="text-xs muted">优先形成近期可执行、可验证的能力证据</p></div></template><ol class="grid gap-3"><li v-for="(item, i) in arrayOf(analysis.short_term_plan)" :key="i" class="flex gap-3 rounded-lg bg-elevated p-3"><span class="grid size-7 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary">{{ Number(i) + 1 }}</span><div><p v-if="typeof item === 'object' && (item.title || item.action || item.dimension)" class="text-sm font-medium">{{ item.title || item.action || item.dimension }}</p><p class="text-sm leading-6 muted">{{ displayText(typeof item === 'object' ? (item.plan || item.description || item.content || item.goal || item) : item) }}</p></div></li><p v-if="!arrayOf(analysis.short_term_plan).length" class="text-sm muted">暂无短期行动计划</p></ol></UCard>
        <UCard><template #header><div><h2 class="font-semibold">长期发展目标</h2><p class="text-xs muted">将优势能力沉淀为稳定的职业竞争力</p></div></template><ol class="grid gap-3"><li v-for="(item, i) in arrayOf(analysis.long_term_goals)" :key="i" class="flex gap-3 rounded-lg bg-elevated p-3"><span class="grid size-7 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary">{{ Number(i) + 1 }}</span><div><p v-if="typeof item === 'object' && (item.title || item.goal || item.dimension)" class="text-sm font-medium">{{ item.title || item.goal || item.dimension }}</p><p class="text-sm leading-6 muted">{{ displayText(typeof item === 'object' ? (item.description || item.content || item.plan || item) : item) }}</p></div></li><p v-if="!arrayOf(analysis.long_term_goals).length" class="text-sm muted">暂无长期发展目标</p></ol></UCard>
      </div>

      <UCard><template #header><h2 class="font-semibold">各维度详细分析</h2></template><div class="dimension-grid"><article v-for="item in arrayOf(analysis.dimension_analysis)" :key="dimensionName(item)" class="rounded-xl border border-default p-4"><div class="flex items-center justify-between"><h3 class="font-medium">{{ dimensionName(item) }}</h3><div class="flex items-center gap-2"><strong class="text-primary">{{ dimensionScore(item) }}</strong><UBadge v-if="item.level" :label="item.level" color="neutral" variant="soft" /></div></div><p class="mt-2 text-sm leading-6 muted">{{ displayText(item.interpretation || item.analysis || item.description) }}</p></article><p v-if="!arrayOf(analysis.dimension_analysis).length" class="text-sm muted">暂无维度详细分析</p></div></UCard>

      <UCard><template #header><div><h2 class="font-semibold">行业适配性分析</h2><p class="text-xs muted">结合能力结构判断更容易发挥优势的行业场景</p></div></template><div class="industry-grid"><article v-for="(item, i) in arrayOf(analysis.industry_match || analysis.industry_adaptability)" :key="i" class="rounded-lg bg-elevated p-4"><div v-if="typeof item === 'object'" class="mb-1 flex items-center justify-between"><strong>{{ item.industry || item.name || item.field || '适配方向' }}</strong><UBadge v-if="item.match_score || item.score" :label="`${item.match_score || item.score} 分`" variant="soft" /></div><p class="text-sm leading-6 muted">{{ displayText(item) }}</p></article><p v-if="!arrayOf(analysis.industry_match || analysis.industry_adaptability).length" class="text-sm muted">暂无行业适配分析</p></div></UCard>
      <UCard><template #header><div><h2 class="font-semibold">材料关键词分析</h2><p class="text-xs muted">从全部材料中提取的能力、经历和职业方向关键词</p></div></template><div class="flex flex-wrap gap-2"><UBadge v-for="(item, i) in arrayOf(analysis.material_keywords || analysis.keywords || analysis.keyword_analysis)" :key="i" :label="displayText(item)" color="neutral" variant="soft" /><p v-if="!arrayOf(analysis.material_keywords || analysis.keywords || analysis.keyword_analysis).length" class="text-sm muted">暂无材料关键词</p></div></UCard>
    </template>

    <UModal v-model:open="historyOpen" title="历史能力画像">
      <template #body><div class="grid gap-2"><button v-for="item in history" :key="item.id" type="button" class="flex items-center justify-between rounded-xl border border-default p-3 text-left hover:border-primary" @click="loadPortrait(item.id)"><div><p class="font-medium">{{ item.name }} · {{ item.major }}</p><p class="text-xs muted">{{ String(item.create_time || '').replace('T', ' ').slice(0, 19) }}</p></div><div class="text-right"><p class="font-semibold">{{ Math.round(item.score_avg || 0) }} 分</p><p class="text-xs muted">完整度 {{ Math.round(item.completeness || 0) }}</p></div></button><UEmpty v-if="!history.length" title="暂无历史画像" /></div></template>
    </UModal>
  </div>
</template>

<style scoped>
.profile-top-grid { display: grid; gap: 1rem; align-items: stretch; }
.dimension-grid { display: grid; gap: .75rem; }
 .industry-grid { display: grid; gap: .75rem; }
@media (min-width: 768px) { .dimension-grid, .industry-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (min-width: 1280px) { .profile-top-grid { grid-template-columns: minmax(300px, .9fr) minmax(360px, 1.1fr) minmax(300px, .9fr); } }
</style>
