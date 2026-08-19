<script setup lang="ts">
import type { PersonalityAnswer, PersonalityQuestion, PersonalityResult } from '~/types/personality'
import PersonalityFingerprint from '~/components/visualization/personality/PersonalityFingerprint.vue'
import { usePersonalityApi } from '~/composables/api/usePersonalityApi'
import { canRestorePersonalityProgress, questionSetSignature, readPersonalityCache, writePersonalityCache } from '~/utils/cache/personality-cache'

definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '性格测试' })

const personalityApi = usePersonalityApi()
const auth = useAuth()
const toast = useToast()
const questions = ref<PersonalityQuestion[]>([])
const answers = ref<Record<number, 'A' | 'B'>>({})
const result = ref<PersonalityResult>()
const loading = ref(true)
const submitting = ref(false)
const started = ref(false)
const current = ref(0)
const fingerprintAnimationRevision = ref(0)
const historyOpen = ref(false)
const historyLoading = ref(false)
const historyItems = ref<PersonalityResult[]>([])
const activatingId = ref<number>()
const preferenceSaving = ref(false)
const deleteOpen = ref(false)
const deleting = ref(false)
const questionSignature = ref('')
const cacheUserId = computed(() => auth.user.value?.id || 'guest')
const answered = computed(() => Object.keys(answers.value).length)
const question = computed(() => questions.value[current.value])
const explorationJob = computed(() => result.value?.recommended_jobs?.[0] || '')

function persist() {
  writePersonalityCache(cacheUserId.value, {
    answers: answers.value,
    result: result.value,
    started: started.value,
    currentQuestionIndex: current.value,
    questionSignature: questionSignature.value || undefined,
    savedAt: new Date().toISOString()
  })
}

function start() {
  started.value = true
  persist()
}

function select(value: 'A' | 'B') {
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
    const payload: PersonalityAnswer[] = Object.entries(answers.value).map(([id, user_choice]) => ({ question_id: Number(id), user_choice }))
    result.value = await personalityApi.submit(payload)
    fingerprintAnimationRevision.value += 1
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

function openDelete() { deleteOpen.value = true }
function closeDelete() { deleteOpen.value = false }

async function openHistory() {
  historyOpen.value = true
  historyLoading.value = true
  try {
    historyItems.value = await personalityApi.history()
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '历史测评加载失败', color: 'error' })
  } finally {
    historyLoading.value = false
  }
}

async function activateHistory(profileId: number) {
  activatingId.value = profileId
  try {
    result.value = await personalityApi.activate(profileId)
    answers.value = {}
    started.value = true
    fingerprintAnimationRevision.value += 1
    historyItems.value = await personalityApi.history()
    persist()
    toast.add({ title: '已切换当前人格测评', color: 'success' })
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '切换失败', color: 'error' })
  } finally {
    activatingId.value = undefined
  }
}

async function togglePersonalization(enabled: boolean) {
  if (!result.value?.profile_id || preferenceSaving.value) return
  preferenceSaving.value = true
  try {
    result.value = await personalityApi.setPersonalization(result.value.profile_id, enabled)
    persist()
    toast.add({ title: enabled ? '已允许用于匹配解释' : '已停用偏好个性化', color: 'success' })
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '设置保存失败', color: 'error' })
  } finally {
    preferenceSaving.value = false
  }
}

async function removeResult() {
  if (!result.value?.profile_id || deleting.value) return
  deleting.value = true
  try {
    const impact = await personalityApi.remove(result.value.profile_id)
    result.value = await personalityApi.latest()
    answers.value = {}
    current.value = 0
    started.value = Boolean(result.value)
    deleteOpen.value = false
    persist()
    toast.add({ title: `测评已删除，已清理 ${impact.scrubbed_match_runs || 0} 条匹配偏好快照`, color: 'success' })
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '删除失败', color: 'error' })
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  auth.hydrate()
  const cache = readPersonalityCache(cacheUserId.value)
  if (cache) {
    answers.value = cache.answers
    result.value = cache.result
    started.value = cache.started
    current.value = cache.currentQuestionIndex
  }
  try {
    const [remoteQuestions, remoteResult] = await Promise.all([
      personalityApi.questions(),
      personalityApi.latest().catch(() => undefined)
    ])
    questions.value = remoteQuestions
    const signature = questionSetSignature(questions.value)
    if (cache && !result.value && !canRestorePersonalityProgress(cache, signature)) {
      answers.value = {}
      current.value = 0
      started.value = false
      toast.add({ title: '题库已更新，旧答题进度已安全重置', color: 'info' })
    }
    questionSignature.value = signature
    current.value = Math.min(current.value, Math.max(0, questions.value.length - 1))
    if (remoteResult) {
      const cachedProfileId = cache?.result?.profile_id
      result.value = remoteResult
      started.value = true
      if (!cachedProfileId || cachedProfileId !== remoteResult.profile_id) answers.value = {}
      persist()
    }
  } finally {
    loading.value = false
  }
})

watch([answers, current, started], persist, { deep: true })
</script>

<template>
  <div class="cockpit-page personality-page">
    <PersonalityHistoryModal
      v-model:open="historyOpen"
      :items="historyItems"
      :loading="historyLoading"
      :activating-id="activatingId"
      @activate="activateHistory"
    />
    <UModal v-model:open="deleteOpen" title="删除本次人格测评" description="原始答案和本次测评将被删除，直接关联的匹配偏好快照会同步清理。">
      <template #footer><div class="flex w-full justify-end gap-2"><UButton color="neutral" variant="ghost" @click="closeDelete">取消</UButton><UButton color="error" icon="i-lucide-trash-2" :loading="deleting" @click="removeResult">确认删除</UButton></div></template>
    </UModal>
    <CockpitPageHeader eyebrow="Personality Lens / Preference" title="职业性格测试" description="用一组没有标准答案的二选一问题，辨认更自然的决策方式、协作偏好与职业环境倾向。" icon="i-lucide-brain" mark="06" edition-label="偏好档案" />
    <div class="personality-workspace page-stack mx-auto w-full max-w-4xl">

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
      <PersonalityHero :mbti="result.mbti_type" :name="result.complete_analysis?.name" :summary="result.complete_analysis?.summary || result.personality_analysis">
        <template #visual>
          <PersonalityFingerprint :result="result" :answers="answers" :animation-revision="fingerprintAnimationRevision" />
        </template>
      </PersonalityHero>
      <UCard>
        <div class="grid gap-4 md:grid-cols-[1fr_auto] md:items-center">
          <div>
            <div class="flex flex-wrap items-center gap-2"><h2 class="font-semibold">工作偏好使用方式</h2><UBadge :label="result.personalization_enabled ? '已允许个性化' : '默认关闭'" :color="result.personalization_enabled ? 'primary' : 'neutral'" variant="soft" /></div>
            <p class="mt-2 text-sm leading-6 muted">开启后，系统可在匹配中附加偏好解释；当前阶段不会改变能力分、岗位筛选或排序。</p>
          </div>
          <USwitch :model-value="Boolean(result.personalization_enabled)" :disabled="preferenceSaving || result.status === 'legacy'" label="允许用于个性化" @update:model-value="togglePersonalization(Boolean($event))" />
        </div>
      </UCard>
      <UAlert v-if="result.status === 'legacy'" color="warning" variant="soft" icon="i-lucide-history" title="这是历史类型摘要" description="该记录没有连续四维测量值，因此不会生成数值型偏好解释；重新测评后可获得完整工作偏好画像。" />
      <PersonalityDimensions :items="result.dimension_analysis || []" />
      <div class="panel-grid two">
        <PersonalityStrengths :items="result.complete_analysis?.core_strengths || []" />
        <PersonalityCareerTendency :items="result.complete_analysis?.career_tendencies || []" />
        <PersonalityWorkplaceRelations :items="result.complete_analysis?.workplace_relationships || []" />
        <PersonalityGrowthAdvice :items="result.complete_analysis?.development_areas || []" />
      </div>
      <PersonalityStressResponse :content="result.complete_analysis?.stress_response" />
      <PersonalityRecommendedJobs :jobs="result.recommended_jobs || []" :advice="result.job_recommendations?.career_advice" />
      <UCard>
        <template #header><h2 class="font-semibold">把偏好带回职业主线</h2></template>
        <p class="mb-4 text-sm muted">推荐岗位只是探索线索；进入真实岗位库后，仍会继续比较能力证据和岗位要求。</p>
        <div class="flex flex-wrap gap-3">
          <UButton :to="{ path: '/jobs', query: explorationJob ? { q: explorationJob, from: 'personality' } : { from: 'personality' } }" icon="i-lucide-search">带着偏好探索岗位</UButton>
          <UButton to="/match?preference=explain" color="neutral" variant="outline" icon="i-lucide-git-compare">进入人岗匹配</UButton>
          <UButton to="/profile" color="neutral" variant="outline" icon="i-lucide-radar">查看综合画像</UButton>
        </div>
      </UCard>
      <div class="flex flex-wrap gap-3">
        <UButton variant="outline" icon="i-lucide-history" @click="openHistory">历史测评</UButton>
        <UButton variant="outline" icon="i-lucide-rotate-ccw" @click="restart">重新测试</UButton>
        <UButton color="error" variant="ghost" icon="i-lucide-trash-2" @click="openDelete">删除本次测评</UButton>
      </div>
      </template>
    </div>
  </div>
</template>
