<script setup lang="ts">
import type { HuePreference, ThemePreference } from '~/composables/useAppearancePreferences'
import { normalizeHuePreference, normalizeThemePreference } from '~/composables/useAppearancePreferences'

definePageMeta({ middleware: 'auth' })
useSeoMeta({ title: '个人中心' })

type MatchGoal = 'fit' | 'stretch'

type PreferenceForm = {
  theme: ThemePreference
  hue: HuePreference
  allow_external_llm: boolean
  default_match_goal: MatchGoal
  default_refine_with_llm: boolean
  match_result_count: number
  report_copywriter: boolean
  report_public_info: boolean
  report_auto_replan: boolean
  report_graph_recommendations: boolean
  report_recommendation_llm: boolean
  learning_resource_count: number
  competition_count: number
}

type PreferencesPayload = {
  stored?: boolean
  preferences?: Partial<PreferenceForm>
  limits?: Partial<Record<'match_result_count' | 'learning_resource_count' | 'competition_count', number>>
}

const defaultForm: PreferenceForm = {
  theme: 'system',
  hue: '192',
  allow_external_llm: true,
  default_match_goal: 'fit',
  default_refine_with_llm: false,
  match_result_count: 30,
  report_copywriter: true,
  report_public_info: true,
  report_auto_replan: true,
  report_graph_recommendations: true,
  report_recommendation_llm: true,
  learning_resource_count: 5,
  competition_count: 3
}

const auth = useAuth()
const api = useApi()
const settings = useSettingsApi()
const toast = useToast()
const appearance = useAppearancePreferences()

const loading = ref(true)
const saving = ref(false)
const data = ref<PreferencesPayload>()
const form = reactive<PreferenceForm>({ ...defaultForm })

const hueNumber = computed({
  get: () => Number(form.hue),
  set: value => chooseHue(String(value))
})

const goalItems = [
  { label: '稳妥匹配', value: 'fit' },
  { label: '冲刺发展', value: 'stretch' }
]

const limits = computed(() => ({
  match_result_count: data.value?.limits?.match_result_count ?? 100,
  learning_resource_count: data.value?.limits?.learning_resource_count ?? 20,
  competition_count: data.value?.limits?.competition_count ?? 10
}))

function normalizeGoal(value: unknown): MatchGoal {
  return value === 'stretch' ? 'stretch' : 'fit'
}

function normalizeNumber(value: unknown, fallback: number) {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function normalizePreferences(preferences: Partial<PreferenceForm> = {}): PreferenceForm {
  return {
    ...defaultForm,
    ...preferences,
    theme: normalizeThemePreference(preferences.theme),
    hue: normalizeHuePreference(preferences.hue),
    default_match_goal: normalizeGoal(preferences.default_match_goal),
    allow_external_llm: Boolean(preferences.allow_external_llm ?? defaultForm.allow_external_llm),
    default_refine_with_llm: Boolean(preferences.default_refine_with_llm ?? defaultForm.default_refine_with_llm),
    report_copywriter: Boolean(preferences.report_copywriter ?? defaultForm.report_copywriter),
    report_public_info: Boolean(preferences.report_public_info ?? defaultForm.report_public_info),
    report_auto_replan: Boolean(preferences.report_auto_replan ?? defaultForm.report_auto_replan),
    report_graph_recommendations: Boolean(preferences.report_graph_recommendations ?? defaultForm.report_graph_recommendations),
    report_recommendation_llm: Boolean(preferences.report_recommendation_llm ?? defaultForm.report_recommendation_llm),
    match_result_count: normalizeNumber(preferences.match_result_count, defaultForm.match_result_count),
    learning_resource_count: normalizeNumber(preferences.learning_resource_count, defaultForm.learning_resource_count),
    competition_count: normalizeNumber(preferences.competition_count, defaultForm.competition_count)
  }
}

function applyPreferenceForm(preferences: Partial<PreferenceForm> = {}) {
  Object.assign(form, normalizePreferences(preferences))
  appearance.applyPreferences(form)
}

function chooseHue(value: HuePreference) {
  form.hue = normalizeHuePreference(value)
  appearance.applyHue(form.hue)
}

async function load() {
  loading.value = true
  try {
    auth.hydrate()
    const [me, preferences] = await Promise.all([
      api.ok<{ user: any }>('/api/auth/me'),
      settings.preferences()
    ])

    auth.user.value = me.user
    let payload = preferences as PreferencesPayload

    if (!payload.stored) {
      const patch = appearance.localPatch()
      if (Object.keys(patch).length) payload = await settings.savePreferences(patch)
    }

    data.value = payload
    applyPreferenceForm(payload.preferences)
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : String(error), color: 'error' })
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const payload = await settings.savePreferences({ ...form }) as PreferencesPayload
    data.value = payload
    applyPreferenceForm(payload.preferences)
    toast.add({ title: '偏好已保存', color: 'success' })
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : String(error), color: 'error' })
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-stack">
    <div class="page-heading">
      <h1 class="flex items-center gap-2">
        <UIcon name="i-lucide-circle-user-round" class="text-primary" />
        个人中心
      </h1>
      <p class="muted">账户、界面、AI 与隐私偏好</p>
    </div>

    <USkeleton v-if="loading" class="h-96" />

    <template v-else>
      <UCard>
        <template #header>
          <h2 class="font-semibold">账户信息</h2>
        </template>

        <div class="grid gap-3 sm:grid-cols-3">
          <div><span class="muted">用户名：</span>{{ auth.user.value?.username }}</div>
          <div><span class="muted">邮箱：</span>{{ auth.user.value?.email }}</div>
          <UBadge :label="auth.isAdmin.value ? '管理员' : '普通用户'" class="w-fit" />
        </div>
      </UCard>

      <div class="grid gap-4 xl:grid-cols-2">
        <UCard>
          <template #header>
            <h2 class="font-semibold">外观</h2>
          </template>

          <div class="grid gap-5">
            <UFormField label="主题色">
              <div class="space-y-3">
                <div class="flex items-center justify-between text-sm">
                  <span class="muted">旧版色相滑条</span>
                  <strong>{{ form.hue }}°</strong>
                </div>
                <div class="account-slider-shell">
                  <input
                    v-model.number="hueNumber"
                    aria-label="账户主题色相"
                    type="range"
                    min="0"
                    max="360"
                    step="5"
                    class="account-slider"
                  >
                </div>
              </div>
            </UFormField>
          </div>
        </UCard>

        <UCard>
          <template #header>
            <h2 class="font-semibold">匹配偏好</h2>
          </template>

          <div class="grid gap-4 sm:grid-cols-2">
            <UFormField label="默认目标">
              <USelect v-model="form.default_match_goal" :items="goalItems" class="w-full" />
            </UFormField>
            <UFormField label="结果数量">
              <UInput v-model.number="form.match_result_count" type="number" min="1" :max="limits.match_result_count" />
            </UFormField>
            <USwitch v-model="form.default_refine_with_llm" label="默认启用 AI 精排" />
          </div>
        </UCard>
      </div>

      <UCard>
        <template #header>
          <div>
            <h2 class="font-semibold">AI 与隐私</h2>
            <p class="text-sm muted">关闭外部 AI 后，个人材料不会发送给第三方模型；依赖模型的功能会使用本地兜底或明确停用。</p>
          </div>
        </template>

        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <USwitch v-model="form.allow_external_llm" label="允许外部 AI 处理个人数据" />
          <USwitch v-model="form.report_copywriter" label="报告 AI 文案" />
          <USwitch v-model="form.report_public_info" label="公开信息增强" />
          <USwitch v-model="form.report_auto_replan" label="自动重新规划" />
          <USwitch v-model="form.report_graph_recommendations" label="图谱资源推荐" />
          <USwitch v-model="form.report_recommendation_llm" label="推荐 AI 精排" />
        </div>
      </UCard>

      <UCard>
        <template #header>
          <h2 class="font-semibold">推荐数量</h2>
        </template>

        <div class="grid gap-4 sm:grid-cols-2">
          <UFormField label="每个目标的学习资源">
            <UInput v-model.number="form.learning_resource_count" type="number" min="1" :max="limits.learning_resource_count" />
          </UFormField>
          <UFormField label="每个目标的竞赛">
            <UInput v-model.number="form.competition_count" type="number" min="0" :max="limits.competition_count" />
          </UFormField>
        </div>
      </UCard>

      <div class="flex justify-end">
        <UButton icon="i-lucide-save" :loading="saving" @click="save">保存偏好</UButton>
      </div>
    </template>
  </div>
</template>

<style scoped>
.account-slider-shell {
  border-radius: 0.55rem;
  background: oklch(0.8 0.1 0);
  padding: 0 0.25rem;
}

.account-slider {
  width: 100%;
  height: 1.5rem;
  appearance: none;
  border-radius: 0.35rem;
  background-image: var(--color-selection-bar);
}

.account-slider::-webkit-slider-thumb {
  width: 0.55rem;
  height: 1rem;
  appearance: none;
  border-radius: 0.18rem;
  background: rgb(255 255 255 / 0.78);
  box-shadow: 0 0 0 1px rgb(15 23 42 / 0.18);
}

.account-slider::-moz-range-thumb {
  width: 0.55rem;
  height: 1rem;
  border: 0;
  border-radius: 0.18rem;
  background: rgb(255 255 255 / 0.78);
  box-shadow: 0 0 0 1px rgb(15 23 42 / 0.18);
}

</style>
