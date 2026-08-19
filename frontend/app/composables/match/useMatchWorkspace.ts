import type { JobCard } from '~/types/job'
import type { MatchGoal, MatchHistoryItem, MatchPreviewResult, PreferenceMode } from '~/types/match'
import type { PersonalityResult } from '~/types/personality'
import type { ResumeOption } from '~/types/profile'
import { useMatchApi } from '~/composables/api/useMatchApi'
import { useProfileApi } from '~/composables/api/useProfileApi'
import { usePersonalityApi } from '~/composables/api/usePersonalityApi'
import { isAbortError } from '~/composables/useApi'
import { readMatchCache, writeMatchCache } from '~/utils/cache/match-cache'

export function useMatchWorkspace() {
  const matchApi = useMatchApi()
  const profileApi = useProfileApi()
  const personalityApi = usePersonalityApi()
  const settingsApi = useSettingsApi()
  const auth = useAuth()
  const toast = useToast()
  const route = useRoute()
  const resumes = ref<ResumeOption[]>([])
  const resumeId = ref<number>()
  const q = ref('')
  const locationQ = ref('')
  const goal = ref<MatchGoal>('fit')
  const refine = ref(false)
  const preferenceMode = ref<PreferenceMode>('off')
  const personalityProfile = ref<PersonalityResult>()
  const loading = ref(false)
  const refineLoading = ref(false)
  const runError = ref('')
  const historyLoading = ref(false)
  const result = ref<MatchPreviewResult>()
  const selectedJob = ref<JobCard>()
  const detailJobId = ref<string | null>(null)
  const historyOpen = ref(false)
  const history = ref<MatchHistoryItem[]>([])
  const restoredMessage = ref('')
  const cacheUserId = computed(() => auth.user.value?.id || 'guest')
  const jobs = computed(() => result.value?.jobs || [])
  const top5 = computed(() => result.value?.llm?.ok ? result.value.llm.top5 : [])
  const studentScores = computed(() => result.value?.student.scores || {})
  const selectedPersonalityProfileId = computed(() => result.value?.preference_context?.personality_profile_id || personalityProfile.value?.profile_id)
  let runSequence = 0
  let activeController: AbortController | undefined

  function persist() {
    if (!result.value) return
    writeMatchCache(cacheUserId.value, {
      result: result.value,
      resumeId: resumeId.value,
      filters: { q: q.value, locationQ: locationQ.value, goal: goal.value, refine: refine.value, preferenceMode: preferenceMode.value }
    })
  }

  function applyResult(data: MatchPreviewResult, restoredResumeId?: number, preserveSelection = false) {
    runError.value = ''
    const selectedId = preserveSelection ? selectedJob.value?.id : undefined
    result.value = data
    selectedJob.value = selectedId
      ? data.jobs.find(item => item.job.id === selectedId)?.job || selectedJob.value
      : undefined
    if (data.filters) {
      q.value = data.filters.q || ''
      locationQ.value = data.filters.location_q || ''
      goal.value = data.filters.match_goal === 'stretch' ? 'stretch' : 'fit'
    }
    if (data.preference_context?.mode) preferenceMode.value = data.preference_context.mode
    if (restoredResumeId && resumes.value.some(item => item.id === restoredResumeId)) resumeId.value = restoredResumeId
    persist()
  }

  function refinementError(error: unknown) {
    if (isAbortError(error)) return 'AI 精排响应超过 90 秒，已保留完整粗排结果。你可以稍后单独重试精排。'
    const message = error instanceof Error ? error.message : 'AI 精排服务暂时不可用'
    return `${message}；已保留完整粗排结果，可稍后重试精排。`
  }

  function normalizeRefinementResult(data: MatchPreviewResult): MatchPreviewResult {
    if (!data.llm) {
      return {
        ...data,
        llm: { ok: false, error: '当前账号隐私偏好或平台设置未允许 AI 精排，已保留完整粗排结果。', top5: [] }
      }
    }
    if (data.llm.ok) return data
    if (data.llm.error && data.llm.error_code) return data
    const raw = data.llm.error || ''
    const error = raw.includes('DEEPSEEK_API_KEY')
      ? 'AI 精排服务尚未配置，已保留完整粗排结果。'
      : raw.includes('APITimeoutError') || raw.toLowerCase().includes('timed out')
        ? 'AI 精排响应超过 90 秒，可能是服务繁忙；已保留完整粗排结果，可点击重试。'
      : raw.includes('json_decode_error') || raw.includes('missing_top5') || raw.includes('parse_failed')
        ? 'AI 返回内容格式异常，已保留完整粗排结果，可点击重试。'
        : raw.includes('deepseek_http_error')
          ? 'AI 精排服务连接失败，已保留完整粗排结果，可点击重试。'
          : raw || 'AI 精排暂时不可用，已保留完整粗排结果。'
    return { ...data, llm: { ...data.llm, error } }
  }

  async function requestRefinement(sequence: number, controller: AbortController) {
    if (!resumeId.value || !result.value) return
    refineLoading.value = true
    try {
      const refined = await matchApi.preview({
        resume_id: resumeId.value,
        q: q.value.trim(),
        location_q: locationQ.value.trim(),
        match_goal: goal.value,
        refine_with_llm: true,
        persist_snapshot: true,
        preference_mode: preferenceMode.value,
        personality_profile_id: preferenceMode.value !== 'off' ? selectedPersonalityProfileId.value : undefined
      }, { signal: controller.signal, timeout: 110_000 })
      if (sequence !== runSequence) return
      applyResult(normalizeRefinementResult(refined), undefined, true)
    } catch (error) {
      if (sequence !== runSequence) return
      result.value = {
        ...result.value,
        llm: { ok: false, error: refinementError(error), top5: [] }
      }
      persist()
    } finally {
      if (sequence === runSequence) refineLoading.value = false
    }
  }

  async function run() {
    if (!resumeId.value) {
      runError.value = '请先选择一份能力画像，再开始匹配。'
      toast.add({ title: '请选择能力画像', color: 'warning' })
      return
    }
    activeController?.abort()
    const sequence = ++runSequence
    const controller = new AbortController()
    activeController = controller
    const shouldRefine = refine.value
    loading.value = true
    refineLoading.value = false
    runError.value = ''
    restoredMessage.value = ''
    try {
      applyResult(await matchApi.preview({
        resume_id: resumeId.value,
        q: q.value.trim(),
        location_q: locationQ.value.trim(),
        match_goal: goal.value,
        refine_with_llm: false,
        persist_snapshot: !shouldRefine,
        preference_mode: preferenceMode.value,
        personality_profile_id: preferenceMode.value !== 'off' ? personalityProfile.value?.profile_id : undefined
      }, { signal: controller.signal, timeout: 30_000 }))
    } catch (error) {
      if (sequence !== runSequence) return
      runError.value = error instanceof Error ? error.message : '匹配失败，请稍后重试'
      toast.add({ title: runError.value, color: 'error' })
    } finally {
      if (sequence === runSequence) loading.value = false
    }
    if (sequence === runSequence && shouldRefine && result.value && !result.value.llm?.ok && !runError.value) {
      await requestRefinement(sequence, controller)
    }
  }

  async function retryRefine() {
    if (!resumeId.value || !result.value || refineLoading.value) return
    activeController?.abort()
    const sequence = ++runSequence
    const controller = new AbortController()
    activeController = controller
    await requestRefinement(sequence, controller)
  }

  async function openHistory() {
    historyOpen.value = true
    historyLoading.value = true
    try {
      history.value = await matchApi.history()
    } catch (error) {
      toast.add({ title: error instanceof Error ? error.message : '匹配历史加载失败', color: 'error' })
    } finally {
      historyLoading.value = false
    }
  }

  async function restore(item: MatchHistoryItem) {
    historyLoading.value = true
    try {
      const detail = await matchApi.historyDetail(item.run_id)
      refine.value = Boolean(item.refine_with_llm)
      applyResult(detail, item.resume_id || detail.resume_id)
      historyOpen.value = false
      const unavailable = item.resume_id && !resumes.value.some(row => row.id === item.resume_id)
      restoredMessage.value = unavailable ? '历史结果已恢复；原能力画像已不可用，请重新选择画像后再匹配。' : '历史匹配条件与结果已完整恢复。'
    } catch (error) {
      toast.add({ title: error instanceof Error ? error.message : '匹配记录恢复失败', color: 'error' })
    } finally {
      historyLoading.value = false
    }
  }

  function select(job: JobCard) {
    selectedJob.value = job
  }

  function openDetail(job: JobCard) {
    selectedJob.value = job
    detailJobId.value = job.id
  }

  onMounted(async () => {
    auth.hydrate()
    const cache = readMatchCache(cacheUserId.value)
    if (cache) {
      result.value = cache.result
      resumeId.value = cache.resumeId
      q.value = cache.filters.q
      locationQ.value = cache.filters.locationQ
      goal.value = cache.filters.goal
      refine.value = cache.filters.refine
      preferenceMode.value = cache.filters.preferenceMode
    }
    try {
      resumes.value = await profileApi.listResumes()
    } catch (error) {
      toast.add({ title: error instanceof Error ? error.message : '画像列表加载失败', color: 'error' })
    }
    try {
      personalityProfile.value = await personalityApi.latest()
      const preferenceAvailable = personalityProfile.value?.status === 'measured' && personalityProfile.value.personalization_enabled
      if (!cache && preferenceAvailable) preferenceMode.value = 'explain'
      if (route.query.preference === 'explain' && preferenceAvailable) preferenceMode.value = 'explain'
      // Turning personalization off must affect every future run, including a
      // workspace restored from an older cache that had explanation mode on.
      if (!preferenceAvailable) preferenceMode.value = 'off'
    } catch {
      personalityProfile.value = undefined
      if (!cache) preferenceMode.value = 'off'
    }
    if (cache) return
    try {
      const data = await settingsApi.preferences()
      goal.value = data.preferences?.default_match_goal === 'stretch' ? 'stretch' : 'fit'
      refine.value = Boolean(data.preferences?.default_refine_with_llm)
    } catch {
      // 匹配可继续使用安全默认值。
    }
  })

  onBeforeUnmount(() => activeController?.abort())

  return {
    resumes, resumeId, q, locationQ, goal, refine, preferenceMode, personalityProfile, loading, refineLoading, runError, historyLoading, result,
    selectedJob, detailJobId, historyOpen, history, restoredMessage, jobs, top5,
    studentScores, run, retryRefine, openHistory, restore, select, openDetail
  }
}
