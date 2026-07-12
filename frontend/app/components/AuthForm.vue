<script setup lang="ts">
import { z } from 'zod'
import type { AuthUser, OkEnvelope } from '~/types/api'

const props = defineProps<{ mode: 'login' | 'register' }>()
const api = useApi()
const auth = useAuth()
const route = useRoute()
const toast = useToast()
const loading = ref(false)
const state = reactive({ account: '', username: '', email: '', password: '' })
const schema = props.mode === 'login'
  ? z.object({ account: z.string().min(1, '请输入账号'), password: z.string().min(6, '密码至少 6 位') })
  : z.object({ username: z.string().min(2, '用户名至少 2 位'), email: z.email('邮箱格式不正确'), password: z.string().min(6, '密码至少 6 位') })

async function submit() {
  const payload = props.mode === 'login'
    ? { account: state.account, password: state.password }
    : { username: state.username, email: state.email, password: state.password }
  const parsed = schema.safeParse(payload)
  if (!parsed.success) { toast.add({ title: parsed.error.issues[0]?.message || '请检查输入', color: 'error' }); return }
  loading.value = true
  try {
    const result = await api.request<OkEnvelope<{ token: string; user: AuthUser }>>(`/api/auth/${props.mode}`, { method: 'POST', body: payload })
    if (!result.ok || !result.data) throw new Error(result.message || '操作失败')
    auth.save(result.data.token, result.data.user)
    toast.add({ title: props.mode === 'login' ? '登录成功' : '注册成功', color: 'success' })
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : (result.data.user.is_admin ? '/graph-admin' : '/')
    await navigateTo(redirect)
  } catch (error) {
    toast.add({ title: error instanceof Error ? error.message : '操作失败', color: 'error' })
  } finally { loading.value = false }
}
</script>

<template>
  <UCard class="mx-auto max-w-md">
    <template #header>
      <div class="page-heading">
        <h1>{{ mode === 'login' ? '登录' : '注册' }}</h1>
        <p class="muted">{{ mode === 'login' ? '继续你的职业规划旅程' : '创建 PathFy 账户' }}</p>
      </div>
    </template>
    <UForm :state="state" class="grid gap-4" @submit="submit">
      <UFormField v-if="mode === 'login'" label="账号" name="account"><UInput v-model="state.account" class="w-full" /></UFormField>
      <template v-else>
        <UFormField label="用户名" name="username"><UInput v-model="state.username" class="w-full" /></UFormField>
        <UFormField label="邮箱" name="email"><UInput v-model="state.email" type="email" class="w-full" /></UFormField>
      </template>
      <UFormField label="密码" name="password"><UInput v-model="state.password" type="password" class="w-full" /></UFormField>
      <UButton type="submit" block :loading="loading">{{ mode === 'login' ? '登录' : '注册' }}</UButton>
    </UForm>
    <template #footer>
      <p class="text-center text-sm muted">
        {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
        <NuxtLink :to="mode === 'login' ? '/register' : '/login'" class="text-primary font-medium">{{ mode === 'login' ? '立即注册' : '返回登录' }}</NuxtLink>
      </p>
    </template>
  </UCard>
</template>
