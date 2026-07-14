<script setup lang="ts">
definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '岗位探索' })

const api = useJobsApi()
const toast = useToast()
const q = ref('')
const sort = ref('default')
const page = ref(1)
const jobsLoading = ref(false)
const assistantLoading = ref(false)
const result = ref<any>({ jobs: [], total: 0, total_pages: 1 })
const selected = ref<string | null>(null)
const message = ref('')
const messages = ref<any[]>([])
const sessions = ref<any[]>([])
const sessionId = ref<number>()

async function load() {
  jobsLoading.value = true
  try {
    result.value = await api.list({ q: q.value, sort: sort.value, page: page.value, pageSize: 20, seed: sort.value === 'random' ? crypto.randomUUID?.() || String(Date.now()) : '' })
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '岗位加载失败', color: 'error' })
  } finally { jobsLoading.value = false }
}

async function loadSessions() {
  try {
    sessions.value = (await api.sessions()).sessions || []
  } catch { sessions.value = [] }
}

async function ask() {
  const content = message.value.trim()
  if (!content || assistantLoading.value) return
  messages.value.push({ role: 'user', content })
  message.value = ''
  assistantLoading.value = true
  try {
    const response = await api.chat(content, sessionId.value)
    sessionId.value = response.session_id || sessionId.value
    const assistantMessage = response.assistant_message || { role: 'assistant', content: response.reply || response.message || '已完成分析。' }
    messages.value.push(assistantMessage)
    if (response.jobs?.length) result.value = { ...result.value, jobs: response.jobs, total: response.jobs.length, total_pages: 1 }
    await loadSessions()
  } catch (error) {
    messages.value.push({ role: 'assistant', content: error instanceof Error ? error.message : '暂时无法回答，请稍后重试。', error: true })
  } finally { assistantLoading.value = false }
}

async function restoreSession(id: number) {
  sessionId.value = id
  assistantLoading.value = true
  try {
    const response = await api.session(id)
    messages.value = response.messages || []
    if (response.jobs?.length) result.value = { ...result.value, jobs: response.jobs, total: response.jobs.length, total_pages: 1 }
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '会话加载失败', color: 'error' })
  } finally { assistantLoading.value = false }
}

function newSession() {
  sessionId.value = undefined
  messages.value = []
}

watch([page, sort], load)
onMounted(() => { load(); loadSessions() })
</script>

<template>
  <div class="page-stack">
    <div class="page-heading">
      <h1 class="flex items-center gap-2"><UIcon name="i-lucide-briefcase-business" class="text-primary"/>岗位探索</h1>
      <p class="muted">浏览岗位能力要求，右侧助手可直接帮你筛选和解释</p>
    </div>

    <div class="jobs-layout">
      <main class="min-w-0 page-stack">
        <UCard>
          <form class="flex flex-wrap gap-3" @submit.prevent="page = 1; load()">
            <UInput v-model="q" icon="i-lucide-search" placeholder="岗位、公司或地点" class="min-w-60 flex-1" />
            <USelect v-model="sort" :items="[{label:'综合排序',value:'default'},{label:'要求从高到低',value:'score_desc'},{label:'要求从低到高',value:'score_asc'},{label:'随机浏览',value:'random'}]" class="w-44" />
            <UButton type="submit">搜索</UButton>
          </form>
        </UCard>

        <div v-if="jobsLoading" class="grid gap-4 md:grid-cols-2"><USkeleton v-for="n in 6" :key="n" class="h-72" /></div>
        <div v-else-if="result.jobs.length" class="grid gap-4 md:grid-cols-2">
          <UCard v-for="job in result.jobs" :key="job.id" class="job-card cursor-pointer" @click="selected = job.id">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0"><h2 class="truncate text-lg font-semibold">{{ job.title }}</h2><p class="mt-1 truncate text-sm muted">{{ job.company }} · {{ job.location }}</p></div>
              <UBadge :label="`${Math.round(job.score_avg || 0)} 分`" variant="soft" />
            </div>
            <CapabilityRadar :scores="job.scores || {}" height="190px" />
            <div class="flex items-center justify-between border-t border-default pt-3">
              <span class="font-medium text-primary">{{ job.salary || '薪资面议' }}</span>
              <UButton size="sm" variant="ghost" trailing-icon="i-lucide-chevron-right" @click.stop="selected = job.id">详情</UButton>
            </div>
          </UCard>
        </div>
        <UEmpty v-else title="没有匹配岗位" icon="i-lucide-search-x" />
        <UPagination v-if="result.total > (result.page_size || 20)" v-model:page="page" :total="result.total" :items-per-page="result.page_size || 20" />
      </main>

      <aside class="assistant-column">
        <UCard class="assistant-card">
          <template #header>
            <div class="flex items-center justify-between gap-2">
              <div><h2 class="font-semibold">AI 岗位助手</h2><p class="text-xs muted">描述你的偏好，我来筛选岗位</p></div>
              <UButton icon="i-lucide-square-pen" size="sm" color="neutral" variant="ghost" aria-label="新对话" @click="newSession" />
            </div>
          </template>
          <div class="assistant-body">
            <USelect v-if="sessions.length" :model-value="sessionId" :items="sessions.map(x => ({ label: x.title || `会话 ${x.id}`, value: x.id }))" placeholder="历史会话" size="sm" class="w-full" @update:model-value="v => v && restoreSession(Number(v))" />
            <div class="messages">
              <div v-if="!messages.length" class="grid gap-3 py-6 text-center">
                <UIcon name="i-lucide-message-circle-more" class="mx-auto size-9 text-primary" />
                <p class="text-sm muted">例如：“找适合计算机专业、偏实践的岗位”</p>
              </div>
              <div v-for="(item, index) in messages" :key="item.id || index" :class="['message', item.role === 'user' ? 'user' : 'assistant']">{{ item.content }}</div>
              <div v-if="assistantLoading" class="message assistant muted">正在分析…</div>
            </div>
            <form class="grid gap-2" @submit.prevent="ask">
              <UTextarea v-model="message" :rows="3" autoresize :maxrows="6" placeholder="输入岗位偏好或问题…" />
              <UButton type="submit" block :loading="assistantLoading" icon="i-lucide-send">发送</UButton>
            </form>
          </div>
        </UCard>
      </aside>
    </div>

    <JobDetailModal :job-id="selected" @close="selected = null" />
  </div>
</template>

<style scoped>
.jobs-layout { display: grid; gap: 1rem; align-items: start; }
.job-card { transition: border-color .18s ease, transform .18s ease; }
.job-card:hover { border-color: color-mix(in srgb, var(--ui-primary) 45%, transparent); transform: translateY(-2px); }
.assistant-column { min-width: 0; }
.assistant-card { position: sticky; top: 5.5rem; }
.assistant-body { display: grid; gap: .75rem; }
.messages { display: grid; align-content: start; gap: .6rem; min-height: 260px; max-height: calc(100vh - 370px); overflow-y: auto; }
.message { max-width: 92%; border-radius: .8rem; padding: .65rem .75rem; white-space: pre-wrap; font-size: .875rem; line-height: 1.55; }
.message.user { justify-self: end; background: var(--ui-primary); color: white; }
.message.assistant { justify-self: start; background: var(--ui-bg-elevated); border: 1px solid var(--ui-border); }
@media (min-width: 1280px) { .jobs-layout { grid-template-columns: minmax(0, 1fr) 340px; } }
</style>
