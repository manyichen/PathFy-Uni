import type { AuthUser } from '~/types/api'
import type { PreferencesPayload, UserPreferences } from '~/types/settings'
import { useSettingsApi } from '~/composables/api/useSettingsApi'
import { defaultUserPreferences, normalizeUserPreferences, serializeUserPreferences, validateUserPreferences } from '~/utils/account-preferences'

export function useAccountPreferences() {
  const auth = useAuth()
  const api = useApi()
  const settings = useSettingsApi()
  const appearance = useAppearancePreferences()
  const toast = useToast()
  const loading = ref(true)
  const saving = ref(false)
  const saveError = ref('')
  const data = ref<PreferencesPayload>()
  const form = reactive<UserPreferences>({ ...defaultUserPreferences })
  const savedSnapshot = ref(serializeUserPreferences(form))
  const limits = computed(() => ({
    match_result_count: data.value?.limits?.match_result_count ?? 100,
    learning_resource_count: data.value?.limits?.learning_resource_count ?? 20,
    competition_count: data.value?.limits?.competition_count ?? 10
  }))
  const errors = computed(() => validateUserPreferences(form, limits.value))
  const valid = computed(() => Object.keys(errors.value).length === 0)
  const dirty = computed(() => serializeUserPreferences(form) !== savedSnapshot.value)

  function applyForm(value: Partial<UserPreferences> = {}, markSaved = false) {
    Object.assign(form, normalizeUserPreferences(value))
    appearance.applyPreferences(form)
    if (markSaved) savedSnapshot.value = serializeUserPreferences(form)
  }

  function rollback() {
    applyForm(JSON.parse(savedSnapshot.value) as UserPreferences)
  }

  async function load() {
    loading.value = true
    try {
      auth.hydrate()
      const [me, response] = await Promise.all([api.ok<{ user: AuthUser }>('/api/auth/me'), settings.preferences()])
      auth.user.value = me.user
      let payload = response
      if (!payload.stored) {
        const localAppearance = appearance.localPatch()
        if (Object.keys(localAppearance).length) payload = await settings.savePreferences(localAppearance)
      }
      data.value = payload
      applyForm(payload.preferences, true)
    } catch (error) {
      saveError.value = error instanceof Error ? error.message : '偏好加载失败'
      toast.add({ title: saveError.value, color: 'error' })
    } finally {
      loading.value = false
    }
  }

  async function save() {
    saveError.value = ''
    if (!valid.value) {
      saveError.value = '请先修正超出范围的推荐数量'
      return
    }
    saving.value = true
    try {
      const payload = await settings.savePreferences({ ...form })
      data.value = payload
      applyForm(payload.preferences, true)
      toast.add({ title: '偏好已保存', color: 'success' })
    } catch (error) {
      rollback()
      saveError.value = `${error instanceof Error ? error.message : '保存失败'}；修改已回滚到上次保存状态。`
    } finally {
      saving.value = false
    }
  }

  function beforeUnload(event: BeforeUnloadEvent) {
    if (!dirty.value) return
    event.preventDefault()
    event.returnValue = ''
  }

  watch(() => [form.theme, form.hue] as const, ([theme, hue]) => appearance.applyPreferences({ theme, hue }))
  onMounted(() => { window.addEventListener('beforeunload', beforeUnload); load() })
  onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))

  return { auth, loading, saving, saveError, data, form, limits, errors, valid, dirty, save, rollback }
}
