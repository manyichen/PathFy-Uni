import { adminHeaderNavigation, isHeaderNavActive, userHeaderNavigation, type HeaderNavItem } from '~/types/navigation'

export function useHeaderController() {
  const auth = useAuth()
  const route = useRoute()
  const mobileOpen = ref(false)
  const logoutOpen = ref(false)
  const headerScrolled = ref(false)
  const accountLabel = computed(() => auth.user.value?.username || '个人中心')
  const nav = computed<HeaderNavItem[]>(() => (auth.isAdmin.value ? adminHeaderNavigation : userHeaderNavigation).map(item => ({ ...item, active: isHeaderNavActive(route.path, item.to) })))

  function syncScroll() {
    headerScrolled.value = window.scrollY > 8
  }

  function requestLogout() {
    mobileOpen.value = false
    logoutOpen.value = true
  }

  async function logout() {
    logoutOpen.value = false
    mobileOpen.value = false
    auth.clear()
    await navigateTo('/')
  }

  onMounted(() => {
    auth.hydrate()
    syncScroll()
    window.addEventListener('scroll', syncScroll, { passive: true })
  })
  onBeforeUnmount(() => window.removeEventListener('scroll', syncScroll))
  watch(() => route.fullPath, () => {
    mobileOpen.value = false
    if (import.meta.client) syncScroll()
  })

  return { auth, mobileOpen, logoutOpen, headerScrolled, accountLabel, nav, requestLogout, logout }
}
