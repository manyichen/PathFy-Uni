import type { CapabilityScores } from '~/types/capability'
import type { ProfileDetail, ProfileMaterial, ResumeOption } from '~/types/profile'
import { useProfileApi } from '~/composables/api/useProfileApi'
import { clearProfileCache, readProfileCache, writeProfileCache } from '~/utils/cache/profile-cache'
import { PROFILE_FILE_MAX_COUNT, profileItems, validateProfileFile } from '~/utils/profile-display'

export function useProfileWorkspace() {
  const profileApi = useProfileApi()
  const auth = useAuth()
  const toast = useToast()
  const name = ref('')
  const major = ref('')
  const text = ref('')
  const files = ref<File[]>([])
  const loading = ref(false)
  const restoringId = ref<number>()
  const result = ref<ProfileDetail>()
  const history = ref<ResumeOption[]>([])
  const historyOpen = ref(false)
  const historyLoading = ref(false)
  const historyError = ref('')
  const submitError = ref('')
  const activeResumeId = ref<number>()
  const cacheUserId = computed(() => auth.user.value?.id || 'guest')
  const scores = computed<Partial<CapabilityScores>>(() => result.value?.scores || {})
  const analysis = computed(() => result.value?.detailed_analysis || {})
  const materials = computed<ProfileMaterial[]>(() => profileItems(analysis.value.material_summary || result.value?.materials) as ProfileMaterial[])

  function choose(event: Event) {
    const input = event.target as HTMLInputElement
    const selected = Array.from(input.files || [])
    const checked = selected.map(file => ({ file, error: validateProfileFile(file) }))
    const valid = checked.filter(item => !item.error).map(item => item.file)
    const errors = checked.map(item => item.error).filter(Boolean)
    const available = Math.max(0, PROFILE_FILE_MAX_COUNT - files.value.length)
    if (errors.length) toast.add({ title: '部分材料未加入', description: errors.slice(0, 3).join('；'), color: 'warning' })
    if (valid.length > available) toast.add({ title: `最多上传 ${PROFILE_FILE_MAX_COUNT} 份材料`, color: 'warning' })
    files.value = [...files.value, ...valid.slice(0, available)]
    input.value = ''
  }

  function removeFile(index: number) {
    files.value.splice(index, 1)
  }

  function persist(payload = result.value) {
    if (!payload) return
    writeProfileCache(cacheUserId.value, { resumeId: activeResumeId.value || payload.resume_id || payload.id, portrait: payload })
  }

  function applyPortrait(row: ProfileDetail, id = row.resume_id || row.id) {
    result.value = row
    activeResumeId.value = id
    name.value = row.name || name.value
    major.value = row.major || major.value
    persist(row)
  }

  async function loadPortrait(id: number, quiet = false) {
    restoringId.value = id
    historyError.value = ''
    try {
      applyPortrait(await profileApi.getPortrait(id), id)
      historyOpen.value = false
      if (!quiet) toast.add({ title: `已恢复画像 #${id}`, color: 'success' })
    } catch (error) {
      historyError.value = error instanceof Error ? error.message : '画像加载失败，请重试'
      if (!quiet) toast.add({ title: historyError.value, color: 'error' })
    } finally {
      restoringId.value = undefined
    }
  }

  async function loadHistory() {
    historyOpen.value = true
    historyLoading.value = true
    historyError.value = ''
    try {
      history.value = await profileApi.listResumes()
    } catch (error) {
      historyError.value = error instanceof Error ? error.message : '历史画像加载失败'
    } finally {
      historyLoading.value = false
    }
  }

  async function submit() {
    submitError.value = ''
    if (!name.value.trim() || !major.value.trim() || (!files.value.length && !text.value.trim())) {
      submitError.value = '请填写姓名、专业并提供至少一份材料'
      return
    }
    loading.value = true
    try {
      const body = new FormData()
      body.append('name', name.value.trim())
      body.append('major', major.value.trim())
      if (text.value.trim()) body.append('profile_text', text.value.trim())
      for (const file of files.value) body.append('materials', file)
      const portrait = await profileApi.uploadPortrait(body)
      applyPortrait(portrait)
      files.value = []
      history.value = await profileApi.listResumes().catch(() => history.value)
      toast.add({ title: '能力画像生成成功', color: 'success' })
    } catch (error) {
      submitError.value = error instanceof Error ? error.message : '材料分析失败，请检查材料后重试'
    } finally {
      loading.value = false
    }
  }

  onMounted(async () => {
    auth.hydrate()
    const cached = readProfileCache(cacheUserId.value)
    if (cached) applyPortrait(cached.portrait, cached.resumeId)
    try {
      history.value = await profileApi.listResumes()
      const latest = history.value[0]
      if (latest?.id) await loadPortrait(latest.id, true)
    } catch {
      if (!cached) clearProfileCache(cacheUserId.value)
    }
  })

  return {
    name, major, text, files, loading, restoringId, result, history, historyOpen,
    historyLoading, historyError, submitError, activeResumeId, scores, analysis,
    materials, choose, removeFile, loadPortrait, loadHistory, submit
  }
}
