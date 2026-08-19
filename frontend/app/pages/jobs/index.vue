<script setup lang="ts">
import type { JobAssistantMessage, JobAssistantSession, JobCard, JobListResult } from '~/types/job'
import { isAbortError } from '~/composables/useApi'
import { createLatestRequestController, SEARCH_DEBOUNCE_MS } from '~/utils/request-performance'

definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '岗位探索' })

type SaveState = 'idle' | 'saving' | 'saved' | 'failed'
type JobViewMode = 'list' | 'constellation'
const JobConstellationExplorer = defineAsyncComponent(() => import('~/components/visualization/jobs/JobConstellationExplorer.vue'))
const api = useJobsApi()
const route = useRoute()
const toast = useToast()
const q = ref(typeof route.query.q === 'string' ? route.query.q : '')
const sort = ref('default')
const page = ref(1)
const jobsLoading = ref(true)
const jobsError = ref('')
const assistantLoading = ref(false)
const normalResult = ref<JobListResult>({ jobs: [], total: 0, page: 1, page_size: 20, total_pages: 1 })
const assistantJobs = ref<JobCard[]>()
const assistantPage = ref(1)
const assistantPageSize = 20
const selected = ref<string | null>(null)
const viewMode = ref<JobViewMode>('list')
const message = ref('')
const messages = ref<JobAssistantMessage[]>([])
const sessions = ref<JobAssistantSession[]>([])
const sessionId = ref<number>()
const currentSession = ref<JobAssistantSession>()
const failedPrompt = ref('')
const saveStates = ref<Record<number, SaveState>>({})
const listRequests = createLatestRequestController()
let searchTimer: ReturnType<typeof setTimeout> | undefined
const inAssistantResults = computed(() => assistantJobs.value !== undefined)
const visibleJobs = computed(() => {
  if (!assistantJobs.value) return normalResult.value.jobs
  const start = (assistantPage.value - 1) * assistantPageSize
  return assistantJobs.value.slice(start, start + assistantPageSize)
})
const assistantResultTotal = computed(() => assistantJobs.value?.length || 0)

function formatTime(value?: string) {
  return value ? value.replace('T', ' ').slice(0, 16) : ''
}

async function load() {
  const ticket = listRequests.start()
  jobsLoading.value = true
  jobsError.value = ''
  try {
    const result = await api.list({ q: q.value, sort: sort.value, page: page.value, pageSize: 20, seed: sort.value === 'random' ? globalThis.crypto?.randomUUID?.() || String(Date.now()) : '' }, { signal: ticket.signal })
    if (!ticket.isCurrent()) return
    normalResult.value = result
    assistantJobs.value = undefined
  } catch (error) {
    if (isAbortError(error)) return
    jobsError.value = error instanceof Error ? error.message : '岗位加载失败，请稍后重试'
    toast.add({ title: jobsError.value, color: 'error' })
  } finally {
    if (ticket.isCurrent()) jobsLoading.value = false
  }
}

function submitSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  if (page.value === 1) load()
  else page.value = 1
}

function scheduleSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(submitSearch, SEARCH_DEBOUNCE_MS)
}

async function loadSessions() {
  try {
    sessions.value = (await api.sessions()).sessions
    currentSession.value = sessions.value.find(item => item.id === sessionId.value) || currentSession.value
  } catch { sessions.value = [] }
}

async function ask(retryContent?: string) {
  const content = (retryContent || message.value).trim()
  if (!content || assistantLoading.value) return
  messages.value.push({ role: 'user', content })
  message.value = ''
  failedPrompt.value = ''
  assistantLoading.value = true
  try {
    const response = await api.chat(content, sessionId.value)
    sessionId.value = response.session_id || sessionId.value
    messages.value.push(response.assistant_message || { role: 'assistant', content: response.reply || response.message || '已完成分析。' })
    assistantJobs.value = response.jobs || []
    assistantPage.value = 1
    await loadSessions()
  } catch (error) {
    failedPrompt.value = content
    messages.value.push({ role: 'assistant', content: error instanceof Error ? error.message : '暂时无法回答，请稍后重试。', error: true })
  } finally { assistantLoading.value = false }
}

async function saveMessage(item: JobAssistantMessage) {
  if (!item.id || saveStates.value[item.id] === 'saving' || item.is_saved) return
  saveStates.value[item.id] = 'saving'
  try {
    await api.saveMessage(item.id)
    item.is_saved = true
    saveStates.value[item.id] = 'saved'
  } catch (error) {
    saveStates.value[item.id] = 'failed'
    toast.add({ title: error instanceof Error ? error.message : '保存失败，可重试', color: 'error' })
  }
}

async function restoreSession(id: number) {
  sessionId.value = id
  assistantLoading.value = true
  try {
    const response = await api.session(id)
    currentSession.value = response.session
    messages.value = response.messages || []
    assistantJobs.value = response.jobs || []
    assistantPage.value = 1
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '会话加载失败', color: 'error' })
  } finally { assistantLoading.value = false }
}

function newSession() {
  sessionId.value = undefined
  currentSession.value = undefined
  messages.value = []
  assistantJobs.value = undefined
  assistantPage.value = 1
  failedPrompt.value = ''
}

function selectJob(id: string) {
  selected.value = id
}

function setViewMode(mode: JobViewMode) {
  viewMode.value = mode
}

function clearAssistantResults() {
  assistantJobs.value = undefined
  assistantPage.value = 1
}

function shuffledJobs(items: JobCard[]) {
  const copy = [...items]
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const random = globalThis.crypto?.getRandomValues
      ? globalThis.crypto.getRandomValues(new Uint32Array(1))[0]! / 2 ** 32
      : Math.random()
    const target = Math.floor(random * (index + 1))
    ;[copy[index], copy[target]] = [copy[target]!, copy[index]!]
  }
  return copy
}

async function refreshConstellation() {
  selected.value = null
  if (assistantJobs.value) {
    assistantJobs.value = shuffledJobs(assistantJobs.value)
    assistantPage.value = 1
    toast.add({
      title: assistantJobs.value.length > assistantPageSize ? '已从 AI 筛选结果中随机换一批岗位' : '当前 AI 筛选结果已重新排列',
      color: 'info'
    })
    return
  }
  if (sort.value !== 'random') {
    page.value = 1
    sort.value = 'random'
    return
  }
  if (page.value !== 1) {
    page.value = 1
    return
  }
  await load()
}

watch([page, sort], load)
watch(q, scheduleSearch)
onMounted(() => { load(); loadSessions() })
onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
  listRequests.cancel()
})
</script>

<template>
  <div class="cockpit-page">
    <CockpitPageHeader eyebrow="Job Exploration / Discovery" title="岗位探索" description="在统一岗位库中搜索、比较与随机漫游，也可以让 AI 助手把模糊偏好整理成可解释的候选范围。" icon="i-lucide-briefcase-business" mark="01" edition-label="岗位星图" />
    <div class="jobs-layout">
      <div class="min-w-0 page-stack">
        <UCard>
          <form class="flex flex-wrap gap-3" @submit.prevent="submitSearch">
            <UInput v-model="q" icon="i-lucide-search" placeholder="岗位、公司或地点" class="min-w-60 flex-1" />
            <USelect v-model="sort" :items="[{label:'综合排序',value:'default'},{label:'要求从高到低',value:'score_desc'},{label:'要求从低到高',value:'score_asc'},{label:'随机浏览',value:'random'}]" class="w-44" />
            <UButton type="submit">搜索</UButton>
            <div class="job-view-switch" role="group" aria-label="岗位结果视图">
              <UButton type="button" size="sm" :variant="viewMode === 'list' ? 'solid' : 'ghost'" icon="i-lucide-layout-grid" @click="setViewMode('list')">列表</UButton>
              <UButton type="button" size="sm" :variant="viewMode === 'constellation' ? 'solid' : 'ghost'" icon="i-lucide-orbit" @click="setViewMode('constellation')">星群</UButton>
            </div>
          </form>
        </UCard>
        <UAlert v-if="route.query.from === 'personality'" color="info" variant="soft" icon="i-lucide-brain-circuit" title="已带入人格测评的岗位探索线索" description="这里展示真实岗位库搜索结果；人格类型不会替代能力要求，也不会隐藏其他岗位。" />
        <UAlert
          v-if="jobsError"
          role="alert"
          color="error"
          variant="soft"
          icon="i-lucide-circle-alert"
          title="岗位列表加载失败"
          :description="jobsError"
        >
          <template #actions>
            <UButton size="sm" color="error" variant="outline" icon="i-lucide-rotate-ccw" :loading="jobsLoading" @click="load">重新加载</UButton>
          </template>
        </UAlert>
        <UAlert v-if="inAssistantResults" color="info" variant="soft" icon="i-lucide-sparkles" title="当前展示 AI 助手筛选结果" :description="`共 ${assistantResultTotal} 个岗位，每页展示 ${assistantPageSize} 个`"><template #actions><UButton size="sm" color="neutral" variant="outline" @click="clearAssistantResults">返回普通岗位列表</UButton></template></UAlert>
        <div v-if="jobsLoading" class="grid gap-4 md:grid-cols-2"><USkeleton v-for="n in 6" :key="n" class="h-72" /></div>
        <template v-else-if="visibleJobs.length">
          <JobConstellationExplorer
            v-if="viewMode === 'constellation'"
            :jobs="visibleJobs"
            :selected-id="selected"
            :source-kind="inAssistantResults ? 'assistant' : 'list'"
            :total-available="inAssistantResults ? assistantResultTotal : normalResult.total"
            :page="inAssistantResults ? assistantPage : normalResult.page"
            :page-size="inAssistantResults ? assistantPageSize : normalResult.page_size"
            :query="q"
            :sort="sort"
            @select="selectJob"
            @refresh="refreshConstellation"
          />
          <div v-else class="grid gap-4 md:grid-cols-2">
            <UCard v-for="job in visibleJobs" :key="job.id" class="job-card cursor-pointer" @click="selectJob(job.id)">
              <div class="flex items-start justify-between gap-3"><div class="min-w-0"><h2 class="truncate text-lg font-semibold">{{ job.title }}</h2><p class="mt-1 truncate text-sm muted">{{ job.company }} · {{ job.location }}</p></div><UBadge :label="`${Math.round(job.score_avg || 0)} 分`" variant="soft" /></div>
              <DeferredCapabilityRadar :scores="job.scores" height="190px" />
              <div class="flex items-center justify-between border-t border-default pt-3"><span class="font-medium text-primary">{{ job.salary || '薪资面议' }}</span><UButton size="sm" variant="ghost" trailing-icon="i-lucide-chevron-right" @click.stop="selectJob(job.id)">详情</UButton></div>
            </UCard>
          </div>
        </template>
        <UEmpty v-else-if="!jobsError" title="没有匹配岗位" icon="i-lucide-search-x" />
        <UPagination v-if="inAssistantResults && assistantResultTotal > assistantPageSize" v-model:page="assistantPage" :total="assistantResultTotal" :items-per-page="assistantPageSize" />
        <UPagination v-else-if="!inAssistantResults && normalResult.total > normalResult.page_size" v-model:page="page" :total="normalResult.total" :items-per-page="normalResult.page_size" />
      </div>

      <aside class="assistant-column"><UCard class="assistant-card">
        <template #header><div class="flex items-start justify-between gap-2"><div><h2 class="font-semibold">{{ currentSession?.title || 'AI 岗位助手' }}</h2><p class="text-xs muted">{{ currentSession?.updated_at ? `更新于 ${formatTime(currentSession.updated_at)}` : '描述偏好，我来筛选岗位' }}</p></div><UButton icon="i-lucide-square-pen" size="sm" color="neutral" variant="ghost" aria-label="新对话" @click="newSession" /></div></template>
        <div class="assistant-body">
          <USelect v-if="sessions.length" :model-value="sessionId" :items="sessions.map(x => ({ label: `${x.title || `会话 ${x.id}`} · ${formatTime(x.last_message_at || x.updated_at)}`, value: x.id }))" placeholder="历史会话" size="sm" class="w-full" @update:model-value="v => v && restoreSession(Number(v))" />
          <div class="messages">
            <div v-if="!messages.length" class="grid gap-3 py-6 text-center"><UIcon name="i-lucide-message-circle-more" class="mx-auto size-9 text-primary" /><p class="text-sm muted">例如：“找适合计算机专业、偏实践的岗位”</p></div>
            <div v-for="(item, index) in messages" :key="item.id || index" :class="['message', item.role === 'user' ? 'user' : 'assistant', item.error && 'error']">
              <div>{{ item.content }}</div>
              <div v-if="item.role === 'assistant' && item.id && !item.error" class="mt-2 border-t border-default pt-2">
                <UButton size="xs" color="neutral" variant="ghost" :loading="saveStates[item.id] === 'saving'" :icon="item.is_saved || saveStates[item.id] === 'saved' ? 'i-lucide-check' : saveStates[item.id] === 'failed' ? 'i-lucide-rotate-ccw' : 'i-lucide-bookmark'" @click="saveMessage(item)">{{ item.is_saved || saveStates[item.id] === 'saved' ? '已保存' : saveStates[item.id] === 'failed' ? '保存失败，重试' : '保存回答与筛选结果' }}</UButton>
              </div>
            </div>
            <UButton v-if="failedPrompt" size="sm" color="error" variant="soft" icon="i-lucide-rotate-ccw" :disabled="assistantLoading" @click="ask(failedPrompt)">重试上一条问题</UButton>
            <div v-if="assistantLoading" class="message assistant muted">正在分析…</div>
          </div>
          <form class="grid gap-2" @submit.prevent="ask()"><UTextarea v-model="message" :rows="3" autoresize :maxrows="6" placeholder="输入岗位偏好或问题…" /><UButton type="submit" block :loading="assistantLoading" icon="i-lucide-send">发送</UButton></form>
        </div>
      </UCard></aside>
    </div>
    <JobDetailModal :job-id="selected" @close="selected = null" />
  </div>
</template>

<style scoped>
.jobs-layout { display: grid; gap: 1rem; align-items: start; }
.job-card { transition: border-color .18s ease, transform .18s ease; }
.job-card:hover { border-color: color-mix(in srgb, var(--ui-primary) 45%, transparent); transform: translateY(-2px); }
.job-view-switch { display: inline-flex; align-items: center; gap: .15rem; border: 1px solid var(--ui-border); border-radius: .65rem; padding: .14rem; }
.assistant-column { position: sticky; top: 4.75rem; z-index: 10; align-self: start; min-width: 0; max-height: calc(100vh - 5.5rem); }
.assistant-card { max-height: calc(100vh - 5.5rem); overflow: hidden; }
.assistant-body { display: grid; gap: .75rem; }
.messages { display: grid; align-content: start; gap: .6rem; min-height: 260px; max-height: calc(100vh - 370px); overflow-y: auto; }
.message { max-width: 92%; border-radius: .8rem; padding: .65rem .75rem; white-space: pre-wrap; font-size: .875rem; line-height: 1.55; }
.message.user { justify-self: end; background: var(--ui-primary); color: white; }
.message.assistant { justify-self: start; background: var(--ui-bg-elevated); border: 1px solid var(--ui-border); }
.message.error { border-color: color-mix(in srgb, var(--ui-error) 40%, transparent); }
@media (min-width: 1280px) { .jobs-layout { grid-template-columns: minmax(0, 1fr) 350px; } }
@media (max-width: 1279px) { .assistant-column, .assistant-card { position: static; max-height: none; overflow: visible; } }
</style>
