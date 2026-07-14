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
    result.value = body.data
    persist()
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
})

watch([answers, current, started], persist, { deep: true })
</script>

<template>
  <div class="page-stack mx-auto w-full max-w-4xl">
    <div class="page-heading">
      <h1 class="flex items-center gap-2"><UIcon name="i-lucide-brain" class="text-primary"/>职业性格测试</h1>
      <p class="muted">用一组二选一问题了解职业偏好，约 5 分钟完成</p>
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
  </div>
</template>
