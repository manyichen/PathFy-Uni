<script setup lang="ts">
import type { CodeEnvelope } from '~/types/api'

definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '性格测试' })

const api = useApi()
const auth = useAuth()
const toast = useToast()
const questions = ref<any[]>([])
const answers = ref<Record<number, string>>({})
const result = ref<any>()
const loading = ref(true)
const submitting = ref(false)
const started = ref(false)
const current = ref(0)
const history = ref<any[]>([])
const historyOpen = ref(false)
const historyLoading = ref(false)
const restoringId = ref<number>()
const cacheKey = computed(() => `career_personality_v1_${auth.user.value?.id || 'guest'}`)
const answered = computed(() => Object.keys(answers.value).length)
const question = computed(() => questions.value[current.value])

function persist() {
  if (!import.meta.client) return
  localStorage.setItem(cacheKey.value, JSON.stringify({
    v: 1, answers: answers.value, result: result.value, started: started.value,
    currentQuestionIndex: current.value, savedAt: Date.now()
  }))
}

function start() {
  started.value = true
  persist()
}

function select(value: string) {
  if (!question.value) return
  answers.value[question.value.id] = value
  if (current.value < questions.value.length - 1) current.value += 1
}

function normalizeProfile(profile: any) {
  const detailed = profile?.detailed_analysis || {}
  const recommendations = detailed.job_recommendations || profile?.job_recommendations || {}
  const recommendedJobs = Array.isArray(profile?.recommended_jobs)
    ? profile.recommended_jobs
    : String(profile?.recommended_jobs || '').split(/[,，]/).map(item => item.trim()).filter(Boolean)
  return {
    ...profile,
    profile_id: profile?.profile_id || profile?.id,
    dimension_analysis: profile?.dimension_analysis || detailed.dimension_analysis,
    complete_analysis: profile?.complete_analysis || detailed.complete_analysis,
    job_recommendations: recommendations,
    recommended_jobs: recommendedJobs.length ? recommendedJobs : (recommendations.recommended_jobs || [])
  }
}

async function loadHistory() {
  const userId = auth.user.value?.id
  if (!userId) return
  historyLoading.value = true
  try {
    const body = await api.request<CodeEnvelope<any[]>>(`/api/personality/history/${userId}`)
    if (body.code === 200) history.value = body.data || []
  } finally { historyLoading.value = false }
}

async function openHistory() {
  historyOpen.value = true
  try { await loadHistory() }
  catch (error) { toast.add({ title: error instanceof Error ? error.message : '历史记录加载失败', color: 'error' }) }
}

async function restoreProfile(profileId: number, close = true) {
  restoringId.value = profileId
  try {
    const body = await api.request<CodeEnvelope<any>>(`/api/personality/profile/${profileId}`)
    if (body.code !== 200) throw new Error(body.msg || '记录加载失败')
    result.value = normalizeProfile(body.data)
    started.value = true
    if (close) historyOpen.value = false
    persist()
  } finally { restoringId.value = undefined }
}

async function submit() {
  if (answered.value !== questions.value.length) {
    toast.add({ title: '请完成全部题目', color: 'warning' })
    return
  }
  submitting.value = true
  try {
    const body = await api.request<CodeEnvelope<any>>('/api/personality/submit', {
      method: 'POST',
      body: { answers: Object.entries(answers.value).map(([id, user_choice]) => ({ question_id: Number(id), user_choice })) }
    })
    if (body.code !== 200) throw new Error(body.msg || '提交失败')
    result.value = normalizeProfile(body.data)
    persist()
    await loadHistory()
    toast.add({ title: '测试完成', color: 'success' })
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '提交失败', color: 'error' })
  } finally {
    submitting.value = false
  }
}

function restart() {
  answers.value = {}
  result.value = undefined
  current.value = 0
  started.value = false
  persist()
}

onMounted(async () => {
  auth.hydrate()
  const raw = localStorage.getItem(cacheKey.value)
  if (raw) {
    try {
      const cache = JSON.parse(raw)
      answers.value = Array.isArray(cache.answers)
        ? Object.fromEntries(cache.answers.map((item: any) => [Number(item.question_id), item.user_choice]))
        : (cache.answers || {})
      result.value = cache.result || cache.personalityProfile
      started.value = cache.started != null
        ? Boolean(cache.started)
        : (cache.showStartScreen === false || Boolean(Object.keys(answers.value).length))
      current.value = Number(cache.currentQuestionIndex || 0)
    } catch { /* ignore invalid cache */ }
  }
  try {
    const body = await api.request<CodeEnvelope<any[]>>('/api/personality/questions')
    if (body.code === 200) questions.value = body.data || []
    current.value = Math.min(current.value, Math.max(0, questions.value.length - 1))
  } finally {
    loading.value = false
  }
  try {
    await loadHistory()
    if (!result.value && !answered.value && history.value[0]?.id) await restoreProfile(history.value[0].id, false)
  } catch { /* history is optional; local progress remains available */ }
})

watch([answers, current, started], persist, { deep: true })
</script>

<template>
  <div class="page-stack mx-auto w-full max-w-4xl">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div class="page-heading">
        <h1 class="flex items-center gap-2"><UIcon name="i-lucide-brain" class="text-primary"/>职业性格测试</h1>
        <p class="muted">用一组二选一问题了解职业偏好，约 5 分钟完成</p>
      </div>
      <UButton color="neutral" variant="soft" icon="i-lucide-history" @click="openHistory">历史记录<span v-if="history.length">（{{ history.length }}）</span></UButton>
    </div>

    <USkeleton v-if="loading" class="h-96" />

    <UCard v-else-if="!started && !result" class="overflow-hidden">
      <div class="grid items-center gap-8 p-3 md:grid-cols-[1fr_280px]">
        <div>
          <UBadge label="MBTI 职业偏好" variant="soft" />
          <h2 class="mt-4 text-2xl font-semibold">从你的自然选择出发</h2>
          <p class="mt-3 leading-7 muted">测试没有标准答案。请选择更接近日常状态的选项，完成后可查看性格特征、核心优势和推荐岗位。</p>
          <div class="mt-6 flex flex-wrap gap-5 text-sm muted">
            <span class="flex items-center gap-2"><UIcon name="i-lucide-list-checks" />{{ questions.length }} 道题</span>
            <span class="flex items-center gap-2"><UIcon name="i-lucide-clock-3" />约 5 分钟</span>
            <span class="flex items-center gap-2"><UIcon name="i-lucide-save" />自动保存进度</span>
          </div>
          <UButton class="mt-7" size="xl" icon="i-lucide-play" @click="start">{{ answered ? '继续测试' : '开始测试' }}</UButton>
        </div>
        <div class="grid aspect-square place-items-center rounded-3xl bg-primary/10">
          <UIcon name="i-lucide-brain-circuit" class="size-28 text-primary" />
        </div>
      </div>
    </UCard>

    <template v-else-if="!result">
      <div class="flex items-center gap-4">
        <UProgress :model-value="answered" :max="questions.length" class="flex-1" />
        <span class="text-sm font-medium">{{ answered }}/{{ questions.length }}</span>
      </div>
      <UCard v-if="question">
        <template #header>
          <p class="text-sm text-primary">第 {{ current + 1 }} 题</p>
          <h2 class="mt-1 text-xl font-semibold">{{ question.question_text }}</h2>
        </template>
        <div class="grid gap-3">
          <UButton color="neutral" variant="outline" size="xl" block class="justify-start py-5 text-left" @click="select('A')">A · {{ question.option_a }}</UButton>
          <UButton color="neutral" variant="outline" size="xl" block class="justify-start py-5 text-left" @click="select('B')">B · {{ question.option_b }}</UButton>
        </div>
      </UCard>
      <div class="flex justify-between">
        <UButton :disabled="current === 0" color="neutral" variant="ghost" icon="i-lucide-arrow-left" @click="() => { current-- }">上一题</UButton>
        <UButton v-if="answered === questions.length" :loading="submitting" size="lg" @click="submit">提交测试</UButton>
        <UButton v-else :disabled="current >= questions.length - 1" color="neutral" variant="ghost" trailing-icon="i-lucide-arrow-right" @click="() => { current++ }">下一题</UButton>
      </div>
    </template>

    <template v-else>
      <UCard>
        <div class="text-center">
          <p class="text-5xl font-bold text-primary">{{ result.mbti_type }}</p>
          <h2 class="mt-3 text-xl font-semibold">{{ result.complete_analysis?.name || '性格分析' }}</h2>
          <p class="mx-auto mt-4 max-w-3xl leading-7 muted">{{ result.complete_analysis?.summary || result.personality_analysis }}</p>
        </div>
      </UCard>
      <div class="panel-grid two">
        <UCard><template #header><h2 class="font-semibold">核心优势</h2></template><ul class="list-disc space-y-2 pl-5"><li v-for="x in result.complete_analysis?.core_strengths || []" :key="x">{{ x }}</li></ul></UCard>
        <UCard><template #header><h2 class="font-semibold">推荐岗位</h2></template><div class="flex flex-wrap gap-2"><UBadge v-for="x in result.recommended_jobs || []" :key="x" :label="x" /></div></UCard>
      </div>
      <UButton variant="outline" icon="i-lucide-rotate-ccw" @click="restart">重新测试</UButton>
    </template>

    <UModal v-model:open="historyOpen" title="性格测试记录">
      <template #body>
        <div v-if="historyLoading" class="grid gap-2"><USkeleton v-for="n in 4" :key="n" class="h-20" /></div>
        <div v-else class="grid gap-2">
          <button v-for="item in history" :key="item.id" type="button" class="flex items-center justify-between gap-3 rounded-xl border border-default p-3 text-left transition hover:border-primary" :disabled="restoringId === item.id" @click="restoreProfile(item.id)">
            <span class="flex min-w-0 items-center gap-3"><strong class="grid size-11 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">{{ item.mbti_type }}</strong><span class="min-w-0"><span class="block text-sm font-medium">{{ item.mbti_type }} · 职业性格测试</span><small class="muted">{{ String(item.created_at || '').replace('T', ' ').slice(0, 16) }}</small></span></span>
            <UIcon :name="restoringId === item.id ? 'i-lucide-loader-circle' : 'i-lucide-chevron-right'" :class="restoringId === item.id && 'animate-spin'" class="shrink-0" />
          </button>
          <UEmpty v-if="!history.length" title="暂无测试记录" description="完成测试后，结果会保存在这里。" />
        </div>
      </template>
    </UModal>
  </div>
</template>
