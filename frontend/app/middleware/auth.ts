export default defineNuxtRouteMiddleware((to) => {
  if (!import.meta.client) return
  const auth = useAuth()
  auth.hydrate()
  if (!auth.isAuthenticated.value) return navigateTo(`/login?redirect=${encodeURIComponent(to.fullPath)}`)
})
