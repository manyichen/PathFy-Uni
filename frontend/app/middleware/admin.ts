export default defineNuxtRouteMiddleware(() => {
  if (!import.meta.client) return
  const auth = useAuth()
  auth.hydrate()
  if (!auth.isAuthenticated.value) return navigateTo('/login')
  if (!auth.isAdmin.value) return navigateTo('/')
})
