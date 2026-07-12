<script setup lang="ts">
definePageMeta({ middleware: 'auth' }); useSeoMeta({ title: '个人中心' })
const auth = useAuth(); const api = useApi(); const loading = ref(true)
onMounted(async () => { try { const data = await api.ok<{ user: any }>('/api/auth/me'); auth.user.value = data.user } finally { loading.value = false } })
</script>
<template><div class="page-stack"><div class="page-heading"><h1>个人中心</h1><p class="muted">账户信息与登录状态</p></div><UCard><USkeleton v-if="loading" class="h-24" /><div v-else class="grid gap-3"><div><span class="muted">用户名：</span>{{ auth.user.value?.username }}</div><div><span class="muted">邮箱：</span>{{ auth.user.value?.email }}</div><UBadge :label="auth.isAdmin.value ? '管理员' : '普通用户'" class="w-fit" /></div></UCard></div></template>
