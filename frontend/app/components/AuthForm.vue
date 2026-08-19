<script setup lang="ts">
import { z } from 'zod'
import type { AuthUser, OkEnvelope } from '~/types/api'

const props = defineProps<{ mode: 'login' | 'register' }>()
const api = useApi()
const auth = useAuth()
const journey = useAuthJourney()
const route = useRoute()
const toast = useToast()
const loading = ref(false)
const showConnectionStatus = ref(false)
const state = reactive({ account: '', username: '', email: '', password: '' })
let statusTimer: ReturnType<typeof setTimeout> | undefined

const schema = props.mode === 'login'
  ? z.object({ account: z.string().min(1, '请输入账号'), password: z.string().min(6, '密码至少 6 位') })
  : z.object({ username: z.string().min(2, '用户名至少 2 位'), email: z.email('邮箱格式不正确'), password: z.string().min(6, '密码至少 6 位') })

const identityStarted = computed(() => props.mode === 'login'
  ? state.account.trim().length > 0
  : state.username.trim().length > 0 || state.email.trim().length > 0)
const passwordReady = computed(() => state.password.length >= 6)
const title = computed(() => props.mode === 'login' ? '欢迎回来' : '创建你的路径')
const description = computed(() => props.mode === 'login'
  ? '登录后继续画像、匹配与行动计划。'
  : '用一份账户保存你的画像、目标与每次复盘。')

watch([identityStarted, passwordReady], ([identity, password]) => {
  journey.setInputProgress(identity, password)
}, { immediate: true })

onMounted(() => journey.setMode(props.mode))

onBeforeUnmount(() => {
  if (statusTimer) clearTimeout(statusTimer)
})

async function submit() {
  const payload = props.mode === 'login'
    ? { account: state.account, password: state.password }
    : { username: state.username, email: state.email, password: state.password }
  const parsed = schema.safeParse(payload)
  if (!parsed.success) {
    toast.add({ title: parsed.error.issues[0]?.message || '请检查输入', color: 'error' })
    return
  }

  loading.value = true
  showConnectionStatus.value = false
  journey.startSubmitting()
  statusTimer = setTimeout(() => { showConnectionStatus.value = true }, 400)

  try {
    const result = await api.request<OkEnvelope<{ token: string; user: AuthUser }>>(`/api/auth/${props.mode}`, {
      method: 'POST',
      body: payload
    })
    if (!result.ok || !result.data) throw new Error(result.message || '操作失败')

    auth.save(result.data.token, result.data.user)
    toast.add({ title: props.mode === 'login' ? '登录成功' : '注册成功', color: 'success' })
    const redirect = typeof route.query.redirect === 'string'
      ? route.query.redirect
      : (result.data.user.is_admin ? '/graph-admin' : '/')
    await journey.playSuccess({ destination: redirect })
  } catch (error) {
    journey.playError()
    toast.add({ title: error instanceof Error ? error.message : '操作失败', color: 'error' })
  } finally {
    if (statusTimer) clearTimeout(statusTimer)
    showConnectionStatus.value = false
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page-shell" :class="{ 'is-journey-transitioning': journey.isTransitioning.value }">
    <ClientOnly>
      <AuthJourneyTransition />
    </ClientOnly>
    <AuthJourneyStage :mode="mode" />

    <section class="auth-form-zone" :aria-busy="loading">
      <div class="auth-form-kicker" aria-hidden="true">
        <span>{{ mode === 'login' ? 'RETURN' : 'START' }}</span>
        <i />
        <span>PATHFY</span>
      </div>

      <div class="auth-card">
        <header class="auth-card-header">
          <div class="auth-card-mark" aria-hidden="true">
            <UIcon :name="mode === 'login' ? 'i-lucide-route' : 'i-lucide-sparkles'" />
          </div>
          <div>
            <p class="auth-card-overline">{{ mode === 'login' ? 'WELCOME BACK' : 'CREATE ACCOUNT' }}</p>
            <h1>{{ title }}</h1>
            <p>{{ description }}</p>
          </div>
        </header>

        <UForm :schema="schema" :state="state" class="auth-form" @submit="submit">
          <UFormField v-if="mode === 'login'" label="账号" name="account">
            <UInput
              v-model="state.account"
              class="w-full"
              size="xl"
              icon="i-lucide-user-round"
              autocomplete="username"
              autocapitalize="none"
              :disabled="loading"
              placeholder="用户名或邮箱"
            />
          </UFormField>

          <template v-else>
            <UFormField label="用户名" name="username">
              <UInput
                v-model="state.username"
                class="w-full"
                size="xl"
                icon="i-lucide-user-round"
                autocomplete="username"
                :disabled="loading"
                placeholder="如何称呼你"
              />
            </UFormField>
            <UFormField label="邮箱" name="email">
              <UInput
                v-model="state.email"
                type="email"
                class="w-full"
                size="xl"
                icon="i-lucide-mail"
                autocomplete="email"
                autocapitalize="none"
                :disabled="loading"
                placeholder="name@example.com"
              />
            </UFormField>
          </template>

          <UFormField label="密码" name="password">
            <UInput
              v-model="state.password"
              type="password"
              class="w-full"
              size="xl"
              icon="i-lucide-lock-keyhole"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              :disabled="loading"
              placeholder="至少 6 位"
            />
          </UFormField>

          <div class="auth-submit-block">
            <UButton
              type="submit"
              block
              size="xl"
              trailing-icon="i-lucide-arrow-right"
              :disabled="loading"
            >
              {{ loading ? '正在连接路径…' : (mode === 'login' ? '登录' : '注册') }}
            </UButton>
            <Transition name="auth-status">
              <p v-if="showConnectionStatus" class="auth-connection-status" role="status">
                <span />正在连接你的路径，请稍候
              </p>
            </Transition>
          </div>
        </UForm>

        <footer class="auth-card-footer">
          <p>
            {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
            <NuxtLink :to="mode === 'login' ? '/register' : '/login'">
              {{ mode === 'login' ? '从这里开始' : '返回登录' }}
            </NuxtLink>
          </p>
          <span><UIcon name="i-lucide-shield-check" />你的规划数据仅用于个人职业工作台</span>
        </footer>
      </div>
    </section>
  </div>
</template>
