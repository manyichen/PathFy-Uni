<script setup lang="ts">
type HeaderNavItem = {
  label: string
  to: string
  icon: string
}

const auth = useAuth()
const route = useRoute()
const mobileOpen = ref(false)
const logoutOpen = ref(false)
const headerScrolled = ref(false)

const userNav: HeaderNavItem[] = [
  { label: '首页', to: '/', icon: 'i-lucide-house' },
  { label: '岗位探索', to: '/jobs', icon: 'i-lucide-briefcase-business' },
  { label: '能力画像', to: '/profile', icon: 'i-lucide-radar' },
  { label: '性格测试', to: '/personality', icon: 'i-lucide-brain' },
  { label: '人岗匹配', to: '/match', icon: 'i-lucide-target' },
  { label: '职业图谱', to: '/graph', icon: 'i-lucide-network' },
  { label: '生涯报告', to: '/report', icon: 'i-lucide-file-text' }
]

const adminNav: HeaderNavItem[] = [
  { label: '图谱管理', to: '/graph-admin', icon: 'i-lucide-database' },
  { label: '系统设置', to: '/graph-admin/settings', icon: 'i-lucide-settings' }
]

const accountLabel = computed(() => auth.user.value?.username || '个人中心')

const nav = computed(() => (auth.isAdmin.value ? adminNav : userNav).map(item => ({
  ...item,
  active: isNavActive(item.to)
})))

function isNavActive(to: string) {
  if (to === '/') return route.path === '/'
  if (to === '/graph-admin') return route.path === to || (route.path.startsWith('/graph-admin/') && !route.path.startsWith('/graph-admin/settings'))
  return route.path === to || route.path.startsWith(`${to}/`)
}

function syncHeaderScroll() {
  headerScrolled.value = window.scrollY > 8
}

async function logout() {
  logoutOpen.value = false
  mobileOpen.value = false
  auth.clear()
  await navigateTo('/')
}

onMounted(() => {
  auth.hydrate()
  syncHeaderScroll()
  window.addEventListener('scroll', syncHeaderScroll, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', syncHeaderScroll)
})

watch(() => route.fullPath, () => {
  mobileOpen.value = false
  if (import.meta.client) syncHeaderScroll()
})
</script>

<template>
  <header class="app-header" :class="{ 'is-scrolled': headerScrolled }">
    <div class="header-shell">
      <div class="header-bar">
        <NuxtLink to="/" class="brand-link" aria-label="PathFy 首页">
          <span class="brand-mark">
            <img src="/assets/home/fu.svg" alt="" class="size-7">
          </span>
          <span class="brand-copy">
            <span class="brand-name">PathFy</span>
            <span class="brand-subtitle">职业规划智能体</span>
          </span>
        </NuxtLink>

        <nav class="desktop-nav" aria-label="主导航">
          <NuxtLink
            v-for="item in nav"
            :key="item.to"
            :to="item.to"
            class="nav-pill"
            :class="{ 'is-active': item.active }"
            :aria-current="item.active ? 'page' : undefined"
          >
            <UIcon :name="item.icon" class="size-4 shrink-0" />
            <span>{{ item.label }}</span>
          </NuxtLink>
        </nav>

        <div class="header-actions">
          <div class="utility-group" aria-label="外观设置">
            <LightDarkSwitch />
            <ThemePreferences />
          </div>

          <UButton
            v-if="auth.isAuthenticated.value"
            to="/account"
            color="neutral"
            variant="ghost"
            icon="i-lucide-user-round"
            class="account-entry desktop-auth-action"
          >
            {{ accountLabel }}
          </UButton>
          <UButton
            v-if="auth.isAuthenticated.value"
            color="neutral"
            variant="soft"
            icon="i-lucide-log-out"
            class="desktop-auth-action"
            @click="() => { logoutOpen = true }"
          >
            退出
          </UButton>
          <UButton v-else to="/login" icon="i-lucide-log-in" class="desktop-auth-action">
            登录
          </UButton>
          <UButton
            class="mobile-menu-button"
            icon="i-lucide-menu"
            color="neutral"
            variant="ghost"
            aria-label="打开导航"
            @click="() => { mobileOpen = true }"
          />
        </div>
      </div>
    </div>
  </header>

  <USlideover
    v-model:open="mobileOpen"
    title="导航"
    :ui="{ content: 'sm:max-w-sm', body: 'p-0' }"
  >
    <template #body>
      <div class="mobile-panel">
        <div class="mobile-panel-head">
          <div class="mobile-mark">
            <img src="/assets/home/fu.svg" alt="" class="size-7">
          </div>
          <div>
            <p class="text-sm font-semibold">PathFy</p>
            <p class="text-xs muted">选择一个入口继续规划</p>
          </div>
        </div>

        <nav class="mobile-nav" aria-label="移动端导航">
          <NuxtLink
            v-for="item in nav"
            :key="item.to"
            :to="item.to"
            class="mobile-nav-link"
            :class="{ 'is-active': item.active }"
            :aria-current="item.active ? 'page' : undefined"
            @click="() => { mobileOpen = false }"
          >
            <UIcon :name="item.icon" class="size-4 shrink-0" />
            <span>{{ item.label }}</span>
            <UIcon name="i-lucide-chevron-right" class="ml-auto size-4 opacity-45" />
          </NuxtLink>
        </nav>

        <div class="mobile-account">
          <UButton
            v-if="auth.isAuthenticated.value"
            to="/account"
            icon="i-lucide-user-round"
            color="neutral"
            variant="soft"
            block
            @click="() => { mobileOpen = false }"
          >
            {{ accountLabel }}
          </UButton>
          <UButton
            v-if="auth.isAuthenticated.value"
            icon="i-lucide-log-out"
            color="error"
            variant="ghost"
            block
            @click="() => { logoutOpen = true; mobileOpen = false }"
          >
            退出
          </UButton>
          <UButton v-else to="/login" icon="i-lucide-log-in" block @click="() => { mobileOpen = false }">
            登录
          </UButton>
        </div>
      </div>
    </template>
  </USlideover>

  <UModal v-model:open="logoutOpen" title="确认退出登录">
    <template #body>
      <p class="muted">退出后会清除本机保存的登录状态和当前用户缓存。</p>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton color="neutral" variant="ghost" @click="() => { logoutOpen = false }">取消</UButton>
        <UButton color="error" icon="i-lucide-log-out" @click="logout">确认退出</UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  padding: 0.65rem max(1rem, env(safe-area-inset-left)) 0.45rem;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--ui-bg) 88%, transparent), transparent);
  transition: padding 180ms ease, transform 180ms ease;
}

.header-shell {
  width: min(100%, 78rem);
  margin: 0 auto;
}

.header-bar {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.75rem;
  min-height: 4rem;
  border: 1px solid color-mix(in srgb, var(--ui-border) 82%, transparent);
  border-radius: 1rem;
  background: color-mix(in srgb, var(--ui-bg) 88%, transparent);
  padding: 0.45rem;
  box-shadow: 0 18px 42px -34px rgb(15 23 42 / 0.52);
  backdrop-filter: blur(18px) saturate(1.2);
  transition: min-height 180ms ease, border-color 180ms ease, background 180ms ease, box-shadow 180ms ease;
}

.app-header.is-scrolled {
  padding-top: 0.45rem;
}

.app-header.is-scrolled .header-bar {
  min-height: 3.55rem;
  border-color: color-mix(in srgb, var(--ui-primary) 20%, var(--ui-border));
  background: color-mix(in srgb, var(--ui-bg) 94%, transparent);
  box-shadow: 0 16px 36px -30px rgb(15 23 42 / 0.72);
}

.brand-link {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.65rem;
  border-radius: 0.75rem;
  padding: 0.4rem 0.55rem;
  color: var(--ui-text);
  text-decoration: none;
  transition: background 160ms ease, transform 160ms ease;
}

.brand-link:hover {
  background: color-mix(in srgb, var(--ui-primary) 8%, transparent);
}

.brand-link:active {
  transform: scale(0.98);
}

.brand-mark,
.mobile-mark {
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 0.75rem;
  background: color-mix(in srgb, var(--ui-primary) 12%, var(--ui-bg));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ui-primary) 20%, transparent);
}

.brand-copy {
  display: grid;
  min-width: 0;
  gap: 0.05rem;
}

.brand-name {
  font-size: 1rem;
  line-height: 1.15rem;
  font-weight: 750;
}

.brand-subtitle {
  max-width: 7.5rem;
  overflow: hidden;
  color: var(--ui-text-muted);
  font-size: 0.72rem;
  line-height: 0.9rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.desktop-nav {
  display: none;
  min-width: 0;
  justify-content: center;
  gap: 0.15rem;
}

.nav-pill {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-height: 2.5rem;
  border-radius: 0.7rem;
  padding: 0 0.62rem;
  color: var(--ui-text-muted);
  font-size: 0.86rem;
  font-weight: 600;
  text-decoration: none;
  transition: color 160ms ease, background 160ms ease, transform 160ms ease;
}

.nav-pill::after {
  content: "";
  position: absolute;
  right: 0.72rem;
  bottom: 0.38rem;
  left: 0.72rem;
  height: 2px;
  border-radius: 999px;
  background: var(--ui-primary);
  opacity: 0;
  transform: scaleX(0.3);
  transition: opacity 160ms ease, transform 160ms ease;
}

.nav-pill:hover {
  background: color-mix(in srgb, var(--ui-primary) 7%, transparent);
  color: var(--ui-text);
}

.nav-pill.is-active {
  background: color-mix(in srgb, var(--ui-primary) 11%, transparent);
  color: var(--ui-primary);
}

.nav-pill.is-active::after {
  opacity: 1;
  transform: scaleX(1);
}

.header-actions {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  justify-content: flex-end;
  gap: 0.35rem;
}

.utility-group {
  display: inline-flex;
  align-items: center;
  gap: 0.1rem;
  border-radius: 0.8rem;
  background: color-mix(in srgb, var(--ui-bg-elevated) 72%, transparent);
  padding: 0.12rem;
}

.account-entry {
  max-width: 8.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.desktop-auth-action {
  display: none;
}

.mobile-menu-button {
  display: inline-flex;
}

.mobile-panel {
  display: grid;
  gap: 1rem;
  padding: 1rem;
}

.mobile-panel-head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  border-bottom: 1px solid var(--ui-border);
  padding-bottom: 1rem;
}

.mobile-nav {
  display: grid;
  gap: 0.35rem;
}

.mobile-nav-link {
  position: relative;
  display: flex;
  min-height: 2.75rem;
  align-items: center;
  gap: 0.65rem;
  border: 1px solid transparent;
  border-radius: 0.75rem;
  padding: 0 0.75rem;
  color: var(--ui-text-muted);
  font-size: 0.95rem;
  font-weight: 600;
  text-decoration: none;
  transition: color 160ms ease, border-color 160ms ease, background 160ms ease;
}

.mobile-nav-link::before {
  content: "";
  width: 3px;
  height: 1.35rem;
  border-radius: 999px;
  background: var(--ui-primary);
  opacity: 0;
  transform: scaleY(0.45);
  transition: opacity 160ms ease, transform 160ms ease;
}

.mobile-nav-link:hover,
.mobile-nav-link.is-active {
  border-color: color-mix(in srgb, var(--ui-primary) 22%, transparent);
  background: color-mix(in srgb, var(--ui-primary) 8%, transparent);
  color: var(--ui-primary);
}

.mobile-nav-link.is-active::before {
  opacity: 1;
  transform: scaleY(1);
}

.mobile-account {
  display: grid;
  gap: 0.5rem;
  border-top: 1px solid var(--ui-border);
  padding-top: 1rem;
}

@media (min-width: 1180px) {
  .desktop-nav {
    display: flex;
  }

  .mobile-menu-button {
    display: none;
  }
}

@media (min-width: 640px) {
  .desktop-auth-action {
    display: inline-flex;
  }
}

@media (max-width: 720px) {
  .app-header {
    padding-right: 0.75rem;
    padding-left: 0.75rem;
  }

  .header-bar {
    grid-template-columns: minmax(0, 1fr) auto;
    min-height: 3.65rem;
  }

  .brand-subtitle {
    display: none;
  }

  .utility-group {
    background: transparent;
    padding: 0;
  }
}

@media (max-width: 420px) {
  .brand-link {
    gap: 0.45rem;
    padding-right: 0.3rem;
    padding-left: 0.35rem;
  }

  .brand-name {
    font-size: 0.95rem;
  }

  .header-actions {
    gap: 0.1rem;
  }
}
</style>
