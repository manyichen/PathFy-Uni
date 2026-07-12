<script setup lang="ts">
const auth = useAuth()
const colorMode = useColorMode()
const route = useRoute()
const mobileOpen = ref(false)
const hue = ref('192')
const hueOptions = [
  { label: '青', value: '192' }, { label: '蓝', value: '220' },
  { label: '紫', value: '270' }, { label: '绿', value: '150' }
]

const userNav = [
  { label: '首页', to: '/', icon: 'i-lucide-house' },
  { label: '岗位探索', to: '/jobs', icon: 'i-lucide-briefcase-business' },
  { label: '能力画像', to: '/profile', icon: 'i-lucide-chart-radar' },
  { label: '性格测试', to: '/personality', icon: 'i-lucide-brain' },
  { label: '人岗匹配', to: '/match', icon: 'i-lucide-git-compare' },
  { label: '职业图谱', to: '/graph', icon: 'i-lucide-network' },
  { label: '生涯报告', to: '/report', icon: 'i-lucide-file-chart-column' }
]
const nav = computed(() => auth.isAdmin.value
  ? [{ label: '图谱管理', to: '/graph-admin', icon: 'i-lucide-database' }]
  : userNav)

function logout() {
  auth.clear()
  navigateTo('/')
}

function toggleTheme() {
  colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark'
  if (import.meta.client) localStorage.setItem('theme', colorMode.preference)
}

function applyHue(value: string | undefined) {
  if (!import.meta.client) return
  if (!value) return
  localStorage.setItem('hue', value)
  document.documentElement.style.setProperty('--pathfy-hue', value)
}

onMounted(() => {
  auth.hydrate()
  const theme = localStorage.getItem('theme')
  if (theme === 'dark' || theme === 'light') colorMode.preference = theme
  hue.value = localStorage.getItem('hue') || '192'
  applyHue(hue.value)
})
</script>

<template>
  <UHeader title="PathFy" :ui="{ root: 'sticky top-0 z-50' }">
    <template #title>
      <NuxtLink to="/" class="flex items-center gap-2 font-bold">
        <img src="/assets/home/fu.svg" alt="" class="size-7">
        <span>PathFy</span>
      </NuxtLink>
    </template>

    <UNavigationMenu :items="nav" class="hidden lg:flex" />

    <template #right>
      <USelect v-model="hue" :items="hueOptions" class="hidden w-20 sm:block" aria-label="主题色" @update:model-value="applyHue" />
      <UButton icon="i-lucide-sun-moon" color="neutral" variant="ghost" aria-label="切换主题" @click="toggleTheme" />
      <UButton v-if="auth.isAuthenticated.value" to="/account" color="neutral" variant="ghost">
        {{ auth.user.value?.username || '个人中心' }}
      </UButton>
      <UButton v-if="auth.isAuthenticated.value" color="neutral" variant="soft" @click="logout">退出</UButton>
      <UButton v-else to="/login">登录</UButton>
      <UButton class="lg:hidden" icon="i-lucide-menu" color="neutral" variant="ghost" @click="() => { mobileOpen = true }" />
    </template>
  </UHeader>

  <USlideover v-model:open="mobileOpen" title="导航">
    <template #body>
      <div class="grid gap-2">
        <UButton
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          :icon="item.icon"
          :variant="route.path === item.to ? 'soft' : 'ghost'"
          color="neutral"
          block
          @click="() => { mobileOpen = false }"
        >{{ item.label }}</UButton>
      </div>
    </template>
  </USlideover>
</template>
